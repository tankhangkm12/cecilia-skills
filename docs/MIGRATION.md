# Migration

## From v20.1 to v20.2 (Antigravity-first)

1. `uv tool install --force git+https://github.com/<you>/cecilia-skills@v20.2.0`, then `cecilia upgrade --all`
   (or `cecilia upgrade <project>`). The upgrade replaces the Antigravity `hooks.json` (it now also judges
   `call_mcp_tool`, `invoke_subagent`, `define_subagent` and adds a `PreInvocation` reminder) and re-copies the
   agents (orchestrator/plan/review on `pro`).
2. Start Antigravity **from the workspace**: `cecilia open <project> --agy` (add `--skip-permissions` if you use it).
   `agy` started from another folder does not load the workspace hooks or agents.
3. `cecilia doctor` must show the Antigravity hook OK and `agy` ≥ 1.2.7.
4. New optional config: `antigravity` (`identity`, `main_agent`, `ask`, `models`), `consensus.provenance`,
   `guard.agent_may_run`, and for the MCP server `mcp.control`, `mcp.agy_skip_permissions`, `mcp.agy_timeout_min`.
   `cecilia upgrade` adds the defaults without touching your values.

## From v20.0 to v20.1

1. `uv tool install --force git+https://github.com/<you>/cecilia-skills@v20.1.0`, then `cecilia upgrade --all`
   (every workspace in `~/.cecilia/workspaces.json`; the first time, `cecilia upgrade <project>` once per project
   registers it).
2. Hooks now call plain `python` (Windows) / `python3` — the one on your PATH. Set `guard.python` in the config, or
   `cecilia upgrade <project> --python C:\Python312\python.exe`, to pin one. `cecilia doctor` checks it (and flags
   the Microsoft Store stub). The 20.0.1 `.cmd` launcher is removed unless a path has a space.
3. New config keys, all optional with defaults: `consensus`, `automation`, `orchestration.orchestrator_commands`,
   `orchestration.orchestrator_mcp`, `guard.python`, `mcp.permission_mode`.
4. The orchestrator is narrower: only `cecilia`, Cecilia's scripts, read-only and git-integration commands; no MCP
   tools; writes only `tensura/tasks|decisions|inbox|runs` and `state.md`. If you relied on it running something
   else, add the command name to `orchestration.orchestrator_commands` — better: let a role do it.
5. `cecilia approve` lints the plan first (unset variables, placeholders, swallowed errors, delete-before-verify,
   secret dumps, paths prefixed with the project folder). `--all` approves every block in one run.
6. Optional: `cecilia mcp` — see `docs/MCP.md`.

## From v19.2 to v20

1. **Upgrade the tool:** `uv tool upgrade cecilia` if you installed from a branch, or
   `uv tool install --force git+https://github.com/<you>/cecilia-skills@v20.1.0` for the tag. `cecilia --version` → 20.1.0.
2. **Upgrade each workspace:** `cecilia upgrade <project>`. It
   - refreshes skills (now 13, with `cecilia-extend`), agents and the guard, and writes `.cecilia/registry.json`
     (the compiled registry the guard and `workflow.py` read);
   - adds the V20 config keys — `flow`, `flows`, `orchestration`, `parallel.limits`, `lanes`, `test.lenses`,
     `review.panel.from`, `fix_loop`, `rules`, `extensions` — without changing any value you set (an existing
     `parallel.max_writers` is kept and read as the cap for dev agents);
   - creates `rules/` with empty files carrying a header (`_project.md`, `roles/<role>.md`, `flows/<flow>.md`);
   - makes the orchestrator the main thread: Claude Code workspace settings `"agent": "cecilia-orchestrator"` and the
     hook matcher with `Agent|Task`; Antigravity `mainAgent: true` on the orchestrator. A customised
     `.claude/settings.json` is not overwritten — merge `settings.json.cecilia-suggested` by hand.
3. **Check:** `cecilia doctor`, `cecilia mode --show` (shows flow, lanes, fix loop), then HOST-SMOKE H90–H99 on each
   host you use.
4. **Optional:** narrow `lanes` to your project's folders; put project rules into `rules/` (`cecilia rules …`); switch to
   `cecilia flow team` if you work in a team.

**What changes day to day**

| v19.2 | v20 |
|---|---|
| you talk to any role, the main session may do small work itself | you talk to the orchestrator (main thread); it never codes, tests or reviews — even FAST dispatches one role |
| STANDARD: short plan, then work | STANDARD: 2–3 options (agents, split, lenses, time, tokens) → you choose → `workflow.json` → dispatch |
| up to `parallel.max_writers` (3) writers | no configured cap; the option you choose sets the numbers (host limit applies) |
| one tester | one test agent per lens (functional, integration, …) in parallel |
| review panel in CONTROLLED or on request | panel from STANDARD (3–4 lenses), CONTROLLED 5–6 + red team |
| fixes after review by hand | automatic fix loop, at most 3 rounds, then options |
| any role may edit where the task leads | each role writes only in its lane; otherwise `HANDOFF: needs <role>` |
| project rules only in `CLAUDE.md` / conventions | `rules/` in the workspace, embedded in every brief, only you edit |
| — | flows `personal` / `team`; `cecilia-extend` + `cecilia extension apply` |

Existing tasks keep working: a task without `workflow.json` continues in its v19.2 state; the next STANDARD dispatch
asks for options first. Plans and approvals for CONTROLLED are unchanged (`cecilia approve`).

## From v19.0 to v19.2

1. `uv tool uninstall cecilia && uv tool install git+https://github.com/<you>/cecilia-skills@v19.2.0`
2. `cecilia upgrade <project>` for each workspace — refreshes skills/agents/guard, adds `review` and `scale` to the
   config (nothing you set changes) and re-writes the workspace `CLAUDE.md`/`AGENTS.md` (imports the project's own).
3. Optional: `cecilia init <project> --dry-run` shows which `scale` it would propose; set it in the config.
4. Run HOST-SMOKE H80–H86.


## From v18.x to v19

1. **Install uv and the tool** (`docs/INSTALL.md` §2). Python on your machine no longer matters.
2. **Create the workspace:** `cecilia init <project>` → `<project>.cecilia/`. Your v18 `.cecilia/config.json` is
   not read from the project automatically — copy the values you changed (roles, plan_first, git, ui, parallel,
   models) into the new workspace config, or run `cecilia init … --in-project` to keep the old layout (it migrates
   the config in place, backs it up and prints the before → after table).
3. **Move your documents:** move `<project>/tensura/` to `<project>.cecilia/tensura/` (plans, reports, docs). If
   `tensura/docs` is shared with your team and belongs in the repository, keep it there and tell the agents its
   path in the workspace `CLAUDE.md`.
4. **Remove the old in-project install** (after the workspace works — HOST-SMOKE H00, H60):
   `.claude/skills/cecilia-*`, `.claude/agents/cecilia-*.md`, the Cecilia entries in `.claude/settings.json`,
   `.agents/skills/cecilia-*`, `.agents/agents/cecilia-*`, the `cecilia-guard` group in `.agents/hooks.json`,
   `.cecilia/`, `.playwright/cli.config.json` if Cecilia wrote it, the `# Cecilia` block in `.git/info/exclude`.
   If you had turned the v19 push lock on: `cecilia push-lock off` **before** removing `.cecilia/`.
   `cecilia doctor` → `project untouched` OK when done.
5. **Behaviour changes to expect:** agents no longer push or open PRs (they give you the commands); infra and
   migration edits always ask; reports are ≤ 15 lines in chat with the full text in `tensura/reports/<TASK>/`;
   SKILL cards are short and the detail lives in `references/workflow.md`.
6. Run `docs/HOST-SMOKE.md` H00–H01, H13, H60–H76.


## From v18.0 to v18.1

1. **Upgrade in place:** `python tools/install.py --project <abs path> --host claude --host antigravity
   --apply --upgrade`. Cecilia's own files are replaced, the old copies go to `.cecilia/backup/<time>/`.
   Your `.cecilia/config.json`, mode, approvals and `hooks.json` stay as they are. `.claude/settings.json`
   is replaced (and backed up) only if it still holds exactly what v18.0 wrote; a customised one stays and
   you merge `settings.json.cecilia-suggested` — **important on Windows**: the new hook matcher adds
   `PowerShell` (Claude Code's PowerShell tool was not guarded before) and the hook uses the exec form
   (`command` + `args`, Claude Code 2.1.142+). Also new: ask for `npx skills`, `playwright-cli install*`;
   deny edits to `.mcp.json`, `.playwright/cli.config.json`; `PowerShell(...)` rules.
2. **Config (optional):** add `"browser": "playwright-cli"` and `"style": "none"` inside `"ui"`. Missing keys
   use these defaults. `python .cecilia/bin/cecilia_mode.py --show` prints and checks them.
3. **Browser (once per machine, when the agent asks):** `npm install -g @playwright/cli@latest`,
   `playwright-cli install-browser chromium`. Node.js ≥ 18.
4. `.gitignore`: add `.cecilia/backup/` and `.playwright-cli/`. Commit `.playwright/cli.config.json` so
   worktrees and teammates share it (or pass it with `--config=<main checkout>/.playwright/cli.config.json`).
5. Windows: nothing to change — the guard now recognises `git.exe`, `*.cmd`, PowerShell cmdlets.
6. Run HOST-SMOKE H00, H25–H29, H41–H43.

## From v17.2.x to v18

1. **Git.** Every project must be a git repository; the agent now refuses to edit on `main`/`develop`/
   `release/*`. Commit or stash your own changes, then let the agent create task branches. (Opt out per
   project: `"git": {"require_task_branch": false}`.)
2. **Remove Codex files** if you used them (`.codex/`); v18 does not install or support them.
3. **Reinstall** with `tools/install.py --apply` for Claude Code and/or Antigravity. Remove the old skill
   folders first if the installer reports conflicts (the common files were renamed). Hooks are rewritten
   with your Python's absolute path — merge `*.cecilia-suggested` if you had customised settings.
4. **Config.** Your existing `.cecilia/config.json` is kept. Add the new sections if you want non-defaults:
   `plan_first` (object per mode), `git`, `parallel`, `models` — see `docs/INSTALL.md`. Missing sections
   use the defaults (plan_first on for STANDARD/CONTROLLED, git flow required, 3 parallel writers).
5. Add `tensura/backups/` to `.gitignore`.
6. Run `docs/HOST-SMOKE.md` (H00 first: the hook must run).

| v17.2.1 | v18 |
|---|---|
| `policy.md`, `modes.md`, `gates.md` | `core.md` |
| `interview.md` | `decisions.md` (+ options, research) |
| `execution.md` | `parallel.md` (parallel by default) |
| `git-pr.md` | `git.md` (+ checkpoints, backup, rollback) |
| — | `numbers.md` + `scripts/capacity.py`, `code-quality.md` |
| edits allowed on any branch | edits only on a task branch (guard) |
| `plan_first: false` | `plan_first` on for STANDARD/CONTROLLED |
| one writer at a time until smoke-tested | up to `parallel.max_writers` (3) at once |
| one A3 quote per message | several quotes in one numbered message, approved per item |
| Claude Code, Codex, Antigravity | Claude Code, Antigravity |


## From v17.1 to v17.2

Nothing you rely on is removed. Steps:

1. Install v17.2 project-local over the project (`tools/install.py --apply`). New skills
   (`cecilia-db`, `cecilia-ui`) and agents are added; the installer creates `.cecilia/config.json` only if
   the project has none, and never overwrites files that differ — merge `*.cecilia-suggested` yourself.
   Remove the old copy of a skill folder first if the installer reports it as a conflict.
2. Check `python3 .cecilia/bin/cecilia_mode.py --show`: every role on except `cecilia-ui`. Turn roles
   on/off by editing `.cecilia/config.json`.
3. **Docs layout.** Existing projects with the flat v17.1 names (`01-idea.md` … `10-infra-<svc>.md`) keep
   working: agents read them through `shared/workspace.md` §2.1 and keep writing in the legacy names
   until you migrate. To migrate, set `docs_layout`, then ask any agent: "migrate tensura/docs to the
   v17.2 layout" — it does it as one task (`git mv` per the table, links fixed, one commit).
4. Schema and migrations now belong to `cecilia-db` while it is on; `cecilia-design` and `cecilia-dev-be`
   take them back automatically when you turn it off.
5. Run `docs/HOST-SMOKE.md` (new checks H14–H19).

| v17.1 | v17.2 |
|---|---|
| 9 roles | 11 roles: + `cecilia-db`, `cecilia-ui` (off by default) |
| every installed role usable | `.cecilia/config.json` turns roles on/off; orchestrator plans only with roles that are on |
| plan-first only when asked in chat | `plan_first: true` makes it the project default |
| reports without a compliance line | every finish ends with `Deviations:` |
| `tensura/docs/0N-*.md` flat | `system/`, `modules/<m>/` or `services/<s>/modules/<m>/`, `apps/<app>/`, descriptive names |
| schema written by cecilia-design | owned by cecilia-db (design is the fallback) |
| Penpot/Figma writes: A3 like any connector | denied while cecilia-ui is off; A3 or allowed (`ui.design_writes`) while on |
| roster hard-coded in several tools | one roster: `tools/roster.py` |


## From v16

The v16 role names stay the same. The important behavior change is **local coding no longer requires
G2 in the default mode**.

| v16 | v17 |
|---|---|
| every A2 code/test/config edit requires active G2 | STANDARD default: Cecilia's task authorizes reasonable local edits |
| small tasks still produce scope block/approval | FAST can inspect → edit → focused check directly |
| independent challenge/review heavily defaulted | proportionate; mandatory for CONTROLLED/HIGH |
| one control style | FAST / STANDARD / CONTROLLED |
| Codex `approval_policy = "untrusted"` | Codex `approval_policy = "on-request"` |
| Codex hook root was `PreToolUse` | current top-level `hooks.PreToolUse` schema |

### Steps

1. Finish/checkpoint active work.
2. Install v17 project-local and merge any `*.cecilia-suggested` host configs manually.
3. Ensure `.cecilia/mode.json` exists; installer creates `standard` on a fresh install. On an existing
   project, create/set it yourself with `cecilia_mode.py standard` after installing the tool.
4. Run `docs/HOST-SMOKE.md`.
5. Use STANDARD daily. Switch to CONTROLLED when you want exact V16-style G2 scope enforcement.

Existing v16 `cecilia-scope` plans and approval records remain useful in CONTROLLED mode.

## From v14 / v15

Install v17 as a fresh project-local Cecilia bundle, remove/archive old Cecilia skills from host scan
paths, keep `tensura/` docs/reports, then smoke-test. Do not treat old words such as `APPROVED` as a
CONTROLLED G2 approval.
