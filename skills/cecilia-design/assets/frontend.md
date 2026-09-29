# <app> — frontend architecture

> Sources: `requirements.md` §<n> · `<unit>-api.yaml` **version <v>** · design system: <name or none>
> Decisions: `DECISIONS.md` D-<nn>, D-<nn> · Confidence: `[verified]` `[inferred]` `[unverified]`

## 1. Platform & strategy
| Item | Decision | Why (requirement it serves) |
|---|---|---|
| Platform / browsers / devices | | |
| Rendering strategy | | |
| Framework + version | | |
| Design system | | |
| Server-state approach | | |
| Client-state approach | | |
| Forms | | |
| i18n / timezone / money | | |

## 2. Screens
| SCR | Name | Actor(s) | Serves | Entry points | Permissions |
|---|---|---|---|---|---|

## 3. Per screen
### SCR-01 — <name>
**Data**
| Element | Endpoint (EP) | Field | If missing |
|---|---|---|---|

**States** *(every row is mandatory; write "n/a" with a reason rather than deleting one)*
| State | Trigger | What the user sees | What they can do |
|---|---|---|---|
| loading | | | |
| empty — no data | | | |
| empty — no results for filter | | | |
| partial | | | |
| error `<CODE>` | per error code from the contract | | |
| permission denied | | | |
| offline / stale | | | |
| submitting | | | |
| success | | | |

**Actions**
| Action | Endpoint | Optimistic? | On success | On failure | What refreshes |
|---|---|---|---|---|---|

## 4. Component tree
```
<ASCII tree: CMP ids, which screen owns each, which are from the design system>
```
| CMP | Name | Owner screen | Props | Holds state? | Shared? |
|---|---|---|---|---|---|

## 5. State ownership
| Data | Owner (URL / server cache / global / form / derived) | Invalidated by | Survives refresh? |
|---|---|---|---|

## 6. Routing
| Path | SCR | Guard | Deep link without permission | Not found |
|---|---|---|---|---|

## 7. Forms & validation
| Form | Field | Client rule | Mirrors server rule | Error code → message |
|---|---|---|---|---|

## 8. Shared patterns
<loading / empty / error / retry / stale / toast-vs-inline — decided once, referenced by every screen>

## 9. Accessibility & budgets
| Item | Target | Measured by |
|---|---|---|
| Accessibility level | | |
| Bundle per entry | | |
| Interaction latency | | |
| First paint | | |

## 10. Contract gaps *(change requests to design-be)*
| # | Screen | Needs | Contract provides | Proposed change | Blocks |
|---|---|---|---|---|---|

## 11. Doubts
<2–4: problem → consequence → alternative → trade-off>

## 12. Assumptions & risks
