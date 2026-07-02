"""Model + provider configuration.

Project 3 is framework-free: no ADK, no LiteLLM. We talk to providers directly
through the OpenAI-compatible client by pointing `base_url` at each provider and
passing the bare model slug (no `openrouter/` / `groq/` LiteLLM prefixes).

Carried forward from Project 1's wiring:
  - Primary:  GLM-4.7-Flash via OpenRouter  (good tool-call discipline, cheap)
  - Judge:    Llama 4 Scout via Groq        (LLM-as-a-Judge in eval, Phase 6)
  - Fallback: GLM-4.7 via Cerebras          (documented, not primary)
"""

import os

from dotenv import load_dotenv

load_dotenv()

# --- Provider endpoints (OpenAI-compatible) ---------------------------------
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
CEREBRAS_BASE_URL = "https://api.cerebras.ai/v1"

# --- Model slugs (bare — no LiteLLM provider prefix) ------------------------
OPENROUTER_GLM_MODEL = "z-ai/glm-4.7-flash"
GROQ_SCOUT_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
CEREBRAS_GLM_MODEL = "zai-glm-4.7"

# --- Active selection -------------------------------------------------------
# Primary agent model. Phase 1 will run the 10-query reliability baseline
# against this before anything is built on top of it (measure-before-proceeding).
PRIMARY_MODEL = OPENROUTER_GLM_MODEL
PRIMARY_BASE_URL = OPENROUTER_BASE_URL

# Judge model used only by the eval harness in Phase 6.
JUDGE_MODEL = GROQ_SCOUT_MODEL
JUDGE_BASE_URL = GROQ_BASE_URL

# --- API keys (from environment / .env) -------------------------------------
# The numbered OPENROUTER_API_KEY / _KEY2… keys accumulated as earlier accounts drained (each 402s
# once out of credits). `_KEY6` (2026-06-30) is a FRESH, FUNDED account. `OPENROUTER_ACTIVE_KEY` is
# the key both paths use first — the hand-built LLMClient AND ADK's LiteLlm (which has no 402
# fallback of its own, so it MUST be pointed at a funded key directly). Prefer the newest funded
# key; the drained originals stay in the chain as last-resort rotation targets.
_OPENROUTER_KEYS_IN_ORDER = [
    os.environ.get(name) for name in (
        "OPENROUTER_API_KEY7",              # newest funded account first (2026-07-01)
        "OPENROUTER_API_KEY6",              # fresh funded account (2026-06-30, now near-empty)
        "OPENROUTER_API_KEY", "OPENROUTER_API_KEY2", "OPENROUTER_API_KEY3",
        "OPENROUTER_API_KEY4", "OPENROUTER_API_KEY5", "OPENROUTER_API_KEY_FALLBACK",
    )
]
_OPENROUTER_KEYS_IN_ORDER = [k for k in _OPENROUTER_KEYS_IN_ORDER if k]
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")  # original primary (kept for back-compat)
# The key clients should use first (funded), then the rest as the 402-rotation fallback chain.
OPENROUTER_ACTIVE_KEY = _OPENROUTER_KEYS_IN_ORDER[0] if _OPENROUTER_KEYS_IN_ORDER else None
OPENROUTER_FALLBACK_KEYS = _OPENROUTER_KEYS_IN_ORDER[1:]
# Back-compat single-value alias (first fallback, if any).
OPENROUTER_API_KEY_FALLBACK = OPENROUTER_FALLBACK_KEYS[0] if OPENROUTER_FALLBACK_KEYS else None
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
CEREBRAS_API_KEY = os.environ.get("CEREBRAS_API_KEY")
