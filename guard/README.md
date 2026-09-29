# .cecilia — Cecilia's controls (v20)

This folder belongs to you, not to the agents. Agents may read it; the guard refuses normal edit-tool
changes to it. In workspace mode (v19 default) it lives in `<project>.cecilia/.cecilia/`, and
`config.json` → `workspace.project` names the project the guard protects. The `cecilia` command runs these tools
for you (`cecilia mode`, `cecilia approve`, `cecilia push`, `cecilia doctor`).

| Path | What |
|---|---|
| `bin/cecilia_guard.py` | Host hook. Always protects A3/A4, secret/control files and git flow (no edits/commits on protected branches); in CONTROLLED it also enforces G2 write scope. |
| `bin/cecilia_mode.py` | **Your** interactive mode switch: FAST / STANDARD / CONTROLLED. Default is STANDARD. |
| `bin/cecilia_approve.py` | **Your** G2 approval tool for CONTROLLED work. |
| `bin/cecilia_doctor.py` | Read-only health check: hooks really deny, project untouched, config, MCP secrets (masked). |
| `bin/policy.json` | The guard's data (live tools, deploy words, default profiles, local-only paths). |
| `pushlock.json` | State of the optional git-level push lock. |
| `mode.json` | Persistent project control mode. Agents do not edit it. |
| `config.json` | **You** edit it by hand: `workspace.project`, roles on/off, `plan_first`, `docs_layout`, `ui`, `git` (`local_only`), `profiles`, `tool_rules`, `parallel`, `models`, and (v20) `flow`, `lanes`, `orchestration`, `fix_loop`, `rules`. Agents only read it. |
| `approvals/<task>.json` | CONTROLLED scope approvals. Revoke with `cecilia_approve.py --revoke <task>`. |
| `guard.log` | Every ask/deny the guard issued. Keep it out of git. |
| `registry.json` | Snapshot of the role/flow/lens registry written by the installer. The guard reads each role's agent type and lane from it (v20). |
| `extensions/` | Roles/flows/lenses Cecilia applied with `cecilia extension apply`. Agents never write here. |
| `run.sqlite` | Optional orchestration ledger. Keep it out of git. |
| `backup/<time>-before-v<ver>/` | Old copies of Cecilia's files saved by `install.py --upgrade`. Keep it out of git; delete when you no longer need them. |

Also yours: `../rules/` — the project rules every role reads (`_project.md`, `roles/<role>.md`,
`flows/<flow>.md`, `lenses/<lens>.md`). Change them with `cecilia rules add|rm|edit`; agents may only
`cecilia rules list|show|lint`.

What v20 adds (Claude Code only — the hook's `agent_type` names the agent; Antigravity passes no identity, so
there these rules are procedural and `cecilia_check.py` reports breaches):

- **Orchestrator lane** — `cecilia-orchestrator` writes only under `tensura/` (edit tools and shell writes).
- **Role lanes** — a role writes only inside `lanes.<role>` (globs; `tensura/…` = workspace, others = project,
  `!` excludes) plus `tensura/reports|tasks|backups/` and `tensura/lessons.md`; otherwise it stops with a
  `HANDOFF: needs <role>` line.
- **Workflow gate** — from STANDARD (`orchestration.workflow_required_from`), an `Agent`/`Task` dispatch of a
  writer/tester role needs the brief header `[cecilia-brief TASK=… ROLE=… … WORKFLOW=<hash> ROUND=<n> RULES=…]`
  whose WORKFLOW equals the chosen `tensura/tasks/<TASK>/workflow.json` hash; ROUND above `fix_loop.max_rounds`
  is denied. FAST, reviewers and other agents are not gated.
- **Rules gate** (`rules.enforce: "gate"`) — a role's first write needs its rules read: its brief header with the
  current `RULES=<hash>` in the transcript, or a Read of each rules file that exists.
- These gates switch on when `registry.json` or the v20 config keys exist; without both the guard behaves as v19.2.

Also yours: `../.playwright/cli.config.json` — limits the agents' browser to local pages (the guard
blocks agent edits to it; add an origin yourself when a check needs one).

Everyday commands:

```bash
cecilia mode --show          # mode + roles on/off from config.json
cecilia mode standard
cecilia mode controlled
cecilia approve tensura/plans/SHOP-42.md --task SHOP-42-B01
cecilia approve --list
cecilia approve --revoke SHOP-42-B01
python .cecilia/bin/cecilia_guard.py --explain "git push origin feat/SHOP-42"
python .cecilia/bin/cecilia_guard.py --explain "playwright-cli open https://example.com"   # ask
python .cecilia/bin/cecilia_guard.py --explain "echo x > src/a.ts" --agent cecilia-orchestrator   # deny
```

FAST/STANDARD deliberately do **not** require a machine scope for ordinary local edits: Cecilia is
present and the agent is a pair programmer. CONTROLLED restores strict G2 scope enforcement.

The guard is a seat belt, not a sandbox. Keep production credentials, deploy keys and admin tokens
out of the agent session.
