# Safe migrations — schema changes on tables with real data

Code rolls back; data does not. A migration that is instant on a laptop can lock a production table for
minutes. Every migration here states what it locks, for how long, and how it is undone.

## 1. Before writing it

| Question | Where the answer goes |
|---|---|
| Rows and size of every table touched (largest first) | database doc §10 "Lock taken / expected duration" |
| Lock level the statement takes on this engine and version | same row — `engines/*.md` |
| Does old code still work after it (rolling deploy, canary)? | if not → split with expand/contract (§2) |
| Rollback: the down migration, or "irreversible — restore from backup taken at <step>" | migration file + §10 |
| Interrupted halfway — what state is left, can it resume? | §10 |

The migration tool the repo already uses wins (Flyway, Liquibase, Alembic, Prisma Migrate, TypeORM,
Knex, Rails…). An ORM-generated migration is a draft: read the SQL it produces and fix it.

## 2. Expand / migrate / contract

Aligned with `cecilia-devops` (deploy-and-rollback §3):

1. **Expand** — add the new column/table/index, nullable or with a cheap default. Old code keeps working.
2. **Migrate** — new code writes both shapes; backfill in batches (§4); verify.
3. **Contract** — drop the old shape in a later release, once rolling back past that point is no longer
   wanted. Dropping is a separate, explicitly approved step.

A rename is never one step: add new, dual-write, backfill, switch reads, drop old.

## 3. Low-lock recipes

| Change | PostgreSQL | MySQL (InnoDB, 8.0) |
|---|---|---|
| Add nullable column / column with constant default | fast (PG 11+ no rewrite for a non-volatile default) | `ALGORITHM=INSTANT` (8.0.12+; any position from 8.0.29) |
| Add index | `CREATE INDEX CONCURRENTLY` (outside a transaction; drop an `INVALID` leftover) | `ALGORITHM=INPLACE, LOCK=NONE` |
| Add foreign key | `ADD CONSTRAINT … NOT VALID`, then `VALIDATE CONSTRAINT` separately | online for InnoDB with `foreign_key_checks` considerations — check the version's online DDL table |
| Add NOT NULL | `CHECK (col IS NOT NULL) NOT VALID` → `VALIDATE` → `SET NOT NULL` (PG 12+ uses the valid check) → drop the check | usually a table rebuild — plan it with an online schema tool |
| Change column type | usually a rewrite — new column + backfill + swap | rebuild — `gh-ost` / `pt-online-schema-change` for big tables |
| Big table restructure | new table + copy + swap (`partitioning-retention.md` §6) | `gh-ost` / `pt-online-schema-change` |

Always put a short lock timeout on DDL so it fails instead of queueing all traffic behind it:
PostgreSQL `SET lock_timeout = '3s';` in the migration, MySQL `SET SESSION lock_wait_timeout = 3;`.
Retry later is cheaper than an outage. Online-schema tools are dependencies to install (A3) and
infrastructure to run (`cecilia-devops`).

## 4. Backfills

- Batches bounded by primary key range (e.g. 5 000 rows), committed per batch — PG procedures can
  `COMMIT` between batches (`db-code.md` §6).
- Throttle: pause between batches; stop when replication lag or load passes a stated threshold.
- Resumable: record the last key done; re-running skips completed ranges.
- Verify: counts and a checksum per range between old and new shape before switching reads.

## 5. Where each migration runs

| Target | Authority |
|---|---|
| local container / Testcontainers | A2 (FAST/STANDARD task envelope; CONTROLLED scope) — run up, down, up |
| shared dev/staging | A3 — quote the exact command, target and backup status |
| production | A4 — Cecilia runs it. Hand over: the command, the pre-check queries, the expected lock/duration, the verification query, the rollback, and the backup taken in that session (`cecilia-devops` §3) |

The guard already asks for `prisma migrate deploy`, `flyway migrate`, `liquibase update` and any
`psql`/`mysql` call; production targets are denied.
