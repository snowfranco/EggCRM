# CI Evaluation Gate — Implementation Spec

**Owner:** Claude.ai (architecture/spec) → **Implementer:** Claude Code
**Status:** Awaiting sign-off before build
**Applies to:** Nova (P3 framework-free, P4 multi-agent). Existing harness in `eval/`: `structural_eval.py`, `llm_judge.py`, `trajectory_eval.py`, `run_eval.py`.

## Goal

Wire the **existing** eval harness into GitHub Actions as a merge-blocking status check that fires on prompt/model/eval changes. **The evaluators are not modified** — we add a thin comparison + reporting layer around them and a workflow file. This closes the one gap identified in the article audit: the eval engine exists but was never automated as a gate.

## Design principles (carried from P3/P4)

- **Both-defenses:** deterministic checks hard-block; LLM-judge scores soft-block with tolerance. Same philosophy as the two-layer guardrail.
- **Measure-before-proceeding:** the enforced floor lives in a committed baseline contract, not in code.
- **Evidence over assumptions:** every run emits an auditable JSON report + PR comment. The gate's verdict is reproducible from the artifact.
- **Process over output:** the gate blocks on trajectory/routing discipline, not only output metrics. This is the differentiator — see D-CI-2.

---

## Decisions

### D-CI-1 — Separate *baseline* from *threshold*
`eval/baselines.json` holds the last-known-good score per metric plus a tolerance band. **Threshold = baseline − tolerance.** A run fails a metric when `measured < threshold`. The original article conflates baseline and threshold; we don't, because judge noise would otherwise cause false failures.

```json
{
  "judge_model": "groq/llama-4-scout-17b",
  "judge_samples": 3,
  "metrics": {
    "structural_pass_rate": { "baseline": 1.00, "tolerance": 0.00, "class": "hard" },
    "safety_pass_rate":     { "baseline": 1.00, "tolerance": 0.00, "class": "hard" },
    "routing_discipline":   { "baseline": 1.00, "tolerance": 0.00, "class": "hard" },
    "correctness":          { "baseline": 4.83, "tolerance": 0.30, "class": "soft" },
    "helpfulness":          { "baseline": 4.66, "tolerance": 0.30, "class": "soft" },
    "persona":              { "baseline": 4.86, "tolerance": 0.30, "class": "soft" }
  }
}
```
(Baselines above are placeholders from P3 scores — Claude Code should regenerate them from a clean full run on `main` before enabling the gate as required.)

### D-CI-2 — Two gate classes
- **HARD (tolerance 0, blocks merge):** `structural_pass_rate`, `safety_pass_rate`, `routing_discipline`. These are deterministic and reproducible, so they are legitimate hard blockers.
- **SOFT (tolerance band, blocks merge only on real drop):** `correctness`, `helpfulness`, `persona` from LLM-as-Judge. Median-of-N + band absorbs non-determinism.

**Why this matters:** an output-only gate would pass a build where Nova stopped verifying account tier (the P4 failure — 96% output accuracy, 8% process compliance). Gating on `routing_discipline` is what makes this gate catch what the article's design misses. This is also the demo (see §Demonstration Feature).

### D-CI-3 — Judge determinism controls
- `temperature=0` on all judge calls.
- `judge_samples=3`, take the **median** per case.
- **Pin** `judge_model` in `baselines.json`. If the judge model string changes, that's a baseline-affecting change and must be re-baselined in the same PR.

### D-CI-4 — Tiered run scope (cost/latency)
- **PR trigger → `smoke` set:** all safety cases + all tier-routing cases + 2–3 representative output cases (~6–8 total). Target < 2 min, low token cost.
- **Push to `main` + nightly → `full` set.**
Rationale: full judge eval on every PR is slow and token-heavy (the article's own runtime note). Safety and routing cases *always* run on PR because those regressions must never merge.

### D-CI-5 — Path filtering
PR gate triggers only when behavior can change:
```
paths: [ "**/prompt.py", "agent/**", "eval/golden_set*.json", "**/model_config*" ]
```
Docs-only PRs skip the gate. (This is the article's "prompt/model change" trigger, made precise.)

### D-CI-6 — Secrets & isolation
- Dedicated CI keys as GitHub secrets: `OPENROUTER_CI_KEY`, `GROQ_CI_KEY`. Standalone keys with their own rate budget.
- **Rotation note:** P4 flagged the LiteLLM adapter has no key rotation. The CI key must be independent so a CI run can't exhaust the dev key's budget.

### D-CI-7 — Outputs & auditability
- `run_eval.py` writes `eval/reports/<mode>-<sha>.json`.
- Workflow uploads it as a build artifact and posts a PR comment table: `metric | baseline | threshold | measured | Δ | class | pass/fail`.
- **Slack / W&B notifications are deferred** (parking-lot candidate — over-scoped for a demo).

---

## Interface contract (what `run_eval.py` must expose)

Additive only. Claude Code should check current signatures first, then add:

- `--mode {smoke,full}` — selects the case subset.
- `--baseline <path>` — enables compare mode.
- `--report <path>` — machine-readable JSON out.
- **Exit codes:** `0` = all gates pass · `1` = one or more gates failed (hard or soft) · `2` = **infra error** (judge unreachable, rate-limited after retries). Encode hard-vs-soft per-metric in the report, not the exit code.
- **Infra vs regression:** on judge failure, retry once with the fallback model (Scout ↔ GLM). If still failing, exit `2`. The workflow treats `2` as `error` (neutral), **not** `failure`, so infra flakiness never looks like a regression.

## Report schema (minimum)
```json
{
  "sha": "…", "mode": "smoke", "judge_model": "…",
  "metrics": {
    "routing_discipline": { "baseline": 1.0, "threshold": 1.0, "measured": 0.5, "class": "hard", "pass": false }
  },
  "overall_pass": false,
  "hard_failures": ["routing_discipline"],
  "soft_failures": []
}
```

## Workflow: `.github/workflows/eval-gate.yml`
```
on:
  pull_request: { paths: [ … see D-CI-5 … ] }
  push:         { branches: [ main ] }

job eval-gate:
  - actions/checkout@v4
  - actions/setup-python@v5   (3.11)
  - pip install -r requirements.txt
  - if PR:   python eval/run_eval.py --mode smoke --baseline eval/baselines.json --report eval/reports/pr-${{ github.sha }}.json
  - if main: python eval/run_eval.py --mode full  --baseline eval/baselines.json --report eval/reports/main-${{ github.sha }}.json
  - actions/upload-artifact@v4  (the report)
  - actions/github-script@v7    (read report → post/update PR comment table)
env:
  OPENROUTER_CI_KEY: ${{ secrets.OPENROUTER_CI_KEY }}
  GROQ_CI_KEY:       ${{ secrets.GROQ_CI_KEY }}
```
**Branch protection (repo settings, done by human):** require the `eval-gate` status check + "require branches up to date before merging".

## Baseline update process
A legitimate improvement raises the floor in the **same PR** that produces it: edit `baselines.json`, justify in the PR body, log as a `DECISIONS.md` entry. The gate reads the baseline from the PR branch, so "improve + re-baseline" is one atomic, reviewed change. No manual out-of-band threshold editing.

## Failure modes (must be handled)
| Mode | Mitigation |
|---|---|
| Judge non-determinism → false fail | median-of-3 + tolerance band (D-CI-3) |
| Judge/API down or rate-limited | retry w/ fallback model → exit `2` → job = *error*, not *failure* |
| Token cost blowup | smoke subset on PR (D-CI-4) |
| Silent judge model drift | pinned `judge_model`, re-baseline required if changed |
| Docs PR blocked needlessly | path filter (D-CI-5) |

---

## Demonstration Feature — Refund eligibility requires verified tier

**Why this feature:** it exercises `routing_discipline` (the trajectory gate), which is exactly the thing an output-only gate can't catch. The demo *is* the P4 finding, reproduced as a caught regression. Deterministic → clean, repeatable demo with no judge flakiness in the headline metric. Surface is small (prompt.py + 2 golden cases + 1 baseline entry) — persona-swap-style.

**Behavior:** Nova must verify the customer's account tier (via the existing account tool) **before** stating refund eligibility, because refund windows are tier-dependent. Answering a refund-eligibility question without a prior verified account lookup is a routing-discipline failure, even if the stated policy happens to be correct.

**Golden cases (add to set, tagged `routing`):**
1. Verified-tier customer asks about refund window → Nova verifies, then answers → compliant.
2. Unverified customer asks about refund window → Nova must verify first → compliant only if the account lookup precedes the eligibility statement.

**The demo sequence (this is what proves the gate works):**
1. `main`: feature implemented correctly. Full run → `routing_discipline = 1.0`. Gate green. Re-baseline.
2. Open a PR that "simplifies" `prompt.py` by dropping the verify-before-refund step — a *plausible, well-intentioned* change. Output judge scores stay high (the answer still reads fine). But `routing_discipline` drops to ~0.5. **Hard gate fails → PR blocked.**
3. The PR comment shows: correctness/helpfulness green, `routing_discipline` red. That contrast is the entire pitch.
4. Restore the step → gate green → merge.

Keep the regression PR as a permanent demo branch (`demo/routing-regression`) so the red→green story is reproducible on command.
