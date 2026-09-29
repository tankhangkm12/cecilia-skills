# CORE flow options (any non-CRUD operation)

Run for every CORE operation before describing it. One question per operation (if an operation has
two independent forks, e.g. algorithm and duplicate protection, ask them as two turns).

## Question template

```
**[cecilia-design · Stage 3 · LLD order] Q5/~9 — Place order: how to hold stock**

Understanding: <1–2 sentences, FR/BR IDs>

**Option A — <name>**
1. <step: DB write / external call / transaction start-end>
2. ...
Gain: ... · Cost: ... · Needs: <existing stack | new component → hard stop> · Sources: ...

**Option B — <name>** (same shape)

| Risk spot | How it breaks | Named mechanism per option |
|---|---|---|
| step 3 decrement | two requests → negative stock | A: atomic update · B: optimistic lock |

Data & states: <new tables/columns/states; what is snapshotted>
I lean to A because <project-specific reason>. Reply A/B or your own.
```

Rules: ≥ 2 real options · every race/duplicate spot has a **named** mechanism · external calls never
inside a DB transaction · new infrastructure is a hard stop and needs an option using only existing stack.

## Race & duplicate failure patterns

| Failure | Code smell |
|---|---|
| Lost update | read → compute → write, no lock/version |
| Double submit | POST create/pay, client retry, no natural key |
| Check-then-act | `if status == PENDING then update` |
| Reprocessing (at-least-once) | queue consumers, partner webhooks, overlapping cron |
| Oversell / limit breach | `SUM() < limit` then `INSERT` |
| Deadlock | several tx locking rows in different orders |

## Concurrency menu (propose in this order; go up only when the previous fails, say why)

| Mechanism | How | Fits | Cost |
|---|---|---|---|
| Unique constraint | DB rejects duplicates via natural key | duplicate records | map violation to error code |
| Atomic update | `UPDATE stock SET qty=qty-? WHERE id=? AND qty>=?` | simple decrement | add/subtract only |
| Optimistic lock | `version` column, 0 rows = conflict | rare contention | retry/409 handling |
| Pessimistic lock | `SELECT … FOR UPDATE` in tx | frequent contention, short sequences | holds connections, deadlock risk |
| Distributed lock | Redis/ZooKeeper + TTL + fencing token | multi-instance, beyond one DB | new infra; TTL expiry trap |
| Serialize by key | queue/partition by entity id | ordering matters, async OK | new infra, no immediate result |
| Serializable isolation | raise isolation level | low volume, correctness first | many rollbacks, needs retry |

## Idempotency menu

| Mechanism | For | Note |
|---|---|---|
| Idempotency-Key header | POST create/pay | store (key, endpoint, body hash) → response with TTL; same key + different body → 409 `IDEMPOTENCY_KEY_REUSED`; in-flight → 409 `REQUEST_IN_PROGRESS`; record in the same tx as the side effect |
| Natural key + unique index | order per (user, cart), partner transaction id | cheapest |
| Dedupe table by eventId | message consumers | insert first, skip duplicates, plus DLQ |
| State machine guard | transitions | `UPDATE … WHERE status='PENDING'`; 0 rows = already done |
| Outbox | DB write + publish | never publish inside the tx |

Whether the second call returns 200 (old result) or 409 is a **business decision** — ask.

## Traps to mention when relevant

Lock taken after reading · transaction spanning HTTP/queue calls · inconsistent lock ordering · TTL
shorter than work · retries without backoff/limit or on non-idempotent ops · tests only on happy path
(require "same input twice" and "two parallel actors" cases in stage 6).
