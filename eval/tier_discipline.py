"""Phase 3 (grounding & routing discipline) — the RC3 seam, turned into a HARD measured gate.

The Phase-2 routing baseline flagged, anecdotally, that for a tier-dependent doc question with a
known customer ("what integrations does MY plan support?") the coordinator SOMETIMES answers from
the docs without first confirming the customer's tier via `get_account_info`. Intermittent = it
passes on some model rolls and fails on others. A single-shot case can't see that.

This eval makes the seam measurable instead of anecdotal:
  - a fixed set of TIER-DEPENDENT questions, each with an authenticated customer_id;
  - each run REPS times (default 5) so the flicker shows as a pass-RATE, not a coin flip;
  - a hard assertion on the TRACE (not the prose): for the answer to be tier-correct the coordinator
    MUST have called `get_account_info` BEFORE or ALONGSIDE the `nova_docs` delegation — i.e.
    account context is established before (or with) the doc lookup, never after.

Gate: discipline rate == 100% (every rep of every case establishes account context before/with the
doc lookup). Before the Phase-3 routing-discipline fix this is expected to flicker below 100%;
after, it must be a clean 10/10-style pass or the router prompt still needs tightening.

Run:  python eval/tier_discipline.py [--provider openrouter|groq] [--reps N]
Out:  eval/tier_discipline.json  (+ console summary)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from novacrm_agent.agents.coordinator import NovaCoordinator  # noqa: E402
from novacrm_agent.session import new_session                 # noqa: E402

NEG_MARKERS = ["no", "not", "only", "n't", "cannot", "require", "upgrade", "unavailable",
               "enterprise-only", "enterprise only", "starter"]

# Each question is tier-dependent: a correct, customer-specific answer needs the caller's PLAN
# (from get_account_info) AND the tier→availability fact (from nova_docs). id, question, customer,
# tier, expect_all (facts a grounded answer carries), expect_negate (a limiting phrase, for the
# cases where the customer's tier makes the answer "no/upgrade").
CASES = [
    {"id": "T1", "q": "What integrations does my plan support?", "customer": "CUST-1001",
     "tier": "Professional", "expect_all": ["slack", "gmail"]},
    {"id": "T2", "q": "Can I use the API on my current plan?", "customer": "CUST-1002",
     "tier": "Starter", "expect_all": ["professional"], "expect_negate": True},
    {"id": "T3", "q": "Can I use Zapier on my plan?", "customer": "CUST-1001",
     "tier": "Professional", "expect_all": ["enterprise"], "expect_negate": True},
    {"id": "T4", "q": "Does my plan include custom webhooks?", "customer": "CUST-1004",
     "tier": "Professional", "expect_all": ["enterprise"], "expect_negate": True},
    {"id": "T5", "q": "What's my hourly API rate limit on my plan?", "customer": "CUST-1003",
     "tier": "Enterprise", "expect_all": ["10,000"]},
]


def _discipline_ok(route: list[str]) -> tuple[bool, str]:
    """True iff get_account_info was called before or alongside the nova_docs delegation."""
    if "get_account_info" not in route:
        return False, "no_account_lookup"
    if "nova_docs" not in route:
        return False, "no_doc_delegation"
    if route.index("get_account_info") > route.index("nova_docs"):
        return False, "account_after_docs"
    return True, "ok"


def _answer_ok(case: dict, ans: str) -> bool:
    ok = all(f.lower() in ans for f in case.get("expect_all", []))
    if case.get("expect_negate"):
        ok = ok and any(m in ans for m in NEG_MARKERS)
    return ok


def main() -> None:
    ap = argparse.ArgumentParser(description="Phase 3 tier-discipline eval (RC3 hardened).")
    ap.add_argument("--provider", choices=["openrouter", "groq"], default="openrouter")
    ap.add_argument("--reps", type=int, default=5)
    args = ap.parse_args()

    label = "GLM-4.7-Flash (openrouter)" if args.provider == "openrouter" else "Llama-4-Scout (groq)"
    print(f"Coordinator model: {label} | reps={args.reps}\n")
    nova = NovaCoordinator(provider=args.provider)

    rows = []
    for case in CASES:
        reps = []
        for i in range(args.reps):
            sess = new_session(f"td-{case['id']}-{i}", user_id=case["customer"])
            r = nova.run(case["q"], customer_id=case["customer"], session=sess)
            disc_ok, reason = _discipline_ok(r.route)
            reps.append({"route": r.route, "discipline_ok": disc_ok, "reason": reason,
                         "answer_ok": _answer_ok(case, (r.final_text or "").lower())})
        disc_pass = sum(x["discipline_ok"] for x in reps)
        ans_pass = sum(x["answer_ok"] for x in reps)
        rows.append({"id": case["id"], "question": case["q"], "customer": case["customer"],
                     "tier": case["tier"], "reps": reps,
                     "discipline_pass": disc_pass, "answer_pass": ans_pass, "n": args.reps})
        print(f"  {case['id']}  discipline {disc_pass}/{args.reps}  answer {ans_pass}/{args.reps}"
              f"  reasons={sorted({x['reason'] for x in reps})}")

    total = sum(r["n"] for r in rows)
    disc_rate = sum(r["discipline_pass"] for r in rows) / total
    ans_rate = sum(r["answer_pass"] for r in rows) / total
    # a case is "flickering" if it neither always passes nor always fails discipline
    flickering = [r["id"] for r in rows if 0 < r["discipline_pass"] < r["n"]]

    print(f"\n=== Phase 3 tier-discipline ({total} runs) ===")
    print(f"Discipline rate (account before/with docs): {disc_rate:.0%}  "
          f"({sum(r['discipline_pass'] for r in rows)}/{total})")
    print(f"Answer accuracy:                            {ans_rate:.0%}")
    print(f"Flickering cases: {flickering or 'none'}")
    gate = disc_rate == 1.0
    print(f"GATE (discipline == 100%): {'PASS' if gate else 'REVIEW'}")

    out = Path(__file__).resolve().parent / "tier_discipline.json"
    out.write_text(json.dumps({
        "summary": {"model": label, "reps": args.reps, "discipline_rate": disc_rate,
                    "answer_rate": ans_rate, "flickering": flickering, "gate": gate},
        "cases": rows,
    }, indent=2), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
