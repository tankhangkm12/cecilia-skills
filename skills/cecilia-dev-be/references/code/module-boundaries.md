# Module & service boundaries — as few dependencies as possible

Why Cecilia is strict: **parallel work** (two people own two modules without waiting for each other)
and **maintainability** (a module exposing a narrow door can change its internals freely). Every new
dependency ties two people together; tie only when needed, with the thinnest thread.

## 1. Dependency ladder (pick the highest rung that works)
| # | Way | Coupling | When |
|---|---|---|---|
| 1 | Nothing needed — data already snapshotted locally | none | consider first |
| 2 | Event — B publishes, A listens and stores what it needs | very loose | A tolerates seconds of delay |
| 3 | Narrow facade/port published by B | loose | A needs data now |
| 4 | Wrapped sync network call (microservices) | medium | fresh data from another service is mandatory |
| 5 | ~~import B's service~~ | **forbidden** | |
| 6 | ~~import B's repository~~ | **forbidden** | |
| 7 | ~~JOIN/query B's tables or B's DB~~ | **forbidden** | |
| 8 | ~~shared entities, migrations or DB connection across services~~ | **forbidden** | |
About to do 5–8 → stop and propose a higher rung. Adding any new module-to-module dependency is an
architecture decision → ask.

## 2. One public door per module
Public: facade/port (only what others need) · facade DTOs (not entities) · event definitions ·
controllers (for external clients). Everything else is internal: services, repositories, entities,
mappers, private exceptions/constants, tables.

```ts
// ❌ order knows user's internals
constructor(private readonly userRepo: UserRepository) {}
// ✅ order asks one narrow question
constructor(private readonly users: UserFacade) {}
const customer = await this.users.getPurchasingProfile(dto.userId); // { id, tier, isActive }
```
Enforce the fence: Java package-private internals + ArchUnit test · TS `index.ts` exporting facade/DTOs
+ lint rule against deep imports · Python narrow `Protocol` facade + import-linter contracts. Adding such
a tool is a dependency → propose.

## 3. Microservices fences
Own DB per service, no exceptions ("just one SELECT" included) · shared `libs/contracts` holds only event
definitions/DTOs · prefer events; sync calls need timeout + circuit breaker + fallback · frequently needed
foreign data → local read copy updated by events.

## 4. Accept a little duplication for independence
Data **as of the moment it happened** (name/address on an invoice, price at purchase, FX rate at payment)
→ snapshot into your own table; it is your data. Data that must be **fresh** (balance, current
permissions, stock) → facade/API, no ad-hoc caching. Deliberate duplication is documented.

## 5. Breaking cycles (A needs B and B needs A)
1. They are one module → merge. 2. Invert with an event. 3. Extract a named third module (a real
business concept, not a `common/` bucket).

## 6. Smells to report (not to fix silently)
Small feature touches 3 modules · A imports B in > 5 places · facade with ~20 methods · two owners keep
hitting merge conflicts · unit-testing A requires half of B.

## 7. Checklist
- [ ] No import of another module's internal service/repository/entity
- [ ] No JOIN/query into another module's tables; no access to another service's DB
- [ ] Cross-module calls via narrow facade/port or events; facades return DTOs with only needed fields
- [ ] No import cycles
- [ ] "At that moment" data snapshotted
- [ ] New dependency proposed and approved
- [ ] Module unit-testable without other modules
