# Release readiness & risk review

Inputs: plan (all batches DONE? open tasks, `OPS-Bnn` applied?), the infrastructure docs, reports (open BUG-nn by severity, review Blockers unresolved,
agent-chosen decisions unconfirmed), test run reports (coverage by ID, perf/security results), PRs merged
since last release, migrations, config/env changes, dependency changes, docs versions.

## Checklist (print every row with evidence)
| # | Area | Check |
|---|---|---|
| 1 | Scope | every in-scope ID implemented, tested, reviewed clean; out-of-scope confirmed |
| 2 | Bugs | no open Critical/High; Medium/Low accepted explicitly by Cecilia |
| 3 | Reviews | no unresolved Blocker in any review report |
| 4 | Tests | release-blocking TCs pass; no unexplained skipped/flaky; NFR targets met or waived |
| 5 | Security | IDOR/auth/validation checks done; dependency audit clean or accepted; secrets not in repo |
| 6 | Data | migrations reviewed: locking on large tables, order, rollback tested, backfill plan, backups before release |
| 7 | Contracts | API/event changes backward compatible or versioned; clients informed |
| 8 | Config | new env vars/secrets present per environment; feature flags defaults |
| 9 | Operations | health/readiness, alerts, dashboards hooks, runbook for rollback; on-call informed |
| 9b | Delivery path | every `OPS-Bnn` in scope merged **and** applied to the target `ENV-nn`; rollback rehearsed and recorded; no drift left open between repo and environment (`review-infra.md`) |
| 9c | Incidents | no open `INC-nn` for the affected services; follow-up actions from closed ones exist as plan tasks |
| 10 | Decisions | no `[agent-chosen — needs review]` left unconfirmed in shipped scope |
| 11 | Docs | docs match what ships (DECISIONS updated, API yaml matches code) |

## Risk register in the report
`# · risk · likelihood (H/M/L) · impact (H/M/L) · evidence · mitigation · owner · go/no-go effect`

Verdict: **GO** / **GO with accepted risks** (list them for Cecilia to accept) / **NO-GO** (blocking items). The
verdict is a recommendation; Cecilia decides.
