"""FastAPI wrapper tests — offline (agent + memory monkeypatched, no network/server)."""

from fastapi.testclient import TestClient

from novacrm_agent import server
from novacrm_agent.orchestrator import TurnResult
from novacrm_agent.tracing import Tracer

client = TestClient(server.app)


def _fake_result(tmp_path):
    tr = Tracer("web", "CUST-1001", log_dir=tmp_path)
    with tr.span("input_guard", "screen"):
        pass
    with tr.span("llm_call", "iter 0") as s:
        s.token_count = 120
    with tr.span("output_guard", "scan") as s:
        s.extra["action"] = "ok"
    return TurnResult(
        final_text="You're on the Professional plan, billed annually.",
        messages=[],
        tool_calls=[{"name": "get_account_info",
                     "arguments": '{"customer_id": "CUST-1001"}',
                     "output": {"plan": "Professional"}}],
        iterations=2, tracer=tr, blocked_by=None,
    )


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_chat_response_and_trace_shape(monkeypatch, tmp_path):
    monkeypatch.setattr(server._agent, "run", lambda *a, **k: _fake_result(tmp_path))
    monkeypatch.setattr(server.retriever, "get_memories", lambda uid, **k: [])

    r = client.post("/chat", json={"message": "what plan am I on?",
                                    "session_id": "t1", "customer_id": "CUST-1001"})
    assert r.status_code == 200
    d = r.json()
    assert d["response"].startswith("You're on")
    t = d["trace"]
    assert t["guardrails"] == {"input": "✓ clean", "output": "✓ approved"}
    assert t["tools"][0]["name"] == "get_account_info"
    assert t["iterations"] == 2 and t["tokens"] == 120
    assert isinstance(t["latency_ms"], int) and t["memories"] == []


def test_chat_accepts_null_customer(monkeypatch, tmp_path):
    monkeypatch.setattr(server._agent, "run", lambda *a, **k: _fake_result(tmp_path))
    monkeypatch.setattr(server.retriever, "get_memories", lambda uid, **k: [])
    r = client.post("/chat", json={"message": "hi", "session_id": "t2", "customer_id": None})
    assert r.status_code == 200
