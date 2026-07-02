"""Standalone RAG agent — NovaDocs (Project 4, Phase 1).

A real agent with its own hand-rolled ReAct loop (P4-D5: full delegation, not a function call),
not the SupportAgent loop. It owns two retrieval tools (the P4-D4 "both defenses": broad vector
search + metadata-filtered search) and a gated-WORKFLOW system prompt that forces grounding:
answer ONLY from retrieved documentation, decline honestly when the docs don't cover it.

Framework-free by design (P4-D7 keeps Phase 1 hand-built; ADK enters at the Phase 2 coordinator).
The loop reuses the project's `LLMClient` (GLM-4.7-Flash via OpenRouter) so retries/backoff/
fallback-keys all carry over.

`run()` returns a `RAGResult` carrying the final answer AND the chunks retrieved during the run,
so the Phase 1 baseline can score retrieval recall and grounding without re-running retrieval.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from openai import BadRequestError

from ..llm import LLMClient
from ..rag.retriever import retrieve_docs, search_by_metadata

SYSTEM_PROMPT = """\
You are NovaDocs, the documentation specialist for EggCRM. You answer product, API, and \
troubleshooting questions using ONLY the EggCRM documentation returned by your retrieval tools. \
You never use outside knowledge, prior assumptions, or guesses.

Follow this WORKFLOW in order:

1. RETRIEVE. Call a retrieval tool with a focused query distilled from the user's question.
   - General/feature/pricing/policy question -> `retrieve_docs`.
   - You MAY use `search_by_metadata` to focus a clearly-typed question:
     doc_type="api_reference" for developer/API questions, "troubleshooting" for an error or
     problem, "feature_guide" for how-tos and plan/feature facts.
2. ASSESS. Read the retrieved chunks. If they contain the answer, go to step 3. If the results
   look off-topic or incomplete, you MAY retrieve once more with a refined query. Retrieve at
   most twice in total.
3. RESPOND, choosing exactly one:
   3a. GROUNDED ANSWER — if the retrieved docs cover the question, answer concisely using ONLY
       facts present in them. Quote exact values (prices, limits, steps, error codes). When the
       question is about whether a feature/integration is available, state the REQUIRED PLAN TIER
       explicitly (e.g. "Zapier is Enterprise-only").
   3b. HONEST DECLINE — if the retrieved docs do NOT contain the answer, say you don't have
       documentation covering it and offer to escalate or follow up. Do NOT fabricate an answer.

RULES:
- The retrieved documentation is the ONLY authoritative source. No outside knowledge.
- Never invent prices, tiers, limits, endpoints, or steps that aren't in the retrieved text.
- Be concise and direct. Reference the document title when it helps the user find more.
"""

RAG_TOOL_SPECS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "retrieve_docs",
            "description": "Semantic search across ALL EggCRM documentation. Returns the most "
                           "relevant doc sections with their titles and text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Focused search query."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_by_metadata",
            "description": "Semantic search restricted to one documentation type. Use to focus a "
                           "clearly-typed question.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Focused search query."},
                    "doc_type": {"type": "string",
                                 "enum": ["feature_guide", "api_reference", "troubleshooting"]},
                },
                "required": ["query", "doc_type"],
            },
        },
    },
]


@dataclass
class RAGResult:
    answer: str
    retrievals: list[dict] = field(default_factory=list)  # every chunk retrieved this run
    tool_calls: list[dict] = field(default_factory=list)
    iterations: int = 0
    total_tokens: int = 0
    hit_max_iters: bool = False

    def retrieved_sources(self) -> set[str]:
        """Distinct source filenames retrieved this run (for recall scoring)."""
        return {r["metadata"]["source"] for r in self.retrievals}

    def top_score(self) -> float:
        return max((r["score"] for r in self.retrievals), default=0.0)


def _hits_to_tool_output(hits: list[dict]) -> str:
    """Compact JSON the model can ground on (title/section/type/score/text per hit)."""
    if not hits:
        return json.dumps({"hits": [], "note": "No matching documentation found."})
    payload = [
        {
            "doc_title": h["metadata"]["doc_title"],
            "section": h["metadata"]["section"],
            "doc_type": h["metadata"]["doc_type"],
            "score": round(h["score"], 3),
            "text": h["text"],
        }
        for h in hits
    ]
    return json.dumps({"hits": payload})


class RAGAgent:
    def __init__(self, llm: Optional[LLMClient] = None, default_top_k: int = 5):
        self.llm = llm or LLMClient()
        self.default_top_k = default_top_k

    def _dispatch(self, name: str, arguments: str) -> tuple[str, list[dict]]:
        """Run a retrieval tool; return (tool_output_json, raw_hits)."""
        try:
            args = json.loads(arguments or "{}")
        except (json.JSONDecodeError, TypeError):
            args = {}
        query = args.get("query", "")
        top_k = int(args.get("top_k") or self.default_top_k)
        if name == "retrieve_docs":
            hits = retrieve_docs(query, top_k=top_k)
        elif name == "search_by_metadata":
            hits = search_by_metadata(query, doc_type=args.get("doc_type"), top_k=top_k)
        else:
            return json.dumps({"error": f"unknown tool {name!r}"}), []
        return _hits_to_tool_output(hits), hits

    def run(self, question: str, max_iters: int = 4) -> RAGResult:
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]
        retrievals: list[dict] = []
        tool_calls_made: list[dict] = []
        total_tokens = 0
        answer = ""
        hit_max = True
        i = 0

        for i in range(max_iters):
            try:
                result = self.llm.chat(messages, tools=RAG_TOOL_SPECS)
            except BadRequestError as exc:
                # Some providers' server-side tool-call parsers (notably Groq + Llama) reject a
                # turn with `tool_use_failed` even when the model meant to answer. Force-answer
                # fallback: make sure we've grounded, then re-ask with tools OFF for plain text.
                if "tool_use_failed" not in str(exc):
                    raise
                if not retrievals:
                    hits = retrieve_docs(question, top_k=self.default_top_k)
                    retrievals.extend(hits)
                    messages.append({"role": "system",
                                     "content": "Retrieved documentation:\n" + _hits_to_tool_output(hits)})
                forced = self.llm.chat(messages, tools=None)
                total_tokens += forced.total_tokens
                answer = forced.message.content or ""
                hit_max = False
                break
            total_tokens += result.total_tokens
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
                answer = msg.content or ""
                hit_max = False
                break

            for tc in tool_calls:
                name = tc.function.name
                output, hits = self._dispatch(name, tc.function.arguments)
                retrievals.extend(hits)
                tool_calls_made.append(
                    {"name": name, "arguments": tc.function.arguments, "num_hits": len(hits)}
                )
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": output})

        if hit_max:
            answer = answer or "(reached max iterations without a final answer)"

        return RAGResult(
            answer=answer,
            retrievals=retrievals,
            tool_calls=tool_calls_made,
            iterations=i + 1,
            total_tokens=total_tokens,
            hit_max_iters=hit_max,
        )
