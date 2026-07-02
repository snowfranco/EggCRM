# Claude Code bootstrap — EggCRM Support Agent (Project 3)

Read `PROJECT.md` (what this is) and `ACTIVE.md` (current state + next action) at the
start of every session. `DECISIONS.md` holds Project 3's rationale; **`DECISIONS_4.md`**
holds Project 4's (Agentic RAG + multi-agent). `localdoc/project-4-handoff.md` is the
current plan; `project-3-plan.md` is the prior phased plan.

## Ground rules for this project
- **Framework-free RAG, ADK for multi-agent (Project 4 change, P4-D7).** Project 3 was
  strictly framework-free. Project 4 keeps the **RAG pipeline hand-built** (chunking,
  embedding, vector store, retrieval — raw Python) but uses **ADK deliberately for the
  coordinator/delegation layer only**. ADK's `LiteLlm` adapter is accepted as ADK-internal
  plumbing to keep using GLM-4.7-Flash via OpenRouter. Do not reach for a framework anywhere
  else — building the rest by hand is still the point.
- **Measure before proceeding.** Do not layer a new capability on an uncharacterized
  foundation. Each phase has a baseline gate; run it and record results before moving on.
- **Both defenses per failure mode.** Primary fix + safety net (e.g. input classifier +
  output grounding; forced behavior + defensive validation).
- **Structure > content for small models.** System-prompt rules go in ordered gated
  WORKFLOWs, not flat parallel lists.
- **Regression every phase.** Re-run prior baselines; no phase ships if it regresses one.
- **Structured logging everywhere** (D1): timestamp, session_id, user_id, phase, intent,
  outcome, duration_ms, token_count, error.

## Layout
- `src/novacrm_agent/` — orchestrator, runner, config
  - `tools/` — knowledge_base, account, ticketing (Phase 1)
  - `memory/` — extractor, store, retriever (Phase 3)
  - `guardrails/` — input_guard, topic_guard, output_guard, escalation (Phase 4–5)
  - `rag/` — chunker, embedder, store, ingest, retrieval (Project 4, hand-built)
  - `agents/` — rag_agent (standalone), coordinator/Nova-router (Project 4, ADK)
- `data/knowledge_base/docs/` — Project 4 documentation corpus (markdown w/ front-matter)
- `data/` — knowledge_base (RAG corpus), accounts (mock fixtures), memory_store,
  sessions (runtime, gitignored)
- `eval/` — adapted from `../research-agent/eval/` in Phase 6
- `tests/` — pytest

## Human-owned (don't decide these unilaterally)
API keys, eval case curation, prompt-engineering/persona content (D4), KB content (D3),
memory-topic definitions (D5). Draft proposals are fine; flag them for sign-off.

## Commands
- Install: `pip install -r requirements.txt`
- Test: `pytest`
