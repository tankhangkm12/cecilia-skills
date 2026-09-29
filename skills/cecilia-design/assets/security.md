# Security — <system>

> Sources: `architecture.md` · `*-api.yaml` v<n> · `*-database.md` · `*-frontend.md` · the infrastructure docs
> Scanner evidence: <tool + version + date, or "none — findings are [unverified]">
> Authorisation to test a running system: <none | Cecilia, written, <date>, target <x>, window <y>>

## 1. What we are protecting
| Asset | Where it lives | Worst day if it leaks / is altered | Regulation |
|---|---|---|---|

## 2. Actors considered
| Actor | Access they start with | Motivation |
|---|---|---|
| anonymous internet | | |
| authenticated customer | | |
| employee / support | | |
| partner system | | |
| compromised dependency or CI | | |

## 3. Trust boundaries
```
<ASCII — every crossing carries: what data · which identity · what if the caller lies>
```

## 4. Threats
| THR | Boundary/flow | STRIDE | Scenario (1 line) | Likelihood + reason | Impact + reason | Control | Status |
|---|---|---|---|---|---|---|---|

<Each Critical/High threat written out in full per `references/security/threat-model.md` §3.>

## 5. Controls
| CTL | Threat(s) | Control | Level (structural/systematic/per-endpoint/procedural) | Lives in | Implemented by | Test that keeps it fixed |
|---|---|---|---|---|---|---|

## 6. Authorization matrix
<per `references/security/authz-matrix.md` — every endpoint × actor, ownership condition, deny response>

## 7. Supply chain
| Metric | Value | Tool + version | Date |
|---|---|---|---|
| Critical / High / Moderate / Low | | | |

| Finding | Package | Reachable from our code? | Attacker reach | Fix cost | Decision |
|---|---|---|---|---|---|

## 8. Secrets & data exposure
| Check | Result | Evidence |
|---|---|---|
| No secret values in repo, logs, bundle, image | | |
| PII redaction list covers every sensitive field | | |
| Error responses reveal nothing about existence | | |

## 9. Accepted risks
| # | Risk | Why accepted | Accepted by | Date | Revisit when |
|---|---|---|---|---|---|

## 10. Open items blocking release
| # | Item | Severity | Owner | Blocks |
|---|---|---|---|---|

## 11. Metrics
| Metric | Value | Formula | Source |
|---|---|---|---|
| Threats with a control | / | | |
| Endpoints with ownership rule | / | | |
| Endpoints verified in code | / sampled | | |
