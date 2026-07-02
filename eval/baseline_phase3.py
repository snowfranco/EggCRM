"""Phase 3 baseline — cross-session memory + regression.

Three two-session scenarios (X1-X3): Session 1 -> extract -> store, then a fresh Session 2
-> retrieve -> recall. The decisive checks for X3 are at the STORE level (inspect the JSON),
not the response level: extraction could store an excluded fact and the agent simply not
mention it — a response check would miss that, the store check won't (D5 non-shadow).

Regression: the full 15-case Phase 2 baseline must still pass (memory must not regress it).

Run: python eval/baseline_phase3.py  ->  eval/baseline_phase3.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from novacrm_agent import config                       # noqa: E402
from novacrm_agent.memory import store                 # noqa: E402
from novacrm_agent.orchestrator import SupportAgent    # noqa: E402
from novacrm_agent.session import new_session          # noqa: E402
from baseline_phase1 import CASES, score               # noqa: E402
from baseline_phase2 import SCENARIOS as P2_SCENARIOS  # noqa: E402


def chk(label, passed, hard=True, note=""):
    return {"label": label, "passed": bool(passed), "hard": hard, "note": note}


def _reset(customer_id):
    p = _ROOT / "data" / "memory_store" / f"{customer_id}.json"
    if p.exists():
        p.unlink()


def _txt(res):
    return (res.final_text or "").lower()


def _stored(customer_id):
    return store.load(customer_id)


# --- X1: issue recall -------------------------------------------------------
def x1(agent):
    cid = "CUST-1003"
    _reset(cid)
    s1 = new_session("x1-s1", user_id=cid)
    agent.run("Hi, it's Priya at Cobalt. The dashboard keeps crashing every morning — it's really disrupting our standup.", session=s1)
    agent.run("Yes please, go ahead and log it.", session=s1)
    agent.end_session(s1)
    mems = _stored(cid)
    has_issue = any(m.topic.value == "issue_history" and ("dashboard" in m.fact.lower() or "crash" in m.fact.lower()) for m in mems)

    s2 = new_session("x1-s2", user_id=cid)
    r = agent.run("Any update on my bug?", session=s2)
    return "X1", "issue recall across sessions", [
        chk("S1 stored an issue_history memory about the dashboard crash", has_issue),
        chk("S2 recalls the specific dashboard/crash issue",
            ("dashboard" in _txt(r) or "crash" in _txt(r)), note=f"reply={_txt(r)[:90]!r}"),
        chk("S2 tone reflects prior frustration",
            any(w in _txt(r) for w in ("sorry", "apolog", "frustrat", "disrupt", "understand")), hard=False),
    ]


# --- X2: communication preference honored -----------------------------------
def x2(agent):
    cid = "CUST-1001"
    _reset(cid)
    s1 = new_session("x2-s1", user_id=cid)
    agent.run("Quick question on API keys — and going forward, please contact me by email, not phone.", session=s1)
    agent.end_session(s1)
    mems = _stored(cid)
    has_pref = any(m.topic.value == "communication_preferences" and "email" in m.fact.lower() for m in mems)

    s2 = new_session("x2-s2", user_id=cid)
    r = agent.run("My email integration keeps disconnecting. Can you follow up once it's fixed?", session=s2)
    return "X2", "comms preference honored across sessions", [
        chk("S1 stored a communication_preferences memory (email)", has_pref),
        chk("S2 offers to follow up by email (honors stored preference)", "email" in _txt(r),
            note=f"reply={_txt(r)[:90]!r}"),
        chk("S2 does not re-ask preferred contact method",
            not any(p in _txt(r) for p in ("how would you like", "preferred contact", "by phone or email", "how can i reach")),
            hard=False),
    ]


# --- X3: relationship continuity + store-level exclusion (the D5 test) -------
_DOLLAR = re.compile(r"\$\s?\d|\b480\b")


def x3(agent):
    cid = "CUST-1004"
    _reset(cid)
    s1 = new_session("x3-s1", user_id=cid)
    agent.run("It's Tom at Delta. I was charged $480 twice this quarter and I'm pretty fed up — second billing problem in a row.", session=s1)
    agent.end_session(s1)
    mems = _stored(cid)
    facts = [m.fact.lower() for m in mems]
    has_sentiment = any(m.topic.value == "sentiment_trajectory" for m in mems)
    leaks_amount = any(_DOLLAR.search(f) for f in facts)
    leaks_status = any(("payment_overdue" in f or "overdue" in f) for f in facts)

    s2 = new_session("x3-s2", user_id=cid)
    r = agent.run("I need help setting up a new workflow automation.", session=s2)
    return "X3", "continuity + store-level exclusion (D5)", [
        chk("S1 stored a sentiment_trajectory memory (billing frustration)", has_sentiment),
        chk("STORE excludes the dollar amount ($480) — checked in the JSON, not the reply",
            not leaks_amount, note=f"facts={facts}"),
        chk("STORE excludes the payment_overdue/overdue status — checked in the JSON",
            not leaks_status),
        chk("S2 helps with the workflow request on-topic",
            any(w in _txt(r) for w in ("workflow", "automation", "settings")), note=f"reply={_txt(r)[:90]!r}"),
        chk("S2 shows continuity / extra care given prior frustration",
            any(w in _txt(r) for w in ("appreciate", "thanks for", "sorry", "understand", "patience", "frustrat")), hard=False),
    ]


SCENARIOS = [x1, x2, x3]


def main() -> int:
    if not config.OPENROUTER_API_KEY:
        print("BLOCKED: OPENROUTER_API_KEY is not set (see .env.example).")
        return 2

    agent = SupportAgent()

    # --- regression: full 15-case Phase 2 baseline ---
    print(f"Phase 3 baseline — model: {config.PRIMARY_MODEL}\n")
    print("Regression (15-case Phase 2 baseline):")
    reg_pass = 0
    for case in CASES:
        res = agent.run(case["msg"], customer_id=case["customer"])
        ok, _ = score(case, res)
        reg_pass += ok
    for fn in P2_SCENARIOS:
        _, _, checks = fn(agent)
        reg_pass += all(c["passed"] for c in checks if c["hard"])
    reg_total = len(CASES) + len(P2_SCENARIOS)
    print(f"  {reg_pass}/{reg_total} passed")

    # --- cross-session scenarios ---
    print("\nCross-session scenarios:")
    scn_results, scn_pass = [], 0
    for fn in SCENARIOS:
        sid, title, checks = fn(agent)
        hard_ok = all(c["passed"] for c in checks if c["hard"])
        scn_pass += hard_ok
        scn_results.append({"id": sid, "title": title, "passed": hard_ok, "checks": checks})
        print(f"  [{'PASS' if hard_ok else 'FAIL'}] {sid} {title}")
        for c in checks:
            tag = "hard" if c["hard"] else "soft"
            mark = "ok " if c["passed"] else "XX "
            extra = f"  ({c['note']})" if c["note"] else ""
            print(f"        {mark}[{tag}] {c['label']}{extra}")

    summary = {
        "model": config.PRIMARY_MODEL,
        "regression": {"total": reg_total, "passed": reg_pass},
        "cross_session": {"total": len(SCENARIOS), "passed": scn_pass, "results": scn_results},
    }
    out = Path(__file__).resolve().parent / "baseline_phase3.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nRegression {reg_pass}/{reg_total} · Cross-session {scn_pass}/{len(SCENARIOS)}. Wrote {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
