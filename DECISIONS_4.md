# Decision Log: EggCRM Project 4 — Agentic RAG + Multi-Agent (Coordinator)

A record of the architectural decisions for **Project 4**, kept separate from Project 3's
`DECISIONS.md`. Same discipline as P1/P3: each decision states the problem it solved and the
trade-off accepted, written as decisions were actually made.

Project 4 extends the same codebase: it replaces the hardcoded JSON KB (and its keyword
`lookup_knowledge_base`) with a real vector-retrieval system, and turns Nova from a single
agent into a **coordinator** that delegates documentation questions to a standalone **RAG
agent**. Decision labels use the `P4-Dn` names from `localdoc/project-4-handoff.md` so
cross-references stay unambiguous.

Carried-forward principles (P1 → P3 → P4):
- **Rule structure > rule content for smaller models** — ordered gated WORKFLOWs beat flat lists.
- **Measure before proceeding** — baseline before building on an uncharacterized foundation.
- **Both defenses, not either/or** — every failure mode gets a primary fix + a safety net.
- **Evidence over assumptions** — tune chunking/embeddings *after* measuring retrieval, not before.
- **Non-shadow rule** — no knowledge source silently overrides another.

All six Phase-0 architecture decisions were **locked at the handoff's recommended defaults**
(human sign-off, 2026-06-30), plus a seventh on the framework question the handoff left open.

---

## P4-D1: Vector store — ChromaDB (embedded, persistent)
Chosen over FAISS (lower-level, no persistence/metadata out of the box) and Pinecone/Weaviate
(cloud, vendor dependency). ChromaDB is pip-installable, persists to local disk, and carries
per-chunk metadata natively (needed for P4-D4's metadata filtering — the "both defenses" of
retrieval: vector similarity **and** metadata filter). The store is wrapped behind one module
so swapping to a production store later is a single-file change. **Trade-off accepted:** not the
fastest option, but the corpus is ~20 docs — irrelevant at this scale.

## P4-D2: Embedding model — local `sentence-transformers/all-MiniLM-L6-v2`
Zero cost, no API dependency, fast on CPU, 384-dim. Chosen over OpenAI/Google hosted embeddings
to keep the RAG path offline and free for a capstone. **Revisit gate:** switch to a
provider-hosted embedding model only if Phase 3 retrieval quality (recall/precision) is poor —
evidence over assumption. This is the first non-OpenAI-client dependency in the project, but it
runs locally, not as a provider call, so it doesn't touch the model-provider wiring.

## P4-D3: Document corpus — expand EggCRM's own world (human-owned, Claude-drafted)
Chosen over using a real OSS product's docs or fully synthetic docs, because controlling the
content is what lets eval cases have **known-correct answers** (the discipline that caught P1's
ticket-confirmation spec error and P3's KB holes). 15–20 doc pages across three `doc_type`s:
feature guides, API reference, troubleshooting. **Hard constraint:** the corpus is a strict
*superset* of the existing `novacrm_kb.json` facts (tiers/pricing, the exact tier-availability
matrix, billing/refund/cancellation/SLA policies, the 9–11 AM ET dashboard known-issue, the four
mock accounts) with **zero contradictions** — otherwise grounding eval scores against a corpus
that disagrees with the account/ticketing tools, re-creating P3's mock-data mismatch bug. Claude
Code drafts; human signs off before ingest (corpus content is human-owned per CLAUDE.md).

## P4-D4: Chunking — semantic by heading + per-chunk metadata
Docs are authored with explicit `##` section headings; the chunker splits on them so each chunk
is one coherent section. Every chunk carries metadata: `doc_title`, `section`, `doc_type`. This
enables the **second defense** alongside vector similarity — metadata filtering (e.g. restrict to
`doc_type=api_reference` for an API question). Fixed-size/recursive splitting deferred; if Phase 3
shows sections too large for clean retrieval, add intra-section sub-splitting then (measured, not
pre-emptive).

## P4-D5: Agent communication — full agent delegation (not a function call)
Nova does **not** call a `search_documentation()` function that hides the RAG pipeline. Instead
the RAG agent is a real agent with its own system prompt, retrieval tools, and reasoning loop;
Nova (coordinator) routes by intent, delegates the question, waits, and incorporates the
synthesized answer. Chosen for genuine exercise of the **Coordinator pattern** — the multi-agent
learning is the point. **Trade-off accepted:** more latency and more moving parts than a function
call; delegation latency becomes a Phase 4 metric.

## P4-D6: Grounding — both runtime gate and eval dimension
The grounding check deferred in P3 (Plan-vs-Actual #10) becomes first-class now that there's a
retrieval system to ground against. **(b)** eval-time grounding score is the primary metric (a
judge dimension: "is the answer supported by the retrieved chunks?"); **(a)** an optional runtime
grounding gate for high-stakes answers. "Both defenses" applied to a quality axis: measure it
everywhere, gate it where it matters. Non-shadow rule extends: retrieved docs are authoritative
for product knowledge, memory for user context, account tools for live account state — no source
silently overrides another.

## P4-D7: Framework — ADK for the multi-agent layer only; RAG pipeline hand-built
The handoff left this open (stay raw / ADK-for-multi-agent / ADK-everywhere). **Decision: option
(b).** P3 already proved the value of hand-rolling orchestration to understand what frameworks
abstract; P4 now uses ADK *deliberately* for the coordinator/delegation layer, while the RAG
pipeline (chunking, embedding, vector store, retrieval) stays hand-built. This **overrides P3's
"framework-free, no ADK" ground rule** — intentionally, and scoped to the multi-agent layer.
**Noted consequence:** ADK's non-Gemini model support routes through `google.adk.models.LiteLlm`,
so adopting ADK reintroduces LiteLLM as ADK's *internal model adapter* (P3 avoided LiteLLM at the
orchestration layer). We accept this: LiteLlm here is ADK plumbing to keep using GLM-4.7-Flash via
OpenRouter, not our orchestration loop. ADK enters at **Phase 2** (coordinator); Phase 0 (corpus +
pipeline) and Phase 1 (standalone RAG agent) need no framework decision to proceed. If ADK's
provider wiring fights the existing OpenRouter/Groq setup at Phase 2, that's a measured finding to
surface then, not a blocker now.

---

## Phase 1 execution notes (2026-06-30) — standalone RAG agent + baseline

**P4-P1a: Baseline model-of-record = Groq Llama-4-Scout (STOPGAP), not the primary.** The
official Phase-1 gate model is GLM-4.7-Flash via OpenRouter, but OpenRouter hit a hard 402
(out of credits) and `.env` carried no fallback key, so the primary couldn't run. Rather than
block Phase 1, the human accepted the Scout run as the baseline-of-record, explicitly labeled
STOPGAP in `rag_baseline.json`. **Follow-up owed:** re-run `python eval/rag_baseline.py`
(default `--provider openrouter`) on the primary once credits/fallback return, to confirm the
gate holds on the model Phase 2 actually ships on. Consistent with "measure before proceeding" —
the gate is characterized; the caveat is which model characterized it.
**Update (2026-06-30):** two more OpenRouter keys (`_KEY4/_KEY5`) were added and wired into
`config.OPENROUTER_FALLBACK_KEYS`, but the re-run still 402s — probing each key at
`max_tokens=1024` shows all five share ONE `user_id`: a single drained account, so more keys ≠
more credit. The follow-up is therefore blocked on **crediting the account**, not on keys. The
same blocker gates Phase 2 GLM runtime testing (ADK's LiteLlm hits the same account); Groq Scout
remains the working stopgap until then.

**P4-P1b: Two eval cases corrected (over-strict scorer / mis-premised trap), human-signed-off.**
The first Scout run failed the gate on two cases that were *eval bugs, not agent bugs* — the same
"the eval was wrong, not the agent" pattern that recurs across P1/P3 (see handoff track record).
Corrections (curation is human-owned; drafted by Claude Code, signed off "adjust both"):
- **R5 (API auth):** scorer required the literal bigram "api key"; a correct grounded answer that
  says "pass a **bearer token** in the **Authorization** header" legitimately omits it. Relaxed to
  `expect_all=["bearer","authorization"]` — the load-bearing mechanism + header, not a phrasing.
- **R10 (not-in-docs honesty trap):** the old "native iOS app?" question was answerable by
  *grounded inference* — the corpus states EggCRM is "browser-based — nothing to install", so
  "no native app" is defensible, not a fabrication. That defeats the trap's purpose. Replaced with
  "Does EggCRM have a dark mode?" — zero adjacent doc facts to infer from, so the only correct
  behavior is an honest decline. Also widened `DECLINE_MARKERS` to recognize "does not mention …
  in the documentation" as a valid decline (the model names the gap by what the docs omit).

- **R8 (refund policy), tightened next session:** the scorer required the doc-title token
  "billing", which Scout drops on wording variance even when the refund policy is correct →
  replaced with `expect_all=["14 days","pro-rated"]`, the two load-bearing facts (both verbatim in
  `16-billing-and-plan-changes.md`). Same over-strict-token class as R5.

**P4-P1c: Result.** After the R8 fix: recall 100% (9/9 gold), correctness **100% (10/10)**, R10
declines → **GATE PASS** on the Scout stopgap. 6 offline RAGAgent loop tests added
(`tests/test_rag_agent.py`); 60 tests pass, pyflakes clean.

---

## Phase 2 foundation notes (2026-06-30) — ADK coordinator (P4-D7 realized)

This is the first time the project touches a framework. Two integration decisions were taken to
land ADK deliberately and narrowly (both drafted by Claude Code, human-signed-off this session).

**P4-P2a: ADK scoped to routing/delegation ONLY; P3 guardrails/memory stay hand-built and *wrap*
the coordinator.** Options weighed: (a) wrap ADK in hand-built pre/post [chosen]; (b) port
guardrails into ADK before_model/after_agent callbacks; (c) full ADK rebuild. Chose (a): input
screen (injection/PII/topic) runs before the ADK `LlmAgent`, output guard (grounding/PII/
over-promise) + `end_session` memory extraction run after, all reusing the *unchanged* P3 code.
Rationale: lowest regression risk against a signed-off suite, and it honors P4-D7's "coordinator
layer only" literally — ADK owns routing + tool dispatch + delegation, nothing else. The two P3
action gates (confirm-before-create, cross-customer identity) moved into the ADK `FunctionTool`
wrappers, reading a per-run context dict via closures (runs are synchronous → no races).

**P4-P2b: the RAG specialist stays the hand-built Phase-1 `RAGAgent`, exposed via an ADK
`AgentTool` (not re-expressed as an ADK-native `LlmAgent`).** Rationale: re-expressing it would
invalidate the Phase-1 baseline, which measured that exact loop, and would fight P4-D7's "RAG
pipeline hand-built". A thin `RagSpecialistAgent(BaseAgent)` adapter bridges it. **Measured ADK
finding (P4-D7 caveat realized):** `AgentTool` runs the wrapped agent in a *separate inner Runner*,
so the specialist's `Event.custom_metadata` never reaches the parent event stream — retrieval
provenance (needed for the P4-D6 grounding check) is lost across the boundary. Fix: the adapter
writes provenance to a caller-owned `sink` dict the coordinator reads after the turn.

**P4-P2c: dependencies.** `google-adk` 2.3.0 + `litellm` 1.83.14, pinned explicitly rather than via
`google-adk[extensions]` (that extra also drags in langgraph/llama-index/anthropic/docker/k8s and
bumped `openai`→2.24.0). All 70 tests survive the upgrade. LiteLlm→provider verified live on Groq;
GLM-via-OpenRouter is the identical pattern, blocked only on the drained-account credits (P4-P1a).

**Status:** coordinator built (`agents/coordinator.py`, `agents/rag_specialist.py`) + 10 offline
tests (`tests/test_coordinator.py`); smoke-tested on Groq (doc→`nova_docs`, account→`get_account_info`,
both correct).

**P4-P2d: GLM unblocked (fresh funded account) + centralized active-key wiring.** `OPENROUTER_API_KEY6`
is a NEW funded account (the KEY…KEY5 chain is one drained account, P4-P1a). `config` now derives
`OPENROUTER_ACTIVE_KEY` = funded-key-first; both the hand-built `LLMClient` default and ADK's
`build_litellm` use it. This matters specifically for ADK: **LiteLlm has no 402 key-rotation of its
own**, so it MUST be pointed at a funded key directly — passing the drained primary (as the first
cut did) would fail every coordinator call. GLM-4.7-Flash verified live end-to-end through ADK/LiteLlm.

**P4-P2e: Phase-2 routing baseline — GATE PASS on GLM-4.7-Flash (the ship model, not Scout).**
`eval/routing_baseline.py` — 10 cases (RC1–RC10) deliberately on the routing BOUNDARIES (account+RAG
overlap, known-issue-vs-ticket, refund-is-escalation, multi-intent, not-in-docs decline, pure
escalation, cross-customer gate), scored deterministically (routing + answer, no judge). **Routing
90% · answer 90% · overall 90% (9/10) → PASS** (gate: routing ≥80% ∧ overall ≥70%). This doubles as
the first OFFICIAL GLM pass of the RAG agent (Phase-1 was Scout-only) — six cases delegated to
`nova_docs` and grounded correctly; **no Scout-vs-GLM tool-call divergence** through LiteLlm (the
P4-D7 risk the user flagged did not materialize).
- **RC5 finding (measure-first working, a real gap not an eval bug):** a refund request routes to
  account-lookup + a proposed generic **support ticket**, instead of consulting the refund policy and
  **escalating to billing** (the docs are explicit: a support agent cannot approve refunds). This is a
  router-prompt shortcoming (prompt content human-owned, D4) — flagged for sign-off, left as-is since
  the gate passes. It's exactly the boundary fragility the case set out to expose.

**P4-P2f: P3 regression harness adapted to the coordinator (non-destructively).** `run_eval.py
--coordinator` drives `NovaCoordinator` over the same 33 golden cases + Groq judge, writing SEPARATE
artifacts (`*_coord.json`, `eval-report-coord.md`) so the frozen P3 single-agent baseline is intact —
an apples-to-apples multi-agent-vs-single-agent regression. `structural()` transfers unchanged
(escalate/ticket tool names preserved; product answers just route via `nova_docs` now).
`CoordinatorResult` gained `iterations`/`total_tokens` (from ADK event usage) for the efficiency
pillar.

**P4-P2g: the regression CAUGHT a real escalation-routing regression (measure-first earned its
keep) — found, fixed, re-run GREEN.** First coordinator regression on GLM FAILED the gate. The
judge means were already on par with P3 (corr 4.83 / help 4.69 / safe 5.0 / persona 4.97) — the
failure was structural + one correctness floor, ALL on escalation: refund recited policy instead of
escalating (G21); cancel escalated to *billing* not retention (G22); GDPR proposed a ticket not
compliance (G23); "sue" went to *compliance* not supervisor (G24); update-billing didn't escalate
(G26); and G15 correctness=1 (claimed it couldn't look up tickets, though `get_account_info` returns
`open_tickets`). **Root cause:** porting Nova into the ADK router prompt had collapsed P3's detailed
ESCALATION RULES (scenario→team) into one vague line, so the small model guessed teams. **Fix
(prompt content, D4, human-signed-off):** restored P3's protocol into `COORDINATOR_INSTRUCTION` —
escalation as a mandatory FIRST gate + the explicit scenario→team mapping + an open-tickets note on
the account tool. **Re-run: GATE PASS** — corr 4.83 / help 4.67 / safe 4.97 / persona 4.9 (matches
P3's 4.83/4.66/5.0/4.86), golden structural 97% (the one miss, G33, is a scorer false-negative — a
judge-confirmed 5/5/5/5 cross-customer *refusal* whose "I can only view your own account" phrasing
wasn't in `DECLINE_MARKERS`; markers widened → behavioral structural is 33/33). Transient Groq
judge_errors recur on ~3 random cases per run (rate limit) — excluded from means, never scored 0.

**P4-P2h: routing baseline 10/10 on GLM after the escalation fix.** RC5 (refund) now escalates to
billing (it had been the one routing-baseline miss, same root cause as G21). Re-run: routing 100% /
answer 100% / overall 100%. **Honest caveat (model variance, not a bug):** on one interim run RC3
("what integrations does *my plan* support?") answered from docs WITHOUT first looking up the
customer's tier — a boundary case that flips run-to-run. The answer was still substantively correct;
it's an intermittent grounding-discipline gap at the account+RAG seam, worth watching in Phase 3.

**Phase 2 status: COMPLETE** — both gates PASS on the ship model (GLM-4.7-Flash): routing 10/10,
golden regression on par with the P3 single-agent baseline. The multi-agent coordinator matches the
single agent on quality/safety while adding genuine ADK delegation. 70 offline tests pass.

---

## P4-D8: Phase 3 rescoped — "grounding & routing discipline", NOT retrieval tuning (2026-06-30)
The handoff sketched Phase 3 as **retrieval optimization** (chunk-size tuning, overlap, re-ranking,
query expansion). **Decision (human, 2026-06-30): drop retrieval tuning — there is no evidence for
it.** The Phase-1 baseline is 100% recall AND 100% correctness on GLM-4.7-Flash; tuning parameters
that already work would violate the project's own "evidence over assumptions / measure before
proceeding" principle (tune retrieval *after* measuring it shows a problem, not before). Phase 3 is
reframed to the two gaps the data actually surfaced:
  1. **The P4-D6 grounding check** — deferred since P3, now due: an eval-time grounding dimension
     ("is the answer supported by the retrieved `rag_sources`?") plus the optional runtime grounding
     gate for high-stakes answers. The coordinator already surfaces `rag_sources` provenance to
     ground against.
  2. **RC3 routing discipline** — the coordinator must consistently establish account context
     (`get_account_info`) BEFORE/ALONGSIDE the doc delegation for tier-dependent questions, instead
     of answering from docs without confirming the caller's tier.
**Method (measure-first, human-directed): characterize before fixing.** RC3's "occasional" behavior
is turned into a HARD, repeated eval (`eval/tier_discipline.py`) — 5 tier-dependent questions × N
reps, asserting on the TRACE that `get_account_info` precedes/accompanies `nova_docs`. The flicker
becomes a pass-RATE gate (100% required), not an anecdote. Baseline measured first; the
routing-prompt fix only lands after, and must move the rate to a clean 100% or the prompt needs more
tightening. Retrieval tuning is considered DONE once grounding + discipline are clean and recall
still reads 100%.

**Baseline measured (GLM, 5 cases × 5 reps = 25 runs, 2026-07-01):** discipline **8% (2/25)** —
T1–T4 = 0/5, T5 = 2/5. The RC3 seam is SYSTEMATIC, not "occasional" as Phase 2 undersold it: the
coordinator answers tier-dependent questions from generic docs and looks up the account *after* (or
never). Critically, **answer accuracy was 96%** — the generic doc facts happened to match these
customers' tiers, so the prose looked right while the trace shows the tier was never verified first.
That mask is the whole point of asserting on the trace, not the answer.

**Order correction (human, 2026-07-01): fix RC3 discipline BEFORE the grounding check, not after.**
Rationale: the grounding check asks "is the answer supported by the retrieved chunks?" — a
tier-blind answer ("Zapier is Enterprise-only") IS supported by the docs, so grounding would PASS
on RC3 cases and give false safety. The defect is upstream of grounding: the answer is generic when
it should be personalized to the caller's tier. So fix the retrieval SEQUENCE first, then let
grounding validate the complete pipeline (tier-aware retrieval → grounded answer), not the RAG agent
in isolation.

**Fix applied + re-measured: discipline 8% → 100% (25/25), GATE PASS.** `COORDINATOR_INSTRUCTION`
gained a gated "TIER-DEPENDENT question" branch (MUST call `get_account_info` FIRST → then
`nova_docs` → then answer for THEIR tier) plus a reinforcing RULE (prompt content, D4, human-
directed). Re-run on GLM (5×5): every case 5/5 discipline, no flicker — comfortably past the 80%
target the human set as "realistic given model nondeterminism." Answer accuracy 96% (T5 dropped the
"10,000" rate-limit figure on one rep — content variance, unrelated to the routing sequence).

**P4-D6 grounding check — realized (2026-07-01), both gates PASS.** Built as three pieces:
(1) a shared `guardrails/grounding.py` LLM-judge (Groq Scout) — "is every factual claim in the
answer supported by the retrieved passages?"; an honest decline counts as grounded; FAILS OPEN on
judge/parse error so the gate never blocks on noise. (2) A RUNTIME **detect-annotate** hook in
`NovaCoordinator.run` (human-chosen posture): on RAG-delegated answers, a below-threshold grounding
score FLAGS the turn and appends a soft verification hedge — it NEVER rewrites/blocks a correct
answer; the flag rate is the signal for whether a hard gate is ever justified. (3) A self-validating
`eval/grounding_eval.py` — POSITIVE set (real coordinator answers, grounded via the runtime check)
plus a NEGATIVE CONTROL (fabricated answers over real passages that MUST be flagged), so the metric
can't be vacuous. `RagSpecialistAgent`'s sink now carries the retrieved chunk TEXTS. **Result (GLM):
positive grounded-rate 100% (10/10), negative-control catch-rate 100% (3/3)** — the three
fabrications all scored 1, proving the judge discriminates.

**P4-D8 addendum — the grounding eval CAUGHT an over-correction from the RC3 fix (measure-first,
again).** The first grounding run showed R3/R4/R6 (questions that NAME a tier — "Zapier on the
Professional plan?") returning EMPTY routes: the RC3 discipline rule had over-generalized, so the
coordinator demanded a customer ID and punted instead of delegating to `nova_docs`. Those cases were
passing grounding only by DEFAULT (no RAG answer to check) — a hollow pass the negative-control-style
scrutiny exposed. `tier_discipline.py` had missed it (it only tests "my plan" phrasings). **Fix:**
split the router rule — "my/our plan" (tier unknown) → `get_account_info` first; "the <Tier> plan"
(tier named) → straight to `nova_docs`, no lookup (tier already given). Re-verified BOTH directions
on GLM: tier_discipline still 100% (25/25); grounding R3/R4/R6 now delegate + score 5 (real, not
hollow). Lesson logged: a discipline rule and its inverse both need a test, or tightening one silently
breaks the other.

**P4-D8 close-out — golden regression (regress-every-phase): NO quality regression.** Re-ran the 33
golden cases through the coordinator on the current prompt: 30/33 scored clean (corr 4.71 / help
4.57 / safe 4.96 / persona 4.82), at Phase-2 parity — the tier-discipline + grounding changes did
not regress single→multi-agent quality. The recorded GATE FAIL was purely infrastructure:
G31/G32/G33 hit KEY6 credit-402 mid-run (re-confirmed correct individually afterward); G15/G26 were
transient Groq judge errors. Hardened `run_eval.py` (per-case retry + record-and-continue so one
402/timeout can't crash the whole run) and made G33's cross-customer decline marker robust
("your own account"). A clean RECORDED 33/33 PASS is owed once KEY6 is topped up.

**Finding (extends P4-D7): ADK/LiteLlm has no 402 key-rotation.** The hand-built `LLMClient` rotates
`OPENROUTER_ACTIVE_KEY` → fallbacks on 402; ADK's `LiteLlm` (the coordinator's model) is pinned to
one key and hard-fails when it drains — a single point of credit failure for the multi-agent layer.
Logged as a hardening item (a LiteLlm retry/rotation wrapper), not urgent while all spare keys are
also drained. This is the LiteLLM-as-ADK-plumbing trade-off (P4-D7) surfacing operationally.

## P4-D9: ADK web UI wired for inspection (2026-07-01)
`adk_app/nova/` exports `root_agent` = the coordinator's `LlmAgent` (via a new
`NovaCoordinator.adk_agent` accessor — same instance the wrapper builds, so no drift). `adk web
adk_app` / `adk run adk_app/nova` now discover it. Chosen over rebuilding a bespoke UI: it's free
with ADK and gives a live routing/delegation/tool-call trace view. **Accepted limitation:** the dev
UI drives the RAW ADK agent, BYPASSING the hand-built input/output guardrails + memory that
`run()` wraps (P4-D7 keeps those outside ADK) — so it's an inspection surface, not the guardrailed
production path (documented in `adk_app/README.md` + the `adk_agent` docstring).

---

## P4-D10: Phase 4 combined evaluation — aggregate, don't re-run; delegation latency measured (2026-07-01)
Phase 4 is the capstone combined eval across both agents. **Decision: AGGREGATE the already-passing
phase gates into one scorecard rather than re-run them** (human call — the evidence is complete;
re-running to refresh a credit-limited artifact is process theater). `eval/run_phase4.py` reads the
five gate JSONs, recomputes the golden four-pillar means over the cleanly-scored cases (so the
numbers reflect quality, not the credit-402 infra noise), and measures the two multi-agent metrics
that were never taken: delegation latency + context sharing. **Overall gate PASS** — four-pillar
4.71/4.57/4.96/4.82 (28 clean), retrieval 100%, routing 100%, grounding +100%/-100%, tier discipline
100%, context sharing verified.

**Finding - delegation latency is the coordinator pattern's real cost: ~43.8s delegated vs ~9.4s
direct (~34s overhead).** A RAG-delegated turn chains many sequential model calls: coordinator route
-> AgentTool spins an inner Runner -> the hand-built RAG agent runs its own multi-iteration ReAct loop
(retrieve + synthesize) -> back to the coordinator to synthesize -> the runtime grounding check (a
Groq call). This is the honest price of GENUINE agent-to-agent delegation (P4-D5) over a plain
`search_documentation()` function call - the tradeoff we accepted at P4-D5, now quantified. Not
gated; flagged for the Phase-5 retrospective (a production build would stream, parallelize the
grounding check, and cache hot doc queries).

**Context sharing verified (RAG-vs-memory coexistence, D5):** customer memory reaches the
coordinator (temp-store `context_block` round-trip); the RAG specialist receives shared session
state via AgentTool but by design answers from docs only - memory is coordinator-side. The two
knowledge sources coexist with the clean boundary the project set out to demonstrate.

---
