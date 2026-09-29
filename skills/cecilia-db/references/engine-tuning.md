# Engine settings, instance size and replicas — from hardware up

Tuning comes **after** schema, indexes and queries. A bigger machine hides a missing index for a month;
then the bill and the problem both grow. Every recommendation here is an option for Cecilia with the
measurement that motivates it; applying it to a shared or production server is not this role's action
(`cecilia-devops` applies config through IaC; production is Cecilia's).

## 1. Measure before recommending

| Signal | PostgreSQL | MySQL | Says |
|---|---|---|---|
| Cache hit ratio | `pg_stat_database` (`blks_hit` vs `blks_read`) | buffer pool reads vs read requests | working set fits in memory? |
| Active vs idle connections | `pg_stat_activity` | `SHOW STATUS LIKE 'Threads_%'` | pool too big / leaks |
| Waits | `wait_event_type` in `pg_stat_activity` | `performance_schema` wait events | CPU, IO or locks? |
| Temp files / disk sorts | `temp_files` in `pg_stat_database` | `Created_tmp_disk_tables` | memory per operation too low, or a query to fix |
| Bloat / vacuum lag | `n_dead_tup`, last autovacuum | history list length | cleanup cannot keep up |
| Replication lag | `pg_stat_replication` | `SHOW REPLICA STATUS` | replicas usable for reads? |

Plus host metrics: CPU, memory, disk IOPS and latency, network. Record each as an `M-nn` row.

## 2. Instance size — the four resources

Project memory, storage and connection needs with `scripts/capacity.py` (`growth`, `connections`,
`throughput`) before proposing a size; confirm with the §1 measurements after.

| Resource | Sized by | Sign it is short |
|---|---|---|
| Memory | the hot working set (hot tables + indexes) should fit in cache | low hit ratio, high read IOPS |
| CPU | concurrent active queries, not connections | CPU saturated with active sessions ≈ cores |
| Disk IOPS / latency | write rate, checkpoint/flush, cache misses | IO waits, latency spikes at checkpoints |
| Storage | data + indexes + growth (`partitioning-retention.md`) + WAL/binlog + free space for maintenance | < 20 % free; rebuilds cannot run |

Present options as a table: current · proposed · monthly cost delta (source: the provider's price page,
dated) · the metric it fixes.

## 3. Common starting points — to be measured, never applied blind

| Setting | PostgreSQL | MySQL (InnoDB) |
|---|---|---|
| Main cache | `shared_buffers` — about 25 % of RAM is the usual start | `innodb_buffer_pool_size` — commonly 50–75 % of RAM on a dedicated server |
| Planner's view of OS cache | `effective_cache_size` ≈ 50–75 % of RAM | — |
| Memory per sort/hash | `work_mem` — per operation, per connection: `work_mem × parallel ops × connections` can exceed RAM | `sort_buffer_size`, `join_buffer_size` — per session, keep modest |
| Maintenance | `maintenance_work_mem` for index builds and vacuum | — |
| SSD storage | `random_page_cost` ≈ 1.1–1.5 instead of 4 | — |
| Write durability vs speed | keep `fsync`, `synchronous_commit` on unless Cecilia accepts data-loss risk in writing | keep `innodb_flush_log_at_trx_commit=1` unless the same |
| Redo / WAL size | `max_wal_size` so checkpoints are not constant | `innodb_redo_log_capacity` (8.0.30+) |
| Cleanup | per-table autovacuum scale factors lower on large, hot tables | purge threads; watch history list length |

Managed services (RDS, Cloud SQL, Azure) set some of these already and forbid others — read the
provider's parameter group docs for the version before proposing a change.

## 4. Read replicas

Good for read-heavy load that tolerates lag (lists, reports, search). Not for read-your-own-write flows
(the user saves and immediately reloads) — route those to the primary. The design must say which queries
may go to a replica and what lag is acceptable; the app routing is `dev-be` code; the replica is
`devops` infrastructure. Monitor lag and fall back to the primary when it passes the stated limit.

## 5. What goes in the report

Each recommendation: the metric that motivates it (with `M-nn`) → the change → the expected effect →
how it will be verified after apply → how to revert → who applies it (devops via IaC for shared, Cecilia
for production).
