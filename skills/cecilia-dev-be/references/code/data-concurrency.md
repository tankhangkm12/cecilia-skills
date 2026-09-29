# Money, time, concurrency, idempotency

## 1. Money — never floating point
| Lang/DB | Use | Forbidden |
|---|---|---|
| TypeScript | integer minor units, or `decimal.js`/`big.js` (only if already a dependency or approved) | `number` with decimals |
| Python | `decimal.Decimal`, Pydantic `condecimal` | `float` |
| Java | `BigDecimal` created from String; or `long` minor units | `double`, `float` |
| PostgreSQL | `numeric(19,4)` or `bigint` minor units | `real`, `double precision`, `money` |
One representation for the whole project (docs decide) · column names state unit or have a currency column ·
rounding rule (where, digits, mode) comes from docs and lives in one place (`money.util`) · splits handle the
remainder so parts sum to the total · JSON carries money as string or minor-unit integer.

## 2. Time
Store UTC (`timestamptz`; Java `Instant`/`OffsetDateTime`; Python aware `datetime.now(UTC)`; TS ISO with `Z`) ·
APIs return ISO-8601 with offset · pure dates use `date`, never a timestamp · convert to local time only in
presentation · business periods ("revenue of 30 Aug VN time") converted to UTC bounds in the application
layer with explicit names (`fromUtc`, `toUtc`) · inject a Clock, never call `now()` in business logic ·
"+1 day" ≠ "+24h" across DST.

## 3. Race & duplicate patterns to recognise
Lost update (read-compute-write without lock/version) · double submit · check-then-act · at-least-once
reprocessing (consumers, webhooks, overlapping cron) · oversell (`SUM < limit` then insert) · deadlock
(different lock order). The LLD should name the mechanism; if it does not → `workflows/solution-options.md`.

## 4. Mechanisms (implement the one the docs chose)
| Mechanism | Implementation notes |
|---|---|
| Unique constraint | natural key; catch the violation in the adapter → ConflictException with errorCode |
| Atomic update | `UPDATE … SET qty = qty - :n WHERE id = :id AND qty >= :n`; 0 rows → business error |
| Optimistic lock | `version` column in WHERE; 0 rows → 409 / bounded retry per docs |
| Pessimistic lock | `SELECT … FOR UPDATE` inside a short transaction; lock rows in a fixed order |
| Distributed lock | only if approved infra; TTL > work time; fencing token |
| Serialize by key | queue partition by entity id |
| State guard | `UPDATE … WHERE status = 'PENDING'`; 0 rows = already processed |
| Idempotency-Key | see `api-contract.md` §4; record in the same transaction |
| Dedupe table | consumers: insert `eventId` in the same transaction as the work; duplicate → skip |
| Outbox | write data + outbox row in one transaction; separate publisher marks `published_at`; consumers idempotent |

Traps: lock taken after the read · transaction spanning HTTP/queue calls · retries without backoff/limit or
on non-idempotent operations · TTL shorter than processing. Second-call behaviour (200 with old result vs
409) is a business decision from docs — never pick it yourself.

## 5. Transactions
Scope decided by the service/use case (not repository, not controller) · as short as possible · no
external calls inside · events/mails via outbox after commit · Java: `@Transactional` on services,
`readOnly` for reads, beware self-invocation; Python: unit of work; Node: a transaction manager wrapper
passing a context to repositories.
