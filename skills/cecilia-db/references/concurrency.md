# Concurrency, isolation and hot rows

## 1. Isolation — know the default and what it allows

| Engine default | Allows | Typical surprise |
|---|---|---|
| PostgreSQL READ COMMITTED | non-repeatable reads, write skew | check-then-insert races; use constraints, `SELECT … FOR UPDATE`, or SERIALIZABLE with retries |
| MySQL InnoDB REPEATABLE READ | phantom-safe reads via gap/next-key locks | lock waits and deadlocks on range updates; consistent snapshot hides concurrent commits |
| MongoDB (single document atomic; multi-document transactions snapshot) | cross-document races outside transactions | transaction lifetime/size limits, retries on TransientTransactionError |
| Distributed SQL (often SERIALIZABLE) | none of the anomalies | client-side retries required, higher latency |

State per invariant how it is protected: constraint, row lock, conditional update, serializable transaction,
or single writer.

## 2. Hot rows / keys

Quantify with `capacity.py contention` (writes/s on the same key × window). Options and their ceilings:
`cecilia-api-ux` `contention.md` §2 (optimistic lock, conditional atomic update, pessimistic lock, reservation,
queue, sharded counter). Prefer the database's atomic conditional update for counters and stock.

## 3. Deadlocks

Lock rows in a consistent order; keep transactions short (no network calls inside); index the columns used in
`WHERE` of updates (otherwise range/next-key locks widen); retry deadlock victims (bounded).

## 4. Queues in the database

`SELECT … FOR UPDATE SKIP LOCKED` (PostgreSQL, MySQL 8) for worker queues; one status column + index; batch
sizes small; outbox table for events (microservices-data.md).

## 5. Idempotency storage

Idempotency-Key table: key UNIQUE, request hash, response, created_at, TTL/cleanup job. The unique insert is the
lock; a replay returns the stored response.
