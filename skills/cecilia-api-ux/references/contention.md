# Contention — when correctness turns into rejection

Anything many users change at once is a **hot key**: stock of a flash-sale item, a voucher with limited uses,
a seat, a wallet balance, a counter, a unique username being claimed. The mechanism protecting it decides what
users see under load.

## 1. Measure the exposure

For each hot key: peak writes/s **on that key** (not on the endpoint) and the window between reading the state
and writing it (read → check → write, including network hops and business logic).

`capacity.py contention --rps-per-key 0.2,5,50 --window-ms 40 --retries 1`

P(conflict per attempt) ≈ 1 − e^(−λ·w). Serialised ceiling ≈ 1000 ÷ w(ms) commits/s per key.

| Rejection users see at peak | Verdict |
|---|---|
| ≤ 1 % | fine — make the retry and the message right (§3) |
| 1–10 % | SHOULD-FIX — shorten the window, retry server-side, or change mechanism |
| > 10 % or ceiling < peak | BLOCKER for that task — change mechanism (§2) |

## 2. Mechanisms (compare on the same criteria; Cecilia picks)

| Mechanism | Conflicts | Ceiling per key | Complexity | Fits |
|---|---|---|---|---|
| Optimistic lock (version check, 409) | 1 − e^(−λw) | ≈ 1000/w | low | rarely-contended records (profiles, drafts) |
| Conditional atomic update (`UPDATE … SET qty = qty − 1 WHERE qty ≥ 1`) | none from ordering; fails only when truly sold out | high (row lock held ms) | low | counters, stock, quotas |
| Pessimistic lock (`SELECT … FOR UPDATE`) | waits instead of failing | ≈ 1000/lock-hold | medium; deadlock risk | multi-row invariants in one DB |
| Reservation with TTL (hold → confirm/expire) | none; users see "reserved for 10 min" | high | medium | checkout, seats, limited vouchers |
| Queue / single writer per key | none; latency grows with backlog | the worker's rate | high | extreme bursts, fairness needed |
| Sharded counter (N sub-counters) | spread by N | N × single | medium | very hot counters, approximate reads OK |

Measure the chosen one again with the same inputs; show before → after.

## 3. The retry and the message (every mechanism needs these)

- Server-side retry for conflicts the user cannot resolve (another buyer changed stock): bounded, jittered.
- Only **idempotent** operations are retried; POSTs that create or charge need an Idempotency-Key.
- A 409 the user must resolve says what changed and keeps the user's input (`"price changed from … to …"`).
- A 409 / 429 a client can retry carries `Retry-After`.
- Sold out is not a conflict: a clear business error the UI can show.

## 4. Where to look in code

Version columns and `@Version`/`version` checks, `WHERE version = ?` updates, unique constraints hit by
`INSERT`, `SELECT … FOR UPDATE`, read-modify-write in application code (read stock, compute, save), counters
updated from several services.

## 5. Measuring on localhost (A3 — ask first)

Seed one hot key locally, replay the peak with k6/wrk/`hey` against the local server at the projected rate for
60 s, count 409s/business errors and p95. Report measured next to projected. Never against shared or
production systems.
