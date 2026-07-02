"""Structured JSON tracing (Decision D1).

Framework-free means we own the observability. Every component emits a span with a
single shared schema:

    timestamp, session_id, user_id, phase, intent (before), outcome (after),
    duration_ms, token_count, error

Logs + traces + metrics fall out of this one schema with no vendor coupling. Spans
are written as JSON Lines to eval/logs/<session_id>.jsonl and also kept in memory so
the eval harness (Phase 6) can read a turn's full trajectory without parsing files.

The span() context manager is the only thing callers touch:

    with tracer.span("tool_dispatch", "get_account_info(CUST-1001)") as s:
        result = ...
        s.outcome = "ok"
        s.token_count = 0

If the block raises, the span records the error and re-raises (we never swallow).
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

# Canonical phase names — keep this list authoritative so logs stay queryable.
PHASES = (
    "input_guard",       # Phase 4
    "context_assembly",
    "llm_call",
    "tool_dispatch",
    "output_guard",      # Phase 5
    "memory_extraction",  # Phase 3
)


@dataclass
class Span:
    phase: str
    intent: str
    session_id: str
    user_id: str
    timestamp: str
    outcome: Optional[str] = None
    duration_ms: Optional[float] = None
    token_count: Optional[int] = None
    error: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)


class Tracer:
    """Per-session tracer. One instance per conversation."""

    def __init__(self, session_id: str, user_id: str, log_dir: str | Path = "eval/logs"):
        self.session_id = session_id
        self.user_id = user_id
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.log_dir / f"{session_id}.jsonl"
        self.spans: list[Span] = []

    @contextmanager
    def span(self, phase: str, intent: str, **extra: Any) -> Iterator[Span]:
        if phase not in PHASES:
            raise ValueError(f"unknown phase {phase!r}; expected one of {PHASES}")
        s = Span(
            phase=phase,
            intent=intent,
            session_id=self.session_id,
            user_id=self.user_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            extra=dict(extra),
        )
        start = time.monotonic()
        try:
            yield s
        except Exception as exc:  # record then re-raise — never swallow
            s.error = f"{type(exc).__name__}: {exc}"
            s.outcome = s.outcome or "error"
            raise
        finally:
            s.duration_ms = round((time.monotonic() - start) * 1000, 2)
            if s.outcome is None:
                s.outcome = "ok"
            self._write(s)

    def _write(self, s: Span) -> None:
        self.spans.append(s)
        record = {k: v for k, v in asdict(s).items() if v is not None and v != {}}
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

    # --- helpers for the eval harness -------------------------------------
    def total_tokens(self) -> int:
        return sum(s.token_count or 0 for s in self.spans)

    def tool_calls(self) -> list[Span]:
        return [s for s in self.spans if s.phase == "tool_dispatch"]
