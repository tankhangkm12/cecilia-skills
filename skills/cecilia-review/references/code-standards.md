# Cecilia's code standards — review reference

Use to judge code when docs are silent. Repo linter config and established conventions win on formatting
details; architecture/boundary/security rules below are Cecilia's standard unless docs say otherwise.

**Structure:** layers — thin controllers (no logic, no try/catch formatting, no envelope building), services
hold logic and transaction scope, repositories hide the ORM behind ports named by intent, adapters wrap
SDKs. Architecture level (feature-modular → domain → clean/hexagonal) as per LLD; domain imports no
framework/ORM at level 3.

**Infrastructure wrapping:** every external dependency (broker, RPC, outbound HTTP, cache, storage, mail/SMS,
payment, ORM/driver, logger, clock/random/uuid, config/secrets, search) behind a business-named port in the
inner layer; adapters call the SDK, map models, translate errors, apply timeouts and bounded retries for
idempotent calls, log with requestId. Env read only in one validated config module (fail fast, no secret
defaults). Logger wrapped with redaction.

**Module boundaries:** no import of another module's services/repositories/entities; no JOINs into its
tables; no cross-service DB access; cross-module via narrow facade DTOs or events; snapshot "as of that
moment" data; no cycles; new inter-module dependency needs approval. Microservices: own DB, idempotent
consumers + DLQ, outbox, additive events with eventVersion, timeouts + circuit breakers, trace propagation,
thin gateway, no business logic in shared libs.

**API:** envelope `{success,data,message,errorCode,requestId,timestamp}` from a shared interceptor; closed
exemption list (binary/stream, SSE/WS, health, metrics, inbound webhooks, OAuth redirects, `.well-known`);
error codes from one catalog, fixed HTTP status, no 5xx leaks; requestId from context in body + header and
across calls/messages; plural kebab paths, versioned; no 204; capped page size, stable sort; Idempotency-Key
on irreversible POSTs; DTOs separate from entities, no sensitive response fields.

**Data:** money never float (decimal or minor units, one representation, central rounding); UTC storage,
ISO-8601 with offset, `date` for pure dates, injected clock; migrations with rollback; indexes for FKs and
filters; documented concurrency mechanism for every read-compute-write/check-then-act; no external calls in
transactions.

**Security:** declarative validation + whitelist; bounded lengths/ranges/arrays; ownership checks (404);
parameterized SQL; whitelisted dynamic columns; bcrypt/argon2; no secrets in code/JWT; explicit CORS; rate
limits on sensitive endpoints; structured logs, English messages, requestId, redaction list, no hot-loop logs.

**Code quality:** strict types (no `any`, no `dict[str, Any]` payloads, no `Map<String,Object>` DTOs, no raw
generics, Optional returns in Java); functions ~≤ 30 lines, nesting ≤ 2, ≤ 3 params, no flag params, no param
mutation; S and O first, abstractions only for external deps or ≥ 2 real implementations; domain exceptions
with a single global handler, no empty catch; files with role suffixes (TS kebab, Python snake, Java Pascal);
intent-named repository methods; banned names (`data2`, `temp`, `obj`, `doStuff`, `helper`, `utils` buckets);
comments: public docstrings, doc references (`Per LLD §x (FR-nn)`), numbered step comments in multi-step
flows, why-comments; no commented-out code, no TODO without task id; async style consistent, parallel
independent calls, timeouts everywhere.

**Git/PR:** the repo's own convention, else `feat-be/` `feat-fe/` `fix/` `refactor/` `test/` `ci/` `infra/` branches; Conventional
Commits with `[TASK]`; one logical change per commit; Draft PR with full description (context, flow, per-file
changes, doc checklist, decisions, checks, rebase notes, impact, out-of-scope proposals); no unapproved
dependency changes.
