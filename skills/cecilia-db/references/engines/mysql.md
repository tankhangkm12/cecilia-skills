# MySQL (InnoDB) — engine notes

Version matters: state it (`SELECT VERSION();`) and cite dev.mysql.com/doc/refman/<version>/ for anything
that matters. Notes assume MySQL 8.0+ with InnoDB. MariaDB diverges in many of these — treat it as its
own engine (`_new-engine.md`).

## Types and keys
- Money `DECIMAL(19,4)` or `BIGINT` minor units; time `DATETIME(3)` stored in UTC (or `TIMESTAMP` with its
  2038 limit); pure dates `DATE`.
- The primary key is the clustered index: a random UUID PK scatters inserts across pages. Prefer an
  ordered key (auto-increment, or time-ordered UUID stored as `BINARY(16)` — `UUID_TO_BIN(uuid, 1)` swaps
  the time parts of a v1 UUID).
- `utf8mb4` everywhere; index key length limits apply to long `VARCHAR` — use prefix indexes knowingly.

## Indexes
- Every secondary index carries the primary key columns; a wide PK makes every index wide.
- Functional indexes (8.0.13+), descending indexes (8.0), `INVISIBLE` indexes (8.0) to test a drop safely.
- `EXPLAIN FORMAT=TREE`; `EXPLAIN ANALYZE` executes the query (8.0.18+).

## Online DDL
- `ALGORITHM=INSTANT` for adding columns (8.0.12+; any position 8.0.29+), `INPLACE` with `LOCK=NONE` for
  many index operations, `COPY` rebuilds the table. State the algorithm explicitly so MySQL errors instead
  of silently falling back to a heavier one.
- Every DDL needs a metadata lock: a long transaction blocks it, and everything queues behind it.
  `SET SESSION lock_wait_timeout = <small>` in the migration.
- Big tables: `gh-ost` or `pt-online-schema-change` (tools to install — A3, run by devops/Cecilia).

## Partitioning
- `RANGE`, `LIST`, `HASH`, `KEY`, `RANGE COLUMNS`. Every unique key (including the PK) must include all
  partition key columns. Partitioned InnoDB tables do not support foreign keys.
- Retention: `DROP PARTITION`; future periods: `REORGANIZE PARTITION pmax INTO (...)` from a scheduled
  Event or external job.

## DB-side code
- Stored procedures, functions, triggers (several per event with `FOLLOWS`/`PRECEDES`), Events
  (`event_scheduler=ON`). Triggers and functions cannot commit or run DDL.
- No materialized views: summary tables maintained by a job or trigger.
- Tests: integration tests on a real container.

## Observability
- Slow query log (`long_query_time`), `performance_schema`, `sys` schema views
  (`sys.statement_analysis`, `sys.schema_unused_indexes`, `sys.innodb_lock_waits`).

## Connections and timeouts
- Thread per connection; `max_connections` (default 151). Poolers: ProxySQL, cloud proxies.
- `max_execution_time` (SELECT only), `innodb_lock_wait_timeout` (row locks, default 50 s),
  `lock_wait_timeout` (metadata locks, default one year — always set it for DDL), `wait_timeout`.

## Memory and durability
- `innodb_buffer_pool_size` is the main lever; `innodb_redo_log_capacity` (8.0.30+).
- `innodb_flush_log_at_trx_commit=1` and `sync_binlog=1` for durability; anything else is a data-loss
  trade-off Cecilia accepts in writing.
