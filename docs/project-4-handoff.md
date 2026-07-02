# Project 4 Handoff — from Project 3 (EggCRM Support Agent)

Context carried forward from Project 3, the framework-free customer-support agent with memory
and guardrails (capstone for Google's 5-Day AI Agents Intensive). Project 3 lives at
`~/Projects/novacrm`; its full rationale is in `DECISIONS.md` (D1–D15).

## What carries forward

### Models & API keys (all still wired)
- **Primary agent:** GLM-4.7-Flash via OpenRouter (`z-ai/glm-4.7-flash`) — strong tool-call
  discipline at low cost (validated by the Phase 1 baseline, D2/D8).
- **LLM-as-a-Judge:** Llama 4 Scout via Groq (`meta-llama/llama-4-scout-17b-16e-instruct`) —
  separate provider from the agent (no self-eval bias, no quota collision).
- **Documented fallback:** GLM-4.7 via Cerebras. Plus a fallback-key chain
  (`OPENROUTER_API_KEY2`/`_KEY3`) that auto-engages on a 402.
- Keys live in `.env` (`OPENROUTER_API_KEY`, `GROQ_API_KEY`, optional fallbacks).

### Eval infrastructure (adapted from Project 1, proven across 6 phases)
- Per-phase baselines (`eval/baseline_phase{1..5}.py`) + the combined four-pillar runner
  (`eval/run_eval.py`) producing `outputs/eval-report.md`.
- LLM-as-a-Judge with a 4-dimension rubric (correctness/helpfulness/safety/persona), JSON output,
  one retry → `judge_error` (logged + excluded from means, never scored 0).
- Response caching (`--use-cache`) so re-judging never re-runs the agent.
- Curated suites reusable as-is: golden dataset, adversarial corpus (injection/PII/topic),
  output-failure corpus, cross-session scenarios.

### Key learnings (the operating discipline)
1. **Gated WORKFLOW > flat rules** for smaller models — mandatory ordered gates (escalation,
   confirm-before-create) outperform parallel instructions.
2. **Measure before proceeding** — baseline every layer before building on it; never trust an
   uncharacterized foundation.
3. **Both defenses** — every failure mode gets a primary fix + a safety net (prompt gate + code
   gate; input redaction + output re-scan).
4. **Evidence over assumptions** — verify with traces/stored state, not plausible-sounding prose
   (the judge corroborates escalations against the `escalate_to_team` trace, not the reply text).
5. **Non-shadow rule (D5)** — tool-authoritative state (plan/billing/storage) is read live, never
   memorized; memory holds only durable context the system of record doesn't.

### The phase catches that proved "measure-first" earns its keep
Each phase's baseline caught something a smoke test would have missed:
- **P1:** the eval's own ticket-confirmation expectation was wrong (the agent correctly
  proposed-then-confirmed); fixed the contract, not the agent.
- **P2:** a real confirm-before-create regression (duplicate tickets) → mandatory gate.
- **P3:** extraction missed a preference embedded in a transactional turn → 4th few-shot.
- **P4:** topic guard would false-positive on keyword-less follow-ups → lean-allow; the "sue"
  keyword muzzled abuse-escalation → removed legal-threat terms.
- **P5:** mock-data mismatches (emails) would have made assertions pass vacuously.
- **P7 (cleanup):** the output guard treated a customer's OWN email as cross-customer when the
  session had no `user_id` → self-customer determination fixed.

## What's different for Project 4

The likely Project 4 theme is **RAG** (vector retrieval over external documents) vs. the
**memory** (user-specific facts) built here. That boundary is already clean from Project 3's D5:
- **Memory** = per-user durable facts, written back, consolidated, injected at session start.
- **RAG** = shared external knowledge retrieved on demand; Project 3's `lookup_knowledge_base`
  is keyword retrieval over a small KB — Project 4 replaces it with real vector retrieval
  (embeddings, chunking, reranking) over a larger corpus.

Carry the same discipline: characterize retrieval quality (recall/precision) before building the
agent on top, and keep the RAG/memory separation explicit so grounding stays auditable.
