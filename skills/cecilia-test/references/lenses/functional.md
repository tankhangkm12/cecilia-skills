# Lens: functional (cecilia-test v20)

Brief header `LENS=functional`. Shared lens rules (files, isolation, report, lane): `../workflow.md` §Lenses.

## Attacks
Does the unit do exactly what the documents promise, including every way it must fail: each AC and BR,
each error code, each allowed and blocked state transition, each edge of each input.

## Oracle
SRS `AC-nn` (Given/When/Then) · `BR-nn` · LLD flows, state machines and error-code tables · API contract
(status, `errorCode`, schema) · Cecilia's decisions. Current behaviour and dev notes are hints, never the oracle.

## Techniques
- Coverage frame of `../test-design.md` §2 for every input and operation, never free-form.
- **Boundary values:** min, max, min-1, max+1, zero, negative, empty, very long, unicode.
- **Negative first:** every AC gets at least one case that must fail; every error code gets a case that triggers it.
- **State:** every transition allowed and every one blocked, with the documented error.
- **Idempotency:** same request twice, same key with a different body.
- Cheapest level that proves the rule (`../test-levels.md` §2 unit, §4 API); E2E only for a journey
  no lower level can prove, and then it belongs to the `ui` lens.

## Files
`<repo test root>/functional/...`, or the repo's co-located convention with the suffix `.functional`
(`order-cancel.functional.spec.ts`, `test_order_cancel_functional.py`). Unit tests mock ports only.

## Environment
Unit level needs none. API level: own app port and own test DB from the brief's RUNTIME block.

## Report
`tensura/reports/<TASK>/test-functional.md` with the coverage table `ID · TCs · automated · result`,
uncovered IDs with the reason, and the BUG table (`BUG-functional-nn`).

## Never
Assert what the code does when the docs say otherwise (that is a BUG or a question) · invent an expected
result (ask) · test races, load, auth attacks, browser rendering or schema: those are other lenses; a
finding there goes in the report as `HANDOFF: needs cecilia-test LENS=<lens> — <what>`.
