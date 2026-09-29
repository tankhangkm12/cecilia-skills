# MongoDB engine pack

Research the version in use (`db.version()`); behaviour differs between major versions. Cite docs.

## 1. Modelling

- **Embed** what is read together and bounded (order + its items); **reference** what is shared, unbounded or
  updated independently (customer, product). Documents are limited to 16 MB — any array that grows without
  bound (comments, events, followers) goes to its own collection (`capacity.py docsize`).
- Patterns: subset (recent N embedded, rest referenced), extended reference (copy the few fields you display),
  computed (maintain totals on write), bucket (time-series per hour/device), outlier (flag huge documents).
- Schema validation (`$jsonSchema`) on every collection with required fields and types; version field for
  migrations.

## 2. Indexes

- Compound index order **ESR**: Equality fields, then Sort, then Range.
- Cover the query (projection only indexed fields, exclude `_id` if not indexed) to avoid document fetches.
- Partial and sparse indexes for optional fields; TTL indexes for expiry; unique indexes for invariants.
- Each index costs writes and RAM; `$indexStats` to find unused ones.

## 3. Reading plans

`db.coll.find(q).sort(s).explain("executionStats")` → check `winningPlan` (IXSCAN vs COLLSCAN), `totalKeysExamined`
and `totalDocsExamined` vs `nReturned` (ratio ≫ 1 = wrong index), `SORT` stage in memory (missing sort key in index).
Aggregations: put `$match` and `$sort` first so they use indexes; `$lookup` on indexed foreign fields only; avoid
`$lookup` in hot paths at scale.

## 4. Consistency and transactions

- Single-document writes are atomic — model invariants into one document when possible.
- Multi-document transactions: need a replica set; keep short (lifetime and size limits); retry on
  `TransientTransactionError` / `UnknownTransactionCommitResult`.
- Write concern `majority` for data that must survive failover; read concern `majority`/`snapshot` where stale
  reads hurt; read preference secondary only for lag-tolerant reads.

## 5. Application code

- N+1: fetch references in batch (`$in` with the id list) and hydrate in memory, or `$lookup` once.
- Pagination by range on an indexed key (`_id > last`), not large `skip`.
- Updates with operators (`$inc`, `$set`, conditional filters) instead of read-modify-write; optimistic concurrency
  with a version field in the filter.
- ODM (Mongoose etc.): `lean()` for read paths, explicit projections, no implicit population loops.

## 6. Scale

Replica set (≥ 3 voting members) for HA; sharding only after rungs 0–5 (`scaling-ladder.md`): shard key with high
cardinality, even write distribution and present in most queries; monotonically increasing keys create a hot
shard (hash or compound key). Time-series collections for measurements.

## 7. Size queries

`db.coll.stats()` (`size`, `avgObjSize`, `totalIndexSize`), `db.stats()`; working set vs WiredTiger cache.
