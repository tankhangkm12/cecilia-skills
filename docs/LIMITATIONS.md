# Limits to understand — v20

## Host enforcement

| Boundary | Claude Code | Antigravity |
|---|---|---|
| reviewer read-only | agent `tools` + `disallowedTools` | read-only tool list |
| edits only on a task branch (git flow) | guard on Edit/Write/MultiEdit/NotebookEdit | guard on write/replace tools |
| commit/merge/rebase/pull on a protected branch | guard on Bash | guard on `run_command` |
| FAST/STANDARD local edits | allowed except protected/secret paths | same |
| CONTROLLED exact write scope (optionally per worktree) | guard | guard |
| A4 common forms | guard + deny rules | guard |
| A3 common forms | ask | `force_ask` |
| control files (`.cecilia/`, host settings) | guard + host deny | guard |
| design-tool writes (Penpot/Figma) | guard on `mcp__*` | not visible to the hook — procedural |
| browser: local pages only | guard on `playwright-cli` + MCP `browser_navigate`; `.playwright/cli.config.json` blocks other origins | guard on `playwright-cli`; the config file blocks other origins |
| orchestrator writes only `tensura/` | guard (hook `agent_type`) | procedural — `cecilia_check.py` reports |
| role lanes | guard (hook `agent_type`) + `HANDOFF` | procedural — `cecilia_check.py` reports |
| writer/tester dispatch needs a chosen workflow; fix round ≤ 3 | guard on `Agent\|Task` (brief header + `workflow.json` hash) | procedural — `cecilia_check.py` reports |
| rules read before the first write | guard reads the transcript (`rules.enforce: "gate"`) | procedural — brief embeds the rules |
| `rules/`, `.cecilia/extensions/` are control paths; `cecilia flow\|rules\|extension apply` human-only | guard | guard (paths and commands need no agent identity) |

## v20

- **Antigravity hooks cannot tell which agent is calling.** Its hook input names the tool, not the agent, so the
  orchestrator lane, role lanes, the workflow gate and the rules gate are **procedural** there: the orchestrator's
  skill, the briefs and the role cards say it, and `cecilia_check.py` reports violations after the fact (a write
  outside a lane, a dispatch without `workflow.json`, a round above 3). Control paths and human-only commands are
  still enforced on both hosts. Use Claude Code when you need the gates enforced.
- **Claude Code identity comes from the hook's `agent_type`.** Inside a sub-agent it is the sub-agent's name; for
  the main thread it is present when the session runs as an agent (`agent` setting / `--agent`). A session started
  without the setting (for example `claude --agent other`, or a settings file you replaced) has no orchestrator
  identity: the main-thread lane is then not applied — HOST-SMOKE H90 checks it.
- **`chosen` is procedural, not cryptographic.** `workflow.json` records Cecilia's choice and a hash of the option;
  the guard checks that the file exists, `chosen` is set and the brief carries the same hash. An agent that writes
  `workflow.json` itself (it is under `tensura/`, which the orchestrator may write) can fake a choice — the transcript
  and `options.md` show it, and reviews check it. Stronger isolation needs a separate user/VM (§Important limits).
- **Many agents cost tokens and machine load.** Each parallel agent reads its own card, rules and guides and runs its
  own tests, builds, browsers and containers. The options show projected tokens and time; the worktrees, ports and
  compose projects of N agents run on your machine at once. Pick the smaller option on a laptop.
- **Host concurrency limits still apply** (Claude Code: 20 running sub-agents by default, then spawning fails until
  one finishes; Antigravity: host-defined). An option with more agents than the host allows runs in waves.
- **The rules gate reads the transcript.** It looks for the brief header with the current `RULES=<hash>` or a Read of
  the rules files, like `tool_rules`; an unreadable transcript allows the write. Rules with `forbid_regex` /
  `require_command` are checked by `cecilia_check.py`, not by the hook; other rules are procedural.
- **Lanes are globs, not semantics.** Default lanes come from the registry and are generic (`src/**`, `app/**` …);
  narrow them in `lanes` for your layout. A file both FE and BE need is a hand-off, not a shared write.
- **The fix loop stops at 3 rounds by design** — a finding that survives three rounds is a decision for Cecilia, not
  more agent time.
- **Extensions are proposals.** `cecilia-extend` writes under `tensura/extensions/`; only `cecilia extension apply`
  (human) installs them, and `tools/registry.py` validation is structural — read the proposed skill before applying.

## v19.2

- **The holdout guard set has been used once.** Its misses were fixed, so it is no longer a blind test; the next
  release needs a fresh holdout written the same way (an agent that never reads `guard/`).
- **Hidden-command decoding is best effort:** base64 tokens in the same command line and quoted strings inside
  `python -c` / `node -e` code that calls a shell are decoded and judged; code read from files, string
  concatenation or other encodings are not. Unreadable encodings still ask.
- **Content scan looks for high-confidence credential shapes** (cloud keys, private-key headers, tokens, URLs with
  passwords); placeholders (`example`, `localhost`, `password`, `xxx`) pass. Custom secrets without a known shape are
  not recognised — `cecilia_check.py` (gitleaks when installed) is the second net.
- **The review panel is procedure, not host-enforced.** The orchestrator keeps rounds blind and anonymous through the
  files it writes; a host that runs everything in one context cannot guarantee that. It costs roughly
  reviewers × 2 + 1 agent runs.
- **Lessons and conventions are only as good as their upkeep**; `cecilia lessons` shows candidates, promoting one
  into the skills is Cecilia's edit in her Cecilia repository.
- **Importing the project's `CLAUDE.md`** asks for approval once (external import); if declined, agents read it only
  when told.

## Workspace mode (v19)

- **The project folder is protected by the guard, not by the file system.** The agent can technically reach any
  path its host allows; the guard denies Cecilia paths inside the project and every write outside project +
  workspace `tensura/`. Shell scripts that build paths at run time are not fully modelled (see "Guard is not a
  sandbox").
- **Git keeps worktree metadata in the project's `.git/worktrees/`** when parallel writers use
  `<workspace>/.worktrees/`. That is git's own bookkeeping inside `.git` (never committed, never pushed); remove
  it with `git worktree prune` after cleanup. The optional push lock (`cecilia push-lock on`) also writes the
  project's `.git/config` — that is why it is off by default.
- **Claude Code reaches the project as an additional directory** (`permissions.additionalDirectories`). Its
  `.claude/` inside the project (if you have your own) is not loaded as project settings; Cecilia's are the
  workspace's. `CLAUDE.md` of the project is not auto-loaded either — ask the agent to read it, or copy the
  parts you need into the workspace `CLAUDE.md` yourself.
- **Relative permission rules are relative to the workspace.** Secret-file read denies are repeated with the
  project's absolute path (`Read(//…)`); rules you add yourself need the same.
- **Antigravity multi-folder workspaces:** skills/agents/hooks are read from `.agents/` of the workspace folder
  (listed first in `<project>.code-workspace`). Whether every Antigravity version loads them from a non-first
  folder or applies the hook to tool calls in the second folder is **not verified here** — HOST-SMOKE H65. If it
  fails on your version: open the workspace folder alone and let the agent use absolute project paths, or use the
  older in-project layout (`cecilia init … --in-project`).
- **Hooks call the uv tool's Python by absolute path.** `uv tool install --force`/`upgrade` keeps the same path;
  `uv tool uninstall` removes it (hooks then fail → `cecilia doctor` FAIL). `uvx` environments are temporary: do
  not use them for Cecilia.
- **Evals cost real tokens and run on Claude Code only** (`claude -p`); Antigravity has no headless mode the
  runner can drive — use its printed checklist by hand.
- **Token numbers are static estimates** (bytes / 4 of the instruction files a scenario names). Real usage comes
  from `cecilia evals`, which records the host's own counters.

## Important limits

- **Guard is not a sandbox.** A shell/script can write in ways text/path hooks do not fully model — e.g.
  a script that edits files on a protected branch. Such a change still cannot be *committed* there (the
  guard denies the commit), but keep production credentials, deploy keys and admin tokens out of the
  agent session.
- **The branch check reads `.git/HEAD`.** A repository with an unusual layout (bare repo, `GIT_DIR`
  elsewhere) may look "not a git repository"; set `git.require_task_branch` false for it.
- **FAST/STANDARD semantic scope is procedural by design.** Use CONTROLLED when exact machine scope matters.
- **Mode and approval tools use TTY + guard, not cryptographic identity.** For stronger isolation, run
  the agent in a separate container/VM/user and protect `.cecilia/` externally.
- **MCP/connectors carry their own authority.** Restrict connector permissions separately.
- **Role on/off, `plan_first`, options, research, numbers and the Deviations/Rollback lines are
  procedural** — the host cannot tell a plan from an edit or a researched option from a guess. HOST-SMOKE
  H06, H10, H30–H32 check them; `cecilia-review` checks them on every artifact.
- **Design-tool detection is by connector name** (`penpot`, `figma`); others are treated as ordinary
  connectors (writes are A3).
- **Parallel speed depends on the host.** Claude Code runs several sub-agents at once; Antigravity
  depends on its version (HOST-SMOKE H20). Without it, the orchestrator runs sequentially or writes
  briefs for separate sessions.
- **`capacity.py` projects, it does not measure.** Row and index sizes are model estimates (about ±20 %);
  per-connection memory defaults are assumptions to replace with a measurement. Every output says how.
- **Local database access through `docker compose exec` is not inspected further** by the guard.
- **The browser boundary is the config file, not the guard.** The guard reads the command line;
  `route`, `eval` or the page's own scripts can still request anything — `.playwright/cli.config.json`
  (`allowedOrigins`) is what blocks non-local origins. Keep it, commit it, and do not run the browser
  with your real profile. In a worktree without the committed file, pass `--config=` (the agents do).
- **Visual checks are evidence, not a verdict.** Pixel diff % moves with fonts, anti-aliasing and live
  data; contrast from sampled colours includes anti-aliasing. Screenshots are looked at, numbers track
  progress. Visual taste (`ui.style`) is procedural — review checks it, the host cannot.
- **Vendored guidelines and style guides are frozen** at the commits in `THIRD-PARTY.md`; upstream fixes
  arrive only when the package re-vendors them.
- **PowerShell coverage is by name.** Common cmdlets and aliases are mapped, `powershell -Command`,
  `pwsh -c`, `cmd /c`, `wsl …`, script blocks `{ … }` are looked into, `-EncodedCommand` asks; `.ps1`
  files, .NET calls (`[IO.File]::WriteAllText`) and string-built paths are not parsed.
- **Here-doc bodies are read as commands.** A commit message or notes file written with `<<'EOF'` whose
  lines look like `git push -f` or `npm publish` is denied/asked — reword the line or write the file with
  the edit tool. This is deliberate: bodies fed to a shell must never slip through.
- **`git stash`** is allowed; it can set aside an uncommitted `.cecilia/mode.json`. Commit mode changes
  (or keep `.cecilia/mode.json` out of git) if that matters to you.
- **Names that look like 8.3 short names** (`Button~1.tsx`) are refused for edit tools on Windows.
- **Windows path aliases** (NTFS streams `file::$DATA`, trailing dots/spaces, 8.3 short names) are denied
  for edit tools; the shell path check is text-based.
- **Antigravity MCP calls are not visible to the hook** — Playwright MCP navigation, design-tool writes and
  `tool_rules` gates are procedural there (reminded, reported by `cecilia_check`); use `playwright-cli`
  (default) for the guarded path.
- **`tool_rules` gates check the transcript for an earlier lookup call**, matched by tool name and package name.
  A lookup of an unrelated library with the same short name passes; a package imported under a different name
  than its registry name may need a second lookup.
- **`cecilia_check` deps step reads public registries** (npm, PyPI) when online; `--offline` skips it and the
  result is `unverified`, never `pass`.
- **Compliance packs (VN PDPL, GDPR) are engineering checklists, not legal advice**, researched in 2026-09;
  verify against the official text before relying on them.
- **Hooks depend on the interpreter path the installer wrote.** Re-run the installer after moving or
  upgrading Python; HOST-SMOKE H00 detects a hook that does not run.
- **SQLite ledger and local evidence are bookkeeping, not tamper-proof audit storage.**
- **Production detection by command names is best effort.** The true boundary is no production
  credential in the agent session.
- **Host formats change.** Run HOST-SMOKE after host upgrades.

## What Cecilia intentionally does not try to do

It does not make the agent autonomous or run unattended, and it is not a cryptographically secure
control plane. It optimises a solo developer's interactive workflow: plans you approve, work on
branches you can roll back, parallel roles where the work is independent, numbers and options for every
real decision, and hard boundaries around external, destructive and production actions.
