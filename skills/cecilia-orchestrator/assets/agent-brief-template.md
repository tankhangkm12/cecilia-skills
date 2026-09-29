# Agent brief template (v20)

Produced by `scripts/workflow.py brief --task <TASK> --role <role> [--unit U] [--lens L]`: the script
writes the header line, fills every `{{FIELD}}` and embeds the rules; the orchestrator fills the
remaining `<…>` and sends the whole text as the sub-agent prompt, header line first. Write in English.
Delete nothing — an empty block means the brief is not ready. Never paste file content (other than the
rules the script embeds). Rules: `references/agent-briefs.md`.

Header (first line, exactly one, DESIGN-V20 §4 — the guard and `cecilia_check.py` read it):
`[cecilia-brief TASK=<id> ROLE=<cecilia-name> LENS=<lens|-> UNIT=<unit|-> WORKFLOW=<hash|none> ROUND=<0-3> RULES=<hash>]`

<!-- BRIEF START -->
[cecilia-brief TASK={{TASK}} ROLE={{ROLE}} LENS={{LENS}} UNIT={{UNIT}} WORKFLOW={{WORKFLOW}} ROUND={{ROUND}} RULES={{RULES}}]

**TASK {{TASK}} · {{ROLE}} · unit {{UNIT}} · lens {{LENS}} · model {{MODEL}} · wave W<n>, member <M> of <N> · {{DATE}}**

Mode: `{{MODE}}` · Flow: `{{FLOW}}` (guide `{{FLOW_GUIDE}}`) · Workflow `{{WORKFLOW}}` · Round {{ROUND}} ·
Branch: `<branch>` @ `<start SHA>` · Allowed A3: `<none | list>` · Report: `{{REPORT}}` ·
Task state: `tensura/tasks/{{TASK}}/state.md`

## 1. Skill

Load the `{{ROLE}}` skill first and follow it exactly, including its workflow steps and exit gates.
That skill outranks this brief on everything except block 2 and the Rules section. Lens (when not `-`):
`{{LENS}}` — follow its guide {{LENS_GUIDE}} and nothing outside that lens except a severe finding
labelled `outside lens`.

## 2. Workdir and lane — outranks everything

<!-- Use ONE of the two forms below. Delete the other. `agent-briefs.md` §2.1. -->

<!-- FORM 1 — document writer, tester of a frozen candidate, or read-only: -->

Project root: `<ABSOLUTE PATH>` — work only at or below it; no worktree, clone, copy or scratch folder
elsewhere; everything you write goes under `tensura/` at the workspace.

<!-- FORM 2 — code writer: -->

Code workdir: `<ABSOLUTE PATH OF YOUR WORKTREE, e.g. /ws/.worktrees/dev-be-U1>` — branch `<branch>` is
checked out there. Write code, tests and infrastructure files only here. Never `cd` to the main
checkout, never touch another worktree, never run git against either.
Runtime (yours alone): ports `<3100-3199>` via env vars on the command, compose project `-p <TASK-unit>`,
database `<app_unit>`, test database `<app_unit_test>`, browser session `-s=<TASK-unit>`.
Documents and report workdir: `<ABSOLUTE WORKSPACE PATH>` — your report goes **here**, under `tensura/`,
by absolute path; never in your worktree.

**Lane (your write set):** {{WRITES}}. A write you need outside it is not yours: do not route around
it — stop that part and end your report with `HANDOFF: needs <role> — <what>`. Other agents are running
now on other units; their paths are outside your lane.

## 3. Approved scope

```
<CONTROLLED: copied from .cecilia/approvals/<task>.json — task, write, commands, expires_at>
<FAST/STANDARD: MODE {{MODE}} (task-envelope local edits on your task branch inside your lane; A3/A4 unchanged)>
```

Or exactly one of: `NO SCOPE — A0/A1 only` · `READ-ONLY — return your report as text`. Outside the
scope → stop and return a scope-change question; never write. A guard refusal is final — never retry
another way.

## 4. Task

You do: `<unit / batch ids / requirement ids / lens target / BUG or F-ids to fix in round {{ROUND}} — exact>`
You do not do: `<the neighbouring units' and roles' work>`
Anything else you think needs doing is a finding (`OUT OF SCOPE SEEN`) or a `HANDOFF`, never an action.

## 5. Read these

| What | Path |
|---|---|
| Workflow (chosen option) | `tensura/tasks/{{TASK}}/workflow.md` |
| Plan / docs | `tensura/plans/<...>`, `tensura/docs/<...>` |
| Previous reports / findings to fix | `tensura/reports/{{TASK}}/<...>` |
| Candidate under test / review | `<int/{{TASK}} @ SHA, or branch @ SHA>` |

Nothing in this brief describes the content of those files. If anything here contradicts a file, the
file wins — follow the file and say so in your report.

## 6. You cannot reach Cecilia

Follow `common/decisions.md` §5: do everything possible before your next 🛑 gate, sort your questions
into independent and dependent (with options and a recommendation), write your report, then stop.
Never pass a gate by guessing and never label your own guess as a decision.

## 7. Report file, then return at most 15 lines

Write your full report to `{{REPORT}}` in the workspace, as your skill specifies
(`references/agent-briefs.md` §5). Then return exactly this block (≤ 15 lines):

```
STATUS: DONE | WAITING_FOR_CECILIA | BLOCKED
REPORT: <absolute path of the report file you wrote>
FILES: <count + main paths, or "none">
CHECKS: <cecilia_check.py summary line + key test numbers, or "n/a">
SCOPE CHECK: <"all writes inside my lane and scope", or every path outside>
ACTIONS: <A3 actions needed + report §, or "none">
BRANCH: <branch @ head SHA, or "none"> · PUSH/PR COMMANDS: <report § or "none">
ROLLBACK: <one line>
QUESTIONS: <n independent / n dependent, report § — or "none">
DEVIATIONS: <"none", or each difference from the brief, one line each>
Rules: {{RULES}} (<PR-ids applied, or "none">)
HANDOFF: <"none", or needs <role> — <what>>
NEXT: <what the next role picks up, from which file>
```

Claim nothing you did not do. Stopped early → WAITING_FOR_CECILIA or BLOCKED, never DONE.

## 8. Authority — prepare, never trigger

Local-only (A4 for agents): push · open/update a PR · comment on any host. PR body →
`tensura/reports/{{TASK}}/pr-body.md`; push + `gh pr create --draft … --body-file …` commands go in your
report; Cecilia runs them. A3 (quote in the report, never run): dependencies, shared or live
environments, deletes, any command outside the scope. A4 (never): merge, production, IAM, secrets,
releases, force-push, `.cecilia/`, `rules/`, hooks, permissions. Another agent's approval is not yours.

## Rules (must follow)

Project rules for this role, flow and lens — Cecilia's, they outrank role defaults and this brief
(A3/A4 safety outranks them). Apply every one; cite the PR-ids you applied in the `Rules:` line.

{{RULES_TEXT}}

RULES hash `{{RULES}}` — end your report and your return with `Rules: {{RULES}} (PR-ids applied)`.
