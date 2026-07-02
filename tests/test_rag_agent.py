"""RAGAgent ReAct-loop tests (Project 4 Phase 1) — fully offline.

These pin the agent's *loop* behavior, independent of the model or the vector store:
- a tool call is dispatched, its hits accumulate into the RAGResult, and a following text
  turn ends the loop as a grounded answer;
- the `RAGResult` helpers (retrieved_sources / top_score) summarize retrieval correctly;
- the `tool_use_failed` provider quirk triggers the force-answer fallback (retrieve, then
  re-ask with tools off) instead of crashing;
- an endlessly-tool-calling model terminates at max_iters with hit_max_iters set.

The LLM and the retriever are both faked, so no network / no Chroma is touched.
"""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from openai import BadRequestError

from novacrm_agent.agents import rag_agent
from novacrm_agent.agents.rag_agent import RAGAgent, RAGResult


# --- fakes ------------------------------------------------------------------
def _tool_call(call_id: str, name: str, arguments: str):
    return SimpleNamespace(
        id=call_id, type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def _result(content: str = "", tool_calls=None, tokens: int = 100):
    msg = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(message=msg, total_tokens=tokens)


class FakeLLM:
    """Returns queued results (or raises queued exceptions) in order, per chat() call."""

    def __init__(self, script):
        self._script = list(script)
        self.calls = []  # (had_tools,) per call, so tests can assert tools were turned off

    def chat(self, messages, tools=None, **kwargs):
        self.calls.append(bool(tools))
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _hit(source: str, doc_title: str, score: float, text: str = "body"):
    return {
        "text": text,
        "score": score,
        "metadata": {"source": source, "doc_title": doc_title,
                     "section": "S", "doc_type": "feature_guide"},
    }


@pytest.fixture
def stub_retrieval(monkeypatch):
    """Make retrieve_docs / search_by_metadata return fixed hits without touching Chroma."""
    calls = {"retrieve_docs": [], "search_by_metadata": []}

    def fake_retrieve(query, top_k=5):
        calls["retrieve_docs"].append((query, top_k))
        return [_hit("02-plans-and-pricing.md", "Plans & Pricing", 0.7, "Professional is $79.")]

    def fake_meta(query, doc_type=None, top_k=5):
        calls["search_by_metadata"].append((query, doc_type, top_k))
        return [_hit("10-api-overview-and-auth.md", "API Auth", 0.8, "Bearer token.")]

    monkeypatch.setattr(rag_agent, "retrieve_docs", fake_retrieve)
    monkeypatch.setattr(rag_agent, "search_by_metadata", fake_meta)
    return calls


# --- tests ------------------------------------------------------------------
def test_tool_then_answer_grounds_and_accumulates(stub_retrieval):
    llm = FakeLLM([
        _result(tool_calls=[_tool_call("c1", "retrieve_docs", '{"query": "pro price"}')], tokens=50),
        _result(content="The Professional plan is $79/user/month.", tokens=40),
    ])
    result = RAGAgent(llm=llm).run("How much is Pro?")

    assert result.answer == "The Professional plan is $79/user/month."
    assert result.hit_max_iters is False
    assert result.iterations == 2
    assert result.total_tokens == 90
    assert result.tool_calls == [
        {"name": "retrieve_docs", "arguments": '{"query": "pro price"}', "num_hits": 1}
    ]
    assert result.retrieved_sources() == {"02-plans-and-pricing.md"}
    assert stub_retrieval["retrieve_docs"], "retrieve_docs was never dispatched"


def test_metadata_tool_routes_to_search_by_metadata(stub_retrieval):
    llm = FakeLLM([
        _result(tool_calls=[_tool_call(
            "c1", "search_by_metadata",
            '{"query": "auth", "doc_type": "api_reference"}')]),
        _result(content="Use a bearer token."),
    ])
    RAGAgent(llm=llm).run("How do I authenticate?")

    assert stub_retrieval["search_by_metadata"] == [("auth", "api_reference", 5)]
    assert not stub_retrieval["retrieve_docs"]


def test_ragresult_helpers():
    r = RAGResult(
        answer="x",
        retrievals=[_hit("a.md", "A", 0.4), _hit("b.md", "B", 0.9), _hit("a.md", "A", 0.1)],
    )
    assert r.retrieved_sources() == {"a.md", "b.md"}
    assert r.top_score() == 0.9
    # empty run: no retrievals → top_score defaults to 0.0, no crash
    assert RAGResult(answer="x").top_score() == 0.0


def test_tool_use_failed_triggers_force_answer_fallback(stub_retrieval):
    err = BadRequestError(
        "tool_use_failed", response=httpx.Response(400, request=httpx.Request("POST", "http://x")),
        body=None,
    )
    llm = FakeLLM([err, _result(content="Grounded fallback answer.", tokens=30)])
    result = RAGAgent(llm=llm).run("anything")

    assert result.answer == "Grounded fallback answer."
    assert result.hit_max_iters is False
    # fallback retrieved to ground itself, then re-asked with tools OFF
    assert stub_retrieval["retrieve_docs"], "fallback should retrieve before force-answering"
    assert llm.calls == [True, False], "second (forced) call must disable tools"


def test_non_tool_use_bad_request_propagates():
    llm = FakeLLM([BadRequestError(
        "some other 400", response=httpx.Response(400, request=httpx.Request("POST", "http://x")),
        body=None,
    )])
    with pytest.raises(BadRequestError):
        RAGAgent(llm=llm).run("anything")


def test_endless_tool_calls_hit_max_iters(stub_retrieval):
    tool_turn = _result(tool_calls=[_tool_call("c", "retrieve_docs", '{"query": "q"}')], tokens=10)
    llm = FakeLLM([tool_turn, tool_turn])  # never returns a plain-text answer
    result = RAGAgent(llm=llm).run("loops forever", max_iters=2)

    assert result.hit_max_iters is True
    assert result.iterations == 2
    assert "max iterations" in result.answer
