# Growth, partitioning and retention — keep big tables cheap

A table that only grows eventually costs more than its data is worth: slower vacuums and backups,
indexes that no longer fit in memory, deletes that take hours. Decide how each fast-growing table ends
its life **before** it is big.

## 1. First question: does it need partitioning at all?

Start from the projection: `scripts/capacity.py growth --columns … --users L,E,H --rows-per-user-month …
--months 24 --index …` gives table + index size per scenario (`numbers.md`). Decide on those numbers.

| Situation | Usually enough | Partition when |
|---|---|---|
| queries hit recent rows via an index, table < a few tens of GB | good indexes | — |
| old rows must be removed on a schedule (logs, events, audit, sessions) | batched delete, if volume is small | deleting by `DELETE` takes too long or bloats the table |
| queries almost always filter on time or tenant, table far beyond memory | composite index led by that column | scans still touch too much; maintenance windows too long |
| analytics over history | summary tables / materialized views (`db-code.md`) | raw history must stay queryable and large |

Partitioning is not a speed-up by itself: a query that does not filter on the partition key reads
**every** partition. State the queries that will prune, with their `WHERE`, before choosing a key.

## 2. Choosing the scheme — options for Cecilia

| Choice | Options | Trade-off |
|---|---|---|
| Key | time column (`created_at`), tenant, hash of id | time fits retention; tenant fits isolation; hash only spreads load |
| Interval | day / week / month | too fine → thousands of partitions slow planning; too coarse → retention drops too much at once |
| Retention | N days/months, by law or business | drives the interval — drop whole partitions, never delete rows |
| Old data | drop · detach and archive to cheap storage · summarise then drop | cost vs ability to answer old questions |

Keep the count of live partitions in the hundreds, not tens of thousands. Unique keys and primary keys
must include the partition key on both engines — decide how the business uniqueness rule is still
enforced (`engines/*.md`).

## 3. Never create partitions in the insert path

A trigger or application code that creates a table when a row for a new period arrives is the pattern to
avoid: DDL in the hot path takes heavy locks at peak load, races between concurrent inserts, and on MySQL
a trigger cannot run DDL at all. PostgreSQL rejects creating a partition of the parent from inside an
insert into that parent ("being used by active queries in this session").

The rule: **partitions are created ahead of time by a scheduled job**, several intervals in advance, and
monitored.

| Engine | Declarative scheme | Pre-create / drop job |
|---|---|---|
| PostgreSQL | `PARTITION BY RANGE (created_at)` (PG 10+) | `pg_partman` with `pg_cron`, or a job in the app's scheduler calling a migration-managed procedure |
| MySQL | `PARTITION BY RANGE (TO_DAYS(created_at))` or `RANGE COLUMNS` | MySQL Event Scheduler calling a procedure, or an external scheduler; split the `MAXVALUE` partition with `REORGANIZE PARTITION` |

The job itself is DB-side code: in a migration, with a test, listed in the database doc §8.

## 4. Monitoring that must exist

- How many future partitions exist (alert below two intervals ahead).
- Rows landing in a default / `MAXVALUE` partition (should be zero — PG: attaching a new partition scans
  the default partition, so keep it empty or do not create one).
- Job last success time.
- Size per partition, to catch a surprise growth before the disk does.

## 5. Retention without pain

| Engine | Remove old data | Notes |
|---|---|---|
| PostgreSQL | `ALTER TABLE t DETACH PARTITION p CONCURRENTLY` (PG 14+), then archive and `DROP TABLE p` | `CONCURRENTLY` cannot run inside a transaction block |
| MySQL | `ALTER TABLE t DROP PARTITION p` (or `EXCHANGE PARTITION` into an archive table first) | metadata lock: set `lock_wait_timeout` low so it gives up instead of queueing everyone |

Unpartitioned table that must shed rows: delete in bounded batches by primary key range, pause between
batches, stop when replication lag or load rises, resumable from the last key. Never one giant `DELETE`.

## 6. Converting an existing big table

Partitioning a live table is a data migration (`migrations.md`): new partitioned table, dual-write or
trigger-based copy, backfill in batches, verify counts and checksums per range, swap names in a short
lock window, keep the old table until Cecilia approves dropping it. CONTROLLED, and the production run is
Cecilia's.
