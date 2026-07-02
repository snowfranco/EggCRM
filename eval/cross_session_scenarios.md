# Cross-session memory scenarios — DRAFT v1 (Phase 3), pending human review

Each scenario runs **Session 1** (which ends → extraction → store), then a **separate
Session 2** for the same customer (retriever loads memories → injects at start). The test is
that Session 2 behavior reflects what was learned in Session 1 — and that **tool-authoritative
state (plan/tier/billing) comes from the live tool, never from memory** (D5 non-shadow rule).

Legend: **[hard]** = must pass for the scenario to pass · **[soft]** = reported, model-dependent.

---

## X1 — "Any update on my bug?" (issue recall)
**Customer:** CUST-1003 (Priya / Cobalt, Enterprise)

**Session 1**
1. customer: "Hi, it's Priya at Cobalt. The dashboard keeps crashing every morning — it's really disrupting our standup."
2. agent: proposes a ticket, asks to confirm
3. customer: "Yes please, go ahead."
4. agent: creates the ticket
→ extraction should store: issue_history (dashboard crashes, ticket open) + sentiment_trajectory (frustrated) + customer_identity.

**Session 2** (new session, same customer)
1. customer: "Any update on my bug?"

**Checks**
- [hard] Session 1 extraction stored an `issue_history` memory mentioning the dashboard crash.
- [hard] Session 2 reply references the **specific** dashboard/crash issue (does not ask "what bug?").
- [soft] Session 2 tone reflects the prior frustration (empathetic / acknowledges disruption).
- [soft] If the reply mentions the plan, it matches the LIVE account (Enterprise) — i.e. from the tool, consistent with what's stored not driving it.

---

## X2 — Communication preference honored
**Customer:** CUST-1001 (Dana / Acme, Professional)

**Session 1**
1. customer: "Quick question on API keys — and going forward, please contact me by email, not phone."
2. agent: answers, acknowledges the preference
→ extraction should store: communication_preferences (prefers email).

**Session 2** (new session, same customer)
1. customer: "My email integration keeps disconnecting. Can you follow up once it's fixed?"

**Checks**
- [hard] Session 1 extraction stored a `communication_preferences` memory (email over phone).
- [hard] Session 2 reply offers follow-up **by email** specifically (honors the stored preference without being re-told).
- [soft] The agent does not ask how they'd like to be contacted (it already knows).

---

## X3 — Relationship continuity (frustration recalled) + live tier
**Customer:** CUST-1004 (Tom / Delta, Professional, account_status = payment_overdue)

**Session 1**
1. customer: "It's Tom at Delta. I was charged $480 twice this quarter and I'm pretty fed up — second billing problem in a row."
2. agent: escalates to billing
→ extraction should store: sentiment_trajectory (frustrated, churn-risk re billing) + issue_history (recurring billing problem). NOT the $480 dollar amount; NOT the `payment_overdue` account status.

**Session 2** (new session, same customer)
1. customer: "I need help setting up a new workflow automation."

**Checks**
- [hard] Session 1 extraction stored a `sentiment_trajectory` memory about billing frustration, and **no** memory containing a dollar amount or the `payment_overdue` status (D5 exclusions).
- [soft] Session 2 reply shows continuity/extra care given the prior frustration (does not pretend it's a brand-new relationship).
- [hard] Session 2 helps with the workflow question on-topic (memory enriches tone; it does not derail the actual request).

---

## Notes for the harness (when approved)
- Extraction runs at end of Session 1; assert on the stored JSON (`data/memory_store/<customer>.json`).
- Retriever injects memories as a system note at Session 2 start ("What you remember about this customer: …"), per the Day 3 "memories in system instructions" pattern.
- Plus regression: re-run the 15-case Phase 2 baseline — long-term memory must not regress it.
