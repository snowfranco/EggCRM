---
doc_title: API Overview & Authentication
doc_type: api_reference
---

# API Overview & Authentication

API access requires the **Professional** plan or higher. It is not available on Starter.

## Base URL and format
The EggCRM REST API is served at `https://api.eggcrm.com/v1`. All requests and responses are
JSON. Send `Content-Type: application/json` on requests with a body. Timestamps are ISO 8601 UTC.

## Generating an API key
Create a key under **Settings > Integrations > API Keys > Generate New Key**. Copy the key when it
is shown — it is displayed only once. A key inherits the permissions of the role you assign it
(read-only or read-write) and can be scoped to specific resources. Keys are listed (by prefix and
label, never the full secret) on the same page, where they can be revoked.

## Authenticating a request
Pass the key as a bearer token in the `Authorization` header:

```
GET /v1/contacts
Host: api.eggcrm.com
Authorization: Bearer nova_sk_live_xxxxxxxx
```

A missing or invalid key returns `401 Unauthorized`. A valid key without permission for the
resource returns `403 Forbidden`.

## Pagination
List endpoints return up to 50 records per page. Use `?limit=` (max 100) and `?cursor=` to page;
each response includes a `next_cursor` field that is null on the last page.

## Versioning
The API is versioned in the path (`/v1`). Breaking changes ship under a new version; non-breaking
additions (new fields, new endpoints) are made within the current version.

## Where to go next
See **Contacts API** and **Deals API** for resource endpoints, **Webhooks API** for event
delivery (Enterprise-only), and **API Rate Limits & Errors** for limits and error codes.
