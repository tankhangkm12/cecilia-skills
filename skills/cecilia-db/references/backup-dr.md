# Backup, point-in-time recovery and disaster recovery

A backup that has never been restored is a hope. Every database the project runs gets an RPO, an RTO, a
backup method that meets them, and a **restore drill with a measured time**.

## 1. Targets (Cecilia/business decide; write them in the database doc)

| Term | Meaning | Typical question |
|---|---|---|
| RPO | how much data (time) may be lost | "5 minutes of orders?" |
| RTO | how long until it works again | "1 hour?" |
| Retention | how far back you can restore | "30 days? 7 years for invoices?" |

## 2. Methods

| Method | RPO | RTO | Notes |
|---|---|---|---|
| Logical dump (pg_dump, mysqldump, mongodump) | since last dump | slow (rebuilds indexes) | portable; fine for small DBs and dev; not PITR |
| Physical/base backup + WAL/binlog/oplog archiving (pgBackRest, WAL-G, Barman; xtrabackup + binlog; managed PITR) | seconds–minutes | load + replay | **PITR**: restore to just before a bad migration or delete |
| Storage/volume snapshots | since snapshot | fast | must be crash-consistent (engine support) |
| Replicas | ~0 for hardware loss | failover seconds–minutes | **not a backup**: deletes and bad migrations replicate too |
| Managed service backups | per provider | per provider | verify retention, PITR window, cross-region copy, restore time |

3-2-1: three copies, two media, one off-site/other account or region; backups encrypted; access separate from
the application's credentials (ransomware, mistakes).

## 3. Restore time

`capacity.py restore --data-gb L,E,H --restore-mbps L,E,H --index-factor … --wal-gb … --rto-minutes T` —
then replace the projection with a drill.

## 4. Drill (runbook `assets/dr-runbook.md`)

Restore the latest backup into a scratch instance → replay to a target time → run integrity checks (row
counts, constraint checks, application smoke test) → record measured RTO, data loss (RPO) and problems.
Cadence: quarterly, and after any backup-method change. Non-production drills can be run by the agent on
local/scratch resources (A2/A3); anything touching shared or production backups is Cecilia's (A4).

## 5. Before risky changes (git.md §4)

Local: dump before migrations/data fixes. Shared/production: a fresh backup + PITR window confirmed + the
restore command written in the release packet **before** the change.

## 6. Checks

Backup job success alerts; backup age alert; restore drill result in the database doc; retention matches
legal holds and deletion rules (security-compliance.md §4 — deleted personal data also expires from backups).
