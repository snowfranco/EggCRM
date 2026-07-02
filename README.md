# EggCRM Support Agent

A **framework-free** customer-support agent with **memory** and **guardrails** for *EggCRM*, a
fictional CRM SaaS. Built as the capstone for Google's 5-Day AI Agents Intensive Course — the
orchestration loop, session/long-term memory, input/output guardrails, and human-in-the-loop
escalation are all hand-built (no ADK, no LangChain, no LiteLLM), so every abstraction a framework
would normally hide is visible and owned in the code.

It meets **Nova**, a support agent that answers product/billing/account questions, remembers
customers across conversations, refuses prompt-injection and off-topic requests, redacts PII,
escalates what it isn't authorized to handle, and is measured end-to-end across four pillars.

> **Project 4 evolves this into a multi-agent system** — Nova becomes an ADK *coordinator* that
> delegates documentation questions to a hand-built RAG specialist over a real vector store, with a
> grounding check on top. This README documents the framework-free P3 agent; see
> **[`README_PROJECT4.md`](README_PROJECT4.md)** for the Agentic RAG + Multi-Agent build and its
> combined evaluation.

## Architecture

```
                              ┌──────────────────────────────┐
        user message ───────► │  INPUT GUARDRAILS            │  PII redact → injection → topic
                              └──────────────┬───────────────┘
                                             ▼
   long-term memory ───────►  ┌──────────────────────────────┐
   (per-user, injected)       │  CONTEXT ASSEMBLY            │  system prompt + memories + history
                              └──────────────┬───────────────┘
                                             ▼
                              ┌──────────────────────────────┐
                              │  ORCHESTRATION LOOP (ReAct)  │  think → call tools → observe → repeat
                              │   tools: KB · account ·      │  (max-iters safety net)
                              │   ticketing · escalate       │  + action gates (confirm, identity)
                              └──────────────┬───────────────┘
                                             ▼
                              ┌──────────────────────────────┐
                              │  OUTPUT GUARDRAILS           │  PII · forbidden · cross-customer · over-promise
                              └──────────────┬───────────────┘
                                             ▼
        reply to user ◄───────────────────  ┤
                                             ▼ (end of conversation)
                              ┌──────────────────────────────┐
                              │  MEMORY EXTRACTION           │  durable facts → per-user store
                              └──────────────────────────────┘
```

- **Orchestration loop** (`orchestrator.py`) — hand-rolled ReAct: assemble context, call the model,
  dispatch tool calls, feed observations back, repeat until a final answer or the max-iters net.
- **Tools** (`tools/`) — `lookup_knowledge_base` (RAG over the KB), `get_account_info` (source of
  truth for account state), `create_support_ticket`, `escalate_to_team` (structured HITL handoff).
- **Memory** (`memory/`) — session history (short-term) + per-user durable facts (long-term):
  extracted at conversation end, consolidated, injected at session start. Tool-authoritative state
  (plan/billing/storage) is read live, never memorized (the "non-shadow" rule, D5).
- **Guardrails** (`guardrails/`) — input: PII redaction → injection (3-state regex + LLM-on-uncertain)
  → topic boundary; output: PII / forbidden-content / cross-customer / over-promise; plus action
  gates (confirm-before-create, identity check). Every failure mode has a primary fix + a safety net.
- **Tracing** (`tracing.py`) — one structured-span schema (timestamp/phase/intent/outcome/tokens/…)
  → JSONL; the observability backbone, no vendor coupling.

## Setup

```bash
git clone <repo> && cd novacrm
python3 -m venv venv
./venv/bin/python -m pip install -e .          # installs the package + deps
npm install && npm run build                    # builds the demo web UI (webui/app.js)
cp .env.example .env                            # then add your keys:
#   OPENROUTER_API_KEY=...   (agent; required)
#   GROQ_API_KEY=...         (LLM-judge; required for eval)
#   OPENROUTER_API_KEY2/3=... (optional fallback keys, used on a 402)
```

## Usage

```bash
# CLI chat
./venv/bin/python -m novacrm_agent.runner --customer CUST-1001

# Demo server (web UI + API) → http://localhost:8001
./venv/bin/python -m novacrm_agent.server        # --port N to change

# Full four-pillar evaluation (LLM-judge via Groq)
./venv/bin/python -m eval.run_eval               # --use-cache re-judges without re-running the agent

# Tests
./venv/bin/python -m pytest
```

The server exposes `GET /` (the demo UI), `GET /health`, and `POST /chat`
(`{message, session_id, customer_id}` → `{response, trace}`).

## Evaluation results

Combined four-pillar eval over a 32-case golden dataset (agent: GLM-4.7-Flash; judge: Llama 4 Scout
via Groq). Gate: mean ≥ 4.0 per dimension, no case with safety ≤ 2, no case with correctness = 1.

| Pillar | Metric | Result |
|---|---|---|
| **Effectiveness** | mean correctness / helpfulness (judge, 1–5) | **4.8–5.0 / 4.6–4.8** |
| **Safety** | mean safety (judge) | **5.0** |
| | prompt-injection blocked | **100%** (18/18) |
| | output leak-free | **100%** (10/10) |
| | PII redaction / topic boundary | **6/6 · 7/7** |
| | HITL escalation case files | 5 |
| **Robustness** | golden structural pass | 97% |
| | Phase 2 regression / Phase 3 cross-session | 15/15 · 3/3 |
| **Efficiency** | mean iterations / tokens / latency | 2.0 · 3,850 · 3.4s |
| **Persona** | mean persona (judge) | 4.8–4.9 |

**Gate: PASS** (no floor violations) on the latest run — best observed 4.97 / 4.81 / 5.0 / 4.94.
Full report: `outputs/eval-report.md`; raw data: `eval/combined_report.json`.

The agent runs at temperature 0.2 and the judge is a free-tier model, so per-run results vary, and
the strict floors (no single `correctness=1`) are sensitive to that variance. A **"3 consecutive
green runs"** criterion is the stronger gate; run it in a stable shell:

```bash
for n in 1 2 3; do ./venv/bin/python -m eval.run_eval | grep GATE; done
```

The one historically-flaky case (G17, confirm-then-create) was root-caused and fixed in D15
(output-guard self-customer determination now spans the whole session). Transient judge failures
are logged as `judge_error` and excluded from means.

## Key decisions

Full rationale in [`DECISIONS.md`](DECISIONS.md) (D1–D15 + a Plan-vs-Actual table). The five most
consequential:

1. **Two-model architecture (D2)** — GLM-4.7-Flash (agent, OpenRouter) + Llama 4 Scout (judge, Groq):
   separate providers avoid self-evaluation bias and quota collision.
2. **Non-shadow rule (D5)** — tool-authoritative state (plan/billing/storage) is read live, never
   memorized; memory holds only durable context the system of record doesn't. Keeps grounding clean.
3. **Escalation as a tool (D6)** — `escalate_to_team` makes escalation a structured, trace-visible
   action instead of prose, so eval/observability can verify it (and HITL can log a case file).
4. **S5 efficiency check demoted (D11)** — re-fetching authoritative state live is *correct* per D5;
   the original check penalized the right behavior (a Phase-2/Phase-3 contradiction, caught by eval).
5. **Extraction-prompt calibration (D10)** — a 4th few-shot for preferences embedded in transactional
   turns; the few-shots are the calibration core that draws the "worth remembering vs noise" line.

## What I learned

*(Framework comparison — with-framework (Project 1, ADK) vs. without-framework (Project 3) — to be
written.)*
