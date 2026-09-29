# Scaffold — new project, service or module

Build from HLD/LLD. Everything not in docs is asked (grouped gates).

## 1. Decisions to confirm before creating anything

New module vs inside an existing one (same aggregate / same change cadence → existing) · architecture
level (`code/architecture.md`) · for a new project the **stack as a set**, asked as ONE question with
2–3 complete bundles (framework + ORM + migrations + package manager + runtime version + lint/format),
each researched and with a recommendation — never six separate fragments and never six at once ·
monolith vs microservices if HLD is silent (never assume microservices) · communication channel for
microservices · repo layout (mono/poly repo) · CI/Docker needed now or later.

## 2. Build order — vertical slice, not horizontal layers

1. Skeleton that runs: config module (validated, fail fast), wrapped logger, request context
   (requestId), envelope + global error handler, error-code catalog, health endpoints, lint/format config
   agreed with Cecilia.
2. One complete thin slice for the first planned ID end to end (endpoint → service → port → adapter →
   DB migration), verified manually.
3. Then the remaining IDs of the batch.

Minimum skeleton per module: public facade/port + DTOs · service/use cases · repository port + adapter ·
mapper · module wiring · migrations. Nothing speculative (no empty folders for "later", no generic
base services, no unrequested README/docs/examples).

## 3. Day one vs later

Day one: what the batch IDs need + the skeleton above. Later (propose, do not build): caching,
queues, search, dashboards, extra environments — unless docs require them now.

## 4. Checks

- Runs locally with documented commands; health endpoints answer.
- Config missing → app refuses to start with a clear message.
- No business code imports SDKs/ORM directly; module boundaries enforced (index/exports/package-private).
- Lint/format pass; existing tests (if any) green.
