# DESIGN-V20 — the V20 contract (registry, config, rules, brief header, guard gates)

Cecilia skills pack v20.0.0. Python stdlib only; scripts
must run on Python 3.9+ and Windows (use `pathlib`, `encoding="utf-8"`, no shell-isms). See `README.md`, `CHANGELOG.md` and `docs/EXTENDING.md`.

## 0. What V20 is (decided with Cecilia)

1. **Orchestrator only orchestrates.** It is the host's main thread (Claude Code `"agent": "cecilia-orchestrator"` in
   workspace settings; Antigravity `mainAgent: true`). It writes only under the workspace `tensura/`. It never does
   specialist work (code, tests, reviews, designs, migrations) — not even FAST: FAST = it dispatches one role with a
   3-line brief and no workflow file.
2. **Workflow is mandatory from STANDARD.** The orchestrator proposes 2–3 **options** that differ in: number of agents
   per kind, how work is split (`module` | `layer` | `competing`), test/review lenses, and a projected time + token
   estimate. Cecilia chooses; the choice is frozen into `workflow.json` (with a hash). No writer dispatch before that.
3. **Many agents in parallel.** No configured cap (`parallel.limits.* = null`); the chosen option sets the numbers;
   the host's own limit still applies (Claude Code: 20 concurrent). Several instances of one role may run at once
   (e.g. 3 × cecilia-dev-be on disjoint units, 5 × cecilia-test with different lenses).
4. **Test lenses (7):** `functional` (AC, edge, negative), `integration` (services, contract, migrations),
   `concurrency-perf`, `security`, `ui` (real browser, a11y, states), `database`, `infra` (validate only, never apply).
5. **Review panel from STANDARD.** Keep 2 rounds (blind R1 → anonymous cross-examination R2) + judge. STANDARD 3–4
   lenses chosen by the diff; CONTROLLED 5–6 lenses + redteam; FAST = one reviewer.
6. **Fix loop:** automatic, max **3** rounds, fixes BLOCKER + SHOULD-FIX that the judge ACCEPTED; each round re-tests
   the affected lenses and re-reviews the lenses that had findings on the new SHA. DISPUTED or rounds exhausted →
   stop and give Cecilia options.
7. **Models per role**, proposed per agent in the workflow (orchestrator/judge/redteam strongest, dev/test balanced).
8. **Both hosts equal** (Claude Code + Antigravity). Where Antigravity cannot be enforced by its hook, the rule is
   procedural there and `cecilia_check.py` reports violations.
9. **SOLID layering.** Role = expertise (skill) · Flow = process · Agent type = permissions · Guard = enforcement ·
   Adapter = host format. New roles/flows/lenses are added by **one manifest file** + their guide/skill files; tables
   and adapters are generated.
10. **Flows** (= "chế độ"): `personal` (v19.2 behaviour) and `team` (ticket intake, branch/commit/PR-template rules,
    escalation to the leader, docs export, PR size limit, reading review comments). More flows later = new manifest.
11. **Per-project rules** in the workspace `rules/` folder (global + per role + per flow + per lens), always read by
    agents, writable only by Cecilia.
12. **`cecilia-extend`** role: scaffolds a new role/flow/lens from templates, validates it, proposes it under
    `tensura/extensions/<name>/`; Cecilia applies it with `cecilia extension apply` (human-only).
13. Keep everything else from v19.2: A0–A4, local-only, guard A3/A4 rules, `cecilia approve` for CONTROLLED,
    workspace mode, lessons, conventions.

Naming: the new concept is **flow** (config key `flow`, CLI `cecilia flow`). Do not use "mode" (FAST/STANDARD/
CONTROLLED) or "profiles" (path profiles, already taken).

## 1. Registry (owner A1) — `registry/` at repo root, JSON files

```
registry/
  README.md                       schema reference (human)
  agent-types/<name>.json         orchestrator, writer, tester, reviewer
  roles/<cecilia-name>.json       one per role (12 existing + cecilia-extend)
  flows/<name>.json               personal, team
  lenses/test/<name>.json         7 test lenses
  lenses/review/<name>.json       correctness, security, data, performance, api-consumer, tests, operations, ui,
                                  simplicity, redteam (the v19.2 panel lenses)
```

**agent-types/<name>.json**
```json
{"name": "writer", "summary": "…", "writes": "lane",              // lane | tensura-only | none
 "may_dispatch": false, "main_thread": false,
 "claude": {"tools": ["Read","Grep","Glob","Edit","Write","Bash", "…"], "disallowedTools": []},
 "antigravity": {"tools": ["…"], "commandExecutionPolicy": "…"}}
```
`orchestrator`: writes `tensura-only`, may_dispatch true, main_thread true. `reviewer`: writes `none` (review) —
api-ux keeps its v19.2 permission (writes only its report under tensura/) via role-level override.

**roles/<name>.json**
```json
{"name": "cecilia-dev-be", "agent_type": "writer", "kind": "code",
 "description": "one line for the host agent file (same text as v19.2 roster)",
 "default_on": true, "model": "balanced",
 "consumes": ["api-contract", "module-design", "plan"], "produces": ["code", "pr-body", "report"],
 "lane": ["src/**", "app/**", "server/**", "backend/**", "services/**", "!**/*.test.*"],
 "report": "tensura/reports/<TASK>/dev-be.md",
 "review_guide": ["references/review-code.md", "references/code-standards.md", "references/security/review-code-security.md"],
 "rules_slot": "rules/roles/dev-be.md",
 "lenses": null,                       // "test" or "review" when the role takes a lens
 "overrides": {"claude": {"tools": null, "disallowedTools": null}, "antigravity": {"tools": null}}}
```
- `lane` globs: paths starting with `tensura/` are workspace-relative; all others are project-relative; `!` excludes.
  Every role may additionally always write `tensura/reports/<TASK>/**`, `tensura/tasks/<TASK>/**`,
  `tensura/backups/<TASK>/**`. Docs roles (discovery, design, plan, api-ux) lanes are under `tensura/docs/**` /
  `tensura/plans/**`; review has `[]` (read-only). Defaults are generic; `cecilia init` may narrow them per project.
- `review_guide` paths are relative to `skills/cecilia-review/`.
- `rules_slot` = `rules/roles/<short>.md` where `<short>` = name without `cecilia-`.
- Generated adapters for the 12 existing roles must keep the v19.2 tool sets (use `overrides` where a role differed:
  design inherits tools, ui has no Bash, dev-fe/test have `mcp__playwright`, review/api-ux read-only…).

**flows/<name>.json**
```json
{"name": "team", "summary": "…", "rules_slot": "rules/flows/team.md", "guide": "shared/flows/team.md",
 "steps": ["intake", "plan", "approve", "dispatch", "review", "handoff", "finish"],
 "settings": {"tracker": "none", "branch_pattern": "feature/{ticket}-{slug}",
              "pr_template": ".github/pull_request_template.md",
              "commit_pattern": "^(feat|fix|chore|docs|refactor|test|perf|ci|build)(\\([^)]+\\))?!?: .+",
              "max_pr_lines": 400, "docs_export": "", "escalate": ["architecture", "public-contract", "schema", "dependency", "security"]}}
```
`personal.settings` = `{}`. Every flow must declare all 7 steps; its guide has one `## <step>` section per step.

**lenses/<kind>/<name>.json**: `{"name": "security", "kind": "test", "summary": "…", "guide": "skills/cecilia-test/references/lenses/security.md", "when": "auth, input handling, secrets, tenants…", "rules_slot": "rules/lenses/security.md"}` (review lens guide = `skills/cecilia-review/references/panel.md#<lens>`).

**tools/registry.py (A1)** — public API, used by roster/build_adapters/validate/install/scaffold:
```python
load(root: Path | None = None, extensions: Path | None = None) -> dict   # merged registry: {"version","agent_types","roles","flows","lenses":{"test":{},"review":{}}}
validate(reg: dict, root: Path | None = None) -> list[str]               # schema + references exist (skill dir, guides, agent_type, lens guides, flow guide sections); [] = OK
compile(reg: dict) -> dict                                               # JSON snapshot written to <workspace>/.cecilia/registry.json by the installer
short(name: str) -> str                                                  # "cecilia-dev-be" -> "dev-be"
default_lanes(reg) -> dict[str, list[str]]
```
Extensions (`<workspace>/.cecilia/extensions/registry/{roles,flows,lenses/*,agent-types}/*.json`, skills in
`<workspace>/.cecilia/extensions/skills/<name>/`) are merged by `load(..., extensions=…)`; a name that collides with
the core registry is an error. `python tools/registry.py --check [--extensions DIR]` prints errors, exit 1 on any.

**tools/roster.py (A1)** stays as a thin compatibility layer over the registry: `VERSION = "20.0.0"`,
`ORCHESTRATOR`, `ORCH_DESC`, `ROLES` (name → (kind, description), all roles except the orchestrator, incl.
cecilia-extend), `DEFAULT_OFF`, `DEFAULT_MODELS`, `all_names()`, `default_config()`, `migrate_config()`,
`UI_BROWSERS`, `UI_STYLES`, `policy()`.

**Generated docs (A1, by `tools/build_adapters.py`)**: `shared/generated/roster.md` (role · agent type · lane ·
consumes · produces · report · review guide · rules slot), `shared/generated/lenses.md`, `shared/generated/flows.md`.
Hand-written files link to these instead of repeating tables.

## 2. Config — `.cecilia/config.json` (defaults in `roster.default_config()`, A1)

New / changed keys (everything else as v19.2):
```json
{"flow": "personal",
 "flows": {"team": { …team.settings defaults… }},
 "orchestration": {"orchestrator_writes": "tensura-only", "workflow_required_from": "standard", "options": 3},
 "parallel": {"limits": {"dev": null, "test": null, "review": null}, "wave_checkin": "auto"},
 "lanes": { "<role>": ["…globs…"] },                 // from registry default_lanes(); Cecilia edits
 "test": {"lenses": ["functional","integration","concurrency-perf","security","ui","database","infra"]},
 "review": {"panel": {"from": "standard", "reviewers": {"standard": 3, "controlled": 5},
                      "redteam_in": ["controlled"], "rounds": 2, "judge_model": "strongest", "cross_model": ""}},
 "fix_loop": {"max_rounds": 3, "severities": ["BLOCKER", "SHOULD-FIX"], "on_exhausted": "options"},
 "rules": {"dir": "rules", "enforce": "gate", "max_bytes_per_file": 2048},
 "extensions": {"dir": ".cecilia/extensions"}}
```
`parallel.max_writers` is no longer written; if a user config has it, it is kept and read as a cap for `dev`.
`migrate_config()` adds the new keys (V20_KEYS), never changes values Cecilia set, converts nothing silently.

## 3. Rules folder (workspace `<ws>/rules/`)

```
rules/_project.md          every role + orchestrator
rules/roles/<short>.md     that role only (one per role, created empty-with-header at init/upgrade)
rules/flows/<flow>.md      when that flow is active
rules/lenses/<lens>.md     optional, when that lens runs
```
Format: Markdown. Each rule is a list line `- PR-nn: text` (ids unique per file). Optional machine checks in a
fenced block with info string `cecilia-check` holding a JSON list:
`[{"id": "PR-03", "forbid_regex": "console\\.log\\(", "paths": ["src/**"]}, {"id": "PR-04", "require_command": "npm run lint"}]`.
Precedence: A3/A4 safety > project rules > role defaults > skill text. Rules may only tighten: a rule that tries to
allow push/PR/merge/production/secrets is a lint error.

**Rules hash** (same algorithm everywhere — workflow.py, guard, cecilia_check; copy the function, do not import):
```python
def rules_hash(ws: Path, role: str | None, flow: str, lens: str | None) -> str:
    files = ["rules/_project.md"] + ([f"rules/roles/{short(role)}.md"] if role else []) + \
            [f"rules/flows/{flow}.md"] + ([f"rules/lenses/{lens}.md"] if lens else [])
    h = hashlib.sha256()
    for rel in files:
        p = ws / rel
        if p.is_file():
            h.update(rel.encode() + b"\n" + p.read_bytes() + b"\n")
    return h.hexdigest()[:12]
```
`short(role)` strips a leading `cecilia-`. Only Cecilia edits `rules/` (guard control path; CLI `cecilia rules …`).

## 4. Brief header and task files (owner A3; read by guard A2 and cecilia_check A6)

Every brief produced by `workflow.py brief` starts with exactly one line:
```
[cecilia-brief TASK=<id> ROLE=<cecilia-name> LENS=<lens|-> UNIT=<unit|-> WORKFLOW=<hash|none> ROUND=<0-3> RULES=<hash>]
```
followed by the fields of `assets/agent-brief-template.md` and a `## Rules (must follow)` section that embeds the
full text of the applicable rules files. `ROUND=0` = first build, 1..3 = fix rounds.

Task folder `<ws>/tensura/tasks/<TASK>/`:
- `options.json` / `options.md` — the 2–3 options (written by `workflow.py options`).
- `workflow.json` — `{"task","mode","flow","chosen","option":{…},"created","hash"}`; `hash` = first 12 hex of
  sha256 of the canonical JSON (`sort_keys=True, separators=(",",":")`) of `option`. `workflow.md` = readable copy.
- `run.json` — `{"task","round": 0, "agents": [{"id","role","lens","unit","state","sha","started","ended","tokens"}]}`.
- `state.md` (v19.2, unchanged).

`workflow.py` subcommands (keep the existing ones): `options`, `choose`, `brief`, `round`, `agent`
(start/done updates in run.json), `merge-tests`. Workspace found by `--workspace` or walking up from cwd to a folder
with `.cecilia/config.json`; registry from `<ws>/.cecilia/registry.json` (fallback: repo `registry/` via
`tools/registry.py` when run from the source repo).

Every role's report ends with the v19.2 lines plus: `Rules: <hash> (PR-ids applied)` and, when it stopped because of
its lane, `HANDOFF: needs <role> — <what>`.

## 5. Guard additions (owner A2) — `guard/cecilia_guard.py`, `guard/policy.json`

Reads `<ws>/.cecilia/registry.json` (optional; absent → the new gates are off) and config `lanes`, `orchestration`,
`fix_loop`, `rules`, `flow`. New decisions (Claude Code; agent identity = hook input `agent_type`):
1. **Orchestrator lane:** a write (edit tools and shell write targets) by `agent_type == "cecilia-orchestrator"`
   outside `<ws>/tensura/**` → DENY ("dispatch it to the right role").
2. **Role lanes:** a write by a cecilia role outside its `lanes` globs (+ implicit tensura/reports|tasks|backups of
   any task) → DENY with `HANDOFF` hint. Agents that are not cecilia roles: v19.2 behaviour.
3. **Workflow gate:** hook matcher now includes `Agent|Task` (A1 adds it to settings). Tool input
   `{"subagent_type","prompt",…}`. If `subagent_type` is a cecilia role whose agent type is `writer` or `tester`,
   and the work mode is STANDARD or CONTROLLED (respect `orchestration.workflow_required_from`): the prompt's first
   line must be a valid brief header; `tensura/tasks/<TASK>/workflow.json` must exist with a non-empty `chosen`
   and the header's `WORKFLOW` must equal its `hash` → else DENY with the fix ("run workflow.py options/choose").
   `ROUND` > `fix_loop.max_rounds` → DENY ("give Cecilia options"). FAST mode, reviewers and non-cecilia agents: no gate.
4. **Rules gate** (`rules.enforce == "gate"`): the first write by a cecilia role in a session is DENIED unless its
   transcript contains its brief header with `RULES=<current hash>` or a Read of its rules files (reuse the
   `tool_rules` transcript machinery; unreadable transcript → allow, as tool_rules does).
5. **Control paths:** `<ws>/rules/**` and `<ws>/.cecilia/extensions/**` are control files (agents never write them).
   Agent-run `cecilia flow|rules add|rules rm|extension apply` → DENY (human-only, like `cecilia mode`).
6. Antigravity: gates 1–4 are not enforceable (no agent identity) → unchanged behaviour; document in LIMITATIONS.
Keep the corpus gate 100 %/100 %: add adversarial/benign lines for the new rules to `tests/corpus/*.jsonl` where a
command-line form exists (e.g. `cecilia flow team`, `cecilia extension apply x`, `echo x > rules/_project.md`).
Bump `VERSION` in the guard and `policy.json` to `20.0.0`.

## 6. Extending V20

New roles, flows and lenses follow `docs/EXTENDING.md` (manifest in `registry/` + guide/skill, or ask the
`cecilia-extend` role). Tables in `shared/generated/` and the host adapters are generated by
`tools/build_adapters.py`; `tools/sync_common.py` copies `shared/` into every skill; `tools/validate.py` checks it all.
