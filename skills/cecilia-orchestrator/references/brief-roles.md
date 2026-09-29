# Briefing — per-role notes and review panel briefs

Part of `agent-briefs.md` (the blocks and the return contract live there). Read the rows for the roles you are briefing.

## 3. Per-role notes

| Role | Scope names | Read block must include | Ends at |
|---|---|---|---|
| cecilia-discovery | mode (scope / onboard / requirements / reconcile) + scope; scope mode: Cecilia's prompt verbatim | repo root, existing `tensura/docs/`, the brief | scope: `tensura/tasks/<TASK>/scope.json`; else docs written + exit gate table |
| cecilia-design | mode + stage + service (`backend · S-LLD · order`) | `tensura/docs/` (README, DECISIONS, all existing stage docs), the brief/idea source | stage doc written + exit gate table |
| cecilia-plan | epic id; Create / Track / Adjust; consensus part (`p<n>` compete / critique, or merge) | `scope.json`, doc paths (exact files), `tensura/reports/<TASK>/`, repo root; critique: the other two plans; merge: `votes/plan-result.json` | `<TASK>-p<n>.md`, ballot, or merged plan with open points |
| cecilia-db | task type (schema / performance / growth / DB code / connections / engine / migration) + unit | module design, the database doc, migrations folder, the code issuing the queries, engine + version, where measurements may run | database doc + migrations + measurements; shared/production actions as quotes |
| cecilia-dev-be / cecilia-dev-fe | batch id + its requirement ids, task type (feature / bugfix / refactor / scaffold / PR comments) | plan path, the doc sections the batch cites, contract version, latest dev+review+test reports, open `BUG-nn`, base branch | report + `pr-body.md`; push + Draft PR commands in the report for Cecilia |
| dev-be / dev-fe as **integrator** | `int/<TASK>` + conflicting branches @ SHA + conflicted paths | docs for both sides' intended behaviour, both members' reports | conflicts resolved on `int/<TASK>` in its own worktree, suite green |
| cecilia-ui | app + SCR ids + tool (`D-nn`, or ask) | requirements, `<app>-frontend.md`, contract, existing tokens/UI doc, `DECISIONS.md` | UI doc + tokens + exports; design-tool writes follow `ui.design_writes` |
| cecilia-test | batch or feature + test levels wanted | plan, AC/LLD/API doc paths, the branch or PR under test, `test-cases-<svc>.md` | test code + run report + bug reports; push/PR commands in the report for Cecilia |
| cecilia-api-ux | round (1 or 2 of max 2) + target: contract draft (design API stage) or dev-be change on branch @ SHA | contract path + version, requirements/journeys, frontend screens, code + schema when after dev-be, load assumptions, previous `api-ux.md` and the owners' fix reports | `tensura/reports/<TASK>/api-ux.md` with `AUX-nn` (owner + measurable acceptance); edits nothing |
| cecilia-review | the concrete target: PR url/diff, test suite path, doc set, or release | the target, plus plan + docs to judge it against | severity-ranked report; edits nothing |
| cecilia-devops | the change + target environment (`ENV-nn`), or the live incident (`INC-nn`) | plan, the infrastructure docs, prior devops/incident reports, the repo's infra paths, branch/PR | files + static gate + prepared apply quotes, or incident evidence with prepared recovery commands |
| cecilia-extend | role / flow / lens + name to scaffold | `docs/EXTENDING.md`, the registry | proposal in `tensura/extensions/<name>/`; Cecilia applies it |

| (orchestrator itself) briefing | which briefing (full status / one area / quality posture / decision queue) + `<TASK>` | `tensura/README.md`, the reports index, plan + status table, `challenges.md`, `metrics.md`, `DECISIONS.md`, the review reports, the PR state, and which report surface is connected | draft briefing written, waiting for verification — **not** published |
| cecilia-review (panel) | `mode: panel-reviewer, lens: <lens>`, `panel-voter` (v1–v3) or `panel-minutes` | only what §"Review panel briefs" lists — never the author's report | lens: findings as text · voter: its two ballots · minutes: `panel/verdict.md`; edits nothing else |
| cecilia-review (verify mode) | the exact draft to check + `<TASK>` | the draft path, every source it cites, and the logs it should have cited (`metrics.md`, `challenges.md`, plan status, review reports) | verification note with `PASS` or discrepancies; edits nothing |

Launch each role with its own agent definition from the package's adapters (Claude Code
`.claude/agents/`, Antigravity `.agents/agents/`): writers get edit and shell
tools and the guard; `cecilia-review` gets read-only tools — a voter or minutes writer writes only its own
ballot or minutes file. Never launch review with a write-capable agent because it is "quicker".

Workdir shape: code writers (dev-be, dev-fe, test, devops, db) split — worktree for code, the workspace for
report and documents; discovery, design, plan, ui, api-ux single workdir, only their `tensura/` files;
review read-only, report as text. Lanes per role: config `lanes` (registry defaults).

**Extra blocks for a `cecilia-devops` brief**, after block 5:

```
APPROVAL: You may not approve your own applies. Every read of a live system and every
state-changing command needs Cecilia's per-action approval quote (authority.md §3). You cannot reach
her, so compose the quote, put it in PENDING QUESTIONS, and stop. Production is Cecilia's: compose any
production command, with its verification and rollback, for her to run.

SECRETS: You never handle a secret value (secrets.md). Compose the `read -s` command for Cecilia,
or ask before any retrieval from a secret manager. Names only in every report, PR and message.
```

**Extra block for a `cecilia-api-ux` brief** (v20), after block 5 — dispatched only when api-ux is on in
`.cecilia/config.json`, after the design API stage drafts a contract and again after dev-be changes an API:

```
API-UX: READ-ONLY on code, contract and docs. GET against localhost only; any write request (even
local), any non-local host and any load test is A3 — write the quote in your report, do not run it.
Round <1|2> of at most 2. Target: <contract path + version | dev-be branch @ SHA>.
Previous api-ux report: <path or none>. Owners' fix reports: <paths or none>.
Every finding is AUX-nn with owner (design / dev-be / db / dev-fe) and a measurable acceptance.
Re-check round: re-measure each open AUX-nn → resolved (number) / not resolved / Cecilia accepted.
Report: tensura/reports/<TASK>/api-ux.md. Return: §5, at most 15 lines.
```

The orchestrator routes each `AUX-nn` to its owner in that owner's next brief (path + ids, never the
finding text). Still failing after round two → stop and give Cecilia options (`common/decisions.md`).

### Review panel briefs

Procedure: cecilia-review `panel.md`; the run: `references/panel-run.md`; ballots: `references/consensus.md`.
Each member is a fresh cecilia-review agent with the normal blocks (Scope `READ-ONLY`) from
`workflow.py brief --role cecilia-review --lens <lens>` (voter and minutes: no `--lens`), second line
`TASK · cecilia-review (panel-reviewer: <lens> | panel-voter v<n> | panel-minutes) · model · round · date`,
and one block after block 5, copied from `assets/panel-brief-blocks.md`:

- **Lens** (one per lens, one wave): `mode: panel-reviewer, lens: <lens>`; reads only the diff @ SHA,
  oracle docs, tool results and `panel/inputs.md` — never the author's report or other panel files.
- **Voter** (3 fresh agents, one wave, models per `consensus.models`; never a lens reviewer of the round):
  reads `panel/r1-all.md`, re-derives every F-id, writes `votes/review/v<n>.json` + `votes/verdict/v<n>.json`.
- **Minutes** (one fresh agent, after both tallies): reads the two results; writes `panel/verdict.md`;
  changes no outcome.

Lens reviewers return their report as text (you store it); every member ends with STATUS and DEVIATIONS
lines. Members never talk to each other or spawn agents; every step passes through files. No parallel
agents (Antigravity) → the same briefs, one after another, each a fresh context.

Never grant a devops agent a standing approval in its brief — "you may apply to staging" is exactly
the delegation `authority.md` forbids.

