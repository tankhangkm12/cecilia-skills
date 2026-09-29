# Security, validation, logging, observability

## A. Validation & security
- Everything from outside the process is untrusted until validated: body, query, params, headers, queue
  messages, partner responses, env, uploads.
- Declarative validation on DTOs (class-validator + `ValidationPipe({whitelist, forbidNonWhitelisted, transform})`,
  Pydantic v2 `extra="forbid"`, Bean Validation `@Valid`). Unknown fields rejected/stripped (mass assignment).
  After validation, services trust the types.
- Syntax validation ≠ business rules ("email format" in DTO; "email not taken" in service → ConflictException).
- Always bound: string lengths, numeric min/max, real enums, array sizes, page size, upload mime + size +
  extension, date ranges (`from ≤ to`).
- AuthN and authZ are separate layers. Role checks at controller guards; **ownership checks in the service /
  query** (`findByIdAndOwner(id, userId)`; not found → 404 to avoid leaking existence) — prevents IDOR.
- Short-lived JWT + revocable refresh token stored server-side; no sensitive data in JWT payloads (signed,
  not encrypted); service-to-service via mTLS or scoped internal tokens; never trust client `X-User-Id`.
- Secrets only via config module, validated at boot, no defaults; `.env` git-ignored; passwords bcrypt/argon2;
  never home-made crypto; PII encrypted at rest when docs require.
- Injection: parameterized SQL always; dynamic sort/filter columns from a fixed whitelist; cast NoSQL inputs
  (`{$ne:null}`); no user input in shell commands; SSRF whitelist + block private IPs; normalize paths, block `..`;
  explicit CORS origins with credentials; rate limits on login/OTP/expensive creates; security headers;
  constant-time comparison for tokens/signatures.

## B. Logging & observability
- Structured JSON logs via `AppLogger`: `timestamp` (UTC), `level`, `service`, `requestId` (from context),
  `message` (English, short, lowercase), `context` object; microservices add `traceId`, `spanId`, `eventId`.
- Levels: debug (investigation details) · info (business events: order created, payment succeeded, event
  published) · warn (recovered anomaly: retry, fallback) · error (needs a human).
- Where: one line per request at the edge (middleware) · each outbound call in adapters · key business
  decisions (state change, rejection). Not in hot loops, not every micro-step, not whole entities "just in case".
- Redaction in the logger wrapper by key list: password, passwordHash, token, accessToken, refreshToken,
  apiKey, secret, authorization, full card number, CVV, OTP, national id, session cookie. Masked forms if
  needed (`u***@x.com`, `****1234`). Full stack traces server-side only.
- `/health` liveness (no DB dependency) and `/health/ready` readiness (DB, broker, cache).
- Metrics hooks if Prometheus/OTel exists: requests by endpoint/status, p95/p99 latency, outbound latency,
  consumer lag, DLQ size. Do not build dashboards unless asked.
- Handlers for unhandled rejections/exceptions log and exit cleanly; graceful shutdown on SIGTERM: stop
  intake → finish in-flight → close DB/broker → exit.
