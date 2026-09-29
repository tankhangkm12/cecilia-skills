# HLD → `tensura/docs/system/architecture.md`

Input: `idea.md`, `requirements.md`. The most expensive forks live here; everything later builds on them.

## Step 1 — Summary (≤ 15 lines)

Problem, key actors, scale, hard constraints, v1 scope, key NFRs. Ask if correct.

## Step 2 — Seven forks (≈ 7–10 questions, one per turn)

Each with options table, thresholds ("at the scale you gave, option X starts to hurt when…"), researched
sources, recommendation. See `references/backend/architecture-options.md`.

1. **Overall architecture** — monolith / modular monolith / microservices / serverless.
2. **Stack** — backend language + framework, frontend, database type, runtime/hosting. Neutral
   presentation; recommend from team skills and problem, not hype. Research current versions.
3. **Service/module boundaries** — split criteria, responsibility, **data ownership** (every dataset
   has exactly one owner).
4. **Communication** — sync (REST/gRPC) vs async (queue/event) per interaction, and why.
5. **Infrastructure components** — cache, queue, object storage, search, scheduler. Each must name
   the concrete flow that needs it; every component is operated forever.
6. **Authentication & authorization** — mechanism, permission model (role/permission/resource), token
   lifecycle, and **how the server identifies the user on session refresh** when the access token has
   expired (common gap).
7. **NFR mechanisms** — how each NFR from the SRS is met (latency, peak load, availability, backups per
   data store with RPO/RTO, retention, logging/monitoring).

## Step 3 — Proposal tables (prepare, then ask Cecilia to approve/edit, one question each)

**Security**

| Area | Proposal | Why |
|---|---|---|
| Resource-level permission (user A requests B's resource) | | |
| Personal data at rest | | |
| Secret management | | |
| Uploads (types, max size, scanning, storage) | | |
| Never-log fields | | |
| Rate limits | | |

**Operations**

| Item | Proposal |
|---|---|
| Environments (dev/staging/prod, shared DB?) | |
| Config & secret injection | |
| Migrations under live traffic + rollback path | |
| App rollback | |
| Health checks & alerts (who is notified) | |
| Environments needed and what each must provide (fills §10) | |
| Config and secret **names** the flows require (names only) | |

**Screens** (skip for APIs/pipelines): `# · screen · actor · data shown · actions`. From UI designs if
provided (say so), otherwise derived from UCs (say it is derived). Screens reveal forgotten endpoints:
filters, empty/loading states, admin screens.

## Step 4 — ASCII architecture diagram (mandatory) + main data flow diagram

## Step 5 — Write from template. Record decisions.

## Exit gate

| # | Check | Result + evidence |
|---|---|---|
| 1 | Every dataset has exactly one owning service/module | |
| 2 | Every diagram arrow is in the communication table and vice versa | |
| 3 | Every infra component names the flow that needs it | |
| 4 | Every NFR from SRS has a mechanism with a number | |
| 5 | Every data store has a backup row with RPO/RTO | |
| 6 | Session refresh: user lookup data is stated | |
| 7 | Every FR maps to a service/module | |
| 8 | Every screen is served by ≥ 1 service | |
| 9 | Every technology choice cites a source + version | |
| 10 | Every environment in §10 states what it must provide and who may deploy to it | |
| 11 | Every row of the delivery-expectations table traces to an NFR, a flow or a section — no orphans | |
| 12 | Every config/secret the flows need is listed **by name only**; no value appears anywhere in the doc | |
