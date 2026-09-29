# Data across services

| Pattern | Use when | Cost |
|---|---|---|
| **Database per service** | services owned by different teams/lifecycles | no cross-service joins or transactions |
| **Shared database** (one schema per service) | early stage, one team | coupling; migrations coordinated |
| **Transactional outbox** | a service must change its data *and* publish an event reliably | outbox table + relay (polling or CDC) |
| **CDC** (Debezium, logical replication, change streams) | feed search/analytics/read models without dual writes | infra to run; schema changes propagate |
| **Saga** (orchestrated or choreographed) | a business transaction spans services (order → payment → stock) | compensations for every step; visible intermediate states |
| **Read model / CQRS** | screens need data from several services | eventual consistency window to state and show |
| **API composition** | small joins across two services | latency adds up; partial failure |

Rules:
1. Never write to two databases in one request without outbox/saga — one of the writes will be lost someday.
2. Every event has an id and is processed idempotently (dedupe table or natural idempotency).
3. State the consistency window the user can see (e.g. "order appears in history within 2 s") and what the UI
   shows meanwhile (cecilia-api-ux latency-failure.md §4).
4. Reference data owned elsewhere is copied as a read model with its source and refresh rule, never edited.
