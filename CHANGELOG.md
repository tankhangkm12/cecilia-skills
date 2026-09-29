# Changelog

## v20.2.0 — 2026-09-29 · Antigravity-first: guard sees MCP and subagents, knows who is calling; MCP control

- **Why:** on Antigravity the orchestrator called k8s/Proxmox MCP tools itself, wrote the consensus ballots itself
  and, when a subagent call failed, did everything itself. The 20.1 Antigravity hook only matched
  `run_command` and file writes, so MCP calls (`call_mcp_tool`) and `invoke_subagent` never reached the guard, and
  the guard could not tell the orchestrator from a role there.
- **Hook coverage:** Antigravity PreToolUse now matches `call_mcp_tool` (normalised to `mcp__<server>__<tool>`
  for the MCP policy), `invoke_subagent` and `define_subagent`, plus a `PreInvocation` hook that reminds the
  orchestrator (and each subagent its role) at the start of a conversation.
- **Identity on Antigravity:** each subagent is its own conversation; the guard reads its transcript and takes the
  role from the `[cecilia-brief ROLE=…]` header of its first message; no header = the main agent = the
  orchestrator. Lanes, the orchestrator limits (no MCP, no specialist commands, tensura-only writes), the workflow
  gate and the rules gate now apply on Antigravity as on Claude Code (`antigravity.identity`, `main_agent`).
- **Dispatch:** the orchestrator may only invoke enabled `cecilia-*` roles; unknown names (`teamwork_preview`,
  `self`, …) and `define_subagent` are refused with "stop and report — never do the work yourself".
- **Provenance:** every write under `tensura/` is logged to `.cecilia/provenance.jsonl` (role + conversation /
  agent id + model). `workflow.py tally` discards ballots the orchestrator wrote, flags unverified ones and reports
  independence `verified | strong | weak` on the decision card (`consensus.provenance: warn | require`).
  `workflow.py brief --unit v1..v3 | p1..p3 | h1..h3` for voters.
- **Agents:** orchestrator, plan and review run on `pro`, others `inherit` (`antigravity.models` to change);
  `call_mcp_tool` only in the lists of roles that touch systems (devops, discovery, db, test, dev-be, dev-fe);
  orchestrator gains `manage_subagents`, `send_message`.
- **`cecilia open <project> --agy [--skip-permissions]`** starts `agy` in the workspace (starting it elsewhere skips
  Cecilia). Doctor checks the hook shape, `agy` ≥ 1.2.7 (subagents from a custom main agent), global leftovers
  and lists MCP servers.
- **A3 on Antigravity** uses `force_ask` (asks even under `--dangerously-skip-permissions`); `antigravity.ask: "ask"`
  hands it to the host's normal permission flow.
- **`guard.agent_may_run`:** open `mode`, `approve`, `flow`, `rules add`, `extension apply`, `push` to agents if
  you want; default: agents in the workspace cannot approve their own plans.
- **`cecilia mcp`:** Antigravity headless runs (`agy -p --agent cecilia-orchestrator --output-format json`,
  stdin closed, answer recovered from the transcript when agy's non-TTY stdout is empty, `--conversation` to
  continue); control tools `cecilia_mode`, `cecilia_approve` (incl. `all`), `cecilia_flow`, `cecilia_rules_add`,
  `cecilia_extension_apply`, `cecilia_push` via `--yes --by mcp` (only with `CECILIA_MCP=1`), audited in
  `tensura/audit/control.jsonl`; `mcp.control: all | none`.
- **Docs:** `docs/ANTIGRAVITY.md` (Vietnamese guide), orchestrator `references/antigravity.md`, `docs/MCP.md`.

## v20.1.0 — 2026-09-29 · one prompt → one decision card, 3-agent consensus, narrower orchestrator, cecilia mcp

- **One prompt, one card.** The orchestrator dispatches cecilia-discovery to measure the task (repo/cluster, read
  only) into `tensura/tasks/<T>/scope.json`; nobody asks open questions — facts are measured, only preferences and
  risk choices are asked, all on ONE decision card (`workflow.py decision` → `tensura/decisions/<T>.md`: scope,
  suggested mode with the command, models, options with votes, open questions with defaults, vetoes). The answer
  (`workflow.py answer`) also freezes `workflow.json`. Guard refusals are retried up to `automation.self_retry`;
  a failing guard stops the agent (`cecilia doctor`), it never hands you bypass commands.
- **Consensus (majority of 3 independent agents)** from STANDARD on plan, review, root cause and final verdict:
  independent contexts, different models when available, anonymised critique, ballots with evidence
  (`tensura/tasks/<T>/votes/`), `workflow.py tally` (strict majority; evidence-less votes dropped; independence
  weak with one model). Safety veto in CONTROLLED: a single data-loss / secret / destructive concern is never
  outvoted — it goes to the card. Replaces "2 rounds + judge"; the judge writes the minutes. Tests are not voted.
- **Narrower orchestrator (enforced on Claude Code):** commands only `cecilia`, Cecilia's scripts, read-only and
  git-integration commands; every MCP tool denied; writes only `tensura/tasks|decisions|inbox|runs`, `state.md`
  (plans, docs, reports, votes, verdicts belong to roles). Config escape hatches `orchestration.orchestrator_commands`
  / `orchestrator_mcp`.
- **Guard:** `kubectl get secret … -o yaml|json` asks, written to a file or `tee` is denied; `etcdctl get` on
  `/registry/secrets` denied.
- **`cecilia approve`:** plan linter (unset `$VARS`, placeholders like `kong-xxx`, `|| true`, delete before verify,
  secret dumps, paths prefixed with the project folder name, unverified root causes as a warning) — an error
  approves nothing; `approve --all` approves every block with one confirmation; `approve lint <plan>`.
- **Hooks call `python`** (`python3` off Windows) from PATH; `guard.python` / `--python` to pin; inline
  Antigravity command without quotes, `.cmd` launcher only when a path has a space. Doctor checks the interpreter
  (version, Store stub), no longer flags `…TokenDate` keys as secrets, and tells you when a newer tag exists.
- **`cecilia upgrade --all`**, `cecilia workspaces` (`~/.cecilia/workspaces.json`).
- **Setup:** a project whose root is the infra folder (k8s/Helm/Kustomize/Terraform at the top level) gets root
  globs in the devops lane and infra profile; the stale ".git/info/exclude" message is gone for workspaces.
- **`cecilia mcp`** (new): MCP server (stdio, or `--http` on 127.0.0.1 only, no auth) so another LLM can start
  tasks, follow runs, read cards and reports (secrets redacted) and answer decision cards. Claude Code runs
  headless (`claude -p --agent cecilia-orchestrator`); Antigravity through `tensura/inbox/`. It cannot approve,
  change mode/flow/rules, push, or run arbitrary commands. `docs/MCP.md`.

## v20.0.1 — 2026-09-28 · Antigravity hook on Windows, workflow gate for docs roles, CONTROLLED for live clusters

- **Antigravity on Windows: the guard hook never ran.** Antigravity hands the hook command to `cmd.exe` with its
  double quotes backslash-escaped, so a quoted interpreter path (any user folder with a space, e.g.
  `C:/Users/Thanh Tan/...`) failed with "is not recognized" on every tool call. The installer now writes
  `.cecilia/bin/cecilia_guard_antigravity.cmd` (holding the quoted command line) and the hook command is its bare
  backslash path. `cecilia upgrade` replaces an Antigravity `hooks.json` that only holds Cecilia's hook (it was
  never recognised before and only got a `.cecilia-suggested` copy). `cecilia doctor` fails a quoted hook command
  on Windows instead of reporting it OK.
- **Workflow gate:** roles that write only under `tensura/` (plan, discovery, design, extend) are no longer gated —
  they prepare the options; code/test/infra writers still need the chosen `workflow.json`.
- **Rules:** live clusters/VMs are a CONTROLLED trigger (`core-min.md`); the orchestrator never rewrites a plan or
  rules on findings itself — findings go back to their owner and only the judge rules; plan review: a root cause
  stated as fact without `[verified]` evidence, or a recovery step without a tested rollback, is a Blocker;
  devops Kubernetes guide: control plane and etcd (measure first, `member remove/add` for one bad member,
  restore on every member only when quorum is lost, snapshot handling).

## v20.0.0 — 2026-09-28 · orchestrator-only, workflows with options, parallel lenses, rules, flows, registry

**Orchestrator only orchestrates.** `cecilia-orchestrator` is the host's main thread (Claude Code `"agent":
"cecilia-orchestrator"` in the workspace settings; Antigravity `mainAgent: true`). It writes only under the workspace
`tensura/` and never does specialist work — FAST dispatches one role with a 3-line brief. On Claude Code the guard
denies an orchestrator write outside `tensura/` (hook `agent_type`).

**Workflow with options (from STANDARD).** `workflow.py options` writes 2–3 options (agents per kind, split `module` |
`layer` | `competing`, test/review lenses, projected time and tokens, model per agent) to
`tensura/tasks/<TASK>/options.{json,md}`; Cecilia chooses; `workflow.py choose` freezes it into `workflow.json` with a
12-hex hash. Every brief starts with `[cecilia-brief TASK=… ROLE=… LENS=… UNIT=… WORKFLOW=… ROUND=… RULES=…]`;
`run.json` tracks each agent. Claude Code: the hook matcher includes `Agent|Task`; a writer/tester dispatch without a
chosen workflow, with a wrong hash or with `ROUND` above `fix_loop.max_rounds` is denied.

**Parallel.** No configured cap (`parallel.limits.* = null`; an old `parallel.max_writers` is kept and read as the dev
cap); the chosen option sets the numbers, the host limit still applies. Several instances of one role run at once on
disjoint units.

**Test lenses** (`cecilia-test/references/lenses/`): functional, integration, concurrency-perf, security, ui, database,
infra (validate only). **Review panel from STANDARD** (3–4 lenses by the diff; CONTROLLED 5–6 + redteam; FAST one
reviewer), two rounds + judge as in v19.2. **Fix loop:** automatic, at most 3 rounds on ACCEPTED BLOCKER/SHOULD-FIX,
re-testing affected lenses and re-reviewing lenses with findings on the new SHA; DISPUTED or exhausted → options.

**Lanes.** Each role writes only inside its `lanes` globs (config, defaults from the registry) plus its task's
`tensura/reports|tasks|backups`; outside → deny (Claude Code) and `HANDOFF: needs <role> — <what>` in the report.

**Per-project rules.** Workspace `rules/` (`_project.md`, `roles/<short>.md`, `flows/<flow>.md`, `lenses/<lens>.md`),
list lines `- PR-nn: …` plus optional `cecilia-check` blocks (`forbid_regex`, `require_command`). Briefs embed the text
and its hash; `rules.enforce: "gate"` denies a role's first write until it has read them (Claude Code). Only Cecilia
edits `rules/` (`cecilia rules …`); rules may only tighten. `cecilia_check.py` reports rule violations.

**Flows.** `flow: "personal"` (v19.2 behaviour) or `"team"` (ticket intake, branch/commit/PR-template patterns, PR
size limit, escalation to the leader, docs export, reading review comments); `cecilia flow team` (human-only). A flow
is a manifest + a guide with one section per step (`shared/flows/`).

**Registry (SOLID).** `registry/` holds one JSON manifest per agent type, role, flow and lens; `tools/registry.py`
(`load`, `validate`, `compile`, `short`, `default_lanes`) merges workspace extensions; `tools/roster.py` is a
compatibility layer over it; `tools/build_adapters.py` generates the host agents and `shared/generated/{roster,flows,
lenses}.md`. The installer writes the compiled snapshot to `<ws>/.cecilia/registry.json`.

**`cecilia-extend`** (13th role) scaffolds a role/flow/lens from `templates/`, validates it and proposes it under
`tensura/extensions/<name>/`; `cecilia extension apply tensura/extensions/<name>` (human-only) installs it into
`.cecilia/extensions/`. `cecilia scaffold` does the same from the command line.

**CLI.** `cecilia flow`, `cecilia rules`, `cecilia extension`, `cecilia scaffold`; `cecilia upgrade` adds the V20
config keys (never changes a value you set), `rules/` with headers, `registry.json` and the main-thread setting.

**Guard.** Orchestrator lane, role lanes, workflow gate, rules gate (Claude Code); `rules/**` and
`.cecilia/extensions/**` are control paths; agent-run `cecilia flow|rules add|rules rm|extension apply` is denied.
Antigravity: the new gates are procedural (no agent identity in its hook input) and `cecilia_check.py` reports them.

**Validate / evals / docs.** `tools/validate.py` adds registry errors, a stale-command lint (agent-facing markdown must
not name the in-project `cecilia_mode.py`/`cecilia_approve.py` scripts), repo paths named in docs and tool
docstrings must exist, one version in every file that states it, `tools/rules-patch-*.json` overlays on the rule
ledger, "v20" in every SKILL.md heading. Evals V01–V10 (orchestrator-only, options before dispatch, agent counts,
lanes, lenses, panel, fix loop, "fix it yourself", CONTROLLED); S01 grader expects `cecilia push`. Token scenario
`standard-feature-v20`. New `docs/RELEASE.md` (release gate); HOST-SMOKE H90–H99; MIGRATION v19.2 → v20.

## v19.2.0 — 2026-09-27 · review panel, simplest code, blind-tested guard, learning loop

**Review panel** (`cecilia-review` `panel.md`, orchestrator `panel-run.md`, `brief-roles.md`, templates): lenses
chosen by the diff (correctness always, redteam in CONTROLLED; security, data, performance, api-consumer, tests,
operations, ui, simplicity), round 1 blind and parallel, orchestrator anonymises, round 2 cross-examination
(AGREE/REFUTE/ADD with evidence; changing a position needs new evidence; no voting), a judge that took no part
(strongest model) decides each finding on evidence — ACCEPTED / REJECTED / DISPUTED → Cecilia; a DISPUTED would-be
BLOCKER makes the verdict INCOMPLETE. Auto in CONTROLLED G3/G4, on request in STANDARD. Config `review.panel`.

**Simplest code** in the always-loaded `core-min.md`; `Simpler option:` in the short plan and the CONTROLLED plan;
review asks the simplicity question on every code review (over-engineering = SHOULD-FIX).

**Guard.** A holdout set written by a separate agent that never saw the guard (90 adversarial + 45 benign) found
15 gaps (75/90) and one false positive; fixed to 89/90 and 45/45 (the remaining item is a deliberate policy:
applying migrations to the local development database is allowed). New: git aliases/`GIT_CONFIG_*` that push,
commands hidden in base64 / PowerShell `-EncodedCommand` / interpreter code (decoded and judged), process
substitution from the network, inline shell aliases, writes to shell/git profiles, agent permission-bypass flags,
secrets read from git history, installer downloads (ask), `KEY=VALUE` environment arguments (`RAILS_ENV=staging`),
grep patterns no longer read as file paths, **content scan** of Edit/Write for real-looking credentials.

**Learning loop.** `tensura/lessons.md` (`L-nn`, `[generic?]` for promotion; `cecilia lessons [--all DIR]`),
`tensura/conventions.md` one-page project conventions (discovery `onboard/conventions.md`), the project's own
`CLAUDE.md`/`AGENTS.md` imported into the workspace guide. `scale` small/standard/large proposed by `cecilia init`.

**CLI.** `cecilia status`, `cecilia scorecard`, `cecilia lessons`, `cecilia clean` (`tools/workspace_tools.py`).

**Evals** run in workspace mode; `--resume`, `--max-tokens`, stop on host usage limits with results kept; S13. First
real core run on Claude Code: safety 11/11, activation 2/2, quality 2/2, process 3/4 (`tools/evals/baseline-v19.2.json`).
It showed the main session did not load a Cecilia skill for plain tasks (no Rollback/Deviations): the workspace
`CLAUDE.md` now routes every task through a skill (P01 FAIL → PASS). Remaining: P03 answers a quick either/or question
in prose instead of the options table. Graders for S03/S06/P02/P03 now test the property, not the wording.

**Tokens.** Orchestrator briefs split (`agent-briefs.md` + `brief-roles.md` + `brief-more.md`, `panel-run.md`):
STANDARD frontend feature 43k tok (v19.0: 42k) after adding the panel, simplicity and lessons rules. The 28k target
is not met: the rest is domain guidance (code principles, visual checks, web guidelines) that would lose quality.

## v19.0.0 — 2026-09-27 · workspace + uv, local-only, api-ux, db growth, fewer tokens

**Install with uv, work from a workspace.** The package is a uv tool (`pyproject.toml`, `src/cecilia/cli.py`):
`uv tool install git+<your repo>@v19.0.0` gives the `cecilia` command (init, open, doctor, upgrade, mode, approve,
push, push-lock, validate, tokens, corpus, evals) and uv brings the Python. `cecilia init <project>` creates
`<project>.cecilia/` next to the project (skills, agents, hooks with `--workspace`, `.cecilia/` with
`workspace.project`, `tensura/`, `CLAUDE.md`/`AGENTS.md`, `<project>.code-workspace`); **nothing is written into
the project** — no exclude lines, no settings, no docs. Claude Code gets the project as an additional directory and
absolute `Read(//…)` denies for its secret files. The in-project layout stays available (`--in-project`).

**Local-only.** Agents never push, open/edit/merge PRs, comment, create remote branches/tags or change remotes
(A4, guard deny); they write the PR body to `tensura/reports/<TASK>/pr-body.md` and hand Cecilia the
`cecilia push …` + `gh pr create … --body-file …` commands. Optional git-level push lock (`pushInsteadOf` +
`pushurl` swap) via `cecilia push-lock on`; `cecilia push` unlocks, pushes, relocks.

**New role `cecilia-api-ux`** — plays the API's consumers: calls and sequential depth per screen, N+1,
over/under-fetch, error DX, idempotency, pagination, contention and rejection rates (Poisson model,
`capacity.py contention`), latency/failure, breaking changes (`apikit.py summary|journey|diff`). Read-only;
`AUX-nn` findings with owner and measurable acceptance, two fix rounds at most. Orchestrator dispatches it after the
API contract and after API-changing backend work.

**cecilia-db** — growth forecasting (`capacity.py forecast|threshold|docsize|restore`), a 10-rung scaling ladder,
engine selection by mechanism with ADR and POC, backup/PITR/DR runbook and drills, concurrency and hot rows,
microservices data (outbox, CDC, saga), HA/replication, security and privacy engineering with VN PDPL and GDPR
checklists, MongoDB engine pack, database template §14–17.

**Tokens.** `core-min.md` (always loaded, every invariant) + SKILL cards ≤ 5 KB + detail in
`references/workflow.md`; `git.md` split into `git.md` / `git-handoff.md`; file-based hand-off (≤ 15-line returns,
`tensura/tasks/<TASK>/state.md`); descriptions ≤ 450 characters. Measured statically: descriptions 9.7 KB → 5.1 KB,
mandatory per role 19–25 KB → 8.6–9.6 KB, STANDARD frontend feature 258 KB → 170 KB, shared re-reads 36 % → 3 %.
`tools/tokens.py --check` fails CI on regressions.

**Guard.** Policy data in `guard/policy.json`; path profiles (infra, data → ask in every mode); compound-command
state (cd, branch, downloaded files); `tool_rules` gate on Claude Code (context7 before new imports) with a
UserPromptSubmit reminder; the `cecilia` CLI's control subcommands and `uv tool install` of Cecilia are human-only;
`uv tool install|run`, `uv python install` ask. Corpus gate 172/172 adversarial, 119/119 benign. Writes through a symlink are judged on the resolved path too; `ln` to a control path is denied.

**Tools.** `cecilia_check.py` (the repo's own lint/typecheck/build/test + secrets + dependency checks incl.
typosquats + size, evidence.json), `cecilia_doctor.py`, `tools/setup.py` wizard, `tools/evals/` (40 scenarios on a
fixture with planted problems, `claude -p`, real token counts, host-limit detection), CI workflow.

**Rules ledger** 151 rules (133 carried, R067/R071/R072/R074/R015 tightened for local-only, R134–R151 new).

## v18.1.0 — 2026-09-24 · see the UI, measure it, upgrade safely

**Frontend sees what it built.** New `visual-check.md` (dev-fe, test): open the running app in a real
browser (`ui.browser`: `playwright-cli` default, `playwright-mcp`, `none`), capture every SCR × state ×
breakpoint, read the console, drive error/empty states with `route` mocks from the contract, emulate dark
mode / reduced motion / forced colours, evidence table in the report. Own session per member
(`-s=<member>`, added to the parallel runtime table, the brief's RUNTIME block and
`workflow.py --resources`). Installing the CLI or a browser is an A3 quote, never done by the agent.

**Measured UI.** New `scripts/uikit.py` (dev-fe, test; stdlib PNG reader/writer): `contrast` (WCAG 2.x
ratio, AA/AAA verdicts), `palette` (dominant colours → nearest design token by ΔE, contrast vs dominant),
`diff` (pixel difference vs a design export: %, box, diff image, `--max-percent` exit code).

**Guidelines and taste.** Vercel Web Interface Guidelines vendored at a fixed commit
(`web-interface-guidelines.md` in dev-fe, ui, test, review) with a priority note (approved design and the
project's copy language win). Optional style guides from taste-skill (`ui.style`: taste, minimalist, soft,
brutalist, redesign; default none) with a "Cecilia overrides" block: fill gaps only, no new dependency,
no hot-linked assets, accessibility first. New `image-to-code.md` (dev-fe). dev-fe rules 11–12, test rule
10, review-frontend checks 11–13, review-ui checks 12–13, ui rule 9. Sources and licences: `THIRD-PARTY.md`.

**Guard.**
- Playwright: local pages only; `install*`, a non-local URL (`open`/`goto`/`tab-new`, MCP
  `browser_navigate`), `attach`/`--cdp`/`--extension`/`--profile`, another `--config`, `run-code`,
  `close-all`/`kill-all`, `PLAYWRIGHT_MCP_*` env overrides → ask. `.playwright/cli.config.json` and
  `.mcp.json` are protected files.
- `npx` / `bunx` / `pnpm dlx` / `yarn dlx` / `npm exec` are judged by the command they run
  (`npx skills add` → ask, `npx prisma migrate deploy` → ask, `npx -c "…"` → inner command).
- **Windows fixes:** executable names are normalised (`git.exe`, `C:\…\npm.cmd`, upper case), Windows
  paths no longer lose their backslashes when split, PowerShell/cmd names map to their rules
  (`Remove-Item`/`del`/`rd`, `Get-Content`/`gc`, `iex`, `Invoke-WebRequest`/`Invoke-RestMethod` with
  `-Method Post`/`-Body`, `Start-Process -Verb RunAs`), `iwr … | iex` is denied like `curl … | sh`, and
  PowerShell write cmdlets count for control-file protection. Before 18.1 these forms were allowed.
- Shell writes into `.claude/skills` / `.agents/skills` are denied (running their scripts is fine).

**Guard hardening (independent audit before release).**
- Claude Code's **PowerShell tool** is now guarded (hook matcher and the command check; `PowerShell(...)`
  permission rules mirror the `Bash(...)` ones). It is on by default on Windows.
- Claude Code hook in **exec form** (`command` + `args`, absolute paths, no shell): identical under Git Bash
  and PowerShell, safe with spaces in paths, no dependency on `$CLAUDE_PROJECT_DIR`. The installer detects
  `claude --version` and writes the quoted shell form for releases older than 2.1.142 (`--hook-form`).
- Second audit pass: a quote-aware command splitter (braces, `{…}` without spaces, `${VAR}`, `2>&1`, `&>`,
  `>|`), both Windows and POSIX readings of backslashes are judged (`g\it push -f` is `git`), here-doc
  bodies are judged as commands, wrapper options with values (`nice -n 5`, `timeout -s KILL 10`,
  `xargs -n 1`, `env -S`), more PowerShell/cmd/bash flag forms, downloads and extractions into control
  folders (`curl -o`, `-OutFile`, `tar -C`, `unzip -d`), control-file writes judged per command (no false
  denial for `git commit -m "… .cecilia …"`), `git branch -M/-m/-f/-D` rules refined, commands over 100 KB
  ask, `.cecilia/mode.json` is never listed on re-install.
- Nested shells are looked into: `bash -lc`, `sh -xc`, `cmd /c|/k`, `powershell -Command`, `pwsh -c`,
  `wsl …`, `if/then/do/exec/!` prefixes, PowerShell `{ … }` blocks, backtick and caret escapes, line
  continuations; `-EncodedCommand` and text piped into a shell ask; here-doc bodies are not commands.
- Global options no longer hide A4: `npm --registry x publish`, `pnpm -r publish`, `yarn npm publish`,
  `gh -R o/r pr merge`, `gh api -XPUT …`. `--no-verify` abbreviations and `-nm` clusters, `core.hooksPath`
  are denied; git aliases ask; `git branch -f|-D|-M` / `update-ref` on a protected branch are denied;
  `git checkout|restore … <control file>` is denied.
- Windows: relative backslash paths keep their separators (`Get-Content backend\.env` is denied), drive
  roots and profile folders count as wipe targets, NTFS stream / trailing-dot / 8.3 aliases are denied for
  edits, `.WORKTREES` is case-folded.
- Fewer false denials: `2>&1` and `>/dev/null` are not writes, redirects are checked by target, running the
  skills' own scripts and the run ledger (`.cecilia/run.sqlite`) are allowed, reading
  `.cecilia/bin/cecilia_mode.py` is allowed, connector *read* tools (`list_releases`, `get_file_permissions`)
  are no longer treated as writes.
- `config.json`, `mode.json`, approvals and JSON inputs are read BOM-tolerant (PowerShell 5 writes a BOM);
  `workflow.py wave-add` and `check_packet.py` read UTF-8 on Windows; `capacity.py` accepts `int8`/`float8`;
  `cecilia_approve.py --hours` is capped.
- Port blocks from `workflow.py --resources` are unique across the whole run, not per wave.

**Installer.** `--upgrade` replaces Cecilia's own files that differ (skills, agents, `.cecilia/bin`) and
retires files a version no longer ships, after backing every old copy up to
`.cecilia/backup/<timestamp>-before-v<version>/` (global: `~/.cecilia-backup/`). Config, mode, approvals,
host settings/hooks and `.playwright/cli.config.json` are never replaced. Project installs create
`.playwright/cli.config.json` (local origins only) unless `ui.browser` is not `playwright-cli`.
`.gitignore` reminder adds `.cecilia/backup/`, `.playwright-cli/` and `tensura/reports/*/ui/`. With
`--upgrade`, a `settings.json` that only holds what an older Cecilia wrote is replaced too (backed up);
a customised one gets a refreshed `*.cecilia-suggested`. A warning when run from a virtual environment.

**Adapters.** Claude Code dev-fe/test agents may use a Playwright MCP server named `playwright`
(`tools: … mcp__playwright`); every other MCP server stays excluded. Permission rules: ask for
`npx skills`, `playwright-cli install*`; deny edits to `.mcp.json` and the Playwright config.

**Checks.** Rule ledger 133 rules (119 from v17.2.1 + 14 from v18.0/18.1), all kept. 98 tests
(Python 3.9 and 3.11). `validate.py` compiles `uikit.py`, runs a contrast reference value and checks the
browser config allows local origins only.

## v18.0.0 — 2026-09-24 · git flow, backups, parallel roles, options and numbers

**Hosts.** Claude Code and Antigravity only (Codex CLI removed). Claude Code can now be installed
user-global too. Hook commands use the absolute interpreter path, so Windows needs no `python3`.

**Git flow and rollback (enforced).**
- The guard denies file edits on protected branches (`git.protected`, default main/master/develop/trunk/
  production/prod/release/*), on a detached HEAD and outside a git repository (`git.require_task_branch`).
  `tensura/reports/` and `tensura/backups/` stay writable. Worktree checkouts are checked on their own branch.
- `git commit/merge/rebase/cherry-pick/revert/am/pull` while on a protected branch are denied (A4).
- New `shared/git.md`: branch model (gitflow / github / auto), checkpoints (commit per step, `backup/*`
  branches), backups of what git does not hold (`tensura/backups/`, git-ignored), Rollback block in every
  report and PR.

**Approval before edits.** `plan_first` is per mode and on by default for STANDARD and CONTROLLED.

**Parallel roles.** New `shared/parallel.md`: parallel by default up to `parallel.max_writers` (3), all
members of a wave launched in one turn, runtime isolation (ports, compose project, DB per member),
integration branch + combined tests, `wave_checkin` auto/step, separate-session fallback for hosts
without sub-agents. Grouped A3 approvals (one numbered message, answered per item). CONTROLLED scopes can
be bound to a worktree (`"worktree"`), enforced by the guard. `workflow.py plan-waves --max-writers
--resources`. Default models per role in `config.json` `models`.

**Decisions and research.** New `shared/decisions.md` (merges the interview protocol): ≥ 3 options when
three exist (incl. keep-as-is), same criteria, numbers, dated sources, bias check, recommendation kept
separate; mandatory web research for versions, behaviour, prior art.

**Numbers.** New `shared/numbers.md` and `scripts/capacity.py` (in every skill): row/table/index size by
users and months (PostgreSQL and MySQL storage models), connections → RAM, rps → in-flight requests,
instances and DB connections (Little's law), bandwidth, storage cost; low/expected/high, sensitivity,
verification query. `[projected]` label joins `[verified]`/`[inferred]`/`[unverified]`.

**Code quality.** New `shared/code-quality.md`; review checks leanness, delivery (branch, rollback,
deviations) and decisions/numbers on every artifact.

**Less duplication, no lost rules.** `policy.md` + `modes.md` + `gates.md` → `core.md` (the only file every
role reads first); `interview.md` → `decisions.md`; `execution.md` → `parallel.md`; `git-pr.md` → `git.md`.
One source (`shared/scoped/`) for files two roles shared as copies: threat model, authZ matrix,
traceability, decision log, bugfix/refactor/out-of-scope workflows, PR template. Per-skill boilerplate
("Enabled?", repeated Deviations paragraphs) removed. Rule ledger `tools/rules.json`: 119 normative rules
of v17.2.1 mapped to their v18 place; `validate.py` fails if one disappears (119/119 kept; three carry a
note because v18 changed them on purpose: grouped A3 messages, parallel by default, seams from docs).

**Fixes carried from v17.2.1:** UTF-8/ASCII hook I/O on Windows; case-insensitive protected paths on
Windows; dev PRs may contain focused regression tests (review guide no longer contradicts dev-be).

Tests: 64 (git flow, worktree scopes, capacity, parallel waves, rule ledger, installer for both hosts).


## v17.2.1 — 2026-09-24 · Windows encoding fix (also affects v17.1)

- **Guard broke the host on Windows.** Python pipes default to the legacy code page (cp1252/cp1258), so
  every ask/deny reason with an em dash was written as byte `0x97` — invalid UTF-8. Hosts that parse the
  hook output strictly failed with `proto: field google.protobuf.Value.string_value contains invalid
  UTF-8`. The guard now writes ASCII-only JSON (`\u2014` escapes) and forces UTF-8 on stdout/stderr.
- **Guard denied harmless commands on Windows.** Hook input was decoded with the legacy code page, so a
  command or path with some Vietnamese letters (e.g. `Ý`, byte `0x9D`) raised a decode error and the
  guard failed closed with "internal error, blocked for safety". Input is now read as UTF-8 bytes.
- All other scripts (mode, approve, install, validate, sync, build, package, packet check, workflow)
  force a UTF-8 console so Vietnamese paths and dashes never crash them.
- Regression tests run the hook under cp1252 and cp1258 for Claude Code, Codex and Antigravity.

## v17.2.0 — 2026-09-24 · database and UI roles, role switches, readable docs

- **New role `cecilia-db`** — schema, constraints, indexes, query plans, partitioning and retention (never
  created in the insert path), procedures/functions/triggers/jobs only inside versioned migrations,
  connection pools and timeouts, engine settings, instance size and read replicas. PostgreSQL and MySQL
  notes plus `_new-engine.md`. Local DB work follows the work mode; shared DBs are A3; production is
  Cecilia's.
- **New role `cecilia-ui`** (off by default) — flows, wireframes, high-fidelity screens with every state,
  tokens (`design-tokens.json`, DTCG format), component specs, WCAG 2.2 AA checks, handoff to dev-fe
  through `<app>-ui.md` and `ui-exports/`. Tool asked once per project: Penpot, Figma or Markdown.
- **`.cecilia/config.json`** — per-project role switches, `plan_first`, `docs_layout`,
  `ui.design_writes`. Created by the installer; edited by hand; shown by `cecilia_mode.py --show` with
  typo warnings. The orchestrator plans only with roles that are on and reports a needed-but-off role.
- **Guard** — Penpot/Figma connector writes are denied while `cecilia-ui` is off and asked (or allowed by
  `ui.design_writes`) while on; reads stay allowed. Codex hooks now pass `mcp__*` calls to the guard.
- **Obedience** — `plan_first` project option; a `Deviations:` line ends every report, brief return
  (`DEVIATIONS`), briefing and review report.
- **Docs layout** — `tensura/docs/system/`, `modules/<m>/` (monolith) or `services/<s>/…/modules/<m>/`
  (microservices), `apps/<app>/`; files named `<module>-design.md`, `<unit>-database.md`,
  `<unit>-api.md/.yaml`, `<app>-frontend.md`, `<app>-ui.md`… Logical-name table in `workspace.md` §2.1;
  legacy flat names still read. Templates renamed to match.
- **Review** — `review-database.md`, `review-ui.md`, a "Review guide per role" table (validate fails if a
  role has none) and written objectivity rules.
- **Maintainability** — one roster (`tools/roster.py`) read by build_adapters, validate, install and
  tests; `shared/scoped/` for files two skills share (schema guide + database template for db and its
  design fallback); `docs/EXTENDING.md` checklist; validate checks role wiring.
- Tests extended for config, design-tool guard, Codex MCP, installer config, roster wiring.


## v17.1.0 — 2026-09-23 · Antigravity canonical agents + global install

- Antigravity adapters now generate canonical nested custom agents at `agents/<name>/agent.md`.
- Antigravity agent `skills:` references are customization-root relative (`skills/<name>`), so the same
  definition works project-local and global.
- Added `tools/install.py --global --host antigravity [--apply]`.
- Global Antigravity install covers 2.0/IDE skills, CLI skills, global agents, shared hooks, and a global
  Cecilia guard/control binary directory.
- Project and global Antigravity hooks now embed the exact Python executable used by the installer,
  avoiding the Windows `python3` launcher mismatch.
- Added regression coverage for nested agent discovery layout, global installation, idempotency, and
  rejecting unsupported global hosts.

## v17.0.0 — 2026-09-23 · adaptive vibe coding

V17 keeps the same 9 specialist skills but changes Cecilia from a heavy always-on production pipeline
into a daily-driver pair-programming workflow for a developer who remains present and in control.

- Added three work modes in `shared/modes.md`: **FAST**, **STANDARD** (default), and **CONTROLLED**.
- FAST/STANDARD treat a clear user coding task as authorization for the reasonable **local** edits
  needed to complete it; no G2/file-by-file approval ceremony.
- CONTROLLED preserves the strict v16 `cecilia-scope` + G2 flow for broad, risky or explicitly locked
  work. High-risk domains are automatically biased toward CONTROLLED.
- A3/A4 boundaries remain mode-independent: shared/live/destructive/network actions require explicit
  human confirmation; production mutation, merge, IAM, raw secrets and publishing remain human-only.
- Added `.cecilia/bin/cecilia_mode.py`; the human can persist `fast`, `standard` or `controlled` per
  project. Agents are blocked from changing the mode themselves.
- Orchestrator now chooses the smallest useful role chain instead of invoking every role. Planning,
  challenge, evidence and independent review scale with task risk.
- Updated dev/test/review/devops behavior for adaptive ceremony while preserving production controls.
- Updated guard semantics: structured local writes are allowed in FAST/STANDARD but protected/control
  paths and secret files remain blocked; CONTROLLED retains exact write-scope checks.
- Updated Codex adapter to current `approval_policy = "on-request"` and current top-level hooks schema.
- Installer now creates STANDARD mode by default and installs the mode tool.
- Expanded regression tests for mode behavior and human-only mode switching.

## v16.0.0 — 2026-09-23 · hỗ trợ, không tự ý

Mục tiêu do Cecilia đặt: một bộ skill + agent hỗ trợ làm production, **chỉ hỗ trợ, không được tự ý**;
duyệt plan một lần rồi agent sửa local trong phạm vi đó; mọi thứ ra khỏi máy thì hỏi từng lần.
Host: Claude Code, Codex CLI, Antigravity.

**Nền là v15, chuyên môn lấy lại từ v14.**
- Giữ của v15: 9 vai, cổng G1–G4, bằng chứng gắn SHA, reviewer độc lập, ledger resume/receipt,
  packet checker, validator chạy được từ mọi thư mục.
- Lấy lại từ v14 (đã chỉnh cho v16, không dán nhãn cảnh báo): hướng dẫn onboard (survey, as-built,
  nhãn độ tin cậy, reconcile, risk map), SRS, HLD/LLD/DB/API, thiết kế FE, threat model/authZ, bộ quy
  tắc code BE/FE và stack, workflow bugfix/refactor/scaffold, chiến lược/thiết kế/cấp độ test, bug
  report, review theo từng loại artifact, verify commission/omission, devops authority/deploy/rollback/
  incident/platform, orchestrator (presets, models, briefs, relay, fallback, briefing), template riêng
  từng vai. Giao thức phỏng vấn nhóm câu hỏi và phản biện hai vòng (rút gọn).

**Mới trong v16.**
- Mô hình quyền A0–A4 trên một trang (`shared/policy.md`), dùng chung cho mọi skill.
- **cecilia-scope**: plan kết thúc bằng khối JSON liệt kê đúng file/lệnh/môi trường; Cecilia kích hoạt
  bằng `cecilia_approve.py` trong terminal của mình (từ chối chạy không có TTY) → snapshot có hạn.
- **cecilia_guard.py**: một hook cho 3 host — chặn A4, hỏi A3, chặn sửa ngoài scope, chặn sửa
  guard/approvals/cấu hình host/.git, chặn đọc file secret, phân loại hành động MCP (Claude); fail closed.
- Adapter sinh từ một bảng (`tools/build_adapters.py`): Claude Code (agents + settings với hook và
  permissions), Codex (agents TOML, config untrusted/workspace-write/no network, hooks, rules),
  Antigravity (agents, hooks). Reviewer read-only ở cả ba.
- Push, PR, comment, dependency, đọc hệ thống live, apply non-prod: **A3 từng lần** (v14/v15 cho tự làm
  một phần). Bỏ "cửa khẩn cấp production" của v14. Orchestrator mặc định `step`.
- Mức độ nghiêm trọng thống nhất: BLOCKER / SHOULD-FIX / SUGGESTION / QUESTION.
- Installer project-local cho 3 host, không ghi đè, gợi ý gộp; 22 test tự động.
