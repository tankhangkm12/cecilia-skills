# Refactor — survey, approve, then change

<!-- scoped source: shared/scoped/dev/refactor.md — synced into cecilia-dev-be and cecilia-dev-fe. Do not edit a copy. -->

Refactor = change structure, keep behaviour. Behaviour changes → it is a fix or a feature; use that
workflow. Refactors drift ("tidy one function" → 40-file diff); the approval gate fixes scope first. A
refactor not in the plan/docs is out-of-scope work: it needs the three approvals in `out-of-scope.md`.

## Phase 1 — Survey (change nothing)

1. **Purpose:** unblocks an upcoming planned feature (best reason) · stops a recurring bug source ·
   removes duplication that forces edits in several places · a measured hot path (`numbers.md`) ·
   Cecilia asked. "Looks nicer" is not a reason — say so and ask.
2. **Safety net:** does test coverage exercise the area (error branches, boundaries, not just the happy
   path)? Is the suite green now? No net → add focused characterization tests first when their paths are
   in the task envelope/scope, otherwise propose that cecilia-test adds them first, or Cecilia accepts a
   no-net refactor with stated risk.
3. **Boundary:** exact files/functions/components to touch AND what you deliberately leave untouched.

## Phase 1 output · 🛑

```markdown
**Goal:** …
**Current problem:** `path:20-140` — … (numbers where they exist: size, complexity, duplication count, timing)
**Safety net:** <n tests cover it, green> / <none → propose TEST task or accept risk>
**Options** (decisions.md §6): (A) … scope/gain/cost · (B) … · (C) leave as is — I lean to A because …
**Will touch:** … **Deliberately NOT touching:** …
**Behaviour guaranteed unchanged:**
  backend — API, response shape, error codes, side-effect order
  frontend — rendered output per state, calls made and their order, error-code handling, focus and navigation
**Risk:** where behaviour could silently change
```

## Phase 2 — Change (approved scope only)

- Branch `refactor/<TASK>-<desc>`; `git branch backup/<TASK>-<n>` before large moves (`git.md` §3).
- Structure and behaviour never change in the same step. Small steps; run tests after each; commit each
  green step.
- Nothing "while I'm here": no features, no bug fixes found on the way (report them), no renames or
  formatting outside scope.
- Public contracts unchanged (endpoints, payloads, error codes, event names, public signatures, shared
  component props).
- Moving/renaming → update every import, config and test reference (reference updates in tests are
  allowed; changing test assertions is not — that signals a behaviour change → stop and ask).
- Proof: same test count, same tests green, unmodified assertions; manual verification of the main flows.

Commit `refactor(scope): …`. Continue with D5–D8 (dev-be) / F5–F8 (dev-fe) in `references/workflow.md`. The report adds **Behaviour
unchanged: evidence**, **Found on the way, not fixed** (framed as (A) extend scope / (B) leave for later)
and the Rollback block. Self-critique: where could behaviour have changed unnoticed (backend: side-effect
order, null/empty handling, transaction boundaries, exception branches; frontend: effect order and
cleanup, render timing, which states a branch can now reach)?
