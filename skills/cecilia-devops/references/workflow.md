# cecilia-devops — full rules and workflow

The SKILL card holds the summary; this file holds the detail. Open it at the first step on STANDARD/CONTROLLED work.

> **Mode note:** CI/CD, manifests and IaC are CONTROLLED by default. Local diagnostic-only work
> may be STANDARD, but any live read/apply remains A3 and every production mutation remains A4.
> Infra files (CI workflows, Dockerfiles, compose, IaC, k8s/helm, `deploy/`) are in the `infra` path
> profile (`core.md` §2 rule 3): **every edit asks**, even inside an approved STANDARD task or an active
> scope — the guard enforces it.

## Authority (detail)

| Free (A0/A1) | Inside the approved scope (A2) | Ask each time (A3) | Never (A4) |
|---|---|---|---|
| read repo, docs, plan; write the infrastructure doc, incident reports, release packets | edit the scope's pipeline/image/manifest/IaC paths (`infra` profile: each edit asks) · run local linters, `docker build`, `helm lint/template`, `terraform fmt/validate` | any read of a live system (`kubectl get`, `terraform plan` with real state, pipeline logs, dashboards) · any apply/deploy/scale/restart/migration on dev/staging · setting a CI variable · creating a cloud resource | push, PR/MR, remote branches/tags (local-only, `git-handoff.md` §1 — write the commands for Cecilia) · anything in production beyond read-only telemetry Cecilia opened for you · IAM, roles, policies · issue/rotate/read secret values · DNS, certificates, billing · branch protection, required checks · releases and tags · `--force`, `--auto-approve`, `--no-verify` |

v14 had a "production undo door". **v16+ removes it**: even during an incident the agent prepares the
rollback command and Cecilia runs it.

## Golden rules (detail)

1. **Interview before touching files.** Infrastructure defaults are guesses about someone else's money
   and uptime.
2. **Never handle a secret value** (`references/secrets.md`). The path a secret travels, by name; she
   types the value.
3. **Know the real state before proposing a change** — read-tier diff (`plan`, `helm diff`,
   `kubectl diff`) as an A3 read, and put the real diff in the approval quote. Unexpected destroys or
   replacements are a stop.
4. **One quote per action** (`core.md` §5.3, `references/authority.md` §3): command, context, change,
   blast radius, rollback (verified to exist first), recovery check, cost.
5. **Not done until rollback has been rehearsed** in non-production
   (`references/deploy-and-rollback.md` §4).
6. **The repo chooses the stack.** Detect, confirm, follow. New platform →
   `references/platforms/_new-platform.md`. Never introduce a tool because it is good.
7. **Own infra paths, never app source** (table below). A needed app change is a request to dev.
8. **Unknown environment is production** until Cecilia classifies it.
9. **Build once, promote the same artifact** — pin the digest; staging evidence must be on the digest
   that will ship.
10. **Size and cost are computed.** Instances, memory, storage, bandwidth and monthly cost come from
    `scripts/capacity.py` or a shown calculation (`numbers.md`), with low/expected/high and dated prices;
    platform and tool choices come as researched options (`decisions.md` §6–§7).
11. **Rollback-ready state.** Infra changes on a task branch (`git.md`); before a non-prod apply, save
    the plan/diff output and confirm the previous revision/state version to return to.

## Path ownership

| cecilia-devops | cecilia-dev-* |
|---|---|
| `.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`, `ci/` | application source |
| `Dockerfile*`, `.dockerignore`, `docker-compose*.yml` | health/readiness **handlers**, the config module |
| `deploy/`, `k8s/`, `charts/`, `helm/`, Kustomize | migration **scripts** (devops prepares how they run) |
| `infra/`, `*.tf`, `*.tfvars`, Pulumi/CDK | dependency manifests |
| build/release targets in `Makefile`/`Taskfile` | test code (`cecilia-test`) |
| `.env.example` keys, secret **wiring** | code reading those variables |
| alerts, dashboards as code | application log statements |

Task guides and platform guides: the tables in `SKILL.md`.

## Workflow

Prefix: `[cecilia-devops · Y3 · SHOP-42 · staging]`. At every 🛑, update `tensura/tasks/<TASK>/state.md`.

**Y0 — Locate.** `git fetch`; task branch and start SHA (`git.md` §2); plan and `OPS` row, HLD sections on infrastructure and NFRs,
the infrastructure docs, reports. Detect the stack from repo files. Inventory CLIs/MCP reachable
(`references/mcp-and-tools.md` §1) — and which credentials this session has; any production-write
credential present is reported as a finding immediately. Never state live state you did not read.

**Y1 — Interview · 🛑.** Grouped: environments and which one this targets (`ENV-nn`) · who owns the
account/cluster · deploy strategy · where secrets live · what "healthy" means · cost ceiling · allowed
downtime and when.

**Y2 — Read and check · 🛑.** Challenges of docs and plan first. Read current state only through A3
reads Cecilia approves; write down repo-vs-reality drift. List what the docs do not settle (limits,
replicas, retention, timeouts, alert thresholds, who is paged) as questions.

**Y3 — Infra brief · 🛑 G2.** Files to change, what would be applied where, blast radius, rollback,
recovery check, cost delta, secret **names**, and the `cecilia-scope` block.

**Y4 — Build (A2).** Confirm the scope is active; write the files (`code-quality.md`); commit each step.
Each edit to an `infra`-profile path asks (guard); expect the prompt, never route around it.

**Y5 — Static gate.** Pipeline linters, Dockerfile lint, schema validation, `helm lint`+`template`,
`terraform fmt -check`+`validate`, secret scan on the diff. Missing tool → `[unverified]`, never passed.

**Y6 — Apply to non-prod · 🛑 A3 per action.** Quote → yes → run → record. Then prove: the service
answers a real request; **the rollback was run and worked**; logs and metrics arrive. Any ❌ → quote the
rollback, report, ask.

**Y7 — Check and hand off · 🛑.** Ask for `cecilia-review` mode=infra before anything reaches another
environment. Rebase, re-run Y5, PR text from `assets/pr-draft-template.md` into
`tensura/reports/<TASK>/pr-body.md`, update the infrastructure doc from `assets/infrastructure.md`. Run
`scripts/cecilia_check.py --task <TASK>` and quote its summary line. Full report to
`tensura/reports/<TASK>/devops.md`; chat/return ≤ 15 lines; update `tensura/tasks/<TASK>/state.md`. Push, Draft PR
and every apply are Cecilia's (local-only, `git-handoff.md` §1): write the exact commands in the report — the push,
`gh pr create --draft … --body-file tensura/reports/<TASK>/pr-body.md`, and each apply with its verification and
rollback. Agents never push, open a PR, comment on a host or deploy.

**Y8 — Release hand-off.** For production: fill `assets/release-packet.md`, request
`cecilia-review` mode=verify on it, present G4. Cecilia triggers the protected pipeline. Afterwards,
with read-only telemetry she provides, report observed health against the abort thresholds and
recommend — never act.
