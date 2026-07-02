"""`root_agent` export so `adk web` / `adk api_server` / `adk run` can discover the coordinator.

The exported agent is the SAME ADK `LlmAgent` that `NovaCoordinator` builds (via its `.adk_agent`
accessor) — one definition, no drift. Driving it from the ADK dev UI runs only the routing/
delegation loop and bypasses the hand-built guardrails/memory (see this package's README and the
`adk_agent` docstring). We keep the wrapper instance alive at module scope so the agent's bound
tool methods (which read the wrapper's per-run context) stay valid for the UI's lifetime.
"""

from __future__ import annotations

from novacrm_agent.agents.coordinator import NovaCoordinator

# Provider "openrouter" → GLM-4.7-Flash via LiteLlm on the funded OPENROUTER_ACTIVE_KEY (from .env).
_coordinator = NovaCoordinator(provider="openrouter")
root_agent = _coordinator.adk_agent
