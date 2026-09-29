# Cecilia's usual standards — offer as the RECOMMENDED option, never apply silently

In this skill the agent decides nothing; these are the defaults Cecilia usually picks, to put first in
option tables or in one "approve this conventions table" question.

## API

- Envelope for every business endpoint: `{success, data, message, errorCode, requestId, timestamp}`.
  `success` ⇔ 2xx · `data` null on error · `message` for humans · `errorCode` UPPER_SNAKE for machines,
  null on success · `requestId` always · `timestamp` ISO-8601 UTC with ms. Validation errors:
  `data.fields[{field, code, message}]`. Lists: `data.items` + `data.pagination`.
- Closed exemption list: file/binary/stream downloads · SSE/WebSocket · health/readiness probes ·
  `/metrics` · inbound third-party webhooks · OAuth redirects/callbacks · mandated public standards
  (`.well-known`). Exempt endpoints still send `X-Request-Id`.
- Error codes `<DOMAIN>_<SITUATION>`, one catalog, each code bound to one HTTP status; published codes
  never change. 5xx messages generic (details in logs by requestId).
  Suggested map: VALIDATION_FAILED 400 · UNAUTHENTICATED 401 · PERMISSION_DENIED 403 · X_NOT_FOUND 404 ·
  conflicts/state 409 · business rule 422 · RATE_LIMIT_EXCEEDED 429 · INTERNAL_ERROR 500 · partner 502 · timeout 504.
- `requestId`: generated/accepted at the edge (`X-Request-Id`), propagated via context, logs, outbound
  HTTP headers, message headers, gRPC metadata; returned in body and header; = traceId if OpenTelemetry.
- REST: plural kebab-case nouns, `/api/v1`, breaking change → new version; actions as
  `POST /orders/{id}/cancel`; no 204 (envelope → 200 + `data: null`); offset pagination default, cursor
  for large/fast-changing/infinite lists (opaque cursor, stable sort with unique tiebreaker); hard cap
  on page size; Idempotency-Key for irreversible POSTs.
- DTOs separate from entities in both directions; response DTOs never contain sensitive fields.
- Events: `{eventId, eventType <domain>.<entity>.<past-action>, eventVersion, occurredAt, requestId,
  producer, payload}`; additive only. gRPC: `.proto` is source of truth, `reserved` for removed fields.

## Data

- Money never float: decimal (`numeric(19,4)`) or integer minor units, one representation project-wide;
  column names state unit/currency; rounding rule is a business decision in one place; JSON sends money
  as string or minor-unit integer.
- Time stored in UTC (`timestamptz`), ISO-8601 with offset in APIs, `date` for pure dates, convert to
  local only in presentation, inject a clock.
- Tables plural snake_case; FK `<singular>_id`; time columns `_at`; enums UPPER values listed.
- Migrations always, each with a working rollback; index every FK and frequent filter/sort column.

## Security & logging

Validate at the boundary with declarative DTO rules and whitelist unknown fields · resource ownership
checked in the service/query (404 instead of 403 to avoid leaking existence) · parameterized SQL,
sort/filter columns from whitelist · no secret defaults, config validated at boot · bcrypt/argon2 ·
explicit CORS origins · rate limits on login/OTP/expensive creates · structured JSON logs with
requestId, English messages, redaction of password/token/apiKey/secret/card/CVV/OTP/national id ·
liveness without DB, readiness with dependencies · graceful shutdown.

## Code organization (for LLD "proposed code structure")

Feature-modular by default, raise level when signals appear · repository pattern hiding the ORM ·
every external dependency behind a business-named port + adapter (translates errors, timeouts,
retries, logging) · one config module · wrapped logger · module boundaries via narrow facades or events.
