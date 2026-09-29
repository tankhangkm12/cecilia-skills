# Test plan — <system>

> Updated: <YYYY-MM-DD> · Inputs: `requirements.md`, `<module>-design.md`, `<unit>-api.md`

## 1. Scope & policy
| Item | Decision |
|---|---|
| Levels in scope | manual · API/integration · E2E · performance · basic security · unit hints |
| Release-blocking severity | |
| Known-issue policy | |

## 2. Preparation
| Item | Content |
|---|---|
| Environments | |
| Test accounts | |
| Seed data | |
| Real data allowed? | |

## 3. Manual / acceptance
| TC | Screen / flow | Preconditions | Steps | Expected (concrete) | Severity | AC/FR |
|---|---|---|---|---|---|---|
Mandatory UI states: empty list · loading · offline · server error.

## 4. API / integration
| TC | Endpoint | Input | HTTP | Expected response | FR/AC |
|---|---|---|---|---|---|
Each endpoint: happy · invalid · forbidden.

## 5. Concurrency (every CORE op)
| TC | Operation | Race scenario | Mechanism (LLD D-nn) | Expected |
|---|---|---|---|---|

## 6. Performance & basic security *(if in scope)*
| TC | Scenario | Load / attack | Target (NFR) | Tool hint |
|---|---|---|---|---|

## 7. Unit-test hints
| Function / branch | Cases |
|---|---|

## 8. Traceability
| AC / error code | TC |
|---|---|

## 9. Assumptions & risks
