# DR runbook — <database> · <environment>

Targets: RPO … · RTO … · Retention …
Backup method: … · Location(s): … · Encryption/keys: … · Who can restore: …

## Restore to a point in time (scratch instance first)
1. Choose target time (UTC) and why.
2. Provision scratch instance: <command>
3. Restore base backup: <command>
4. Replay logs to target time: <command>
5. Integrity checks: row counts <query>, constraints <query>, app smoke <command>
6. Record: start/end time → measured RTO; last transaction present → data loss (RPO)
7. Promote / repoint (production — Cecilia only, A4): <command> · rollback: <command>

## Failover (replica promotion)
Detect → decide → promote <command> → repoint clients → verify → rebuild old primary.

## Drill log
| Date | Scenario | Measured RTO | Data lost | Issues | Follow-ups |
|---|---|---|---|---|---|
