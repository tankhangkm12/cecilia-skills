# Vietnam personal-data protection — engineering checklist

**Not legal advice.** Laws and decrees change; before relying on this, research the current official text
(Law on Personal Data Protection and its implementing decree(s)) and cite version and date in the report.
As researched for v19: the Law on Personal Data Protection took effect on 1 January 2026 with an implementing
decree effective the same date; it replaced Decree 13/2023/ND-CP. Verify.

| Topic | Engineering implication | Where in the DB doc |
|---|---|---|
| Basic vs sensitive personal data | classify columns; sensitive (e.g. health, biometric, financial, location, children's data — per the law's list) gets stricter access, encryption and logging | §17 inventory |
| Consent / legal basis | store consent records (who, what purpose, when, version, withdrawal) queryable per person | consent table |
| Data-subject rights | export, correction, deletion, restriction flows with deadlines from the law | §17 procedures |
| Impact assessment | processing and cross-border transfer impact-assessment dossiers kept up to date; the law sets filing deadlines (research) | link to dossier |
| Cross-border transfer | know which stores/replicas/backups/vendors are outside Vietnam | §17 "leaves country" column |
| Breach notification | notification to the competent authority within the legal deadline (researched: 72 hours — verify) | runbook |
| Retention & deletion | delete or anonymise when the purpose ends | §5/§7 retention |
| Security measures | access control, encryption, logging, audit trails | security-compliance.md §2 |

Output: a checklist with status per row (done / gap / unknown), the gap owner, and questions for counsel.
