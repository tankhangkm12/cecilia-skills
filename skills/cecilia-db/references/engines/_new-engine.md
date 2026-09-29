# Adding an engine (MariaDB, SQL Server, Oracle, CockroachDB, Cassandra, …)

When the project uses an engine without a notes file here, research it before advising — from the
vendor's official docs for the exact version — and write `references/engines/<engine>.md` with the same
sections as `postgresql.md`, each item citing its source and the version it applies to:

1. Types and keys (money, time, UUID/ordered keys, clustered vs heap storage)
2. Indexes (types, online build, how to test a drop)
3. Locks worth knowing (what DDL blocks, how to bound the wait)
4. Partitioning / sharding (key rules, retention, pre-creation)
5. DB-side code (procedures, functions, triggers, jobs, how to test them)
6. Observability (top queries, plans, waits, lock waits)
7. Connections and timeouts (limit, poolers, statement/lock/idle timeouts)
8. Memory and durability (main cache, durability switches and their data-loss trade-off)

Until that file exists, every engine-specific claim in a report is `[unverified]` unless it quotes the
vendor doc. Tell Cecilia the file was added so she can keep it for the next project.
