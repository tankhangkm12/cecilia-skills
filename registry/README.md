# Registry (v20) — schema reference

One JSON manifest per role, agent type, flow and lens. `tools/registry.py` loads and validates them;
`tools/build_adapters.py` generates the host agents (`adapters/**`) and the tables in `shared/generated/`
(`roster.md`, `lenses.md`, `flows.md`) from them. Hand-written docs link to those tables instead of repeating them.

Layers: **role** = expertise (its skill) · **flow** = process · **agent type** = permissions · guard = enforcement ·
adapter = host format. Adding a role, flow or lens = one manifest here + its skill/guide files, then
`python3 tools/registry.py --check` and `python3 tools/build_adapters.py`.

```
registry/
  agent-types/<name>.json      orchestrator, writer, tester, reviewer
  roles/<cecilia-name>.json    one per role (the file name is the role name)
  flows/<name>.json            personal, team
  lenses/test/<name>.json      functional, integration, concurrency-perf, security, ui, database, infra
  lenses/review/<name>.json    correctness, security, data, performance, api-consumer, tests, operations, ui,
                               simplicity, redteam
```

Every manifest's `name` equals its file name; names are unique per section (a test lens and a review lens may
share a name, e.g. `security`). Files are UTF-8 JSON.

## agent-types/<name>.json

| Key | Type | Meaning |
|---|---|---|
| `name` | string | `orchestrator` · `writer` · `tester` · `reviewer` |
| `summary` | string | one line |
| `writes` | string | `lane` (its role's lane) · `tensura-only` (workspace `tensura/**`) · `none` (read-only) |
| `may_dispatch` | bool | may start other agents (Claude Code `Agent(...)`, Antigravity `invoke_subagent`) |
| `main_thread` | bool | runs as the host's main thread (Claude Code `"agent"` in settings, Antigravity `mainAgent: true`); at most one type |
| `claude.tools` | list or `"inherit"` | allowlist; `"inherit"` = the session's tools (MCP included; the guard judges each call) |
| `claude.disallowedTools` | list | written as `disallowedTools:` (omitted when empty) |
| `antigravity.tools` | list | Antigravity tool names |
| `antigravity.commandExecutionPolicy` | string | written only when the tools include `run_command` |
| `antigravity.model` | string | `model:` of the Antigravity agent (`inherit` · `flash` · `pro`); orchestrator `pro`, others `inherit`. A workspace overrides per role in `.cecilia/config.json` → `antigravity.models` (`{"dev-be": "flash"}`), applied by the installer |

## roles/<cecilia-name>.json

| Key | Type | Meaning |
|---|---|---|
| `name` | string | `cecilia-<short>`, lower-kebab-case |
| `agent_type` | string | a name from `agent-types/` |
| `kind` | string | body text of the host agent: `orchestrator` · `code` · `docs` · `design` · `read` |
| `description` | string | one line for the host agent file (no `: `) |
| `default_on` | bool | value in a fresh `.cecilia/config.json` → `roles` |
| `model` | string | `strongest` · `balanced` · `fast` · `inherit` or a host model name (config `models`) |
| `consumes` / `produces` | list | logical artifacts (`api-contract`, `module-design`, `code`, `report`, …) |
| `lane` | list | write globs. `tensura/…` = workspace-relative, others project-relative, `!` excludes. Every role may also write `tensura/reports/<TASK>/**`, `tensura/tasks/<TASK>/**`, `tensura/backups/<TASK>/**`. `[]` = only those. Config `lanes` copies these defaults; Cecilia (or `cecilia init`) narrows them |
| `report` | string | report path (`tensura/reports/<TASK>/<short>.md`) |
| `review_guide` | list | guide files relative to `skills/cecilia-review/` |
| `rules_slot` | string | `rules/roles/<short>.md` |
| `lenses` | null or string | `"test"` / `"review"` when one instance runs one lens |
| `overrides` | object | `{"claude": {"tools", "disallowedTools"}, "antigravity": {"tools", "commandExecutionPolicy", "model", "extra_tools"}}` — `null` = take the agent type's value; `extra_tools` appends to the Antigravity allow-list (20.2: `call_mcp_tool` for devops, discovery, db, test, dev-be, dev-fe); `model` = plan and review run on `pro`; `"inherit"` (tools) = the session's tools. Used to keep the v19.2 tool sets (design/discovery/plan/extend deny NotebookEdit, ui has no Bash, api-ux keeps its v19.2 tools as a reviewer that writes its report) |

## flows/<name>.json

| Key | Type | Meaning |
|---|---|---|
| `name` · `summary` | string | |
| `rules_slot` | string | `rules/flows/<name>.md` |
| `guide` | string | repo-relative guide (`shared/flows/<name>.md`) with one `## <step>` section per step |
| `steps` | list | must contain all of `intake`, `plan`, `approve`, `dispatch`, `review`, `handoff`, `finish` |
| `settings` | object | defaults copied to config `flows.<name>` (`{}` for `personal`) |

## lenses/<kind>/<name>.json

| Key | Type | Meaning |
|---|---|---|
| `name` · `summary` · `when` | string | `when` = what the change must touch for the lens to be picked |
| `kind` | string | `test` or `review` (= its folder) |
| `guide` | string | test: `skills/cecilia-test/references/lenses/<name>.md`; review: `skills/cecilia-review/references/panel.md#<name>` (the file is checked, not the anchor) |
| `rules_slot` | string | `rules/lenses/<name>.md` |

## Extensions (per workspace)

`<ws>/.cecilia/extensions/registry/{agent-types,roles,flows,lenses/test,lenses/review}/*.json` with skills in
`<ws>/.cecilia/extensions/skills/<name>/SKILL.md`; relative guide paths resolve inside the extensions folder
first. `load(extensions=…)` merges them; a name that collides with the core registry is an error. Only Cecilia
applies an extension (`cecilia extension apply`); `cecilia-extend` only proposes one under `tensura/extensions/`.

## API and CLI (`tools/registry.py`)

```python
load(root=None, extensions=None) -> dict   # {"version","agent_types","roles","flows","lenses":{"test","review"},"errors"}
validate(reg, root=None) -> list[str]      # [] = OK
compile(reg) -> dict                       # snapshot the installer writes to <ws>/.cecilia/registry.json
short(name) -> str                         # "cecilia-dev-be" -> "dev-be"
default_lanes(reg) -> dict[str, list[str]]
```

`python3 tools/registry.py --check [--extensions DIR]` prints every error and exits 1 on any;
without `--check` it prints the compiled snapshot.
