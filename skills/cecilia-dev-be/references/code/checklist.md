# Self-review checklist (before Draft PR)

Tick what applies; groups the change does not touch → write "n/a" in your head, do not tick blindly.
🔴 = blocker (fix before PR), others = fix or explain in the PR.

## 🔴 Process
- [ ] Interview done; brief approved; every change traces to a plan ID or approved proposal
- [ ] No files outside the brief; no new/upgraded dependency; no deleted files/tables/endpoints without approval
- [ ] Test files changed only inside the approved scope, and only focused regression tests for this change (independent acceptance tests are cecilia-test's)
- [ ] Every doc gap/risk found was asked, not guessed

## 🔴 Structure & boundaries
- [ ] Layers respected (thin controllers, logic in services, ORM only in repositories/adapters)
- [ ] No import of another module's internals; no cross-module JOINs; no cross-service DB access
- [ ] Every external SDK behind a business-named port; adapters translate errors and set timeouts
- [ ] Env access only in config; clock/random/uuid injected

## 🔴 API & errors
- [ ] Envelope from shared interceptor; exemptions only from the closed list
- [ ] requestId in body + header, from context
- [ ] Domain exceptions with catalog errorCodes; one global handler; no empty catch; no 5xx leak
- [ ] Entities never bound from requests or returned; response DTOs without sensitive fields
- [ ] Page size capped; stable sort; Idempotency-Key where docs require

## 🔴 Data, money, time, concurrency
- [ ] No float money; UTC storage; `date` for pure dates
- [ ] Migration present with rollback when schema changes
- [ ] Every read-compute-write / check-then-act has the documented mechanism
- [ ] No external call inside a transaction; outbox for DB + event

## 🔴 Security
- [ ] Declarative DTO validation with whitelist; lengths/ranges/array sizes bounded
- [ ] Ownership checks (IDOR); parameterized SQL; whitelisted sort/filter columns
- [ ] No hard-coded secrets or secret defaults; sensitive fields redacted in logs

## Code quality
- [ ] Types strict (no `any` / `dict[str, Any]` payloads / `Map<String,Object>` DTOs / raw generics)
- [ ] Functions ~≤ 30 lines, nesting ≤ 2, ≤ 3 params, no flag params, no param mutation
- [ ] Names: role-suffixed files, intent-named repository methods, no banned names
- [ ] Comments: docstrings on public API, doc references, step comments in flows, why-comments; no noise, no commented-out code, no TODO without task id
- [ ] No abstraction without an external dependency or ≥ 2 real implementations
- [ ] Size signals checked (§10): file ~≤400 lines, class ≤7 public methods, ≤5 constructor deps,
      no pass-through layer — each crossing either justified in the PR or split by reason
- [ ] Any file/class already over a signal that this change touches: named in the brief, with keep-or-split stated
- [ ] Async style consistent; independent calls parallel; retries only idempotent with backoff
- [ ] Structured logs with requestId at the right places, none in hot loops
- [ ] Microservices (if any): idempotent consumers, DLQ, event versioning, breaker, trace propagation

## Delivery
- [ ] Build, lint/format, existing tests green after rebase
- [ ] Manual verification recorded in the report for every ID (not in PR)
- [ ] PR description complete; out-of-scope findings listed as proposals
