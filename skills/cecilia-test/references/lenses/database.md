# Lens: database (cecilia-test v20)

Brief header `LENS=database`. Shared lens rules (files, isolation, report, lane): `../workflow.md` §Lenses.

## Attacks
The schema and the data it must protect: migrations that do not go down, constraints that do not hold,
queries that are fine on 10 rows and collapse on the documented volume, locks a migration takes.

## Oracle
DB design doc (tables, constraints, indexes, retention) · migration files and their declared down path ·
NFR data volumes and growth (`numbers.md`, `capacity.py growth`/`forecast` figures) · LLD invariants.

## Techniques
- **Migrations up → down → up** on an empty DB and on a seeded one; schema after the second up equals the
  first (dump and diff). No down path → finding unless the plan documents a backup/restore step.
- **Constraints:** each NOT NULL, UNIQUE, CHECK and FK violated once by a direct insert; the app maps it
  to the documented `errorCode`. Invariants the DB must hold (no negative stock) tested at DB level.
- **Data volume:** seed synthetic data to the documented volume (or a stated fraction, scaled with
  `capacity.py`); `EXPLAIN (ANALYZE, BUFFERS)` for each new/changed query; index used, time recorded.
- **Migration locks:** on the seeded DB, measure the lock taken and its duration; long locks on hot
  tables → finding with the online alternative named.
- **Backfills:** idempotent when re-run, batched, resumable.
- DB-side code (procedures, triggers, jobs): each branch executed once.

## Files
`<repo test root>/database/...` or suffix `.database`; seed generators in the lens folder.

## Environment
Own disposable DB `<db>_test_database` (or schema) on own port; container via `docker compose -p
<TASK>-test-db`. Never a shared, staging or production database; restoring real dumps is A4.

## Report
`tensura/reports/<TASK>/test-database.md`: table `migration · up · down · up · lock (ms) · rows`, query
table `query · rows · plan · time`, BUG table (`BUG-database-nn`).

## Never
Edit a migration, index or schema (`HANDOFF: needs cecilia-db`) · run against non-disposable data.
