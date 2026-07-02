"""Memory layer tests (offline): consolidation rules, store I/O, retriever, extractor."""

import json
from types import SimpleNamespace

from novacrm_agent.llm import LLMResult
from novacrm_agent.memory import extractor, retriever, store
from novacrm_agent.memory.schemas import ExtractionResult, MemoryEntry, StoredMemory


def _extraction(*entries):
    return ExtractionResult(memories=[MemoryEntry(**e) for e in entries])


def test_changeable_topic_last_write_wins():
    existing = store.consolidate(
        [], _extraction({"topic": "communication_preferences",
                         "fact": "Prefers phone contact.", "confidence": 0.9, "source_turn": 1}),
        "sess-1", now="t0")
    # a new, overlapping comms preference should REPLACE, not duplicate
    merged = store.consolidate(
        existing, _extraction({"topic": "communication_preferences",
                               "fact": "Prefers email contact, not phone.", "confidence": 0.95, "source_turn": 2}),
        "sess-2", now="t1")
    prefs = [m for m in merged if m.topic.value == "communication_preferences"]
    assert len(prefs) == 1
    assert "email" in prefs[0].fact
    assert prefs[0].last_updated == "t1"


def test_issue_history_appends_distinct_events():
    e1 = _extraction({"topic": "issue_history", "fact": "Dashboard crashes every morning.",
                      "confidence": 0.9, "source_turn": 1})
    e2 = _extraction({"topic": "issue_history", "fact": "Email sync stopped working entirely.",
                      "confidence": 0.9, "source_turn": 1})
    merged = store.consolidate(store.consolidate([], e1, "s1"), e2, "s2")
    issues = [m for m in merged if m.topic.value == "issue_history"]
    assert len(issues) == 2  # distinct events accumulate


def test_store_roundtrip(tmp_path):
    mems = store.consolidate([], _extraction(
        {"topic": "customer_identity", "fact": "Priya at Cobalt.", "confidence": 1.0, "source_turn": 1}),
        "s1", now="t0")
    store.save("CUST-1003", mems, store_dir=tmp_path)
    loaded = store.load("CUST-1003", store_dir=tmp_path)
    assert loaded[0].fact == "Priya at Cobalt."


def test_retriever_block_excludes_when_empty(tmp_path):
    assert retriever.context_block("CUST-9999", store_dir=tmp_path) is None


def test_retriever_block_renders_memories(tmp_path):
    store.save("CUST-1003", [StoredMemory(
        topic="issue_history", fact="Dashboard crashes daily.", confidence=0.9,
        source_session="s1", source_turn=1, first_seen="t0", last_updated="t0")],
        store_dir=tmp_path)
    block = retriever.context_block("CUST-1003", store_dir=tmp_path)
    assert "Dashboard crashes daily." in block
    assert "get_account_info" in block  # reminds the agent tier/billing is live


def test_extractor_parses_forced_tool_call():
    args = json.dumps({"memories": [
        {"topic": "sentiment_trajectory", "fact": "Frustrated about billing.",
         "confidence": 0.8, "source_turn": 3}]})
    msg = SimpleNamespace(content=None, tool_calls=[
        SimpleNamespace(function=SimpleNamespace(name="record_memories", arguments=args))])

    class FakeLLM:
        def chat(self, *a, **k):
            return LLMResult(message=msg, prompt_tokens=1, completion_tokens=1, finish_reason="tool_calls")

    from novacrm_agent.session import new_session
    s = new_session("sess-x", user_id="CUST-1004")
    s.add_turn("user", "I was double charged and I'm fed up")
    s.add_turn("assistant", "Escalating to billing.")
    result = extractor.extract(s, llm=FakeLLM())
    assert len(result.memories) == 1
    assert result.memories[0].topic.value == "sentiment_trajectory"
