"""Input guardrail pipeline (Phase 4) — runs before context assembly.

Gated order (PII -> injection -> topic): PII first so sensitive ids never reach the model or
the trace even if a later layer escalates. Returns a result the orchestrator acts on: blocked
turns short-circuit with a safe message; allowed turns proceed on the redacted text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from . import injection_guard, pii_guard, topic_guard

_INJECTION_REFUSAL = (
    "I can't help with that request. I can assist with your EggCRM account, billing, "
    "features, integrations, and support — what can I help you with?"
)


@dataclass
class InputGuardResult:
    allowed: bool
    redacted_input: str
    reason: str
    blocked_by: Optional[str] = None      # "injection" | "topic" | None
    safe_message: Optional[str] = None    # what to tell the user when blocked
    redactions: list[str] = field(default_factory=list)
    security_note: Optional[str] = None   # appended when PII was redacted


def screen_input(text: str, llm=None) -> InputGuardResult:
    # 1) PII — redact and continue (never block on PII per policy)
    redacted, redactions = pii_guard.redact(text)
    security_note = pii_guard.SECURITY_NOTE if redactions else None

    # 2) injection — three-state regex, LLM only on uncertain
    verdict, reason = injection_guard.check(redacted, llm=llm)
    if verdict is injection_guard.Verdict.BLOCK:
        return InputGuardResult(False, redacted, reason, blocked_by="injection",
                                safe_message=_INJECTION_REFUSAL, redactions=redactions,
                                security_note=security_note)

    # 3) topic boundary
    in_scope, category, t_reason = topic_guard.check(redacted, llm=llm)
    if not in_scope:
        return InputGuardResult(False, redacted, f"{category}: {t_reason}", blocked_by="topic",
                                safe_message=topic_guard.DECLINE_MESSAGE, redactions=redactions,
                                security_note=security_note)

    return InputGuardResult(True, redacted, "passed", redactions=redactions,
                            security_note=security_note)
