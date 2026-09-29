# Frontend design → `<app>-frontend.md` (path per `references/common/workspace.md` §2.1)

Architecture, not visual design: structure, data, states and behaviour. Layout, colour and typography belong to `cecilia-ui` when it is on in `.cecilia/config.json` — it designs every SCR × state listed here. When it is off, they are out of scope unless Cecilia asks; if she has a design system, record its name and where components come from.

No API contract yet → design screens, states and components anyway, and produce the **data requirements list** the contract must satisfy — that list is how the backend learns what the frontend needs before either exists.

**FE-0 — Locate.** Read `requirements.md`, `<unit>-api.yaml` if it exists, any existing `*-frontend.md`, the repo
(is there already a frontend, with conventions to follow?), `DECISIONS.md`. ≤ 10 lines.

**FE-1 — Challenge upstream · 🛑.** 2–4 concrete objections against the SRS and the contract: a journey
with no screen, a permission rule no screen enforces, an endpoint returning data no screen shows, an
error code no state handles. Record in `tensura/reports/<TASK>/challenges.md`.

**FE-2 — Interview · 🛑**, in grouped gates, in this order:
1. Platform and target: web / mobile web / native shell · browsers and devices to support · does SEO
   or first-load time matter (this decides rendering strategy).
2. Framework and rendering: options with trade-offs, researched versions; repo convention wins if one
   exists.
3. Design system: existing one, component library, or build from scratch.
4. State strategy: server-cache library vs hand-rolled · what lives in the URL · form library.
5. Auth in the UI: where the token lives, what a session expiry looks like to the user, what a
   permission-denied screen does.
6. Offline, real-time, and optimistic updates: needed at all, and for which screens.
7. i18n, timezone and money formatting: which locales, who owns the strings.
8. Budgets: bundle size, interaction latency, accessibility level.

**FE-3 — Screens · 🛑.** Inventory with `SCR-nn`: purpose · actor · entry points · data shown · actions ·
permissions · which `FR`/`UC` it serves. Then per screen, **the full state table** (loading, empty, partial, each error code, permission-denied, offline/stale, submitting, success) and the
**data table**: element → source endpoint (`EP-nn`) → field → what happens when it is missing.

**FE-4 — Components and state.** Component tree with `CMP-nn`, each with its props, its owner screen,
and whether it holds state. Shared components named once. The state ownership table (server cache · global · URL · form · derived — exactly one owner each). Routing
map: path → screen → guard → what happens on a deep link without permission.

**FE-5 — Forms and validation.** Per form: fields, client rules, and **which server rules they mirror**
(`BR-nn` from the SRS, error codes from the contract). Client validation never replaces server
validation and never contradicts it — where they differ, that is a finding.

**FE-6 — Write `<app>-frontend.md`, run the exit gate**, print every row with evidence:

| # | Check |
|---|---|
| 1 | Every `SCR` traces to ≥ 1 `FR`/`UC`, and every user-facing `FR` has ≥ 1 `SCR` |
| 2 | Every screen has all states — loading, empty, partial, **every error code it can receive**, permission-denied, offline, submitting |
| 3 | Every data element names its endpoint and field; nothing is "derived somehow" |
| 4 | Every endpoint the screens need exists in the contract, or is in "Contract gaps" |
| 5 | Every piece of state names exactly one owner |
| 6 | Every route states its guard and its deep-link behaviour |
| 7 | Every form's client rules name the server rule they mirror |
| 8 | Budgets stated as numbers, with how they will be measured |
| 9 | Every technology choice cites a source and a version |

**FE-7 — Report · 🛑** (`common/evidence.md` §3) + the two metrics + the contract-gap list, which goes to
`cecilia-design (backend mode)` as change requests. Then one question: what next.

## Contract gaps — the section that earns this skill its place

```markdown
| # | Screen | Needs | Contract provides | Proposed change | Blocks |
|---|---|---|---|---|---|
| G-01 | SCR-04 order list | item count per order | order object has no count | add `itemCount` to GET /orders | FE-B02 |
```

Every row is a question for `cecilia-design (backend mode)` and a decision for Cecilia. Found during design, a gap
costs one contract edit; found during implementation, it costs a stalled frontend batch and a backend
change mid-flight. This table is the cheapest thing in the whole workflow.
