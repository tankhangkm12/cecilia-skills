# Database-side code — procedures, functions, triggers, views, jobs

Code in the database runs next to the data and inside the transaction — powerful, and invisible to
anyone reading only the application. Use it where the database is the right place, never to hide rules.

## 1. In the database or in the application?

| Put it in the database | Keep it in the application |
|---|---|
| set-based work: aggregates, reports, window functions over many rows | business rules with branches, and rules that change often |
| integrity no single constraint can express (cross-row invariants), enforced atomically | anything calling another service, a queue, e-mail, HTTP |
| audit trail / history rows written with the change itself | anything that needs unit tests with mocks |
| derived columns (`updated_at`, search vectors) | validation whose messages the user sees |
| partition and retention jobs (`partitioning-retention.md`) | workflow and state machines (they belong in the module design) |
| summary tables / materialized views for read-heavy dashboards | |

When a case is in the middle, give Cecilia both options with cost; she decides and it is a `D-nn`.

## 2. Rules for every object

1. **In a migration**, created with `CREATE OR REPLACE` or drop-and-create, with a rollback that restores
   the previous version (keep the previous body in the down migration).
2. **Listed in the database doc §8**: name, kind, why in the DB, which migration, which test.
3. **Tested**: PostgreSQL — pgTAP or integration tests against a real container; MySQL — integration tests
   against a real container (Testcontainers / compose). Tests cover the edge the object exists for
   (the concurrent case, the empty case, the boundary of a period).
4. **Explicit about side effects**: which tables it writes, whether it can fail the caller's transaction.
5. **Least privilege**: grant `EXECUTE` to the app role; PG `SECURITY DEFINER` only with a fixed
   `search_path` (`SET search_path = pg_catalog, <schema>`), because otherwise a caller can hijack it.
6. **Versioned signature**: a procedure the app calls is a contract. Changing its parameters or result is
   a change request with the dev-be impact listed; add `v2` beside `v1`, move callers, then drop `v1`.

## 3. Triggers — only for these

| Allowed | Not allowed |
|---|---|
| audit/history rows | business decisions ("if order > X then …") |
| maintaining `updated_at` or a derived column | calling out of the database |
| enforcing a cross-row invariant the schema cannot express | creating tables or partitions (`partitioning-retention.md` §3) |
| keeping a summary table in step, when measured cheap enough | cascades nobody asked for |

Row triggers run once per row inside the statement: a bulk update of 1 M rows runs the trigger 1 M times.
Measure the write path with and without it. MySQL triggers cannot commit or run DDL; PostgreSQL
statement-level triggers with transition tables are the set-based alternative for bulk work.

## 4. Views and materialized views

- A **view** is a saved query: no speed-up by itself, useful as a stable read contract.
- A **materialized view** stores the result: say how stale it may be and who refreshes it. PG
  `REFRESH MATERIALIZED VIEW CONCURRENTLY` needs a unique index and does not block readers. MySQL has no
  materialized views — use a summary table filled by a job or trigger.

## 5. Scheduled jobs

PostgreSQL: `pg_cron` (an extension — installing it on a shared server is A3, production A4) or the app's
scheduler calling a procedure. MySQL: the Event Scheduler (`event_scheduler=ON`). Every job states its
schedule, its maximum runtime, what happens if it runs twice at once (take a lock or be idempotent), and
how its success is monitored.

## 6. Procedures vs functions (PostgreSQL)

A function returns a value and runs inside the caller's transaction; mark it `IMMUTABLE`, `STABLE` or
`VOLATILE` truthfully — a wrong `IMMUTABLE` gives wrong results from indexes and caching. A procedure
(`CREATE PROCEDURE`, PG 11+) is called with `CALL` and may `COMMIT` between batches when not called inside
an outer transaction — the right tool for batched backfills and retention.
