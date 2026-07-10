"""CI eval gate — thin comparison + reporting layer (spec: docs/ci-eval-gate-spec.md).

The evaluators themselves are NOT modified (spec ground rule): `run_eval.py` keeps its
structural checks + LLM judge, `tier_discipline.py` keeps its trace assertion. This module
adds the pure logic around them:

  - D-CI-1: baseline vs threshold. `baselines.json` holds last-known-good + tolerance;
    threshold = baseline - tolerance; a metric fails when measured < threshold.
  - D-CI-2: two gate classes. "hard" metrics are deterministic (tolerance 0) and block merge
    outright; "soft" metrics are LLM-judge scores that block only on a real drop.
  - D-CI-3: judge pinning. The judge model string in baselines.json must match the harness's
    active judge — drift is a baseline-affecting change, refused as an infra error.
  - D-CI-4: tiered scope. `select_cases` picks the smoke subset (all safety cases + a few
    representative output cases) for PR runs; full = everything.

Stdlib-only on purpose: the compare/report logic is unit-tested offline (tests/test_ci_gate.py)
with no provider, ADK, or vector-store dependencies.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

# D-CI-4: smoke = all safety-category golden cases + these representative output cases
# (factual pricing, account lookup, multi-turn memory) so every PR run exercises one case
# from each non-safety behavior family without paying for the full 33-case judge pass.
SMOKE_REPRESENTATIVE_IDS = ("G01", "G12", "G18")


def load_baselines(path: str | Path) -> dict:
    """Read the committed baseline contract (eval/baselines.json)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def median(values: list) -> float:
    """Per-case judge score = median of N temperature-0 samples (D-CI-3)."""
    return statistics.median(values)


def validate_judge_pin(baselines: dict, active_model: str) -> str | None:
    """D-CI-3: the pinned judge must match the harness judge. Returns an error string on
    drift (caller exits 2 — infra, not regression), None when the pin holds."""
    pinned = baselines.get("judge_model")
    if pinned and pinned != active_model:
        return (f"judge model drift: baselines.json pins '{pinned}' but the harness judge is "
                f"'{active_model}'. A judge change is baseline-affecting and must be "
                f"re-baselined in the same PR (D-CI-3).")
    return None


def select_cases(cases: list[dict], mode: str,
                 representative_ids: tuple[str, ...] = SMOKE_REPRESENTATIVE_IDS) -> list[dict]:
    """D-CI-4 tiered scope. smoke: every safety case (those regressions must never merge)
    + the representative output cases. full: the whole set."""
    if mode == "full":
        return list(cases)
    keep = set(representative_ids)
    return [c for c in cases if c["category"] == "safety" or c["id"] in keep]


def compare_metrics(baselines: dict, measured: dict[str, float]) -> dict:
    """Compare every contracted metric against its threshold (D-CI-1).

    Raises KeyError if a contracted metric was not measured — the caller must treat that as
    an infra error (exit 2), never as a pass.
    """
    out = {}
    for name, spec in baselines["metrics"].items():
        m = measured[name]
        threshold = round(spec["baseline"] - spec["tolerance"], 6)
        out[name] = {
            "baseline": spec["baseline"],
            "threshold": threshold,
            "measured": round(m, 4),
            "class": spec["class"],
            "pass": m >= threshold,
        }
    return out


def build_report(*, sha: str, mode: str, judge_model: str, metrics: dict,
                 extra: dict | None = None) -> dict:
    """Assemble the auditable report (D-CI-7 / spec §Report schema). Hard-vs-soft is encoded
    per metric here, not in the exit code."""
    hard_failures = [n for n, m in metrics.items() if not m["pass"] and m["class"] == "hard"]
    soft_failures = [n for n, m in metrics.items() if not m["pass"] and m["class"] == "soft"]
    report = {
        "sha": sha,
        "mode": mode,
        "judge_model": judge_model,
        "metrics": metrics,
        "overall_pass": not hard_failures and not soft_failures,
        "hard_failures": hard_failures,
        "soft_failures": soft_failures,
    }
    if extra:
        report.update(extra)
    return report


def exit_code(report: dict) -> int:
    """0 = all gates pass; 1 = one or more gates failed (hard or soft). Infra errors never
    reach here — the runner exits 2 before comparing."""
    return 0 if report["overall_pass"] else 1


def write_report(report: dict, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return p


def format_table(metrics: dict) -> str:
    """Console rendering of the per-metric verdicts (the PR comment renders the same table
    from the report JSON in the workflow)."""
    lines = ["metric | baseline | threshold | measured | Δ | class | verdict",
             "-------|----------|-----------|----------|---|-------|--------"]
    for name, m in metrics.items():
        delta = round(m["measured"] - m["baseline"], 4)
        verdict = "pass" if m["pass"] else f"FAIL ({m['class']})"
        lines.append(f"{name} | {m['baseline']} | {m['threshold']} | {m['measured']} | "
                     f"{delta:+g} | {m['class']} | {verdict}")
    return "\n".join(lines)
