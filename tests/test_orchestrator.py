"""Orchestrator loop tests with a fake LLM — no network.

Verifies the two things the loop must get right: it dispatches a tool call and feeds the
observation back, and it terminates (both normally and via the max_iters safety net).
"""

from types import SimpleNamespace

from novacrm_agent.llm import LLMResult
from novacrm_agent.orchestrator import SupportAgent


def _tool_call(name, arguments, call_id="call_1"):
    return SimpleNamespace(id=call_id, type="function",
                           function=SimpleNamespace(name=name, arguments=arguments))


def _result(content=None, tool_calls=None, finish_reason="stop"):
    msg = SimpleNamespace(content=content, tool_calls=tool_calls)
    return LLMResult(message=msg, prompt_tokens=10, completion_tokens=5, finish_reason=finish_reason)


class FakeLLM:
    def __init__(self, scripted):
        self._scripted = list(scripted)
        self.calls = 0

    def chat(self, messages, tools=None, tool_choice="auto", temperature=0.2,
             max_tokens=1024, max_retries=3):
        self.calls += 1
        return self._scripted.pop(0)


def test_loop_dispatches_tool_then_answers():
    fake = FakeLLM([
        _result(tool_calls=[_tool_call("get_account_info", '{"customer_id": "CUST-1001"}')]),
        _result(content="You're on the Professional plan, billed annually."),
    ])
    agent = SupportAgent(llm=fake, guardrails=False)  # loop mechanics in isolation
    res = agent.run("What plan am I on?", customer_id="CUST-1001")

    assert res.tool_names() == ["get_account_info"]
    assert res.tool_calls[0]["output"]["plan"] == "Professional"
    assert "Professional" in res.final_text
    assert res.hit_max_iters is False
    assert res.iterations == 2
    # tool observation was fed back into the transcript
    assert any(m["role"] == "tool" for m in res.messages)


def test_direct_answer_no_tools():
    fake = FakeLLM([_result(content="Hi, I'm Nova. How can I help?")])
    res = SupportAgent(llm=fake, guardrails=False).run("hello")
    assert res.tool_calls == []
    assert res.iterations == 1


def test_max_iters_guard():
    # model that never stops calling tools — safety net must trip
    looping = [_result(tool_calls=[_tool_call("lookup_knowledge_base", '{"query": "x"}')])
               for _ in range(10)]
    res = SupportAgent(llm=FakeLLM(looping), guardrails=False).run("loop forever", max_iters=3)
    assert res.hit_max_iters is True
    assert res.iterations == 3
