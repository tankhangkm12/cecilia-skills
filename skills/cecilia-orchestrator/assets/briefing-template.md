# Briefing — <project> · <TASK>

> Data class synced outward: ids, statuses, metrics, challenge text. No secret values. — cecilia-orchestrator (briefing)

> **BRIEFING · <TASK> · as of <YYYY-MM-DD> · <WAITING_FOR_CECILIA | BLOCKED | IN_PROGRESS | DONE>**
> Done: <what is merged/approved, with the measured number and its M-nn>
> Now: <what is in flight, which batch, which role, where it stopped>
> Blocked: <what cannot move and by what — or "nothing">
> Decide: <count of open decisions; the one that blocks most, named>
> Next: <the single next action and who owns it>
> Deviations: <every deviation the roles reported since the last briefing — or "none reported">

Verification: <PASS by cecilia-review (verify mode) <date> | self-verified — weaker>

## Needs your decision
<numbered. `[agent-chosen — needs review]` first. Each: the question in one line · options with
 gain/cost · the owning role's recommendation · source ref (C-nn / report path / plan row). "None" if none.>

## Measured
<only metrics that changed or that gate a step. value · formula · source · label · M-nn · previous value.>

| M-nn | Metric | Value (was) | Formula | Source | Label |
|---|---|---|---|---|---|

## Quality posture
<assembled, not authored. Per area: review findings by severity (report path) · coverage/tests (M-nn) ·
 OPEN challenges (C-nn). Areas with no review or tests: say "not yet reviewed" — that is the finding.>

## Progress
<per batch: tasks MERGED / total (plan status table) · state per role · PR states (Delivery tab).>

## What each area still needs
<one line per area, from reports' "For other roles" and unmet plan dependencies. "None" if none.>

---
Surface: <link to Sheets/Docs/Notion>  ·  Snapshot: `tensura/reports/<TASK>/<date>-lead-briefing.md`
