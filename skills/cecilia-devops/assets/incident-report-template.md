# INC-nn — <short description>

> Date: <YYYY-MM-DD> · Role: devops · Environment: ENV-nn <name> · Severity: S1 | S2 | S3
> Status: ACTIVE | STABLE (cause not fixed) | RESOLVED · Task: <TASK>
> Detected at: <HH:MM> · Stable at: <HH:MM> · Duration of impact: <…>

Write this **during** the incident, not afterwards. Secrets by name only. Every factual line carries
`[verified]` (read this session, with the source) / `[inferred]` / `[unverified]`.

## 1. Impact

Who was affected, which operation, how badly, and how that was measured. Include what was **not**
affected. If the failure was silent or produced wrong results rather than errors, say so prominently
— that changes what has to be checked afterwards.

## 2. Timeline

| Time | Event | Source | By |
|---|---|---|---|
| 13:58 | deploy orders v1.5.0 | deploy marker + pipeline run #482 `[verified]` | pipeline |
| 14:02 | /checkout 5xx rises to 40% | dashboard `[verified]` | — |
| 14:24 | rollback to revision 7 — approved by Cecilia 14:23 | `helm rollback` output `[verified]` | agent |
| 14:27 | 5xx back below 0.5%, held 5 min | dashboard `[verified]` | — |

Every action taken, who approved it, and what it did. Actions handed to Cecilia are marked
`handed to Cecilia` with her reported result.

## 3. What was ruled out, and how

| Hypothesis | Ruled out by | Confidence |
|---|---|---|

This section is what stops the next person repeating the same checks.

## 4. Current state

What is running now, what is still degraded, what was changed and not yet changed back, and anything
that could not be read (with what that leaves uncertain).

## 5. Cause

The mechanism, at a level where something can be done about it. Keep asking "and why was that
possible?" past the first plausible answer — the first answer is usually the trigger, not the cause.
Unknown → say unknown and list the two most promising next checks; a guessed cause is worse than an
open one.

## 6. Detection

How it was found and how long that took. Found by a customer or by Cecilia rather than by an alert →
that is a finding in its own right and belongs in the actions below.

## 7. What went well · where luck helped

Worth preserving (the rehearsed rollback, the deploy marker that pinned it in seconds) — and the
parts that would have been much worse with different timing, load or day of week.

## 8. Actions

| # | Action | Role | Why | Tracked as |
|---|---|---|---|---|
| 1 | | dev-be / dev-fe / devops / test / design / plan | | batch or PR |

Two questions every incident asks of this skill's own work, answered explicitly:

- **Would an alert have caught this sooner?** (`observability.md` §4) →
- **Had the rollback been rehearsed, and did it behave as expected?** (`deploy-and-rollback.md` §4) →

## 9. Needs your decision

Numbered, each with options and a recommendation. `[agent-chosen — needs review]` items first.
"None" if none.
