"""Nova coordinator — the multi-agent router (Project 4, Phase 2).

This is where ADK enters the project (P4-D7): Nova becomes an ADK `LlmAgent` that routes each
request by intent and delegates. Per this session's sign-off:

- **ADK is scoped to routing/delegation only.** The proven P3 guardrails + memory stay hand-built
  and *wrap* this coordinator (input screen before, output guard + memory extraction after) —
  they are not ported into ADK callbacks. See `NovaCoordinator.run`.
- **The RAG specialist stays hand-built** (`RagSpecialistAgent` wrapping the Phase-1 `RAGAgent`),
  exposed to the coordinator through an ADK `AgentTool` — genuine delegation (P4-D5), and the
  Phase-1 baseline stays valid because the underlying loop is unchanged.
- **Account/ticketing/escalation are ADK `FunctionTool`s** over the existing P3 callables, and the
  two P3 action gates (confirm-before-create, cross-customer identity) move into those wrappers.

The model is ADK's `LiteLlm` adapter pointed at GLM-4.7-Flash via OpenRouter (P4-D7's accepted
LiteLLM reintroduction). `build_litellm` centralizes provider wiring so the baseline can swap to
the Groq Scout stopgap while OpenRouter is out of credits.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Optional

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from google.adk.tools.agent_tool import AgentTool
from google.genai import types

from .. import config
from ..guardrails import action_gates, escalation, output_guard
from ..guardrails.grounding import HEDGE_NOTE, check_grounding
from ..guardrails.input_pipeline import screen_input
from ..llm import LLMClient
from ..memory import extractor, retriever, store
from ..memory.schemas import ExtractionResult
from ..session import Session, ToolInteraction
# Aliased so the public ADK tool names below (which ADK derives from the wrapper __name__) read as
# get_account_info / create_support_ticket / escalate_to_team, not internal method names.
from ..tools.account import get_account_info as _account_lookup
from ..tools.escalation import escalate_to_team as _escalate
from ..tools.ticketing import create_support_ticket as _create_ticket
from .rag_agent import RAGAgent
from .rag_specialist import RagSpecialistAgent

APP_NAME = "novacrm"
COORDINATOR_NAME = "nova"

COORDINATOR_INSTRUCTION = """\
You are Nova, EggCRM's customer support coordinator. You do not answer product questions from \
your own knowledge — you route each request to the right specialist or tool and compose the reply.

Follow this WORKFLOW in order; earlier steps gate later ones.

1. CHECK ESCALATION FIRST (mandatory gate — before anything else). If the request matches an
   ESCALATION RULE below, call `escalate_to_team` with the MAPPED team immediately, then tell the
   customer you are connecting them. Do NOT try to resolve it yourself, recite policy, or propose a
   support ticket instead of escalating.
   ESCALATION RULES (scenario -> team):
   - Refund request (any mention of a refund) -> billing. A support agent CANNOT approve refunds.
   - Account cancellation ("cancel my account") -> retention.
   - Legal / compliance / data-protection request (GDPR, "delete my data", data processing) -> compliance.
   - Customer is abusive or threatens legal action ("sue", "lawyer") -> supervisor.
   - Request to change payment method / update billing details (e.g. a new card) -> billing.
   - SLA credit request -> escalate to billing AND propose a support ticket.
   After escalating, say: "I'm connecting you with our <team> team, who can help with this directly.
   They'll have the full context of our conversation."

2. OTHERWISE, CLASSIFY the request and act:
   - TIER-DEPENDENT question — a product question about what THIS customer's OWN plan can do,
     access, or is limited to, where the plan/tier is NOT named in the question (e.g. "what
     integrations does MY plan support?", "can I use Zapier on my plan?", "what's MY rate limit?",
     "does my plan include X?"). For these you MUST, IN THIS ORDER: (a) call `get_account_info`
     FIRST to establish the customer's plan/tier; (b) THEN delegate to `nova_docs` for the
     feature's tier requirements; (c) THEN answer for THEIR SPECIFIC tier — say whether it is
     available ON THEIR PLAN, and if not, name the tier they would need. NEVER answer a "my plan"
     question from the docs alone — a generic doc answer can be WRONG for their tier.
     (If no customer_id is available at all, then ask for it — but only for genuine "my plan"
     questions, never for the tier-named questions below.)
   - GENERAL PRODUCT / DOCUMENTATION question (NOT tied to this customer's own plan) -> delegate
     STRAIGHT to `nova_docs`; do NOT look up or ask for the account. This INCLUDES questions that
     NAME a specific tier (e.g. "can I use Zapier on the Professional plan?", "is API access
     available on Starter?", "what's the Enterprise rate limit?") — the tier is already given, so
     no account lookup is needed — as well as features, how-tos, pricing, and troubleshooting.
     Treat what `nova_docs` returns as the ONLY source of product facts.
   - ACCOUNT question (this customer's own plan, billing cycle, status, or OPEN TICKETS) -> call
     `get_account_info` with their customer_id. Its result INCLUDES the customer's open tickets
     (field `open_tickets`) — read them from there; never say you cannot look up tickets. Never
     guess account details.
   - SUPPORT TICKET -> propose a summary + priority and get the customer's explicit confirmation
     FIRST. Only call `create_support_ticket` after they have confirmed in a prior turn.
3. GROUND: for anything about the product, rely ONLY on what `nova_docs` returns. If it says the
   topic is not documented, pass that honesty through — do NOT fill the gap from your own knowledge.
4. RESPOND: compose one concise, helpful reply for the customer. Quote exact values (prices,
   limits, steps) from `nova_docs`. Reference account facts only from `get_account_info`.

RULES:
- Never invent prices, tiers, limits, endpoints, or steps. Those come from `nova_docs` only.
- For ANY question about what the customer's OWN plan supports or is limited to, ALWAYS confirm
  their plan with `get_account_info` BEFORE delegating to `nova_docs`. Personalize the answer to
  their tier; never give a generic answer to a "my plan" question.
- Never promise refunds, credits, or SLA exceptions — only the mapped human team can approve those.
- Account state comes only from `get_account_info`; a customer may only see their OWN account.
- Do not create a ticket without a prior explicit customer confirmation.
"""


def build_litellm(provider: str = "openrouter") -> LiteLlm:
    """ADK model adapter. 'openrouter' = primary GLM-4.7-Flash; 'groq' = Scout stopgap.

    LiteLLM selects the provider from the model-slug prefix and reads the matching API key from
    the environment (OPENROUTER_API_KEY / GROQ_API_KEY), both loaded by `config`.
    """
    if provider == "groq":
        return LiteLlm(model=f"groq/{config.GROQ_SCOUT_MODEL}")
    # LiteLlm has no 402-rotation of its own, so point it at the ACTIVE (funded) key directly.
    return LiteLlm(
        model=f"openrouter/{config.OPENROUTER_GLM_MODEL}",
        api_key=config.OPENROUTER_ACTIVE_KEY,
    )


@dataclass
class CoordinatorResult:
    final_text: str
    route: list[str] = field(default_factory=list)      # tools/specialists invoked, in order
    tool_calls: list[dict] = field(default_factory=list)  # {name, arguments, output}
    rag_sources: list[str] = field(default_factory=list)  # provenance from nova_docs (grounding)
    blocked_by: Optional[str] = None
    iterations: int = 0           # coordinator LLM turns this run (efficiency metric)
    total_tokens: int = 0         # summed from ADK event usage_metadata
    grounding: Optional[dict] = None  # P4-D6 runtime grounding check (RAG-delegated answers only)

    def delegated_to_rag(self) -> bool:
        return "nova_docs" in self.route


class NovaCoordinator:
    """Hand-built guardrail/memory wrapper around the ADK coordinator (P4-D7 scope)."""

    def __init__(
        self,
        provider: str = "openrouter",
        rag: Optional[RAGAgent] = None,
        guard_llm: Optional[LLMClient] = None,
        guardrails: bool = True,
    ):
        self.guardrails = guardrails
        # Guardrail/memory/extractor calls reuse the hand-built LLMClient (Groq Scout guard model
        # in P3); default to it so screening doesn't depend on the ADK/LiteLLM path.
        self._guard_llm = guard_llm or LLMClient(
            model=config.GROQ_SCOUT_MODEL, base_url=config.GROQ_BASE_URL,
            api_key=config.GROQ_API_KEY,
        )
        # Per-run context the tool closures read (runs are synchronous, so no races).
        self._ctx: dict[str, Any] = {}
        # Out-of-band sink the RAG specialist writes provenance to (AgentTool hides its events).
        self._rag_sink: dict[str, Any] = {}
        self._rag_specialist = RagSpecialistAgent(rag=rag, sink=self._rag_sink)

        self._agent = LlmAgent(
            name=COORDINATOR_NAME,
            model=build_litellm(provider),
            instruction=self._instruction_provider,
            tools=[
                AgentTool(agent=self._rag_specialist),
                FunctionTool(self.get_account_info),
                FunctionTool(self.create_support_ticket),
                FunctionTool(self.escalate_to_team),
            ],
        )
        self._session_service = InMemorySessionService()
        self._runner = Runner(app_name=APP_NAME, agent=self._agent,
                              session_service=self._session_service)

    @property
    def adk_agent(self) -> LlmAgent:
        """The raw ADK coordinator agent — for `adk web`/`adk api_server` inspection.

        NOTE: driving this directly (as the ADK dev UI does) runs ONLY the ADK routing/delegation
        loop — it BYPASSES the hand-built input/output guardrails + memory that `run()` wraps around
        it (P4-D7 keeps those outside ADK). With no wrapper-populated `_ctx`, the action gates fall
        back to their session-less behavior (cross-customer check is inert; ticket creation stays
        blocked until proposed). Use the UI to inspect routing + delegation traces, not as the
        guardrailed production path — that's `NovaCoordinator.run()`.
        """
        return self._agent

    # --- dynamic instruction: inject memory + customer context per run -------
    def _instruction_provider(self, ctx: ReadonlyContext) -> str:
        parts = [COORDINATOR_INSTRUCTION]
        if self._ctx.get("customer_id"):
            parts.append(f"\nThe customer's account ID for this conversation is "
                         f"{self._ctx['customer_id']}.")
        if self._ctx.get("memory_block"):
            parts.append("\n" + self._ctx["memory_block"])
        return "\n".join(parts)

    # --- ADK FunctionTools (P3 callables + the two action gates) -------------
    # ADK derives each tool's name + description from the method __name__ + docstring, so these
    # keep the P3 tool names the model already knows. `self` is bound, so it isn't in the schema.
    def get_account_info(self, customer_id: str) -> dict:
        """Retrieve a customer's account details (plan, billing cycle, status). A customer may
        only view their OWN account."""
        if self.guardrails and action_gates.is_cross_customer(
            self._ctx.get("session"), customer_id
        ):
            return {"found": False,
                    "error": "identity_check_failed: cannot disclose another customer's account."}
        return _account_lookup(customer_id)

    def create_support_ticket(self, customer_id: str, summary: str, priority: str) -> dict:
        """Create a support ticket. Requires the customer to have confirmed a proposed
        summary + priority in a PRIOR turn."""
        if self.guardrails and not action_gates.ticket_proposed(self._ctx.get("session")):
            return {"created": False,
                    "error": "confirmation_required: propose the ticket (summary + priority) and "
                             "get the customer's explicit confirmation in a prior turn first."}
        return _create_ticket(customer_id=customer_id, summary=summary, priority=priority)

    def escalate_to_team(self, customer_id: str, team: str, reason: str) -> dict:
        """Hand the conversation to a human team when an escalation rule fires."""
        return _escalate(customer_id=customer_id, team=team, reason=reason)

    # --- the wrapped run -----------------------------------------------------
    def run(
        self,
        user_message: str,
        customer_id: Optional[str] = None,
        session: Optional[Session] = None,
        session_id: Optional[str] = None,
        user_id: str = "anonymous",
    ) -> CoordinatorResult:
        if session is not None:
            session_id = session.session_id
            user_id = session.user_id or user_id
        session_id = session_id or f"sess-{session and session.session_id or 'adhoc'}"

        # 1. INPUT GUARDRAILS (hand-built, before the coordinator) — same as P3.
        security_note: Optional[str] = None
        if self.guardrails:
            guard = screen_input(user_message, llm=self._guard_llm)
            if not guard.allowed:
                if session is not None:
                    self._record(session, user_message, guard.safe_message, [])
                return CoordinatorResult(final_text=guard.safe_message, blocked_by=guard.blocked_by)
            user_message = guard.redacted_input
            security_note = guard.security_note

        # 2. Per-run context for the tool closures + dynamic instruction.
        memory_block = ""
        if session is not None and session.user_id:
            memory_block = retriever.context_block(session.user_id) or ""
        self._ctx = {"session": session, "customer_id": customer_id, "memory_block": memory_block}

        # 3. Run the ADK coordinator (routes + delegates).
        self._rag_sink.clear()  # fresh provenance per turn
        events = self._invoke(session_id, user_id, user_message)
        final_text, tool_calls, iterations, total_tokens = self._harvest(events)
        rag_sources = list(self._rag_sink.get("rag_sources", []))

        # 4. OUTPUT GUARDRAILS (hand-built, after the coordinator) — same as P3.
        if security_note:
            final_text = f"{final_text}\n\n{security_note}".strip()
        if self.guardrails:
            self_ids = action_gates.served_customer_ids(session, tool_calls)
            og = output_guard.check(final_text, self_customer_ids=self_ids)
            if og.action != "ok":
                final_text = og.output
            if og.escalate_team:
                escalation.log_escalation(session, og.escalate_team, og.reason,
                                          trigger="output_guard_overpromise")
            for tc in tool_calls:
                out = tc["output"] if isinstance(tc["output"], dict) else {}
                if tc["name"] == "escalate_to_team" and out.get("escalated"):
                    escalation.log_escalation(session, out.get("team", "unknown"),
                                              out.get("reason", ""), trigger="agent_escalation")

        # 5. GROUNDING CHECK (P4-D6) — DETECT + ANNOTATE, never block. RAG-delegated answers only.
        # A weakly-grounded RAG answer gets a soft verification hedge appended (not a rewrite) and a
        # flag in the trace; the flag rate is the signal for whether a hard gate is ever warranted.
        grounding_info = None
        if self.guardrails and rag_sources:
            gr = check_grounding(final_text, self._rag_sink.get("rag_chunks", []),
                                 llm=self._guard_llm)
            grounding_info = {"checked": gr.checked, "grounded": gr.grounded, "score": gr.score,
                              "reason": gr.reason, "flagged": gr.flagged}
            if gr.flagged:
                final_text = f"{final_text}\n\n{HEDGE_NOTE}".strip()

        if session is not None:
            self._record(session, user_message, final_text, tool_calls)

        return CoordinatorResult(
            final_text=final_text,
            route=[tc["name"] for tc in tool_calls],
            tool_calls=tool_calls,
            rag_sources=rag_sources,
            iterations=iterations,
            total_tokens=total_tokens,
            grounding=grounding_info,
        )

    def _invoke(self, session_id: str, user_id: str, message: str) -> list:
        """Sync bridge: ensure the ADK session exists, run one turn, return its events."""
        async def _go() -> list:
            existing = await self._session_service.get_session(
                app_name=APP_NAME, user_id=user_id, session_id=session_id)
            if existing is None:
                await self._session_service.create_session(
                    app_name=APP_NAME, user_id=user_id, session_id=session_id)
            content = types.Content(role="user", parts=[types.Part(text=message)])
            collected = []
            async for ev in self._runner.run_async(
                user_id=user_id, session_id=session_id, new_message=content):
                collected.append(ev)
            return collected

        return asyncio.run(_go())

    @staticmethod
    def _harvest(events: list) -> tuple[str, list[dict], int, int]:
        """Pull final text, ordered tool/delegation calls, LLM-turn count, and token total."""
        final_text = ""
        calls: dict[str, dict] = {}          # call_id -> {name, arguments, output}
        order: list[str] = []
        iterations = 0
        total_tokens = 0
        for ev in events:
            um = getattr(ev, "usage_metadata", None)
            if um is not None:
                total_tokens += getattr(um, "total_token_count", 0) or 0
            content = getattr(ev, "content", None)
            if not content or not content.parts:
                continue
            # a coordinator LLM turn = a model-authored event that either calls a tool or answers.
            if any(getattr(p, "function_call", None) is not None
                   or (getattr(p, "text", None) and ev.is_final_response())
                   for p in content.parts):
                iterations += 1
            for part in content.parts:
                fc = getattr(part, "function_call", None)
                fr = getattr(part, "function_response", None)
                if fc is not None:
                    cid = getattr(fc, "id", None) or f"{fc.name}:{len(order)}"
                    calls[cid] = {"name": fc.name,
                                  "arguments": json.dumps(dict(fc.args or {}), default=str),
                                  "output": None}
                    order.append(cid)
                elif fr is not None:
                    cid = getattr(fr, "id", None)
                    resp = fr.response
                    if cid in calls:
                        calls[cid]["output"] = resp
                    else:
                        key = f"{fr.name}:resp:{len(order)}"
                        calls[key] = {"name": fr.name, "arguments": "{}", "output": resp}
                        order.append(key)
                elif getattr(part, "text", None) and ev.is_final_response():
                    final_text = part.text
        tool_calls = [calls[c] for c in order if c in calls]
        return final_text, tool_calls, iterations, total_tokens

    def end_session(self, session: Session) -> ExtractionResult:
        """End-of-conversation memory extraction (unchanged from P3, uses the guard LLM)."""
        result = extractor.extract(session, llm=self._guard_llm)
        if session.user_id and result.memories:
            store.update_from_extraction(session.user_id, result, session.session_id)
        return result

    @staticmethod
    def _record(session: Session, user_message: str, final_text: str, tool_calls: list[dict]) -> None:
        session.add_turn("user", user_message)
        interactions, escalated, target = [], False, None
        for tc in tool_calls:
            try:
                tool_input = json.loads(tc["arguments"] or "{}")
            except (json.JSONDecodeError, TypeError):
                tool_input = {"_raw": tc["arguments"]}
            interactions.append(ToolInteraction(
                tool_name=tc["name"], tool_input=tool_input,
                tool_output=json.dumps(tc["output"], default=str),
            ))
            out = tc["output"] if isinstance(tc["output"], dict) else {}
            if tc["name"] == "escalate_to_team" and out.get("escalated"):
                escalated, target = True, out.get("team")
        session.add_turn("assistant", final_text, tool_interactions=interactions or None,
                         escalated=escalated, escalation_target=target)
        session.save()
