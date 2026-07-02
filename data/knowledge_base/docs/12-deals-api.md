---
doc_title: Deals API
doc_type: api_reference
---

# Deals API

The Deals API manages deals and their pipeline stages. Requires Professional+ (pipelines
themselves require Professional+) and an API key. Base URL: `https://api.eggcrm.com/v1`.

## The deal object
| Field | Type | Notes |
|-------|------|-------|
| `id` | string | e.g. `deal_3b9d77`. Read-only. |
| `title` | string | Deal name. |
| `amount` | number | Deal value, in account currency. |
| `currency` | string | ISO 4217, e.g. `USD`. |
| `pipeline_id` | string | The pipeline the deal belongs to. |
| `stage_id` | string | Current stage. |
| `contact_id` | string | Associated contact. |
| `owner_id` | string | Owning user. |
| `expected_close` | string | ISO 8601 date. |
| `status` | string | `open`, `won`, or `lost`. |
| `created_at` / `updated_at` | string | Read-only. |

## Endpoints
- `GET /v1/deals` — list deals (filter by `pipeline_id`, `stage_id`, `status`, `owner_id`).
- `GET /v1/deals/{id}` — retrieve a deal.
- `POST /v1/deals` — create a deal. `title`, `amount`, and `pipeline_id` are required.
- `PATCH /v1/deals/{id}` — update fields, including moving stage via `stage_id`.
- `POST /v1/deals/{id}/move` — convenience endpoint to move a deal to a stage:
  `{ "stage_id": "stg_qualified" }`. Stage changes are written to deal history and the
  contact timeline, and can fire workflow automations.

## Pipelines and stages (read)
- `GET /v1/pipelines` — list pipelines and their ordered stages (including each stage's default
  win probability). Pipelines are configured in the app under **Settings > Pipelines**, not via
  the API.

## Forecast
Weighted forecast value is `amount * stage_probability`. The API returns `amount`; compute
weighted value client-side, or use the in-app Forecast report (advanced forecasting dashboards are
Enterprise-only — see **Reporting & Analytics**).
