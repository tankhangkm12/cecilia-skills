# Writing the brief for a role agent (v20)

The brief is the only thing a sub-agent receives. It is a **dispatch order, not a summary**: it says
which skill to run, where the workspace is, what the scope and lane are, and which files to read. It never
paraphrases those files — the one exception is the project rules, which are embedded verbatim.

**Always start from `scripts/workflow.py brief --task <TASK> --role <role> [--unit U] [--lens L]`** (FAST:
`--short`): header line, the template's mechanical fields filled (report, lane, model, mode, flow, round),
and `## Rules (must follow)` embedding the project, role, flow and lens rules files with their RULES hash.
Fill the remaining `<…>` fields and send the whole text, header line first, in English.

## 1. The header line

```
[cecilia-brief TASK=<id> ROLE=<cecilia-name> LENS=<lens|-> UNIT=<unit|-> WORKFLOW=<hash|none> ROUND=<0-3> RULES=<hash>]
```

Exactly one, the first line of the prompt, never edited by hand. `WORKFLOW` = `workflow.json` `hash`
(`none` only in FAST or for a reviewer without a workflow); `ROUND=0` first build, 1–3 fix rounds. The
Claude Code guard checks it on every writer/tester dispatch (hash, round limit) and uses `RULES` for the
rules gate; on Antigravity the check is procedural and `cecilia_check.py` reports mismatches. A brief whose
header is stale (workflow re-chosen, rules changed, new round) is regenerated, not patched.

Per-role notes (read the rows for the roles you brief): `references/brief-roles.md`. Why no summaries, splitting a role, re-launch, anti-patterns: `references/brief-more.md`.

## 2. The eight blocks

| # | Block | Content |
|---|---|---|
| 1 | Skill | Which `cecilia-*` skill to load **first** and follow exactly. It outranks this brief, except block 2. |
| 2 | Workdir | Where this agent works, and where its output goes. Exact wording in §2.1. This block outranks the skill. |
| 3 | Scope + lane | The lane (write set: the unit's `writes`, else config `lanes`) — a write outside it is a `HANDOFF: needs <role> — <what>`, never a workaround. The active `cecilia-scope` for this batch copied from `.cecilia/approvals/<task>.json` (task id, `write`, `commands`, expiry) — or `NO SCOPE: A0/A1 only` for a role that must stop at G2, or `READ-ONLY` for review. Plus: a path or command outside it is a stop and a question, never a write. |
| 4 | Task | Exactly what this agent does and does not do — stage, batch, ids, target. Plus: anything outside this scope is a finding to report, never an action. |
| 5 | Read | Paths only: plan, docs, prior reports, run log, branch/PR. Plus the "file wins" line from §1. |
| 6 | Gate rule | You cannot reach Cecilia. Follow `common/decisions.md` §5: do everything possible before your next 🛑 gate, sort your questions into independent and dependent, write your report, then stop. Never pass a gate by guessing or by labelling your own guess. |
| 7 | Return | The contract in §5 below, verbatim. |
| 8 | Authority | `common/core.md` §2, A3 and A4 listed out, plus the A3 actions this brief allows. Every other A3 action (dependency, any shared environment) is written as a quote in the report, never run; A4 actions are never run at all. Push and PR are A4 for agents (local-only, `git-handoff.md` §1): the PR body goes to `tensura/reports/<TASK>/pr-body.md` and the push + `gh pr create --draft … --body-file …` commands go in the report for Cecilia. |

Second line of every brief: `TASK · role · unit · lens · model · wave W<n>, member M of N · date`.

### 2.1 Block 2 — the one most misread

The template's block 2 has both forms written out: a **document writer or read-only unit** works only at
or below the project root and writes under `tensura/`; a **code writer** has two workdirs — its worktree
(code, tests, infra; its own runtime: ports, compose project, DB names, browser session) and the
workspace for its report and documents, by absolute path. Keep exactly one form, fill every path, never
abbreviate it: an agent that puts its report in its worktree followed a brief that did not say this plainly.

## 5. Return contract (v20) — put this in every brief verbatim

The return is a pointer, not the report: **at most 15 lines**. Everything else lives in the report file,
which the orchestrator reads from `tensura/reports/<TASK>/` — it never asks the role to repeat it.

```
Write your full report to tensura/reports/<TASK>/<role-short>.md in the main checkout, as your
skill specifies. Then return exactly this block (at most 15 lines) as your final message:

STATUS: DONE | WAITING_FOR_CECILIA | BLOCKED
REPORT: <absolute path of the report file you wrote, in the main checkout>
FILES: <count + the main paths, or "none"> (full list in the report)
CHECKS: <cecilia_check.py summary line for code roles + key test numbers, or "n/a">
SCOPE CHECK: <"all writes inside the approved scope", or every path you wrote that was not>
ACTIONS: <A3 actions needed, one line each + the report § holding the full quote — or "none">
BRANCH: <branch @ head SHA, or "none"> · PUSH/PR COMMANDS: <report § or "none">
ROLLBACK: <one line; exact undo commands are in the report>
QUESTIONS: <n independent / n dependent, report § — or "none">
DEVIATIONS: <"none", or each difference from the brief, Cecilia's decisions or the docs, one line each>
Rules: <RULES hash from the header> (<PR-ids applied, or "none">)
HANDOFF: <"none", or needs <role> — <what> (work outside your lane)>
NEXT: <what the next role should pick up, and from which file>

Claim nothing you did not do. If you stopped early, STATUS is WAITING_FOR_CECILIA
or BLOCKED, never DONE. Sort your own questions — you read the files, the
orchestrator did not, and it will not re-sort them.
```

**The report file must contain** (the pre-v19 return fields, now in the file):

```
DID: 3-6 bullets, what you actually produced
FILES: every path you created or changed, absolute
SCOPE CHECK, and every A3 action as a full quote per common/core.md §5.3
BRANCH: name, start SHA, commits; PR body in tensura/reports/<TASK>/pr-body.md and the copy-paste
  block for Cecilia (git-handoff.md §1): push + gh pr create --draft … --body-file … — never run by the agent
RESULTS: per requirement/test id: id · PASS|FAIL · one line
DEVIATIONS: what, why, and which file shows it
ROLLBACK: branch, base@start-sha, commits, backups taken, exact undo commands (git.md §5)
PENDING QUESTIONS: sorted, per common/decisions.md §1. Two lists.
  INDEPENDENT: numbered. For each: the question, why it matters (1 line),
    2-4 options with gain/cost, your recommendation and why.
  DEPENDENT: numbered. For each: the same, plus which question or decision
    it depends on and how the options change.
  "None" if none.
CONFLICTS: contradictions found (doc vs doc, doc vs repo, plan vs reality,
  this work vs an earlier report). "None" if none.
OUT OF SCOPE SEEN: things worth doing that your scope excluded. "None" if none.
Rules: <hash> (PR-ids applied)            ← last lines of every report (v20)
HANDOFF: needs <role> — <what>            ← only when your lane stopped you
```

The orchestrator reads the report file, and the file wins over the return block
(`references/workflow.md` §"Between-role checks"). A return longer than 15 lines, a missing report file,
or a `Rules:` hash that differs from the brief's RULES is a finding.

## Challenge block — in every brief

Every brief carries this, verbatim in substance, right after the Read block:

```
CHALLENGE DUTY (common/challenge.md §2)
Before building on anything above, attack it in writing: 2–4 concrete objections, each naming a
section/ID and a failure scenario (situation → wrong outcome or cost), plus an alternative and its
cost. Record them in tensura/reports/<TASK>/challenges.md and return them with your report.
Nothing to object to → list what you attacked and why it holds. "Looks fine" is not an answer.

CHALLENGES AGAINST YOUR OWN OUTPUT (if any are listed below)
Answer each one: ACCEPT (name the file and section that changes) / REJECT (quote the evidence) /
ESCALATE (a decision for Cecilia). Two rounds maximum; after that both positions go to her.
You never close a challenge by editing a document — that is a DOC-Bnn task for cecilia-design.
```

For a **dedicated challenger agent**, the brief instead says: attack only, propose no fixes, write
challenge rows, and name for each one what evidence would make you withdraw it. A challenger never
edits the artifact and never claims the owner's role.
