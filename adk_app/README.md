# ADK web UI — inspecting the Nova coordinator

This directory exists so ADK's dev tooling (`adk web`, `adk api_server`, `adk run`) can DISCOVER
the multi-agent coordinator. ADK scans an agents directory for sub-packages that export a
`root_agent`; `nova/` is that package.

## Run it

    # from the repo root (uses the funded OpenRouter key from .env via config)
    ./venv/bin/adk web adk_app        # web UI at http://localhost:8000
    # or a one-shot CLI chat:
    ./venv/bin/adk run adk_app/nova

Pick **nova** in the UI's agent dropdown. You'll see Nova route each message: delegate product
questions to the `nova_docs` specialist (an AgentTool), call `get_account_info` /
`create_support_ticket` / `escalate_to_team`, and the full tool-call/delegation trace.

## Important caveat — this is an INSPECTION view, not the production path

`adk web` drives the **raw ADK `LlmAgent`** directly. That runs only the routing/delegation loop and
**BYPASSES the hand-built input/output guardrails + memory** that `NovaCoordinator.run()` wraps
around it (P4-D7 deliberately keeps those outside ADK). With no wrapper context, the action gates
fall back to session-less behavior (cross-customer identity check is inert; ticket creation stays
blocked until proposed). For the guardrailed path, use `NovaCoordinator` (or the P3 `webui/` demo).

The agent shown here is the SAME `LlmAgent` instance `NovaCoordinator` builds — one definition, no
drift (`nova/agent.py` exposes `NovaCoordinator(...).adk_agent`).
