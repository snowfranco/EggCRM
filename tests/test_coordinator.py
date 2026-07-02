"""NovaCoordinator tests (Project 4 Phase 2) — offline.

The coordinator's *routing* needs a live model (measured in the Phase-2 baseline, not here). These
tests pin the parts that must hold without the LLM:
- the two P3 action gates, now living in the ADK FunctionTool wrappers (cross-customer identity,
  confirm-before-create), including that guardrails=False bypasses them;
- `_harvest` reconstructing ordered tool calls + final text from an ADK event stream;
- the RAG specialist adapter extracting the delegated query and writing provenance to its sink.

Constructing a NovaCoordinator builds the ADK LlmAgent/LiteLlm/Runner but makes NO network call
(the model is only hit inside run()), so these stay fast and offline.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from novacrm_agent.agents.coordinator import CoordinatorResult, NovaCoordinator
from novacrm_agent.agents.rag_specialist import RagSpecialistAgent
from novacrm_agent.session import Session


def _session(user_id="CUST-1001"):
    return Session(session_id="s1", user_id=user_id, created_at="t0", updated_at="t0")


@pytest.fixture(scope="module")
def nova():
    # provider="groq" avoids depending on OpenRouter credit even for construction-time wiring.
    return NovaCoordinator(provider="groq")


# --- action gate: cross-customer identity -----------------------------------
def test_account_gate_blocks_other_customer(nova):
    nova._ctx = {"session": _session("CUST-1001")}
    out = nova.get_account_info("CUST-2002")
    assert out["found"] is False
    assert "identity_check_failed" in out["error"]


def test_account_gate_allows_own_account(nova):
    nova._ctx = {"session": _session("CUST-1001")}
    out = nova.get_account_info("CUST-1001")
    assert out["found"] is True
    assert out["customer_id"] == "CUST-1001"


def test_account_gate_bypassed_when_guardrails_off():
    off = NovaCoordinator(provider="groq", guardrails=False)
    off._ctx = {"session": _session("CUST-1001")}
    # no gate → the mock lookup runs even for a different customer
    assert off.get_account_info("CUST-1003")["found"] is True


# --- action gate: confirm-before-create -------------------------------------
def test_ticket_gate_requires_prior_confirmation(nova):
    sess = _session("CUST-1001")  # no assistant proposal yet
    nova._ctx = {"session": sess}
    out = nova.create_support_ticket("CUST-1001", "Export fails", "high")
    assert out["created"] is False
    assert "confirmation_required" in out["error"]


def test_ticket_gate_passes_after_proposal(nova):
    sess = _session("CUST-1001")
    sess.add_turn("user", "my export keeps failing")
    sess.add_turn("assistant", "I'll create a ticket with summary 'export fails' at high priority — shall I?")
    nova._ctx = {"session": sess}
    out = nova.create_support_ticket("CUST-1001", "Export fails", "high")
    assert out.get("created") is True


# --- _harvest: reconstruct calls + final text from ADK events ----------------
def _part(text=None, fc=None, fr=None):
    return SimpleNamespace(text=text, function_call=fc, function_response=fr)


def _event(parts, final=False):
    return SimpleNamespace(content=SimpleNamespace(parts=parts), is_final_response=lambda: final)


def test_harvest_orders_calls_and_captures_final_text():
    events = [
        _event([_part(fc=SimpleNamespace(id="a", name="nova_docs", args={"request": "pricing?"}))]),
        _event([_part(fr=SimpleNamespace(id="a", name="nova_docs", response={"answer": "$79"}))]),
        _event([_part(fc=SimpleNamespace(id="b", name="get_account_info", args={"customer_id": "CUST-1003"}))]),
        _event([_part(fr=SimpleNamespace(id="b", name="get_account_info", response={"found": True}))]),
        _event([_part(text="Here is your answer.")], final=True),
    ]
    final_text, calls, iterations, tokens = NovaCoordinator._harvest(events)
    assert final_text == "Here is your answer."
    assert [c["name"] for c in calls] == ["nova_docs", "get_account_info"]
    assert calls[0]["output"] == {"answer": "$79"}
    assert calls[1]["arguments"] == '{"customer_id": "CUST-1003"}'
    # two tool-call turns + one final-answer turn = 3 coordinator LLM turns
    assert iterations == 3


def test_harvest_ignores_contentless_events():
    events = [SimpleNamespace(content=None, usage_metadata=None, is_final_response=lambda: False),
              _event([_part(text="final")], final=True)]
    final_text, calls, _iters, _tokens = NovaCoordinator._harvest(events)
    assert final_text == "final"
    assert calls == []


# --- RAG specialist adapter -------------------------------------------------
def test_specialist_extracts_query_from_user_content():
    ctx = SimpleNamespace(user_content=SimpleNamespace(
        parts=[SimpleNamespace(text="How do I export data?")]))
    assert RagSpecialistAgent._extract_query(ctx) == "How do I export data?"


def test_specialist_extract_query_handles_empty():
    assert RagSpecialistAgent._extract_query(SimpleNamespace(user_content=None)) == ""


def test_coordinator_result_delegated_helper():
    assert CoordinatorResult(final_text="x", route=["nova_docs"]).delegated_to_rag() is True
    assert CoordinatorResult(final_text="x", route=["get_account_info"]).delegated_to_rag() is False
