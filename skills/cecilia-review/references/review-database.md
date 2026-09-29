# Reviewing database work — schema, migrations, DB-side code, performance claims

Targets: the database doc, migration files, procedures/functions/triggers/jobs, pool and timeout
config, and every performance number `cecilia-db` reported. Database defects are expensive because they
land on data that already exists; judge each change as if the largest table were already in production.

## 1. Re-derive, do not trust

- A performance claim is PASS only when its evidence (plan output, timing runs, data size, `M-nn` row)
  exists and says exactly that. Plan on toy data presented as proof → SHOULD-FIX `[unverified]`.
- Lock and duration estimates: check the statement's lock level for the stated engine version
  (`cecilia-db` `references/engines/*.md` is the author's claim, the vendor doc is the oracle).
- Read the migration SQL itself, not the ORM model — generated SQL is what runs.

## 2. Checks, heaviest first

| # | Check | Failure it catches |
|---|---|---|
| 1 | Every business rule that must hold is a constraint (UNIQUE, CHECK, FK, PK) or a documented race | duplicates and orphans under concurrency |
| 2 | Each migration: lock level + expected duration on the largest table, `lock_timeout`/online method, down path or backup step | a "quick" ALTER that blocks traffic for minutes |
| 3 | Expand/contract respected: old code works after the migration; no drop in the same release as its replacement | rollback impossible, outage on canary |
| 4 | Backfills batched, throttled, resumable, verified | one giant transaction, replication lag, half-done state |
| 5 | Every index serves a named query; no duplicate or left-prefix-redundant index; hot write tables not over-indexed | slower writes, memory wasted |
| 6 | Plans: estimates vs actuals, rows read vs returned, spills — as in the evidence | a fix that only worked on 100 rows |
| 7 | Fast-growing tables have a growth answer; partitions pre-created by a job, never in the insert path; unique keys include the partition key | runaway tables, failed inserts at month change |
| 8 | DB-side code: in a migration, listed in the database doc, tested, no hidden business decisions, no DDL in triggers, `SECURITY DEFINER` with fixed `search_path`, correct volatility | invisible behaviour, privilege escalation, wrong cached results |
| 9 | Connection budget: pool × max instances + jobs + reserve ≤ limit; timeouts set at every layer | "too many connections" at the first scale-out |
| 10 | Money/time types (`numeric`/`DECIMAL`, UTC timestamps), UUID version matches the decision | rounding errors, time-zone bugs, wrong key order |
| 11 | No production statement, credential or data in the repo, report or PR | leaked access, A4 bypass |

## 3. Severity

| Level | Examples |
|---|---|
| **Blocker** | a DDL that takes an exclusive lock on a large live table with no plan · a dropped constraint the business needs · partition creation in a trigger · a migration with no down path and no backup step · pool budget over the limit at max instances · a performance claim that gates a merge with no evidence |
| **Should-fix** | missing `lock_timeout` · unmeasured index benefit · trigger not listed in the doc · timeouts only in the app |
| **Suggestion** | naming, index column order with small measured effect |
| **Question** | "is 90-day retention a legal requirement or a guess?" |

## 4. Also report

A table per migration: `migration · tables (rows) · lock · duration claim · verified? · down path`, and
a table per performance claim: `claim · evidence found · consistent with the evidence? · verdict`. The
reviewer runs nothing; when a number must be reproduced, ask for a run by `cecilia-db` or `cecilia-test`
on the same data and judge its output.
