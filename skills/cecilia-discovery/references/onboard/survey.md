# Survey — wide and shallow, before anything deep

Goal of K2: know what exists, what talks to what, and **what you could not find**. Cheap, mechanical,
and it changes what is worth reading deeply. Do not start reading business logic before this is done.

## 1. What to inventory

| # | Look for | How you usually find it | Records |
|---|---|---|---|
| 1 | Entry points | `main`, `index`, `app`, framework bootstrap, `Dockerfile` CMD, CI deploy targets | how many deployables exist — often more than expected |
| 2 | HTTP surface | router/controller registrations, OpenAPI file if any, gateway config | route · method · handler · auth? |
| 3 | Async surface | consumers, subscribers, listeners, topic/queue names | topic · consumer · what it does |
| 4 | Scheduled work | cron definitions, scheduler registrations, infra cron, k8s CronJob | schedule · job · what it touches |
| 5 | Persistence | migrations, ORM entities/models, raw SQL, and **the live schema if allowed** | table · owner module · rough size if known |
| 6 | Outbound calls | HTTP clients, SDKs, partner base URLs in config | who we call · where from · timeout? retry? |
| 7 | Config & secrets | `.env*`, config modules, k8s manifests, CI variables | key names only, **never values** |
| 8 | Dependencies | manifest + lockfile | name · version · last release · EOL? |
| 9 | Tests | test folders, CI test steps, coverage output if produced | which areas have tests, which have none |
| 10 | Git signal | `git log --since=1.year --name-only`, churn per path, last touch per module | what is alive, what is frozen |

Every row is mechanical. Anything against a running system is A3 — quote it and ask (SKILL.md "Authority for this role").

## 2. The system map — the deliverable of this step

An ASCII diagram plus three tables. The third one is the reason this step exists.

```
[client] → [api-gateway] → ┬→ [order-svc] ──→ (orders db)
                           ├→ [payment-svc] ─→ (payments db) ──→ {partner X}
                           └→ [?? admin-ui] — no entry point found
                                   [order-svc] → «orders.created» → [notify-svc]
                                                                  → «orders.created» → ?? (no consumer found)
```

**A. Components** — name · kind (service, job, ui, library) · deployable? · where its code lives ·
last touched.
**B. Connections** — from · to · channel (sync/async/db) · evidence (file where the call is made).
**C. Not found** — the column people skip and then regret:

| Thing | Expected because | Could not find | Meaning (labelled) |
|---|---|---|---|
| consumer of `orders.created` | it is published in `order.service.ts:88` | no subscriber in this repo | `[unknown]` — another repo, or an event nobody listens to |
| entry point for `admin/` | the folder exists with controllers | not registered anywhere | `[unknown]` — dead, or wired dynamically |
| migrations for `audit_log` | the table is queried in `audit.repository` | no migration creates it | `[unknown]` — created by hand, or by another system |

A "not found" is never silently dropped and never called "unused" (`evidence.md` §6).

## 3. Sizing the deep pass

After the map, propose to Cecilia — one question — what to document deeply, with the reason:

- what she is about to change (from K1: why she needs this)
- what touches money, state machines or customer data
- what has no tests and high churn — where a change will break something quietly
- what everything else depends on

And say plainly what will stay at survey depth. A document that claims a depth it does not have is
the failure mode of this whole skill.

## 4. Repo-shape traps worth checking early

Monorepo with several deployables · generated code committed (do not document it as hand-written) ·
vendored dependencies · more than one framework generation in the same repo (an old and a new module
layout, both live) · a second, older copy of the same service under a different folder · feature flags
that change the flow at runtime · environment-specific branches. Each of these silently doubles the
work if found at K4 instead of K2.
