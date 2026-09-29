# API contract — envelope, errors, requestId, REST, DTOs, events

The API doc (`*-api.md` / `*-api.yaml`) wins over this file. This is the default when tensura/docs/repo are silent (still
confirm with Cecilia if the repo has no envelope yet — it is a contract decision).

## 1. Envelope — every business endpoint
```json
{ "success": true, "data": { "id": "usr_01H8X" }, "message": "OK", "errorCode": null,
  "requestId": "req_01H8XKPM3QF9", "timestamp": "2026-08-30T09:14:22.117Z" }
```
Failure: `success:false, data:null, message:<human>, errorCode:"USER_NOT_FOUND"`.
Validation: `data: { "fields": [ { "field": "email", "code": "INVALID_FORMAT", "message": "…" } ] }`, `errorCode: "VALIDATION_FAILED"`.
Paged: `data: { "items": [], "pagination": { "page": 1, "pageSize": 20, "totalItems": 137, "totalPages": 7 } }`;
cursor: `pagination: { "nextCursor": "…", "hasMore": true, "limit": 20 }`.

Rules: `success` ⇔ 2xx · `data` null on error · `message` for humans (i18n OK, never parsed) · `errorCode`
UPPER_SNAKE, null on success · `requestId` always · `timestamp` ISO-8601 UTC ms.
**The envelope is built by a shared interceptor/filter/middleware, never by each controller.**

Closed exemption list (do not add cases): binary/file/stream responses · SSE/WebSocket/long-poll ·
health/readiness/liveness · `/metrics` · inbound third-party webhooks · OAuth redirects/3xx · mandated
standards (`.well-known`, OpenID discovery). Exempt endpoints still set `X-Request-Id` and errors still
go through the global handler (in the format the receiver expects).

## 2. Error codes
`<DOMAIN>_<SITUATION>` in one catalog (enum/const); each code fixed to one HTTP status; published codes
never change without approval; 5xx messages generic (no stack, SQL, table names, paths).
VALIDATION_FAILED 400 · UNAUTHENTICATED 401 · PERMISSION_DENIED 403 · USER_NOT_FOUND 404 ·
EMAIL_ALREADY_EXISTS / ORDER_ALREADY_PAID 409 · INSUFFICIENT_BALANCE 422 · RATE_LIMIT_EXCEEDED 429 ·
INTERNAL_ERROR 500 · PAYMENT_GATEWAY_UNAVAILABLE 502 · SERVICE_TIMEOUT 504.

## 3. requestId
```
Client/Gateway ─X-Request-Id?─► middleware: reuse or generate (uuid v7/ulid), store in context
  ├─► every log line of the request
  ├─► every outbound HTTP header X-Request-Id
  ├─► every published message header
  ▼
Response: envelope.requestId + X-Request-Id header
```
Generated at the edge, never in services; propagated implicitly (Node `AsyncLocalStorage`, Python
`contextvars`, Java `MDC` — propagate across threads/`@Async`), never passed as function arguments;
crosses Kafka/RabbitMQ/gRPC/TCP; equals traceId when OpenTelemetry is present.

## 4. REST conventions
Plural kebab nouns `/api/v1/user-profiles/{id}/orders` · version in path; breaking change → new version ·
GET (no side effects) / POST (create or action) / PATCH / PUT / DELETE · 200, 201, 202; **no 204**
(envelope → 200 + `data:null`) · offset pagination `?page=&pageSize=&sort=createdAt:desc` default; cursor
for large/fast-changing/infinite lists (opaque base64 cursor; stable sort with unique tiebreaker
`createdAt desc, id desc`) · hard server cap on page size (e.g. 100) · named filters `?status=ACTIVE` ·
actions `POST /orders/{id}/cancel`.

**Idempotency-Key** for irreversible POSTs (create order, charge, send): store `(key, endpoint, body hash)
→ response` with TTL (e.g. 24h) in the same transaction as the side effect; same key + same body → stored
response, no re-execution; same key + different body → 409 `IDEMPOTENCY_KEY_REUSED`; first still running →
409 `REQUEST_IN_PROGRESS`.

## 5. DTOs
Never bind entities from requests or return them. Request DTOs carry declarative validation. Response DTOs
list only exposable fields (no `passwordHash`, `internalNote`, `costPrice`) — structural protection, not
"remember to hide". Mapping in dedicated mappers. Dates ISO-8601 UTC; money as minor-unit integer or
string + currency; ids as strings (uuid/ulid if DB ids must not leak).

## 6. Service-to-service
Events:
```json
{ "eventId": "evt_…", "eventType": "billing.invoice.created", "eventVersion": 1,
  "occurredAt": "…Z", "requestId": "req_…", "producer": "billing-service", "payload": {} }
```
Past-tense type · additive changes only; breaking → new `eventVersion` run in parallel · consumers
idempotent by `eventId` · payload sufficient so consumers need not call back.
gRPC: `.proto` is the source of truth; new fields get new numbers; removed numbers `reserved`; standard
status codes + our errorCode in details; requestId in metadata.
Internal REST/TCP: same envelope; timeout + circuit breaker mandatory.

## 7. API documentation
Generated from code (decorators, springdoc, FastAPI) and kept consistent with `*-api.yaml`; each
endpoint declares possible errorCodes and examples. Do not create extra doc pages unless asked.
