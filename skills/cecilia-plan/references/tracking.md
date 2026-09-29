# Tracking & adjusting

## 1. Inputs to read (Track mode)

1. The plan (latest on the branch where plans are delivered; `git fetch` first).
2. `tensura/reports/<TASK>/` — newest first; note every "Needs your decision", BLOCKED status, open BUG-nn,
   review Blockers, and open `INC-nn` incident reports (an unresolved incident blocks further deploys).
3. PR/MR states on the git host (open/draft/ready/merged/closed, CI status, age) if a tool is available;
   otherwise ask Cecilia (one question) or rely on reports and say so.
4. Branches on remote matching plan names.
5. Source docs: changed since recorded version/date? (git log on docs paths; external → ask).

Short interview still applies: if the request is ambiguous (which epic? all?) ask one question; if clear,
read first and ask only about conflicts.

## 2. Progress report (`tensura/reports/<TASK>/<date>-plan-progress.md`)

Use the workspace report template; Details section:

```markdown
## Board
| Batch | DEV | REV code | TEST | REV tests | OPS | REV infra | Batch state |
|---|---|---|---|---|---|
| B-01 | MERGED | DONE | DRAFT_PR | TODO | — | — | in test |

## Traceability coverage
Implemented & merged: n/N IDs · Tested: n/N · Reviewed clean: n/N · Not started: <IDs>

## Blockers & risks
| # | Item | Since | Blocks | Proposed action (options) |
|---|---|---|---|---|

## Drift detected
| Type | Evidence | Impact |
|---|---|---|
| Plan status ≠ reality | row says DRAFT_PR, PR merged | fixed row (factual) |
| Work outside plan | branch feat-be/SHOP-42-07-x not in plan | ask |
| Docs changed after plan approval | tensura/docs/modules/order/order-design.md changed <commit> | re-trace needed |
| Stalled | TEST-B02 IN_PROGRESS, no report for n days | ask owner |

## Next actions
| Who (role/agent) | Task | Why now |
|---|---|---|
```

Status rows that are **factually** wrong (host says merged) may be corrected by the plan skill with a
note; anything else is proposed.

## 3. Detecting problems

- Dependency violated (a batch started before its dependency merged).
- Parallel tasks touching the same files (compare PR diffs to expected files).
- Open Blocker in a review report while the PR is Ready/merged.
- An ops row at `MERGED` but never `APPLIED`, or `APPLIED` with no rollback rehearsal recorded.
- Live state drift reported by devops (repo says one thing, the environment another) not yet resolved.
- Open BUG-nn not assigned to any DEV task.
- Requirement IDs not covered by any batch, or covered twice.
- `[agent-chosen — needs review]` items still unconfirmed.

## 4. Adjust mode

1. Explain the trigger (blocked batch, doc change, bug, Cecilia request) with evidence.
2. Present options one question at a time, e.g. split B-03 · move FR-09 to B-05 · insert fix batch
   `BE-B03a` for BUG-04 · re-sequence TEST before BE for B-04 · pause epic.
3. Show the plan diff (rows before/after). Never rewrite history rows; retired tasks get `~~ID~~ replaced by …`.
4. After approval: update plan, add a "Plan changes" row (date, change, reason, approved by), deliver
   per the chosen delivery mode, report, notify affected roles in "For other roles".
