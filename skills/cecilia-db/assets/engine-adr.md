# ADR-<nn>: Database for <workload> — <status: proposed | accepted | superseded>

Date · Deciders: Cecilia · Prepared by: cecilia-db

## Context
Workload profile (engine-selection.md §1) and forecast summary with numbers.

## Options (≥ 3, incl. "stay with current")
| Criterion (weight) | Option A | Option B | Option C |
|---|---|---|---|
| Fit to data shape / transactions | | | |
| Mechanism notes (storage, MVCC, replication) | | | |
| Scale ceiling vs forecast | | | |
| Latency p95 (POC) | | | |
| Operations (team, managed offering, backup/PITR) | | | |
| Cost/month at month 12 | | | |
| Migration effort & reversibility | | | |

## POC (local copy, month-12 data volume)
Data, queries, tools (pgbench / sysbench / YCSB / k6), results with commands.

## Decision
## Consequences (what gets harder, extra stores to run)
## Revisit when
- e.g. peak writes > …/s · data > … TB · second region · licence change
## Sources (official docs with version and date)
