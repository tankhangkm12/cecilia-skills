# Architecture options (stage 2 and stage 3 structure)

Present these as options; Cecilia decides. Research current versions/limits before quoting them.

## 1. System shape

| Option | Fits when | Starts to hurt when |
|---|---|---|
| Monolith | tiny team, simple domain, fast v1 | many devs step on each other; parts need different scaling |
| **Modular monolith** (Cecilia's usual recommendation for new projects) | one deployable, clear module boundaries, ACID transactions | a module needs independent scaling/release/tech |
| Microservices | independent scaling, several teams, different tech, different availability or release cadence | small team; no tracing/ops maturity; distributed transactions everywhere |
| Serverless | spiky low-volume workloads, event glue | long-running work, cold-start-sensitive latency, vendor lock-in |

Split to microservices only on real signals: one part needs very different scaling · teams blocking
each other · different tech required · different availability · forced different release cycles.
With strict module boundaries a later split is days, not a rewrite.

## 2. Structure level inside a module/service

| Level | Structure | Use when |
|---|---|---|
| 1 Feature-modular | controller → service → repository, dto, entities per feature | CRUD, thin logic |
| 2 + domain | adds `domain/` (entities, value objects, pure rules) | rules multiply |
| 3 Clean/Hexagonal | domain (entities, ports) · application (use cases, tx boundary) · infrastructure (adapters) · presentation | complex domain |

Level 3 dependency rule: presentation → application → domain; infrastructure → domain (implements ports);
domain imports no framework/ORM. Suggest raising the level when ≥ 2 signals: state machine · rules that
need testing without DB · multiple sources for one concept · invariants over a cluster (aggregate) ·
domain language beyond CRUD.

## 3. Communication

| Channel | Fits | Warning |
|---|---|---|
| Kafka | event streams, replay, many consumer groups, high throughput, per-key ordering | heavy ops; overkill for small systems |
| RabbitMQ / NATS | commands/events, flexible routing, small–mid systems | no Kafka-style replay |
| gRPC | low-latency internal sync calls, strict contracts | temporal coupling |
| REST via gateway | external clients; simple internal calls | not for async flows |
| TCP transport | small internal systems on one network | weak tooling |

Default proposal: async events; sync only when the caller needs the answer to respond to its client.
Every sync call needs timeout + circuit breaker + fallback; no deep chains (A→B→C→D).

## 4. Microservices invariants (state them in the HLD when chosen)

Own database per service · no distributed transactions (events + saga with compensations, saga state
persisted) · idempotent consumers + DLQ with metrics · outbox for "write DB + publish" · requestId/
traceId across every channel · events are additive; breaking change = new `eventVersion` in parallel ·
gateway has no business logic; internal services do not trust raw identity headers · shared libs hold
contracts/types only, never entities or business logic.

## 5. Data ownership & module boundaries

Every dataset has one owner. Consumers use, in order of preference: data already snapshotted locally
(values "at the time it happened": invoice name, price at purchase) → events → narrow facade/port →
wrapped sync call. Never: importing another module's internals, JOINs into its tables, shared entities
or migrations, touching another service's DB. A→B and B→A → wrong split: merge, invert with events, or
extract a named third module.

## 6. Infrastructure components

Each cache/queue/search/scheduler/object store must name the concrete flow needing it. Everything
external is designed behind an interface owned by the business side (port + adapter) so it can be replaced.
