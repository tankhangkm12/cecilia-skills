# Reviewing tests (test code, test-case catalogs, run reports)

## 1. Coverage against the docs (heaviest)
- Every AC/FR/BR in the batch has ≥ 1 test case; every error code has a triggering case; every endpoint has
  happy + invalid + forbidden; every allowed and blocked state transition; every CORE operation has a
  concurrency case proving the documented mechanism; idempotency replay/conflict cases; NFR targets tested
  where in scope. Produce the table `ID · TCs · automated? · gap`.
- Expected results come from docs, not from current behaviour (look for assertions that merely mirror the
  code, e.g. asserting a status the docs contradict).

## 2. Test quality
- Asserts observable behaviour/contract, not internals or call counts of private collaborators.
- Does not mock the unit under test; mocks only at ports in unit tests; integration tests really hit the
  DB/broker they claim to verify.
- Deterministic: injected/frozen clock, no sleeps as sync, no order dependence, isolated data, no shared
  mutable fixtures, no real third-party calls, no production data or secrets.
- Would the test fail if the requirement broke? (Mentally mutate the rule: flip a condition, remove a guard.)
  If not → it is a vacuous test.
- Names describe behaviour + condition; AAA; parametrized repetition; IDs referenced.
- Negative/boundary cases actually use boundary values (min−1, max+1), not arbitrary ones.
- E2E: stable selectors, few critical journeys, failure artifacts; no flaky waits.
- Performance: scenario matches NFR, environment approved and representative, warm-up, percentiles, error rate.
- Security tests stay within approved environments; findings mapped to OWASP categories.
- Skipped/xfail tests reference a BUG-nn approved by Cecilia; flaky tests are reported, not hidden.

## 3. Bug reports & run reports
Reproducible steps, concrete expected (quoted doc) vs actual, evidence, severity consistent with the guide,
no duplicates, redacted data; run report numbers add up; release verdict supported by open-bug list.

## 4. Test PR hygiene
No product code changes; test dependencies approved; branch/commit conventions; CI config untouched unless approved.

## 5. Test lens reports (v20)
From STANDARD each tester runs one lens and writes `tensura/reports/<TASK>/test-<lens>.md` (lens guide:
cecilia-test `references/lenses/<lens>.md`). Review each report against its own lens, and the set as a whole:

| Check | Finding when |
|---|---|
| Pinned | report SHA ≠ the reviewed SHA, or no environment/commands → results are `[unverified]` here |
| Lens set | a lens the diff needed (auth → security, schema → database, UI → ui, IaC → infra, shared state → concurrency-perf) did not run → coverage gap, SHOULD-FIX (BLOCKER for a CORE/money/security rule) |
| In lane | test files outside the lens-owned folder/suffix, another lens's files edited, or any product code, migration, IaC, CI or `.env` change → BLOCKER |
| Oracle | cases cite AC/FR/BR/NFR/contract; assertions mirror current behaviour instead of the docs |
| Lens depth | functional: negatives and boundaries per AC · integration: real local DB/broker, contract per endpoint · concurrency-perf: barrier-started races repeated with the count stated, measured p95/rps vs NFR and vs `[projected]` · security: other-owner/tenant case per endpoint · ui: state × breakpoint screenshots, console, keyboard path · database: up→down→up, each constraint violated once, volume stated · infra: validate/plan only — any apply is BLOCKER |
| BUG table | exactly `\| ID \| Title \| Severity \| Repro \| Evidence \|`, ids `BUG-<lens>-nn` stable across rounds, fix-loop severity scale, repro runnable; a bug downgraded to hide it → BLOCKER |
| Fix rounds | every earlier `BUG-<lens>-nn` has a Re-test row (`VERIFIED` / `REOPENED` / `STILL_OPEN`) at the new SHA |
| End lines | `Rules: <hash> (PR-ids)` present; `HANDOFF:` lines for anything out of lane instead of a workaround |

In a panel the `tests` lens runs this section; other lenses use the reports as evidence (`panel.md` §3).

Severity and finding format: same as `review-code.md` §2–§3 (a missing test for a CORE/money/security rule is
a Blocker for batch completion; a weak assertion on a low-risk path is Should-fix).
