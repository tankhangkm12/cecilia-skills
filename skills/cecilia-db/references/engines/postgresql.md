# PostgreSQL — engine notes

Version matters: state it (`SELECT version();`) and cite the official docs page for the version in use
(postgresql.org/docs/<major>/). Items below name the version that introduced them.

## Types and keys
- Money `numeric(19,4)` or `bigint` minor units; time `timestamptz`; pure dates `date`.
- `uuid` type; `gen_random_uuid()` makes **v4**. UUIDv7 needs `uuidv7()` (PG 18+) or app-side generation
  — verify the function you write produces the version the design chose.
- Identity columns (`GENERATED ALWAYS AS IDENTITY`) over `serial` in new schemas.
- `jsonb` with GIN index for containment queries; do not replace columns the design needs to constrain.

## Indexes
- B-tree default; `INCLUDE` columns (11+); partial (`WHERE`); expression indexes; GIN, GiST, BRIN.
- `CREATE INDEX CONCURRENTLY` / `DROP INDEX CONCURRENTLY`: no transaction block; failure leaves `INVALID`.
- `REINDEX CONCURRENTLY` (12+) for bloated indexes.

## Locks worth knowing
- Most `ALTER TABLE` forms take `ACCESS EXCLUSIVE` — blocks reads and writes; it also waits behind any
  long transaction and everything queues behind it. Use `lock_timeout`.
- `VALIDATE CONSTRAINT` takes a weaker lock (`SHARE UPDATE EXCLUSIVE`) — reads and writes continue.
- `CREATE INDEX` (non-concurrent) blocks writes for the whole build.

## Partitioning
- Declarative `RANGE` / `LIST` / `HASH` (10+); indexes on the parent propagate (11+); primary/unique keys
  must include the partition key; foreign keys referencing partitioned tables (12+).
- `DETACH PARTITION … CONCURRENTLY` (14+). Attaching a partition scans the default partition if one exists.
- `pg_partman` (extension) for premaking and retention; `pg_cron` for scheduling. Extensions on a
  managed service: check the provider supports them.

## DB-side code
- Functions (`CREATE FUNCTION`, volatility categories); procedures (`CREATE PROCEDURE`, `CALL`, may
  `COMMIT`, 11+); triggers row/statement level, transition tables for statement triggers (10+).
- `SECURITY DEFINER` always with `SET search_path`.
- Tests: pgTAP, or integration tests on a real container.

## Observability
- `pg_stat_statements` (extension; must be in `shared_preload_libraries`), `auto_explain` for slow-plan
  logging, `pg_stat_activity`, `pg_locks`, `pg_stat_user_tables` / `_indexes`.

## Connections
- Process per connection; `max_connections` needs a restart to change. Poolers: PgBouncer, pgcat,
  RDS Proxy. Transaction-pooling limits: see `connections.md` §4.
- Timeouts: `statement_timeout`, `lock_timeout`, `idle_in_transaction_session_timeout`
  (`idle_session_timeout` 14+).

## MVCC housekeeping
- Updates and deletes leave dead tuples; autovacuum cleans them. Hot, large tables need per-table
  autovacuum settings; long transactions stop cleanup everywhere.
- `fillfactor` below 100 on update-heavy tables helps HOT updates.
