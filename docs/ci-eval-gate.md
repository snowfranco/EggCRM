# CI evaluation gate — runbook

Spec: `docs/ci-eval-gate-spec.md` (D-CI-1…7) · Decision log: `DECISIONS_4.md` → P4-D11 ·
Workflow: `.github/workflows/eval-gate.yml` · Gate logic: `eval/ci_gate.py` +
`eval/run_eval.py --mode` · Contract: `eval/baselines.json`.

The existing evaluators are unchanged; the gate is a thin comparison + reporting layer around
them, wired into GitHub Actions as a merge-blocking status check.

## What runs when

| Trigger | Scope | Cases |
|---|---|---|
| PR touching behavior paths (D-CI-5) | `smoke` | all 8 safety golden cases + G01/G12/G18 representatives, + routing-discipline cases ×1 rep |
| Push to `main`, nightly cron, manual dispatch | `full` | all 33 golden cases + routing-discipline cases ×3 reps |

Routing-discipline cases = the 5 tier cases (`tier_discipline.py`, reused unmodified) + the
2 refund-eligibility cases (`routing_cases.py`, the demo feature). Docs-only PRs skip the gate
via the path filter.

## Metrics and classes (D-CI-2)

| Metric | Source | Class |
|---|---|---|
| `structural_pass_rate` | `structural()` over the run's golden cases | hard |
| `safety_pass_rate` | `structural()` over the safety-category golden cases | hard |
| `routing_discipline` | trace assertion: account verification before/with the docs delegation / eligibility statement | hard |
| `correctness`, `helpfulness`, `persona` | LLM judge, median-of-3 at temperature 0 (D-CI-3) | soft |

Threshold = baseline − tolerance (D-CI-1). Hard metrics have tolerance 0; soft metrics carry a
0.3 band so judge noise can't cause false failures.

**Exit codes:** `0` all gates pass · `1` gate failed (hard vs soft is encoded per-metric in the
report, not the exit code) · `2` infra error (agent/judge unreachable after retry + Scout↔GLM
fallback) — surfaced as a **neutral** check run, never a failure.

The merge-blocking check is the **`eval-gate-verdict`** check run the workflow creates (the job
itself always completes so that exit 2 can be neutral rather than red).

## One-time enablement (human-owned)

1. **Secrets** (repo → Settings → Secrets → Actions), per D-CI-6 standalone CI keys:
   - `OPENROUTER_CI_KEY` — mapped by the workflow onto `OPENROUTER_API_KEY7`, the
     highest-precedence slot in `config.py`'s key chain, so it can't drain the dev keys.
   - `GROQ_CI_KEY` — mapped onto `GROQ_API_KEY` (judge + guard model).
2. **Regenerate baselines** — the committed `eval/baselines.json` values are placeholders from
   the recorded P3/P4 scores. On `main`, with funded keys:

   ```bash
   python eval/run_eval.py --mode full --report eval/reports/rebaseline.json
   ```

   (no `--baseline` → measurement-only). Copy the `measured` block's values into
   `eval/baselines.json`, commit with a `DECISIONS_4.md` note.
3. **Branch protection** (repo settings): require the `eval-gate-verdict` status check and
   "require branches to be up to date before merging".

## Baseline update process (D-CI-1)

A legitimate improvement raises the floor **in the same PR that produces it**: edit
`baselines.json`, justify in the PR body, log a `DECISIONS_4.md` entry. The gate reads the
baseline from the PR branch, so improve + re-baseline is one atomic, reviewed change. Never
edit thresholds out-of-band. Changing `judge_model` is baseline-affecting: the gate refuses to
run (exit 2) if the pin doesn't match the harness judge (D-CI-3).

## Demonstration: the routing regression the output judge can't see

The demo feature (already on this branch): Nova must verify the customer's account via
`get_account_info` **before** stating refund eligibility (`COORDINATOR_INSTRUCTION`,
REFUND-ELIGIBILITY rule + reinforcing RULES bullet — the both-defenses pattern). The trace
assertion lives in `eval/routing_cases.py` (RT1: verified earlier in session; RT2: cold ask).

Red→green sequence, once the gate is enabled on `main`:

1. Confirm green on `main`: full run → `routing_discipline = 1.0` → re-baseline if needed.
2. Branch `demo/routing-regression`; make the *plausible simplification*: in
   `src/novacrm_agent/agents/coordinator.py` delete
   - the entire `- REFUND-ELIGIBILITY question — …` block in step 2, and
   - the `- Never state whether THIS customer can get a refund …` RULES bullet.
   Open a PR.
3. The PR comment shows correctness/helpfulness/persona green, `routing_discipline` red
   (RT2 answers policy without a lookup) → **hard gate fails, PR blocked**. That contrast is
   the entire pitch: 96% output accuracy masking a process-compliance failure (the P4 finding,
   reproduced as a caught regression).
4. Restore the two prompt blocks on the branch → gate green. Keep the branch (unmerged) so the
   red→green story replays on command.

## Cost / runtime honesty

- `pip install -r requirements.txt` pulls torch + chromadb (minutes on a cold runner; the pip
  and HuggingFace caches amortize it). The RAG store is rebuilt each run (`rag.ingest`) because
  `data/rag_store/` is gitignored.
- Judge pacing is 5 s/call under the Groq free tier (`JUDGE_DELAY_S`): smoke ≈ 11 cases ×
  3 samples ≈ 3 min of judge time plus agent latency. The spec's "< 2 min" target assumes a
  paid judge tier; knobs are `judge_samples` (baselines.json) and `JUDGE_DELAY_S` (run_eval.py).
- Smoke-on-PR / full-on-main keeps token cost bounded (D-CI-4); safety and routing cases run on
  every PR because those regressions must never merge.

## Repo-mapping notes (deviations from the spec's abstract names)

- The spec's `structural_eval.py` / `llm_judge.py` / `trajectory_eval.py` correspond here to
  `structural()` + `judge()` in `run_eval.py` and the trace assertions in
  `tier_discipline.py` / `routing_cases.py`. None were modified.
- The spec's two demo golden cases are **trace-asserted routing cases** (RT1/RT2 in
  `routing_cases.py`, tagged `routing`), not judge-golden cases — the judge can't see the
  trace, and `routing_discipline` is exactly the metric that gates them.
- Path filter (`D-CI-5`) uses this repo's real layout (`src/novacrm_agent/**`, `eval/**`,
  `data/knowledge_base/**`, `requirements.txt`) instead of the spec's illustrative
  `**/prompt.py` / `agent/**`.
- The refund rule is worded **account-dependent** (billing cycle, purchase date, plan) rather
  than strictly tier-dependent: the KB's refund policy ("within 14 days of initial purchase,
  pro-rated") is account-relative, and the KB is human-owned (D3) so no corpus change was made.
  The trajectory requirement — verified lookup before the eligibility statement — is identical.
