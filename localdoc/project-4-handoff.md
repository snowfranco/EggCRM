# Project 4 Handoff — Agentic RAG + Multi-Agent Prototype for EggCRM

## Context from Projects 1–3

Three projects completed from Google's 5-Day AI Agents Intensive Course:

- **Project 1** (ADK): Product Strategy Research Agent — established eval harness, gated WORKFLOW pattern, measure-before-proceeding discipline
- **Project 3** (framework-free): EggCRM Customer Support Agent — memory (session + cross-session), two-layer guardrails, HITL escalation, full four-pillar evaluation

The RAG-vs-memory boundary is already clean from Project 3's D5 decisions: memory curates dynamic, user-specific context (who the customer is, their history, their preferences). RAG handles static, external knowledge (product documentation, release notes, troubleshooting guides). Project 3 used a hardcoded knowledge base (JSON). Project 4 replaces that with a real retrieval system and uses it as the vehicle for introducing multi-agent coordination.

## What Project 4 Builds

### The Product: EggCRM Documentation RAG Agent

EggCRM's support agent (Project 3's Nova) currently answers from a small, hardcoded knowledge base. Real product documentation is much larger — feature guides, API docs, release notes, troubleshooting playbooks, changelog entries. A RAG agent retrieves relevant documentation chunks to ground Nova's answers in the actual product docs rather than a curated FAQ.

### The Multi-Agent Angle: Coordinator Pattern

Instead of bolting RAG into Nova directly, build it as a separate specialist agent that Nova delegates to. This creates a minimal but real multi-agent system:

```
                    ┌─────────────────┐
     User ─────────▶│  Nova (Router)  │
                    │  Support Agent  │
                    └───────┬─────────┘
                            │ routes by intent
              ┌─────────────┼──────────────┐
              ▼             ▼              ▼
     ┌────────────┐  ┌────────────┐  ┌──────────┐
     │ RAG Agent  │  │ Account    │  │ Escalation│
     │ (docs/KB)  │  │ Tools      │  │ Protocol  │
     └────────────┘  └────────────┘  └──────────┘
```

Nova becomes the orchestrator/router. When a customer asks a product question ("how do I set up workflow automation?"), Nova routes to the RAG agent, which retrieves relevant doc chunks and synthesizes an answer. When they ask about their account, Nova uses its existing tools. When they need escalation, Nova uses the existing protocol. This is the Coordinator pattern from the course's Agents Companion — a manager agent that routes to specialists.

### Why this scope

It exercises every remaining course concept cleanly:
- **Agentic RAG** (Day 3 + Companion): vector retrieval, chunking strategy, embedding model selection, retrieval evaluation, grounding checks
- **Multi-agent coordination** (Day 1 + Companion): the coordinator pattern, agent-to-agent communication, routing logic, fallback strategies
- **The RAG-vs-memory teaching point**: RAG and memory coexist in the same system with clear boundaries — RAG handles product knowledge, memory handles user context
- **Grounding evaluation**: the deferred grounding check from Project 3's Phase 6 becomes a first-class eval dimension, now that there's a retrieval system to ground against

## Architecture Decisions to Make (Phase 0)

### D1: Vector store
Options: ChromaDB (embedded, zero-infrastructure, good for local dev), FAISS (faster, lower-level), Pinecone/Weaviate (cloud, production-grade but adds vendor dependency). Recommendation: ChromaDB — it's pip-installable, persistent, and good enough for a capstone project. The interface is simple enough that swapping to a production store later is a one-module change.

### D2: Embedding model
Options: OpenAI embeddings via OpenRouter (if available), a free local model (sentence-transformers/all-MiniLM-L6-v2 via HuggingFace), or Google's embedding model (if API key allows). Recommendation: start with a local sentence-transformer — zero cost, no API dependency, fast enough for a small corpus. Switch to a provider-hosted model only if retrieval quality is poor.

### D3: Document corpus
What documentation to ingest. Options: (a) expand the existing EggCRM KB into longer-form docs (feature guides, API reference, troubleshooting playbooks), (b) use a real open-source product's documentation, (c) generate synthetic docs. Recommendation: (a) — expand EggCRM's world. You control the content so you can write eval cases with known-correct answers. Create 15–20 doc pages covering feature deep-dives, API reference, and troubleshooting guides. Each page becomes chunks in the vector store.

### D4: Chunking strategy
How to split documents for embedding. Options: fixed-size (simple), semantic (by section/heading), recursive character splitting. Recommendation: semantic by heading — the EggCRM docs can be structured with clear headings, making semantic chunking natural. Add metadata (doc_title, section, doc_type) to each chunk for filtering.

### D5: Agent communication protocol
How Nova talks to the RAG agent. Options: (a) function call — Nova calls a `search_documentation(query)` tool that internally runs the RAG pipeline, (b) full agent delegation — Nova sends a message to the RAG agent which has its own ReAct loop and returns a synthesized answer, (c) sub-agent with shared context. Recommendation: (b) for the multi-agent learning — the RAG agent is a real agent with its own system prompt, retrieval tool, and reasoning loop, not just a function call. Nova delegates, waits for the response, and incorporates it. This exercises the coordinator pattern genuinely.

### D6: Grounding evaluation
The deferred item from Project 3. Now that there's a retrieval system, grounding checks become meaningful: "is the agent's answer actually supported by the retrieved chunks?" Options: (a) runtime grounding gate (reject ungrounded responses), (b) eval-time grounding score (LLM-as-a-Judge dimension). Recommendation: both — (b) as the primary metric in the eval rubric, (a) as an optional runtime check for high-stakes answers. This completes the quality flywheel that Project 3 deferred.

## Phased Build Plan (sketch)

### Phase 0: Decisions + corpus creation
- Human: D1–D6 decisions, write the EggCRM documentation corpus (15–20 pages)
- Claude Code: scaffold, set up ChromaDB, implement chunking + embedding pipeline, ingest corpus

### Phase 1: RAG agent (standalone)
- Build the RAG agent as a standalone agent with its own ReAct loop
- Tools: `retrieve_docs(query) -> list[chunks]`, `search_by_metadata(filters) -> list[chunks]`
- System prompt: "You are a documentation expert for EggCRM. Answer questions using ONLY the retrieved documentation. If the docs don't cover it, say so."
- Baseline: 10 documentation questions, measure retrieval recall + answer correctness

### Phase 2: Multi-agent integration
- Wire Nova as the coordinator — intent classification routes to RAG agent vs. account tools vs. escalation
- Communication protocol between agents
- Session context shared (customer memories available to both agents)
- Baseline: the full Project 3 test suite (regression) + 10 new RAG-specific cases

### Phase 3: Retrieval optimization
- Measure retrieval quality (recall, precision, relevance)
- Tune: chunk size, overlap, metadata filtering, query expansion
- Implement re-ranking if baseline shows relevance issues
- Grounding checks (runtime + eval)

### Phase 4: Combined evaluation
- Full four-pillar eval across both agents
- New dimensions: retrieval quality, grounding accuracy, routing correctness
- Multi-agent-specific metrics: routing accuracy, delegation latency, context sharing

### Phase 5: Documentation + retrospective

## What Carries Forward

### Models & APIs (all still wired)
- OpenRouter (GLM-4.7-Flash) — primary agent model
- Groq (Llama 4 Scout) — guard model + eval judge
- Tavily (available, potentially useful for web-search augmentation in RAG)

### Infrastructure
- Eval harness (structural_eval, llm_judge, trajectory_eval, run_eval) — proven across P1 and P3, adapts again
- Structured JSON logging with trace-compatible schema
- Guardrail architecture (input + output, two-layer) — carries into the multi-agent context
- Memory system (extraction, store, retrieval) — coexists with RAG

### Proven Operating Principles
- **Gated WORKFLOW over flat rules** — for both Nova's router prompt and the RAG agent's prompt
- **Measure before proceeding** — baselines at every phase
- **Both defenses, not either/or** — applies to retrieval too (vector search + metadata filter)
- **Evidence over assumptions** — chunking strategy decided after measuring retrieval quality, not before
- **Non-shadow rule** — extends naturally: RAG-retrieved docs are authoritative for product knowledge, memories are authoritative for user context, account tools are authoritative for live account state. No source silently overrides another.

### Phase catches that validated measure-first (the track record)
- P1: ticket-confirmation spec error — eval was wrong, not the agent
- P3-Phase 2: prompt regression on confirm-before-create
- P3-Phase 3: embedded-preference extraction gap, recall-utilization failure
- P3-Phase 4: topic-guard false-positive, "sue" keyword muzzling escalations
- P3-Phase 5: mock data mismatches in output failure corpus
- P3-Phase 7: cross-customer false-positive in output guard, G08 KB hole, G30 max-iters timeout

### Working Arrangement (unchanged)
- Claude.ai: architecture decisions, planning, specs, review, red-teaming
- Claude Code: all implementation
- Human: API keys, prompt engineering decisions, eval case curation, document corpus authoring

## What's Different About Project 4

| Dimension | Project 3 | Project 4 |
|-----------|----------|----------|
| Knowledge source | Hardcoded JSON KB | Vector-retrieved documentation |
| Agent count | Single agent | Multi-agent (coordinator + specialist) |
| Retrieval | None (keyword search over FAQ) | Embedding + vector similarity + re-ranking |
| Grounding | Deferred to eval dimension | First-class (runtime + eval) |
| New infrastructure | Memory system | Embedding pipeline, vector store, agent communication |
| Framework | Framework-free (raw Python) | TBD — could stay raw, or use ADK for the multi-agent layer |

### The framework question for Project 4
Project 3 proved the value of going framework-free for understanding the internals. Project 4 could go either way: (a) stay framework-free and build the multi-agent coordination from scratch (more learning, more code), (b) use ADK for the multi-agent layer while keeping the RAG pipeline hand-built (best of both — you already know what ADK abstracts, now use it deliberately), (c) use ADK for everything. Decision deferred to Phase 0 of Project 4.
