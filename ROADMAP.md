# ROADMAP — EggCRM Support Agent

> Live status board + the exact next action. Update at the end of every working session.
> Rationale for anything here: the ADR log in `PROJECT_OS.md`. Deferred ideas: `PARKING_LOT.md`.
> Supersedes `ACTIVE.md` (kept as the session-by-session historical log).
>
> Legend: ✅ complete · 🔄 in progress · ⬜ not started · ⛔ blocked · 💤 parked · 👤 human-owned

## Now

**Project 4 — Phase 5 (documentation + retrospective) 🔄** — the only open work in the repo.

**➡️ NEXT ACTION 👤 [HUMAN]:** write the retrospective *conclusions* — the with-framework (ADK)
vs framework-free comparison:
1. The P4 questions drafted at the end of `README_PROJECT4.md` ("Was ADK worth it for a 3-agent
   system?", leverage vs lock-in, what to reach for next time). Measured observations are already
   drafted there; only the conclusions/recommendation are missing.
2. The P3 "What I learned" section, still a placeholder at `README.md:141-144`.

When both land → **Project 4 (and the repo's course track) is COMPLETE.**

`[GAP]` Last recorded activity is 2026-07-01 (docs) / 2026-07-02 (git import); today is
2026-07-16. Whether the retrospectives were drafted elsewhere (e.g. Notion) is unknown.

## Status board — Project 4: Agentic RAG + Multi-Agent Coordinator

Plan: `localdoc/project-4-handoff.md` · Decisions: ADR-016…031 (`PROJECT_OS.md`) · Evidence: `ACTIVE.md:6-223`

| Phase | Scope | Status | Gate result (evidence) |
|---|---|---|---|
| 0 | Decisions + 20-doc corpus + hand-built RAG pipeline (121 chunks) | ✅ 2026-06-30 | 5/5 probe queries top-hit; 54 tests (`ACTIVE.md:202-213`) |
| 1 | Standalone RAG agent (framework-free ReAct) + baseline | ✅ 2026-06-30 | Recall 100%, correctness 100%, honest decline — PASS (`eval/rag_baseline.py`; Scout stopgap, ADR-023; later validated on GLM) |
| 2 | ADK coordinator; P3 guardrails/memory wrap it | ✅ 2026-06-30 | Routing 10/10 on GLM; golden regression at P3 parity 4.83/4.67/4.97/4.9 (`ACTIVE.md:47-112`) |
| 3 | Grounding check + tier-routing discipline (rescoped, ADR-028) | ✅ 2026-07-01 | Discipline 8%→100% (25/25); grounding +100%/−100%; no quality regression — closed on evidence (ADR-029) |
| 4 | Combined capstone eval across both agents | ✅ 2026-07-01 | **OVERALL GATE PASS** — all six sub-gates (`eval/run_phase4.py`, `outputs/phase4-report.md`) |
| 5 | Documentation + retrospective | 🔄 | `README_PROJECT4.md` drafted; conclusions 👤 pending |

Phase-4 scorecard (from `README_PROJECT4.md:97-107`): correctness 4.71 / helpfulness 4.57 /
safety 4.96 / persona 4.82 · retrieval 100% · routing 100% · grounding +100%/−100% · tier
discipline 100% · context sharing verified · delegation latency 43.8s vs 9.4s direct (~34s
overhead — measured trade-off, not gated).

## Status board — Project 3: framework-free support agent (COMPLETE)

Plan: `project-3-plan.md` · Decisions: ADR-001…015 (`PROJECT_OS.md`) · Evidence: `ACTIVE.md:227-339`, `DECISIONS.md`

| Phase | Scope | Status | Gate result |
|---|---|---|---|
| 0 | Scaffold + decisions D1–D5 | ✅ | Skeleton green |
| 1 | Bare ReAct loop, 4 tools | ✅ | 10/10 structural; GLM discipline confirmed (ADR-008) |
| 2 | Session memory | ✅ | 15/15 after the confirm-before-create gate (ADR-009) |
| 3 | Cross-session memory | ✅ | Cross-session 3/3, regression 15/15 (ADR-010/011) |
| 4 | Input guardrails | ✅ | Injection 39%→100%; PII 6/6; topic 7/7 (ADR-012) |
| 5 | Output guardrails + HITL | ✅ | Leak-free 60%→100%; 5 case files (ADR-013) |
| 6 | Combined four-pillar eval | ✅ | GATE PASS 4.8/4.8/4.97/4.97 (ADR-014) |
| 7 | Cleanup + README + fixes | ✅ | Final GATE PASS, best 4.97/4.81/5.0/4.94 (ADR-015) |
| — | "What I learned" retrospective | 🔄 👤 | Placeholder at `README.md:141-144` |

Extras shipped alongside: FastAPI demo server (`novacrm_agent.server`, port 8001) + esbuild web
UI (`webui/`), CLI runner, structured JSONL tracing.

## Blocked / waiting

- ⛔ **Nothing hard-blocks the remaining work** — the retrospectives need no API credits.
- 💤 **OpenRouter credit state unknown** `[GAP]`: KEY7 was the newest funded account
  (2026-07-01, `src/novacrm_agent/config.py:47`); KEY6 near-empty; KEY…KEY5 one drained account.
  Any future GLM eval run needs a funded key first.
- 👤 Human-owned inputs (per `PROJECT_OS.md` role tags): retrospective narratives; any change to
  prompts, KB/corpus, eval cases, memory topics, keys.

## Runbook notes (durable ops gotchas, condensed from `ACTIVE.md`)

- Install: `pip install -r requirements.txt`; editable: `./venv/bin/python -m pip install -e .`
- Rebuild vector store: `python -m novacrm_agent.rag.ingest` (ChromaDB store is gitignored).
- Tests: `pytest` — offline, LLM/retriever faked; last recorded green: 76 (`ACTIVE.md:200`).
- Inspect routing live: `adk web adk_app` — **bypasses guardrails** (ADR-030); production path is
  `NovaCoordinator.run()`.
- Demo server: `python -m novacrm_agent.server` (port 8001; 8000 had a squatter on the original
  dev machine). Web UI deps MUST be installed at the repo root (`npm install && npm run build`)
  or esbuild resolves two Reacts; hard-refresh after rebuilds (`ACTIVE.md:279-295`).
- Keys: `.env` — `OPENROUTER_API_KEY*` chain + `GROQ_API_KEY` (judge/guard). `config.py` picks
  the active key funded-first; ADK/LiteLlm does NOT rotate on 402 (`PARKING_LOT.md`).
- Keep the working copy OUT of cloud-synced folders — a synced path progressively OS-locked
  files and broke the venv (`ACTIVE.md:297-301`).

## History

Project 1 (ADK research agent) lives in the sibling `research-agent` repo `[GAP]` (location/
status unknown — referenced as `../research-agent`). Project 2: `[GAP]` — never mentioned in any
doc or commit. Full session-by-session history: `ACTIVE.md`; decision narratives: `DECISIONS.md`,
`DECISIONS_4.md`.
