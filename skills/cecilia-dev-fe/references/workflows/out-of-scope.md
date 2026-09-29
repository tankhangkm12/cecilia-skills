# Work outside the docs: propose, never just do

<!-- scoped source: shared/scoped/dev/out-of-scope.md — synced into cecilia-dev-be and cecilia-dev-fe. Do not edit a copy. -->

Out of scope = any change not traceable to a requirement ID in the plan: performance tweaks, refactors,
renames, cleanups, fixing a bug you stumbled on (even one line), extra validation/logging/caching/
retries/indexes/memoisation, new or upgraded dependencies, tool config changes, doc edits.

Why strict: unrequested changes mixed into a PR make it slower to review, harder to revert, and slip
behaviour changes past everyone who signs off. Good ideas still matter — they take their own road.

## Three approvals

```
① proposal with options ──► Cecilia chooses to do it
② architecture & flow agreed ──► Cecilia agrees
③ explicit permission to start ──► then code
```
② and ③ may share a message but ③ must be an explicit question; silence is not permission.

**① Proposal** — in the report ("Needs your decision") and the PR section "Out-of-scope proposals"; do
not interrupt the main flow unless it is severe (data loss, security hole) → report immediately. Numbers
for the problem (`numbers.md`), options per `decisions.md` §6:

```markdown
**P2 — N+1 query when listing orders** (`order.repository.ts:88`, not in docs)
   (frontend example: the orders list re-renders every row on each keystroke — `OrderList.tsx:88`)
Problem: one extra query per order → 50 orders = 51 queries; measured 420 ms at 50 orders [verified M-07].
- A. Do nothing
- B. New task after this epic (cecilia-plan adds it)
- C. Separate batch inside this epic
- D. Fold into current batch (not recommended: mixes perf with feature)
I lean to B.
```
Always include "do nothing". Never a single option.

**② Design** — where (module/files/layer or feature module/components), contract/schema impact,
shared-component and design-system impact (frontend), before/after flow, ≥ 3 approaches when they exist,
dependency / migration / budget (bundle, latency) / accessibility / test impact, which batch and branch.

**③ Permission** — "May I start P2 with option X on branch …?" → wait.

Approved → it becomes a traced item (`X-nn`, approved date) that cecilia-plan should add; implement like any
batch on its own branch; commit type matches its nature (`perf`, `refactor`, `fix`).

**No separate proposal needed only for:** registering the new module in the app wiring, or fixing
type/lint errors your own change caused — and in CONTROLLED only when that file is inside the approved
`cecilia-scope`. Unsure → it is out of scope; ask.
