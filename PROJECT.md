# EggCRM Support Agent — Project 3

Customer support agent with **memory** and **guardrails**, built **without an agent
framework** (raw Python orchestration loop). Third project in Google's 5-Day AI Agents
Intensive course track. Project 1 (research agent, ADK) lives at `../research-agent`.

## Why this project exists
1. Understand what frameworks abstract away by building the orchestration loop by hand.
2. Learn memory and guardrail patterns at the code level, not the config level.
3. Compare the "with framework" (P1/ADK) vs "without framework" (P3) experience.

## Scope (locked)
- **Domain:** EggCRM — fictional CRM SaaS. Billing / account / feature / bug support.
- **Memory:** session (short-term) + cross-session per-user facts (long-term). No
  semantic/embedding memory this project. RAG vs. memory demonstrated side-by-side.
- **Guardrails:** all four categories (prompt injection, PII, topic boundary,
  escalation), primary defense first, safety nets in a second pass.
- **Observability:** custom structured JSON tracing (D1). Phoenix deferred.
- **Models:** GLM-4.7-Flash @ OpenRouter (primary), Llama 4 Scout @ Groq (eval judge).

## Working arrangement
- Architecture/planning/prompt decisions: human-in-the-loop.
- Implementation: Claude Code.
- Human owns: API keys, eval case curation, prompt engineering, KB/persona content.

## Key references
- `project-3-handoff.md` — context carried from Project 1.
- `project-3-plan.md` — the full phased plan (Phases 0–7).
- `DECISIONS.md` — decision log (D1–D5 so far).
- `../research-agent/eval/` — Project 1 eval infra to adapt in Phase 6.

## Discipline (from Project 1)
Measure before proceeding · both defenses per failure mode · structure > content for
small models · regression-test every phase against prior baselines.
