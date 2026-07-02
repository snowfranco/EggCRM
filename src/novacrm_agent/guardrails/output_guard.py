"""Output guardrail (Phase 5) — egress scan before delivery. The NET behind the input guard.

Checks, in order:
  1. forbidden content (system-prompt fragments / internal tool names / model+infra) -> BLOCK
  2. cross-customer data (another customer's email in the reply)                       -> BLOCK
  3. over-promising (refund/credit/SLA commitments)                                    -> BLOCK + rewrite-to-escalate
  4. PII egress (card/SSN)                                                             -> REDACT in place

Action policy (approved D-Phase5): redact PII in place; block forbidden/cross-customer with a
safe fallback; block over-promise and REWRITE to a clean escalation that does NOT reveal why it
was rewritten (the internal log captures the real reason). Forbidden-content markers are kept
distinctive (prompt fragments + underscored tool names) so legitimate how-to replies that use
"Step 1:" or "create a ticket" are not false-positived.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from . import pii_guard

_ACCOUNTS_PATH = Path(__file__).resolve().parents[3] / "data" / "accounts" / "accounts.json"

_FORBIDDEN = [
    "you are nova", "## workflow", "check escalation (mandatory", "system prompt",
    "my instructions are", "my system prompt",
    "escalate_to_team", "get_account_info", "lookup_knowledge_base", "create_support_ticket",
    # model / infra leakage
    "openrouter", "litellm", "z-ai/glm", "glm-4.7",
]

_OVERPROMISE = [
    r"refund (is |has been |was )?(approved|processed|issued)",
    r"(approved|processed|issued) your refund",
    r"i'?ve (approved|processed|issued|granted) (your )?(refund|credit)",
    r"credited your account",
    r"credit (is |has been )?(applied|issued)",
    r"i'?ll credit",
    r"i (guarantee|promise) ",
    r"we guarantee",
    r"100% uptime",
]
_OVERPROMISE_RE = [re.compile(p) for p in _OVERPROMISE]
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

SAFE_FALLBACK = ("I'm not able to share that. I can help with your EggCRM account, billing, "
                 "features, or support — what do you need?")
OVERPROMISE_REWRITE = ("Let me connect you with our {team} team, who can help with this "
                       "directly. They'll have the full context of our conversation.")


@dataclass
class OutputGuardResult:
    approved: bool
    output: str
    action: str            # "ok" | "redacted" | "blocked" | "rewritten"
    reason: str
    escalate_team: Optional[str] = None


@lru_cache(maxsize=1)
def _customer_by_email() -> dict[str, str]:
    """email (lowercased) -> customer_id (upper)."""
    data = json.loads(_ACCOUNTS_PATH.read_text(encoding="utf-8"))
    return {(a.get("contact_email") or "").lower(): cid.upper()
            for cid, a in data.items() if a.get("contact_email")}


def check(response: str, self_customer_ids: Optional[set] = None) -> OutputGuardResult:
    """Scan a response. `self_customer_ids` = the customer(s) this turn legitimately serves
    (session user + accounts looked up this turn); any OTHER customer's email is a cross-customer
    leak. With no self ids (e.g. a no-session adversarial turn), ANY account email is blocked."""
    text = response or ""
    low = text.lower()
    allowed = {c.upper() for c in (self_customer_ids or set())}

    # 1) forbidden content (prompt / tools / infra)
    for marker in _FORBIDDEN:
        if marker in low:
            return OutputGuardResult(False, SAFE_FALLBACK, "blocked", f"forbidden content: {marker!r}")

    # 2) cross-customer data — an account email belonging to a customer we are NOT serving
    by_email = _customer_by_email()
    for found in _EMAIL_RE.findall(text):
        owner = by_email.get(found.lower())
        if owner and owner not in allowed:
            return OutputGuardResult(False, SAFE_FALLBACK, "blocked", f"cross-customer data: {found}")

    # 3) over-promising — block + rewrite-to-escalate (route money promises to billing)
    for rx in _OVERPROMISE_RE:
        if rx.search(low):
            return OutputGuardResult(False, OVERPROMISE_REWRITE.format(team="billing"),
                                     "rewritten", f"over-promise: {rx.pattern[:40]}",
                                     escalate_team="billing")

    # 4) PII egress — redact in place, deliver the rest
    redacted, kinds = pii_guard.redact(text)
    if kinds:
        return OutputGuardResult(True, redacted, "redacted", f"redacted PII egress: {kinds}")

    return OutputGuardResult(True, text, "ok", "clean")
