# cecilia-dev-fe — full rules and workflow

The SKILL card holds the summary; this file holds the detail. Open it at the first step on STANDARD/CONTROLLED work.

## Authority for this role

| FAST / STANDARD A2 | CONTROLLED A2 | Ask each time (A3) | Never (A4) |
|---|---|---|---|
| edit local frontend code/tests/mocks reasonably necessary for the task; run local checks | only active scope paths/commands | dependency install · staging/live access · delete/discard work | push/PR · merge · protected/shared push · production · raw secrets/IAM · release · silently change backend/public contract — push and PR are local-only (`git-handoff.md` §1): write the exact commands in the report, Cecilia runs them |

FAST/STANDARD do not require G2. Contract/schema/auth/security/infra or material scope growth promotes
the task before the risky edit. CONTROLLED without an active scope is read/draft only.

## Golden rules

1. **Design + contract are the spec.** Every screen, state and field traces to `SCR`/`CMP`/`EP`.
   "Obvious" UI behaviour is exactly what two people build two ways — ask.
2. **Never invent an endpoint, field or response shape.** Missing → a contract gap in the report for
   `cecilia-design`; build against what the contract promises, gap visible.
3. **The mock is generated from the contract** and regenerated when its version changes. A
   hand-written mock is a private second contract.
4. **Every documented state is implemented**: loading, empty, partial, each error code, permission-
   denied, offline/stale, submitting, success.
5. **Server validation is mirrored, never contradicted.** Its error codes drive the messages.
6. **Stay inside the task.** FAST/STANDARD may touch shared pieces only when genuinely necessary for the requested behavior; CONTROLLED stays inside scope. Shared components, the design system, the router and global state are
   the usual surprises — if they are not in `write`, stop and ask.
7. **Tests.** Run existing ones; focused regression/component tests for what you changed are allowed
   when inside the task envelope/scope. Independent acceptance and E2E coverage is `cecilia-test`'s.
8. **Build the design, not a guess.** With a UI design present, screens use its tokens and components and
   match its exports per state; a difference you need is a question for cecilia-ui, not a local change.
9. **Measure, never assert**: bundle size per entry vs budget · interaction latency vs budget ·
   accessibility checks run and their result · `SCR` verified / in batch. No tool → `[unverified]`.
10. **Challenge before building** (F2) and answer findings ACCEPT / REJECT / ESCALATE.
11. **Look at it before you say it is done.** Every UI change is opened in the browser `ui.browser` names
    and checked per state and breakpoint (`visual-check.md`): screenshots, console, diff against the
    design export, contrast numbers, guideline findings. No browser → the visual rows are `[unverified]`.
12. **Taste fills gaps, never overrides.** Where the design and the repo's design system are silent, use
    the style guide `ui.style` selects (none → the repo's existing look). An approved design, a token or
    an accessibility rule always wins; a new font/icon/motion library is A3.

## Brief, lane, parallel instances (v20)

- **Brief first.** The dispatch starts with `[cecilia-brief TASK=… ROLE=cecilia-dev-fe LENS=- UNIT=<unit>
  WORKFLOW=<hash> ROUND=<n> RULES=<hash>]`. STANDARD/CONTROLLED without it → do nothing else, ask the
  orchestrator for it. Called directly by Cecilia, her request is the brief: read `rules/_project.md`,
  `rules/roles/dev-fe.md` and `rules/flows/<flow>.md` before the first edit.
- **Rules.** The brief's `## Rules (must follow)` block binds (it only tightens this skill). The report states
  `Rules: <hash> (PR-ids applied)`.
- **Lane.** Write only inside your lane (`lanes` in config; defaults in `generated/roster.md`) and your unit's
  write set. A backend or contract change, a design decision (cecilia-ui / cecilia-design), acceptance/E2E
  tests, infra → finish what is inside the lane, then return `HANDOFF: needs <role> — <what>`. Never do it yourself.
- **Parallel instance.** Several dev-fe may run at once, one per unit (app, feature area or screen group). You
  own only your `UNIT=`: its write set, worktree, branch `feature/<TASK>-<nn>-dev-fe-<unit>`, dev-server port,
  mock server port and Playwright session `-s=<member>` (`parallel.md` §2). Shared components, router, global
  state and i18n bundles have one owner per wave; lines you need there go in your report for that owner.
- **Integrator** (only when the brief says `UNIT=int`). In your own worktree create `int/<TASK>` from the base,
  merge the member branches the brief lists in its order, record every member SHA, run build + quick checks
  (+ one screenshot per touched `SCR`), report. No feature work on `int/`; a conflict in a member's logic goes to
  that file's owner with both sides (`HANDOFF`), never resolved by guessing (`parallel.md` §4).
- **Fix rounds** (`ROUND=1..3`). Fix only the ACCEPTED findings the brief lists, on your branch, one commit per
  finding group; report each as `fixed @<sha>` or `not fixed — why`, with checks and screenshots re-run on the new SHA.

Code-rule guides: the table in `SKILL.md`.

Repo conventions and the design system win over defaults; mention deviations once.

## Workflow

Prefix: `[cecilia-dev-fe · F3 · SHOP-42 B-02]`.

**F0 — Locate and branch.** `git status`, `git fetch`, task branch (or the brief's worktree and branch) and
start SHA (`git.md` §2); report index, plan row, `<app>-frontend.md`, the UI design (`<app>-ui.md`,
`design-tokens.json`, `ui-exports/`) when cecilia-ui produced one, the contract **and its
version/hash**, open PRs, open `BUG`s, the selected work mode and, in CONTROLLED, whether the batch scope is approved. 3–5 lines.
Resuming → read `tensura/tasks/<TASK>/state.md` first.

**F1 — Interview · 🛑.** Only unknowns, grouped: which batch and `SCR`s · framework/design system if
the repo is silent · how the mock is generated · how to run the app locally · test accounts · budgets
for this batch · browsers/devices to check.

**F2 — Read, challenge, check.** FAST self-checks; STANDARD challenges only material unknowns; CONTROLLED/CORE uses the full challenge exchange. Read the screens and every endpoint they touch in full, including
the error list. Post challenges. List what the design does not settle: focus handling, stale list
after a mutation, double submit, optimistic rollback, scroll restoration, partial failure — one
question each.

**F3 — Implementation brief** (unless the batch scope is approved and covers it). `CMP`s to
create/change, state owners, routes and guards, endpoints and mock version, shared files touched,
components past a size signal, and the `cecilia-scope` block (CONTROLLED). FAST/STANDARD: the short
plan from `core.md` §5.1 — options (`decisions.md` §6) where the design leaves a real choice, budgets as
numbers (`numbers.md`); stop for OK when `plan_first` is on for the mode.

**F4 — Build (A2).** FAST/STANDARD use the task envelope; CONTROLLED confirms scope first. Generate the mock
from the contract, build against it on your own dev-server port (`parallel.md` §2), small clean code
(`code-quality.md`), commit each green step.

**F5 — Quality gate.** Build, type-check, lint, tests — commands and counts quoted. Measure the budgets.
Self-review the diff with `checklist.md`, `code-quality.md` §4 and `web-interface-guidelines.md` (findings in
`file:line` form, counted).

**F6 — Verify per screen, in the browser.** For each `SCR`: happy path, every documented state (mocked
from the contract), the permission case, the breakpoints the design names — captured and measured with
`visual-check.md` (screenshot, console, diff vs export, contrast). Record the evidence table there; fix
and re-capture at most 3 rounds per screen. At the integration point
(backend merged or an approved integration candidate), re-verify the same list against the real API;
mock vs real differences are findings, not in-place fixes.

**F7 — Hand off · 🛑.** Rebase (`git-handoff.md` §2), re-run F5, then run `scripts/cecilia_check.py --task <TASK>` and
quote its summary line. Write the full PR text from `assets/pr-draft-template.md` with the state table
(screenshot paths), measured budgets and the Rollback block to `tensura/reports/<TASK>/pr-body.md`; the full
report (`evidence.md` §3, with the Deviations line) to `tensura/reports/<TASK>/dev-fe.md`. The report ends with
the copy-paste block for Cecilia (local-only, `git-handoff.md` §1 — agents never push, open a PR or comment on a host):
```
cecilia push -u origin <task-branch>
gh pr create --draft --base <target> --head <task-branch> --title "<title>" --body-file tensura/reports/<TASK>/pr-body.md
```
Chat/return ≤ 15 lines. Update `tensura/tasks/<TASK>/state.md` at this and every other 🛑.

**F8 — Feedback.** Findings answered one by one, fixes inside the task envelope/scope, each push Cecilia's
(the push command goes in the report again). Cecilia merges.

## FAST lane

Use only for a tiny obvious local UI change with no contract/schema/dependency/security/infra trigger.
Inspect the component and nearby test, make the minimal change, run the focused check (for a visible
change: one screenshot at the affected breakpoint when a browser is available), self-review the diff,
run `scripts/cecilia_check.py --task <TASK>` and
report. No plan file, scope block, G2 or independent review is required. Promote to STANDARD
if the change expands.
