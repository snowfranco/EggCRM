"""PII detection & redaction (Phase 4) — deterministic, runs first in the pipeline.

Policy (D-Phase4, approved): redact-and-continue for card/SSN (so a real billing issue isn't
walled), allow phone/email (operationally needed). Redacting at the INPUT boundary means
sensitive ids never reach the model, tool calls, traces (eval/logs/), or memory. Card matches
are Luhn-validated to avoid redacting ordinary long numbers (false-positive guard, PII04-06).
"""

from __future__ import annotations

import re

# candidate card: 13–16 digits possibly split by spaces/dashes
_CARD_CANDIDATE = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def _luhn_ok(digits: str) -> bool:
    total, parity = 0, len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def redact(text: str) -> tuple[str, list[str]]:
    """Return (redacted_text, kinds_redacted). Cards/SSNs scrubbed; phone/email left intact."""
    redactions: list[str] = []

    def _card_sub(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group())
        if 13 <= len(digits) <= 16 and _luhn_ok(digits):
            redactions.append("credit_card")
            return "[REDACTED_CARD]"
        return m.group()

    text = _CARD_CANDIDATE.sub(_card_sub, text)

    def _ssn_sub(m: re.Match) -> str:
        redactions.append("ssn")
        return "[REDACTED_SSN]"

    text = _SSN.sub(_ssn_sub, text)
    return text, redactions


SECURITY_NOTE = (
    "For your security, please don't share full card or SSN numbers in chat — "
    "our billing team handles payment details securely."
)
