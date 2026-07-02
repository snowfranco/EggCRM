"""Human-in-the-loop escalation protocol (Phase 5).

When the agent escalates (or the output guard blocks an over-promise), write a self-contained
case file to data/escalations/{timestamp}_{session_id}.json — full conversation + reason + team
+ customer id — so a human reviewer picks it up with complete context (the "they'll have the
full context" promise). One file per escalation (approved D-Phase5): each is an independent
case, grep-friendly, no write-contention.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_ESC_DIR = Path(__file__).resolve().parents[3] / "data" / "escalations"


def log_escalation(session, team: str, reason: str, trigger: str = "agent_escalation",
                   extra: Optional[dict] = None) -> Path:
    _ESC_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc)
    sid = session.session_id if session is not None else "no-session"
    record = {
        "timestamp": ts.isoformat(),
        "session_id": sid,
        "customer_id": session.user_id if session is not None else None,
        "team": team,
        "reason": reason,
        "trigger": trigger,
        "conversation": [asdict(t) for t in session.turns] if session is not None else [],
    }
    if extra:
        record.update(extra)
    path = _ESC_DIR / f"{ts.strftime('%Y%m%dT%H%M%S')}_{sid}.json"
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return path
