# Data security and privacy engineering

Not legal advice. The skill produces an engineering checklist and an inventory; Cecilia (and counsel for
regulated data) decides. Packs: `compliance/vn-pdpl.md` (Vietnam), `compliance/gdpr.md` (EU/EEA users).

## 1. Personal-data inventory (database doc §17)

Per table/collection and column/field: category (identifier, contact, financial, location, health/biometric,
children's, credentials), sensitive per the applicable law?, purpose, legal basis/consent reference, retention,
who reads it (roles/services), leaves the country/region?, masked in non-production?

## 2. Controls

| Control | Minimum |
|---|---|
| Least privilege | application role without DDL; migrations run under a separate role; read-only role for analytics; no shared superuser |
| Row/tenant isolation | tenant id in every multi-tenant query; row-level security (PostgreSQL RLS) or enforced repository filters + tests |
| Encryption | TLS in transit (verify certificates); at rest (disk/managed); column/application-level for highly sensitive fields with key management outside the DB |
| Secrets | connection strings in a secret store/env, never in code, logs or docs |
| Credentials storage | passwords hashed (argon2id/bcrypt/scrypt) — never encrypted or plain |
| Audit | who read/changed sensitive data; append-only audit table or log sink; retention |
| Non-production data | synthetic or masked; never a raw production copy on a laptop |
| Logging | no personal data or secrets in query logs, slow-query logs, error messages |
| Backups | encrypted, access-restricted, retention aligned with deletion (backup-dr.md) |

## 3. Data-subject requests (access, correction, deletion, portability)

Map where each person's data lives (inventory), the query to export it, and the deletion/anonymisation
procedure incl. read models, search indexes, caches, analytics and backups (expire with retention or crypto-shred).

## 4. Retention and deletion

Retention per table from law/contract; implement with partitions/TTL (`partitioning-retention.md`); legal holds
override; document what "deleted" means (hard delete, anonymised, tombstone).

## 5. Breach readiness

Know which tables hold what (inventory), who to notify and within which deadline (per law pack), and how to
determine scope (audit logs).
