# cecilia-plan — full rules and workflow

The SKILL card holds the summary; this file holds the detail. Open it at the first step on STANDARD/CONTROLLED work.

## Authority

Read repo/docs/reports and write plan/report files under `tensura/`. Never implement the plan, run the
mode/approval tools, approve itself, merge, push or open a PR, or touch production/secrets. Push and PR are
A4 for agents (local-only, `git-handoff.md` §1): a plan never contains a push step for an agent — its final batch
ends with the push + `gh pr create --draft … --body-file tensura/reports/<TASK>/pr-body.md` commands that
Cecilia runs herself.

## Choose planning depth

The depth table is on the SKILL card (FAST one sentence · STANDARD 2–5 steps with units · CONTROLLED full
batches with scope blocks). Do not emit a machine scope block for STANDARD merely because the format exists.

## Create

**P0 — Locate.** Start from `tensura/tasks/<TASK>/scope.json` (discovery's goal, constraints, done_when,
assumptions, signals) when it exists, then read only the authoritative docs/code needed to understand the
requested change and current repo shape. Do not require complete project documentation for an ordinary
local task.

**P1 — Measure unknowns; never ask facts.** A fact (a path, a version, a config value, how the code
behaves, what the cluster runs) is measured with read-only tools and labelled; an `[unverified]` assumption
from `scope.json` is checked now or becomes the first measurement batch. Only a preference or risk choice
that materially changes implementation is a question — written with its choices and a recommended default
for the decision card, never an open "what do you want?". No task IDs, role rosters, worktrees or formal
acceptance tables unless the chosen mode/work actually needs them.

**P2 — Build the plan.**

For STANDARD, use:

```text
Goal: <one sentence>
Plan:
1. <step>            [role · branch · parallel with: <step n> | after: <step m>]
2. <step>
3. <step>
Simpler option: <the simplest approach that would also work; why this plan is not simpler>
Likely touch: <modules/files>
Units: <unit id · role · write set · seams · after: <unit> · test lenses>   (one row per unit; disjoint write sets)
Checks: <relevant tests/lint/build>
Backup: <checkpoint / DB dump / none, why>
Stop if: <contract/schema/security/infra/material-scope trigger>
Handoff: local-only — last step ends with the push + Draft PR commands for Cecilia (git-handoff.md §1), no push step
State: tensura/tasks/<TASK>/state.md
```

With `plan_first` on for the mode (default for STANDARD), the plan waits for Cecilia's OK — from
STANDARD that OK is her answer on the task's decision card, not a separate question; otherwise her original
request is enough to continue.

**Task state.** Every plan names `tensura/tasks/<TASK>/state.md` (goal, mode, branch + start SHA,
steps done / next, pending decisions, report paths). Create it with the plan if it does not exist; update
it at each stop; read it first when resuming.

**Local-only handoff.** No step or batch pushes, opens a PR or comments on a host. The final step
(STANDARD) or final batch (CONTROLLED) ends with "commands for Cecilia": the role writes the PR body to
`tensura/reports/<TASK>/pr-body.md` and puts the push + `gh pr create --draft … --body-file …` commands in
its report; Cecilia runs them (`git-handoff.md` §1). "Done when" for a code task is "commands ready for Cecilia",
not "pushed".

**Parallel by default — units feed the options (v20).** From STANDARD the plan is the input of the
orchestrator's options (`workflow.py options`), so it names **units**: each unit has an id (module, service,
app or layer), the role that builds it, its **write set** (path globs, disjoint from every other unit's —
shared hot files get one owner, `parallel.md` §2), the seams it relies on (contract version, schema, env
names), its dependencies and the test lenses it needs. Units that are disjoint and share only settled seams
may run in the same wave, one instance of the role per unit, branch `feature/<TASK>-<nn>-<role>-<unit>`
(`git.md` §1). The plan does not pick the number of agents or a cap — the options propose them and Cecilia
chooses (`parallel.limits` only when she set one; legacy `parallel.max_writers` counts as the `dev` limit).
Units that cannot be made disjoint → say so; they run in sequence or as a `competing` option. Choices inside the plan come with options (`decisions.md` §6) and sizes with
projections (`numbers.md`).

For CONTROLLED, use `references/planning-method.md`: requirement traceability, reviewable batches,
exact paths, dependency proof, test/review rows, one branch per batch, waves, and `cecilia-scope`
blocks (with `"worktree"` when the batch runs in parallel). Include generated files,
lockfiles, migration registries, routers/DI modules and other real write paths rather than vague globs.

**P3 — Challenge.** STANDARD: the consensus critique round (§Consensus) is the challenge; outside a
consensus run challenge only the material uncertainty (often one developer/test viewpoint is enough). CONTROLLED: dev-be/dev-fe/test/review (plus db and ui when their rows are in the plan and they are on)
challenge the plan before G2 using
`references/common/challenge.md`.

**P4 — Handoff.** STANDARD: return the short plan with its units to the orchestrator, which turns it into
2–3 options for Cecilia; no G2. Called directly without an orchestrator: hand to the relevant dev/test role.
CONTROLLED: present G2 and the exact human commands:

```bash
cecilia mode controlled
cecilia approve tensura/plans/<plan>.md --all
```

(`--all` approves every batch's scope block in one run; `--task <TASK-B01>` approves one.)

The agent never runs them.

**P5 — Report.** Full plan/report to `tensura/plans/<plan>.md` and `tensura/reports/<TASK>/plan.md`;
chat/return ≤ 15 lines (status · plan path · steps/batches/units · open decisions · `Rules:` · `Deviations:`); update
`tensura/tasks/<TASK>/state.md` at each stop.

## Consensus (from STANDARD) — compete, critique, merge

The orchestrator never plans: three planners do, independently, and `workflow.py tally` counts their votes
(cecilia-orchestrator `consensus.md`). The brief's CONSENSUS block says which part you play. Each planner is
its own subagent (Agent/Task, Antigravity `invoke_subagent`), header `ROLE=cecilia-plan UNIT=p<n>`; the tally
checks provenance — a ballot the orchestrator wrote is discarded, an unverified one is flagged on the card.

**Competing `p<n>`.** Write `tensura/plans/<TASK>-p<n>.md` from `scope.json` alone, with no model or agent
name in it: a normal plan plus one row per decision point — `rootcause` (bugs/incidents) · `approach` ·
`order` (batch order, why) · `rollback` (per batch; what cannot be undone) — each with your choice, its
evidence (`[verified]` path, command + output, file:line) and the rejected alternative.

**Measurement first.** A root cause is `[verified]` only when you reproduced it or read the causing line at
the current SHA. Otherwise the first batch is a **measurement batch** (read-only: `EXPLAIN`, logs,
`kubectl get/describe`, a failing test) naming the result that would change the plan; no fix batch before it.

**Critic `p<n>`.** Read the other two plans (no ballot, no author), check their claims yourself, write only
`tensura/tasks/<TASK>/votes/plan/p<n>.json`: one item per decision point of each other plan, id
`<point>-p<k>` (e.g. `approach-p2`), `agree`/`disagree` + evidence + one-line reason; your own `abstain`;
`safety` (data-loss | secret | destructive) whenever a point risks it.

**Merger.** After the tally, one fresh planner writes `tensura/plans/<TASK>.md`: the **adopted** points
only, the units (§P2) and 2–3 option shapes (agents per kind, split, lenses). Every **open** point (no
majority, or two conflicting adopted), every **veto** and every `scope.json` question → `## Open for the card`: choices from the plans,
the most-agreed one as default, why. Never settle an open point or add a point no planner proposed.

## Track

Report measured state, not impressions: completed/total task or requirement IDs when those IDs exist,
current branch/SHA/PR when relevant, failing checks, blockers, open review findings, and next decision.
Read `tensura/tasks/<TASK>/state.md` first and update it with the measured state.
For ordinary STANDARD work, a concise “done / failing / next” status is better than a full control
packet.

## Adjust

When facts change, show before → after for affected plan steps and why. STANDARD updates the chat/file
plan directly when it stays inside Cecilia's task. CONTROLLED scope changes need a new G2 approval.

Templates in `assets/` remain available for complex planning; they are not mandatory for daily work.
