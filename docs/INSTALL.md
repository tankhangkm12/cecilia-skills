# Install Cecilia v20 (Claude Code + Antigravity) — with uv

You install **uv** once. uv downloads and manages the Python Cecilia runs on; you never install or pick a Python.
Everything Cecilia writes for a project goes to a **workspace folder next to it** (`<project>.cecilia/`); the
project folder is never touched and nothing is ever pushed anywhere.

## 1. Put this repository on your git host (once)

This folder is a normal git repository. Push it to a **private** repository you own, and tag releases:

```bash
git init && git add -A && git commit -m "Cecilia 20.2.0"
git remote add origin https://github.com/<you>/cecilia-skills.git
git push -u origin main
git tag v20.2.0 && git push origin v20.2.0
```

(Your workspaces are never inside this repository, so there is nothing of a project here to leak.)

## 2. Install the `cecilia` command (once per machine)

```bash
# uv: https://docs.astral.sh/uv/getting-started/installation/
#   Windows:  winget install --id astral-sh.uv   (or: powershell -c "irm https://astral.sh/uv/install.ps1 | iex")
#   macOS:    brew install uv
uv tool install git+https://github.com/<you>/cecilia-skills@v20.2.0
uv tool update-shell          # once, if `cecilia` is not found in a new terminal
cecilia --version
```

A private repository uses your normal git credentials (Git Credential Manager on Windows, `gh auth login`, or
SSH: `uv tool install git+ssh://git@github.com/<you>/cecilia-skills@v20.2.0`).

Upgrade later:

```bash
uv tool uninstall cecilia
uv tool install git+https://github.com/<you>/cecilia-skills@v20.2.0   # the new tag
cecilia upgrade D:\projects\shop        # refresh each workspace (skills, agents, guard, hook paths) + doctor
```

Until you run `cecilia upgrade`, a workspace keeps its old skills; if the tool's Python path changed, its hooks fail
closed and `cecilia doctor` shows FAIL — `cecilia upgrade` fixes both.

Do not use `uvx` for Cecilia: the hooks point at the Python of the installed tool, and `uvx` environments are
temporary (the CLI warns if it notices).

## 3. Create a workspace for a project

```bash
cecilia init D:\projects\shop --dry-run   # what it detects and proposes; writes nothing
cecilia init D:\projects\shop             # asks before each step
cecilia init D:\projects\shop --yes       # no questions
```

It detects backend/frontend/API/DB/infra files and your MCP servers (by name only — secret values are never
read out), proposes which roles to switch on (cecilia-ui stays off), adds `tool_rules` for context7 / sequential
thinking when you have them, creates `D:\projects\shop.cecilia\`, runs `cecilia doctor` and a guard smoke test.

Options: `--workspace <abs path>` (another location), `--host claude` / `--host antigravity` (default both),
`--push-lock` (also add the git-level push lock — it writes the project's `.git/config`, so it is off by default;
the guard denies agent pushes either way), `--in-project` (the older v18 layout inside the repository).

The project must be a git repository with a first commit: agents edit only on task branches.

## 4. Open it

**Claude Code** — start it in the workspace; the project is already listed as an additional directory:

```bash
cd D:\projects\shop.cecilia
claude
```

`/hooks` shows the Cecilia hook (absolute path to the uv tool's Python + `--workspace`); `/agents` lists 13
Cecilia agents and the session runs as `@cecilia-orchestrator` (workspace setting `"agent"`). `cecilia open shop --claude` does the same from anywhere.

**Antigravity** — open `D:\projects\shop.cecilia\shop.code-workspace` (workspace first, project second). Check
`/skills reload`, `/agents`, `/hooks`, and select `cecilia-orchestrator` as the main agent. Multi-folder behaviour depends on the Antigravity version: run
HOST-SMOKE H60–H66; if skills or hooks are not picked up, see `docs/LIMITATIONS.md` §Workspace mode.

## 5. Everyday commands

```bash
cecilia status                       # open tasks, what waits for you, branch, recent guard refusals
cecilia doctor                       # hooks really run, project untouched, config, MCP secrets (masked)
cecilia scorecard                    # per role: reports, deviations, self-checks, guard refusals
cecilia lessons [--all D:\projects]  # lessons marked [generic?] you may promote into the skills
cecilia clean [--apply]              # finished worktrees and old backups (asks before removing)
cecilia mode --show                  # mode + roles + profiles + tool rules
cecilia mode controlled              # you type CONTROLLED to confirm
cecilia approve tensura/plans/SHOP-42.md --task SHOP-42-B01
cecilia push -u origin feature/SHOP-42-01-order   # YOU push the project (agents never do)
cecilia push-lock on|off|status      # optional git-level lock
cecilia flow [personal|team]         # show or switch the flow — the process (you type it to confirm)
cecilia rules list | show [role] | lint             # the workspace rules/ folder
cecilia rules add --role dev-be "no raw SQL in handlers"   # or --project / --flow F / --lens L; rules only tighten
cecilia extension list | check DIR   # roles/flows/lenses proposed by cecilia-extend under tensura/extensions/
cecilia extension apply DIR          # copy a checked proposal into .cecilia/extensions and upgrade (asks)
cecilia scaffold role|flow|lens <name>  # skeleton from templates/ (tools/scaffold.py)
```

`cecilia <command> --help` shows the exact options of each.

Run them in the workspace (or pass the project/workspace path as the first argument where shown).

## 6. Browser for UI checks (Playwright CLI)

Once per machine (Node.js ≥ 20). The agent asks before running these; you can also run them yourself:

```bash
npm install -g @playwright/cli@latest
playwright-cli install-browser chromium
```

`shop.cecilia/.playwright/cli.config.json` limits the browser to `localhost` / `127.0.0.1`; add an origin there
yourself when a check needs one. Playwright MCP instead: `"ui": {"browser": "playwright-mcp"}` and add the server
yourself under the name **`playwright`**. No browser: `"none"`. Linux containers as root: `"launchOptions":
{"chromiumSandbox": false}` in that file only.

## 7. Hooks and existing host configuration

The installer never overwrites a different existing file; it writes `*.cecilia-suggested` next to it to merge by
hand (Claude Code `permissions`, `additionalDirectories`, `hooks`; Antigravity `cecilia-guard` group). For Claude
Code it runs `claude --version`: 2.1.142+ → exec form (`command` + `args`, no shell); older → quoted shell form
(needs Git Bash on Windows). A hook whose interpreter cannot start is treated by the host as a non-blocking error
— the guard would silently not run; `cecilia doctor` and HOST-SMOKE H00 check that it runs.

## 8. Windows notes

- The guard recognises `git.exe`, `C:\…\npm.cmd`, PowerShell `Remove-Item`, `Get-Content`, `Invoke-WebRequest`,
  `iex`, `Start-Process -Verb RunAs`; Claude Code's PowerShell tool is guarded like Bash.
- Paths compare case-insensitively (`.CECILIA\` is as protected as `.cecilia/`).
- Hook JSON is ASCII-only and input is read as UTF-8 (Vietnamese prompts are fine).

## 9. Uninstall

```bash
uv tool uninstall cecilia
```

Then delete `<project>.cecilia\` folders you no longer need (your project folders are untouched). If an old
**global** install from v18 is still in `~/.claude` or `~/.gemini`, `cecilia doctor` lists it; remove the
`cecilia-*` folders there and the `cecilia-guard` entry in `~/.gemini/config/hooks.json` yourself.

## 10. Keep production authority out of the agent session

Do not expose production credentials, deploy keys or admin tokens. Use branch protection and your git host's
review controls. The guard is a seat belt, not a sandbox.
