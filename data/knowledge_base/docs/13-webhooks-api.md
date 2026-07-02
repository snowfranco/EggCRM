---
doc_title: Webhooks API
doc_type: api_reference
---

# Webhooks API

Custom webhooks are **Enterprise-only**. They let EggCRM POST an event payload to a URL you
control whenever a subscribed event occurs. (Professional accounts can still trigger Slack
messages from automations, but cannot register custom webhook endpoints.)

## Registering an endpoint
Register endpoints in the app under **Settings > Integrations > Webhooks**, or via the API:
- `GET /v1/webhooks` — list registered endpoints.
- `POST /v1/webhooks` — register an endpoint: `{ "url": "https://...", "events": ["deal.won"] }`.
- `DELETE /v1/webhooks/{id}` — remove an endpoint.

## Event types
Subscribable events include: `contact.created`, `contact.updated`, `contact.deleted`,
`deal.created`, `deal.stage_changed`, `deal.won`, `deal.lost`, and `export.completed`. Subscribe
an endpoint to one or more events.

## Payload and delivery
Each delivery is an HTTP `POST` with a JSON body:
```
{ "event": "deal.won", "occurred_at": "2026-06-30T14:02:11Z", "data": { ...deal object... } }
```
Your endpoint should return a `2xx` status within 5 seconds. Non-2xx or timeout responses are
**retried with exponential backoff** for up to 24 hours, after which the delivery is dropped and
recorded as failed in the endpoint's delivery log.

## Verifying authenticity
Each delivery includes an `X-EggCRM-Signature` header — an HMAC-SHA256 of the raw body using the
endpoint's signing secret (shown once at registration). Recompute the HMAC and compare to verify
the request genuinely came from EggCRM before acting on it.

## Webhooks vs. polling
Prefer webhooks over polling the Contacts/Deals APIs for change detection — they are lower latency
and do not consume your rate-limit budget. See **API Rate Limits & Errors**.
