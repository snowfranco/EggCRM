---
doc_title: Contacts API
doc_type: api_reference
---

# Contacts API

The Contacts API manages contact records. Requires Professional+ and an API key with the relevant
permission. Base URL: `https://api.eggcrm.com/v1`.

## The contact object
| Field | Type | Notes |
|-------|------|-------|
| `id` | string | EggCRM contact id, e.g. `con_8f2a1c`. Read-only. |
| `name` | string | Full name. |
| `email` | string | Unique per account; used for de-duplication. |
| `phone` | string | Optional. |
| `company` | string | Optional. |
| `owner_id` | string | User id of the owning team member. |
| `tags` | array | List of tag strings. |
| `custom_fields` | object | Keyed by custom field name. |
| `created_at` / `updated_at` | string | ISO 8601 UTC. Read-only. |

## Endpoints
- `GET /v1/contacts` — list contacts (paginated; see API Overview).
- `GET /v1/contacts/{id}` — retrieve one contact.
- `POST /v1/contacts` — create a contact. `email` is required.
- `PATCH /v1/contacts/{id}` — update fields on a contact.
- `DELETE /v1/contacts/{id}` — delete a contact (recoverable for 30 days).

## Create example
```
POST /v1/contacts
Authorization: Bearer nova_sk_live_xxxxxxxx
Content-Type: application/json

{ "name": "Dana Lee", "email": "dana@example.com", "tags": ["lead"] }
```
Returns `201 Created` with the new contact object. Posting an email that already exists returns
`409 Conflict` — use `PATCH` to update the existing record instead.

## Filtering
`GET /v1/contacts?tag=vip&updated_since=2026-01-01T00:00:00Z` filters by tag and modification
time. Filtering by custom field uses `custom_fields.<name>=<value>`.

## Errors
See **API Rate Limits & Errors** for the full status-code list. Validation failures return
`400 Bad Request` with a JSON body describing the offending field.
