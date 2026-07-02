"""Phase 3 grounding eval (P4-D6, primary metric) — is the pipeline's answer supported by its docs?

Runs on the FULL coordinator (GLM via ADK) now that RC3 discipline is fixed, so it grades the
complete pipeline (tier-aware retrieval → grounded answer), not the RAG agent in isolation. Two
halves so the metric can't be vacuous:

  POSITIVE  — real doc questions through NovaCoordinator; each RAG-delegated answer is grounding-
              judged against the passages it actually retrieved (via `result.grounding`, the same
              runtime check). A grounded pipeline scores high here. An honest decline counts grounded.
  NEGATIVE  — a control: for a few queries we retrieve the real passages but hand the judge a
  CONTROL     deliberately FABRICATED answer (wrong price/tier). These MUST be flagged — it proves
              the grounding check has teeth and isn't just rubber-stamping everything.

Gate: positive grounded-rate == 100% AND negative-control catch-rate == 100%.

Run:  python eval/grounding_eval.py [--provider openrouter|groq]
Out:  eval/grounding_eval.json  (+ console summary)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from novacrm_agent import config                              # noqa: E402
from novacrm_agent.agents.coordinator import NovaCoordinator  # noqa: E402
from novacrm_agent.guardrails.grounding import check_grounding  # noqa: E402
from novacrm_agent.llm import LLMClient                       # noqa: E402
from novacrm_agent.rag.retriever import retrieve_docs         # noqa: E402
from rag_baseline import CASES as RAG_CASES                   # noqa: E402

# Positive set: the doc-answerable questions from the Phase-1 RAG baseline (customer-agnostic;
# they route to nova_docs through the coordinator). R10 (dark mode) exercises a grounded DECLINE.
POSITIVE = [{"id": c["id"], "q": c["q"]} for c in RAG_CASES]

# Negative control: real query → retrieve real passages → judge a FABRICATED answer. Must be flagged.
NEG_CONTROL = [
    {"id": "N1", "q": "How much is the Professional plan?",
     "fabricated": "The Professional plan is $59 per user per month, with a free tier of 3 users."},
    {"id": "N2", "q": "Can I use Zapier on the Professional plan?",
     "fabricated": "Yes, Zapier is fully supported on the Professional plan at no extra cost."},
    {"id": "N3", "q": "What is the Enterprise API rate limit?",
     "fabricated": "Enterprise has no rate limit — you can make unlimited API requests per second."},
]


def main() -> None:
    ap = argparse.ArgumentParser(description="Phase 3 grounding eval (P4-D6).")
    ap.add_argument("--provider", choices=["openrouter", "groq"], default="openrouter")
    args = ap.parse_args()
    label = "GLM-4.7-Flash (openrouter)" if args.provider == "openrouter" else "Llama-4-Scout (groq)"
    print(f"Coordinator model: {label} | grounding judge: {config.GROQ_SCOUT_MODEL} (groq)\n")

    nova = NovaCoordinator(provider=args.provider)
    # Dedicated judge client (Groq Scout) for the negative control's standalone checks.
    judge = LLMClient(model=config.GROQ_SCOUT_MODEL, base_url=config.GROQ_BASE_URL,
                      api_key=config.GROQ_API_KEY)

    # --- POSITIVE: real pipeline answers, grounding from the runtime check ---
    pos = []
    for case in POSITIVE:
        r = nova.run(case["q"])
        g = r.grounding or {}
        grounded = g.get("grounded", True) if g.get("checked") else True  # non-RAG/decline → grounded
        pos.append({"id": case["id"], "q": case["q"], "route": r.route,
                    "grounding": g, "grounded": grounded, "answer": (r.final_text or "")[:200]})
        print(f"  +{case['id']:<4} grounded={'Y' if grounded else 'N'} "
              f"score={g.get('score', '-')} route={','.join(r.route) or '-'}")

    # --- NEGATIVE CONTROL: fabricated answers over real passages MUST be flagged ---
    neg = []
    for case in NEG_CONTROL:
        hits = retrieve_docs(case["q"], top_k=5)
        chunks = [{"source": h["metadata"]["source"], "section": h["metadata"]["section"],
                   "text": h["text"]} for h in hits]
        gr = check_grounding(case["fabricated"], chunks, llm=judge)
        neg.append({"id": case["id"], "q": case["q"], "flagged": gr.flagged,
                    "score": gr.score, "reason": gr.reason})
        print(f"  -{case['id']:<4} flagged={'Y' if gr.flagged else 'N'} score={gr.score}  ({gr.reason[:60]})")

    pos_grounded = sum(p["grounded"] for p in pos)
    pos_rate = pos_grounded / len(pos)
    neg_caught = sum(n["flagged"] for n in neg)
    neg_rate = neg_caught / len(neg)

    print("\n=== Phase 3 grounding eval ===")
    print(f"Positive grounded-rate:      {pos_rate:.0%}  ({pos_grounded}/{len(pos)})")
    print(f"Negative-control catch-rate: {neg_rate:.0%}  ({neg_caught}/{len(neg)})")
    flagged_pos = [p["id"] for p in pos if not p["grounded"]]
    missed_neg = [n["id"] for n in neg if not n["flagged"]]
    print(f"Ungrounded real answers: {flagged_pos or 'none'} | fabrications missed: {missed_neg or 'none'}")
    gate = pos_rate == 1.0 and neg_rate == 1.0
    print(f"GATE (positive 100% grounded, negative 100% caught): {'PASS' if gate else 'REVIEW'}")

    out = Path(__file__).resolve().parent / "grounding_eval.json"
    out.write_text(json.dumps({
        "summary": {"model": label, "positive_grounded_rate": pos_rate,
                    "negative_catch_rate": neg_rate, "gate": gate},
        "positive": pos, "negative_control": neg,
    }, indent=2), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
