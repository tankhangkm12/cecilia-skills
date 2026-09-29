# Architecture inside the codebase

Follow the architecture in HLD/LLD. Not specified and repo gives no answer → ask (options below).

## 1. Levels
**Level 1 — feature-modular** (CRUD, thin logic)
```
src/modules/<feature>/
├── <feature>.controller.*   receives request, no logic
├── <feature>.service.*      business logic, transaction scope
├── <feature>.repository.*   port + adapter, ORM hidden
├── dto/                     validated input/output
├── entities/
└── <feature>.module.*       wiring
```
**Level 2** — adds `domain/` (entities, value objects, pure rules without framework).
**Level 3 — clean/hexagonal** (complex domain)
```
src/modules/<feature>/
├── domain/          entities, value objects, domain services, events, PORTS
├── application/     use cases, commands, transaction boundary
├── infrastructure/  ADAPTERS: persistence (ORM entities, mappers), gateways, messaging
└── presentation/    controllers, request/response DTOs
```
Dependency rule: presentation → application → domain; infrastructure → domain. Domain imports no
framework, no ORM. Domain entity ≠ ORM entity (joined by a mapper) — the price of level 3.

Raise the level (propose, ask) when ≥ 2 signals: state machine · rules to test without DB · multiple
sources for one concept · invariants across an aggregate · rich domain language.

## 2. Layer responsibilities
| Layer | Does | Must not |
|---|---|---|
| Controller/router | parse/validate request, call service, return plain data | business logic, DB access, try/catch formatting, building the envelope |
| Service/use case | business logic, orchestration, transaction scope | know ORM, HTTP objects, SDKs |
| Repository | data access behind a port | business logic, opening transactions |
| Adapter | call SDK, map data, translate errors, timeout/retry, log | business logic |
| DTO | shape + validation | logic |
| Entity | data model | be returned as a response or bound from a request |

## 3. Shared application infrastructure (monolith)
```
src/
├── common/            no business logic of any module
│   ├── exceptions/    AppException tree
│   ├── errors/        error-code catalog (single source)
│   ├── context/       request context (requestId)
│   ├── filters|handlers/  global exception handler
│   ├── interceptors|middleware/  envelope, request logging
│   └── dto/           envelope, paged response
└── infrastructure/
    ├── config/        validated config, one entry point
    ├── logging/       AppLogger port + adapter (redaction)
    ├── database/      datasource, base entity, transaction manager, migrations/
    ├── cache/ http/ storage/ messaging/   ports + adapters, outbox
```

## 4. Monolith rules
- Modules isolated as if they could be split later (`module-boundaries.md`).
- ACID transactions are the monolith's advantage: use them; keep them short; never call external APIs inside.
- Events/mail/webhooks after commit via outbox, even in a monolith.
- One database, schema per module where the DBMS allows; migrations always, never auto-sync; each
  migration has a working rollback; index FKs and frequent filter/sort columns; soft delete filtered in repositories.
- Base classes stay thin: `BaseEntity` (id, timestamps, deletedAt), small `BaseRepository`, `AppException`,
  `AppLogger`, `AppConfig`, envelope builder. Never `BaseService` with generic logic, `BaseController`
  with generic CRUD, or catch-all helpers.

Microservices → `microservices.md`.
