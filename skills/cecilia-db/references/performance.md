# Query performance — find the cause, change one thing, prove it

Most slow queries are one of five things: a missing or unusable index, too many rows read for the rows
returned, a bad row estimate, a round-trip pattern (N+1), or waiting on a lock. Find which before
changing anything.

## 1. Find what is slow — from evidence, not intuition

| Source | PostgreSQL | MySQL |
|---|---|---|
| Top queries by total time | `pg_stat_statements` (extension) | `performance_schema` digests / `sys.statement_analysis` |
| Individual slow statements | `log_min_duration_statement` | slow query log (`long_query_time`) |
| What is running / waiting now | `pg_stat_activity` (+ `wait_event`) | `SHOW PROCESSLIST`, `sys.innodb_lock_waits` |
| Table access pattern | `pg_stat_user_tables` (seq vs idx scans) | `sys.schema_unused_indexes`, `sys.statements_with_full_table_scans` |

On a shared or production database every one of these is a read of live state: A3 for shared, A4 for
production (Cecilia runs it and gives you the output). Rank by **total** time (calls × mean), not by the
single slowest call — a 5 ms query run 2 million times a day outweighs a 3 s report run twice.

## 2. Read the plan

`EXPLAIN` shows the plan; `EXPLAIN ANALYZE` **executes the statement**. For INSERT/UPDATE/DELETE wrap it
in a transaction and roll back — and still never on production.

```sql
-- PostgreSQL
BEGIN;
EXPLAIN (ANALYZE, BUFFERS, VERBOSE) <statement>;
ROLLBACK;
-- MySQL 8.0.18+
EXPLAIN ANALYZE <select>;          -- executes; EXPLAIN FORMAT=TREE does not
```

What to look for, in order:

1. **Estimated vs actual rows** off by ≥ 10× on a node → statistics problem first (`ANALYZE` the table,
   raise statistics target on the skewed column, extended statistics for correlated columns in PG).
2. **Rows read vs rows returned.** A scan reading 2 M rows to return 20 wants an index or a better one.
3. **Sort / hash spilling to disk** (PG "external merge", "Batches: N" > 1) → the query needs an index
   that provides the order, or less data, before it needs more memory.
4. **Nested loop with a large outer side** → missing index on the inner join key, or a bad estimate.
5. **Time spent outside the plan** — the plan is fast but the endpoint is slow: N+1, network, pool wait.

## 3. Indexes — each one serves a named query

- **Column order**: equality columns first, then the range or sort column. `(tenant_id, status, created_at)`
  serves `WHERE tenant_id=? AND status=? ORDER BY created_at DESC`.
- **Covering**: include the selected columns so the table is not visited (PG `INCLUDE`, MySQL: the
  secondary index already carries the primary key; add the other columns to the key).
- **Partial / filtered** (PG `WHERE deleted_at IS NULL`) for queries that always filter the same way.
- **Expression / functional** when the query filters on `lower(email)` or a JSON path.
- **Special types** (PG): GIN for `jsonb`, arrays, full-text; BRIN for very large append-only tables whose
  physical order follows the column (time series); GiST for ranges and geometry.
- Every index costs writes and memory. An index that serves no named query is removed — MySQL can test
  that safely with an `INVISIBLE` index first; PG: check `idx_scan` over a full business cycle.
- Create on real tables without blocking writes: PG `CREATE INDEX CONCURRENTLY` (not inside a
  transaction; a failure leaves an `INVALID` index to drop), MySQL online DDL `ALGORITHM=INPLACE, LOCK=NONE`.

## 4. Query shapes that do not scale

| Shape | Why it hurts | Instead |
|---|---|---|
| N+1 — a query per row in a loop | round trips grow with the list | one query with a join / `IN (...)`, or the ORM's eager load for this use case |
| `OFFSET 100000` pagination | reads and throws away 100 000 rows | keyset: `WHERE (created_at, id) < (?, ?) ORDER BY created_at DESC, id DESC LIMIT 20` |
| `SELECT *` on wide rows | reads and ships columns nobody shows | name the columns; allows covering indexes |
| function on the indexed column (`WHERE date(created_at) = ?`) | index unusable | range on the raw column, or an expression index |
| `OR` across different columns | often one scan instead of two index lookups | `UNION ALL` of two indexed queries, if measured faster |
| `COUNT(*)` of a huge set per page view | full scan every time | estimate, cached count, or summary table (`db-code.md`) |
| implicit type cast (varchar column compared to a number) | index unusable | match the column type in the parameter |
| long transaction around user think-time or HTTP calls | holds locks and (PG) blocks vacuum | short transactions, work outside them |

## 5. Measure the change

Same database, same data size, same parameters, warm cache stated. Median of ≥ 5 runs plus the cold run;
plan before and after attached; the metric row:

`p95 GET /orders 840 ms → 38 ms — median of 7 warm runs, 2.1 M rows — EXPLAIN ANALYZE + k6 @3f2a9c1 — 2026-09-24 · M-14`

A change that helps one query and hurts writes (a new index on a hot insert table) states both numbers.

## 6. Hand-off to dev-be

The fix often lives in application code: the query the ORM builds, a missing eager load, a loop. Write it
as a "For other roles" line naming file, query and the shape to use; `cecilia-dev-be` changes the code.
