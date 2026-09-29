# cecilia-db — full rules and workflow

The SKILL card holds the summary; this file holds the detail. Open it at DB0 on STANDARD/CONTROLLED work.

## Golden rules (detail)

1. **Measure, never guess.** A performance claim carries a plan or a timing on stated data (`evidence.md`
   §1). "Should be faster" is not a result; before/after on the same data is.
2. **Representative data or say so.** A plan on 100 rows says nothing about 100 million. No realistic data
   → the number is `[unverified]` and the report says what data it would take.
3. **Correctness before speed.** A constraint the business needs (UNIQUE, CHECK, FK) is never dropped for
   speed; a race is never "fixed" by hoping.
4. **Every database object is a migration.** Tables, indexes, procedures, functions, triggers, views,
   jobs, partitions: versioned, reviewed, with a rollback — never typed into a server by hand.
5. **Lock budget first.** Every DDL on a table with real data states the lock it takes, the expected
   duration on the largest table, and `lock_timeout` / online method used (`references/migrations.md`).
6. **The app must see what the DB does.** Triggers and procedures carry no hidden business rules; each one
   is listed in the database doc so `dev-be` knows it exists (`references/db-code.md`).
7. **Options, not decisions.** Engine, key type, partition scheme, retention period, instance size,
   pooler: options with numbers, cost and a recommendation; Cecilia picks.
8. **Version-true syntax.** Engine behaviour differs by major version; name the version and cite the
   official doc for anything that matters (`references/engines/*.md`). Unsure → `[unverified]`.
9. **Project before deciding.** Table size at N users, connections → RAM, pool per instance: run
   `scripts/capacity.py` and present the low/expected/high table (`numbers.md`) before any schema,
   partition, pool or instance-size decision.
10. **Measure**: queries meeting target / queries in scope · p95 before → after with data size · tables
   with a growth answer / tables expected to grow · pool total vs connection limit.

Task guides: the table in `SKILL.md`.

## Workflow

Prefix: `[cecilia-db · DB4 · SHOP-42 · order]`.

**DB0 — Locate and branch.** Task branch and start SHA (`git.md` §2). Config (roles, `docs_layout`), work mode, the unit's database doc and module designs,
the migrations folder and tool (Flyway, Liquibase, Alembic, Prisma, TypeORM, Knex…), engine and
version from the repo (compose file, IaC, driver config), ORM and pool settings in code. 3–6 lines.

**DB1 — Interview · 🛑.** Only unknowns, grouped: engine + version · data volume now and growth per month
· the query/SLO that matters (p95 target, rows returned) · where measurements may run (local seed /
staging copy — A3) · downtime and lock tolerance · retention the business or law requires.

**DB2 — Read and challenge · 🛑.** Read the module design, the code that issues the queries, existing
schema and migrations. Challenge the upstream artifact (2–4 objections with failure scenarios): a rule
with no constraint, a list screen with no index, a table with no growth answer, a transaction that
holds locks across a network call.

**DB3 — Plan.** FAST: one line + the check. STANDARD: 2–5 steps, files, measurements, backup, stop
condition (`core.md` §5.1), with options (`decisions.md` §6) and projections (`numbers.md`) for every real
choice; stop for OK when `plan_first` is on for the mode. Schema/data migrations → CONTROLLED: plan with
`cecilia-scope`, stop at G2.

**DB4 — Work (A2).** Dump the local database before any migration or data change (`git.md` §4). Follow the
task-type guide. One change at a time when measuring, so each number has one cause; commit each step.

**DB5 — Measure.** Before and after on the same data and parameters: plan, timing (median of ≥ 5 warm
runs, plus the cold run), rows, buffers/pages read. Record as `M-nn` rows.

**DB6 — Verify.** Migrations up, down and up again on a local database; tests for DB-side code; the
database doc's exit gate (`schema-design.md`) printed row by row with evidence.

**DB7 — Report and hand off · 🛑.** Report (`evidence.md` §3) with the Deviations line. What `dev-be`
must change (query shape, pool config, retry on serialization failure) goes in "For other roles". PR text
from `assets/pr-draft-template.md` into `tensura/reports/<TASK>/pr-body.md`; push and PR are Cecilia's (local-only, A4 for agents) — write the exact commands in the report. Anything for a shared or production
database is handed to Cecilia as the exact command, its verification query and its rollback.

## FAST lane

A missing index on a known slow query in local/dev, a typo in a migration not yet applied anywhere, a
comment in the database doc: inspect, change, verify locally, report with Deviations. Anything touching
a table with real data, a constraint, or a migration already applied somewhere is not FAST.
