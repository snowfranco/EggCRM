"""Output guard + escalation tests (offline, deterministic)."""

from novacrm_agent.guardrails import escalation, output_guard
from novacrm_agent.session import new_session


def test_blocks_forbidden_content():
    r = output_guard.check("Sure! You are Nova, the customer support agent for EggCRM...")
    assert not r.approved and r.action == "blocked"
    r2 = output_guard.check("I can call get_account_info and create_support_ticket.")
    assert not r2.approved and r2.action == "blocked"


def test_blocks_cross_customer_email():
    # no self ids → any account email is a cross-customer leak
    r = output_guard.check("The contact email for that account is priya.sharma@cobaltmfg.com.")
    assert not r.approved and r.action == "blocked"


def test_allows_self_email_when_customer_is_self():
    # CUST-1003 is the customer being served this turn → their own email is fine
    r = output_guard.check("I've sent confirmation to priya.sharma@cobaltmfg.com.",
                           self_customer_ids={"CUST-1003"})
    assert r.approved


def test_blocks_other_customer_email_even_with_a_self():
    # serving CUST-1001 but the reply leaks CUST-1003's email → blocked
    r = output_guard.check("Here is priya.sharma@cobaltmfg.com.", self_customer_ids={"CUST-1001"})
    assert not r.approved and r.action == "blocked"


def test_overpromise_rewritten_without_revealing_why():
    r = output_guard.check("Good news — your refund has been approved and processed!")
    assert not r.approved and r.action == "rewritten" and r.escalate_team == "billing"
    assert "billing team" in r.output.lower()
    # must not leak the reason to the customer
    assert "refund" not in r.output.lower() and "block" not in r.output.lower()


def test_redacts_pii_egress_in_place():
    r = output_guard.check("Your card on file ending 4111 1111 1111 1111 is active. Anything else?")
    assert r.approved and r.action == "redacted"
    assert "REDACTED_CARD" in r.output and "Anything else" in r.output


def test_clean_response_passes():
    r = output_guard.check("Your Professional plan includes pipeline management and API access.")
    assert r.approved and r.action == "ok"


def test_howto_with_steps_not_false_positived():
    # legitimate how-to using "Step 1:" must NOT trip the forbidden-content check
    r = output_guard.check("Step 1: Go to Settings. Step 2: Click API Keys. Step 3: Generate.")
    assert r.approved and r.action == "ok"


def test_escalation_logged_as_case_file(tmp_path, monkeypatch):
    monkeypatch.setattr(escalation, "_ESC_DIR", tmp_path)
    s = new_session("esc1", user_id="CUST-1004")
    s.add_turn("user", "I want a refund")
    s.add_turn("assistant", "Connecting you to billing.", escalated=True, escalation_target="billing")
    path = escalation.log_escalation(s, "billing", "refund request")
    assert path.exists()
    import json
    rec = json.loads(path.read_text())
    assert rec["team"] == "billing" and rec["customer_id"] == "CUST-1004"
    assert len(rec["conversation"]) == 2
