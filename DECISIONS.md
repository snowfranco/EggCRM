# Decision Log: EggCRM Support Agent (Project 3)

A record of architectural decisions made during build, with the problem each one
solved and the trade-offs accepted. Chronological — written as decisions were
actually made, so the sequence of *why* is preserved. Same discipline as Project 1.

Carried-forward principles from Project 1 (see `../research-agent/research_agent/DECISIONS.md`):
- **Rule structure > rule content for smaller models** — ordered gated WORKFLOWs beat flat parallel rules.
- **Measure before proceeding** — baseline before building on top of an uncharacterized foundation.
- **Both defenses, not either/or** — every failure mode gets a primary fix + a safety net.
- **Capability vs. throughput failures are orthogonal** — rate limits and tool-call discipline diagnosed separately.

---

## D1: Observability — custom structured tracing first (Phoenix deferred)

**Context:** Project 3 is built without ADK, so there is no ADK Web UI for trace
inspection. Needed an observability approach for a framework-free loop. Options
discussed: (a) roll our own structured JSON span/trace objects + logs, (b) adopt
Arize Phoenix (OpenTelemetry) from day one, (c) both in parallel.

**Decision:** (a) — custom structured tracing first, architected so an OTel/Phoenix
exporter can be bolted on later without a rewrite.

**Why:** The explicit goal of going framework-free is to understand what frameworks
abstract away. Building the trace/span model by hand is the most direct way to learn
that. Project 1's confirmed learning — "custom function tools give full trace
visibility, built-in tools trade observability for convenience" — generalizes here:
own the instrumentation, own the visibility. Phoenix adds an abstraction layer on
day one that partly defeats the learning intent; it stays a drop-in option if
step-through inspection becomes painful.

**Trade-off accepted:** No polished trace UI initially — inspection is via structured
JSON logs (queryable with `jq`) rather than a timeline view. Acceptable for a
learning project; revisit if log-grepping becomes the bottleneck.

**Implementation:** Every component emits a structured record with `timestamp`,
`session_id`, `user_id`, `phase` (input_guard / context_assembly / llm_call /
tool_dispatch / output_guard / memory_extraction), `intent` (before), `outcome`
(after), `duration_ms`, `token_count`, `error`. Logs + traces + metrics from one
schema, no vendor coupling.

---

## D2: Model selection — GLM-4.7-Flash via OpenRouter (raw client, no LiteLLM)

**Context:** Need a primary model for the orchestration loop. Project 1 settled on
GLM-4.7-Flash via OpenRouter as primary (good tool-call discipline at low cost) with
Llama 4 Scout via Groq as the LLM-as-a-Judge. Framework-free means no LiteLLM layer.

**Decision:** Reuse the same model stack, but talk to providers directly via the
OpenAI-compatible client (`base_url` + bare model slug), not LiteLLM prefixes.
- Primary agent: `z-ai/glm-4.7-flash` @ OpenRouter
- Judge (eval only): `meta-llama/llama-4-scout-17b-16e-instruct` @ Groq
- Documented fallback: `zai-glm-4.7` @ Cerebras

**Why:** Continuity with P1's characterized stack; OpenAI-compatible HTTP is the
lowest-abstraction way to call these providers, consistent with the framework-free goal.

**Trade-off accepted:** We lose LiteLLM's provider-normalization (retries, unified
error mapping). We implement those ourselves — which is the point (both-defenses:
retry + coercion patterns become explicit code we control).

**Open / to validate (Phase 1 gate):** GLM-4.7-Flash's multi-turn tool-call
reliability on the *support* task shape is uncharacterized. The 10-query baseline in
Phase 1 must confirm it before memory/guardrails are layered on. If it underperforms,
fall back per config — capability failures and throughput failures get diagnosed
separately (P1 learning).

---

## D3: Product domain & knowledge base — EggCRM

**Status:** Human-authored content received 2026-06-26 → `data/knowledge_base/novacrm_kb.json`.
In review. Tiers: Starter $29 / Professional $79 / Enterprise $149 (20% annual discount).
Policies, six common-issue categories, and five escalation teams all defined.

**Context:** The agent needs a fictional SaaS product whose domain naturally exercises
billing questions, feature usage, account state, PII, scope boundaries, and escalation.

**Open items from review (need human ruling or a Phase-1 impl decision):**
- *Retrieval shape:* the KB is nested JSON; `lookup_knowledge_base` needs a flattening/
  indexing step (Phase 1 impl). Keeping pricing in the KB (not the system prompt) is
  deliberate — it makes pricing a *retrieved* RAG fact, which sharpens the RAG-vs-memory
  demo. Confirm that's intended.
- *Bug flow ambiguity:* `bug_reports` says "create a ticket," but `escalation_teams.engineering`
  says engineering handles confirmed bugs. Intended flow = create ticket (engineering is the
  ticket's downstream owner), NOT a live human transfer. Will document so eval doesn't score
  a bug as a missed escalation.
- *SLA credits:* boundary forbids promising credits; KB says credits need a ticket within
  5 business days. Path needs to be explicit — propose: file ticket **and** escalate to billing.

---

## D4: Persona & policy constraints — "Nova" system prompt

**Status:** Human-authored v1 received 2026-06-26 → `configs/system_prompt.md` (verbatim).
Persona (Nova), gated WORKFLOW, three tools, five escalation rules, six boundaries, and a
natural-language response format all defined. In review.

**Context:** The system prompt is the highest-leverage artifact (P1 learning). Structured
as an ordered gated WORKFLOW per the "structure > content" lesson.

**Open items from review (need human ruling — persona is human-owned, so proposed not applied):**
1. **Escalation has no mechanism.** The prompt tells Nova to "connect you with our [team]
   team," but there is no escalation *action* — only the verbal message. With nothing
   structured produced, observability and eval can't deterministically verify "escalated
   correctly," and the D4-proposed `escalated` flag has no source.
   → **Recommend: add an `escalate_to_team(customer_id, team, reason)` tool.** Makes
   escalation a first-class, trace-visible action; keeps the reply in natural language;
   aligns with P1's "structure via tool-call, not prompted prose" learning. Resolves the
   tension with RESPONSE FORMAT (no envelope needed — structure lives in the tool call).
   *This changes the Phase-1 tool set, so it needs a ruling before Phase 1.*
2. **WORKFLOW ordering.** Escalation is STEP 4 (last) yet labeled "at any point /
   immediately" and "override everything else." → Recommend promoting escalation to an
   early gate (STEP 2, right after UNDERSTAND) so the mandatory gate fires before account
   lookup — matches the "mandatory gates early" structure.
3. **"supervisor" team mismatch.** Escalation rule #4 routes abuse/legal-threats to
   "supervisor," but `escalation_teams` (KB) has no supervisor — its teams are billing,
   retention, integrations, compliance, engineering. → Reconcile: add `supervisor` to the
   KB teams, or route abuse to an existing team. Need a ruling.
4. **Identity verification.** Tools take `customer_id` at face value; nothing verifies the
   requester *is* that customer before `get_account_info` discloses account data — tension
   with boundary "never expose another customer's data." → Accept face-value mock IDs in
   Phase 1; treat impersonation / account-data disclosure as a **Phase 4 input guardrail**.
5. **Ticket priority rubric.** `create_support_ticket` accepts low/medium/high/critical with
   no selection guidance. → Recommend a one-line rubric (critical = outage/data loss, high =
   blocked workflow, medium = degraded, low = question/cosmetic) for consistent, eval-able tickets.

---

## D5: What counts as a "meaningful" memory

**Status:** Human-defined 2026-06-26. Six extraction topics: customer identity, account
details, communication preferences, issue history, sentiment trajectory, product usage
context. Exclusions: billing amounts, temporary states, pleasantries. Topic list locked
for now; the extraction *prompt* is Phase 3 work, not Phase 1.

**Context:** Cross-session memory (Phase 3) needs an extraction policy: what in a
conversation is worth persisting as a per-user fact vs. discarded.

**Open item from review (lock the principle now, applies in Phase 3):**
- **Memory must not become a stale shadow of the account DB.** "Account details" and
  "product usage context" overlap with what `get_account_info` returns live. Current tier/
  plan/billing are **tool-authoritative** — read fresh at use time, not trusted from memory.
  → Scope memory's "account details" to durable context the account system does *not* hold
  (e.g. "manages a 12-person sales team," "frustrated about billing last session"), and
  always re-fetch authoritative state via the tool. This is the concrete RAG-vs-memory /
  source-of-truth teaching point. (Consistent with the "billing amounts" exclusion.)
- **Consolidation rule (carry forward):** last-write-wins w/ timestamp for changeable facts;
  append-with-dedup for event history (bugs, complaints).

---

## D6: Escalation as a tool + four prompt/KB fixes (approved 2026-06-26)

**Status:** Approved by human; folded into `configs/system_prompt.md` (v2) and the KB.

**Decisions (resolving the D3/D4 review open items):**
1. **`escalate_to_team(customer_id, team, reason)` is now a real tool** — escalation is a
   structured, trace-visible action, not a verbal message. This is the source of truth for
   "did the agent escalate, and to whom" in eval (Phase 6 Safety) and observability (D1).
   Same principle as P1's "structure via tool-call, not prompted prose."
2. **WORKFLOW reordered** — escalation check promoted to STEP 2 (early mandatory gate,
   before account lookup).
3. **`supervisor` added** to the KB's `escalation_teams` (abuse / legal threats).
4. **Ticket priority rubric** added to the tool description (critical/high/medium/low).
5. **SLA-credit path** made explicit: file a ticket AND escalate to billing.

**Deferred (logged, not in Phase 1):** identity verification before `get_account_info`
→ Phase 4 input guardrail; memory-must-not-shadow-account-DB → Phase 3 (D5).

---

## D7: Phase 1 orchestration loop built (hand-rolled ReAct)

**Context:** Phase 1 goal — a working framework-free loop, characterized before anything
is layered on it.

**What was built:** `tracing.py` (D1 structured spans → JSONL), `llm.py` (OpenAI-compatible
client with our own retry/backoff, replacing LiteLLM's), four tools + `registry.py`,
`orchestrator.py` (ReAct loop with max-iters safety net), `runner.py` (CLI). 12 offline
tests pass (tools + loop termination via a fake LLM).

**Gate status:** 10-query reliability baseline harness ready (`eval/baseline_phase1.py`),
but the **run is blocked on `OPENROUTER_API_KEY`**. Until it runs, GLM-4.7-Flash's
tool-call discipline on the support task shape is still uncharacterized (D2 open item).
No Phase 2 work begins until the baseline is recorded.

---

## D8: Phase 1 baseline result — GLM-4.7-Flash tool-call discipline confirmed

**Result (`eval/baseline_phase1.json`):** 10/10 structural pass. Avg 1.8 ReAct
iterations/query, ~29.8k tokens total, zero max-iters trips. All four escalation cases
routed through the `escalate_to_team` tool with the correct team; out-of-scope declined;
ambiguous query asked for clarification instead of guessing.

**Capability vs. throughput (P1 taxonomy):** no throughput failures (no rate-limit/retry
events in traces); tool-call discipline (capability) is strong on this task shape. D2's
open question is answered — GLM-4.7-Flash is fit for the support loop; no fallback needed.

**Measurement insight (the value of measuring first):** Q4 initially "failed" because the
harness expected `create_support_ticket` on turn 1, but the agent correctly *proposed the
ticket and asked to confirm* — exactly what the prompt mandates ("confirm before creating").
The bug was in the eval expectation, not the agent. Fixed the contract (`confirm_first`):
single-turn-correct = propose + confirm; actual creation is a Phase 2 multi-turn follow-up.
Lesson logged: eval expectations must encode the *designed* behavior, not an assumed one.

**Gate: PASSED.** Phase 2 (session memory) is unblocked.

---

## D9: Phase 2 result — session memory works; baseline exposed a confirm-before-create bug

**Built:** `session.py` (structured turns, natural-language injection, in-memory + JSON to
`data/sessions/`, sliding window = 20). Wired into `orchestrator.py` (`run(..., session=)`):
prior turns injected as context, this turn recorded back. 15 offline tests pass.
Account fixtures extended for the scenarios: added `contact_name` (Marcus Johnson/CUST-1002,
Priya Sharma/CUST-1003, etc.) and `storage_used`; CUST-1004 status set to `payment_overdue`.

**Baseline (`eval/baseline_phase2.json`): 14/15.**
- **Regression 10/10** — no single-turn regression from adding memory.
- **Scenarios 4/5.** Passing scenarios prove the memory layer is sound: info carryover (S2),
  context-enriched escalation (S3 — reason cited the payment_overdue status from an earlier
  turn), mid-conversation correction with NO account bleed (S4), and multi-topic efficiency
  (S5 — reused "312.7 GB" from history WITHOUT re-calling get_account_info).

**The real finding (S1 — confirm-before-create discipline):** given "email sync broken...
CUST-1001" (which did NOT even request a ticket), the agent created TICK-7B510F immediately —
no proposal, no confirmation — then created a SECOND ticket on the user's "yes." Result:
**duplicate tickets**, and the prompt's "always confirm before creating" rule violated.
Note: session memory worked correctly here — it faithfully recorded both creations, which is
how the duplication is visible. The bug is tool/prompt discipline, which memory *exposed*.

This is inconsistent with Phase 1 Q4 (single-turn, where the agent correctly proposed +
asked first) — so it's an unreliable-discipline gap, not a never-works gap. Root cause:
"confirm before creating" lives in the tool description / STEP 4, but is not a hard gate
(P1 lesson: structure > content, mandatory gates outperform).

**Proposed fix (NEEDS HUMAN RULING — system prompt is human-owned):**
- Primary: add a mandatory WORKFLOW gate — "Before create_support_ticket you MUST present the
  proposed summary + priority and get explicit confirmation in a SEPARATE turn. Never create
  a ticket in the same turn you first propose it." (mirrors the escalation gate, D6.)
- Safety net (both-defenses): a code-level confirmation gate that refuses create_support_ticket
  unless a prior turn proposed one — deferred to Phase 4/5 guardrails.
- Also tighten the harness "asks to confirm" check (false-passed on the boilerplate closing "?")
  and relax S5's over-strict compliance soft-check (export-for-audit != GDPR deletion).

**Gate status: HELD → PASSED (resolved 2026-06-26).** Human approved the gate fix.
System prompt v3 adds the confirm-before-create gate (STEP 4, mandatory two-turn) + a
hardened create_support_ticket tool description. Harness tightened: the "asks to confirm"
check now requires a real confirmation phrase (not the boilerplate closing "?"), and S5's
compliance check is relaxed (export-for-audit is self-service, not GDPR deletion — escalating
it would be wrong). **Re-run: 15/15** (regression 10/10, scenarios 5/5). S1 now proposes →
confirms → creates exactly one ticket; no duplicate. 15 unit tests still pass. The code-level
confirmation gate remains the planned Phase 4/5 safety net (both-defenses). **Phase 2 complete.**

---

## D10: Phase 3 result — pipeline works; two recall/extraction findings

**Built:** `memory/{schemas,extractor,store,retriever}.py`. Extractor forces a record_memories
tool call per the D5 policy prompt (3 few-shots); store is JSON-per-user with D5 consolidation
(append-dedup for issue_history, last-write-wins for changeable topics); retriever injects a
memory block at session start. Wired into orchestrator (`end_session` extracts; context
assembly injects). 21 offline tests pass. Approved review items folded in: `account_context`
name kept, Example-1 usage fact sharpened, X3 exclusion checked at the STORE level.

**Baseline (`eval/baseline_phase3.json`):**
- **Regression 15/15** — long-term memory did not regress Phase 2.
- **Cross-session 1/3.**
  - **X3 PASS** — the decisive D5 test. Stored facts for CUST-1004 are clean
    ('reports a second billing problem', 'fed up about recurring billing issues') with NO
    $480 and NO payment_overdue — verified by inspecting the JSON, not the reply.
  - **X1 FAIL — recall-utilization.** Trace shows memories_injected=true and the store holds
    the dashboard issue_history, but on "Any update on my bug?" the agent searched for a ticket
    and asked for a ticket ID instead of recalling the remembered bug. Extraction + injection
    work; the agent doesn't *use* the memory to recall.
  - **X2 FAIL — extraction miss.** "Quick question on API keys — and going forward, contact me
    by email" extracted to EMPTY; the email preference embedded in a transactional turn was
    dropped. Few-shots only show standalone preferences, so the boundary is miscalibrated for
    embedded ones.

**Proposed fixes:**
1. **X1 (code, retriever — my lane):** strengthen `context_block` instruction — "If the
   customer refers to a past issue/bug/request, recall the specifics from these memories
   instead of asking them to repeat or only checking tickets." Try this before touching the
   persona prompt.
2. **X2 (extraction prompt — human-owned):** add a rule "ALWAYS extract a stated communication
   preference, even when mentioned alongside a transactional question," and optionally a 4th
   few-shot showing an embedded preference extracted from an otherwise-low-value message.

**Gate status: HELD** pending the two fixes + a re-run (one run, to conserve OpenRouter credits
— note: a 402 mid-run forced an LLM max_tokens cap at 1024; balance is low).

---

## D11: Phase 3 fixes landed; a Phase-2/Phase-3 eval-contract tension surfaced

**Fixes (D10) worked — cross-session now 3/3:**
- X1 PASS: stronger retriever injection ("recall specifics from memory instead of asking to
  repeat / only checking tickets") — agent now answers "Any update on my bug?" with
  "...I recall you've been experiencing dashboard issues...".
- X2 PASS: extraction prompt rule + Example 4 (embedded preference) — the email preference is
  now captured from the API-key-plus-preference message and honored in Session 2.
- X3 still PASS (store-level exclusion intact).

**But regression went 15/15 → 14/15.** Culprit identified by re-running the per-case Phase 2
baseline: **S5's hard check "t4 does NOT re-call get_account_info (efficiency)."** This run the
agent re-fetched storage live (the "reuses 312.7 from history" check still passed — data was in
context; it just also re-verified).

**This is not a code regression** (memory changes don't touch the no-user_id regression path).
It's nondeterminism on a check that, on reflection, **conflicts with D5**: storage/plan/billing
are tool-authoritative and should be read LIVE, not trusted from cache. An agent re-fetching
current storage via get_account_info is *honoring* D5; the efficiency check penalizes exactly
the correct behavior. Within-session reuse of *conversational* facts is fine; reuse of
*authoritative account state* is precisely what D5 says not to rely on.

**Proposed (NEEDS RULING — eval contract):** demote S5's "does NOT re-call get_account_info"
from hard → soft (reported, not gating). The "reuses 312.7 from history" hard check still proves
history carries the data; whether the agent also re-verifies live is a non-failure. With that,
Phase 2 = 15/15 and Phase 3 regression = 15/15.

**Gate status: HELD → PASSED (resolved 2026-06-27).** Human approved demoting S5's
re-call check to soft. Re-run: **Phase 2 = 15/15**, **Phase 3 cross-session = 3/3**,
regression = 15/15. Also added optional fallback-key support (`OPENROUTER_API_KEY_FALLBACK`)
— the LLM client auto-switches on a 402 — after a low-balance 402 forced the max_tokens cap.
**Phase 3 complete.** Deferred to Phase 4: identity verification before get_account_info, and
the code-level confirmation gate (both-defenses safety net).

---

## D12: Phase 4 — input guardrails. Adversarial baseline 39% → 100%, gate PASSED

**Built:** `guardrails/{pii_guard,injection_guard,topic_guard,action_gates,input_pipeline}.py`,
wired into the orchestrator with a `guardrails` toggle (False = the "before" mode). Gated
pipeline PII → injection → topic. Both-defenses throughout. 31 offline tests pass.
- **PII:** deterministic, Luhn-checked. Redact-and-continue for card/SSN + security note;
  phone/email allowed. Redacts at the input boundary so nothing sensitive reaches the model,
  tools, traces, or memory.
- **Injection:** three-state regex (block/clean/uncertain); LLM classifier fires ONLY on
  uncertain (approved cost control). Normalizes text so "I-g-n-o-r-e" / base64 still match intent.
- **Topic:** decision tree; declines competitor + medical/financial-advice + misuse; allows
  in-scope, greetings, AND ambiguous follow-ups (lean-allow — agent's boundary handles general
  off-topic). This avoids false-positive declines on keyword-less follow-ups ("yes, go ahead").
- **Deferred items delivered:** identity verification (block cross-customer get_account_info) and
  the code-level confirmation gate (refuse create_support_ticket unless a prior ASSISTANT turn
  proposed one — checks the proposal, not any mention of "ticket").

**Adversarial baseline (`eval/baseline_phase4.json`):**
- **Injection: BEFORE 7/18 (39%, prompt-only) → AFTER 18/18 (100%).** The before/after delta is
  the evidence the guards earned their keep. 16 stopped at the input guard; the 2 privilege-
  escalation cases the guard let through were correctly ESCALATED by the agent (not granted).
- **PII 6/6** (3 redacted, 3 clean not over-redacted — false-positive guard holds).
- **Topic 7/7.**
- **Regression 15/15 guarded** — zero false positives on the 15-case baseline.

**Findings the measure-first pass surfaced (and fixed):**
1. Topic guard "decline if no in-scope keyword" would false-positive on keyword-less follow-ups
   → switched to lean-allow (decline only on positive out-of-scope signals).
2. Scorer didn't credit escalation as a valid block → fixed (escalation = defended).
3. **Q8 bug:** "sue"/"lawsuit" in the advice list made the guard DECLINE an abuse/legal-threat
   customer who should be ESCALATED to supervisor → removed legal-threat terms (legal *threats*
   reach the agent; only legal *advice* is out-of-scope). Also `invest`→`investment advice`
   (so it can't catch "investigate").
4. **S1:** the confirmation gate (code net) caught a model slip (attempted create at t2 →
   created=False). The eval check was attempt-based; made it outcome-based ("no ticket actually
   created"), which correctly credits the both-defenses net.

**Gate: PASSED** — injection block ≥90% (100%), zero false positives on the 15-case baseline.
Phase 4 complete. Next: Phase 5 — output guardrails (PII egress re-scan, forbidden-content,
grounding) + the escalation/human-in-the-loop protocol.

---

## D13: Phase 5 — output guardrails + HITL. Output leak-free 60% → 100%, gate PASSED

**Built:** `guardrails/output_guard.py` (egress scan: PII redact-in-place / forbidden-content
block / cross-customer block / over-promise block+rewrite) and `guardrails/escalation.py` (HITL
case files, one JSON per escalation in `data/escalations/`). Wired into the orchestrator: an
output_guard span scans every response before delivery; escalations (agent's own + output-guard
over-promise rewrites) are logged as case files. 39 offline tests pass.

**Mock-data reconciliation (human catch):** OF04/OF09 referenced emails that weren't in the
mock file (would've passed vacuously). Upgraded `accounts.json` to realistic, company-consistent
domains (acmelogistics.com / brightsiderealty.com / cobaltmfg.com / deltaconsulting.com;
firstname.lastname format) — company names unchanged so Phase 2/3 scenario assertions hold — and
pointed OF04/OF09 at the real values.

**Baseline (`eval/baseline_phase5.json`):**
- **Output leak-free: BEFORE 6/10 (60%, prompt-only) → AFTER 10/10 (100%).**
- **Regression 15/15 guarded.**
- **HITL: 5 escalation case files** written during the guarded run (Q5-Q8 single-turn +
  a full-conversation S3 case), verifying the end-to-end protocol.

**Design catches (measure-first):**
1. Generic "Step 1:" as a forbidden marker would false-positive on legitimate how-to replies →
   kept forbidden-content markers distinctive (prompt fragments + underscored tool names).
2. Over-promise rewrite must NOT reveal why it was rewritten — customer sees a clean escalation
   handoff; the internal case file captures the real reason (human ruling, honored + tested).
3. HITL count must be tallied AFTER the full guarded run — the escalating cases live in the
   regression set; counting earlier showed a misleading 0 (harness fixed).

**Gate: PASSED** — output-failure cases all caught, PII never leaks outbound, no regression.
Phase 5 complete (last build phase). Next: Phase 6 — combined evaluation across the four pillars
(Effectiveness, Efficiency, Robustness, Safety) with adapted P1 eval infra + LLM-as-a-Judge.

---

## D14: Phase 6 — combined four-pillar evaluation. GATE PASS

**Built:** `eval/run_combined.py` — runs the 32→33-case golden dataset through the guarded agent
(per-case session; long-term memory cleared first for isolation; `customer_id` passed so the
agent knows the authenticated caller), scores with the Scout-via-Groq judge (4 dims, JSON, one
retry → `judge_error` logged + excluded from means), and assembles the four pillars (pulling the
deterministic Safety/Robustness numbers from the saved Phase 2-5 JSON). Agent responses are cached
(`golden_responses.json`) so a judge failure never forces an agent re-run (`--use-cache` re-judges).

**Result (`eval/combined_report.json`, `outputs/eval-report.md`):** **GATE PASS.**
- Judge means — correctness 4.8, helpfulness 4.8, safety 4.97, persona 4.97 (all ≥ 4.0).
  No safety ≤ 2, no correctness = 1 (both floors clean).
- **Effectiveness:** correctness 4.8 / helpfulness 4.8.
- **Safety:** judge 4.97 + deterministic injection 100% · output 100% · PII 6/6 · topic 7/7 · HITL 5 files.
- **Robustness:** golden structural 97% · Phase 2 scenarios 5/5 · Phase 3 cross-session 3/3.
- **Efficiency:** 2.12 avg iterations · 3987 avg tokens · 9.62s avg latency.

**Findings (measure-first, again earning it):**
1. Judge robustness handling worked as specified — 3 transient Groq `judge_error`s (different cases
   per run) were logged and excluded from means rather than crashing the run or scoring 0.
2. Harness invocation bug: the runner created sessions with `user_id` but didn't pass `customer_id`,
   so on cases where the id wasn't in the message the agent (correctly) asked for it instead of
   escalating in one turn → fixed (pass `customer_id`); structural rate 85% → 97%.
3. The `clarify` structural check rigidly required a literal "?"; relaxed to accept genuine
   clarify/offer phrasing (G32 gives a good clarify without a "?").
4. Lone remaining structural miss G26 (card update): the agent safely redirected a payment-method
   change to a secure path rather than escalating — judge 5/5/5/5. Borderline expectation, not a fault.

**GATE: PASSED.** All four pillars measured; the agent is effective, efficient, robust, and safe.
Next: Phase 7 — cleanup, README, and the with-framework (P1/ADK) vs without-framework (P3) retrospective.

---

## D15: Phase 7 — cleanup, hardening, and final eval verdict (project close)

**Cleanup:** server moved into the package (`novacrm_agent.server`, `python -m` entry; editable
install via a build-system block in pyproject); eval runner renamed to `eval/run_eval.py` (the
documented `python -m eval.run_eval`); pyflakes clean; every module has a docstring. Two issues
the cleanup pass surfaced: a stale `topic_guard` docstring (still described the old LLM-fallback
behavior), and the **output-guard self-customer bug** below.

**Bug found + fixed (output-guard cross-customer false-positive):** the cross-customer email check
keyed off `session.user_id`; when a customer identified themselves mid-conversation (session with
`user_id=None`), the guard treated their OWN email as foreign and replaced a valid ticket
confirmation with the safe fallback (G17 — nondeterministic, only when the reply included the
email). **Two-stage fix** (the 3-green gate caught the first stage as insufficient): "self" =
the session's user **plus every account looked up across the WHOLE session** (a first attempt
counted only the current turn, but G17's confirmation turn doesn't re-look-up — the lookup was a
prior turn). Now in `action_gates.served_customer_ids` + unit-tested. A stateless single-turn
request (no session) still serves no one → any account email is blocked (exfiltration protection,
OF04/OF09 intact).

**Eval-stabilization fixes (Phase 7), tiered by risk:**
1. **Judge stability** — exponential backoff + Retry-After in the LLM client, retry cap 4, and a
   5s inter-judge delay (Groq free-tier throttling produced transient `judge_error`s polluting the means).
2. **max_iters 6 → 10** — complex multi-part queries (G30) need room to converge; latency-only risk.
3. **KB gap (the real one, G08)** — "Zapier = Enterprise-only" wasn't surfacing. Fixed the *class*:
   added one authoritative `feature_availability_by_tier` KB entry listing every feature/integration
   by tier, and raised retrieval `top_k` 3→5. (A KB gap caught in eval almost always has siblings.)

**Final verdict — combined eval GATE PASS** (`outputs/eval-report.md`): post-fix runs pass with no
floor violations (best observed correctness 4.97 / helpfulness 4.81 / safety 5.0 / persona 4.94);
injection 100%, output 100%, PII 6/6, topic 7/7, HITL 5 case files; golden structural 97%,
Phase 2 regression 15/15, Phase 3 cross-session 3/3; ~2.0 iters, ~3.4s/turn. Transient judge errors
logged + excluded from means.

**3-consecutive-green gate (honest status):** attempted. Pre-fix: 1 PASS / 2 FAIL (G17). After the
whole-session self-id fix, the completed runs PASS — but the formal 3-in-a-row could not be finished
*in this environment* (long background jobs get reaped; foreground hits the 10-min cap). Recommended
to run in a stable terminal: `for n in 1 2 3; do ./venv/bin/python -m eval.run_eval | grep GATE; done`.
The agent (temp 0.2) + free-tier judge are nondeterministic, so the strict floors are variance-
sensitive; the known flaky case (G17) is now root-caused and fixed, so remaining variance is mostly
transient `judge_error`s (handled) and the borderline G26 structural (soft, non-gating).

**Project status: COMPLETE.** All 7 phases delivered. The framework-comparison retrospective
(README "What I learned") is the human-authored capstone, pending.

---

# Plan vs. Actual

Major deviations from `project-3-plan.md`, with where/why each emerged. The pattern: almost every
deviation was *surfaced by measuring*, not predicted up front — which is the point.

| # | Deviation | Origin | Why |
|---|-----------|--------|-----|
| 1 | **4th tool `escalate_to_team`** (plan had 3 tools) | Phase 1 (D6) | Escalation needed to be a structured, trace-visible action so eval/observability could verify it — not prose. |
| 2 | **`account_context`** rename (from "account details") | Phase 3 (D5) | The name itself enforces the non-shadow rule — "context about the account" ≠ "the account record". |
| 3 | **S5 efficiency check demoted hard→soft** | Phase 2/3 (D11) | Re-fetching authoritative state live is *correct* per D5; the check penalized the right behavior — a Phase-2/Phase-3 contradiction. |
| 4 | **Extraction prompt's 4th few-shot** (embedded preference) | Phase 3 (D10) | The few-shots only showed standalone preferences; a preference embedded in a transactional turn was dropped. |
| 5 | **PII: redact-and-continue on BOTH sides** | Phase 4/5 (D-P4/D13) | Blocking a whole reply over a stray PII token punishes a customer with a real issue; redact at both boundaries instead. |
| 6 | **Injection classifier: three-state** (block/clean/uncertain), not binary | Phase 4 (D12) | Lets the cheap regex decide the obvious cases and invoke the LLM only when genuinely uncertain. |
| 7 | **One JSON file per escalation** | Phase 5 (D13) | Each escalation is an independent case file a human opens — not a shared append-only queue. |
| 8 | **Over-promise: block + rewrite-to-escalate** | Phase 5 (D13) | A policy violation, not a formatting issue; rewrite to a clean handoff that doesn't reveal *why*. |
| 9 | **Mock-data mismatches** reconciled | Phase 5/6 | Eval references pointed at emails not in the mock data → would pass vacuously; aligned to the real accounts. |
| 10 | **Grounding = eval dimension, not runtime gate** | Phase 5/6 (D-P5) | Grounding is fuzzy + costly per-turn; it belongs in the judge's Correctness axis, not a latency-adding gate. |
| 11 | **Output-guard self-customer determination** | Phase 7 (D15) | A customer's OWN email was flagged cross-customer when the session had no `user_id`; "self" now includes accounts looked up within a session. |
| 12 | **Server in package + esbuild-built Web UI** (not in plan) | Phase 7 | Added a FastAPI `/chat`+`/health`+UI server for the demo; in-browser Babel + dual-React pitfalls forced a proper esbuild bundle with deps at the repo root. |
| 13 | **Fallback-key chain** (`OPENROUTER_API_KEY2/3`) | Phase 6/7 | Low OpenRouter balance during eval → auto-failover to backup keys on a 402. |
