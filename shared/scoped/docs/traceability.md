# Traceability

<!-- scoped source: shared/scoped/docs/traceability.md — synced by tools/sync_common.py. Do not edit a copy. -->

Docs usually fail not because one stage is wrong, but because something stated earlier silently
disappears later. Three directions are mandatory.

**Forward** — every in-scope row, actor, journey step, FR/NFR/BR/AC and screen must receive: an LLD
section, a table/column if stored, an endpoint or event if called, a test case. No home → add it, or
move it explicitly out of scope. Check before closing every stage.

**Backward** — a later decision can break an earlier doc (a 2-step upload in stage 5 breaks a NOT NULL
FK in stage 4). Found → stop, do not patch, print the conflict table, ask.

**LLD ↔ DB both ways** — every table traces to an LLD operation, and every "exactly one / never
duplicate / only one of two null" rule in the LLD maps to a UNIQUE/CHECK/PK. A rule enforced only in
code will be violated by two concurrent requests.

## Conflict table

| Doc | Section | Currently says | Conflicts with | Proposed fix |
|---|---|---|---|---|

## Full consistency checklist

Run after stage 6 of a service, and after any change to a finished stage. Print every row with
**evidence** (section, table, endpoint numbers). "All good" without rows is not allowed; a row is "pass"
only after re-opening the docs, not from memory.

| # | Check | How |
|---|---|---|
| 1 | Idea scope → FR | each in-scope row names its FR IDs |
| 2 | Prose → scope tables | features named in actors/journey/option tables are in in- or out-scope |
| 3 | FR/BR → LLD | each FR/BR of the service names its LLD section |
| 4 | Screens → endpoints | display and action endpoints exist |
| 5 | LLD rules → DB constraints | named UNIQUE/CHECK per rule |
| 6 | CORE ops → Cecilia's choice | each has a D-nn decided by Cecilia; list all agent-chosen rows |
| 7 | Decisions → implementation | each D-nn points to the DDL/YAML/section implementing it; syntax verified |
| 8 | LLD ↔ endpoints | ops without endpoint and endpoints without op, both listed |
| 9 | AC / error codes → test cases | each has ≥ 1 TC |
| 10 | NFR → mechanism | each NFR has a concrete mechanism |
| 11 | HLD security rows → implementation | permission column, encrypted columns, rate-limit config |
