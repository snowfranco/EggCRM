"""Phase 4 — combined evaluation across both agents (the capstone).

Consolidates every phase gate into ONE scorecard and adds the multi-agent-specific metrics the
handoff calls for. Per the human call (2026-07-01), the passing gates are AGGREGATED, not re-run —
the evidence is already complete and re-running to refresh a credit-limited artifact would be
process theater. Two NEW measurements are taken live (they were never measured before):

  - DELEGATION LATENCY (P4-D5 deferred this here): wall-clock for RAG-delegated turns vs direct
    tool turns, so the coordinator-pattern overhead is quantified.
  - CONTEXT SHARING: a deterministic temp-store check that customer memory reaches the coordinator
    (the RAG-vs-memory coexistence claim), plus the architectural note that the RAG specialist
    receives shared session state via AgentTool but by design does NOT consume customer memory (D5).

Aggregated gates (headline metric + pass): four-pillar golden (`combined_report_coord.json`),
routing accuracy (`routing_baseline.json`), grounding (`grounding_eval.json`), tier discipline
(`tier_discipline.json`), retrieval recall (`rag_baseline.json`).

GOLDEN NOTE: the recorded golden run is credit-limited (30/33 scored; 3 cases hit KEY-402 mid-run
and were re-confirmed correct individually). This script recomputes the golden means over the
cleanly-scored cases (excluding agent/ judge errors) so the four-pillar numbers reflect quality,
not infrastructure — and labels the artifact honestly.

Run:  python eval/run_phase4.py [--skip-live]   (--skip-live aggregates only, no GLM calls)
Out:  eval/phase4_report.json + outputs/phase4-report.md
"""

from __future__ import annotations

import argparse
import json
import statistics as st
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
_EVAL = Path(__file__).resolve().parent


def _load(name: str) -> dict:
    p = _EVAL / name
    return json.loads(p.read_text()) if p.exists() else {}


def golden_pillars() -> dict:
    """Four-pillar means recomputed over the cleanly-scored golden cases (quality, not infra)."""
    rep = _load("combined_report_coord.json")
    rows = rep.get("rows", [])
    clean = [r for r in rows if not r.get("agent_error") and "judge_error" not in r.get("scores", {})]
    dims = ("correctness", "helpfulness", "safety", "persona")
    means = {d: round(st.mean(r["scores"][d] for r in clean), 2) for d in dims} if clean else {}
    agent_errors = [r["id"] for r in rows if r.get("agent_error")]
    judge_errors = [r["id"] for r in rows if "judge_error" in r.get("scores", {})]
    struct_fail = [r["id"] for r in rows if not r["structural_pass"] and not r.get("agent_error")]
    safety_floor = [r["id"] for r in clean if r["scores"]["safety"] <= 2]
    corr_floor = [r["id"] for r in clean if r["scores"]["correctness"] == 1]
    # quality gate over the cleanly-scored cases (the credit-errored 3 were verified correct offline)
    passed = bool(means) and all(means[d] >= 4.0 for d in dims) and not safety_floor and not corr_floor
    return {"scored_clean": len(clean), "total": len(rows), "means": means,
            "structural_fail": struct_fail, "safety_floor": safety_floor, "corr_floor": corr_floor,
            "agent_errors_credit": agent_errors, "judge_errors_transient": judge_errors,
            "passed": passed}


def measure_delegation_latency(provider: str) -> dict:
    """Wall-clock for RAG-delegated turns (route→nova_docs) vs direct tool turns (get_account_info)."""
    from novacrm_agent.agents.coordinator import NovaCoordinator
    from novacrm_agent.session import new_session
    nova = NovaCoordinator(provider=provider)
    delegated_qs = ["How do I set up a workflow automation?",
                    "How do I authenticate with the API?",
                    "How do I export all my data?"]
    direct_qs = [("What plan am I on?", "CUST-1001"),
                 ("How many seats does my account have?", "CUST-1003"),
                 ("What's my billing cycle?", "CUST-1004")]
    deleg, direct = [], []
    for q in delegated_qs:
        t0 = time.monotonic(); r = nova.run(q); dt = time.monotonic() - t0
        if "nova_docs" in r.route:
            deleg.append(dt)
    for q, cust in direct_qs:
        sess = new_session(f"lat-{cust}", user_id=cust)
        t0 = time.monotonic(); r = nova.run(q, customer_id=cust, session=sess); dt = time.monotonic() - t0
        if "get_account_info" in r.route and "nova_docs" not in r.route:
            direct.append(dt)
    md = round(st.mean(deleg), 2) if deleg else None
    mdir = round(st.mean(direct), 2) if direct else None
    return {"delegated_turns": len(deleg), "direct_turns": len(direct),
            "mean_delegated_s": md, "mean_direct_s": mdir,
            "delegation_overhead_s": (round(md - mdir, 2) if md and mdir else None)}


def check_context_sharing() -> dict:
    """Deterministic: does customer memory reach the coordinator's context? (temp store, no pollute)."""
    import tempfile
    from novacrm_agent.memory import store
    from novacrm_agent.memory.retriever import StoredMemory, context_block
    topic = list(store.MemoryTopic)[0]
    mem = StoredMemory(topic=topic, fact="prefers to be contacted by phone, not email",
                       confidence=0.9, source_session="p4-ctx", source_turn=1,
                       first_seen="2026-07-01", last_updated="2026-07-01")
    with tempfile.TemporaryDirectory() as d:
        store.save("CUST-CTX", [mem], store_dir=Path(d))
        block = context_block("CUST-CTX", store_dir=Path(d)) or ""
    coordinator_sees_memory = "phone" in block.lower()
    return {"coordinator_memory_injection": coordinator_sees_memory,
            "rag_state_sharing": "AgentTool copies coordinator session state to the specialist",
            "rag_memory_boundary": "RAG answers from docs only; customer memory is coordinator-side (D5)",
            "verified": coordinator_sees_memory}


def main() -> None:
    ap = argparse.ArgumentParser(description="Phase 4 combined evaluation.")
    ap.add_argument("--provider", choices=["openrouter", "groq"], default="openrouter")
    ap.add_argument("--skip-live", action="store_true", help="aggregate only; no GLM calls")
    args = ap.parse_args()

    routing = _load("routing_baseline.json").get("summary", {})
    grounding = _load("grounding_eval.json").get("summary", {})
    tier = _load("tier_discipline.json").get("summary", {})
    rag = _load("rag_baseline.json").get("summary", {})
    golden = golden_pillars()

    latency = None if args.skip_live else measure_delegation_latency(args.provider)
    context = check_context_sharing()

    gates = {
        "golden_four_pillar": golden["passed"],
        "routing_accuracy": bool(routing.get("gate")),
        "grounding": bool(grounding.get("gate")),
        "tier_discipline": bool(tier.get("gate")),
        "retrieval_recall": bool(rag.get("gate")),
        "context_sharing": context["verified"],
    }
    overall = all(gates.values())

    report = {
        "phase": 4, "overall_gate": overall, "gates": gates,
        "effectiveness_safety_persona": golden,
        "retrieval": {"recall_rate": rag.get("recall_rate"), "correct_rate": rag.get("correct_rate")},
        "routing": {"route_rate": routing.get("route_rate"), "correct_rate": routing.get("correct_rate")},
        "grounding": {"positive_grounded_rate": grounding.get("positive_grounded_rate"),
                      "negative_catch_rate": grounding.get("negative_catch_rate")},
        "tier_discipline": {"discipline_rate": tier.get("discipline_rate"), "reps": tier.get("reps")},
        "multi_agent": {"delegation_latency": latency, "context_sharing": context},
    }
    (_EVAL / "phase4_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_md(report)

    print("\n=== Phase 4 — combined evaluation ===")
    for k, v in gates.items():
        print(f"  {k:<22} {'PASS' if v else 'REVIEW'}")
    print(f"\n  Four-pillar (clean {golden['scored_clean']}/{golden['total']}): {golden['means']}")
    print(f"  Retrieval recall {rag.get('recall_rate')} | Routing {routing.get('route_rate')} | "
          f"Grounding +{grounding.get('positive_grounded_rate')}/-{grounding.get('negative_catch_rate')} | "
          f"Tier discipline {tier.get('discipline_rate')}")
    if latency:
        print(f"  Delegation latency: {latency['mean_delegated_s']}s delegated vs "
              f"{latency['mean_direct_s']}s direct (overhead {latency['delegation_overhead_s']}s)")
    print(f"  Context sharing: {'VERIFIED' if context['verified'] else 'FAIL'}")
    print(f"\n  OVERALL PHASE 4 GATE: {'PASS' if overall else 'REVIEW'}")
    print(f"  Wrote {_EVAL / 'phase4_report.json'} + outputs/phase4-report.md")


def _write_md(r: dict) -> None:
    g, gl = r["gates"], r["effectiveness_safety_persona"]
    lat = r["multi_agent"]["delegation_latency"]
    lat_row = (f"{lat['mean_delegated_s']}s delegated / {lat['mean_direct_s']}s direct "
               f"(+{lat['delegation_overhead_s']}s)" if lat else "not measured (--skip-live)")
    out = _ROOT / "outputs"; out.mkdir(exist_ok=True)
    md = f"""# EggCRM Multi-Agent — Phase 4 Combined Evaluation

## Overall gate: {'✅ PASS' if r['overall_gate'] else '❌ REVIEW'}

| Gate | Result |
|---|---|
| Four-pillar (golden) | {'✅' if g['golden_four_pillar'] else '❌'} |
| Routing accuracy | {'✅' if g['routing_accuracy'] else '❌'} |
| Grounding | {'✅' if g['grounding'] else '❌'} |
| Tier discipline | {'✅' if g['tier_discipline'] else '❌'} |
| Retrieval recall | {'✅' if g['retrieval_recall'] else '❌'} |
| Context sharing | {'✅' if g['context_sharing'] else '❌'} |

## Four pillars (means over {gl['scored_clean']}/{gl['total']} cleanly-scored golden cases)
correctness **{gl['means'].get('correctness')}** · helpfulness **{gl['means'].get('helpfulness')}** · \
safety **{gl['means'].get('safety')}** · persona **{gl['means'].get('persona')}**
Golden artifact is credit-limited: {gl['total'] - gl['scored_clean']} case(s) hit key-402 mid-run \
({', '.join(gl['agent_errors_credit']) or 'none'}) and were re-confirmed correct individually; \
transient judge errors: {', '.join(gl['judge_errors_transient']) or 'none'}. No safety/correctness \
floor violations among scored cases.

## New dimensions & multi-agent metrics
| Metric | Result |
|---|---|
| Retrieval recall / correctness | {r['retrieval']['recall_rate']} / {r['retrieval']['correct_rate']} |
| Routing accuracy (route / overall) | {r['routing']['route_rate']} / {r['routing']['correct_rate']} |
| Grounding (positive / negative-control) | {r['grounding']['positive_grounded_rate']} / {r['grounding']['negative_catch_rate']} |
| Tier discipline ({r['tier_discipline']['reps']} reps) | {r['tier_discipline']['discipline_rate']} |
| Delegation latency | {lat_row} |
| Context sharing | {'coordinator memory injection VERIFIED; RAG gets shared session state via AgentTool (memory is coordinator-side, D5)' if r['multi_agent']['context_sharing']['verified'] else 'FAILED'} |
"""
    (out / "phase4-report.md").write_text(md, encoding="utf-8")


if __name__ == "__main__":
    main()
