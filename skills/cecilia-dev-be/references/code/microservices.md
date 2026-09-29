# Microservices (only when HLD chose them)

Communication channel is always per HLD; missing → ask (Kafka / RabbitMQ / NATS / gRPC / REST via gateway / TCP).

## 1. Repo layout
```
project/
├── docker-compose.yml          local full system
├── libs/                       THIN shared code
│   ├── contracts/              event schemas, proto, cross-service DTOs
│   ├── common/                 envelope, AppException, error codes, request context
│   └── observability/          logger, tracing, metrics
└── apps/
    ├── api-gateway/
    └── <name>-service/
        ├── src/ modules/<feature>/ (same as monolith) · infrastructure/{messaging,clients,persistence,config}
        ├── Dockerfile
        └── <manifest>
```
`libs/` never holds business logic or shared entities — editing it must not force redeploying five services.

## 2. Invariants
1. Own database per service; no reads/writes into others' databases.
2. No distributed transactions/2PC; eventual consistency via events + saga.
3. Every consumer idempotent (messages will be redelivered).
4. Every sync call: timeout + circuit breaker + explicit fallback; no deep chains; never inside a DB transaction.
5. requestId/traceId across every channel.
6. Events additive only; breaking → new `eventVersion` in parallel.
7. DB write + publish = outbox; never publish inside the DB transaction.

## 3. Publisher behind a port
Business code knows `EventPublisherPort.publish(event)`. Kafka adapter: topic = eventType, key = aggregate id
(ordering per aggregate), headers `x-request-id`, `x-event-id`.

## 4. Outbox
Table: `id, aggregate_id, event_type, event_version, payload, request_id, created_at, published_at, retry_count`.
Step 1 in transaction: save data + enqueue outbox. Step 2 worker: publish unsent → mark published (at-least-once).

## 5. Consumer
Restore requestId from headers → skip if `eventId` already in `processed_events` → do work and mark processed
in one transaction → retries with backoff → unrecoverable (schema invalid) straight to DLQ → DLQ size metric,
lag metric.

## 6. Sync client
Port in business language (`UserLookupPort.getBasicInfo`), adapter with timeout (e.g. 3s), requestId header,
not-found → null/Optional, other failures → `ExternalServiceException('USER_SERVICE_UNAVAILABLE')`, circuit
breaker, fallback (cached/partial/clean 503).

## 7. Saga
Choreography for simple flows, orchestration for complex; every step has a defined compensation; saga state
persisted; timeouts for stuck sagas; draw the flow and get Cecilia's approval before coding if the LLD lacks it.

## 8. Gateway
Only external entry: routing, token verification, rate limit, requestId, CORS, optional aggregation; no business
logic; passes identity downstream as a signed internal token, not raw headers.

## 9. Observability & lifecycle
OpenTelemetry tracing mandatory; logs carry service/requestId/traceId/eventId; metrics per service (rate,
latency, errors, lag, DLQ, breaker open rate); liveness without DB, readiness with deps; graceful shutdown;
images tagged by commit SHA/semver, never deploy `latest`.
