"""Phase 1 reliability baseline — measure BEFORE building memory/guardrails on top.

Same discipline as Project 1: characterize the foundation first. This measures whether
GLM-4.7-Flash has the tool-call discipline the support task needs — does it call the
right tool, escalate to the right team, decline out-of-scope, and ask before guessing —
across 10 queries spanning the categories in the plan.

Scoring is deterministic/structural (no LLM judge yet; that's Phase 6). Each case
declares what it expects; we check the actual tool calls against it.

Run:  python eval/baseline_phase1.py
Out:  eval/baseline_phase1.json  (+ console summary)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from novacrm_agent import config              # noqa: E402
from novacrm_agent.orchestrator import SupportAgent  # noqa: E402

# id, category, message, customer_id, expectation
CASES = [
    {"id": "Q1", "category": "factual-kb",
     "msg": "How much does the Professional plan cost?", "customer": None,
     "expect": {"tools": ["lookup_knowledge_base"]}},
    {"id": "Q2", "category": "account-lookup",
     "msg": "What plan is my account on?", "customer": "CUST-1001",
     "expect": {"tools": ["get_account_info"]}},
    {"id": "Q3", "category": "how-to-kb",
     "msg": "How do I generate an API key?", "customer": None,
     "expect": {"tools": ["lookup_knowledge_base"]}},
    # The prompt mandates "confirm the summary with the customer before creating",
    # so the single-turn-correct behavior is: gather context + propose + ask to confirm,
    # NOT create the ticket yet. Actual creation is a Phase 2 multi-turn follow-up.
    {"id": "Q4", "category": "multi-step",
     "msg": "My dashboard won't load at all and I can't work. Can you log a ticket?",
     "customer": "CUST-1003", "expect": {"confirm_first": True}},
    {"id": "Q5", "category": "escalation-refund",
     "msg": "I want a refund for this month, please process it.", "customer": "CUST-1002",
     "expect": {"escalate_team": "billing"}},
    {"id": "Q6", "category": "escalation-cancel",
     "msg": "I need to cancel my account.", "customer": "CUST-1001",
     "expect": {"escalate_team": "retention"}},
    {"id": "Q7", "category": "escalation-gdpr",
     "msg": "Under GDPR I want all my personal data deleted.", "customer": "CUST-1004",
     "expect": {"escalate_team": "compliance"}},
    {"id": "Q8", "category": "escalation-abuse",
     "msg": "This product is absolute garbage and I'm going to sue you.", "customer": "CUST-1004",
     "expect": {"escalate_team": "supervisor"}},
    {"id": "Q9", "category": "out-of-scope",
     "msg": "What's the weather in Toronto today?", "customer": None,
     "expect": {"no_tools": True, "decline": True}},
    {"id": "Q10", "category": "ambiguous",
     "msg": "It's broken.", "customer": "CUST-1001",
     "expect": {"clarify": True}},
]

DECLINE_HINTS = ("can't help", "cannot help", "only", "unable", "not able", "outside", "don't have",
                 "i'm not", "i am not", "support for novacrm", "novacrm")


def score(case: dict, res) -> tuple[bool, str]:
    exp = case["expect"]
    tools = res.tool_names()

    if "tools" in exp:
        missing = [t for t in exp["tools"] if t not in tools]
        if missing:
            return False, f"expected tool(s) {missing} not called (called {tools or 'none'})"
        return True, "ok"

    if "escalate_team" in exp:
        esc = [tc for tc in res.tool_calls if tc["name"] == "escalate_to_team"]
        if not esc:
            return False, f"no escalation (called {tools or 'none'})"
        team = (esc[0]["output"] or {}).get("team")
        if team != exp["escalate_team"]:
            return False, f"escalated to {team!r}, expected {exp['escalate_team']!r}"
        return True, "ok"

    if exp.get("no_tools"):
        if tools:
            return False, f"called tools on out-of-scope query: {tools}"
        if exp.get("decline") and not any(h in res.final_text.lower() for h in DECLINE_HINTS):
            return False, "did not clearly decline out-of-scope query"
        return True, "ok"

    if exp.get("confirm_first"):
        if any(tc["name"] in ("create_support_ticket", "escalate_to_team") for tc in res.tool_calls):
            return False, "acted (created/escalated) without confirming with the customer first"
        if "?" not in res.final_text:
            return False, "did not ask the customer to confirm before acting"
        return True, "ok (proposed + confirmed before creating, per prompt)"

    if exp.get("clarify"):
        if any(tc["name"] in ("create_support_ticket", "escalate_to_team") for tc in res.tool_calls):
            return False, "acted on an ambiguous request instead of asking"
        if "?" not in res.final_text:
            return False, "did not ask a clarifying question"
        return True, "ok"

    return False, "no expectation defined"


def main() -> int:
    if not config.OPENROUTER_API_KEY:
        print("BLOCKED: OPENROUTER_API_KEY is not set.\n"
              "Add it to .env (see .env.example), then re-run:\n"
              "  python eval/baseline_phase1.py")
        return 2

    agent = SupportAgent()
    results = []
    passed = 0
    print(f"Phase 1 baseline — model: {config.PRIMARY_MODEL}\n")
    for case in CASES:
        res = agent.run(case["msg"], customer_id=case["customer"])
        ok, note = score(case, res)
        passed += ok
        results.append({
            "id": case["id"], "category": case["category"], "passed": ok, "note": note,
            "tools_used": res.tool_names(), "iterations": res.iterations,
            "tokens": res.tracer.total_tokens() if res.tracer else None,
            "hit_max_iters": res.hit_max_iters,
            "final_text": res.final_text,
        })
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {case['id']} {case['category']:<20} {note}")

    summary = {
        "model": config.PRIMARY_MODEL,
        "total": len(CASES),
        "passed": passed,
        "pass_rate": round(passed / len(CASES), 3),
        "avg_iterations": round(sum(r["iterations"] for r in results) / len(results), 2),
        "total_tokens": sum((r["tokens"] or 0) for r in results),
        "results": results,
    }
    out = Path(__file__).resolve().parent / "baseline_phase1.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n{passed}/{len(CASES)} passed ({summary['pass_rate']:.0%}). Wrote {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
