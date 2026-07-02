"""Grounding-check tests (P4-D6) — offline, LLM faked.

Pin the contract the runtime detect-annotate gate and the eval dimension both rely on:
- a supported answer is grounded and NOT flagged;
- an answer with an unsupported claim is flagged (score below threshold);
- nothing-to-check (no chunks / empty answer) is not a failure (checked=False, not flagged);
- a judge/parse error FAILS OPEN (never blocks on infrastructure noise).
"""

from __future__ import annotations

from types import SimpleNamespace

from novacrm_agent.guardrails.grounding import GROUNDED_THRESHOLD, check_grounding


class FakeLLM:
    def __init__(self, content=None, raise_exc=None):
        self._content, self._raise = content, raise_exc

    def chat(self, messages, **kwargs):
        if self._raise:
            raise self._raise
        return SimpleNamespace(message=SimpleNamespace(content=self._content))


CHUNKS = [{"source": "02-plans-and-pricing.md", "section": "Plans", "text": "Professional is $79."}]


def test_supported_answer_is_grounded_not_flagged():
    llm = FakeLLM('{"grounded": true, "score": 5, "reason": "matches passage"}')
    r = check_grounding("The Professional plan is $79/user/month.", CHUNKS, llm=llm)
    assert r.checked and r.grounded and r.score == 5
    assert r.flagged is False


def test_unsupported_claim_is_flagged():
    llm = FakeLLM('{"grounded": false, "score": 1, "reason": "invented $59 price"}')
    r = check_grounding("The Professional plan is $59/user/month.", CHUNKS, llm=llm)
    assert r.checked and not r.grounded
    assert r.flagged is True


def test_threshold_boundary():
    below = check_grounding("x", CHUNKS, llm=FakeLLM(f'{{"grounded": false, "score": {GROUNDED_THRESHOLD - 1}}}'))
    at = check_grounding("x", CHUNKS, llm=FakeLLM(f'{{"grounded": true, "score": {GROUNDED_THRESHOLD}}}'))
    assert below.flagged is True
    assert at.flagged is False


def test_nothing_to_check_is_not_a_failure():
    assert check_grounding("some answer", [], llm=FakeLLM("unused")).checked is False
    assert check_grounding("", CHUNKS, llm=FakeLLM("unused")).flagged is False


def test_judge_error_fails_open():
    r = check_grounding("answer", CHUNKS, llm=FakeLLM(raise_exc=RuntimeError("boom")))
    assert r.checked is False and r.grounded is True and r.flagged is False
    assert "grounding_judge_error" in r.reason


def test_prose_extraction_tolerates_surrounding_text():
    llm = FakeLLM('Sure!\n{"grounded": true, "score": 5, "reason": "ok"} hope that helps')
    r = check_grounding("The Professional plan is $79.", CHUNKS, llm=llm)
    assert r.grounded and r.score == 5
