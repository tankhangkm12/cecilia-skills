# Workspace — where things live and who owns them (common v20)

<!-- common v20 — canonical copy in shared/, synced into every skill by tools/sync_common.py. Do not edit a copy. -->

Roles cooperate through files, so any agent, model or person can pick up where another stopped.
**No file has two owners.** That is what makes separate roles — and parallel work — safe.

## 1. Roles and ownership

`.cecilia/config.json` says which roles are on (`core.md` §4). A role that is off owns nothing in this
project; its fallback owner (last column) does that work.

**Lanes, inputs, outputs, report path, review guide and rules slot of every role are generated from the
registry:** `generated/roster.md` (next to this file) — the source of truth, never copied by hand. The
project's `lanes` in config may narrow a lane; a write outside it is a `HANDOFF: needs <role> — <what>`
(`core.md` §3.4). Roles added by `cecilia-extend` appear there too.

| Skill | Owns | If off, done by |
|---|---|---|
| cecilia-orchestrator | coordination: options, workflow, briefs, run log — writes only under `tensura/`, never specialist work | Cecilia calls roles directly |
| cecilia-discovery | what exists and what is needed (system map, idea, requirements, as-built docs, risk map, conventions) | Cecilia |
| cecilia-design | how it is built: architecture, module design, API contract, frontend architecture, threat model, `DECISIONS.md` rows | Cecilia |
| cecilia-db | the database: database doc, migrations, DB-side code, performance | cecilia-design (database doc) · cecilia-dev-be (migrations) |
| cecilia-plan | plans, units and write sets, scope blocks, tracking (`tensura/plans/**`) | Cecilia |
| cecilia-dev-be | backend code (one or more instances, one unit each) | Cecilia |
| cecilia-dev-fe | frontend code (one or more instances, one unit each) | Cecilia |
| cecilia-ui | the visual interface: UI design doc, `design-tokens.json`, `ui-exports/**`, the design-tool file | cecilia-design (frontend mode) |
| cecilia-test | test strategy, cases, test code per lens, bugs | Cecilia |
| cecilia-review | judgement per review lens — nothing in the repo; its report only | `[self-review]` only — never counts as independent |
| cecilia-api-ux | the consumer's view of the API — its report `tensura/reports/<TASK>/api-ux.md` only | cecilia-review (design mode, API contract) |
| cecilia-devops | delivery path: pipeline, image, manifest, IaC paths, infrastructure doc, incident reports | Cecilia |
| cecilia-extend | proposals for new roles/flows/lenses under `tensura/extensions/<name>/` (Cecilia applies them) | Cecilia |

A missing upstream artifact is a question for Cecilia or a recommendation to run the role that
produces it — never a refusal, never something invented. Each skill runs alone when called directly.

## 2. Layout — everything under `tensura/`

`docs_layout` in `.cecilia/config.json` is `monolith` or `microservices`. Folders group by module (monolith)
or by service, with its modules inside (microservices). File names carry their module/service/app name, so
an editor tab or quick-open result says what it is without the folder.

**Monolith** — one folder per module:

```
tensura/
├── README.md                          what exists, where things stand — read first
├── docs/
│   ├── README.md                      index + status + confidence of each doc
│   ├── DECISIONS.md                   D-nn decision log
│   ├── system/
│   │   ├── system-map.md              as-built survey           → discovery
│   │   ├── idea.md · requirements.md  problem, scope, FR/NFR/BR/AC → discovery
│   │   ├── architecture.md            architecture (HLD)        → design
│   │   ├── security.md                threat model, authZ matrix → design
│   │   ├── test-plan.md               test strategy             → test
│   │   └── infrastructure.md          delivery path, runtime    → devops
│   ├── modules/<module>/
│   │   ├── <module>-design.md         module design (LLD)       → design
│   │   ├── <module>-database.md       schema, indexes, perf     → db
│   │   └── <module>-api.md + .yaml    API contract — THE SEAM   → design
│   └── apps/<app>/
│       ├── <app>-frontend.md          screens, state, routing   → design
│       ├── <app>-ui.md                visual design             → ui
│       ├── design-tokens.json                                   → ui
│       └── ui-exports/                screen images per state   → ui
├── plans/<TASK>-<slug>.md             plan when useful; CONTROLLED plans end with cecilia-scope block(s)
├── conventions.md                     one page: naming, patterns, commands, layout — discovery keeps it
├── lessons.md                         L-nn lessons from past tasks; `[generic?]` ones Cecilia may promote
├── tasks/<TASK>/
│   ├── state.md                       goal, mode, flow, branch + start SHA, steps done/next, pending
│   │                                  decisions, report paths — updated at every stop, read first when resuming
│   ├── options.json · options.md      the 2–3 options the orchestrator proposed (STANDARD+)
│   ├── workflow.json · workflow.md    the option Cecilia chose, frozen with its hash (briefs carry it)
│   └── run.json                       fix round + every agent: role, lens, unit, state, SHA, tokens
├── extensions/<name>/                 cecilia-extend proposals; `cecilia extension apply` is Cecilia's
├── reports/<TASK>/
│   ├── README.md                      one row per report — read before any report
│   ├── challenges.md · metrics.md     append-only
│   ├── <role>.md                      full report of a role (dev-be.md, db.md, api-ux.md…; rerun → -2, -3)
│   ├── pr-body.md                     Draft PR description Cecilia passes to `gh pr create --body-file`
│   ├── escalation.md                  team flow: decisions for the leader, with options (flows/team.md)
│   ├── briefs/W<n>-<role>-<unit>.md   briefs for separate sessions (parallel.md §5)
│   └── orchestration-<TASK>.md        run log (orchestrator only)
└── backups/<TASK>/                    DB dumps and copies taken before a change (git.md §4)

.cecilia/                              mode, config, approvals, guard — written by Cecilia's tools/hands only
```

**Microservices** — one folder per service; the contract, database and infrastructure belong to the
service, the detailed design to each module inside it:

```
tensura/docs/
├── README.md · DECISIONS.md
├── system/                            as above (system-wide requirements, architecture, security, test plan)
├── services/<svc>/
│   ├── <svc>-overview.md              modules it owns, its database, who calls it → design
│   ├── <svc>-api.md + .yaml           the service's contract    → design
│   ├── <svc>-database.md              database-per-service      → db
│   ├── <svc>-infrastructure.md        its delivery path         → devops
│   └── modules/<module>/
│       └── <module>-design.md         module design (LLD)       → design
└── apps/<app>/                        as above
```

### 2.1 Logical names → paths

Skills name documents by the logical name; resolve it here. `<unit>` is the **module** in a monolith and
the **service** in microservices.

| Logical name | Monolith | Microservices | v17.1 name (legacy) |
|---|---|---|---|
| system map | `system/system-map.md` | same | `00-system-map.md` |
| idea | `system/idea.md` | same | `01-idea.md` |
| requirements (SRS) | `system/requirements.md` | same | `02-srs.md` |
| architecture (HLD) | `system/architecture.md` | same | `03-hld.md` |
| module design (LLD) | `modules/<module>/<module>-design.md` | `services/<svc>/modules/<module>/<module>-design.md` | `04-lld-<svc>.md` |
| database doc | `modules/<module>/<module>-database.md` | `services/<svc>/<svc>-database.md` | `05-db-<svc>.md` |
| API contract | `modules/<module>/<module>-api.md` + `.yaml` | `services/<svc>/<svc>-api.md` + `.yaml` | `06-api-<svc>.md` + `.yaml` |
| service overview | — | `services/<svc>/<svc>-overview.md` | — |
| frontend architecture | `apps/<app>/<app>-frontend.md` | same | `07-fe-<app>.md` |
| UI design | `apps/<app>/<app>-ui.md` (+ `design-tokens.json`, `ui-exports/`) | same | — |
| security | `system/security.md` | same | `08-security.md` |
| test plan | `system/test-plan.md` | same | `09-test-plan.md` |
| infrastructure doc | `system/infrastructure.md` | `services/<svc>/<svc>-infrastructure.md` | `10-infra-<svc>.md` |

All paths are under `tensura/docs/`. Module, service and app names are lower-kebab-case (`booking`,
`payment-svc`, `web-admin`).

### 2.2 Choosing and keeping the layout

- `docs_layout` set → use it. Not set and no docs yet → ask Cecilia once (monolith or microservices);
  she records it in `.cecilia/config.json` — an agent never writes that file.
- **Legacy (v17.1) flat layout found** (`04-lld-*.md` … directly under `tensura/docs/`): read it through
  the table above, keep writing that project in the legacy names, and ask Cecilia once whether to
  migrate. Migration is its own task: `git mv` every file per §2.1, fix links between docs, one commit —
  never mixed into feature work. Never write one project in both layouts.
- A monolith that splits into services is a design Change (`cecilia-design`): the module folders move
  under their new service in one migration task, with the move recorded as a `D-nn`.

### 2.3 Rules

- `<TASK>` = task/epic id (e.g. `SHOP-42`); none → `no-task-<slug>`.
- A repo that already keeps docs elsewhere wins: follow it and record the real location in
  `tensura/README.md`. Plans and reports still live in `tensura/`.
- Never overwrite a report: same name → suffix `-2`, `-3`.
- Do not create every document for a small change. Write what the risk class needs.
- **Local-only:** in workspace mode none of these is in the project at all. In the older in-project layout
  `tensura/`, `.cecilia/`, `.worktrees/` and the installed Cecilia skills/agents are listed in `.git/info/exclude` — never staged, committed or pushed (the guard refuses `git add -f` of them and
  `cecilia_check.py` reports any that slipped in). Docs Cecilia wants in the repo, she copies there herself — or,
  in the `team` flow with `docs_export` set, the role exports them on the task branch (`flows/team.md`).
- `docs_root` in config moves `tensura/` elsewhere (e.g. `../<project>-docs`); every path above is then relative
  to it.
- `tensura/` exists once — in the workspace (workspace mode) or the main checkout (in-project). An agent in a
  git worktree writes code there and its documents/reports to `tensura/` by the absolute path its brief gives.

### 2.4 Workspace mode (default)

`cecilia init <project>` creates `<project>.cecilia/` next to the project. The session runs there; the project
folder holds **no** Cecilia file.

```
shop/                    the project — code only; git, builds and tests run here
shop.cecilia/            the workspace — local-only, never a git remote
├── CLAUDE.md · AGENTS.md          where the project is (read at session start)
├── .claude/ · .agents/            skills, agents, hooks (Cecilia's)
├── .cecilia/                      config (workspace.project, flow), mode, approvals, guard, registry.json,
│                                  extensions/ — Cecilia's tools only
├── rules/                         project rules: _project.md, roles/<short>.md, flows/<flow>.md,
│                                  lenses/<lens>.md — read by every agent, written only by Cecilia
├── tensura/                       docs, plans, reports, tasks/<TASK>/{state.md,options,workflow,run}, backups
├── .worktrees/<member>/           worktrees of the project for parallel writers
└── shop.code-workspace            opens workspace + project together (Antigravity/VS Code)
```

Paths in code are relative to the project; paths in docs and reports are relative to the workspace. The guard
denies any Cecilia path (`tensura/`, `.cecilia/`, `rules/`, skills, hooks) written inside the project, and any
agent write to `rules/` or `.cecilia/`. In the `team` flow, docs Cecilia wants in the project are exported on
the task branch into `flows.team.docs_export` (`flows/team.md`) — that is the only way Cecilia's docs enter the repo.

## 3. Priority when sources conflict

```
Cecilia's direct instruction > docs > plan > repo conventions > these skills' defaults
```

Following the higher source is never silent: note the conflict in one line. A direct instruction that
contradicts docs on business logic, schema or a public contract → confirm once before acting.

## 4. Traceability IDs

| Prefix | Meaning | Created by |
|---|---|---|
| `FR` `NFR` `BR` `UC` `US` `AC` | requirements, rules, use cases/stories, acceptance criteria | discovery |
| `SCR` `CMP` | screen, frontend component | whichever of design (frontend) or ui writes the screen inventory first; the other reuses the ids |
| `EP` | endpoint or event in the contract | design |
| `THR` `CTL` | threat, security control | design (security) |
| `TC` `BUG` | test case, bug | test |
| `D` | decision | whoever records it, in `DECISIONS.md` |
| `E` `B` `W` | epic, batch, wave | plan / orchestrator |
| `PR` | project rule in `rules/*.md` (`- PR-nn: text`, unique per file) | Cecilia |
| `DSG-Bnn` `DB-Bnn` `BE-Bnn` `UI-Bnn` `FE-Bnn` `TEST-Bnn` `REV-Bnn-x` `OPS-Bnn` `DOC-Bnn` `DSC-Bnn` | role task in a batch | plan |
| `C` `M` | challenge, measurement | shared logs |
| `ENV` `INC` | environment, incident | devops |
| `U` `X` `R` | unknown, contradiction, risk in as-built docs | discovery |

IDs are never renumbered once published; retire with `~~FR-07~~ removed D-12`.
