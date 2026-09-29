# Schema design → `<unit>-database.md` (one module or service per run)

<!-- scoped source: shared/scoped/database/schema-design.md — synced into cecilia-db and cecilia-design by
tools/sync_common.py. Do not edit a copy. -->

Owner: **cecilia-db**. When `cecilia-db` is off in `.cecilia/config.json`, `cecilia-design` writes this
document with this same guide (stage S-DB) and leaves the performance sections (template §6–§9) as
"not assessed — cecilia-db off". Path: `references/common/workspace.md` §2.1 (`<unit>` = module in a
monolith, service in microservices).

Input: `<module>-design.md` for every module in the unit. Schema is the hardest thing to change once
real data exists: challenge first, write second. Enough detail to write migrations without asking.

Derive from the module design, not imagination: every table traces to an LLD operation, and every line
of the LLD's stage-4 handoff list gets a concrete constraint. No module design yet → say it will likely
be redone, ask whether to write it first. UI designs or a frontend architecture available → every input,
filter, list column and state is a schema requirement; filter/sort fields need indexes.

## Step 1 — Forks (≈ 7–10 questions, one per turn)

1. DBMS + version; own schema/database or shared.
2. Primary key type (auto-increment / UUID and which version / ULID / business code) and why.
3. Hard vs soft delete per table; audit columns.
4. History/versioning — which data keeps history, which is overwritten (ties to stage 0 audit row).
5. Normalization level; accepted duplication and who keeps copies in sync.
6. Multi-branch / multi-tenant / multi-language; time partitioning for large tables.
7. Files/media: where stored, and whether file metadata is created **before** its parent record
   (presigned upload → nullable FK or staging table). Decide here, not in stage 5.
8. Money representation and rounding, time storage (UTC `timestamptz`, `date` for pure dates) —
   offer Cecilia's standards (`design-standards.md`) as the recommended option.

## Step 2 — Doubts before writing

Over/under-normalization · many-to-many without junction · free-text enums · **FK across service
boundaries** · missing UNIQUE where business demands uniqueness · JSON columns replacing design ·
fast-growing tables without a plan.

## Step 3 — Write (template `assets/database.md`)

1. Conventions (table naming, PK, time columns, soft delete, money, enums)
2. Relations + ASCII ERD + table `relation · type · FK · on parent delete`
3. Per table: `column · type · null · default · constraint · meaning` + keys table (PK/UNIQUE→which
   LLD rule/FK+ON DELETE/CHECK)
4. Indexes: `name · table · columns · type · query or screen served · LLD §`. An index that serves no
   named query is removed.
5. Enums & data rules; rules the schema cannot express and where they are enforced
6. Heavy queries expected — with the plan evidence when cecilia-db owns the doc
7. Growth, partitioning and retention (cecilia-db)
8. Database-side code: procedures, functions, triggers, scheduled jobs (cecilia-db)
9. Connections: pool size per instance, timeouts (cecilia-db)
10. Migration & seed order, rollback per step, backfill for brownfield under traffic
11. Syntax verification table
12. Doubts · Assumptions & risks

## Step 4 — Verify syntax implements the decision

When turning a decision into DDL/config, check the function really produces what was chosen. Real
failures: chose UUIDv7 but wrote `gen_random_uuid()` (v4); chose Argon2id but example uses bcrypt;
chose cursor pagination but query uses OFFSET; chose soft delete but FK is `ON DELETE CASCADE`.
Research the function in official docs; unsure → Assumptions, never guess.

## Exit gate

| # | Check | Result + evidence |
|---|---|---|
| 1 | Every LLD handoff line → a named UNIQUE/CHECK/PK | |
| 2 | Every table traces to an LLD operation | |
| 3 | Every index traces to a query/screen | |
| 4 | Every UI field has storage; every filter/sort has an index | |
| 5 | No FK to another service's table (only reference ids) | |
| 6 | Every VARCHAR has a length, numbers have units, enums list all values | |
| 7 | Every migration step has a rollback | |
| 8 | Every concrete syntax verified (name the functions checked + source) | |
| 9 | (cecilia-db) Every table expected to pass ~10M rows or grow without bound has a growth, partitioning or retention answer | |
| 10 | (cecilia-db) Every procedure/function/trigger/job lives in a versioned migration with rollback and a test | |
| 11 | (cecilia-db) Pool size × instances (+ migrations, jobs, admin) ≤ the server's connection limit, with headroom | |
| 12 | (cecilia-db) Every heavy query has a plan captured on representative data, or is marked `[unverified]` | |

When `cecilia-design` writes this document as the fallback, rows 9–12 read "not assessed — cecilia-db off".
