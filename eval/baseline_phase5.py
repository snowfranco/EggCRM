"""Phase 5 baseline — output-failure BEFORE (unguarded) vs AFTER (guarded), + regression + HITL.

Same discipline as Phase 4: measure how many output-failure cases leak with no output guard,
then activate the guards and re-measure. A case "leaks" if any of its `forbidden` strings
appears in the final response. Also verifies the HITL protocol: escalations produce case files.

Run: python eval/baseline_phase5.py  ->  eval/baseline_phase5.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from novacrm_agent import config                       # noqa: E402
from novacrm_agent.orchestrator import SupportAgent    # noqa: E402
from output_failure_cases import OUTPUT_FAILURE_CASES  # noqa: E402
from baseline_phase1 import CASES, score               # noqa: E402
from baseline_phase2 import SCENARIOS as P2_SCENARIOS  # noqa: E402

_ESC_DIR = _ROOT / "data" / "escalations"


def leaked(case, res) -> bool:
    r = (res.final_text or "").lower()
    return any(f.lower() in r for f in case["forbidden"])


def run_output(agent, label):
    results, clean = [], 0
    for c in OUTPUT_FAILURE_CASES:
        res = agent.run(c["text"])
        is_leak = leaked(c, res)
        clean += not is_leak
        results.append({"id": c["id"], "category": c["category"], "leaked": is_leak,
                        "reply": (res.final_text or "")[:120]})
    print(f"  {label}: {clean}/{len(OUTPUT_FAILURE_CASES)} clean (no leak)")
    return results, clean


def run_regression(agent):
    reg = 0
    for case in CASES:
        ok, _ = score(case, agent.run(case["msg"], customer_id=case["customer"]))
        reg += ok
    for fn in P2_SCENARIOS:
        _, _, checks = fn(agent)
        reg += all(c["passed"] for c in checks if c["hard"])
    total = len(CASES) + len(P2_SCENARIOS)
    print(f"  Regression (guarded): {reg}/{total}")
    return reg, total


def main() -> int:
    if not config.OPENROUTER_API_KEY:
        print("BLOCKED: OPENROUTER_API_KEY is not set.")
        return 2

    print(f"Phase 5 baseline — model: {config.PRIMARY_MODEL}\n")
    unguarded = SupportAgent(guardrails=False)
    guarded = SupportAgent(guardrails=True)

    print("Output-failure leakage:")
    before, n_before = run_output(unguarded, "BEFORE (unguarded)")

    # clear escalation case files so we can count what the guarded run produces
    existing = list(_ESC_DIR.glob("*.json")) if _ESC_DIR.exists() else []
    for p in existing:
        p.unlink()
    after, n_after = run_output(guarded, "AFTER  (guarded)  ")

    print("\nRegression:")
    reg, reg_total = run_regression(guarded)

    # count escalation case files AFTER the full guarded run — the escalating cases (Q5-Q8, S3)
    # are in the regression set, so HITL must be tallied last.
    esc_files = len(list(_ESC_DIR.glob("*.json"))) if _ESC_DIR.exists() else 0
    print(f"  HITL: {esc_files} escalation case file(s) written during guarded run")

    n = len(OUTPUT_FAILURE_CASES)
    summary = {
        "model": config.PRIMARY_MODEL,
        "output_failure": {"total": n,
                           "before_clean": n_before, "before_rate": round(n_before / n, 3),
                           "after_clean": n_after, "after_rate": round(n_after / n, 3),
                           "before": before, "after": after},
        "hitl_escalation_files": esc_files,
        "regression": {"total": reg_total, "passed": reg},
    }
    (Path(__file__).resolve().parent / "baseline_phase5.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n=== Output leak-free BEFORE {n_before}/{n} ({n_before/n:.0%}) -> AFTER {n_after}/{n} "
          f"({n_after/n:.0%}) | HITL files {esc_files} | Regression {reg}/{reg_total} ===")
    print("Wrote baseline_phase5.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
