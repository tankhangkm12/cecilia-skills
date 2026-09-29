# Lens: integration (cecilia-test v20)

Brief header `LENS=integration`. Shared lens rules (files, isolation, report, lane): `../workflow.md` §Lenses.

## Attacks
The seams: service to service, service to DB, broker and third-party adapter. Does each side honour the
contract the other side was built against, and does a failure on one side stay contained?

## Oracle
API/event contract (OpenAPI, AsyncAPI, schema version) · LLD sequence diagrams and error translation ·
migration files as the schema of record · NFR timeouts and retry budgets.

## Techniques
- **Contract tests** per endpoint/event: status, envelope, schema vs OpenAPI (validator if available),
  every documented `errorCode`, `X-Request-Id`, pagination and ordering (`../test-levels.md` §4).
- **Real local dependencies:** the repo's Testcontainers or compose test profile; in-memory fakes only when
  the repo already accepts them. Mock a third party with a stub server (WireMock, MSW, respx, nock).
- **Migrations from scratch** in test setup, then the queries and mappings that use them; constraint
  violations translated to the documented `errorCode`.
- **Transactions:** rollback leaves no partial rows; outbox row written in the same transaction.
- **Consumers:** same event twice → one effect; out-of-order and poison messages → documented handling.
- **Dependency failure:** timeout, 5xx, malformed body → documented fallback, no partial data.

## Files
`<repo test root>/integration/...` or suffix `.integration`. Fixtures and stub mappings in the lens folder.

## Environment
Own compose project `docker compose -p <TASK>-test-integration`, own DB `<db>_test_integration`, own
ports from RUNTIME. Tear down containers and volumes you started before reporting.

## Report
`tensura/reports/<TASK>/test-integration.md`: contract version tested, dependencies and their versions,
the table `endpoint/event · cases · result`, and the BUG table (`BUG-integration-nn`).

## Never
Call a real third-party or shared environment without Cecilia's A3 yes · change a contract or migration to
make a test pass (`HANDOFF: needs cecilia-dev-be` / `cecilia-db`) · load or race testing (`concurrency-perf`).
