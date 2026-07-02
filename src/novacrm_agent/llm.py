"""Thin LLM client over the OpenAI-compatible API (framework-free, no LiteLLM).

Dropping LiteLLM means we own retries and error handling — which is the point (D2).
This wraps the provider call with bounded exponential-ish backoff on transient errors
and returns a small normalized result the orchestrator can use without knowing the
provider. Token usage is surfaced so the tracer can record it per call.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError

from . import config


def _retry_delay(exc: Exception, attempts: int) -> float:
    """Exponential backoff (2,4,8,16s cap 30), honoring a Retry-After header when present."""
    backoff = min(2.0 ** attempts, 30.0)
    headers = getattr(getattr(exc, "response", None), "headers", None)
    if headers:
        try:
            return max(backoff, float(headers.get("retry-after", 0)))
        except (TypeError, ValueError):
            pass
    return backoff


@dataclass
class LLMResult:
    message: Any                 # the raw choice.message (may carry .tool_calls / .content)
    prompt_tokens: int
    completion_tokens: int
    finish_reason: Optional[str]

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class LLMClient:
    def __init__(
        self,
        model: str = config.PRIMARY_MODEL,
        base_url: str = config.PRIMARY_BASE_URL,
        api_key: Optional[str] = None,
    ):
        self.model = model
        self.base_url = base_url
        # default to the ACTIVE (funded) OpenRouter key for the primary endpoint; caller can
        # override. On a 402 the client rotates through OPENROUTER_FALLBACK_KEYS.
        self._api_key = api_key or config.OPENROUTER_ACTIVE_KEY
        self._client: Optional[OpenAI] = None
        self._fallback_keys = list(config.OPENROUTER_FALLBACK_KEYS)
        self._fallback_idx = 0

    def _switch_to_fallback(self) -> bool:
        """On a 402, advance to the next fallback OpenRouter key in the chain (if any left)."""
        if self.base_url != config.OPENROUTER_BASE_URL:
            return False  # fallback keys only apply to OpenRouter
        if self._fallback_idx >= len(self._fallback_keys):
            return False
        self._api_key = self._fallback_keys[self._fallback_idx]
        self._fallback_idx += 1
        self._client = None  # force rebuild with the new key
        return True

    def _ensure_client(self) -> OpenAI:
        if self._client is None:
            if not self._api_key:
                raise RuntimeError(
                    "No API key set. Add OPENROUTER_API_KEY to .env (see .env.example) "
                    "before running anything that calls the model."
                )
            self._client = OpenAI(base_url=self.base_url, api_key=self._api_key)
        return self._client

    def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        tool_choice: str = "auto",
        temperature: float = 0.2,
        max_tokens: int = 1024,
        max_retries: int = 4,
    ) -> LLMResult:
        # Cap output tokens: support replies and memory extractions are short, and
        # providers reserve credit against max_tokens — an uncapped request can 402 on a
        # low balance even though the actual completion is tiny.
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        last_exc: Optional[Exception] = None
        attempts = 0  # counts only transient retries; key-switches don't consume the budget
        while True:
            try:
                resp = self._ensure_client().chat.completions.create(**kwargs)
                choice = resp.choices[0]
                usage = resp.usage
                return LLMResult(
                    message=choice.message,
                    prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                    completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                    finish_reason=choice.finish_reason,
                )
            except (RateLimitError, APIConnectionError) as exc:
                # transient (incl. 429 throttling) — exponential backoff + Retry-After
                last_exc = exc
                attempts += 1
                if attempts >= max_retries:
                    break
                time.sleep(_retry_delay(exc, attempts))
            except APIStatusError as exc:
                # 402 = out of credits → advance the fallback-key chain and retry immediately
                # (does NOT consume the retry budget). 5xx is transient (back off); other 4xx
                # is a real bug — don't waste retries.
                last_exc = exc
                if exc.status_code == 402 and self._switch_to_fallback():
                    continue
                if exc.status_code and 500 <= exc.status_code < 600:
                    attempts += 1
                    if attempts >= max_retries:
                        break
                    time.sleep(_retry_delay(exc, attempts))
                else:
                    raise
        assert last_exc is not None
        raise last_exc
