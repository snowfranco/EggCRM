# PROJECT_OS — EggCRM Support Agent (Projects 3 & 4)

> The operating system for this repo: what it is, who owns what, and every decision with its
> rationale (ADR log below). Live status and next action: `ROADMAP.md`. Deferred ideas:
> `PARKING_LOT.md`. Agent bootstrap: `CLAUDE.md`.
>
> **Provenance note:** this file was standardized from the repo's original OS docs
> (`PROJECT.md`, `DECISIONS.md`, `DECISIONS_4.md`, `ACTIVE.md`) on 2026-07-16. Git history is
> two squashed import commits (2026-07-02), so those docs — not git — are the primary record;
> the ADRs below cite them by line. Reconstructed rationale is marked `[INFERRED]`; unknowns
> are marked `[GAP]`.

## Role tags

- **[HUMAN]** — owned by the human. Never changed unilaterally by an agent: API keys, eval case
  curation, prompt-engineering/persona content, KB/corpus content, memory-topic definitions,
  retrospective narratives. Agents may draft proposals and flag them for sign-off.
- **[AGENT]** — Claude Code's lane: implementation, tests, eval harnesses, tracing, drafts.
- **[SHARED]** — drafted by the agent, ruled on by the human (most architecture decisions).

## Purpose

Two consecutive capstone projects for Google's 5-Day AI Agents Intensive course track, built on
one codebase around **EggCRM**, a fictional CRM SaaS (tiers: Starter $29 / Professional $79 /
Enterprise $149):

1. **Project 3 — framework-free support agent.** "Nova": a customer-support agent with session +
   cross-session memory, two-layer guardrails, and HITL escalation, with the orchestration loop,
   tracing, and retries all hand-built (no ADK, no LangChain, no LiteLLM). The point: understand
   what frameworks abstract away by building it by hand, and compare against Project 1 (a
   research agent built *with* ADK, in the sibling `research-agent` repo). Source: `PROJECT.md`,
   `README.md`.
2. **Project 4 — Agentic RAG + multi-agent coordinator.** Replaces the hardcoded JSON KB with a
   hand-built vector-retrieval pipeline (chunking → local embeddings → ChromaDB) and turns Nova
   into an **ADK coordinator** that delegates documentation questions to a standalone RAG
   specialist, with a grounding check on top. ADK is used *deliberately, for the delegation layer
   only* (ADR-022). Source: `README_PROJECT4.md`, `localdoc/project-4-handoff.md`.

Project numbering: Projects 1, 3, and 4 are documented. **[GAP]** Nothing in the repo or its
history explains what Project 2 was (or whether it was skipped).

## Operating principles

Carried P1 → P3 → P4 (`DECISIONS.md:7-12`, `DECISIONS_4.md:13-19`):

1. **Measure before proceeding** — every phase has a baseline gate; run and record it before
   layering anything on top. Regression-test every phase against prior baselines.
2. **Both defenses per failure mode** — a primary fix plus a safety net (prompt gate + code gate;
   input redaction + output re-scan; vector similarity + metadata filter).
3. **Structure > content for small models** — ordered, gated WORKFLOW prompts beat flat rule lists.
4. **Evidence over assumptions** — verify with traces and stored state, not plausible prose;
   tune only what measurement shows is broken.
5. **Non-shadow rule** — no knowledge source silently overrides another: retrieved docs are
   authoritative for product knowledge, memory for durable user context, account tools for live
   account state (ADR-005, ADR-021).
6. **Structured logging everywhere** — one span schema (timestamp, session_id, user_id, phase,
   intent, outcome, duration_ms, token_count, error) → JSONL (ADR-001).

## System map (with citations)

- `src/novacrm_agent/orchestrator.py` — P3 hand-rolled ReAct loop (max-iters safety net).
- `src/novacrm_agent/tools/` — `knowledge_base`, `account`, `ticketing`, `escalation`, `registry`.
- `src/novacrm_agent/memory/` — `extractor`, `store`, `retriever`, `schemas` (P3 Phase 3).
- `src/novacrm_agent/guardrails/` — input: `pii_guard`, `injection_guard`, `topic_guard`,
  `input_pipeline`; output: `output_guard`; plus `action_gates`, `escalation` (HITL case files),
  `grounding` (P4).
- `src/novacrm_agent/rag/` — hand-built P4 pipeline: `chunker`, `embedder`, `store`, `ingest`,
  `retriever`.
- `src/novacrm_agent/agents/` — `rag_agent` (standalone, framework-free), `rag_specialist`
  (thin ADK adapter), `coordinator` (`NovaCoordinator` wrapping the ADK `LlmAgent`).
- `src/novacrm_agent/{llm,config,session,tracing,runner,server}.py` — client w/ retry + key
  rotation, model/key wiring, session state, spans, CLI, FastAPI demo server.
- `adk_app/nova/` — `root_agent` export for `adk web` (inspection only — bypasses guardrails,
  ADR-030; see `adk_app/README.md`).
- `data/knowledge_base/docs/` — the 20-doc EggCRM corpus **[HUMAN]** (index in its `README.md`);
  `data/knowledge_base/novacrm_kb.json` — the P3 JSON KB **[HUMAN]**.
- `data/accounts/accounts.json` — mock account fixtures. Runtime state is gitignored:
  `data/{memory_store,sessions,escalations,rag_store}/`, `eval/logs/` (`.gitignore`).
- `configs/` — `system_prompt.md` **[HUMAN]**, `memory_extraction_prompt.md` **[HUMAN]**,
  `guardrails_spec.md`, `output_guard_spec.md`, `judge_rubric.md`.
- `eval/` — P3: `baseline_phase{1..5}.py`, `golden_dataset.py`, `adversarial_cases.py`,
  `output_failure_cases.py`, `run_eval.py`; P4: `rag_baseline.py`, `routing_baseline.py`,
  `tier_discipline.py`, `grounding_eval.py`, `run_phase4.py`. Curation is **[HUMAN]**.
- `tests/` — offline pytest suite (LLM/retriever faked); last recorded green run: 76 tests
  (`ACTIVE.md:200`).
- `webui/` + root `package.json` — esbuild-bundled demo UI over `localdoc/novacrm-demo.jsx`.

Naming note: the package, KB file, and demo JSX keep the original **NovaCRM** name
(`novacrm_agent`, `novacrm_kb.json`, `novacrm-demo.jsx`); the 2026-07-02 rebrand to EggCRM
(commit `f08e5ba`) touched docs and UI strings only. `[INFERRED]` A code-level rename was
skipped to avoid churn against the frozen, evaluated P3 deliverable — see `PARKING_LOT.md`.

## Model stack

- **Primary agent:** `z-ai/glm-4.7-flash` @ OpenRouter (ADR-002) — for both the P3 loop and the
  P4 coordinator (via ADK's `LiteLlm`, ADR-022).
- **Judge / guard model (eval only):** `meta-llama/llama-4-scout-17b-16e-instruct` @ Groq —
  separate provider by design (no self-eval bias, no quota collision).
- **Documented fallback:** GLM-4.7 @ Cerebras (never exercised).
- **Key wiring:** `config.py` derives `OPENROUTER_ACTIVE_KEY` (newest funded account first,
  KEY7 → KEY6 → older drained keys; `src/novacrm_agent/config.py:40-59`). The hand-built
  `LLMClient` rotates on a 402; ADK's `LiteLlm` cannot (ADR-028, `PARKING_LOT.md`).

## Doc map (legacy record)

The original OS files remain the deep record and are cited throughout the ADR log:

- `DECISIONS.md` — Project 3 decision narrative, D1–D15 + a Plan-vs-Actual table.
- `DECISIONS_4.md` — Project 4 decision narrative, P4-D1–P4-D10 + execution notes.
- `ACTIVE.md` — the session-by-session state log this `ROADMAP.md` supersedes.
- `PROJECT.md` — the one-page P3 charter this file supersedes.
- Plans/handoffs: `localdoc/project-4-handoff.md` (the P4 plan), `project-3-plan.md` (P3 phased
  plan; the root copy and `localdoc/project-3-plan.md` are byte-identical), `project-3-handoff.md`
  (P1→P3 context), `localdoc/project-3-claude-code-handoff.md` (P3 scaffold handoff),
  `docs/project-4-handoff.md` (P3→P4 carry-forward — a *different* document from the localdoc
  file of the same name).

---

# Decisions Log (ADR format)

One ADR per decision, chronological, keeping the original D/P4-D identifiers for traceability.
`Source` cites the original narrative, which stays authoritative for full detail.

## Project 3 — framework-free support agent

### ADR-001 (D1) — Observability: custom structured tracing; Phoenix deferred
**Status:** Accepted · **Date:** 2026-06-26 `[INFERRED]` · **Owner:** [SHARED] · **Source:** `DECISIONS.md:15-41`
**Context:** No ADK Web UI exists in a framework-free build; options were hand-rolled JSON
spans, Arize Phoenix (OTel), or both.
**Decision:** Hand-rolled structured spans → JSONL, architected so an OTel exporter can bolt on
later. One schema for logs/traces/metrics.
**Consequences:** Full visibility owned in code (the learning goal); no timeline UI — inspection
is `jq` over JSONL. Phoenix parked (`PARKING_LOT.md`).

### ADR-002 (D2) — Models: GLM-4.7-Flash @ OpenRouter + Scout judge, raw client, no LiteLLM
**Status:** Accepted · **Date:** 2026-06-26 `[INFERRED]` · **Owner:** [SHARED] · **Source:** `DECISIONS.md:45-68`
**Context:** P1 characterized this stack; framework-free rules out LiteLLM normalization.
**Decision:** Talk to providers directly via the OpenAI-compatible client. Agent:
`z-ai/glm-4.7-flash` @ OpenRouter; judge: Llama-4-Scout @ Groq; documented fallback GLM @ Cerebras.
**Consequences:** Retries/error-mapping become explicit owned code. Open item (answered by
ADR-008): GLM's multi-turn tool-call reliability on the support shape.

### ADR-003 (D3) — Domain & knowledge base: EggCRM, human-authored
**Status:** Accepted · **Date:** 2026-06-26 · **Owner:** [HUMAN] · **Source:** `DECISIONS.md:72-92`
**Context:** Need a fictional SaaS whose support domain naturally exercises billing, account
state, PII, scope boundaries, escalation.
**Decision:** EggCRM (né NovaCRM), human-authored KB → `data/knowledge_base/novacrm_kb.json`.
Pricing lives in the KB, not the system prompt — deliberately, so pricing is a *retrieved* fact
(sharpens the RAG-vs-memory demo).
**Consequences:** Review items (bug-flow ambiguity, SLA-credit path) resolved in ADR-006.

### ADR-004 (D4) — Persona & policy: "Nova" gated-WORKFLOW system prompt
**Status:** Accepted · **Date:** 2026-06-26 · **Owner:** [HUMAN] · **Source:** `DECISIONS.md:96-128`
**Context:** The system prompt is the highest-leverage artifact (P1 learning).
**Decision:** Human-authored persona + ordered gated WORKFLOW (`configs/system_prompt.md`).
Agent review raised five items: no escalation *mechanism*, workflow ordering, "supervisor" team
missing from KB, no identity verification, no ticket-priority rubric.
**Consequences:** Items 1–3 + rubric resolved by ADR-006; identity verification deferred to the
Phase-4 guardrails (delivered in ADR-012).

### ADR-005 (D5) — Memory policy: six topics + the non-shadow rule
**Status:** Accepted · **Date:** 2026-06-26 · **Owner:** [HUMAN] · **Source:** `DECISIONS.md:132-152`
**Context:** Cross-session memory needs a "worth persisting" policy.
**Decision:** Six extraction topics (identity, account context, communication preferences,
issue history, sentiment, usage context); exclusions (billing amounts, temporary states,
pleasantries). **Non-shadow rule:** tool-authoritative state (plan/billing/storage) is read
live, never memorized. Consolidation: last-write-wins for changeable facts, append-with-dedup
for event history.
**Consequences:** Became the project's signature teaching point; later forced ADR-011's eval fix
and extended to RAG in ADR-021.

### ADR-006 (D6) — Escalation as a real tool + four prompt/KB fixes
**Status:** Accepted · **Date:** 2026-06-26 · **Owner:** [HUMAN] (approved) · **Source:** `DECISIONS.md:156-172`
**Context:** ADR-003/004 review items needed rulings before Phase 1.
**Decision:** `escalate_to_team(customer_id, team, reason)` is a structured, trace-visible tool
(not prose); escalation check promoted to an early mandatory WORKFLOW gate; `supervisor` added
to KB teams; ticket-priority rubric added; SLA-credit path = ticket **and** billing escalation.
**Consequences:** Escalation becomes deterministically evaluable — the backbone of the Safety
pillar and HITL case files.

### ADR-007 (D7) — Phase 1: hand-rolled ReAct loop
**Status:** Accepted · **Date:** 2026-06-26 `[INFERRED]` · **Owner:** [AGENT] · **Source:** `DECISIONS.md:176-189`
**Context:** Phase 1 goal — a characterized, framework-free loop before anything is layered on.
**Decision:** Build `tracing.py`, `llm.py` (own retry/backoff), four tools + registry,
`orchestrator.py` (ReAct + max-iters net), `runner.py` CLI.
**Consequences:** Gate initially blocked on `OPENROUTER_API_KEY`; no Phase 2 until the baseline
was recorded (measure-first held).

### ADR-008 (D8) — Phase 1 gate: GLM tool-call discipline confirmed; fix the eval, not the agent
**Status:** Accepted · **Date:** 2026-06-26/27 `[INFERRED]` · **Owner:** [SHARED] · **Source:** `DECISIONS.md:193-210`
**Context:** 10-query baseline: 10/10 structural, 1.8 iterations avg, zero max-iters trips.
**Decision:** GLM-4.7-Flash is fit for the loop (ADR-002's open item answered). Q4's "failure"
was an eval-contract bug — the agent correctly *proposed-then-confirmed* a ticket; the harness
expected immediate creation. Contract fixed (`confirm_first`).
**Consequences:** Lesson logged: eval expectations must encode *designed* behavior. First entry
in the "the eval was wrong, not the agent" track record.

### ADR-009 (D9) — Phase 2 gate: session memory sound; confirm-before-create became a mandatory gate
**Status:** Accepted · **Date:** 2026-06-26 · **Owner:** [HUMAN] (gate fix approved) · **Source:** `DECISIONS.md:214-257`
**Context:** Baseline 14/15. S1 exposed duplicate ticket creation — "confirm before creating"
lived in a tool description, not a hard gate.
**Decision:** System prompt v3 adds a mandatory two-turn confirm-before-create WORKFLOW gate;
harness's "asks to confirm" check tightened; S5's over-strict compliance check relaxed. Code-level
confirmation gate deferred to Phase 4/5 as the safety net (both-defenses).
**Consequences:** Re-run 15/15. Session memory itself was never the bug — it *exposed* the
discipline gap.

### ADR-010 (D10) — Phase 3: long-term memory pipeline; two findings held the gate
**Status:** Superseded by ADR-011 · **Date:** 2026-06-27 `[INFERRED]` · **Owner:** [SHARED] · **Source:** `DECISIONS.md:261-296`
**Context:** Extractor/store/retriever built per ADR-005; cross-session baseline 1/3.
**Decision:** Hold the gate. Fix X1 (memories injected but not *used* — strengthen the retriever's
context-block instruction, agent lane) and X2 (preference embedded in a transactional turn not
extracted — extraction-prompt rule + 4th few-shot, human lane).
**Consequences:** X3 (non-shadow store hygiene) passed — the decisive ADR-005 test.

### ADR-011 (D11) — Phase 3 gate passed; S5 efficiency check demoted (eval contradicted D5)
**Status:** Accepted · **Date:** 2026-06-27 · **Owner:** [HUMAN] (ruling) · **Source:** `DECISIONS.md:300-331`
**Context:** Fixes landed (cross-session 3/3) but regression dipped 14/15: S5's hard check
penalized re-calling `get_account_info` — exactly what the non-shadow rule *requires*.
**Decision:** Demote S5's "does NOT re-call" check hard → soft. Also add
`OPENROUTER_API_KEY_FALLBACK` auto-switch on 402.
**Consequences:** 15/15 + 3/3. Canonical example of an eval contract contradicting a design
decision — the eval moved, not the design.

### ADR-012 (D12) — Phase 4: input guardrails; injection 39% → 100%
**Status:** Accepted · **Date:** 2026-06-27 · **Owner:** [SHARED] · **Source:** `DECISIONS.md:335-374`
**Context:** Prompt-only defense blocked 7/18 injection attempts.
**Decision:** Gated input pipeline PII → injection → topic. PII: deterministic, Luhn-checked,
redact-and-continue. Injection: three-state regex (block/clean/uncertain) with the LLM classifier
only on *uncertain* (cost control). Topic: lean-allow decision tree. Deferred items delivered:
cross-customer identity gate + code-level confirmation gate.
**Consequences:** 18/18 blocked, PII 6/6, topic 7/7, zero false positives. Measure-first catches:
lean-allow (keyword-less follow-ups), "sue" keyword was muzzling legitimate abuse escalations.

### ADR-013 (D13) — Phase 5: output guardrails + HITL; leak-free 60% → 100%
**Status:** Accepted · **Date:** 2026-06-27 · **Owner:** [SHARED] · **Source:** `DECISIONS.md:378-408`
**Context:** Prompt-only egress was 6/10 leak-free.
**Decision:** Egress scan (PII redact / forbidden-content / cross-customer / over-promise
block+rewrite) + HITL case files, one JSON per escalation. Over-promise rewrites must NOT reveal
why (human ruling); the internal case file captures the reason.
**Consequences:** 10/10 leak-free, 5 case files end-to-end. Mock-data reconciliation (human
catch) prevented vacuous passes.

### ADR-014 (D14) — Phase 6: combined four-pillar eval — GATE PASS
**Status:** Accepted · **Date:** 2026-06-27 · **Owner:** [SHARED] · **Source:** `DECISIONS.md:412-441`
**Context:** Needed one scorecard across Effectiveness/Efficiency/Robustness/Safety.
**Decision:** `eval/run_eval.py` (né run_combined): 33-case golden set, Scout judge (4 dims,
`judge_error` logged + excluded from means, never scored 0), response caching so re-judging never
re-runs the agent.
**Consequences:** PASS — 4.8/4.8/4.97/4.97, injection 100%, output 100%, structural 97%.
Harness fix (pass `customer_id`) moved structural 85% → 97%.

### ADR-015 (D15) — Phase 7: cleanup, output-guard self-customer fix, project close
**Status:** Accepted · **Date:** 2026-06-28 `[INFERRED]` · **Owner:** [SHARED] · **Source:** `DECISIONS.md:445-487`
**Context:** Cleanup pass + a flaky G17: the guard flagged a customer's OWN email as
cross-customer when the session lacked `user_id`.
**Decision:** "Self" = session user + every account looked up across the WHOLE session
(`action_gates.served_customer_ids`). Eval stabilization: judge backoff + Retry-After,
max_iters 6→10, KB `feature_availability_by_tier` entry + top_k 3→5.
**Consequences:** Project 3 COMPLETE — final GATE PASS, best 4.97/4.81/5.0/4.94. The formal
3-consecutive-green run couldn't finish in the dev environment (parked). Human-owned "What I
learned" retrospective still open (`README.md:141-144`).

## Project 4 — Agentic RAG + multi-agent coordinator

Phase-0 decisions locked at the handoff's recommended defaults, human sign-off 2026-06-30
(`DECISIONS_4.md:20-22`).

### ADR-016 (P4-D1) — Vector store: ChromaDB, embedded + persistent
**Status:** Accepted · **Date:** 2026-06-30 · **Owner:** [SHARED] · **Source:** `DECISIONS_4.md:25-31`
**Decision:** ChromaDB over FAISS (no persistence/metadata OOTB) and cloud stores (vendor
dependency); wrapped in one module (`rag/store.py`) so swapping later is single-file.
**Consequences:** Not the fastest — irrelevant at ~20 docs / 121 chunks.

### ADR-017 (P4-D2) — Embeddings: local all-MiniLM-L6-v2
**Status:** Accepted · **Date:** 2026-06-30 · **Owner:** [SHARED] · **Source:** `DECISIONS_4.md:33-38`
**Decision:** Local sentence-transformers (384-dim): zero cost, offline, fast on CPU.
**Consequences:** Revisit gate — switch to hosted embeddings only if measured retrieval quality
is poor (it wasn't: recall 100%). First non-OpenAI-client dependency, but local-only.

### ADR-018 (P4-D3) — Corpus: expand EggCRM's own world, strict superset of the P3 KB
**Status:** Accepted · **Date:** 2026-06-30 · **Owner:** [HUMAN] (signed off) · **Source:** `DECISIONS_4.md:40-49`
**Decision:** 20 human-signed markdown docs (`data/knowledge_base/docs/`), three doc_types.
**Hard constraint:** strict superset of `novacrm_kb.json` with zero contradictions — otherwise
grounding scores against a corpus that disagrees with the tools (P3's mock-data-mismatch class).
**Consequences:** Controlled content ⇒ eval cases with known-correct answers.

### ADR-019 (P4-D4) — Chunking: semantic by heading + per-chunk metadata
**Status:** Accepted · **Date:** 2026-06-30 · **Owner:** [SHARED] · **Source:** `DECISIONS_4.md:51-57`
**Decision:** Split on `##` headings; every chunk carries `doc_title`/`section`/`doc_type` —
metadata filtering is retrieval's second defense alongside vector similarity.
**Consequences:** Sub-splitting deferred until measurement demands it (it didn't; parked).

### ADR-020 (P4-D5) — Agent communication: full delegation, not a function call
**Status:** Accepted · **Date:** 2026-06-30 · **Owner:** [SHARED] · **Source:** `DECISIONS_4.md:59-65`
**Decision:** The RAG agent is a real agent (own prompt, tools, ReAct loop); Nova routes by
intent and delegates. Genuine Coordinator pattern is the learning goal.
**Consequences:** Accepted latency cost — quantified at ~34s/delegated turn in ADR-031.

### ADR-021 (P4-D6) — Grounding: both runtime hook and eval dimension
**Status:** Accepted · **Date:** 2026-06-30 · **Owner:** [SHARED] · **Source:** `DECISIONS_4.md:67-74`
**Decision:** Eval-time grounding score is the primary metric; a runtime check for high-stakes
answers is the second defense. Non-shadow rule extended to three sources (docs/memory/tools).
**Consequences:** Realized in ADR-029 as detect-annotate (never block), positive + negative-control
eval — both 100%.

### ADR-022 (P4-D7) — Framework: ADK for the multi-agent layer ONLY; RAG stays hand-built
**Status:** Accepted · **Date:** 2026-06-30 · **Owner:** [HUMAN] (ruling) · **Source:** `DECISIONS_4.md:76-88`
**Context:** The handoff left this open (stay raw / ADK-for-multi-agent / ADK-everywhere).
**Decision:** Option (b). **Deliberately overrides P3's "framework-free" ground rule**, scoped to
the coordinator/delegation layer. ADK's `LiteLlm` adapter accepted as ADK-internal plumbing to
keep GLM-via-OpenRouter. Chunking/embedding/store/retrieval and the RAG agent's loop stay raw.
**Consequences:** The repo's defining constraint. LiteLLM re-enters as plumbing — its missing
402 rotation later surfaced operationally (ADR-028, ADR-029).

### ADR-023 (P4-P1a) — Phase-1 baseline model-of-record: Groq Scout STOPGAP
**Status:** Accepted · **Date:** 2026-06-30 · **Owner:** [HUMAN] (call) · **Source:** `DECISIONS_4.md:94-107`
**Context:** OpenRouter hard-402'd; probing showed keys KEY…KEY5 share ONE drained account —
more keys ≠ more credit.
**Decision:** Accept the Scout run as baseline-of-record, explicitly labeled STOPGAP; GLM re-run
owed once credits return.
**Consequences:** Discharged when the Phase-2 routing baseline became the first official GLM
pass of the RAG agent (ADR-027 / `DECISIONS_4.md:174-181`).

### ADR-024 (P4-P1b) — Eval curation: R5/R10/R8 corrected (eval bugs, not agent bugs)
**Status:** Accepted · **Date:** 2026-06-30 · **Owner:** [HUMAN] (signed off) · **Source:** `DECISIONS_4.md:109-127`
**Decision:** R5: score the mechanism ("bearer"+"authorization"), not a literal bigram. R10: the
"native iOS app?" trap was answerable by grounded inference — replaced with "dark mode?" (zero
adjacent facts ⇒ forces a true decline); decline markers widened. R8: score the load-bearing
facts ("14 days", "pro-rated"), not a doc-title token.
**Consequences:** Phase-1 gate: recall 100%, correctness 100%, honest decline — PASS.

### ADR-025 (P4-P2a) — ADK scoped to routing/delegation; P3 guardrails/memory WRAP the coordinator
**Status:** Accepted · **Date:** 2026-06-30 · **Owner:** [HUMAN] (signed off) · **Source:** `DECISIONS_4.md:139-147`
**Context:** Options: wrap ADK in hand-built pre/post; port guardrails into ADK callbacks; full
ADK rebuild.
**Decision:** Wrap. Input screen before the `LlmAgent`; output guard + grounding + memory
extraction after; P3 code unchanged. Action gates move into `FunctionTool` closures.
**Consequences:** Lowest regression risk against a signed-off suite; honors ADR-022 literally.
Corollary: anything driving the raw ADK agent (e.g. `adk web`) bypasses the guardrails (ADR-030).

### ADR-026 (P4-P2b/c) — RAG specialist = the hand-built agent behind an `AgentTool`; deps pinned narrowly
**Status:** Accepted · **Date:** 2026-06-30 · **Owner:** [SHARED] · **Source:** `DECISIONS_4.md:149-161`
**Decision:** Don't re-express the RAG agent as an ADK `LlmAgent` — that would invalidate the
Phase-1 baseline. Bridge via a thin `RagSpecialistAgent(BaseAgent)`. Pin `google-adk` + `litellm`
explicitly, NOT `google-adk[extensions]` (drags langgraph/llama-index/etc.).
**Consequences:** Measured ADK finding: `AgentTool` runs the sub-agent in a separate inner
Runner, hiding its events — retrieval provenance is recovered via an out-of-band `sink` dict.

### ADR-027 (P4-P2d–h) — Centralized active-key wiring; Phase-2 gates green after a caught regression
**Status:** Accepted · **Date:** 2026-06-30 · **Owner:** [SHARED] · **Source:** `DECISIONS_4.md:167-222`
**Context:** KEY6 (fresh funded account) unblocked GLM. First coordinator golden regression
FAILED — the router prompt had collapsed P3's scenario→team escalation rules into one vague line.
**Decision:** `config` derives `OPENROUTER_ACTIVE_KEY` (funded-first) for both stacks — LiteLlm
has no rotation, so it must be pointed at a funded key directly. Restore the full escalation
protocol into `COORDINATOR_INSTRUCTION` (mandatory first gate + explicit scenario→team map).
**Consequences:** Routing baseline 10/10; golden regression at P3 parity (4.83/4.67/4.97/4.9);
the regression harness *caught a real regression* — the measure-first discipline's keep earned.

### ADR-028 (P4-D8) — Phase 3 rescoped to grounding + routing discipline; retrieval tuning dropped
**Status:** Accepted · **Date:** 2026-06-30 · **Owner:** [HUMAN] (directed) · **Source:** `DECISIONS_4.md:226-246`
**Context:** The plan sketched Phase 3 as retrieval optimization, but Phase-1 already measured
100% recall/correctness — tuning would be evidence-free.
**Decision:** Rescope to the two measured gaps: the deferred grounding check (ADR-021) and the
RC3 account+RAG discipline seam. Characterize before fixing: `eval/tier_discipline.py` turns the
"occasional" flicker into a pass-RATE gate (5 questions × 5 reps, asserted on the TRACE).
**Consequences:** Baseline showed the seam was SYSTEMATIC (8%, masked by 96% answer accuracy).
Order correction (human): fix discipline BEFORE grounding, or grounding would rubber-stamp
tier-blind answers. Fix → 100% (25/25). The grounding eval then caught the fix's over-correction
(named-tier questions punted) → router rule split "my plan" vs "the <Tier> plan"; both directions
re-verified. Lesson: a discipline rule and its inverse both need a test.

### ADR-029 (P4-D8 close-out) — Close Phase 3 on evidence; decline the cosmetic 33/33 re-run
**Status:** Accepted · **Date:** 2026-07-01 · **Owner:** [HUMAN] (call) · **Source:** `DECISIONS_4.md:295-308`, `ACTIVE.md:150-171`
**Context:** Golden regression: 30/33 scored clean at Phase-2 parity; the 3 misses were mid-run
key-402s (re-confirmed correct individually) + 2 transient judge errors.
**Decision:** Phase 3 is COMPLETE on the evidence; a fresh recorded 33/33 was deemed process
theater. Hardened `run_eval.py` (per-case retry + record-and-continue); G33 decline marker made
robust. LiteLlm's missing 402 rotation logged as a hardening item (`PARKING_LOT.md`).
**Consequences:** The recorded artifact honestly labeled credit-limited, not quality-limited.

### ADR-030 (P4-D9) — `adk web` wired as an inspection surface (guardrails bypassed)
**Status:** Accepted · **Date:** 2026-07-01 · **Owner:** [SHARED] · **Source:** `DECISIONS_4.md:310-317`
**Decision:** `adk_app/nova/` exports `root_agent` = the coordinator's `LlmAgent` (same instance,
no drift) so `adk web adk_app` gives a free routing/delegation trace view.
**Consequences:** Accepted limitation: the dev UI drives the RAW agent, bypassing the hand-built
guardrails/memory — inspection surface, not the production path (`adk_app/README.md`).

### ADR-031 (P4-D10) — Phase 4: aggregate the passing gates, don't re-run; measure delegation cost
**Status:** Accepted · **Date:** 2026-07-01 · **Owner:** [HUMAN] (call) · **Source:** `DECISIONS_4.md:321-343`
**Decision:** `eval/run_phase4.py` consolidates the five gate artifacts into one capstone
scorecard (re-running complete evidence = process theater) and adds the two never-measured
multi-agent metrics: context sharing (verified) and delegation latency.
**Consequences:** OVERALL GATE PASS (all six sub-gates). Honest finding: genuine delegation costs
~43.8s vs 9.4s direct (~34s overhead/turn) — the ADR-020 trade-off, quantified; production
mitigations parked.
