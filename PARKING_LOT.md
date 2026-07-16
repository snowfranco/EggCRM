# PARKING_LOT — EggCRM Support Agent

> Deferred, not forgotten. Each item: what it is, why it was parked, and what wakes it.
> Nothing here blocks `ROADMAP.md`'s next action. Owner tags per `PROJECT_OS.md`.

## Hardening

- **LiteLlm 402 key-rotation wrapper** [AGENT] — ADK's `LiteLlm` is pinned to one key and
  hard-fails when it drains (the hand-built `LLMClient` rotates; ADK doesn't) — a single point of
  credit failure for the coordinator, surfaced mid-run in the golden regression.
  *Parked:* explicitly "deferred unless wanted" at Phase 5. *Wake:* next funded eval run, or any
  production-shaped use. Source: `DECISIONS_4.md:304-308`, `ACTIVE.md:198-199`.
- **3-consecutive-green combined-eval gate (P3)** [AGENT] — the strict gate could never be
  finished in the original dev environment (background runs reaped, 10-min foreground cap); the
  flaky case (G17) was root-caused and fixed. *Wake:* a stable terminal + funded keys:
  `for n in 1 2 3; do ./venv/bin/python -m eval.run_eval | grep GATE; done`.
  Source: `DECISIONS.md:478-484`, `ACTIVE.md:241-247`.
- **Clean recorded 33/33 golden run (P4)** [HUMAN to re-open] — the recorded artifact is 30/33
  scored-clean (3 key-402s re-confirmed individually). A fresh run was **declined 2026-07-01 as
  process theater** (ADR-029); listed here only in case a publishable artifact is ever wanted.
  Source: `ACTIVE.md:150-171`, `DECISIONS_4.md:295-302`.

## Observability & performance

- **Phoenix / OTel exporter** [AGENT] — custom JSONL tracing was chosen first, architected so an
  exporter bolts on without a rewrite. *Wake:* when `jq`-over-JSONL becomes the bottleneck.
  Source: `DECISIONS.md:22-35` (ADR-001).
- **Delegation-latency mitigations** [AGENT] — ~34s overhead per RAG-delegated turn (many
  sequential GLM calls). Production shape: stream, parallelize the grounding check, cache hot doc
  queries. *Parked:* honest measured trade-off of ADR-020, not gated. *Wake:* any latency-
  sensitive deployment. Source: `DECISIONS_4.md:331-339`, `ACTIVE.md:184-188`.

## Retrieval / RAG (all gated on evidence that never arrived — retrieval measured 100%)

- **Intra-section sub-splitting in the chunker** — *Wake:* sections too large for clean
  retrieval. Source: `DECISIONS_4.md:55-57` (ADR-019).
- **Provider-hosted embedding model** — *Wake:* poor measured recall/precision on the local
  MiniLM model. Source: `DECISIONS_4.md:36-38` (ADR-017).
- **Re-ranking / query expansion** — sketched in the P4 plan's original Phase 3, dropped when
  the phase was rescoped (ADR-028) because recall was already 100%. *Wake:* a bigger corpus or
  measured relevance problems. Source: `localdoc/project-4-handoff.md:84-89`.
- **Tavily web-search augmentation for RAG** — mentioned as available in the handoff; never
  wired (no key in `.env.example`, no code references). Source: `localdoc/project-4-handoff.md:102`.

## Product / demo

- **Live-demo memory extraction endpoint** [AGENT] — `/chat` doesn't trigger extraction
  (end-of-conversation only), so the demo's "memories" panel only shows already-stored facts.
  An end-session trigger was offered, not built. Source: `ACTIVE.md:291-293`.
- **Cerebras fallback provider** — documented in ADR-002 and `.env.example`
  (`CEREBRAS_API_KEY`), never exercised. *Wake:* OpenRouter becoming unusable.

## Housekeeping `[INFERRED — reconstructed from repo state, no explicit parking decision found]`

- **NovaCRM → EggCRM code rename** — the 2026-07-02 rebrand (`f08e5ba`) covered docs/UI only;
  `novacrm_agent` (package), `novacrm_kb.json`, `novacrm-demo.jsx` keep the old name. Renaming
  would churn the frozen, evaluated P3 deliverable. *Wake:* only with a deliberate migration.
- **`.env.example` is stale** — documents KEY2/KEY3 only, while `config.py:44-51` consumes
  KEY…KEY7 + `_FALLBACK` with funded-first ordering. Cheap doc fix, [HUMAN] adjacent (keys).
- **Duplicate/legacy doc consolidation** — root `project-3-plan.md` is byte-identical to
  `localdoc/project-3-plan.md`; two *different* documents share the name `project-4-handoff.md`
  (`docs/` = P3→P4 carry-forward, `localdoc/` = the actual P4 plan). Disposition of the legacy OS
  files (`PROJECT.md`, `ACTIVE.md`) now that `PROJECT_OS.md`/`ROADMAP.md` supersede them is a
  **[HUMAN] ruling** — see the standardization review notes.
