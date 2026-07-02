"""Tool-dispatch gates (Phase 4) — the code-level safety nets behind the prompt.

- ticket_proposed: the confirmation gate's check. Looks for the AGENT's actual proposal —
  an assistant-role turn that floats a ticket (summary/priority/"shall I create") — NOT any
  mention of the word "ticket" (so a user's "I don't need a ticket" can't satisfy it).
- is_cross_customer: identity check — refuse get_account_info for a customer other than the
  session's authenticated user (mock-level impersonation guard).
- served_customer_ids: who this conversation legitimately serves (for the output guard's
  cross-customer check) — the session user plus every account looked up across the WHOLE
  session (not just this turn), so a later turn's reply mentioning the customer's own email
  isn't flagged as foreign.
"""

from __future__ import annotations

import json
from typing import Optional

from ..session import Session

_PROPOSAL_MARKERS = (
    "shall i", "should i", "proceed with creating", "go ahead and create",
    "create this", "creating this", "create the ticket", "create a ticket",
    "i'll create", "like me to create", "want me to create",
    "summary", "priority", "proposed ticket",
)


def ticket_proposed(session: Optional[Session]) -> bool:
    """True if a prior ASSISTANT turn proposed a ticket (confirmation precondition)."""
    if session is None:
        return False
    for turn in session.turns:
        if turn.role != "assistant":
            continue
        c = (turn.content or "").lower()
        if "ticket" in c and any(m in c for m in _PROPOSAL_MARKERS):
            return True
    return False


def is_cross_customer(session: Optional[Session], requested_id: str) -> bool:
    """True if the request targets a different customer than the session's known user."""
    if session is None or not session.user_id:
        return False
    req = (requested_id or "").strip().upper()
    return bool(req) and req != session.user_id.strip().upper()


def _account_id(name: str, output) -> Optional[str]:
    if name != "get_account_info":
        return None
    out = output
    if isinstance(out, str):
        try:
            out = json.loads(out)
        except (json.JSONDecodeError, TypeError):
            return None
    if isinstance(out, dict) and out.get("found"):
        cid = str(out.get("customer_id", "")).strip().upper()
        return cid or None
    return None


def served_customer_ids(session: Optional[Session], tool_calls: Optional[list] = None) -> set:
    """Customers this conversation legitimately serves: the session user + every account
    successfully looked up across the whole session (prior turns) and this turn. With no
    session, returns empty (a stateless request serves no one → any account email is foreign)."""
    ids = set()
    if session is None:
        return ids
    if session.user_id:
        ids.add(session.user_id.strip().upper())
    for turn in session.turns:
        for ti in (turn.tool_interactions or []):
            cid = _account_id(ti.tool_name, ti.tool_output)
            if cid:
                ids.add(cid)
    for tc in (tool_calls or []):
        cid = _account_id(tc.get("name"), tc.get("output"))
        if cid:
            ids.add(cid)
    return ids
