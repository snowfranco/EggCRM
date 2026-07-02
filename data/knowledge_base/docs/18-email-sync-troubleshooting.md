---
doc_title: Email Sync & Integration Troubleshooting
doc_type: troubleshooting
---

# Email Sync & Integration Troubleshooting

## When email stops syncing to timelines
Email integration logs messages to contact timelines on every plan. If new email stops appearing:
1. Check **Settings > Integrations** — is the mailbox connection still **Active**, or has it
   errored (often because the mailbox password/OAuth token changed or expired)?
2. **Reconnect** the mailbox (re-authorize Gmail OAuth on Professional+, or re-enter IMAP/SMTP
   credentials). Reconnecting resumes sync from the time of reconnection.
3. Confirm the contact exists and the email address matches — mail to/from an address with no
   matching contact won't appear on a timeline.

## Integration won't connect (Slack, Gmail, Zapier, webhooks)
First confirm the integration is **available on the customer's plan**:
- Slack and Gmail require **Professional or higher**.
- Zapier and custom webhooks are **Enterprise-only**.
A customer on Starter trying to connect Slack, or on Professional trying Zapier, is hitting a
**tier limit, not a bug** — point them to **Plans & Pricing**.

If the plan does include the integration but it still won't connect:
1. **Verify the API key permissions** — an under-scoped or revoked key is the most common cause.
2. **Check the integration status page** for an active incident on that provider.
3. Re-authorize the connection from **Settings > Integrations**.

## Zapier / API connections failing
For Zapier (Enterprise) or direct API clients, a `401` means the API key is missing/invalid and a
`403` means the key lacks permission or the feature isn't on the tier. Regenerate the key under
**Settings > Integrations > API Keys** and re-authorize. See **API Overview & Authentication** and
**API Rate Limits & Errors**.

## Webhook deliveries failing (Enterprise)
If a registered webhook isn't firing, check the endpoint's **delivery log** under **Settings >
Integrations > Webhooks**. EggCRM retries non-2xx responses with backoff for up to 24 hours;
a persistently failing endpoint should return a `2xx` within 5 seconds and verify the
`X-EggCRM-Signature`. See **Webhooks API**.

## When to escalate
Complex API issues and SSO/SAML configuration go to the **integrations team**. Confirmed,
reproducible bugs (with steps) go to **engineering** via a support ticket.
