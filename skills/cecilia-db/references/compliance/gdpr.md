# GDPR (EU/EEA data subjects) — engineering checklist

**Not legal advice.** Verify against the official text and current guidance; cite them.

| Article area | Engineering implication |
|---|---|
| Lawful basis & consent (Art. 6–7) | consent records with purpose, timestamp, version, withdrawal |
| Special categories (Art. 9) | health, biometric, ethnicity… — stricter access, encryption, minimisation |
| Data minimisation & storage limitation (Art. 5) | only needed columns; retention per purpose, enforced by jobs/partitions |
| Rights (Art. 15–22) | access/export (portable format), rectification, erasure incl. derived stores, restriction, objection |
| Privacy by design (Art. 25) | pseudonymisation, defaults, masked non-production data |
| Records of processing (Art. 30) | the personal-data inventory feeds it |
| Security (Art. 32) | encryption, access control, resilience, restore testing (backup-dr.md) |
| Breach notification (Art. 33–34) | notify the supervisory authority within 72 hours where required; scope from audit logs |
| DPIA (Art. 35) | high-risk processing needs an impact assessment |
| International transfers (Ch. V) | know where replicas, backups, vendors and support access are |

Output: checklist with status per row, gap owner, questions for counsel.
