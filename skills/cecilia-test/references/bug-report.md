# Bug reports (never fix product code)

One file per bug: `tensura/reports/<TASK>/<YYYY-MM-DD>-test-bug-BUG-nn-<slug>.md`. Number BUG-nn sequentially per
task (check existing files). Before writing, check for duplicates in existing bug files.

**With a lens (v20):** ids are `BUG-<lens>-nn`, numbered per lens so parallel testers never collide, and stable
across fix rounds. Every open bug is a row of the BUG table in `test-<lens>.md` (`assets/test-lens-report.md`);
a Critical/High bug, or one whose reproduction does not fit a row, also gets the file below (name
`…-test-bug-BUG-<lens>-nn-<slug>.md`). Table severity uses the fix-loop scale: Critical/High → BLOCKER,
Medium → SHOULD-FIX, Low → SUGGESTION.

```markdown
# BUG-07 — <short behaviour-level title>

> Task: <TASK> · Batch: B-02 · Found: YYYY-MM-DD · Reporter: cecilia-test (<agent>) ·
> Status: OPEN | CONFIRMED | FIXED_PENDING_VERIFY | VERIFIED | REOPENED | REJECTED ·
> Severity: Critical | High | Medium | Low · Priority suggestion: P1–P4

## Violated requirement
<ID(s) + doc path §section + quoted expected text>

## Environment
<branch/commit or build, env URL, OS/browser, data seed, accounts>

## Steps to reproduce
1. …
2. …
(minimal, deterministic; include exact request/payload or UI actions)

## Expected
<concrete, from the doc>

## Actual
<concrete: status, body, errorCode, UI text, DB state, logs with requestId>

## Evidence
<test name + failing assertion output, request/response, screenshot/trace path, log lines (redacted)>

## Frequency & scope
<always / n of m runs / only under concurrency / only role X>; other endpoints/screens likely affected [inferred]

## Suspected area (optional, not a fix)
<file/module if obvious from evidence, labelled [inferred]>

## Regression test
<test id/path that reproduces it; failing now>

## History
| Date | Status | By | Note |
|---|---|---|---|
```

Severity guide: **Critical** data loss/corruption, security breach, money wrong, system down · **High** core
flow broken, no workaround · **Medium** wrong behaviour with workaround or non-core flow · **Low** cosmetic,
wording. Doc unclear about the expected behaviour → it is not a bug yet: ask Cecilia and record as a question.

Never paste secrets or personal data; redact. Report bugs in the run report table and "For other roles"
(dev fix, plan to schedule).
