"""The orchestration loop — hand-built ReAct (Think -> Act -> Observe), no framework.

This is the core learning artifact of Project 3: the loop a framework would normally hide.
Each turn:
  1. context_assembly  — system prompt + customer hint + user message
  2. llm_call          — model decides: answer, or call tools
  3. tool_dispatch     — run each tool call, feed observations back
  4. repeat until the model returns a final answer (or max_iters guard trips — safety net)

Phase 1 is single-turn (no memory). Session memory (Phase 2) and guardrail layers
(Phase 4-5) wrap this loop later. Every step is traced (D1).
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .guardrails import action_gates, escalation, output_guard
from .guardrails.input_pipeline import screen_input
from .llm import LLMClient
from .memory import extractor, retriever, store
from .memory.schemas import ExtractionResult
from .session import Session, ToolInteraction
from .tools.registry import TOOL_SPECS, dispatch
from .tracing import Tracer

_DEFAULT_PROMPT = Path(__file__).resolve().parents[2] / "configs" / "system_prompt.md"
_COMMENT = re.compile(r"^\s*<!--.*?-->\s*", re.DOTALL)


def _load_system_prompt(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return _COMMENT.sub("", text).strip()


@dataclass
class TurnResult:
    final_text: str
    messages: list[dict]
    tool_calls: list[dict] = field(default_factory=list)
    iterations: int = 0
    tracer: Optional[Tracer] = None
    hit_max_iters: bool = False
    blocked_by: Optional[str] = None  # "injection" | "topic" when an input guard short-circuited

    def tool_names(self) -> list[str]:
        return [tc["name"] for tc in self.tool_calls]


class SupportAgent:
    def __init__(self, llm: Optional[LLMClient] = None, system_prompt_path: Path = _DEFAULT_PROMPT,
                 guardrails: bool = True):
        self.llm = llm or LLMClient()
        self.system_prompt = _load_system_prompt(system_prompt_path)
        # guardrails=False is the "before" mode for the adversarial baseline.
        self.guardrails = guardrails

    def run(
        self,
        user_message: str,
        customer_id: Optional[str] = None,
        session: Optional[Session] = None,
        session_id: Optional[str] = None,
        user_id: str = "anonymous",
        history_window: int = 20,
        max_iters: int = 10,  # room for multi-part queries to converge (raised from 6 after G30)
    ) -> TurnResult:
        # A session, when provided, supplies identity + prior-turn history and records
        # this turn back. Without one, run() is single-turn (Phase 1 behavior).
        if session is not None:
            session_id = session.session_id
            user_id = session.user_id or user_id
        session_id = session_id or f"sess-{uuid.uuid4().hex[:8]}"
        tracer = Tracer(session_id=session_id, user_id=user_id)

        security_note: Optional[str] = None
        if self.guardrails:
            with tracer.span("input_guard", "screen input (pii/injection/topic)") as gs:
                guard = screen_input(user_message, llm=self.llm)
                gs.outcome = "blocked" if not guard.allowed else "ok"
                gs.extra["blocked_by"] = guard.blocked_by
                if guard.redactions:
                    gs.extra["redactions"] = guard.redactions
            if not guard.allowed:
                if session is not None:
                    self._record(session, user_message, guard.safe_message, [])
                return TurnResult(final_text=guard.safe_message, messages=[], tool_calls=[],
                                  iterations=0, tracer=tracer, hit_max_iters=False,
                                  blocked_by=guard.blocked_by)
            user_message = guard.redacted_input  # downstream sees the redacted text only
            security_note = guard.security_note

        with tracer.span("context_assembly", "build system + history + user context") as s:
            messages: list[dict] = [{"role": "system", "content": self.system_prompt}]
            if session is not None and session.user_id:
                mem_block = retriever.context_block(session.user_id)
                if mem_block:
                    messages.append({"role": "system", "content": mem_block})
                    s.extra["memories_injected"] = True
            if session is not None:
                history = session.context_messages(window=history_window)
                messages.extend(history)
                s.extra["history_turns"] = len(history)
            if customer_id:
                messages.append({"role": "system",
                                 "content": f"The customer's account ID for this conversation is {customer_id}."})
            messages.append({"role": "user", "content": user_message})

        tool_calls_made: list[dict] = []
        final_text = ""
        hit_max = True

        for i in range(max_iters):
            with tracer.span("llm_call", f"iteration {i}") as s:
                result = self.llm.chat(messages, tools=TOOL_SPECS)
                s.token_count = result.total_tokens
                s.outcome = result.finish_reason or "ok"

            msg = result.message
            assistant_msg: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                assistant_msg["tool_calls"] = [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in tool_calls
                ]
            messages.append(assistant_msg)

            if not tool_calls:
                final_text = msg.content or ""
                hit_max = False
                break

            for tc in tool_calls:
                name = tc.function.name
                with tracer.span("tool_dispatch", f"{name}({tc.function.arguments})") as s:
                    output = self._dispatch(name, tc.function.arguments, session)
                    if isinstance(output, dict) and output.get("error"):
                        s.outcome = "gated"
                tool_calls_made.append({"name": name, "arguments": tc.function.arguments, "output": output})
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                 "content": json.dumps(output, default=str)})

        if hit_max:
            final_text = final_text or "(reached max iterations without a final answer)"

        if security_note:
            final_text = f"{final_text}\n\n{security_note}".strip()

        if self.guardrails:
            # "self" customers = who this conversation serves (session user + accounts looked up
            # anywhere in the session). A stateless no-session request serves no one, so any
            # account email is treated as a cross-customer leak (exfiltration protection).
            self_ids = action_gates.served_customer_ids(session, tool_calls_made)
            with tracer.span("output_guard", "scan response before delivery") as os_span:
                og = output_guard.check(final_text, self_customer_ids=self_ids)
                os_span.outcome = og.action
                os_span.extra["action"] = og.action
            if og.action != "ok":
                final_text = og.output  # redacted / safe-fallback / rewritten
            if og.escalate_team:  # over-promise was rewritten → log the handoff
                escalation.log_escalation(session, og.escalate_team, og.reason,
                                          trigger="output_guard_overpromise")
            # HITL: log the agent's own escalations as case files
            for tc in tool_calls_made:
                out = tc["output"] if isinstance(tc["output"], dict) else {}
                if tc["name"] == "escalate_to_team" and out.get("escalated"):
                    escalation.log_escalation(session, out.get("team", "unknown"),
                                              out.get("reason", ""), trigger="agent_escalation")

        if session is not None:
            self._record(session, user_message, final_text, tool_calls_made)

        return TurnResult(
            final_text=final_text,
            messages=messages,
            tool_calls=tool_calls_made,
            iterations=i + 1,
            tracer=tracer,
            hit_max_iters=hit_max,
        )

    def _dispatch(self, name: str, arguments: str, session: Optional[Session]):
        """Dispatch a tool call, applying action gates (confirmation + identity) when guarded."""
        if not self.guardrails:
            return dispatch(name, arguments)
        try:
            args = json.loads(arguments or "{}")
        except (json.JSONDecodeError, TypeError):
            args = {}
        if name == "create_support_ticket" and not action_gates.ticket_proposed(session):
            return {"created": False,
                    "error": "confirmation_required: propose the ticket (summary + priority) and "
                             "get the customer's explicit confirmation in a prior turn before creating."}
        if name == "get_account_info" and action_gates.is_cross_customer(session, args.get("customer_id", "")):
            return {"found": False,
                    "error": "identity_check_failed: cannot disclose another customer's account information."}
        return dispatch(name, arguments)

    def end_session(self, session: Session) -> ExtractionResult:
        """Run at the end of a conversation: extract durable memories and persist them.

        Honors D5 — extraction excludes tool-authoritative state; the store consolidates.
        Returns the (possibly empty) extraction so callers/eval can inspect it.
        """
        result = extractor.extract(session, llm=self.llm)
        if session.user_id and result.memories:
            store.update_from_extraction(session.user_id, result, session.session_id)
        return result

    @staticmethod
    def _record(session: Session, user_message: str, final_text: str, tool_calls: list[dict]) -> None:
        """Persist this turn into the session (structured storage; see session.py)."""
        session.add_turn("user", user_message)

        interactions = []
        escalated, target = False, None
        for tc in tool_calls:
            try:
                tool_input = json.loads(tc["arguments"] or "{}")
            except (json.JSONDecodeError, TypeError):
                tool_input = {"_raw": tc["arguments"]}
            interactions.append(ToolInteraction(
                tool_name=tc["name"],
                tool_input=tool_input,
                tool_output=json.dumps(tc["output"], default=str),
            ))
            out = tc["output"] if isinstance(tc["output"], dict) else {}
            if tc["name"] == "escalate_to_team" and out.get("escalated"):
                escalated, target = True, out.get("team")

        session.add_turn("assistant", final_text,
                         tool_interactions=interactions or None,
                         escalated=escalated, escalation_target=target)
        session.save()
