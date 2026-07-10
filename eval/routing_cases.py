"""Routing-discipline case set for the CI gate (D-CI-2 + spec §Demonstration Feature).

`routing_discipline` is the gate's differentiator: an output-only gate would pass a build
where Nova stopped verifying the account before a tier- or eligibility-dependent answer
(the P4 finding — 96% answer accuracy masking 8% process compliance). These cases assert
on the TRACE, not the prose.

Two sub-sets, combined into one metric by the gate runner:
  - TIER cases: reused verbatim from `tier_discipline.py` (evaluator unmodified) — account
    lookup must precede/accompany the `nova_docs` delegation for "my plan" questions.
  - REFUND-ELIGIBILITY cases (the demo feature): Nova must verify the customer's account via
    `get_account_info` BEFORE stating refund eligibility, because eligibility depends on the
    account (billing cycle, purchase date, plan) — even if the recited policy happens to read
    correct, answering without a prior verified lookup is a routing-discipline failure.

RT1: the account was verified earlier in the session (turn 1 asks the plan) — compliant as
     long as the lookup precedes the eligibility statement.
RT2: fresh session, eligibility asked cold — the lookup must happen in the same turn, before
     answering.

Module top level is stdlib-only so the assertion logic stays offline-testable; the tier cases
are loaded lazily because `tier_discipline` imports the ADK coordinator at module scope.
"""

from __future__ import annotations

REFUND_CASES = [
    {"id": "RT1", "tag": "routing",
     "turns": ["What plan am I on? My ID is CUST-1001.",
               "Thanks — am I still eligible for a refund on my current billing cycle?"],
     "customer": "CUST-1001"},
    {"id": "RT2", "tag": "routing",
     "turns": ["What's my refund window? I'm CUST-1002."],
     "customer": "CUST-1002"},
]


def refund_discipline_ok(route: list[str]) -> tuple[bool, str]:
    """True iff the account was verified before the eligibility statement.

    The eligibility statement is the final answer, so `get_account_info` anywhere in the
    (cross-turn, in-order) route precedes it; if docs were also consulted, the lookup must
    come first (verify, then policy) — same ordering rule as the tier seam.
    """
    if "get_account_info" not in route:
        return False, "no_account_verification"
    if "nova_docs" in route and route.index("get_account_info") > route.index("nova_docs"):
        return False, "account_after_docs"
    return True, "ok"


def load_tier_cases():
    """Deferred import: `tier_discipline` pulls in the ADK coordinator at module top, which
    offline unit tests of this module must not require."""
    from tier_discipline import CASES, _discipline_ok
    return CASES, _discipline_ok
