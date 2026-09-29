# <module> — module design (LLD)

> Updated: <YYYY-MM-DD> · Inputs: `architecture.md`, `requirements.md` · Stack: <lang, framework, DB, cache, broker> · Structure level: <1|2|3>

## 1. Scope
| Item | Content |
|---|---|
| Responsible for | |
| NOT responsible for | |
| Data owned | |
| Depends on / called by | |
| Screens depending on it | |
| FR/BR implemented | |

## 2. Operation classification
| Operation | FR/BR | CORE signals | Class |
|---|---|---|---|

## 3. Internal structure
```
HTTP → Controller → Service → Repository(port) → <DB adapter>
                       ├→ <Cache port>
                       └→ <Publisher port> → <topic>
```
| Component | Responsibility |
|---|---|

Tables *(details in `<unit>-database.md`)*
| Table | Key columns | Indexes needed |
|---|---|---|

## 4. CRUD operations
| Entity | Operation | Who (ownership condition) | Validation | Endpoint | Notes |
|---|---|---|---|---|---|

## 5. CORE operations
### 5.1 <name> — `METHOD /path` — trigger: <screen/API/event> — FR/BR: <IDs>
**Purpose & trigger**
**Chosen option** — Cecilia chose `<A>` (D-nn) · rejected `<B>` because <reason>
**Main flow**
```
Client        API          <Svc>        <Other>        DB
```
**State machine**
| State | Event | New state | Who may trigger |
|---|---|---|---|
**Errors & edge cases**
| Situation | System does | User sees |
|---|---|---|
| Out of stock / limit | | |
| External call timeout | | |
| Double click / retry | | |
| Two users on one record | | |
| Mid-flow failure / orphan data | | |
**Transactions & consistency**
| Item | Decision |
|---|---|
| Transaction scope | |
| Locks & type | |
| Accepted delay | |
| Compensation | |
**Sync vs background**
| Step | Now / background | Retry | Final failure goes to |
|---|---|---|---|
**Proposed code structure**
| Component | Responsibility (1 line) |
|---|---|

## 6. Constants & config
| Name | Value | Unit | Notes |
|---|---|---|---|
## 7. Enums & states
| Enum | Values |
|---|---|
## 8. Events
| Topic | Direction | Payload (field: type) | When | Key |
|---|---|---|---|---|
## 9. Error codes
| Code | HTTP | When | User message |
|---|---|---|---|
## 10. Handoff to stage 4 — DB constraints required
| # | LLD rule | Required constraint |
|---|---|---|
## 11. Doubts
| # | Problem | Consequence if kept | Alternative | Trade-off |
|---|---|---|---|---|
## 12. Assumptions & risks
| # | Content | Impact if wrong | Who confirms |
|---|---|---|---|
