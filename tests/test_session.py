"""Session + history-injection tests (offline, fake LLM)."""

from types import SimpleNamespace

from novacrm_agent.llm import LLMResult
from novacrm_agent.orchestrator import SupportAgent
from novacrm_agent.session import Session, ToolInteraction, new_session


def _tool_call(name, arguments, call_id="c1"):
    return SimpleNamespace(id=call_id, type="function",
                           function=SimpleNamespace(name=name, arguments=arguments))


def _result(content=None, tool_calls=None, finish_reason="stop"):
    return LLMResult(message=SimpleNamespace(content=content, tool_calls=tool_calls),
                     prompt_tokens=10, completion_tokens=5, finish_reason=finish_reason)


class RecordingLLM:
    """Returns scripted results and remembers the messages it was last handed."""
    def __init__(self, scripted):
        self._scripted = list(scripted)
        self.last_messages = None

    def chat(self, messages, tools=None, tool_choice="auto", temperature=0.2,
             max_tokens=1024, max_retries=3):
        self.last_messages = messages
        return self._scripted.pop(0)


def test_turn_renders_tool_use_as_natural_language():
    turn = ToolInteraction(tool_name="get_account_info",
                           tool_input={"customer_id": "CUST-1003"},
                           tool_output='{"plan": "Enterprise"}')
    s = new_session("sess-x", user_id="CUST-1003")
    s.add_turn("user", "what plan am I on?")
    s.add_turn("assistant", "You're on Enterprise.", tool_interactions=[turn])
    msgs = s.context_messages()
    assert msgs[0] == {"role": "user", "content": "what plan am I on?"}
    assert msgs[1]["role"] == "assistant"
    assert "recalled from earlier" in msgs[1]["content"]
    assert "Enterprise" in msgs[1]["content"]


def test_session_save_load_roundtrip(tmp_path):
    s = new_session("sess-rt", user_id="CUST-1001")
    s.add_turn("user", "hi")
    s.add_turn("assistant", "hello",
               tool_interactions=[ToolInteraction("escalate_to_team", {"team": "billing"}, "{}")],
               escalated=True, escalation_target="billing")
    s.save(sessions_dir=tmp_path)
    loaded = Session.load("sess-rt", sessions_dir=tmp_path)
    assert loaded.user_id == "CUST-1001"
    assert loaded.turns[1].escalated is True
    assert loaded.turns[1].escalation_target == "billing"
    assert loaded.turns[1].tool_interactions[0].tool_name == "escalate_to_team"


def test_history_injected_into_next_turn():
    # turn 1: tool call + answer; turn 2: a single direct answer
    llm = RecordingLLM([
        _result(tool_calls=[_tool_call("get_account_info", '{"customer_id": "CUST-1003"}')]),
        _result(content="You're on Enterprise, billed annually."),
        _result(content="You have 85 seats."),
    ])
    agent = SupportAgent(llm=llm, guardrails=False)  # history injection in isolation
    sess = new_session("sess-hist", user_id="CUST-1003")

    agent.run("What plan am I on? CUST-1003", session=sess)
    assert len(sess.turns) == 2  # user + assistant recorded

    agent.run("And how many seats?", session=sess)
    # the second call must have been handed the first turn's history
    injected = " ".join(m["content"] for m in llm.last_messages if isinstance(m.get("content"), str))
    assert "What plan am I on?" in injected
    assert "recalled from earlier" in injected
    assert "Enterprise" in injected
    assert len(sess.turns) == 4
