"""get_account_info — the account system, source of truth for plan/billing state.

Reads mock fixtures (data/accounts/accounts.json). Per D5, this is authoritative: the
agent reads it fresh rather than trusting cross-session memory for tier/billing.

NOTE (D4 open item, deferred to Phase 4): this trusts customer_id at face value — no
identity verification yet. Impersonation / wrong-customer disclosure is an input-guardrail
concern handled in Phase 4, not here.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_ACCOUNTS_PATH = Path(__file__).resolve().parents[3] / "data" / "accounts" / "accounts.json"


@lru_cache(maxsize=1)
def _accounts() -> dict[str, Any]:
    return json.loads(_ACCOUNTS_PATH.read_text(encoding="utf-8"))


def get_account_info(customer_id: str) -> dict[str, Any]:
    """Retrieve a customer's account details by customer_id."""
    cid = (customer_id or "").strip().upper()
    account = _accounts().get(cid)
    if account is None:
        return {"found": False, "customer_id": customer_id,
                "message": "No account found for that customer ID."}
    return {"found": True, **account}
