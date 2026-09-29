# Challenge log — <TASK>

> Append-only. A row is edited only in its **Status** and **Decided by** columns. Protocol:
> `references/common/challenge.md`. Two rounds maximum, then it goes to Cecilia.

| # | Date | Artifact / ID | Challenger → Owner | Claim (failure scenario) | Owner response | Round | Status | Decided by |
|---|---|---|---|---|---|---|---|---|
| C-01 | 2026-09-18 | LLD §4.1 (FR-05) | dev → design | two cancels in parallel both pass the status check → double refund | ACCEPT: version column + conditional update, LLD §4.1 | 1 | ACCEPTED | design |
| C-02 | 2026-09-18 | plan B-02 | dev → plan | B-02 and B-03 both edit the DI module → cannot run in parallel | REJECT: different files [plan §6 expected files] | 2 | ESCALATED | Cecilia 2026-09-19 |

Status: `OPEN` (blocks the gate) · `ACCEPTED` · `REJECTED (evidence)` · `ESCALATED → Cecilia` ·
`DEFERRED (<where tracked>)`.

## Open right now
<the OPEN and ESCALATED rows, copied here so no gate is passed over one — empty means none>

## Accepted but not yet in a document
<ACCEPTED rows that change what a doc says and have no `DOC-Bnn` task yet — this list is doc debt>
