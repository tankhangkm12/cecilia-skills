# Choosing a database — by workload and mechanism, not by brand

Output: ≥ 3 options (include "stay with the current engine"), same criteria, numbers from the forecast, a
POC plan, and an ADR with the conditions that reopen the decision (`assets/engine-adr.md`). Cecilia decides.
Research current versions and limits in official docs; cite them with dates.

## 1. Workload profile (fill first)

| Dimension | Question | Why it decides |
|---|---|---|
| Data shape | relational with invariants across rows? documents read whole? graph? time-series? blobs? | join model, constraints |
| Transactions | multi-row/multi-entity atomicity needed? money, stock, bookings? | engine guarantees vs app-level sagas |
| Consistency | stale reads acceptable where, for how long? | replicas, caches, eventual stores |
| Access patterns | point reads, range scans, ad-hoc filters, full-text, aggregations, geo | index types, specialised stores |
| Write profile | rate, peak factor, hot keys, append-only vs updates | B-tree vs LSM, sharding need |
| Size & growth | from growth-forecast.md | single node vs distributed |
| Latency | p95 per query class | memory vs disk, consensus cost |
| Operations | team skills, managed offering in the region, backup/PITR tooling, upgrades | the usual real constraint |
| Cost & licence | managed price, self-hosting effort, licence terms | total cost of ownership |

## 2. Mechanisms that matter

| Mechanism | Variants | Consequence |
|---|---|---|
| Storage structure | **B-tree** (update in place: PostgreSQL heap + B-tree indexes, InnoDB clustered B-tree, WiredTiger) vs **LSM** (append + compaction: RocksDB-based stores, Cassandra/ScyllaDB) | B-tree: fast reads, write amplification on random updates. LSM: fast writes, read/space amplification, compaction spikes |
| Clustering | InnoDB clusters rows by primary key; PostgreSQL heap is unordered; MongoDB clusters by `_id` via its index | random UUIDv4 keys fragment clustered B-trees — prefer time-ordered keys (UUIDv7/ULID) |
| MVCC | PostgreSQL keeps old row versions in the table (VACUUM, bloat, xid wraparound); InnoDB keeps them in undo logs (purge lag, long-transaction history); WiredTiger snapshots in cache | long transactions hurt all three differently; update-heavy tables need tuning |
| Transactions & isolation | defaults differ (PostgreSQL READ COMMITTED, InnoDB REPEATABLE READ with gap locks, MongoDB snapshot for multi-document transactions with lifetime and size limits; distributed SQL often SERIALIZABLE) | anomalies, retries, lock waits |
| Joins | SQL joins in the engine; MongoDB `$lookup` (costly at scale; model to avoid it); wide-column stores: none (model per query) | how much modelling moves into the application |
| Constraints | FK/CHECK/UNIQUE in SQL; JSON-schema validation and unique indexes in MongoDB; few in wide-column/KV | where invariants live |
| Replication | physical WAL streaming, logical replication, binlog (async/semi-sync), replica-set oplog with elections, Raft per range | failover time, data loss on failover (RPO), read scaling |
| Consistency knobs | synchronous commit, write/read concern `majority`, quorum levels | durability vs latency per write |
| Horizontal scale | extensions/middleware (Citus, Vitess), native sharding (MongoDB, Cassandra), distributed SQL (CockroachDB, YugabyteDB, TiDB) | shard key design, cross-shard cost, consensus latency |
| Backup / PITR | base backup + WAL/binlog/oplog replay; snapshots; logical dumps | RPO/RTO achievable (backup-dr.md) |

## 3. Typical fits (starting points, not answers)

| Workload | Often fits | Watch out |
|---|---|---|
| OLTP with money, stock, bookings, relational invariants | PostgreSQL, MySQL | hot rows (concurrency.md), vacuum/purge on update-heavy tables |
| Catalogue with varying attributes, content read whole | MongoDB, or PostgreSQL JSONB | unbounded arrays, 16 MB documents, `$lookup` at scale |
| Very high write rate, simple queries by key, multi-region | Cassandra/ScyllaDB, DynamoDB-style KV | no ad-hoc queries; model per query; tunable consistency |
| Global strong consistency, SQL, horizontal scale | distributed SQL | per-write consensus latency, cost, operational maturity |
| Full-text search, facets | OpenSearch/Elasticsearch fed by CDC | near-real-time, never the source of truth |
| Analytics over large history | ClickHouse, a warehouse | batch inserts, not for OLTP updates |
| Time-series metrics/events | TimescaleDB (PostgreSQL), time-series stores | retention/compression policies |
| Cache, rate limits, queues, sessions | Redis/Valkey | memory-bound, persistence settings, not the source of truth |

## 4. Method

1. Profile (§1) + forecast (growth-forecast.md) → criteria weights Cecilia agrees on.
2. Three or more options incl. "stay"; per criterion a number or a cited fact.
3. POC on a local copy: representative schema, synthetic data at month-12 size (skewed like production),
   the top 5 queries and the peak write mix; measure p95, throughput, size, restore time.
4. ADR: decision, why, rejected options and why, **revisit when** (e.g. "writes > 3k/s", "data > 2 TB",
   "team adds a second region").
5. Polyglot persistence only with a named workload, an owner and a sync mechanism (outbox/CDC); every extra
   store is another backup, upgrade and on-call path.
