"""Tool tests — KB search, account lookup, ticketing, escalation, and dispatch (offline)."""

from novacrm_agent.tools.account import get_account_info
from novacrm_agent.tools.escalation import escalate_to_team
from novacrm_agent.tools.knowledge_base import lookup_knowledge_base
from novacrm_agent.tools.registry import dispatch
from novacrm_agent.tools.ticketing import create_support_ticket


def test_kb_finds_pricing():
    out = lookup_knowledge_base("how much does the professional plan cost")
    assert "Professional" in out and "$79" in out


def test_kb_finds_refund_policy():
    out = lookup_knowledge_base("can I get a refund")
    assert "refund" in out.lower() and "escalate" in out.lower()


def test_kb_no_match():
    assert "No matching" in lookup_knowledge_base("zzzzz qqqqq")


def test_account_found_and_missing():
    assert get_account_info("CUST-1001")["found"] is True
    assert get_account_info("cust-1001")["found"] is True  # case-insensitive
    assert get_account_info("CUST-9999")["found"] is False


def test_ticket_validation():
    ok = create_support_ticket("CUST-1001", "Dashboard won't load", "high")
    assert ok["created"] and ok["ticket_id"].startswith("TICK-")
    assert create_support_ticket("CUST-1001", "x", "urgent")["created"] is False  # bad priority
    assert create_support_ticket("CUST-1001", "", "low")["created"] is False      # empty summary


def test_escalation_validation():
    ok = escalate_to_team("CUST-1001", "billing", "refund request")
    assert ok["escalated"] and ok["team"] == "billing"
    assert escalate_to_team("CUST-1001", "marketing", "x")["escalated"] is False
    assert escalate_to_team("CUST-1001", "supervisor", "abuse")["escalated"] is True  # D4 fix #3


def test_dispatch_unknown_and_json_args():
    assert "error" in dispatch("nope", "{}")
    out = dispatch("get_account_info", '{"customer_id": "CUST-1003"}')
    assert out["plan"] == "Enterprise"
