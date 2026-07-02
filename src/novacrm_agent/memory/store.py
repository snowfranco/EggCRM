"""Per-user memory store (Phase 3) — JSON-per-user, with D5 consolidation.

Storage: data/memory_store/<customer_id>.json (inspectable; retrieval here is a key
lookup, so JSON beats SQLite — D5 / approved). The interface (load / consolidate / save)
is the seam to swap for SQLite later if retrieval ever needs ranking/filtering.

Consolidation (D5):
  - APPEND_DEDUP topics (issue_history): distinct events accumulate; only near-identical
    facts merge (so the same bug reported twice doesn't double up).
  - CHANGEABLE topics (everything else): last-write-wins — a newer fact on the same topic
    that overlaps an existing one replaces it (e.g. a changed comms preference).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .schemas import ExtractionResult, MemoryTopic, StoredMemory

_STORE_DIR = Path(__file__).resolve().parents[3] / "data" / "memory_store"

APPEND_DEDUP_TOPICS = {MemoryTopic.ISSUE_HISTORY}
_DEDUP_THRESHOLD = 0.7   # near-identical events merge instead of duplicating
_UPDATE_THRESHOLD = 0.5  # changeable facts on the same topic overwrite past this overlap


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _path(customer_id: str, store_dir: Path) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", customer_id)
    return store_dir / f"{safe}.json"


def load(customer_id: str, store_dir: Path = _STORE_DIR) -> list[StoredMemory]:
    path = _path(customer_id, store_dir)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [StoredMemory(**m) for m in data.get("memories", [])]


def save(customer_id: str, memories: list[StoredMemory], store_dir: Path = _STORE_DIR) -> Path:
    store_dir.mkdir(parents=True, exist_ok=True)
    path = _path(customer_id, store_dir)
    path.write_text(json.dumps(
        {"customer_id": customer_id, "memories": [m.model_dump() for m in memories]},
        indent=2), encoding="utf-8")
    return path


def consolidate(existing: list[StoredMemory], extraction: ExtractionResult,
                source_session: str, now: str | None = None) -> list[StoredMemory]:
    """Pure consolidation — returns the merged memory list (D5 rules)."""
    now = now or _now()
    result = list(existing)

    for e in extraction.memories:
        append_dedup = e.topic in APPEND_DEDUP_TOPICS
        threshold = _DEDUP_THRESHOLD if append_dedup else _UPDATE_THRESHOLD

        match_idx = None
        for i, m in enumerate(result):
            if m.topic == e.topic and _jaccard(e.fact, m.fact) >= threshold:
                match_idx = i
                break

        if match_idx is None:
            result.append(StoredMemory(
                topic=e.topic, fact=e.fact, confidence=e.confidence,
                source_session=source_session, source_turn=e.source_turn,
                first_seen=now, last_updated=now,
            ))
        else:
            prev = result[match_idx]
            # append_dedup: keep original fact text; changeable: last-write-wins (new fact)
            result[match_idx] = StoredMemory(
                topic=e.topic,
                fact=prev.fact if append_dedup else e.fact,
                confidence=max(prev.confidence, e.confidence),
                source_session=source_session, source_turn=e.source_turn,
                first_seen=prev.first_seen, last_updated=now,
            )
    return result


def update_from_extraction(customer_id: str, extraction: ExtractionResult,
                           source_session: str, store_dir: Path = _STORE_DIR) -> list[StoredMemory]:
    merged = consolidate(load(customer_id, store_dir), extraction, source_session)
    save(customer_id, merged, store_dir)
    return merged
