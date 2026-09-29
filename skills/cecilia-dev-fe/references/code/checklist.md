# Self-review checklist (before Draft PR)

Tick what applies; a group the change does not touch is "n/a" — do not tick blindly.
🔴 = blocker (fix before PR), others = fix or explain in the PR.

## 🔴 Process
- [ ] Interview done; implementation brief approved; every change traces to a `SCR`/`CMP` id or an approved proposal
- [ ] No files outside the brief; no new or upgraded dependency; no screen, route or shared component deleted without approval
- [ ] Test files changed only inside the approved scope, and only focused regression tests for this change (independent acceptance tests are cecilia-test's)
- [ ] Every gap the design or the contract left open was asked, not guessed

## 🔴 Contract conformance
- [ ] No endpoint called that is absent from `<unit>-api.yaml`; no invented field or response shape
- [ ] Mock **generated** from the contract and regenerated for this contract version; version recorded in the report
- [ ] Response unwrapped in one client layer; branching on `errorCode`, never on `message`
- [ ] Every contract gap found is in the report for `cecilia-design` — none worked around locally

## 🔴 States — the ones the design documents
- [ ] Loading, empty, partial, **each error code the endpoint can return**, permission-denied, offline/stale, submitting, success
- [ ] Every `errorCode` has a designed message and a state; none swallowed, none shown raw
- [ ] `VALIDATION_FAILED` maps `data.fields[]` onto fields, first error focused; unmapped fields still surfaced
- [ ] `403` renders the permission state — not a login redirect, not a generic toast
- [ ] Error boundary per route, with a designed fallback

## 🔴 State, data and ownership
- [ ] State lives where the design says; no server data duplicated into local state that can go stale
- [ ] What each mutation invalidates or refetches is implemented as briefed (`api-contract.md` §7)
- [ ] Optimistic updates only where designed, each with its rollback path
- [ ] Double submit guarded in the handler, not only by a disabled control
- [ ] No auto-retry on non-idempotent calls; one shared in-flight token refresh

## 🔴 Security
- [ ] Nothing user- or server-supplied rendered as HTML; hrefs/srcs from data validated
- [ ] Tokens handled per `security-logging.md` §B; nothing secret in the bundle or a public env var
- [ ] No PII, token or full payload in console, analytics or error reports
- [ ] Hidden controls are not being used as a permission check

## Accessibility
- [ ] Keyboard: every interactive element reachable and operable; visible focus; no trap
- [ ] Focus moved deliberately on route change, dialog open/close, and after submit
- [ ] Semantic elements (`button`, `a`, `label`, headings in order); ARIA only where semantics fall short
- [ ] Form fields have labels and programmatic error association; errors announced
- [ ] Contrast meets the design system; nothing conveyed by colour alone
- [ ] Images have alt text; decorative images marked as such
- [ ] Checked with the tool the repo has (axe, Lighthouse) — result quoted, or `[unverified]`

## Performance and budgets — measured, never asserted
- [ ] Bundle size per entry vs the budget in `<app>-frontend.md`, from the analyser output
- [ ] Interaction latency vs the budget, measured
- [ ] No unnecessary re-render introduced on a hot path (memo/key/selector where the profiler shows it)
- [ ] Lists that can grow are paginated or virtualised as designed; images sized and lazy where designed
- [ ] Any budget that could not be measured is `[unverified]` with the reason — never an estimate

## Code quality
- [ ] Types strict — no `any`, no untyped API responses, no `as` to silence the compiler
- [ ] Components: one responsibility, props not a grab-bag, no prop drilling past the depth the design allows
- [ ] Functions ~≤ 30 lines, nesting ≤ 2, ≤ 3 params, no flag params
- [ ] Hooks obey the rules of hooks; effects have correct deps and a cleanup; no effect doing what a render or an event handler should
- [ ] Naming per repo and design system; no banned names
- [ ] Comments: why-comments and doc references; no noise, no commented-out code, no TODO without a task id
- [ ] No abstraction without ≥ 2 real usages
- [ ] Size signals checked (`principles.md` §10): file ~≤ 400 lines, component not past the signal — each crossing justified in the PR or split by reason
- [ ] Any component already over a signal that this change touches: named in the brief with keep-or-split stated
- [ ] Styling follows the design system; no one-off magic values where a token exists

## Delivery
- [ ] Build, type-check, lint/format, existing tests green **after rebase**, with commands and counts quoted
- [ ] Manual verification recorded in the report per `SCR` — every documented state, not only the happy path
- [ ] Verified against the mock; integration against the real API done or explicitly still pending
- [ ] PR description complete: state table, measured budgets, contract version; out-of-scope findings listed as proposals
