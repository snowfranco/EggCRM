# EggCRM Documentation Corpus (Project 4 RAG)

The retrieval corpus for the Project 4 RAG agent. Each file is one documentation "page" in
Markdown. **Claude-drafted, pending human sign-off** before ingest (corpus content is human-owned
per CLAUDE.md / P4-D3).

## Authoring convention (read by the chunker — P4-D4)
Every doc has YAML front-matter and `##` section headings:

```
---
doc_title: <human title>
doc_type: feature_guide | api_reference | troubleshooting
---

# <title>

## <section heading>   ← the chunker splits on these; each ## section becomes one chunk
...
```

Each chunk carries metadata `{doc_title, section, doc_type}` for vector-similarity **and**
metadata-filtered retrieval (the "both defenses" of P4-D4).

## Inventory (20 docs)

### Feature guides (`feature_guide`)
- `01-getting-started.md` — Getting Started with EggCRM
- `02-plans-and-pricing.md` — Plans & Pricing (prices, billing, **full tier-availability matrix**)
- `03-contact-management.md` — Contact Management
- `04-pipeline-management.md` — Pipeline Management (Pro+)
- `05-workflow-automation.md` — Workflow Automation (Pro+)
- `06-reporting-and-analytics.md` — Reporting & Analytics (advanced analytics = Enterprise)
- `07-integrations-overview.md` — Integrations Overview
- `08-data-export-and-management.md` — Data Export & Management
- `09-security-and-access.md` — Security & Access Control (SSO/SAML = Enterprise)
- `20-service-levels-and-support.md` — Service Levels & Support (SLA, channels, escalation map)

### API reference (`api_reference`)
- `10-api-overview-and-auth.md` — API Overview & Authentication (API access = Pro+)
- `11-contacts-api.md` — Contacts API
- `12-deals-api.md` — Deals API
- `13-webhooks-api.md` — Webhooks API (custom webhooks = Enterprise)
- `14-rate-limits-and-errors.md` — API Rate Limits & Errors

### Troubleshooting (`troubleshooting`)
- `15-login-and-access-troubleshooting.md` — Login & Account Access
- `16-billing-and-plan-changes.md` — Billing & Plan Changes (refund/cancel escalation rules)
- `17-dashboard-performance.md` — Dashboard Performance (**9–11 AM ET known issue**)
- `18-email-sync-troubleshooting.md` — Email Sync & Integration
- `19-data-export-troubleshooting.md` — Data Export

## Consistency contract (P4-D3)
This corpus is a strict **superset** of `data/knowledge_base/novacrm_kb.json` with **no
contradictions**: prices ($29/$79/$149 monthly; 20% annual), storage (5GB/50GB/unlimited), the
exact tier-availability matrix, billing/upgrade/downgrade/refund/cancellation/SLA policies, the
9–11 AM ET dashboard known-issue, and the six escalation teams all match. New material (API
endpoints, error codes, rate limits, roles, retention windows) is additive and internally
consistent. Account-specific state (the four mock accounts) is deliberately **not** baked into the
corpus — that's owned by the account/ticketing tools (non-shadow rule).

## Invented-but-consistent details to confirm at sign-off
These were not in the prior KB; they're plausible and internally consistent, but flag any you'd
rather change: API base URL `https://api.eggcrm.com/v1`; rate limits 1,000/hr (Pro) and
10,000/hr (Enterprise); 14-day Professional trial; 12-char password minimum; 30-day deleted-record
recovery window; 30-minute lockout; webhook 24-hour retry / 5-second response / HMAC-SHA256 signature.
