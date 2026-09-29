# Test design

## 1. Sources and oracle
Expected results come from, in order: SRS acceptance criteria (AC-nn, Given/When/Then) · business rules
(BR-nn) · LLD flows, state machines, edge-case tables, error codes · API contract (status, errorCode,
schema, constraints, permissions) · test plan `06-*` · NFRs (performance/security targets) · UI designs.
Dev manual-verification notes and current behaviour are hints, never the oracle.

## 2. Coverage frame (apply to every input/operation — never free-form)
| Group | Cases |
|---|---|
| Happy path | each AC's positive scenario with concrete data |
| Empty / missing | required field empty/absent, empty body, empty collection |
| Boundaries | min, max, min−1, max+1, zero, negative, very long strings, unicode |
| Type / format | wrong type, bad date, invalid enum, malformed JSON, extra unknown fields (whitelist) |
| Permission | anonymous, wrong role, **another user's resource** (expect documented 404/403) |
| Existence | unknown id, soft-deleted record |
| Duplicates / idempotency | same request twice, same Idempotency-Key with same/different body, unique violation |
| State | every allowed transition + every blocked transition |
| Concurrency | two actors on one record for every CORE operation; prove the chosen mechanism (no oversell, one winner, one event) |
| External failure | dependency timeout/error → documented fallback/error, no partial data |
| UI states | loading, empty, error, offline, forbidden-hidden actions, responsive breakpoints in docs |
| NFR | latency/throughput targets, rate limits, payload size limits |

Every error code in LLD/API has ≥ 1 case triggering it. Every endpoint has happy + invalid + forbidden.

## 3. Test-case catalog `tensura/reports/<TASK>/test-cases-<service>.md`
```markdown
# Test cases — <TASK> — <service>
> Sources: <doc paths + versions> · Updated: <date> · Levels: <unit|integration|api|e2e|perf|security|manual>

| TC | Level | Covers (IDs) | Preconditions / data | Steps / input | Expected (concrete) | Severity | Automated in | Status |
|---|---|---|---|---|---|---|---|---|
| TC-001 | api | FR-05, AC-07 | order PENDING owned by u1 | POST /orders/{id}/cancel as u1 | 200, data.status=CANCELLED, event OrderCancelled once | High | `test/api/order-cancel.spec.ts::cancels pending` | PASS |

## Coverage
| ID | TCs | Automated | Result |
|---|---|---|---|
## Uncovered / blocked
| ID | Reason | Needs |
|---|---|---|
```
Severity: High (blocks release) · Medium · Low — or the project's policy. Status: TODO / PASS / FAIL (BUG-nn)
/ BLOCKED (reason) / FLAKY.

## 4. Choosing the level (prefer the cheapest level that proves the requirement)
Pure business rule/calculation/state guard → unit · repository queries, transactions, constraints,
adapters with test containers/fakes → integration · HTTP contract, auth, envelope, error codes, pagination →
API · multi-screen user journeys, UI states → E2E (few, critical journeys only) · targets from NFR → performance ·
OWASP-style checks on inputs/auth → basic security.
