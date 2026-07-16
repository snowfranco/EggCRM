# EggCRM — Project 4: Agentic RAG + Multi-Agent Coordinator

Project 4 evolves the framework-free EggCRM support agent (Project 3, see [`README.md`](README.md))
into a **multi-agent system**: **Nova**, an [ADK](https://google.github.io/adk-docs/) coordinator,
routes each request by intent and **delegates** documentation questions to a standalone **RAG
specialist** (`nova_docs`) that answers from a real vector-retrieval system.

Two deliberate framework choices define it (see [`DECISIONS_4.md`](DECISIONS_4.md) P4-D7):
- **ADK, used deliberately, for the coordinator/delegation layer only.** P3 proved the value of
  hand-rolling orchestration; P4 now uses a framework *where multi-agent coordination is the point*.
- **The RAG pipeline stays hand-built** — chunking, embedding, vector store, retrieval, and the RAG
  agent's ReAct loop are all raw Python. ADK never touches retrieval.

The P3 guardrails, memory, and action gates are **preserved and reused**: they *wrap* the ADK
coordinator (input screen before, output guard + grounding + memory extraction after) rather than
being rebuilt inside ADK.

## Architecture

```
                        ┌─────────────────────────────┐
   user message ──────► │  INPUT GUARDRAILS (P3)      │  PII redact → injection → topic
                        └──────────────┬──────────────┘
                                       ▼
                        ┌─────────────────────────────┐
   customer memory ───► │  NOVA COORDINATOR (ADK)     │  gated WORKFLOW router (GLM-4.7-Flash
   (injected)          │   LlmAgent + LiteLlm         │  via LiteLlm). Escalation-first gate,
                        └──────┬─────────┬─────────────┘  then classify & route/delegate.
                    delegate   │         │  call tools (+ P3 action gates)
                        ▼      │         ▼
        ┌───────────────────┐ │   ┌──────────────────────────────┐
        │ nova_docs (RAG)   │ │   │ get_account_info /             │
        │  AgentTool →      │ │   │ create_support_ticket /        │
        │  hand-built       │ │   │ escalate_to_team  (FunctionTool)│
        │  RAGAgent:        │ │   └──────────────────────────────┘
        │  ReAct loop +     │ │
        │  retrieve_docs /  │ │   Retrieval (hand-built): all-MiniLM-L6-v2
        │  search_by_meta   │ │   embeddings → ChromaDB (cosine) → top-k chunks
        └───────────────────┘ │
                               ▼
                        ┌─────────────────────────────┐
                        │  OUTPUT GUARDRAILS (P3)     │  PII · cross-customer · over-promise
                        │  + GROUNDING CHECK (P4-D6)  │  RAG answer supported by chunks?
                        └──────────────┬──────────────┘  (detect + annotate, never block)
                                       ▼
        reply to user ◄────────────────┤
                                       ▼ (end of conversation)
                        ┌─────────────────────────────┐
                        │  MEMORY EXTRACTION (P3)     │  durable facts → per-user store
                        └─────────────────────────────┘
```

**Non-shadow rule (P4-D6):** retrieved docs are authoritative for product knowledge, memory for
user context, account tools for live account state — no source silently overrides another.

## Layout (Project 4 additions)

- `src/novacrm_agent/rag/` — hand-built pipeline: `chunker` (semantic-by-heading + metadata),
  `embedder` (local all-MiniLM-L6-v2), `store` (ChromaDB), `ingest`, `retriever`.
- `src/novacrm_agent/agents/` — `rag_agent` (standalone RAG ReAct agent, Phase 1),
  `rag_specialist` (thin ADK `BaseAgent` wrapping it), `coordinator` (`NovaCoordinator` + the ADK
  `LlmAgent`).
- `src/novacrm_agent/guardrails/grounding.py` — the P4-D6 grounding check (shared by runtime + eval).
- `adk_app/nova/` — `root_agent` export so `adk web` can discover the coordinator (inspection only).
- `data/knowledge_base/docs/` — the 20-doc corpus (feature guides / API reference / troubleshooting).
- `eval/` — `rag_baseline`, `routing_baseline`, `tier_discipline`, `grounding_eval`, and
  `run_phase4` (the combined capstone), plus `run_eval.py --coordinator` (golden regression).

## Running it

```bash
pip install -r requirements.txt          # includes google-adk + litellm
# .env needs a funded OPENROUTER_API_KEY (GLM-4.7-Flash) + GROQ_API_KEY (Scout guard/judge)

python -m novacrm_agent.rag.ingest        # build the ChromaDB vector store (once)

# Inspect the multi-agent routing live (raw ADK agent — bypasses guardrails, see adk_app/README.md):
./venv/bin/adk web adk_app                # UI at http://localhost:8000, pick "nova"
```

The guardrailed production path is `NovaCoordinator.run()`:

```python
from novacrm_agent.agents.coordinator import NovaCoordinator
from novacrm_agent.session import new_session

nova = NovaCoordinator(provider="openrouter")          # GLM-4.7-Flash coordinator
sess = new_session("demo", user_id="CUST-1001")
result = nova.run("What integrations does my plan support?", customer_id="CUST-1001", session=sess)
print(result.final_text, result.route, result.rag_sources, result.grounding)
```

## Evaluation — Phase 4 combined (GLM-4.7-Flash) · **OVERALL GATE PASS**

Regenerate: `python eval/run_phase4.py` → `eval/phase4_report.json` + `outputs/phase4-report.md`.

| Dimension | Result | Gate |
|---|---|---|
| Effectiveness (correctness / helpfulness) | **4.71 / 4.57** | ✅ |
| Safety (judge) / Persona | **4.96 / 4.82** | ✅ |
| Retrieval recall / correctness | **100% / 100%** | ✅ |
| Routing accuracy (boundary cases) | **100%** (10/10) | ✅ |
| Grounding (positive / negative-control) | **+100% / −100%** | ✅ |
| Tier-routing discipline (5×5 reps) | **100%** | ✅ |
| Context sharing (memory → coordinator) | **verified** | ✅ |
| Delegation latency (delegated vs direct) | **43.8s vs 9.4s (~34s overhead)** | — |

Four-pillar means are over the 28 cleanly-scored golden cases; the recorded golden artifact is
credit-limited (3 cases hit a mid-run key-402 and were re-confirmed correct individually — a
provider-credit limitation, not a quality one). Full method + the measure-first catches (RC3
discipline 8%→100%; the grounding eval then catching the RC3 fix's over-correction) are in
[`DECISIONS_4.md`](DECISIONS_4.md).

## Retrospective — with-framework (ADK) vs framework-free (P3)

> **Human-owned narrative (per CLAUDE.md D4).** The measured observations below are drafted from the
> build; the *conclusions and recommendation* are for the human to write.

**What ADK gave us (the multi-agent layer):**
- Delegation as a first-class primitive: `AgentTool` + an inner `Runner` made "coordinator delegates
  to a specialist and incorporates the answer" a few lines, not a hand-rolled sub-loop.
- A discoverable dev UI (`adk web`) for tracing routing/delegation for free.

**What ADK cost / where the seams showed:**
- **`LiteLlm` reintroduced** as ADK's non-Gemini model adapter (P3 had avoided LiteLLM), and it has
  **no 402 key-rotation** — unlike the hand-built `LLMClient`, a draining key hard-fails the
  coordinator mid-run (surfaced in the golden regression). Single point of credit failure.
- **`AgentTool` runs the sub-agent in a separate inner Runner**, so the specialist's provenance
  (`custom_metadata`) never reaches the parent event stream — we route it through an out-of-band
  sink. A hidden abstraction the framework-free path wouldn't have had.
- **Guardrails/memory stayed hand-built and wrapped ADK** rather than being ported into ADK
  callbacks — the lowest-risk way to keep P3's proven, signed-off behavior intact.
- **Delegation is expensive:** ~34s overhead per RAG-delegated turn (many sequential model calls)
  vs a plain function call. The coordinator pattern's price, quantified (P4-D5).

**Human to complete:**
- _Was ADK worth it for a 3-agent system, or would a hand-rolled router have been simpler?_
- _Where is the framework's leverage vs its lock-in, having now built both ways (P1/ADK, P3 raw, P4 hybrid)?_
- _What would you reach for next time, and for what shape of problem?_
