# Writing and running tests

Frameworks come from the repo. None → ask with researched options. Follow the repo's test layout; else:
co-located `*.spec.ts` / `tests/` mirroring `src/` (Python) / `src/test/java` (Java).

## 1. Common rules
- Name by behaviour + condition: `should reject cancel when order is shipped` / `test_cancel_raises_when_shipped` /
  `shouldRejectCancel_whenOrderIsShipped`. Put covered IDs in the name or a comment (`// FR-05 AC-07`).
- Arrange–Act–Assert separated by blank lines; one behaviour per test; happy and error paths in separate tests.
- Parametrize repeated rules (`it.each`, `pytest.mark.parametrize`, `@ParameterizedTest`).
- Deterministic: inject/freeze clock, seed random, fixed ids; no dependency on test order or wall time; no
  `sleep` for sync (poll with timeout / await events).
- Assert observable behaviour and contracts (return values, persisted state, emitted events, HTTP status,
  errorCode, envelope), not private calls or call counts of internals.
- Never mock the unit under test. Mock at ports/boundaries in unit tests only.
- Each test creates and cleans its own data; no shared mutable fixtures; never real production data.
- Comments: docstring/TSDoc for shared fixtures/helpers; why-comments for non-obvious setup; doc references.

## 2. Unit
Target services/use cases/domain rules/mappers with logic. Mock repository ports, publishers, gateways,
clock, id generator (ports make this easy). Cover happy path, every thrown error, boundaries (empty, null,
0, negative, max, expired). Stack notes: Jest/Vitest with `Test.createTestingModule` + mocked ports (NestJS);
pytest + `AsyncMock(spec=Port)` (Python); JUnit 5 + Mockito + AssertJ without Spring context (Java).

## 3. Integration
Real DB/broker via the repo's approach (Testcontainers, docker-compose test profile, in-memory only if the
repo already accepts it). Verify: repository queries and mappings, unique/check constraints and their
translation to errorCodes, transactions/rollback, outbox rows, consumer idempotency (same event twice), adapter
error translation with a stubbed HTTP server (WireMock/MSW/respx/nock per repo). Migrations applied from
scratch in test setup.

## 4. API / contract
Against a running app in the approved environment. Check per endpoint: status, envelope shape
(`success,data,message,errorCode,requestId,timestamp`), `X-Request-Id` header, schema vs OpenAPI (validator
if available), errorCode for every documented error, auth (anonymous/wrong role/other owner), validation
(missing, bounds, unknown fields), pagination caps and stable ordering, Idempotency-Key replay/conflict.
Tools per repo: supertest/pactum, pytest+httpx, REST Assured, Postman/Newman collections, or Postman MCP when
available (export the collection into the repo only if approved).

## 5. E2E
Only critical journeys from UCs; stable selectors (roles/labels/test ids), no brittle CSS/xpath; network
stubbing only where the docs allow; screenshots/traces on failure; cover UI states from the design. Tools per
repo (Playwright, Cypress, Selenium). Concurrency across two browser sessions for CORE flows when feasible.

## 6. Performance & basic security
**Performance:** only in an approved non-production environment, and each run there is an A3 action; scenarios from NFRs (e.g. p95 < 300 ms at
200 rps for GET /orders); warm-up, steady load, spike if NFR mentions peaks; record p50/p95/p99, throughput,
error rate, resource notes; compare to target; tools per repo or approved (k6, JMeter, Locust, Gatling).
Scripts committed under the repo's perf folder.

**Basic security** (never against production or third parties; stop immediately if real data exposure is
found and report): authZ/IDOR across users and roles · authentication (missing/expired/tampered token) ·
input validation and injection probes on parameters incl. sort/filter · mass assignment (extra fields) ·
rate limits on login/OTP · sensitive data in responses/logs/errors (stack traces, SQL) · security headers/CORS ·
file upload type/size · dependency audit command of the ecosystem (`npm audit`, `pip-audit`, OWASP
dependency-check) if available. Map findings to OWASP Top 10 / ASVS category.

## 7. Run report details section
```markdown
## Environment
<branch/commit, app version, env URL, DB, data seed, tool versions>
## Commands
<exact commands>
## Results
| Level | Total | Pass | Fail | Blocked | Flaky |
|---|---|---|---|---|---|
## Coverage by ID
| ID | TCs | Result |
|---|---|---|
## Failures
| TC | Classification (product bug / test bug fixed / doc ambiguity / env) | Evidence | BUG / question |
|---|---|---|---|
## Performance
| Scenario | Target | p95 | Throughput | Errors | Verdict |
|---|---|---|---|---|---|
## Security findings
| # | Category | Endpoint/area | Evidence | Severity | BUG |
|---|---|---|---|---|---|
## Release view
<blocking bugs open? coverage gaps? verdict: ready / not ready + why>
```
