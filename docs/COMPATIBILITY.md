# Host compatibility — v20

Checked against the official host documentation on 2026-09-24 (v19 rows) and 2026-09-28 (V20 rows); still run
`HOST-SMOKE.md` on the exact versions you use.

| Host | Skills | Agents | Guard hook | Approval |
|---|---|---|---|---|
| Claude Code | `.claude/skills/<name>/` · `~/.claude/skills/` | `.claude/agents/<name>.md` · `~/.claude/agents/` | `settings.json` `hooks.PreToolUse`, matcher `Bash\|PowerShell\|Edit\|Write\|MultiEdit\|NotebookEdit\|Agent\|Task\|mcp__.*` | permissions allow/ask/deny + hook `permissionDecision` |
| Antigravity project | `.agents/skills/<name>/` | `.agents/agents/<name>/agent.md` | `.agents/hooks.json`, named group `cecilia-guard`, `PreToolUse` | hook `decision`: `allow` / `ask` / `force_ask` / `deny` |
| Claude Code, workspace mode (default) | `<project>.cecilia/.claude/skills/` | `<project>.cecilia/.claude/agents/` | same hook + `--workspace <abs>`; project in `permissions.additionalDirectories` | same |
| Antigravity, workspace mode | `<project>.cecilia/.agents/skills/` (workspace folder listed first in `<project>.code-workspace`) | `<project>.cecilia/.agents/agents/` | `.agents/hooks.json` + `--workspace <abs>` | same — multi-folder behaviour: HOST-SMOKE H65 |
| Antigravity global (older) | `~/.gemini/config/skills/` (2.0/IDE), `~/.gemini/antigravity-cli/skills/` (CLI) | `~/.gemini/config/agents/<name>/agent.md` | `~/.gemini/config/hooks.json` | same |

## V20 — orchestrator as main thread, parallel sub-agents

| Need | Claude Code | Antigravity |
|---|---|---|
| orchestrator is the main thread | workspace `.claude/settings.json` `"agent": "cecilia-orchestrator"` (the `agent` setting; `claude --agent <name>` overrides it for one session) — the main thread takes that agent's system prompt, tools and model; the startup header shows `@cecilia-orchestrator` | `mainAgent: true` in `cecilia-orchestrator/agent.md` makes it selectable as the primary agent in chat — **select it** (HOST-SMOKE H90); the other roles have `subagent: true` |
| dispatch | `Agent(...)` tool (named `Task` before 2.1.63; `Task` still works as an alias) with `subagent_type` + `prompt`; `tools: Agent(<names>)` is an allowlist of dispatchable agents | `invoke_subagent` tool |
| concurrency | 20 running sub-agents per session by default (then `Concurrent subagent limit reached`); `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` changes it (Claude Code 2.1.217+) | a parent may invoke several subagents concurrently |
| nesting | 3 layers below the main conversation (`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`); Cecilia roles never dispatch — only the orchestrator does | 10 layers, strictly enforced — same Cecilia rule |
| isolation | Cecilia worktrees under `<workspace>/.worktrees/` | subagent workspace mode `inherit` / `branch` (own git worktree) / `share`, or Cecilia worktrees |
| agent identity in the hook | common input `agent_type` = agent name, present with `--agent` (and the `agent` setting — H90 confirms) or inside a sub-agent, where the sub-agent's name wins; `agent_id` only inside sub-agents → orchestrator lane, role lanes, workflow gate and rules gate are enforced | the docs name no agent field in hook input → lanes, workflow and rules gates are procedural; `cecilia_check.py` reports violations (LIMITATIONS) |
| workflow gate input | PreToolUse on `Agent\|Task`: `tool_input.subagent_type`, `tool_input.prompt` (first line = brief header) | — |

## Notes

- Claude Code agent frontmatter used: `name`, `description`, `tools` (omitted for the design role →
  inherits, so a Penpot/Figma MCP is reachable), `disallowedTools`, `model: inherit`, `skills` (preloaded).
- Antigravity agent frontmatter used: `name`, `description`, `tools`, `mainAgent`, `subagent`, `model`,
  `commandExecutionPolicy`, `skills` (`skills/<name>`, valid for workspace and global roots).
- Tool sets per role come from the registry (`registry/agent-types/*.json` + role `overrides`); the generated
  adapters keep the v19.2 sets for the 12 v19 roles (review read-only, ui without Bash, dev-fe/test with
  `mcp__playwright`).
- Hook I/O is JSON on stdin/stdout. The guard writes ASCII-only JSON and reads UTF-8, so Windows code
  pages do not matter.
- Claude Code hook: **exec form** — `"command": "<absolute python>"`, `"args": ["<absolute guard>", "--host",
  "claude"]` — no shell, so it behaves the same under Git Bash and PowerShell and with spaces in paths.
  Needs Claude Code 2.1.142+ (May 2026, "hook args exec form"); the installer detects the version and
  falls back to a quoted shell command for older releases (`--hook-form` to override). Claude Code's PowerShell
  tool (on by default on Windows) is guarded like Bash.
- Antigravity hook: shell command with the absolute interpreter and guard paths, quoted.
- Claude Code dev-fe/test agents list `mcp__playwright` in `tools` (server-level pattern, per the
  sub-agents doc); a Playwright MCP server must be registered under the name `playwright`.
- Playwright CLI checked with `@playwright/cli` 0.1.21 (2026-09): `open`/`goto`/`resize`/`screenshot
  --filename`/`snapshot`/`console`/`route`/`-s=<session>`/`--config`, `install-browser`; config file
  `.playwright/cli.config.json` with `network.allowedOrigins` (`http://localhost:*` form supported).
  Requires Node.js ≥ 18.
- Codex CLI support was removed in v18 (use v17.2.1 if you still need it).

## Sources

- Claude Code — "Create custom subagents" (`agent` setting, `--agent`, `Agent` tool, concurrency and
  `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`, nesting depth): https://code.claude.com/docs/en/sub-agents — read
  2026-09-28 · Hooks (PreToolUse input incl. `agent_type`, matchers): https://code.claude.com/docs/en/hooks — read
  2026-09-28 · Tools (PowerShell): https://code.claude.com/docs/en/tools-reference · Week 20 2026 notes (exec-form
  hooks): https://code.claude.com/docs/en/whats-new/2026-w20
- Antigravity — Subagents (`mainAgent`, `subagent`, concurrency, nesting 10, worktree mode `branch`):
  https://antigravity.google/docs/subagents — read 2026-09-28 · Agent Skills: https://antigravity.google/docs/skills/ ·
  Hooks: https://antigravity.google/docs/hooks · Custom agents: https://antigravity.google/blog/introducing-custom-agents
- Playwright CLI: https://playwright.dev/docs/getting-started-cli · https://github.com/microsoft/playwright-cli
