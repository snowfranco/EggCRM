---
doc_title: API Rate Limits & Errors
doc_type: api_reference
---

# API Rate Limits & Errors

Applies to all EggCRM REST API endpoints (`https://api.eggcrm.com/v1`). API access requires
Professional+.

## Rate limits by tier
- **Professional:** 1,000 API requests per hour, per account.
- **Enterprise:** 10,000 API requests per hour, per account.

Limits are enforced on a rolling one-hour window. Each response includes
`X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` (epoch seconds) headers so
you can pace requests.

## Exceeding the limit
Over-limit requests return `429 Too Many Requests` with a `Retry-After` header (seconds to wait).
Back off and retry after the interval; do not retry tighter than `Retry-After`.

## Standard error codes
| Status | Meaning | Typical cause |
|--------|---------|---------------|
| `400 Bad Request` | Validation error | Missing/invalid field; body explains which. |
| `401 Unauthorized` | Auth failed | Missing or invalid API key. |
| `403 Forbidden` | Not permitted | Key lacks permission, or feature not on your tier. |
| `404 Not Found` | No such resource | Wrong id or deleted record. |
| `409 Conflict` | Duplicate | e.g. creating a contact with an existing email. |
| `429 Too Many Requests` | Rate limited | See above; honor `Retry-After`. |
| `500 Internal Server Error` | Server fault | Transient — retry with backoff; if persistent, contact support. |

## Error body shape
```
{ "error": { "code": "validation_error", "message": "email is required", "field": "email" } }
```

## Best practices
Use exponential backoff with jitter on `429` and `500`. Prefer **webhooks** over polling to avoid
spending rate-limit budget on change detection (custom webhooks are Enterprise-only — see
**Webhooks API**). Cache responses where possible and request only the fields you need.
