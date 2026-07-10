# Active State

> Cold-start file: what's done, what's next, what's blocked. Update at the end of
> each working session. (Same pattern as Project 1.)

## CURRENT PROJECT: Project 4 — Agentic RAG + Multi-Agent (Coordinator)
Plan: `localdoc/project-4-handoff.md`. Decisions: `DECISIONS_4.md`.

**CURRENT: Phase 5 — IN PROGRESS** (docs + retrospective). Phases 0/1/2/3/4 COMPLETE (Phase 4
combined eval OVERALL GATE PASS). Phase-5 docs DRAFTED (`README_PROJECT4.md` + README pointer);
only the human-owned framework-comparison NARRATIVE remains. Then Project 4 is done.
Phase 3 closed on the evidence (human call, 2026-07-01): RC3 discipline 8%→100%, grounding gates
PASS, golden regression NO regression (30/33 scored clean at Phase-2 parity + 3 re-confirmed
individually) — a cosmetic 33/33 re-run was declined as process theater. `OPENROUTER_API_KEY7` added
+ wired as the active key (KEY7→KEY6→…). ADK web UI live (`adk web adk_app`). 2026-07-01.

## CI EVAL GATE — BUILT, pending human enablement (P4-D11). 2026-07-10.
Implements the signed-off spec (`docs/ci-eval-gate-spec.md`; runbook `docs/ci-eval-gate.md`).
Evaluators UNMODIFIED — added a thin compare/report layer + workflow:
- `eval/ci_gate.py` (stdlib-only compare logic: threshold = baseline − tolerance, hard/soft
  classes, judge pin, smoke selection) + `eval/baselines.json` (contract; **values are
  PLACEHOLDERS** from recorded P3/P4 scores) + `eval/routing_cases.py` (RT1/RT2
  refund-eligibility trace cases; tier cases imported from `tier_discipline.py` unmodified).
- `run_eval.py` gained gate flags (`--mode smoke|full --baseline --report`; exit 0/1/2 —
  2 = infra, judged NEUTRAL in CI so flakiness never reads as regression). Judge in gate mode:
  median-of-3 at temp 0, per-sample Scout↔GLM fallback. Legacy invocations unchanged.
- `.github/workflows/eval-gate.yml`: PR→smoke, main/nightly/dispatch→full; path-filtered;
  uploads the report artifact; posts/updates a PR comment table; publishes the merge-blocking
  **`eval-gate-verdict` check run** (success/failure/neutral).
- **Demo feature (prompt, D4 — NEEDS SIGN-OFF):** `COORDINATOR_INSTRUCTION` now splits refund
  REQUEST (→ billing escalation, unchanged) from refund-ELIGIBILITY question (→ verify account
  FIRST via `get_account_info`, then `nova_docs`, then answer for their account; generic
  "what's your refund policy?" carve-out stays docs-only). Both-defenses: workflow step + RULES
  bullet. This is the trajectory regression the demo blocks (judge green / routing red).
- **Verified offline:** 20 new unit tests (`tests/test_ci_gate.py`) pass; stubbed end-to-end sim
  drove all three exit codes incl. the demo contrast (hard_failures=[routing_discipline],
  correctness still passing). Live smoke/full runs NOT executed here (no keys in this env).
- **HUMAN TODO to enable:** (1) D4 sign-off on the prompt wording; (2) add `OPENROUTER_CI_KEY`
  + `GROQ_CI_KEY` secrets (D-CI-6 — standalone budgets); (3) re-baseline on main:
  `python eval/run_eval.py --mode full --report eval/reports/rebaseline.json` → copy `measured`
  into `baselines.json`; (4) branch protection: require `eval-gate-verdict` + up-to-date;
  (5) optionally run the red→green demo (runbook §Demonstration, branch `demo/routing-regression`).

### Phase 1 — COMPLETE (standalone RAG agent + baseline gate PASS). 2026-06-30.
- **RAG agent BUILT** (`src/novacrm_agent/agents/rag_agent.py`): NovaDocs, own hand-rolled ReAct
  loop (framework-free per P4-D7 — ADK enters at Phase 2, not here), two retrieval tools
  (`retrieve_docs` + `search_by_metadata` = the P4-D4 both-defenses), grounding-first gated
  WORKFLOW prompt (answer ONLY from retrieved docs; honest decline when not covered). `run()`
  returns a `RAGResult` carrying answer + every chunk retrieved (so the baseline scores recall +
  grounding without re-retrieving). Carries a `tool_use_failed` force-answer fallback for
  server-side tool-parser quirks (Groq/Llama).
- **Phase 1 baseline GATE PASS** (`eval/rag_baseline.py` → `rag_baseline.json`): 10 known-answer
  cases (R1–R10). Recall **100%** (9/9 gold), correctness **100%** (10/10), R10 honest decline YES.
  Gate = recall ≥80% ∧ correctness ≥80% ∧ R10 declines → **PASS**.
  - **Model-of-record = Groq Llama-4-Scout STOPGAP** (human call, 2026-06-30). **GLM re-run still
    OWED and still BLOCKED:** the primary GLM-4.7-Flash gate can't run because OpenRouter is out of
    credits. VERIFIED 2026-06-30: all five keys in `.env` (`OPENROUTER_API_KEY`, `_KEY2…_KEY5`) 402
    at `max_tokens=1024` and report the **same `user_id`** — they're one drained account, so adding
    keys doesn't add credit. `config.OPENROUTER_FALLBACK_KEYS` was extended to include `_KEY4/_KEY5`
    (chain now KEY→KEY2→…→KEY5), so the moment the **account is topped up** the re-run just works:
    `python eval/rag_baseline.py` (default `--provider openrouter`). This blocker also gates Phase 2
    runtime testing on GLM (ADK's LiteLlm talks to the same account).
  - **Eval curation this session** (human-signed-off): R5 scorer was over-strict (required literal
    "api key"; a correct "bearer token / Authorization header" answer failed) → now
    `expect_all=["bearer","authorization"]`. R10's old "native iOS app?" trap was answerable by
    *grounded inference* (docs say "browser-based — nothing to install") → replaced with "Does
    EggCRM have a dark mode?" (zero adjacent doc facts → forces a true decline); `DECLINE_MARKERS`
    widened to accept "does not mention … in the documentation". **R8** scorer required the
    non-load-bearing doc-title token "billing" (flipped on Scout wording variance) → tightened to
    `expect_all=["14 days","pro-rated"]` (the actual refund-policy facts). Correctness 90%→**100%**.
- **Tests:** `tests/test_rag_agent.py` (6 offline loop tests — tool dispatch, retrieval
  accumulation, RAGResult helpers, `tool_use_failed` fallback, non-tool-use 400 propagates,
  max_iters termination; LLM + retriever both faked). **60 tests pass** (54 prior + 6), pyflakes clean.
## Phase 2 — COMPLETE (ADK coordinator; both gates PASS on GLM-4.7-Flash). 2026-06-30.
**GATES (ship model, GLM-4.7-Flash):** routing baseline **10/10** (`routing_baseline.json`); golden
regression **GATE PASS** (`combined_report_coord.json`) — corr 4.83 / help 4.67 / safe 4.97 /
persona 4.9 (matches P3's 4.83/4.66/5.0/4.86), golden structural 97% (behavioral 33/33 after the
G33 marker fix). The multi-agent coordinator matches the P3 single-agent baseline on quality/safety
while adding genuine ADK delegation. Key event: the regression CAUGHT a real escalation-routing
regression (router prompt had dropped P3's scenario→team rules) → fixed → re-run green (see P4-P2g).
**ADK enters here (P4-D7).** Foundation decisions this session (human-signed-off): (1) ADK scoped
to routing/delegation ONLY — the P3 guardrails/memory stay hand-built and *wrap* the coordinator
(input screen before, output guard + memory extraction after), not ported into ADK callbacks;
(2) the RAG specialist stays the hand-built Phase-1 `RAGAgent`, exposed via an ADK `AgentTool` (so
the Phase-1 baseline stays valid).
- **Deps:** `google-adk` 2.3.0 + `litellm` 1.83.14 installed and pinned in `requirements.txt`
  (explicit `google-adk` + `litellm`, NOT the heavy `google-adk[extensions]` bundle, which also
  pulls langgraph/llama-index/etc. and upgraded `openai`→2.24.0 — all 70 tests survive the churn).
  ADK→LiteLlm→provider round-trip verified live on Groq.
- **Built:** `agents/rag_specialist.py` (`RagSpecialistAgent` — thin ADK `BaseAgent` wrapping the
  hand-built `RAGAgent`; provenance recovered via an out-of-band `sink` because `AgentTool` runs the
  sub-agent in a separate inner Runner that hides its events) + `agents/coordinator.py`
  (`NovaCoordinator`: ADK `LlmAgent` "nova" w/ gated-WORKFLOW router prompt; tools = RAG `AgentTool`
  + `get_account_info`/`create_support_ticket`/`escalate_to_team` `FunctionTool`s carrying the two
  P3 action gates; hand-built input/output guardrails + session recording + `end_session` memory
  extraction wrap the ADK run; sync bridge over `Runner.run_async`).
- **Smoke (Groq stopgap):** doc question → routes to `nova_docs`, correct $79 answer + provenance
  (`['01-getting-started.md','02-plans-and-pricing.md','16-billing-and-plan-changes.md']`); account
  question (CUST-1003) → routes to `get_account_info`, correct Enterprise/85-seats. Clean tool names.
- **Tests:** `tests/test_coordinator.py` (10 offline — both action gates incl. guardrails-off bypass,
  `_harvest` event reconstruction, adapter query-extraction, result helper). **70 tests pass**, clean.
- **GLM UNBLOCKED (2026-06-30):** `OPENROUTER_API_KEY6` = a FRESH FUNDED account (different from the
  drained KEY…KEY5). `config` now derives `OPENROUTER_ACTIVE_KEY` (funded key first) — both the
  hand-built `LLMClient` default AND ADK's `build_litellm` use it (LiteLlm has no 402 rotation, so
  it MUST point at a funded key directly). GLM-4.7-Flash verified live end-to-end through ADK/LiteLlm.
- **Phase 2 routing baseline — GATE PASS on GLM-4.7-Flash** (`eval/routing_baseline.py` →
  `routing_baseline.json`, the official gate model, not Scout): 10 boundary-focused cases RC1–RC10
  (anchors + account/RAG boundaries, known-issue-not-ticket, refund-is-escalation, multi-intent,
  not-in-docs decline, pure escalation, cross-customer gate). **Routing 90%, answer 90%, overall
  90% (9/10)** → gate (routing ≥80% ∧ overall ≥70%) **PASS**. This is also the first OFFICIAL GLM
  pass of the RAG agent (RC1/3/4/6/7/8 delegated to `nova_docs` + grounded correctly) — validates
  both stacks on the ship model in one run; no Scout-vs-GLM tool-call divergence observed.
  - **RC5 → same root cause as the regression finding below (now FIXED):** refund routing defaulted
    to ticket-creation instead of billing escalation.
- **P3 regression harness ADAPTED to the coordinator:** `eval/run_eval.py --coordinator` drives
  `NovaCoordinator` over the same 33 golden cases + Groq judge, writing SEPARATE artifacts
  (`golden_responses_coord.json`, `combined_report_coord.json`, `outputs/eval-report-coord.md`) so
  the frozen P3 single-agent deliverable is never clobbered. `CoordinatorResult` gained
  `iterations`/`total_tokens` (from ADK event usage) for the efficiency pillar.
- **REGRESSION FOUND + FIXED — escalation routing (the measure-first gate earned its keep):** first
  coordinator regression on GLM FAILED the gate. Means were fine (corr 4.83 / help 4.69 / safe 5.0 /
  persona 4.97, ≥ P3) but it failed on escalation: **G21** refund→(recited policy, no escalation),
  **G22** cancel→escalated to *billing* not retention, **G23** GDPR→proposed a ticket not compliance,
  **G24** "sue"→*compliance* not supervisor, **G26** update-billing→no escalation; plus **G15**
  correctness=1 (claimed it "can't look up tickets" though `get_account_info` returns `open_tickets`).
  Root cause: the coordinator's router prompt had collapsed P3's detailed ESCALATION RULES
  (scenario→team) into one vague line, so GLM guessed teams. **Fix (human-signed-off, D4):** ported
  P3's protocol into `COORDINATOR_INSTRUCTION` — escalation as a mandatory FIRST gate + explicit
  mapping (refund→billing, cancel→retention, GDPR/data-deletion→compliance, abuse/legal-threat→
  supervisor, payment-change→billing, SLA-credit→ticket+billing) + open-tickets note. **Targeted GLM
  smoke: all 6 now correct** (G15 surfaces TICK-5567; G21–G24/G26 escalate to the right team).
  **Full regression RE-RUN IN PROGRESS on GLM** — record the recovered gate when it lands. (Note:
  transient Groq judge_errors on G08/G20/G21/G22 in the first run — re-judge if they recur.)
- **Tests: 70 pass**, pyflakes clean (10 coordinator + 6 RAG-agent + 54 prior).
- **ADK web UI set up** (2026-07-01): `adk_app/nova/` exports `root_agent` = the coordinator's
  `LlmAgent` (via new `NovaCoordinator.adk_agent`; one definition, no drift). Run
  `./venv/bin/adk web adk_app` (UI at :8000) or `./venv/bin/adk run adk_app/nova`. Discovery
  verified. **Caveat:** the dev UI drives the RAW ADK agent — it BYPASSES the hand-built
  guardrails/memory (those wrap `run()`, outside ADK); inspection view, not the production path.

## Phase 3 — IN PROGRESS: "grounding & routing discipline" (P4-D8 rescope). 2026-07-01.
**Rescoped from "retrieval optimization" → grounding + discipline** (P4-D8, human-directed): Phase-1
recall/correctness are already 100% on GLM, so retrieval tuning is evidence-free. Two measured gaps
instead: (1) the deferred P4-D6 grounding check, (2) the RC3 account+RAG discipline seam.
- **RC3 seam HARD-MEASURED FIRST (measure-before-fix):** `eval/tier_discipline.py` — 5 tier-dependent
  questions (need the caller's plan AND a tier→availability doc fact) × 5 reps, asserting on the TRACE
  that `get_account_info` runs BEFORE/ALONGSIDE the `nova_docs` delegation. **Baseline (GLM,
  25 runs): discipline 8% (2/25); T1–T4 = 0/5, T5 flickers 2/5.** The seam is SYSTEMATIC, not
  "occasional" — the coordinator answers from generic docs and checks the account after or never.
  **Answer accuracy 96% MASKS it** (the generic doc answer happens to match these customers' tiers);
  it would be wrong for a mismatched tier (e.g. a Starter customer). `tier_discipline.json` written.
- **RC3 discipline FIX APPLIED + RE-MEASURED — 8% → 100% (25/25).** Ordering was corrected first,
  BEFORE grounding (human call: grounding on a tier-blind answer would rubber-stamp a generic reply
  as "doc-supported" and mask the real gap — the answer isn't ungrounded, it's un-personalized).
  Fix = `COORDINATOR_INSTRUCTION` gained a gated "TIER-DEPENDENT question" rule ((a) `get_account_info`
  FIRST → (b) `nova_docs` → (c) answer for THEIR tier) + a reinforcing RULE (prompt content, D4,
  human-directed). Re-run (GLM, 25 runs): **discipline 100%, no flicker, GATE PASS** (target was
  80%+). Answer accuracy 96% (T5 one rep dropped the "10,000" limit — content variance, not the seam).
- **P4-D6 GROUNDING CHECK BUILT — both gates PASS on GLM.** Three pieces: (1) shared
  `guardrails/grounding.py` LLM-judge (Groq Scout) "is the answer supported by the retrieved
  passages?" — declines count as grounded, fails OPEN on judge error; (2) RUNTIME detect-annotate
  hook in the coordinator (flags weakly-grounded RAG answers < score 4, appends a soft verification
  hedge, NEVER blocks — human-chosen posture); (3) self-validating `eval/grounding_eval.py`.
  `RagSpecialistAgent` sink now carries the retrieved chunk TEXTS (`rag_chunks`) to ground against.
  **Result (GLM): positive grounded-rate 100% (10/10), negative-control catch-rate 100% (3/3)** —
  fabricated answers all flagged score=1, so the check discriminates (not vacuous). 6 offline
  grounding tests. `grounding_eval.json` written.
- **OVER-CORRECTION found by the grounding eval + fixed (measure-first catch #2 this phase):** the
  first grounding run exposed that the RC3 fix had OVER-triggered — the coordinator demanded a
  customer ID even for questions that NAME a tier ("Zapier on the Professional plan?"), punting
  instead of delegating to `nova_docs` (R3/R4/R6 → empty route, hollow "grounded" default). The
  tier_discipline eval missed it (only tested "my plan" phrasings). **Fix:** sharpened
  `COORDINATOR_INSTRUCTION` to split "my/our plan" (tier unknown → account-first) from "the <Tier>
  plan" (tier named → straight to `nova_docs`, no lookup). **Both directions re-verified on GLM:**
  tier_discipline still 100% (25/25); grounding positives R3/R4/R6 now `nova_docs` + score 5 (real,
  not hollow).
- **Golden regression on the current prompt — NO quality regression** (project rule: regress every
  phase). Ran `run_eval.py --coordinator`: **30/33 cases scored clean — corr 4.71 / help 4.57 /
  safe 4.96 / persona 4.82**, zero structural fails, at Phase-2 parity (4.83/4.66/5.0/4.86). The
  recorded GATE FAIL is **entirely infrastructure**, not quality: **G31/G32/G33 hit 402 (KEY6
  drained mid-run)** — re-ran individually afterwards, all correct (G31 answers, G32 clarifies, G33
  refuses cleanly); **G15/G26** were transient Groq *judge* errors (excluded from means). A clean
  RECORDED 33/33 PASS is **owed once KEY6 is topped up** (human chose: top-up → one clean run).
  - **Hardened `run_eval.py`:** per-case retry + record-and-continue, so one transient 402/timeout
    can't crash a 33-case run (an earlier attempt died on an uncaught ADK/LiteLlm timeout).
  - **G33 decline-marker made robust:** GLM rephrases the cross-customer refusal every run
    ("only view your own account" / "only provide account details for your own account, not for
    other customers") → `DECLINE_MARKERS` now keys on "your own account" (+ "not for other
    customers"). Both observed phrasings pass; behavioral structural is 33/33.
- **FINDING — ADK/LiteLlm has NO key-fallback rotation** (unlike the hand-built `LLMClient`, which
  rotates OPENROUTER_ACTIVE_KEY→fallbacks on 402). So when the coordinator's active key drains, its
  GLM calls hard-fail mid-run with no recovery. All other keys are drained too, so rotation wouldn't
  help right now — logged as a hardening item. KEY6 is hovering at the credit threshold.
- **Phase 3 status: COMPLETE** (closed on evidence, human call 2026-07-01). Both P4-D8 items
  DONE + validated (RC3 discipline 8%→100%; P4-D6 grounding gates PASS; no golden regression —
  30/33 scored clean at Phase-2 parity, 3 re-confirmed individually). The recorded golden artifact
  stays 30/33 (credit-limited, not quality); a fresh 33/33 run was deemed process theater given the
  substance is validated. 76 offline tests pass.

## Phase 4 — COMPLETE: combined evaluation across both agents (OVERALL GATE PASS). 2026-07-01.
`eval/run_phase4.py` → `phase4_report.json` + `outputs/phase4-report.md`. Consolidates every phase
gate into ONE capstone scorecard (aggregates the passing gates, doesn't re-run — evidence complete)
and adds the two multi-agent metrics that were never measured. **ALL SIX SUB-GATES PASS → OVERALL
PASS:**
- Four-pillar golden (means over the 28 cleanly-scored cases): corr 4.71 / help 4.57 / safe 4.96 /
  persona 4.82, no floor violations (credit-limited artifact honestly labeled: 3 cases key-402'd,
  re-confirmed correct individually).
- Retrieval recall 100% · Routing accuracy 100% · Grounding +100%/−100% · Tier discipline 100%.
- **Context sharing VERIFIED** (deterministic temp-store: customer memory reaches the coordinator;
  RAG gets shared session state via AgentTool but is docs-only per the D5 boundary).
- **Delegation latency (P4-D5's deferred metric, now measured): 43.8s delegated vs 9.4s direct →
  ~34s coordinator-pattern overhead.** Honest finding: genuine agent-to-agent delegation is
  expensive here (coordinator route → inner Runner → RAG's own retrieve+synthesize loop →
  coordinator synthesis → grounding check = many sequential GLM calls). Not gated; a real tradeoff
  to note in the retrospective (production would stream/parallelize/cache).
## Phase 5 — IN PROGRESS: documentation + retrospective (final). 2026-07-01.
- **DRAFTED — `README_PROJECT4.md`:** the P4 build doc — architecture diagram (guardrails-wrap-ADK,
  RAG delegation, grounding), layout, run instructions (`ingest`, `adk web adk_app`, `NovaCoordinator`
  snippet, eval scripts), the Phase-4 combined results table (all gates PASS), and a retrospective
  section. Main `README.md` gets a pointer to it (P3 README preserved, DECISIONS/DECISIONS_4 pattern).
- **HUMAN-OWNED — the retrospective NARRATIVE** (with-framework/ADK vs framework-free-P3): I drafted
  the MEASURED observations (what ADK gave: AgentTool delegation + adk web tracing; what it cost:
  LiteLlm no-fallback, AgentTool provenance hidden via inner Runner, ~34s delegation overhead,
  guardrails kept hand-built) and left the *conclusions/recommendation* as prompts for the human (D4).
- **Optional hardening (not required to close P4):** a LiteLlm 402 retry/key-rotation wrapper (the
  coordinator's single-point-of-credit-failure finding). Deferred unless wanted.
- **NEXT:** human writes the retrospective conclusions → Project 4 COMPLETE. 76 offline tests pass.

## Phase 0 — COMPLETE (decisions + corpus + RAG pipeline). 2026-06-30.
- **Decisions LOCKED** (P4-D1…D7 in `DECISIONS_4.md`): Chroma · local all-MiniLM-L6-v2 ·
  expand EggCRM corpus · semantic-by-heading chunking + metadata · full agent delegation ·
  grounding (runtime+eval) · **ADK for multi-agent layer only** (RAG pipeline hand-built).
- **Corpus SIGNED OFF** (human, 2026-06-30): 20 markdown docs under
  `data/knowledge_base/docs/` (10 feature_guide / 5 api_reference / 5 troubleshooting),
  strict superset of `novacrm_kb.json`. Index + invented-detail list in `docs/README.md`.
- **RAG pipeline BUILT + INGESTED** (`src/novacrm_agent/rag/`): `chunker` (semantic-by-heading,
  121 chunks), `embedder` (all-MiniLM-L6-v2, 384-dim, local), `store` (ChromaDB cosine,
  `data/rag_store/`, gitignored), `ingest` (`python -m novacrm_agent.rag.ingest`), `retriever`
  (`retrieve_docs` + `search_by_metadata`). Smoke-tested: all 5 probe queries top-hit correctly.
  **54 tests pass** (43 P3 + 11 new `tests/test_rag.py`), pyflakes clean.
- **NEXT — Phase 1:** standalone RAG agent (own ReAct loop, tools = `retrieve_docs` /
  `search_by_metadata`, "answer ONLY from retrieved docs" prompt) + 10-question baseline
  (retrieval recall + answer correctness). **Framework note:** ADK enters at Phase 2, not Phase 1.

## ENV NOTE 2 (2026-06-30) — two copies + stale venv
P4 works in **`~/Projects/novacrm 2`** (copy made today); **`~/Projects/novacrm`** is the frozen
P3 deliverable. This venv was copied along, so its scripts/install were stale: `./venv/bin/pip`
has a dead shebang (use **`./venv/bin/python -m pip`**), and the editable `.pth` pointed at the
old `novacrm/src` — **realigned** via `python -m pip install -e . --no-deps` to `novacrm 2/src`.
`import novacrm_agent` now resolves here; `-m` invocations work without PYTHONPATH.

---

## Project 3 — COMPLETE (history)

## Phase 7 — COMPLETE. PROJECT DONE.
**Phase 7 — COMPLETE. PROJECT DONE.** (D15) All 7 phases delivered. Final combined eval **GATE
PASS**: correctness 4.83 / helpfulness 4.66 / safety 5.0 / persona 4.86; injection 100% · output
100% · PII 6/6 · topic 7/7 · HITL 5; golden structural 97%, regression 15/15, cross-session 3/3.
43 tests pass, pyflakes clean. Deliverables: `README.md`, `DECISIONS.md` (D1–D15 + Plan-vs-Actual),
`docs/project-4-handoff.md`, server in package (`python -m novacrm_agent.server`), web UI (`webui/`).

### Phase 7 fixes (D15)
Cleanup found + fixed an output-guard cross-customer false-positive (own email when session has no
user_id). Eval stabilization: judge backoff + Retry-After (transient judge_errors), max_iters 6→10
(G30 convergence), KB `feature_availability_by_tier` entry + top_k 3→5 (G08 Zapier-tier gap).

### Gate status (honest)
G17 (confirm-then-create) was flaky — output guard flagged the customer's OWN email as
cross-customer because the lookup was a PRIOR turn. Fixed: `action_gates.served_customer_ids`
now spans the whole session (unit-tested, 44 tests pass). Post-fix completed runs PASS (best
4.97/4.81/5.0/4.94, no floors). The formal **3-consecutive-green gate could NOT be completed in
this environment** (background evals get reaped; foreground hits the 10-min cap). **Run it in a
stable terminal:** `for n in 1 2 3; do ./venv/bin/python -m eval.run_eval | grep GATE; done`.

### Only remaining (human-authored)
README "What I learned" — the with-framework (P1/ADK) vs without-framework (P3) retrospective.

### Session log — 2026-06-27 (end of day)
Completed today: Phase 3 fixes (X1 recall + X2 extraction → cross-session 3/3, D11), Phase 4
input guardrails (injection 39%→100%, D12), Phase 5 output guardrails + HITL (output 60%→100%,
D13), Phase 6 combined eval (GATE PASS, D14). Also added fallback-key chain (KEY2→KEY3) and
realistic mock emails. 39 offline tests + all phase baselines green. **Stopping point: agent is
complete and fully evaluated.** Tomorrow = a simple UI; Phase 7 (README/retrospective) after.

## Done
- Scope locked (domain, memory depth, guardrail breadth, observability, models).
- Project skeleton: `src/novacrm_agent/{tools,memory,guardrails}/`, `tests/`, `eval/`,
  `data/`, `configs/`.
- `requirements.txt`, `pyproject.toml`, `config.py` (model/provider wiring), `.gitignore`,
  `.env.example`.
- `DECISIONS.md` — D1 (observability), D2 (models) decided; D3–D5 drafted.
- Smoke test passing (`pytest`).

## UI / demo
- **`server.py`** (repo ROOT) — FastAPI wrapper for `localdoc/novacrm-demo.jsx`:
  `GET /` (serves the React demo page), `GET /health`, `POST /chat {message, session_id,
  customer_id}` → `{response, trace}`. Trace = guardrails.{input,output},
  tools[].{name,input,output}, memories[].{topic,fact}, iterations, latency_ms, tokens.
  `GET /` renders the .jsx via CDN React + in-browser Babel (NEEDS INTERNET for unpkg); it
  strips the one `react` import + `export default` at request time, so the .jsx stays source of
  truth. Self-contained (adds `src` to path); CORS open.
  Run: `./venv/bin/python server.py` (default :8001; `--port N` or `PORT=N`). Open the URL in a
  browser to see the demo. `tests/test_server.py` offline (TestClient). **42/42 tests pass.**
- **Web UI build:** the `.jsx` is bundled to static JS with esbuild (NO in-browser Babel — gave a
  blank page; NO CDN — works offline). Files: `webui/{main.jsx,index.html}` + built `webui/app.js`
  (~170KB) + **`package.json` at the REPO ROOT**. Server serves `GET /` → index.html, `GET /app.js`
  → bundle (FileResponse reads from disk, so a rebuild needs no server restart).
  **Setup:** `npm install` (once). **Rebuild after editing the .jsx:** `npm run build`.
  - **CRITICAL gotcha (fixed):** deps MUST live at the repo root, not `webui/node_modules`.
    `localdoc/novacrm-demo.jsx` is a sibling of `webui/`, so a webui-local install made esbuild
    resolve TWO Reacts (webui's 18.3.1 for react-dom + a stray global `~/node_modules/react@19`
    for the component) → `Cannot read properties of null (reading 'useState')`. Root install →
    single React. After a rebuild, **hard-refresh the browser** (Cmd+Shift+R) to drop cached app.js.
- **Gotchas:** (1) stale server.py procs squat the port (old code → wrong/blank page); if so,
  `pkill -f server.py` then restart. (2) Tool-launched servers get reaped by the harness — for
  the live demo, run `./venv/bin/python server.py` in YOUR OWN terminal so it persists.
- **Live-memory caveat:** `/chat` doesn't trigger extraction (end-of-conversation only), so the
  live "memories" panel shows only already-stored facts. To populate cross-session memory live,
  add an end-session trigger/endpoint (offered, not yet built).
- The JSX's standalone demo scenarios run with no server (hardcoded data, incl. GlobalEdge/45)
  for screenshots/recordings — independent of the live agent (real data = Cobalt/85).

## ENV NOTE (resolved 2026-06-28)
Project MOVED from `~/Documents/2026 Projects/novacrm` → **`~/Projects/novacrm`**. The old path
was under a cloud-synced folder that progressively OS-locked files ("Operation not permitted",
even sandbox-off; venv python fatal-errored). Moving to a plain local path fixed everything;
venv healthy, all files accessible. Keep the project OUT of cloud-synced folders.

## Server port
Default port is now **8001** (8000 had a stray non-ours process — answers /health but not /chat).
Port is configurable: `./venv/bin/python server.py [--port N]` or `PORT=N`. The demo JSX
`API_URL` is set to `http://localhost:8001` to match. **Live smoke PASSED on 8001** (2026-06-28):
/health ok; /chat (CUST-1003) → correct Enterprise/85-seats reply with get_account_info in the
trace, ~2.7s, clean/approved guardrails. To run for the demo: `./venv/bin/python server.py`.

## Then — Phase 7: cleanup + README + retrospective (final)
Claude Code: tidy code (docstrings/dead code), write `README.md` (setup, architecture, eval
results table from `outputs/eval-report.md`), finalize DECISIONS.md, draft the Project 4 handoff.
Human-owned deliverable: the **"with-framework (P1/ADK) vs without-framework (P3)" writeup** — the
key learning of this project. Gate: README complete, DECISIONS finalized, framework-comparison captured.

## Eval assets (final)
`baseline_phase{1,2,3,4,5}.{py,json}`, `golden_dataset.py`, `golden_responses.json` (cache),
`run_combined.py`, `combined_report.json`, `outputs/eval-report.md`. Re-judge cheaply:
`python eval/run_combined.py --use-cache`.

## Notes (carry forward)
- Curated eval assets so far: `eval/baseline_phase{1,2}.py`, `cross_session_scenarios.md`,
  `adversarial_cases.py` (injection/PII/topic), `output_failure_cases.py`. Reuse in the combined eval.
- GROQ_API_KEY needed for the Scout LLM-judge (only OPENROUTER keys are in .env so far).

## Notes
- OpenRouter balance is low; `OPENROUTER_API_KEY_FALLBACK` now auto-takes over on 402. LLM
  output capped at max_tokens=1024.

## Try it (once the key is set)
- Single query: `python -m novacrm_agent.runner --once "How much is the Pro plan?"`
- Account-aware: `python -m novacrm_agent.runner --customer CUST-1001`
- Traces land in `eval/logs/<session_id>.jsonl`.

## Blocked / open
- D2 open item: GLM-4.7-Flash multi-turn tool-call reliability on the support task
  shape is unvalidated — this is exactly what the Phase 1 gate measures.
- API keys: ensure `.env` has `OPENROUTER_API_KEY` (+ `GROQ_API_KEY` for eval) before
  Phase 1 runs that hit the network.
