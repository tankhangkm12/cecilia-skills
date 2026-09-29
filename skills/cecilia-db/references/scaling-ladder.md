# Scaling ladder — the lowest rung that holds, with a trigger for the next

Cecilia chooses. Present rungs as options on the same criteria (cost/month, complexity, reversibility,
what it fixes, what it does **not** fix, trigger to move up). Numbers from `growth-forecast.md`.

| Rung | Strategy | Mechanism | Fixes | Does not fix | Reversible | Trigger to reach it |
|---|---|---|---|---|---|---|
| 0 | Query, index, schema fixes | plans, covering indexes, less data per row | most "the DB is slow" | a write ceiling | yes | always first (`performance.md`) |
| 1 | Bigger instance (vertical) | more RAM keeps the hot set cached; more IOPS/CPU | memory and IO pressure | single-primary write ceiling, restore time | yes | hot set > 70 % RAM, IO wait |
| 2 | Connection pooling / limits | fewer server processes, queued clients | "too many connections", RAM per connection | slow queries | yes | connections > 70 % of max (`connections.md`) |
| 3 | Cache (cache-aside, TTL, invalidation) | repeated reads served from memory | read load on hot keys | writes, cold reads, consistency | yes | same reads ≫ writes, staleness acceptable |
| 4 | Read replicas | physical/logical replication, reads routed | read throughput, reporting isolation | writes; read-your-writes flows | yes | reads saturate primary; lag acceptable |
| 5 | Partitioning, TTL, archiving (hot/warm/cold) | drop partitions, move old data to cheap storage | table size, maintenance, retention | per-row hot writes | partly | table > 100M rows, retention required (`partitioning-retention.md`) |
| 6 | Read models / materialized views / CQRS | precomputed shapes for heavy screens | expensive aggregations | write load | yes | aggregation queries dominate CPU |
| 7 | Specialised stores for specialised load | search engine, OLAP store, time-series store, fed by CDC/outbox | full-text, analytics, metrics in OLTP | OLTP writes | yes | those queries hurt OLTP p95 |
| 8 | Split by bounded context (DB per service) | each service owns its data | contention between domains, team coupling | a single hot domain | hard | independent teams/domains, different scaling |
| 9 | Sharding / distributed SQL | data split by key across nodes; consensus per range | write ceiling, dataset > one node | cross-shard queries, hot keys | hard | peak writes > one primary after rungs 0–5 |

Rules:
1. Never skip rungs "for later" — every rung above 5 adds permanent operational cost.
2. A hot **key** is not solved by more nodes: fix contention first (`concurrency.md`).
3. Each chosen rung records its trigger for the next in the database doc §14 and a monitoring alert.
4. Template: `assets/scaling-options.md`.
