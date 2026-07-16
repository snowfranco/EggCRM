# CLAUDE.md — EggCRM Support Agent (Projects 3 & 4)

Start every session by reading, in order:
1. **`PROJECT_OS.md`** — what this is, role tags, and the ADR-format Decisions Log (ADR-001…031).
2. **`ROADMAP.md`** — emoji status board, current state, and the exact next action.
3. **`PARKING_LOT.md`** — deferred items; check before proposing "new" work.

Deep decision narratives stay in `DECISIONS.md` (P3, D1–D15) and `DECISIONS_4.md` (P4,
P4-D1–D10) — the ADR log cites into them. Session-by-session history: `ACTIVE.md` (frozen;
update `ROADMAP.md` instead). The current plan is `localdoc/project-4-handoff.md`.

## Ground rules

- **Framework-free RAG, ADK for multi-agent only (ADR-022).** The RAG pipeline (chunking,
  embedding, vector store, retrieval) and the RAG agent's loop are hand-built raw Python. ADK is
  used deliberately for the coordinator/delegation layer only; its `LiteLlm` adapter is accepted
  as ADK-internal plumbing for GLM-4.7-Flash via OpenRouter. Do not reach for a framework
  anywhere else — building the rest by hand is the point.
- **Measure before proceeding.** Never layer a capability on an uncharacterized foundation; every
  phase has a baseline gate — run it and record results first.
- **Both defenses per failure mode.** Primary fix + safety net, always.
- **Structure > content for small models.** System-prompt rules go in ordered gated WORKFLOWs,
  not flat parallel lists.
- **Regression every phase.** Re-run prior baselines; nothing ships if it regresses one.
- **Non-shadow rule (ADR-005/021).** Docs are authoritative for product knowledge, memory for
  durable user context, account tools for live state — read authoritative state live, never from
  memory.
- **Structured logging everywhere (ADR-001):** timestamp, session_id, user_id, phase, intent,
  outcome, duration_ms, token_count, error.
- **Evidence tags.** In OS files, mark reconstructed rationale `[INFERRED]` and unknowns `[GAP]`;
  never fabricate a purpose, decision, or rationale.

## Role tags — [HUMAN] owned (don't decide these unilaterally)

API keys · eval case curation · prompt-engineering/persona content (`configs/system_prompt.md`,
`COORDINATOR_INSTRUCTION`) · KB/corpus content (`data/knowledge_base/`) · memory-topic
definitions · retrospective narratives. Draft proposals are fine; flag them for sign-off.
Everything else is [AGENT] lane (implementation, tests, harnesses) — see `PROJECT_OS.md`.

## Layout

- `src/novacrm_agent/` — orchestrator, runner, server, config (package keeps the pre-rebrand
  NovaCRM name — see `PARKING_LOT.md`)
  - `tools/` · `memory/` · `guardrails/` — Project 3 layers
  - `rag/` — Project 4 hand-built pipeline · `agents/` — RAG agent + ADK coordinator
- `adk_app/` — `adk web` inspection entry (bypasses guardrails, ADR-030)
- `data/` — KB + corpus [HUMAN], mock accounts; runtime stores gitignored
- `configs/` — prompts [HUMAN] + specs · `eval/` — baselines + judges · `tests/` — offline pytest
- `webui/` + root `package.json` — demo UI (deps must install at repo root)

## Commands

- Install: `pip install -r requirements.txt` · Test: `pytest`
- Ingest vector store: `python -m novacrm_agent.rag.ingest`
- Combined eval: `python -m eval.run_eval` (`--coordinator` for P4; needs funded keys)

## Session close

Before stopping: update `ROADMAP.md` (statuses + the exact next action), move anything deferred
to `PARKING_LOT.md`, and append an ADR to `PROJECT_OS.md` for any decision made this session.
