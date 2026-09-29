# Test strategy → `tensura/docs/system/test-plan.md`

Input: SRS (AC-nn), LLD, API contract, UI designs. Real bugs live at boundaries and error branches:
priority is covering every failure case, not many happy-path cases. cecilia-test executes this plan.

## Step 1 — Read inputs; say which part will be thin if an input is missing.

## Step 2 — Questions (one per turn; this stage has few, but never zero)

1. **Severity policy** — what blocks release, what may ship as known issue.
2. **Environments & data** — where tests run, test accounts, seed data source, may real data be touched.
3. **Test levels in scope** — manual/acceptance, API/integration, E2E, unit hints, performance, basic
   security — and target numbers for performance (from NFRs).
4. **Tooling constraints** if any are already mandated (otherwise cecilia-test asks later).

Any real contradiction between sources (screen allows editing a field LLD says is immutable) → stop and ask.

## Step 3 — Generate cases with the boundary/error frame (never free-form)

| Group | Cases |
|---|---|
| Empty / missing | required field empty, empty body |
| Boundaries | min, max, below min, above max |
| Wrong type / format | text in number, bad date, invalid enum |
| Permission | anonymous, wrong role, **other user's data** |
| Existence | unknown id, soft-deleted record |
| Duplicates | same request again (idempotency), unique violation |
| Wrong state | action invalid in current state |
| Concurrency | two actors on one record — mandatory for every CORE operation |

Every concurrency mechanism chosen in the LLD needs ≥ 1 case proving it works.

## Step 4 — Write (template `assets/test-plan.md`)

Sections: preparation · manual/acceptance (`TC · screen/flow · preconditions · steps · expected ·
severity · AC/FR`) incl. empty/loading/offline/server-error UI states · API tests (`TC · endpoint ·
input · HTTP · expected response · FR/AC`, each endpoint ≥ happy + invalid + forbidden) · concurrency
tests · performance/security (if in scope, with numeric targets) · unit-test hints (branches, money,
state transitions) · traceability `AC → TC`. Expected results are concrete values, never "works correctly".

## Exit gate

| # | Check | Result + evidence |
|---|---|---|
| 1 | Every AC-nn has ≥ 1 TC | |
| 2 | Every error code in LLD/API has a TC that triggers it | |
| 3 | Every endpoint has happy / invalid / forbidden TCs | |
| 4 | Every screen appears incl. empty & error states | |
| 5 | Every state transition has an allowed and a blocked TC | |
| 6 | Every CORE op has a concurrency TC proving the chosen mechanism | |
| 7 | No vague expected results | |
