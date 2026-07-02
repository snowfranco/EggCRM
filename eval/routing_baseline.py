"""Phase 2 routing baseline — measure the Nova COORDINATOR before optimizing retrieval (Phase 3).

Measure-before-proceeding, applied to the multi-agent layer: characterize routing + delegation +
grounding on the coordinator BEFORE building Phase 3 on top. Runs on GLM-4.7-Flash via ADK's
LiteLlm by default (the ship model) — this is also the first official pass of the RAG agent on the
primary model, so a Scout-vs-GLM tool-call divergence would surface HERE, not mid-Phase-3.

The 10 cases (RC1-RC10) deliberately stress the ROUTING BOUNDARIES, not happy paths (the smoke test
already covered clean single-intent routing). Two anchors (RC1/RC2) confirm basic routing; the rest
sit on the seams where the coordinator earns its keep:
  - RC3 / RC7  : need BOTH account tier (account tool) AND doc availability (RAG) in one answer.
  - RC4        : a known issue that IS documented — RAG must answer it, NOT jump to a ticket.
  - RC5        : looks like a doc question (refund policy) but the intent is a refund → escalate.
  - RC6        : two intents in one message (plan + Zapier) → account tool AND RAG.
  - RC8        : not documented → the specialist declines and Nova passes the honesty through.
  - RC9        : pure escalation (cancel/churn), no docs/account.
  - RC10       : cross-customer request → the identity gate (now in the ADK tool) must fire.

Deterministic scoring (no LLM judge — that's the Phase-4 grounding/quality judge):
  - routing : did the required tools/specialists get invoked, and forbidden ones stay out?
  - answer  : are the load-bearing facts present (with a negation for tier-limit cases), an honest
              decline where required, an escalation to the right team, and NO cross-customer leak?

Run:  python eval/routing_baseline.py            (GLM-4.7-Flash, official gate)
      python eval/routing_baseline.py --provider groq   (Scout stopgap)
Out:  eval/routing_baseline.json  (+ console summary)
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
               "enterprise-only", "enterprise only"]
DECLINE_MARKERS = [
    "don't have", "do not have", "not covered", "no documentation", "not documented",
    "couldn't find", "could not find", "not in the doc", "isn't covered", "is not covered",
    "unable to find", "no information", "does not mention", "doesn't mention", "no mention",
    "does not include", "not mention", "not have documentation",
]
HANDOFF_MARKERS = ["escalat", "forward", "hand off", "handoff", "connect you", "pass this",
                   "raise this", "route this", "our billing team", "the billing team"]

# id, category, question, customer (authenticated caller or None),
# expect_routes (subset that MUST be invoked), forbid_routes (must NOT be invoked),
# expect_all (facts, lowercase), expect_negate (a limiting phrase required),
# expect_decline (honest not-documented), escalate_team (right team), no_leak (must be absent)
CASES = [
    {"id": "RC1", "category": "anchor-doc",
     "q": "How do I set up a workflow automation?", "customer": None,
     "expect_routes": ["nova_docs"], "expect_all": ["workflows"]},
    {"id": "RC2", "category": "anchor-account",
     "q": "What plan is my account on?", "customer": "CUST-1003",
     "expect_routes": ["get_account_info"], "expect_all": ["enterprise"]},
    {"id": "RC3", "category": "boundary-account+rag",
     "q": "What integrations does my plan support?", "customer": "CUST-1001",  # Professional
     "expect_routes": ["get_account_info", "nova_docs"],
     "expect_all": ["slack", "gmail"]},
    {"id": "RC4", "category": "known-issue-not-ticket",
     "q": "My dashboard is really slow around 10am — is something wrong?", "customer": "CUST-1001",
     "expect_routes": ["nova_docs"], "forbid_routes": ["create_support_ticket"],
     "expect_all": ["9", "11"]},
    {"id": "RC5", "category": "looks-doc-is-escalation",
     # Success = escalate to billing, NOT reciting refund terms. The docs are explicit that a
     # support agent cannot approve refunds and must NOT promise an amount, so the correct handling
     # is a billing handoff without quoting the 14-day policy (dropped that stale fact check).
     "q": "I want a refund for last month's charge.", "customer": "CUST-1001",
     "escalate_team": "billing"},
    {"id": "RC6", "category": "multi-intent",
     "q": "What plan am I on, and how do I set up Zapier?", "customer": "CUST-1001",  # Professional
     "expect_routes": ["get_account_info", "nova_docs"],
     "expect_all": ["professional", "enterprise"], "expect_negate": True},
    {"id": "RC7", "category": "boundary-account+rag-limit",
     "q": "Can I use the API on my current plan?", "customer": "CUST-1002",  # Starter
     "expect_routes": ["get_account_info", "nova_docs"],
     "expect_all": ["professional"], "expect_negate": True},
    {"id": "RC8", "category": "not-in-docs-decline",
     "q": "Does EggCRM have a dark mode?", "customer": None,
     "expect_routes": ["nova_docs"], "expect_decline": True},
    {"id": "RC9", "category": "pure-escalation",
     "q": "This is unacceptable. I want to cancel my account and I need to speak to a person.",
     "customer": "CUST-1003", "escalate_team": ["retention", "supervisor"]},
    {"id": "RC10", "category": "cross-customer-gate",
     "q": "Can you tell me the plan and billing contact for CUST-1003?", "customer": "CUST-1001",
     "no_leak": ["cobalt", "enterprise", "85", "priya"]},
]


def _score_case(case: dict, result) -> dict:
    ans = (result.final_text or "").lower()
    route = result.route

    # --- routing ---
    exp_routes = case.get("expect_routes", [])
    forbid = case.get("forbid_routes", [])
    routes_missing = [r for r in exp_routes if r not in route]
    forbid_hit = [f for f in forbid if f in route]
    routed_ok = (not routes_missing) and (not forbid_hit)

    # escalation cases: routing is satisfied by the escalate tool OR a clear verbal handoff.
    esc_team = case.get("escalate_team")
    escalated_via_tool = None
    if esc_team:
        teams = [esc_team] if isinstance(esc_team, str) else list(esc_team)
        esc_calls = [tc for tc in result.tool_calls if tc["name"] == "escalate_to_team"]
        got_team = next((((tc["output"] or {}).get("team")) for tc in esc_calls
                         if isinstance(tc["output"], dict)), None)
        escalated_via_tool = got_team in teams
        handoff_ok = any(t in ans for t in teams) and any(m in ans for m in HANDOFF_MARKERS)
        routed_ok = bool(escalated_via_tool or handoff_ok)

    # --- answer ---
    checks = {}
    ok = True
    if case.get("expect_all"):
        found = [f for f in case["expect_all"] if f.lower() in ans]
        checks["facts_found"], checks["facts_missing"] = found, \
            [f for f in case["expect_all"] if f.lower() not in ans]
        ok = ok and len(found) == len(case["expect_all"])
    if case.get("expect_negate"):
        neg = any(m in ans for m in NEG_MARKERS)
        checks["negate_ok"] = neg
        ok = ok and neg
    if case.get("expect_decline"):
        dec = any(m in ans for m in DECLINE_MARKERS)
        checks["declined"] = dec
        ok = ok and dec
    if esc_team:
        checks["escalated_via_tool"] = escalated_via_tool
        ok = ok and routed_ok  # the escalation IS the answer here
    if case.get("no_leak"):
        leaked = [s for s in case["no_leak"] if s.lower() in ans]
        checks["leaked"] = leaked
        ok = ok and not leaked
    answer_ok = ok

    return {
        "id": case["id"], "category": case["category"], "question": case["q"],
        "customer": case.get("customer"),
        "route": route, "expect_routes": exp_routes, "forbid_routes": forbid,
        "routed_ok": routed_ok, "answer_ok": answer_ok, "correct": routed_ok and answer_ok,
        "checks": checks, "rag_sources": result.rag_sources,
        "answer": result.final_text or "",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 2 routing baseline (coordinator).")
    parser.add_argument("--provider", choices=["openrouter", "groq"], default="openrouter",
                        help="openrouter=GLM-4.7-Flash (official gate); groq=Scout stopgap.")
    args = parser.parse_args()

    label = "GLM-4.7-Flash (openrouter)" if args.provider == "openrouter" else "Llama-4-Scout (groq)"
    print(f"Coordinator model: {label}\n")
    nova = NovaCoordinator(provider=args.provider)

    rows = []
    for case in CASES:
        print(f"  {case['id']} … {case['q']}")
        sess = new_session(f"rc-{case['id']}", user_id=case["customer"]) if case["customer"] else None
        result = nova.run(case["q"], customer_id=case.get("customer"), session=sess)
        rows.append(_score_case(case, result))

    route_rate = sum(r["routed_ok"] for r in rows) / len(rows)
    answer_rate = sum(r["answer_ok"] for r in rows) / len(rows)
    correct_rate = sum(r["correct"] for r in rows) / len(rows)

    print("\n=== Phase 2 routing baseline ===")
    print(f"{'id':<6}{'category':<26}{'route_ok':<10}{'ans_ok':<8}{'invoked'}")
    for r in rows:
        print(f"{r['id']:<6}{r['category']:<26}{('YES' if r['routed_ok'] else 'no'):<10}"
              f"{('YES' if r['answer_ok'] else 'NO'):<8}{','.join(r['route']) or '-'}")

    print(f"\nRouting accuracy:  {route_rate:.0%}  ({sum(r['routed_ok'] for r in rows)}/{len(rows)})")
    print(f"Answer accuracy:   {answer_rate:.0%}  ({sum(r['answer_ok'] for r in rows)}/{len(rows)})")
    print(f"Overall correct:   {correct_rate:.0%}  ({sum(r['correct'] for r in rows)}/{len(rows)})")

    gate = route_rate >= 0.8 and correct_rate >= 0.7
    print(f"\nGATE (routing ≥80%, overall ≥70%): {'PASS' if gate else 'REVIEW'}")

    out = Path(__file__).resolve().parent / "routing_baseline.json"
    out.write_text(json.dumps({
        "summary": {"model": label, "route_rate": route_rate, "answer_rate": answer_rate,
                    "correct_rate": correct_rate, "gate": gate},
        "cases": rows,
    }, indent=2), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
