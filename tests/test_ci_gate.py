"""Offline tests for the CI-gate comparison layer (eval/ci_gate.py) and the refund
routing-discipline assertion (eval/routing_cases.py). Stdlib-only — no network, no ADK."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))

import ci_gate          # noqa: E402
import routing_cases    # noqa: E402

BASELINES = {
    "judge_model": "judge-x",
    "judge_samples": 3,
    "metrics": {
        "structural_pass_rate": {"baseline": 1.0, "tolerance": 0.0, "class": "hard"},
        "routing_discipline": {"baseline": 1.0, "tolerance": 0.0, "class": "hard"},
        "correctness": {"baseline": 4.8, "tolerance": 0.3, "class": "soft"},
    },
}

ALL_PASS = {"structural_pass_rate": 1.0, "routing_discipline": 1.0, "correctness": 4.9}


def _report(measured):
    metrics = ci_gate.compare_metrics(BASELINES, measured)
    return ci_gate.build_report(sha="abc", mode="smoke", judge_model="judge-x", metrics=metrics)


# --- D-CI-1: baseline vs threshold ------------------------------------------------------------

def test_threshold_is_baseline_minus_tolerance():
    metrics = ci_gate.compare_metrics(BASELINES, ALL_PASS)
    assert metrics["correctness"]["threshold"] == pytest.approx(4.5)
    assert metrics["routing_discipline"]["threshold"] == 1.0


def test_measured_at_threshold_passes():
    metrics = ci_gate.compare_metrics(BASELINES, {**ALL_PASS, "correctness": 4.5})
    assert metrics["correctness"]["pass"] is True


def test_measured_below_threshold_fails():
    metrics = ci_gate.compare_metrics(BASELINES, {**ALL_PASS, "correctness": 4.49})
    assert metrics["correctness"]["pass"] is False


def test_missing_contracted_metric_raises():
    # An unmeasured metric must never silently pass — the runner treats KeyError as infra.
    with pytest.raises(KeyError):
        ci_gate.compare_metrics(BASELINES, {"correctness": 4.9})


# --- D-CI-2: hard vs soft classes + exit codes -------------------------------------------------

def test_all_pass_report_and_exit_0():
    r = _report(ALL_PASS)
    assert r["overall_pass"] is True
    assert r["hard_failures"] == [] and r["soft_failures"] == []
    assert ci_gate.exit_code(r) == 0


def test_hard_failure_blocks():
    r = _report({**ALL_PASS, "routing_discipline": 0.857})
    assert r["hard_failures"] == ["routing_discipline"]
    assert r["overall_pass"] is False
    assert ci_gate.exit_code(r) == 1


def test_soft_failure_also_blocks_via_exit_1():
    # Spec: exit 1 for hard OR soft — the class distinction lives in the report, not the code.
    r = _report({**ALL_PASS, "correctness": 4.0})
    assert r["hard_failures"] == [] and r["soft_failures"] == ["correctness"]
    assert ci_gate.exit_code(r) == 1


def test_report_has_spec_minimum_schema():
    r = _report(ALL_PASS)
    assert {"sha", "mode", "judge_model", "metrics", "overall_pass",
            "hard_failures", "soft_failures"} <= set(r)
    assert {"baseline", "threshold", "measured", "class", "pass"} <= set(
        r["metrics"]["correctness"])


# --- D-CI-3: judge determinism controls --------------------------------------------------------

def test_median_of_three():
    assert ci_gate.median([5, 4, 4]) == 4


def test_median_of_two_valid_samples():
    assert ci_gate.median([5, 4]) == 4.5


def test_judge_pin_holds():
    assert ci_gate.validate_judge_pin(BASELINES, "judge-x") is None


def test_judge_pin_drift_is_error():
    err = ci_gate.validate_judge_pin(BASELINES, "judge-y")
    assert err and "drift" in err


# --- D-CI-4: tiered scope -----------------------------------------------------------------------

CASES = [
    {"id": "G01", "category": "factual"},
    {"id": "G02", "category": "factual"},
    {"id": "G12", "category": "account"},
    {"id": "G21", "category": "safety"},
    {"id": "G33", "category": "safety"},
]


def test_smoke_is_all_safety_plus_representatives():
    ids = [c["id"] for c in ci_gate.select_cases(CASES, "smoke")]
    assert ids == ["G01", "G12", "G21", "G33"]  # G02 (non-representative factual) excluded


def test_full_is_everything():
    assert ci_gate.select_cases(CASES, "full") == CASES


# --- D-CI-7: report file ------------------------------------------------------------------------

def test_write_report_creates_parent_dirs(tmp_path):
    path = tmp_path / "reports" / "smoke-abc.json"
    ci_gate.write_report(_report(ALL_PASS), path)
    assert json.loads(path.read_text())["sha"] == "abc"


def test_format_table_mentions_failures():
    table = ci_gate.format_table(ci_gate.compare_metrics(
        BASELINES, {**ALL_PASS, "routing_discipline": 0.5}))
    assert "FAIL (hard)" in table and "routing_discipline" in table


# --- Demo feature: refund-eligibility routing discipline ----------------------------------------

def test_refund_verify_before_answer_is_compliant():
    ok, reason = routing_cases.refund_discipline_ok(["get_account_info", "nova_docs"])
    assert ok and reason == "ok"


def test_refund_lookup_without_docs_is_compliant():
    ok, _ = routing_cases.refund_discipline_ok(["get_account_info"])
    assert ok


def test_refund_no_lookup_fails():
    # The P4 failure mode: the stated policy may read fine, but no verification happened.
    ok, reason = routing_cases.refund_discipline_ok(["nova_docs"])
    assert not ok and reason == "no_account_verification"


def test_refund_lookup_after_docs_fails():
    ok, reason = routing_cases.refund_discipline_ok(["nova_docs", "get_account_info"])
    assert not ok and reason == "account_after_docs"
