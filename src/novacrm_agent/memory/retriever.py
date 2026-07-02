"""Memory retrieval (Phase 3) — load a user's memories and render them for context.

At session start the orchestrator injects this block as a system message ("what you
remember about this customer"), the Day 3 memories-in-system-instructions pattern. Tier/
billing are NOT here — those are read live via get_account_info (D5 non-shadow rule).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from . import store
from .schemas import StoredMemory

_STORE_DIR = store._STORE_DIR


def get_memories(customer_id: str, store_dir: Path = _STORE_DIR) -> list[StoredMemory]:
    return store.load(customer_id, store_dir)


def context_block(customer_id: str, store_dir: Path = _STORE_DIR) -> Optional[str]:
    memories = get_memories(customer_id, store_dir)
    if not memories:
        return None
    lines = [f"- [{m.topic.value}] {m.fact}" for m in memories]
    return (
        "What you remember about this customer from past conversations:\n"
        + "\n".join(lines)
        + "\n\nUse these memories actively: if the customer refers to a past issue, bug, "
          "request, or preference, recall the specifics from the list above instead of asking "
          "them to repeat or only checking tickets. For current plan/billing/storage, always "
          "check get_account_info — those are live and not in memory."
    )
