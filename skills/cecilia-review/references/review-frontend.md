# Reviewing frontend work

Two targets, one file: the **frontend design** (`<app>-frontend.md`) before code exists, and **frontend
code** afterwards. What makes frontend review different is that the defects are rarely in the happy
path — they are in the states nobody implemented and in the authorization nobody enforced server-side.

The visual design by `cecilia-ui` (`<app>-ui.md`, tokens, exports) is reviewed with `review-ui.md`; this
file covers the frontend architecture and the code.

## 1. Reviewing the design (`<app>-frontend.md`)

| # | Check | The failure it catches |
|---|---|---|
| 1 | Every `SCR` traces to an `FR`/`UC`, and every user-facing `FR` has a screen | a requirement with no interface |
| 2 | Every screen lists **all** states — loading, empty (no data vs no results), partial, **one row per error code the endpoints can return**, permission-denied, offline/stale, submitting | the classic source of rework; a happy-path-only design is not a design |
| 3 | Every data element names endpoint + field | "computed somehow" becomes a guess at implementation time |
| 4 | Every endpoint the screens need exists in the contract, or is in "Contract gaps" | the frontend stalls mid-batch waiting for a field |
| 5 | Every piece of state names exactly one owner | bugs that only appear on refresh or back-navigation |
| 6 | Every route states its guard and deep-link-without-permission behaviour | an unguarded route reachable by URL |
| 7 | Client rules name the server rule they mirror, and contradict none | two truths about what is valid |
| 8 | Budgets are numbers with a measuring tool | "fast" is not reviewable and not enforceable |
| 9 | Shared patterns (error/empty/retry/stale) decided once | every screen inventing its own |

## 2. Reviewing frontend code

Ordered heaviest first.

1. **Contract conformance.** The code calls only endpoints in the contract, sends what it promises,
   and handles **every** documented error code. Findings: a hand-written mock that drifted from the
   `.yaml` · a field the UI invents · an error branch that shows a generic message where the contract
   defines a specific one.
2. **States actually implemented.** Walk the design's state table against the code, per screen. A
   state in the design with no branch in the code is a finding, not a nitpick — it was predicted and
   skipped.
3. **Authorization is presentation only.** Hidden buttons are not security. Every guarded action must
   also be enforced by the server (`cecilia-review` security mode owns that check; here, flag any place the code
   implies the client is the enforcement).
4. **State correctness.** Ownership as designed · cache invalidated after mutations, so a list is not
   stale · URL state survives refresh and sharing · no derived data stored and left to diverge ·
   optimistic updates have a rollback that is actually implemented.
5. **Race and lifecycle bugs.** Double submit · a response arriving after the component unmounted or
   after the user navigated · a request not cancelled when inputs change (search-as-you-type) ·
   effects that refire on every render.
6. **Forms.** Validation mirrors the server · server `errorCode` mapped to the right field · the
   submit button's disabled state cannot trap the user · values preserved on failure.
7. **Accessibility**, as the design's level requires: every flow completable by keyboard · focus moved
   and visible on route change and dialog open · form fields labelled and errors associated · images
   with meaningful alt · nothing conveyed by colour alone. Report what was actually checked and how;
   an unmeasured a11y claim is `[unverified]`.
8. **Budgets** measured, not asserted (`common/evidence.md`): bundle per entry vs budget, interaction
   latency vs budget. A PR that changed the bundle without saying so is a finding.
9. **Security of what ships**: no secrets or internal URLs in the bundle · no unsanitised HTML
   injection · tokens stored where the threat model says · no admin-only code shipped to everyone.
10. **Structure and maintainability**: component boundaries follow data ownership (`principles.md`
    §10 size signals apply to components too) · no prop drilling through four layers where the design
    named an owner · shared components changed without checking their other users.
11. **Visual evidence (v18.1)**: the PR/report carries the `visual-check` table — a screenshot per
    `SCR` × state × breakpoint, console result, diff vs the design export, contrast pairs. Missing rows
    are `[unverified]` (not PASS); look at the screenshots themselves — a clipped label, overflow, wrong
    token colour or a state that shows the happy path is a finding with the image path as evidence.
12. **Web interface guidelines**: check the changed files against `references/web-interface-guidelines.md`
    (priority note at its top — the approved design and the project's copy language win). Report
    `file:line - issue`, severity by impact (inaccessible control = BLOCKER on a CORE flow, otherwise
    SHOULD-FIX; typography/copy polish = SUGGESTION).
13. **Style guide discipline**: when `ui.style` is set, it filled gaps only — an approved token, layout
    or component replaced by the style guide, a new font/icon/motion package without Cecilia's yes, or a
    hot-linked external asset is a finding.

## 3. Severity

| Level | Examples |
|---|---|
| **Blocker** | a documented state not implemented on a CORE flow · calling an endpoint outside the contract · client-only authorization on a sensitive action · a mutation that leaves the list stale on a money screen · a form that loses the user's input on error |
| **Should-fix** | missing focus management · unmeasured budget · duplicated error handling that should use the shared pattern |
| **Suggestion** | naming, structure, minor duplication |
| **Question** | "is this screen meant to be reachable by anonymous users?" |

## 4. Also report

- **State coverage table**: `SCR · states designed · states implemented · gap` — the single most
  useful artifact of a frontend review.
- **Measured budgets** with their tool, next to the target.
- **What `cecilia-design` must decide**, where the code revealed a gap the design never settled.
