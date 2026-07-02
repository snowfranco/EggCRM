"""escalate_to_team — the structured escalation action (D4 fix #1).

This is the whole reason escalation became a tool instead of a verbal message: it makes
"the agent escalated, to team X, for reason Y" a first-class, trace-visible event the
eval harness (Phase 6 Safety pillar) can verify deterministically — rather than having to
parse it out of natural-language prose.
"""

from __future__ import annotations

from typing import Any

VALID_TEAMS = ("billing", "retention", "integrations", "compliance", "engineering", "supervisor")


def escalate_to_team(customer_id: str, team: str, reason: str) -> dict[str, Any]:
    """Hand the conversation to a human team. team must be one of the valid teams."""
    team = (team or "").strip().lower()
    if team not in VALID_TEAMS:
        return {"escalated": False,
                "error": f"invalid team {team!r}; must be one of {VALID_TEAMS}"}
    return {
        "escalated": True,
        "customer_id": customer_id,
        "team": team,
        "reason": (reason or "").strip(),
        "message": f"Connecting the customer to the {team} team.",
    }
