"""create_support_ticket — creates a ticket and returns its id.

Mock implementation: generates a ticket id and echoes the structured ticket. The id is a
short uuid suffix so concurrent calls don't collide. Priority is validated against the
rubric in the system prompt (critical/high/medium/low).
"""

from __future__ import annotations

import uuid
from typing import Any

VALID_PRIORITIES = ("low", "medium", "high", "critical")


def create_support_ticket(customer_id: str, summary: str, priority: str) -> dict[str, Any]:
    """Create a support ticket. priority must be one of low/medium/high/critical."""
    priority = (priority or "").strip().lower()
    if priority not in VALID_PRIORITIES:
        return {"created": False,
                "error": f"invalid priority {priority!r}; must be one of {VALID_PRIORITIES}"}
    if not summary or not summary.strip():
        return {"created": False, "error": "summary is required"}

    ticket_id = f"TICK-{uuid.uuid4().hex[:6].upper()}"
    return {
        "created": True,
        "ticket_id": ticket_id,
        "customer_id": customer_id,
        "summary": summary.strip(),
        "priority": priority,
        "status": "open",
    }
