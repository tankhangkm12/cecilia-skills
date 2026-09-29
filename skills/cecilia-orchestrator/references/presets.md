# Option shapes — what to put in the 2–3 options (v20)

Opened at O1 (`references/workflow.md`). A shape is a starting point for the options on the decision
card, never a decision: the merged plan's units and shapes come first (`references/consensus.md` §4); the
options always differ in agents per kind, split and lenses, and each carries its `[projected]` estimate
from `scripts/workflow.py options`. From STANDARD every option also carries the consensus runs (plan 3 + 3 +
1, review 3 voters + 1 minutes writer per round), which are the same in every option. Every unit is an enabled role; an off role
is replaced by its fallback owner (`workspace.md` §1) or reported as missing. `‖` = same wave, launched in
one message, each writer with its own worktree/branch/ports/DB (`common/parallel.md`).

## By situation

| Situation | Mode | Build units (lean → wide) | Test lenses | Review lenses (STANDARD 3–4 · CONTROLLED 5–6) |
|---|---|---|---|---|
| typo / CSS / small known bug | FAST | one dev-be **or** dev-fe (no options) | focused check in the role | one reviewer if useful |
| normal feature, one layer | STANDARD | dev ×1 → dev ×2 by module | functional (+ integration) | correctness, tests, simplicity (+ the lens the diff needs) |
| FE + BE feature | STANDARD | dev-be ‖ dev-fe → + db ‖ or dev-be ×2 by module | functional, integration, ui | correctness, api-consumer, security or data |
| bug with unclear cause | STANDARD | `rootcause` stage first (3 diagnosers vote); dev ×1 → + a measurement batch when no cause is `[verified]` | functional (regression) | correctness, tests, data |
| test coverage only | STANDARD | — (test units are the work) | the lenses asked, one agent each | tests, correctness, simplicity |
| schema / migration / slow query | CONTROLLED if schema | db → dev-be; or db ‖ dev-be on disjoint paths once the schema is frozen | database, integration, concurrency-perf | correctness, data, performance, operations, security + redteam |
| auth, money/quota, tenants, public contract | CONTROLLED | design → dev-be (‖ dev-fe) → + db | functional, security, integration, concurrency-perf | correctness, security, data, api-consumer, tests + redteam |
| new screens / design system | STANDARD | ui → dev-fe; or ui → dev-fe ×2 by screen group | ui, functional | correctness, ui, simplicity (+ api-consumer) |
| CI/CD, image, manifests, IaC | CONTROLLED | devops ×1 → devops ×2 by pipeline/env | infra (validate only, never apply) | correctness, operations, security, simplicity, tests + redteam |
| open design choice | STANDARD | design ×1 → competing ×2 prototypes | functional, concurrency-perf | correctness, performance, simplicity |
| audit only | any | — | — | review panel or one reviewer on the target |
| production / release | CONTROLLED | devops (release packet) | infra | correctness, operations, security, data, tests + redteam; Cecilia executes production |
| incident | CONTROLLED semantics | `rootcause` stage (3 devops diagnosers, read-only) → devops (prepared commands) | — | operations, correctness; Cecilia runs recovery |

## Making three options

- **A — lean:** fewest agents that still cover every changed layer; the minimum lenses for the mode.
- **B — wide:** split the largest layer by module (disjoint paths), one more test lens where risk is
  (security, concurrency-perf), one more review lens. Costs tokens, not wall time — a parallel wave is one step.
- **C — competing or deep** (only when it earns its place): two units build the same seam two ways when a
  design decision is open or Cecilia asks; or a stronger model on the CORE unit plus the deepest lenses.

Write sets decide what can split: two units of one role in one module collide in the router and DI
module every time — split along the plan's own seams (batch, module, screen group, service), never
"half the batch each". `workflow.py options` rejects overlapping write sets in a module/layer split.

## Dependencies that add a unit

Only when its output is actually missing: design when behaviour/contract/architecture is unsettled · db
when schema, migrations, query performance or growth is part of the change · ui when screens are new and
cecilia-ui is on · plan when coordination or a CONTROLLED scope needs it · devops for delivery/platform
work · api-ux (when on) after a contract draft and after dev-be changes an API. A missing optional role is
not a defect; a missing **required risk control** is.

## Auto-selection examples

| Request | Mode · shape |
|---|---|
| “đổi label Login thành Sign in” | FAST · one dev-fe |
| “thêm endpoint lấy profile” | STANDARD · normal feature, one layer |
| “thêm UI + API cho cancel order” | STANDARD · FE + BE feature |
| “đổi authZ tenant isolation” | CONTROLLED · auth |
| “thêm migration đổi schema orders” | CONTROLLED · schema |
| “sửa GitHub Actions / Helm / Terraform” | CONTROLLED · CI/CD |
| “review PR này” | audit only |
| “thiết kế màn hình đặt vé” | STANDARD · new screens (ui on) else design(frontend) → dev-fe |
