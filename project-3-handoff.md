# Project 3 Handoff — Customer Support Agent with Memory and Guardrails

## Context from Project 1 (completed)

I just completed Project 1 (Personal Research Agent with Tool Use) from Google's 5-Day AI Agents Intensive Course. Key outcomes and decisions that carry forward:

### What was built
- A Product Strategy Research Agent on Google ADK 2.3.0
- GLM-4.7-Flash via OpenRouter (LiteLLM) as the primary model, with Llama 4 Scout via Groq as fallback
- Custom web_search tool (Tavily API) and Pydantic-validated structured output (ResearchBrief schema with StrategicSignal)
- Three-layer eval harness: ADK eval regression + structural checks + LLM-as-a-Judge (Scout via Groq)
- Full decision log (DECISIONS.md, D1-D14) tracking every architectural choice

### Key learnings to apply to Project 3
- **Rule structure > rule content for smaller models:** ordered gated WORKFLOWs with mandatory gates outperform flat parallel rules measurably
- **Measure before proceeding:** 10-query structured reliability baselines before building on top of uncharacterized foundations
- **Both defenses, not either/or:** primary fix + safety net for every failure mode (retry logic + coercion, forced tool_choice + defensive validation)
- **Capability vs. throughput failures are orthogonal:** rate limits and model tool-call discipline are separate failure categories requiring separate diagnosis
- **Built-in tools trade observability for convenience:** custom function tools give full trace visibility

### Working arrangement
- Claude.ai (this chat): architecture decisions, planning, human-layer guidance
- Claude Code: all implementation
- Human (me): human-in-the-loop tasks (API keys, UI interactions, eval case curation, prompt engineering decisions)

### Models & APIs already wired
- OpenRouter API key (GLM-4.7-Flash, other models available)
- Groq API key (Llama 4 Scout 17B, used as LLM-as-a-Judge)
- Tavily API key (search tool)
- Google API key (Gemini, available but rate-limited on free tier)
- Cerebras API key (wired but not primary)

### Eval infrastructure (reusable)
- structural_eval.py: deterministic pass/fail checks
- llm_judge.py: Scout-as-judge with 4-dimension rubric
- trajectory_eval.py: reliability + efficiency metrics
- run_eval.py: unified runner producing combined report

---

## Project 3: Customer Support Agent with Memory and Guardrails

### Decision: Build WITHOUT ADK

Project 1 used ADK. Project 3 will be built with raw code (no agent framework) to:
1. Understand what frameworks abstract away by building the orchestration loop myself
2. Learn memory and guardrail patterns at the code level, not the config level
3. Compare the "with framework" vs "without framework" experience firsthand

### Approach for observability without ADK Web UI
To be decided at session start — options discussed:
- Raw code + structured logging (maximum learning, minimum abstraction)
- Raw code + Arize Phoenix (open-source tracing UI, OpenTelemetry-based)
- The choice affects how step-throughs and trace inspection work

### What this project should exercise (from the course)
- RAG vs. memory distinction (Day 3 context engineering)
- Session state and memory persistence across turns
- Guardrail callbacks / input-output validation (Day 4 agent quality)
- Safety evaluation (prompt injection, PII detection, topic boundaries)
- Human-in-the-loop escalation patterns
- Evaluation with the existing eval infrastructure (adapted for this agent)

### Course materials available as project knowledge
- Day 1: Introduction to Agents
- Day 2: Agent Tools & Interoperability
- Day 3: Context Engineering (sessions, memory, RAG)
- Day 4: Agent Quality (evaluation, guardrails, safety)
- Agents Companion document
- ReAct paper, Chain-of-Thought paper
- GenAIOps guide

---

## What I need from this session
1. Brainstorm and scope Project 3 (what product/domain, what memory patterns, what guardrails)
2. Create a phased implementation plan (same style as Project 1: human tasks vs Claude Code tasks)
3. Build it iteratively with the same measure-before-proceeding discipline from Project 1
4. Run a full eval at the end using adapted versions of the existing eval infrastructure
