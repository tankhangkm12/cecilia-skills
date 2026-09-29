# Connections, pools and timeouts

Every database has a hard connection limit, and each connection costs server memory (a whole process per
connection in PostgreSQL, a thread in MySQL). An application without a bounded pool — or with a pool per
request — fails under load with "too many connections" long before CPU runs out.

## 1. The budget — write it in the database doc §9

Compute it, do not estimate it: `scripts/capacity.py connections …` for server RAM and
`scripts/capacity.py throughput …` for busy connections per instance (`numbers.md`).

```
Σ over consumers (instances at peak × pool max per instance)
  + background workers + scheduled jobs + migrations + admin/monitoring reserve
  ≤ server connection limit × ~0.8
```

- **Instances at peak** means the autoscaler's maximum, not today's count. Ten pods × pool 20 = 200.
- Serverless functions: every warm instance holds its own pool — use pool size 1–2 plus a pooler/proxy.
- The server limit is PostgreSQL `max_connections` or MySQL `max_connections`; raising it costs memory
  per connection and is an engine decision (`engine-tuning.md`), not the first fix.

## 2. Pool size — small, then measured

More connections than the database can run in parallel only adds queueing inside the database. A
widely used starting point (HikariCP "About Pool Sizing") is `connections ≈ (CPU cores × 2) + effective
disk spindles` **for the whole database**, divided across instances. Treat it as a start; measure pool
wait time and database active sessions under load, then adjust. Use a fixed-size pool (min = max) for
steady services.

## 3. Client pool settings by stack

| Stack | Where | Settings to set explicitly |
|---|---|---|
| Java / Spring (HikariCP) | `spring.datasource.hikari.*` | `maximum-pool-size`, `minimum-idle` (= max), `connection-timeout` (wait for a free connection), `max-lifetime` (a little shorter than any server/proxy/firewall idle cut), `keepalive-time` |
| Python / SQLAlchemy | `create_engine` / `create_async_engine` | `pool_size`, `max_overflow`, `pool_timeout`, `pool_recycle`, `pool_pre_ping=True` |
| Node / node-postgres | `new Pool({...})` | `max`, `idleTimeoutMillis`, `connectionTimeoutMillis` |
| Node / Prisma | connection URL | `connection_limit`, `pool_timeout` |
| Node / TypeORM | `extra` passed to the driver | driver pool max (`max` for pg, `connectionLimit` for mysql2) |
| Node / mysql2 | `createPool({...})` | `connectionLimit`, `queueLimit`, `waitForConnections` |

Defaults differ by library and version — read them from the library's docs for the version in the repo
and write the chosen values into config, never rely on an unstated default. One pool per process,
created at start-up and shared; never a pool or client per request.

## 4. Poolers and proxies

| Option | When | Watch out for |
|---|---|---|
| PgBouncer (transaction mode) | many app instances, PostgreSQL | session features break across transactions: `SET`, session advisory locks, `LISTEN/NOTIFY`, temp tables; prepared statements need PgBouncer's protocol-level support or the driver's statement cache off — check both versions |
| RDS Proxy / cloud proxies | managed DB, serverless | pinning (a session that cannot be shared) removes the benefit — know what pins |
| ProxySQL | MySQL, read/write split | query rules are code: version them |

Adding a pooler is an infrastructure change (`cecilia-devops`) and a decision for Cecilia.

## 5. Timeouts — every layer has one

| Timeout | PostgreSQL | MySQL | Why |
|---|---|---|---|
| Statement | `statement_timeout` | `max_execution_time` (SELECT only, ms) or client-side | a runaway query cannot hold a connection forever |
| Lock wait | `lock_timeout` | `innodb_lock_wait_timeout` (rows), `lock_wait_timeout` (metadata — default is very long) | a DDL or update gives up instead of queueing everyone behind it |
| Idle in transaction | `idle_in_transaction_session_timeout` | `wait_timeout` (idle connection) | a forgotten open transaction does not hold locks and block cleanup |
| Pool acquire | client pool setting | client pool setting | the app fails fast and visibly instead of hanging |

Set them per role or per session for the app (`ALTER ROLE app SET statement_timeout = '5s'`), longer for
migrations and reporting roles. The app's request timeout must be longer than the pool acquire timeout
plus the statement timeout, or the caller gives up while the database still works.

## 6. Other pools the backend holds

The same rules apply to every long-lived client: one Redis client/pool per process, one HTTP client with
keep-alive per upstream (e.g. one reused `httpx.AsyncClient`, one Node `Agent` with `keepAlive`), a
broker connection with channels per worker. Bounded size, explicit timeouts, created once. Wiring them
is `cecilia-dev-be`'s code; the numbers belong in the database doc §9 when they touch the database, or in
the infrastructure doc otherwise.

## 7. Symptoms and first checks

| Symptom | First check |
|---|---|
| "too many connections" / "remaining connection slots are reserved" | the budget in §1 at peak instances; leaked connections (pool metrics: in use never returns to 0) |
| requests hang then time out, DB CPU low | pool acquire wait; a long transaction holding a lock (`pg_stat_activity` / `sys.innodb_lock_waits`) |
| sporadic "connection reset" after idle | `max-lifetime` / `pool_recycle` longer than a proxy/firewall idle cut |
| errors only behind PgBouncer | a session feature from §4 |
