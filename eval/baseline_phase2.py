"""Phase 2 baseline — 15 cases: 10 single-turn regression + 5 multi-turn scenarios.

Regression reuses the Phase 1 cases unchanged (no session) — Phase 2 must not regress
single-turn behavior. The 5 scenarios test that the agent USES prior turns, not just that
history exists: confirmation flow, info carryover, context-enriched escalation, mid-convo
correction, and multi-topic efficiency (reuse loaded data without re-calling tools).

Each scenario check is HARD (must pass for the scenario to pass) or SOFT (reported, model-
dependent). Run: python eval/baseline_phase2.py  ->  eval/baseline_phase2.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from novacrm_agent import config              # noqa: E402
from novacrm_agent.orchestrator import SupportAgent  # noqa: E402
from novacrm_agent.session import new_session        # noqa: E402
from baseline_phase1 import CASES, score             # noqa: E402


# --- helpers ----------------------------------------------------------------
def _txt(res):
    return (res.final_text or "").lower()


def _tool_out(res, name):
    for tc in res.tool_calls:
        if tc["name"] == name:
            return tc["output"] if isinstance(tc["output"], dict) else {}
    return None


def _tool_inputs(res, name):
    outs = []
    for tc in res.tool_calls:
        if tc["name"] == name:
            try:
                outs.append(json.loads(tc["arguments"] or "{}"))
            except (json.JSONDecodeError, TypeError):
                outs.append({})
    return outs


def chk(label, passed, hard=True, note=""):
    return {"label": label, "passed": bool(passed), "hard": hard, "note": note}


# --- scenarios --------------------------------------------------------------
def scenario_1(agent):
    """Confirm-then-create ticket (the Q4 flow, now multi-turn)."""
    s = new_session("s1-confirm-create")
    r2 = agent.run("My email sync has been broken for two days. Customer ID is CUST-1001.", session=s)
    r4 = agent.run("Yes, go ahead and create it.", session=s)
    out = _tool_out(r4, "create_support_ticket") or {}
    summ = (out.get("summary") or "").lower()
    # tightened: a closing "Is there anything else?" must not count as asking to confirm.
    # Require an actual confirmation-seeking phrase.
    confirm_phrases = ("shall i", "should i", "would you like", "want me to", "like me to",
                       "confirm", "go ahead", "proceed", "do you want")
    asks_confirm = any(p in _txt(r2) for p in confirm_phrases)
    # Outcome-based (D-Phase4): the safety property is "no ticket is actually CREATED before
    # confirmation", not "no call attempted". The model may attempt a create at t2; the
    # confirmation gate refuses it (created=False) — the both-defenses net. We assert nothing
    # was actually created. (Unguarded, a real premature creation has created=True and fails.)
    t2_created = any(tc["name"] == "create_support_ticket" and (tc["output"] or {}).get("created")
                    for tc in r2.tool_calls)
    return "S1", "confirm-then-create ticket", [
        chk("t2 does NOT actually create a ticket before confirming", not t2_created),
        chk("t2 actually asks to confirm (not just a closing question)", asks_confirm),
        chk("t4 creates the ticket after 'yes'", "create_support_ticket" in r4.tool_names()),
        chk("ticket summary references the original issue (email/sync)",
            ("email" in summ or "sync" in summ), note=f"summary={summ!r}"),
    ]


def scenario_2(agent):
    """Information carryover — plan stated once, used later."""
    s = new_session("s2-carryover")
    r2 = agent.run("I'm on the Starter plan. Can I set up a Zapier integration?", session=s)
    r4 = agent.run("What about Slack?", session=s)
    reasked = any(p in _txt(r4) for p in ("what plan", "which plan", "what tier", "which tier", "your current plan"))
    return "S2", "information carryover (plan context)", [
        chk("t2 says Zapier needs Enterprise", "enterprise" in _txt(r2), hard=False),
        chk("t4 says Slack needs Professional", "professional" in _txt(r4)),
        chk("t4 does NOT re-ask the plan tier", not reasked),
    ]


def scenario_3(agent):
    """Escalation enriched with earlier account context."""
    s = new_session("s3-context-escalation")
    r2 = agent.run("Customer ID CUST-1004. What's going on with my account?", session=s)
    r4 = agent.run("This is ridiculous. I want a refund for last month.", session=s)
    esc = _tool_out(r4, "escalate_to_team") or {}
    reason = (esc.get("reason") or "").lower()
    return "S3", "context-enriched escalation", [
        chk("t2 looks up the account", "get_account_info" in r2.tool_names()),
        chk("t2 notes the overdue/payment status",
            any(w in _txt(r2) for w in ("overdue", "past due", "payment")), hard=False),
        chk("t4 escalates to billing", esc.get("team") == "billing"),
        chk("escalation reason references account context (overdue/payment)",
            any(w in reason for w in ("overdue", "payment", "past due")), hard=False,
            note=f"reason={reason!r}"),
    ]


def scenario_4(agent):
    """Mid-conversation correction — no bleed between accounts."""
    s = new_session("s4-correction")
    r2 = agent.run("I need help with my account. Customer ID is CUST-1002.", session=s)
    r4 = agent.run("Actually sorry, wrong ID. It's CUST-1003.", session=s)
    ids = [i.get("customer_id", "").upper() for i in _tool_inputs(r4, "get_account_info")]
    return "S4", "mid-conversation correction", [
        chk("t2 greets the first account (Marcus/Brightside)",
            any(w in _txt(r2) for w in ("marcus", "brightside")), hard=False),
        chk("t4 looks up the corrected account CUST-1003", "CUST-1003" in ids),
        chk("t4 references the right account (Priya/Cobalt)",
            any(w in _txt(r4) for w in ("priya", "cobalt"))),
        chk("t4 has NO bleed from the first account (no Marcus/Brightside)",
            not any(w in _txt(r4) for w in ("marcus", "brightside"))),
    ]


def scenario_5(agent):
    """Multi-topic — reuse loaded account data without re-calling the tool."""
    s = new_session("s5-multitopic")
    r2 = agent.run("How do I generate an API key? I'm CUST-1003.", session=s)
    r4 = agent.run("Thanks. Also, can you tell me how much storage I'm using?", session=s)
    r6 = agent.run("One more thing — I need to export all our data for an audit.", session=s)
    loaded_at_t2 = "get_account_info" in r2.tool_names()
    return "S5", "multi-topic efficiency", [
        chk("t2 loads the account (precondition for reuse)", loaded_at_t2, hard=False),
        chk("t4 reuses storage figure (312.7) from history", "312.7" in _txt(r4)),
        # SOFT (D11): re-fetching authoritative account state (storage/plan/billing) live is
        # CORRECT per D5's non-shadow rule — so this is reported, not gating. The check above
        # already proves history carries the data; re-verifying live is a non-failure.
        chk("t4 reuses without re-calling get_account_info (efficiency, optional)",
            "get_account_info" not in r4.tool_names(), hard=False),
        chk("t6 explains data export", "export" in _txt(r6)),
        # relaxed: export-for-audit is self-service, NOT a GDPR deletion, so routing it to
        # compliance would be WRONG. Correct behavior = explain export, don't over-escalate.
        chk("t6 handles audit correctly (explains export, no wrong compliance escalation)",
            "export" in _txt(r6) and (_tool_out(r6, "escalate_to_team") or {}).get("team") != "compliance",
            hard=False),
    ]


SCENARIOS = [scenario_1, scenario_2, scenario_3, scenario_4, scenario_5]


def main() -> int:
    if not config.OPENROUTER_API_KEY:
        print("BLOCKED: OPENROUTER_API_KEY is not set (see .env.example).")
        return 2

    agent = SupportAgent()

    # --- regression (single-turn, no session) ---
    print(f"Phase 2 baseline — model: {config.PRIMARY_MODEL}\n")
    print("Regression (Phase 1 cases):")
    reg_results, reg_pass = [], 0
    for case in CASES:
        res = agent.run(case["msg"], customer_id=case["customer"])
        ok, note = score(case, res)
        reg_pass += ok
        reg_results.append({"id": case["id"], "category": case["category"], "passed": ok, "note": note})
        print(f"  [{'PASS' if ok else 'FAIL'}] {case['id']} {case['category']:<20} {note}")

    # --- multi-turn scenarios ---
    print("\nMulti-turn scenarios:")
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

    total = len(CASES) + len(SCENARIOS)
    passed = reg_pass + scn_pass
    summary = {
        "model": config.PRIMARY_MODEL,
        "total": total, "passed": passed, "pass_rate": round(passed / total, 3),
        "regression": {"total": len(CASES), "passed": reg_pass, "results": reg_results},
        "scenarios": {"total": len(SCENARIOS), "passed": scn_pass, "results": scn_results},
    }
    out = Path(__file__).resolve().parent / "baseline_phase2.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nRegression {reg_pass}/{len(CASES)} · Scenarios {scn_pass}/{len(SCENARIOS)} · "
          f"Total {passed}/{total} ({summary['pass_rate']:.0%}). Wrote {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
