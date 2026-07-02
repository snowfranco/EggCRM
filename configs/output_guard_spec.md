<!--
Phase 5 output-guardrail + escalation/HITL spec — DRAFT v1 (2026-06-27), pending human review.
Defines the egress checks (guardrails/output_guard.py) and the human-in-the-loop protocol
(guardrails/escalation.py). Tested by eval/output_failure_cases.py. "Both defenses": the
output guard is the NET behind the input PII guard and the agent's own boundaries.
-->

# Output guardrails + escalation — policy spec (DRAFT)

Runs AFTER the agent produces its final response, BEFORE delivery. Returns
`{approved, reason, sanitized_output}`. The agent's response never reaches the user
unscanned.

## 1. What the output guard scans for

| Check | Detection | Action (proposed) |
|-------|-----------|-------------------|
| **PII egress** | card/SSN regex (reuse `pii_guard`), plus any other customer's email/domain | **REDACT** in place + deliver |
| **Forbidden content** | system-prompt fragments ("you are nova", "## workflow", step headers, "system prompt"); internal tool names (`escalate_to_team`, `get_account_info`, `lookup_knowledge_base`, `create_support_ticket`); model/infra names (glm, openrouter) | **BLOCK** → safe fallback |
| **Over-promising** | refund/credit "approved/processed/applied", SLA "guarantee/100% uptime", that are NOT paired with an escalation | **BLOCK** → rewrite to escalate |
| **Cross-customer data** | another customer's email/name/account fields appearing in the reply | **BLOCK** → safe fallback |
| **Grounding (optional)** | does the answer derive from KB/account/tool results? | deferred — see open Q2 |

**Safe fallback** (forbidden/cross-customer): *"I'm not able to share that. I can help with
your EggCRM account, billing, features, or support — what do you need?"*

**Rewrite-to-escalate** (over-promise): replace the unauthorized promise with the correct
escalation handoff (and fire the escalation action if not already done).

## 2. Escalation / human-in-the-loop protocol (`guardrails/escalation.py`)

When the agent calls `escalate_to_team`, the protocol:
1. Writes a structured escalation record to `data/escalations/<session_id>-<n>.json` — the
   full conversation, the tool/trace trajectory, the team, and the reason — so a human picks
   it up with complete context (the "they'll have the full context" promise made to the user).
2. Returns the customer-facing handoff message (already produced by the agent).
3. Marks the session so subsequent turns know a human is engaged (optional metadata flag).

This makes escalation a real, inspectable handoff rather than just a chat line, and gives
Phase 6's eval a queue to assert against.

## 3. Action policy per failure type (proposed — the main rulings)

Per the plan's earlier note and the redact-at-boundary principle:
- **PII egress → redact-in-place + deliver.** Don't block a useful reply over a stray pattern;
  scrub it. (The input guard should have caught most already; this is the net.)
- **Forbidden content (prompt/tool/infra leak) → block + safe fallback.** A leak is never
  acceptable; replace the whole response.
- **Over-promising → block + rewrite to escalate.** The customer still gets help (routed to the
  right team), just not an unauthorized promise.
- **Cross-customer data → block + safe fallback.** Hard stop.

## Open questions for review
1. **PII egress: redact-in-place (proposed) vs block?** I lean redact-in-place (deliver the
   useful parts); block feels heavy for an egress stray. Your call.
2. **Grounding check now or defer?** It adds an LLM call per turn and is fuzzy. I lean **defer**
   to a Phase 6 eval metric (LLM-judge "is this grounded?") rather than a per-turn gate —
   the PII + forbidden + over-promise checks cover the real leak risks. Agree?
3. **Escalation log destination** = `data/escalations/<session_id>-<n>.json` (inspectable,
   gitignored). Confirm, or do you want a single append-only queue file?
4. **Over-promise handling** = block + rewrite-to-escalate (proposed) vs flag-for-review?
