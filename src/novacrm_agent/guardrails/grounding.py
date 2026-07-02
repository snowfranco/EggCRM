"""Grounding check (P4-D6) — is a RAG-delegated answer supported by the retrieved passages?

This closes the grounding item deferred since Project 3, now that there's a real retrieval system
to ground against. It is used two ways (D6 "both defenses"):
  - EVAL dimension (primary): score grounding over known cases (`eval/grounding_eval.py`).
  - RUNTIME gate (detect + annotate, NOT block): the coordinator calls `check_grounding` on
    RAG-delegated answers and, if support is weak, FLAGS it in the trace + optionally appends a
    soft verification hedge — it never silently rewrites a correct answer (human-chosen posture,
    2026-07-01: measure the flag rate before considering a hard gate).

The check is an LLM judge (the Groq Scout guard model, same as P3's guardrails) rather than lexical
overlap, because "supported by" is a semantic relation — a paraphrase of a retrieved fact is
grounded, a plausible-sounding fact absent from the passages is not. An HONEST DECLINE ("the docs
don't cover that") is treated as grounded: refusing to answer beyond the passages IS the grounded
behavior, so declines never get flagged.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from ..llm import LLMClient

# Score 1-5; below this the answer is treated as insufficiently grounded (flagged at runtime).
GROUNDED_THRESHOLD = 4

_SYSTEM = """You are a grounding judge for a documentation support agent. You are given the SOURCE \
PASSAGES the agent retrieved and the agent's ANSWER. Decide whether every factual claim in the \
answer (prices, tiers, limits, steps, availability, error codes) is SUPPORTED BY the passages.

Rules:
- Supported = stated in, or a faithful paraphrase/derivation of, the passages. Not supported = a \
concrete fact that does not appear in the passages (even if it sounds plausible).
- An honest "the documentation doesn't cover that" / a refusal to answer beyond the passages counts \
as GROUNDED (score 5) — declining is the grounded behavior.
- Generic conversational text (greetings, offers to help) is neutral; judge only factual claims.

Respond with ONLY a JSON object, no other text:
{"grounded": <true|false>, "score": <1-5>, "reason": "<one sentence: name any unsupported claim>"}
score 5 = fully supported (or an honest decline); 3 = mostly, one soft/unclear claim; 1 = contains \
a concrete claim absent from the passages."""


@dataclass
class GroundingResult:
    checked: bool          # False when there were no passages / no answer to check
    grounded: bool
    score: int             # 1-5 (0 when not checked)
    reason: str

    @property
    def flagged(self) -> bool:
        """Runtime flag: checked, and support fell below the threshold."""
        return self.checked and self.score < GROUNDED_THRESHOLD


def _passages_block(chunks: list[dict]) -> str:
    blocks = []
    for c in chunks:
        tag = f"[{c.get('source', '?')} › {c.get('section', '?')}]"
        blocks.append(f"{tag}\n{c.get('text', '')}")
    return "\n\n".join(blocks)


def check_grounding(
    answer: str,
    chunks: list[dict],
    llm: Optional[LLMClient] = None,
) -> GroundingResult:
    """LLM-judge whether `answer` is supported by the retrieved `chunks` (each {source,section,text}).

    Returns checked=False (grounded=True, score=0) when there's nothing to check (no passages or no
    answer) — a turn that didn't retrieve isn't an ungrounded turn. On judge error, fail OPEN
    (grounded=True, checked=False) so the detect-annotate gate never blocks on infrastructure noise.
    """
    if not answer.strip() or not chunks:
        return GroundingResult(checked=False, grounded=True, score=0, reason="nothing to check")
    client = llm or LLMClient()
    user = f"SOURCE PASSAGES:\n{_passages_block(chunks)}\n\nANSWER:\n{answer}"
    msgs = [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}]
    try:
        res = client.chat(msgs, temperature=0.0, max_tokens=200)
        raw = (res.message.content or "").strip()
        obj = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
        score = int(obj["score"])
        return GroundingResult(checked=True, grounded=bool(obj.get("grounded", score >= GROUNDED_THRESHOLD)),
                               score=score, reason=str(obj.get("reason", ""))[:200])
    except Exception as exc:  # judge/parse failure → fail open (never block on noise)
        return GroundingResult(checked=False, grounded=True, score=0,
                               reason=f"grounding_judge_error: {type(exc).__name__}")


# Soft hedge appended (NOT a rewrite) when a RAG answer is flagged as weakly grounded.
HEDGE_NOTE = ("I want to make sure this is accurate against our current documentation — if anything "
              "looks off, I can connect you with a specialist to confirm.")
