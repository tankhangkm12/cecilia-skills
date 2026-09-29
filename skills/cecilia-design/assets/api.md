# <unit> — API contract

> Updated: <YYYY-MM-DD> · Inputs: `<module>-design.md`, `<unit>-database.md` · Machine file: `<unit>-api.yaml` (OpenAPI 3.1) · Base path: `/api/v1/<service>`

## 1. Conventions
| Item | Rule |
|---|---|
| Auth | |
| Content-Type | |
| Time format | |
| Response shape | |
| Pagination | |
| Sorting | |
| Idempotency | |
| Naming | |

## 2. Endpoints
| # | Method | Path | Purpose | Permission (with ownership) | LLD § / FR | Screens | Status codes |
|---|---|---|---|---|---|---|---|

## 3. Cross-check with stage 4
| Stage 4 decision | DB demand | DDL OK? | Action |
|---|---|---|---|

## 4. Endpoint details
### 4.1 `POST /orders` — <purpose>
Permission: · Idempotent: · LLD §: · FR/AC:

Request
| Field | Type | Required | Constraints | Example |
|---|---|---|---|---|

Response `201`
| Field | Type | Description |
|---|---|---|

Errors
| HTTP | errorCode | When |
|---|---|---|

## 5. Shared error codes
| Code | HTTP | Meaning | User message |
|---|---|---|---|

## 6. Doubts
## 7. Assumptions & risks
