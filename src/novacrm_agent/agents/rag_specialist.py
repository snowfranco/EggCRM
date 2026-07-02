"""ADK adapter for the hand-built RAG agent (Project 4, Phase 2).

P4-D5 + P4-D7 + this session's sign-off: the RAG specialist stays the *hand-built* `RAGAgent`
from Phase 1 (its own ReAct loop + retrieval tools, framework-free). We do NOT re-express it as
an ADK-native LlmAgent — that would invalidate the Phase-1 baseline, which measured this exact
loop. Instead we wrap it in the thinnest possible ADK `BaseAgent` so the Nova coordinator can
delegate to it through an `AgentTool` (genuine agent-to-agent delegation, not a function call).

The adapter's only job: read the delegated query from the invocation context, run the hand-built
`RAGAgent`, and yield its grounded answer as a single ADK `Event`. All retrieval, grounding, and
the honest-decline behavior live inside `RAGAgent` — unchanged from Phase 1.
"""

from __future__ import annotations

from typing import AsyncGenerator, Optional

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types

from .rag_agent import RAGAgent

RAG_SPECIALIST_NAME = "nova_docs"

# Description the coordinator's LLM sees when deciding whether to delegate here. Kept explicit
# about scope so routing lands product/API/troubleshooting questions on the docs specialist.
RAG_SPECIALIST_DESCRIPTION = (
    "NovaDocs — the EggCRM documentation specialist. Delegate here for any product, feature, "
    "how-to, pricing, plan/tier, API, or troubleshooting question that should be answered from "
    "the product documentation. Returns a grounded answer (or an honest 'not documented')."
)


class RagSpecialistAgent(BaseAgent):
    """Thin ADK BaseAgent wrapper around the hand-built RAGAgent (delegation target)."""

    # ADK agents are pydantic models; declare the injected agent as an extra field.
    model_config = {"arbitrary_types_allowed": True}
    rag: RAGAgent = None  # type: ignore[assignment]

    def __init__(self, rag: Optional[RAGAgent] = None, sink: Optional[dict] = None, **kwargs):
        super().__init__(
            name=RAG_SPECIALIST_NAME,
            description=RAG_SPECIALIST_DESCRIPTION,
            **kwargs,
        )
        # set after super().__init__ so pydantic doesn't reject the non-model types at construction.
        object.__setattr__(self, "rag", rag or RAGAgent())
        # AgentTool runs this agent in a SEPARATE inner Runner, so its Event.custom_metadata never
        # reaches the parent coordinator's event stream. `sink` is a caller-owned dict the
        # coordinator reads after the turn to recover retrieval provenance (for the grounding check).
        object.__setattr__(self, "sink", sink if sink is not None else {})

    @staticmethod
    def _extract_query(ctx: InvocationContext) -> str:
        """The delegated question arrives as the user content of this sub-invocation."""
        content = ctx.user_content
        if content and content.parts:
            texts = [p.text for p in content.parts if getattr(p, "text", None)]
            if texts:
                return "\n".join(texts).strip()
        return ""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        query = self._extract_query(ctx)
        if not query:
            yield Event(
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text="No question was provided to the documentation specialist.")],
                ),
            )
            return

        # Hand-built RAGAgent owns retrieval + grounding + honest decline (Phase 1, unchanged).
        result = self.rag.run(query)

        # Surface retrieval provenance for the coordinator's output-grounding check downstream —
        # both on the event (for a same-runner reader) and in the out-of-band sink (for AgentTool).
        # `rag_chunks` carries the retrieved passage TEXTS (deduped) so the P4-D6 grounding check
        # can verify the answer is supported by them — filenames alone aren't enough to ground.
        sources = sorted(result.retrieved_sources())
        seen, chunks = set(), []
        for h in result.retrievals:
            key = (h["metadata"]["source"], h["metadata"]["section"])
            if key in seen:
                continue
            seen.add(key)
            chunks.append({"source": h["metadata"]["source"], "section": h["metadata"]["section"],
                           "text": h["text"]})
        self.sink.clear()
        self.sink.update({"rag_sources": sources, "rag_top_score": result.top_score(),
                          "rag_iterations": result.iterations, "rag_query": query,
                          "rag_chunks": chunks})
        yield Event(
            author=self.name,
            content=types.Content(role="model", parts=[types.Part(text=result.answer)]),
            custom_metadata={
                "rag_sources": sources,
                "rag_top_score": result.top_score(),
                "rag_iterations": result.iterations,
            },
        )
