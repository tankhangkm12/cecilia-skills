# Parallel work — waves, isolation, integration, stopping and resuming (common v20)

<!-- common v20 — canonical copy in shared/, synced into every skill by tools/sync_common.py. Do not edit a copy. -->

Independent work runs at the same time. Units that do not write each other's files — backend modules,
frontend apps, database, infrastructure, test lenses — start together as soon as the workflow is chosen and
the docs they build on are approved; each runs its own checks; they meet in an integration step.

## 1. How many — the chosen option sets the numbers

There is **no configured cap** by default: `parallel.limits` in `.cecilia/config.json` is
`{"dev": null, "test": null, "review": null}`. From STANDARD the orchestrator proposes 2–3 options
(`tensura/tasks/<TASK>/options.md`) that differ in agents per kind and how the work is split — `module`
(one unit per module/service), `layer` (db · be · fe · infra) or `competing` (two instances build the same unit,
the panel picks one). The option Cecilia chooses is frozen in `workflow.json`; its numbers are the plan.

Limits that still apply:
- **Host limit** — Claude Code runs at most 20 sub-agents at once; Antigravity per host version
  (`capabilities.md`). More members than that → the option splits them into waves.
- **A number Cecilia set** — `parallel.limits.<kind>` when not `null`; a legacy `parallel.max_writers` is read
  as the `dev` limit. Never exceed it; propose a new option instead.
- **Machine resources** — each member needs its own ports, containers and database (§2 runtime isolation);
  the option's projection says what it costs (`[projected]`, `numbers.md`).

Read-only roles (review of a frozen target) do not count against `dev`. CONTROLLED runs the same way but
checks in after every wave (§3).

## 2. When two writers may run at the same time

All three, or they are in different waves:

1. **Their seams are settled in the docs/plan** — the API contract version, schema, event shape, env var
   and port names the units build on. The plan names them; a writer that needs to change a seam stops
   and reports it (never edits the other side's assumption).
2. **Disjoint files** — expected write sets compared path by path; every unit in `workflow.json` lists its
   write set. The forgotten collisions: DI modules, routers, migration registries, lockfiles, i18n bundles,
   shared enums, error catalog, generated clients, the plan's status table. A shared hot file gets **one**
   owner in the wave; the others list the lines they need in their report and the integration step (§4)
   applies them.
3. **Isolation** — each code writer (every instance) in its own git worktree and branch
   (`git -C <project> worktree add <workspace>/.worktrees/<role>-<unit> -b feature/<TASK>-<nn>-<role>-<unit> <base>`);
   document writers in the main checkout, each on its own files. Two agents never share a checkout.

**Runtime isolation** — files are not the only thing two writers share. Give every member its own:

| Resource | How |
|---|---|
| ports | a block per member: member *k* uses `3000+100k`, `5432+k`, … passed as env vars on the command (`PORT=3100 npm run dev`) — never written into `.env` files |
| docker compose | `docker compose -p <TASK>-<role>-<unit>` so containers, networks and volumes do not collide |
| local database | its own database or schema (`<db>_<role>_<unit>`) created by its migrations |
| test database / caches | per member (`TEST_DB_NAME`, cache dir under its worktree) |
| browser | its own Playwright session `-s=<member>`; never `close-all` / `kill-all` |

The brief names the member's unit, worktree, branch, ports, compose project and database (`UNIT=` in its
header). The helper `cecilia-orchestrator/scripts/workflow.py` checks cycles and path overlap and assigns
port blocks; it does not understand meaning — the plan still has to be right.

Creating a worktree is local A2 (in CONTROLLED the plan lists it); deleting one that holds unpushed work
is A3.

## 3. Waves

A wave is the set of members launched together because none can invalidate another. Build it in order:
dependencies finished → write sets compared → isolation assigned → no writer in the same wave as its
reviewer → the numbers of the chosen option, within the host limit. A wave of one is normal.

**Launch every member of a wave in the same turn** — several sub-agent calls in one message — never one
after another. Long checks (full test suites, builds) run in the background where the host allows it.

After a wave: `wave_checkin` `auto` (default for FAST/STANDARD) → a wave whose members all returned DONE,
with no question, no failed check, no open challenge, no `HANDOFF` and no A3/A4 action pending, is reported in
one line and the next wave starts. `step` (always for CONTROLLED) → stop and report after every wave. Any
question, failed check, A3 quote, third challenge round or end of run stops in both. A `HANDOFF: needs <role>`
is dispatched to that role (a new member) before the wave counts as done.

## 4. Integration — test what was built separately, together

Separate branches passing their own tests do not prove combined behaviour. After a wave with more than
one code writer:

1. Create `int/<TASK>` locally from the base; merge each member's branch (local merge, A2 — never into a
   protected branch). Record every member SHA. The orchestrator does not merge: the brief asks one dev
   instance to act as **integrator** (`UNIT=int`), which merges and nothing else.
2. Conflicts: the integrator does not resolve other members' logic; each conflict goes to the owner of the
   file with both sides. Hot-file lines listed by members (§2.2) are applied by the hot file's owner.
3. `cecilia-test` (lens `integration`, plus the lenses the workflow chose) runs against `int/<TASK>`; results
   name the candidate SHA.
4. Failures go back to the member whose change caused them, as a new turn on its own branch; then
   re-integrate. Review and fix rounds run on the integrated SHA. In the `personal` flow the members' branches
   are the deliverables; the `team` flow may deliver the integrated branch as stacked PRs (`flows/team.md`).
   Cecilia pushes them herself (local-only, `git-handoff.md` §1).

Merging into a shared branch is A4 — Cecilia does it.

## 5. Dispatching a role (orchestrator → sub-agent)

A brief carries everything; the sub-agent has no conversation history. Its first line is the header
`[cecilia-brief TASK=… ROLE=… LENS=… UNIT=… WORKFLOW=… ROUND=… RULES=…]` (`core.md` §3.4); then task · role ·
mode · flow · requirement IDs · source SHA and contract version · scope (`cecilia-scope`, or "no scope: A0/A1
only") · lane · worktree path, branch and workspace path for reports · runtime resources (ports, compose
project, DB name) · environment · commands allowed · evidence location · stop conditions · prior decisions ·
who reviews it · `## Rules (must follow)`.

The sub-agent does everything possible up to its next gate, then returns `STATUS`, outputs with paths
and SHA, checks with counts, findings with IDs, sorted questions, A3 quotes, `Rules:`, `HANDOFF:` (if any),
`DEVIATIONS`, rollback, and the next action. It never contacts Cecilia and never launches other agents unless the brief says so.

**No sub-agent tool on this host** (`capabilities.md`): the orchestrator either runs the roles one after
another in this session, or — when Cecilia wants the speed — writes each member's brief to
`tensura/reports/<TASK>/briefs/W<n>-<role>-<unit>.md` with the exact command to start a separate session in
that member's worktree; Cecilia opens the sessions; each writes its report; the orchestrator collects.

## 6. Stopping, waiting, resuming

States: `RUNNING` → `WAITING_FOR_CECILIA` | `BLOCKED` | `DONE` | `CANCELLED` (per member in
`tensura/tasks/<TASK>/run.json`).

- **Waiting keeps everything** — worktrees, branches, drafts, pending questions.
- **Resume = reconcile first**: re-read `run.json` and the run log, check current SHAs, whether files changed
  under you, the work mode, flow and config, the workflow hash, in CONTROLLED whether the scope is still active,
  and the result of any A3 action in flight. An action whose result is unknown is checked (locally, or by Cecilia on the remote side) — never repeated.
- **Cancel**: ask running sub-agents to stop, confirm they stopped, save outputs and questions, mark the
  run. Never start a replacement writer while the old one might still be writing.
- **Cleanup** (worktrees, local branches, `int/*`, `backup/*`) is a separate step after outputs are
  saved and pushed by Cecilia or explicitly abandoned — A3 if anything unpushed would be lost.

## 7. Bounded effort

Two in-scope correction attempts for a persistent failure inside one member's run, then stop and report.
Flaky test: at most two
reruns, every attempt recorded. Across the task: the review fix loop is at most 3 rounds (`core.md` §3.4).
Time or cost limits Cecilia sets are recorded in the run log; if the host cannot measure cost, say
"cost unmeasured" and use a turn limit instead.
