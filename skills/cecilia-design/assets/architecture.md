# Architecture (HLD) — <project>

> Updated: <YYYY-MM-DD> · Inputs: `idea.md`, `requirements.md`

## 1. Architecture diagram
```
<ASCII>
```
## 2. Services / modules
| Service | Responsibility | Data OWNED | Depends on | Called by | FRs |
|---|---|---|---|---|---|
## 3. Stack
| Layer | Technology + version | Why | Considered & rejected | Sources |
|---|---|---|---|---|
## 4. Screens *(skip if no UI)*
| # | Screen | Actor | Data shown | Actions | FRs |
|---|---|---|---|---|---|
## 5. Main data flows
```
<ASCII>
```
## 6. Communication
| From | To | Sync/async | Protocol / topic | Why |
|---|---|---|---|---|
## 7. Infrastructure components
| Component | Purpose | Flow that needs it |
|---|---|---|
## 8. Authentication & authorization
| Item | Decision |
|---|---|
| Mechanism | |
| Permission model | |
| Token/session lifecycle | |
| Refresh: server identifies user from | |
## 9. Security
| Area | Decision | Why |
|---|---|---|
## 10. Operations
| Item | Decision |
|---|---|

### Environments required *(described by what they must provide; the delivery owner assigns `ENV-nn`)*
| Environment | Purpose | Must provide (data, dependencies, access) | Who may deploy to it | Production-like in |
|---|---|---|---|---|
| dev | local/integration work | seeded fake data, stubbed payment | any role | schema only |
| staging | pre-release verification, perf and E2E runs | anonymised data, real broker, sandbox payment | delivery owner, with approval | topology, versions |
| production | live | — | Cecilia only | — |

### Delivery expectations *(inputs the infrastructure document and the plan's OPS rows consume)*
| Item | Expectation | Traces to |
|---|---|---|
| Deploy unit(s) | <service → image/artifact> | §2 |
| Zero-downtime required? | yes/no, and what a user sees if not | NFR-nn |
| Rollback expectation | what must be undoable, and how fast | NFR-nn |
| Migration constraints | must run before/after code, reversible? | §4 (DB stage) |
| Config & secret **names** needed | `ORDER_TTL`, `PAYMENT_API_KEY` (names only, never values) | flows in §5 |
| Runtime dependencies to provision | DB, cache, broker, object storage, cron | §7 |
| Health signal | what "healthy" means for each service, and the check that proves it | §7 |
| Alert-worthy failures | the conditions somebody must be woken for, and who | NFR-nn |
| Scale & cost envelope | expected load, ceiling that must not be crossed silently | NFR-nn |
## 11. NFR mechanisms
| NFR | Target | Mechanism |
|---|---|---|
### Backups — one row per data store
| Store | Method | RPO | RTO | Verified by |
|---|---|---|---|---|
## 12. Doubts
| # | Problem | Consequence if kept | Alternative | Trade-off |
|---|---|---|---|---|
## 13. Assumptions & risks
| # | Content | Impact if wrong | Who confirms |
|---|---|---|---|
