# Reviewing code (PR, diff, branch, module)

## 1. Axes, heaviest first (report in this order)
1. **Spec conformance** — every plan ID in scope implemented exactly as the docs say (flows, business rules,
   error codes + HTTP status, permissions with ownership, limits, state transitions, events). Also: changes
   that trace to no ID (scope creep / unapproved out-of-scope work), IDs claimed in the PR but not implemented.
2. **Correctness** — edge cases, inverted conditions, off-by-one, null/empty handling, error branches
   missing, wrong precedence of checks vs docs.
3. **Data & concurrency** — transaction scope, read-compute-write without the documented mechanism,
   check-then-act, N+1, events published inside transactions, missing outbox, idempotency for retries/
   consumers, migration safety (locks on big tables, rollback path, backfill), money as float, non-UTC time.
4. **Security** — IDOR (ownership not checked), missing validation/whitelist, SQL concatenation, dynamic
   sort/filter columns, secrets, sensitive data in responses/logs/errors, authN/authZ gaps, CORS, rate limits.
5. **Errors** — swallowed exceptions, empty catch, bare exceptions, 5xx leaking internals, SDK errors reaching
   services, codes not in the catalog.
6. **Architecture & boundaries** — importing other modules' internals, cross-module JOINs, cross-service DB
   access, cycles, SDK/ORM used outside adapters, env read outside config, controllers with logic, envelope
   built in controllers, abstractions without justification. Often missed Blockers — check deliberately.
7. **Maintainability** — function size/nesting/params, naming (role suffixes, intent-named repositories,
   banned names), types (`any`, untyped dicts, `Map<String,Object>`), comments (public docstrings, doc
   references, step comments in flows, why-comments; no noise/commented code/TODO without task).
   **Size and shape** (`code-standards.md`, dev `principles.md` §10): a file past ~400 lines, a class
   past ~7 public methods, a constructor past ~5 dependencies, a pass-through layer that only forwards
   arguments, a business rule spread through nested conditions in a service. Judge these as questions,
   not violations — ask what the unit's reasons to change are, and report it only when you can name
   the second responsibility. Two things are findings regardless: a **split by size rather than by
   reason** (`part1`/`part2`, `helpers2`), and **adding to a file already well past a signal without
   the PR saying so**. Debt compounds where nobody was asked to justify one more addition.
   **Leanness** (`code-quality.md`): dead code, duplication, an existing helper not reused, speculative
   options/layers, a new dependency where the stdlib or repo already had it, a scale trap on a hot path
   (N+1, unbounded list, per-row work in a loop, re-render storm), an "optimisation" with no numbers.
   **Simplicity check (mandatory, every PR):** could less code, fewer layers or no new dependency do the
   same job? Name the simpler shape (the existing helper, the stdlib call, the layer to drop). A real
   simpler shape → **SHOULD-FIX** (over-engineering); none → one line in the report saying so.
8. **Delivery** — work on a task branch (never a protected one), commits per step with messages per
   `git.md` §3, Rollback block present and correct (start SHA, commands, backup paths for any data
   touched), PR description matches the change, migrations/env/contract impact declared, no unrelated
   formatting churn, generated/lock files sane, `Deviations:` line present and consistent with the diff.
9. **Decisions and numbers** — where the change embodies a choice the docs left open: were options
   compared (`decisions.md` §6) and sourced (§7)? Every size, latency, memory or cost claim is measured
   or `[projected]` with formula and inputs (`numbers.md`); an unsupported number is a finding.

Tests in the same PR → also `review-tests.md`. Dev PRs may contain focused regression tests for what they
changed; independent acceptance coverage is `cecilia-test`'s — flag missing test tasks in the plan, not in
the dev PR.

## 2. Severity
| Level | Meaning | Examples |
|---|---|---|
| **Blocker** | must be fixed before merge | spec violation with user impact, security hole, data loss/corruption, broken contract, race on money/stock |
| **Should-fix** | not wrong today, becomes debt/risk | leaking ORM, missing documented log/redaction, 120-line function, boundary smell |
| **Suggestion** | optional improvement | naming, simpler construct |
| **Question** | cannot judge without context | "is null intentional here?" |

A finding caused by code that follows the docs, where the docs themselves are risky → report it as a doc
issue with options: (A) change docs & code / (B) keep and accept risk — Cecilia decides.

## 3. Finding format
```markdown
### B-1 · Blocker · `src/modules/order/cancel-order.service.ts:42` · Spec (FR-05, BR-02)
- **Problem:** …
- **Failure scenario:** order SHIPPED + owner calls cancel → 200 and status CANCELLED (doc: 409 ORDER_NOT_CANCELLABLE)
- **Evidence:** code excerpt/line description; doc quote §4.1 [verified]
- **Suggested direction:** 1–2 lines (no patch)
```

## 4. Also report
- **File walkthrough:** one line per changed file: role and flow.
- **Good:** 1–3 specific things worth keeping.
- **Out of scope, noticed only:** issues in untouched files.
- **Spec coverage table:** `ID · implemented? · where · note`.
