"""Session state — short-term (within-conversation) memory. Phase 2.

Design (per the approved schema):
  - Turns are stored as STRUCTURED data (tool_interactions as fields, not raw tool/result
    role messages). Three consumers read this: the LLM (conversation flow), the logger
    (trace metadata), and Phase 3's memory extractor (what *happened*, not just what was said).
  - Storage format and injection format are decoupled. Stored structured; injected into the
    LLM as natural language ("[recalled from earlier ...]") so the context stays compact and
    we control the rendering.
  - Storage mechanism: in-memory dict + JSON serialization to data/sessions/{id}.json.
    No SQLite — this is a single-threaded CLI; SQLite earns its keep in Phase 3's queryable
    memory store, not here.
  - Truncation: sliding window by turn count (default 20). System prompt is pinned separately
    by the orchestrator and is never part of `turns`. Token-budget truncation deferred (no
    tokenizer dependency; baseline showed short conversations).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_SESSIONS_DIR = Path(__file__).resolve().parents[2] / "data" / "sessions"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ToolInteraction:
    tool_name: str
    tool_input: dict
    tool_output: str  # serialized — see schema note


@dataclass
class SessionTurn:
    turn_number: int
    timestamp: str
    role: str  # "user" | "assistant"
    content: str
    tool_interactions: Optional[list[ToolInteraction]] = None
    escalated: bool = False
    escalation_target: Optional[str] = None

    def to_context_message(self) -> dict:
        """Render this turn for LLM context — natural language, not raw tool pairs."""
        if self.role == "user":
            return {"role": "user", "content": self.content}
        parts = [self.content] if self.content else []
        if self.tool_interactions:
            notes = "; ".join(
                f"{ti.tool_name}({json.dumps(ti.tool_input)}) -> {ti.tool_output}"
                for ti in self.tool_interactions
            )
            parts.append(f"[recalled from earlier in this conversation: {notes}]")
        return {"role": "assistant", "content": "\n".join(parts) or "(no reply)"}


@dataclass
class Session:
    session_id: str
    user_id: Optional[str]
    created_at: str
    updated_at: str
    turns: list[SessionTurn] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def add_turn(
        self,
        role: str,
        content: str,
        tool_interactions: Optional[list[ToolInteraction]] = None,
        escalated: bool = False,
        escalation_target: Optional[str] = None,
    ) -> SessionTurn:
        turn = SessionTurn(
            turn_number=len(self.turns) + 1,
            timestamp=_now(),
            role=role,
            content=content,
            tool_interactions=tool_interactions,
            escalated=escalated,
            escalation_target=escalation_target,
        )
        self.turns.append(turn)
        self.updated_at = turn.timestamp
        return turn

    def context_messages(self, window: int = 20) -> list[dict]:
        """Last `window` turns rendered for the LLM (system prompt pinned by caller)."""
        return [t.to_context_message() for t in self.turns[-window:]]

    # --- persistence ------------------------------------------------------
    def save(self, sessions_dir: Path = _SESSIONS_DIR) -> Path:
        sessions_dir.mkdir(parents=True, exist_ok=True)
        path = sessions_dir / f"{self.session_id}.json"
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, session_id: str, sessions_dir: Path = _SESSIONS_DIR) -> "Session":
        data = json.loads((sessions_dir / f"{session_id}.json").read_text(encoding="utf-8"))
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        turns = []
        for t in data.get("turns", []):
            tis = t.get("tool_interactions")
            turns.append(SessionTurn(
                turn_number=t["turn_number"],
                timestamp=t["timestamp"],
                role=t["role"],
                content=t["content"],
                tool_interactions=[ToolInteraction(**ti) for ti in tis] if tis else None,
                escalated=t.get("escalated", False),
                escalation_target=t.get("escalation_target"),
            ))
        return cls(
            session_id=data["session_id"],
            user_id=data.get("user_id"),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            turns=turns,
            metadata=data.get("metadata", {}),
        )


def new_session(session_id: str, user_id: Optional[str] = None) -> Session:
    ts = _now()
    return Session(session_id=session_id, user_id=user_id, created_at=ts, updated_at=ts)
