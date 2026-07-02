"""Memory extraction (Phase 3) — turn a finished conversation into durable memories.

Runs at the END of a session: renders the transcript, asks the model (forced to call
record_memories) which facts are worth remembering per the D5 policy, and returns a
validated ExtractionResult. Empty results are normal and expected (see prompt Example 2).
Structured output via forced tool-call — the same pattern Project 1 landed on.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from ..llm import LLMClient
from ..session import Session
from .schemas import ExtractionResult, MemoryEntry, MemoryTopic

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "configs" / "memory_extraction_prompt.md"
_COMMENT = re.compile(r"^\s*<!--.*?-->\s*", re.DOTALL)

_RECORD_TOOL = {
    "type": "function",
    "function": {
        "name": "record_memories",
        "description": "Record the durable memories extracted from the conversation (may be empty).",
        "parameters": {
            "type": "object",
            "properties": {
                "memories": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "topic": {"type": "string", "enum": [t.value for t in MemoryTopic]},
                            "fact": {"type": "string"},
                            "confidence": {"type": "number"},
                            "source_turn": {"type": "integer"},
                        },
                        "required": ["topic", "fact", "confidence", "source_turn"],
                    },
                }
            },
            "required": ["memories"],
        },
    },
}


def _load_prompt(path: Path = _PROMPT_PATH) -> str:
    return _COMMENT.sub("", path.read_text(encoding="utf-8")).strip()


def render_transcript(session: Session) -> str:
    """Number every message so source_turn is meaningful; note tool actions briefly."""
    lines = []
    for t in session.turns:
        speaker = "customer" if t.role == "user" else "agent"
        line = f"{t.turn_number}. {speaker}: {t.content}"
        if t.tool_interactions:
            actions = ", ".join(ti.tool_name for ti in t.tool_interactions)
            line += f"  (actions: {actions})"
        lines.append(line)
    return "\n".join(lines)


def extract(session: Session, llm: Optional[LLMClient] = None, prompt: Optional[str] = None) -> ExtractionResult:
    llm = llm or LLMClient()
    prompt = prompt or _load_prompt()
    transcript = render_transcript(session)

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Extract memories from this conversation:\n\n{transcript}"},
    ]
    result = llm.chat(
        messages,
        tools=[_RECORD_TOOL],
        tool_choice={"type": "function", "function": {"name": "record_memories"}},
        temperature=0.0,
    )
    tool_calls = getattr(result.message, "tool_calls", None)
    if not tool_calls:
        return ExtractionResult(memories=[])
    try:
        args = json.loads(tool_calls[0].function.arguments or "{}")
        return ExtractionResult(memories=[MemoryEntry(**m) for m in args.get("memories", [])])
    except Exception:
        # defensive: malformed structured output → no memories rather than a crash
        return ExtractionResult(memories=[])
