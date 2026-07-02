"""Phase 1 RAG baseline — measure the standalone RAG agent BEFORE wiring the coordinator.

Same measure-before-proceeding discipline as the Project 3 baselines: characterize retrieval +
grounding on a fixed set of known-answer questions before building the multi-agent layer on top.

The 10 cases (R1-R10) are human-signed-off (2026-06-30). They span feature / API / troubleshooting,
two tier-boundary traps (R3/R4 — only a grounded answer gets them right), and one not-in-docs
honesty trap (R10 — success = the agent declines instead of fabricating).

Two deterministic scores per case (no LLM judge here; that's the Phase 4 grounding judge):
  - retrieval recall   : did the gold doc appear in the chunks the agent retrieved?
  - answer correctness  : are the load-bearing facts present (and, for tier cases, a negation)?
                          for R10, correctness = an honest decline, not a fabricated answer.

Run:  python eval/rag_baseline.py
Out:  eval/rag_baseline.json  (+ console summary)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from novacrm_agent import config  # noqa: E402
from novacrm_agent.agents.rag_agent import RAGAgent  # noqa: E402
from novacrm_agent.llm import LLMClient  # noqa: E402


def _make_agent(provider: str) -> tuple[RAGAgent, str]:
    """Build a RAGAgent on the chosen provider. Returns (agent, model_label).

    'openrouter' = the primary GLM-4.7-Flash (official Phase 1 gate model).
    'groq'       = Llama-4-Scout (stopgap when OpenRouter is out of credits — labeled as such).
    """
    if provider == "groq":
        llm = LLMClient(model=config.GROQ_SCOUT_MODEL, base_url=config.GROQ_BASE_URL,
                        api_key=config.GROQ_API_KEY)
        return RAGAgent(llm=llm), f"{config.GROQ_SCOUT_MODEL} (groq, STOPGAP)"
    return RAGAgent(), f"{config.PRIMARY_MODEL} (openrouter, primary)"

# Phrases that signal a negative/limiting answer (used by the tier-boundary cases).
NEG_MARKERS = ["no", "not", "only", "n't", "cannot", "require", "upgrade", "unavailable", "enterprise-only"]
# Phrases that signal an honest "I don't have docs on this" (the not-in-docs case).
DECLINE_MARKERS = [
    "don't have", "do not have", "not covered", "no documentation", "not documented",
    "couldn't find", "could not find", "not in the doc", "isn't covered", "is not covered",
    "unable to find", "no information", "not have documentation", "not have any documentation",
    "i don't have", "not have details", "don't have documentation",
    # "does not mention X in the documentation" is an honest decline too — the model names the
    # gap by what the docs omit rather than what it lacks (2026-06-30, same curation as R5/R10).
    "does not mention", "doesn't mention", "no mention", "does not include", "not mention",
]

# id, category, question, gold_sources (filenames), expect_all (required facts, lowercase),
# expect_negate (must also carry a limiting phrase), not_in_docs (success = honest decline)
CASES = [
    {"id": "R1", "category": "feature-howto",
     "q": "How do I set up a workflow automation?",
     "gold": ["05-workflow-automation.md"],
     "expect_all": ["workflows", "new automation"]},
    {"id": "R2", "category": "feature-factual",
     "q": "How much is the Professional plan — monthly and annual?",
     "gold": ["02-plans-and-pricing.md"],
     "expect_all": ["79", "63.20"]},
    {"id": "R3", "category": "tier-boundary",
     "q": "Can I use Zapier on the Professional plan?",
     "gold": ["07-integrations-overview.md", "02-plans-and-pricing.md"],
     "expect_all": ["enterprise"], "expect_negate": True},
    {"id": "R4", "category": "tier-boundary",
     "q": "Is API access available on the Starter plan?",
     "gold": ["10-api-overview-and-auth.md", "02-plans-and-pricing.md"],
     "expect_all": ["professional"], "expect_negate": True},
    {"id": "R5", "category": "api",
     "q": "How do I authenticate a request to the EggCRM API?",
     "gold": ["10-api-overview-and-auth.md"],
     # The load-bearing facts are the mechanism (bearer token) and the header it goes in
     # (Authorization). Dropped the literal "api key" requirement — a correct grounded answer
     # legitimately phrases the credential as "bearer token" without the exact bigram "api key"
     # (2026-06-30 curation, human-signed-off: over-strict assertion, not an agent failure).
     "expect_all": ["bearer", "authorization"]},
    {"id": "R6", "category": "api",
     "q": "What's the API rate limit on Enterprise, and what happens if I exceed it?",
     "gold": ["14-rate-limits-and-errors.md"],
     "expect_all": ["10,000", "429"]},
    {"id": "R7", "category": "troubleshooting",
     "q": "My dashboard is really slow around 10am — is something wrong?",
     "gold": ["17-dashboard-performance.md"],
     "expect_all": ["9", "11", "et"]},
    {"id": "R8", "category": "troubleshooting-policy",
     "q": "I want a refund for this month.",
     "gold": ["16-billing-and-plan-changes.md"],
     # Load-bearing fact is the refund window (14 days) + that it's pro-rated — NOT the incidental
     # doc-title token "billing", which the model drops on wording variance even when the policy is
     # correct (2026-06-30 curation, human-signed-off: same over-strict-token class as R5).
     "expect_all": ["14 days", "pro-rated"]},
    {"id": "R9", "category": "feature-howto",
     "q": "How do I export all my data, and how long does it take?",
     "gold": ["08-data-export-and-management.md"],
     "expect_all": ["data management", "24 hours"]},
    {"id": "R10", "category": "not-in-docs",
     # Replaced the original "native iOS app?" trap: the corpus states EggCRM is "browser-based
     # — nothing to install", so a "no native app" reply is a GROUNDED inference, not a fabrication
     # (2026-06-30 curation, human-signed-off). "Dark mode" has NO adjacent doc fact to infer from,
     # so success is unambiguously an honest decline rather than a defensible inference.
     "q": "Does EggCRM have a dark mode?",
     "gold": [], "not_in_docs": True},
]


def _score_case(case: dict, result) -> dict:
    ans = result.answer.lower()
    sources = result.retrieved_sources()

    # retrieval recall (N/A for the not-in-docs case)
    if case.get("not_in_docs"):
        recall = None
    else:
        recall = any(g in sources for g in case["gold"])

    # answer correctness
    if case.get("not_in_docs"):
        declined = any(m in ans for m in DECLINE_MARKERS)
        correct = declined
        facts = {"declined": declined}
    else:
        found = [f for f in case["expect_all"] if f.lower() in ans]
        facts_ok = len(found) == len(case["expect_all"])
        negate_ok = (not case.get("expect_negate")) or any(m in ans for m in NEG_MARKERS)
        correct = facts_ok and negate_ok
        facts = {"found": found, "missing": [f for f in case["expect_all"] if f.lower() not in ans],
                 "negate_ok": negate_ok}

    return {
        "id": case["id"], "category": case["category"], "question": case["q"],
        "answer": result.answer,
        "retrieved_sources": sorted(sources),
        "top_score": round(result.top_score(), 3),
        "recall": recall, "correct": correct, "facts": facts,
        "iterations": result.iterations, "tokens": result.total_tokens,
        "tool_calls": [tc["name"] for tc in result.tool_calls],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 1 RAG baseline.")
    parser.add_argument("--provider", choices=["openrouter", "groq"], default="openrouter",
                        help="openrouter=primary GLM-4.7-Flash (official gate); groq=Scout stopgap.")
    args = parser.parse_args()

    agent, model_label = _make_agent(args.provider)
    print(f"Model: {model_label}\n")
    rows = []
    for case in CASES:
        print(f"  {case['id']} … {case['q']}")
        result = agent.run(case["q"])
        rows.append(_score_case(case, result))

    gold_rows = [r for r in rows if r["recall"] is not None]
    recall_rate = sum(r["recall"] for r in gold_rows) / len(gold_rows)
    correct_rate = sum(r["correct"] for r in rows) / len(rows)
    r10 = next(r for r in rows if r["id"] == "R10")

    print("\n=== Phase 1 RAG baseline ===")
    print(f"{'id':<4}{'cat':<22}{'recall':<8}{'correct':<9}{'iters':<6}{'sources'}")
    for r in rows:
        rec = "n/a" if r["recall"] is None else ("YES" if r["recall"] else "no")
        cor = "YES" if r["correct"] else "NO"
        print(f"{r['id']:<4}{r['category']:<22}{rec:<8}{cor:<9}{r['iterations']:<6}"
              f"{','.join(s.replace('.md','') for s in r['retrieved_sources'])[:48]}")

    print(f"\nRetrieval recall (gold cases): {recall_rate:.0%}  ({sum(x['recall'] for x in gold_rows)}/{len(gold_rows)})")
    print(f"Answer correctness (all):      {correct_rate:.0%}  ({sum(x['correct'] for x in rows)}/{len(rows)})")
    print(f"R10 not-in-docs honest decline: {'YES' if r10['correct'] else 'NO'}")

    gate = recall_rate >= 0.8 and correct_rate >= 0.8 and r10["correct"]
    print(f"\nGATE (recall ≥80%, correctness ≥80%, R10 declines): {'PASS' if gate else 'REVIEW'}")

    out = Path(__file__).resolve().parent / "rag_baseline.json"
    out.write_text(json.dumps({
        "summary": {"model": model_label, "recall_rate": recall_rate, "correct_rate": correct_rate,
                    "r10_declines": r10["correct"], "gate": gate},
        "cases": rows,
    }, indent=2), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
