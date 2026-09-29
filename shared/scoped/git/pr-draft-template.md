<!-- scoped source: shared/scoped/git/pr-draft-template.md — synced into dev-be, dev-fe, test and db. Do not edit a copy.
     Full Draft PR description for Cecilia, saved as tensura/reports/<TASK>/pr-body.md; she pushes and opens
     the PR herself (local-only). Chat language. Drop sections that do not apply, keep order.
     Write for someone who has not read the code: short sentences, file paths, requirement IDs. -->

## 1. Context
- **Task / issue:** <TASK> · #<issue>
- **Plan:** `tensura/plans/<file>.md` — **Batch <n>/<total>:** <one-sentence goal> · role: <dev-be|dev-fe|test|db>
- **Docs followed:** <doc> §<section> (<IDs>)
- **Branch:** `<branch>` → `<target>` · **Head SHA:** `<sha>` · **Approved scope:** `<TASK>-Bnn` (all changed files inside it: yes/no)
- **Why:** <1–2 sentences, business language>

## 2. Summary of changes
<3–5 bullets, behaviour-level, no file list>

## 3. Flow
<ASCII flow / numbered steps of the main path after the change; mark new/changed steps with ★>

## 4. Changes per file
| File | New/Changed | What | Why (IDs) |
|---|---|---|---|

## 5. Doc checklist
| ID | Requirement (doc §) | Where implemented / tested | Status |
|---|---|---|---|
| FR-03 | ... | `path:line` | ✅ / ⏭ batch n / ❌ blocked |

## 6. Decisions & assumptions
| # | Content | Options compared (decisions.md §6) | Source (D-nn / Cecilia date / [agent-chosen — needs review]) |
|---|---|---|

## 7. Look closely at
- <risky logic / trade-off> — `file:line` — why

## 8. Checks
| Gate | Command | Result |
|---|---|---|
| Build / type-check | | |
| Lint + format | | |
| Tests | | |

## 8b. Database safety *(only when the PR has migrations or DB-side code)*
| Migration | Tables touched (rows) | Lock taken / expected duration | Online method / `lock_timeout` | Down path or backup step | Ran up→down→up locally |
|---|---|---|---|---|---|

| Measurement | Before | After | Data size | Source (`M-nn`) |
|---|---|---|---|---|

DB-side objects added/changed (procedure, function, trigger, job, view): <name — why in the DB — test> / none
Connection budget changed: <pool × instances vs limit> / no

## 8c. Rollback (`git.md` §5)
```
branch <task-branch> from <base>@<start-sha>; commits <sha1..shaN>
undo all, keep history:   git revert --no-edit <start-sha>..HEAD
data:                     <restore command, backup path> / none touched
```

## 9. Rebase & conflicts
- Rebased onto `<target>` @ `<sha>`; conflicts: <file: what each side did → what was kept, why> / none

## 10. Impact
- [ ] DB migration (down path?)  - [ ] New env/config  - [ ] API/event contract change  - [ ] Dependency change (approved in D-nn)

## 11. Out-of-scope proposals (not done here)
| # | Proposal | Why | Options |
|---|---|---|---|

## 11b. Deviations
<none — or each place this PR differs from the instruction or the docs, and why>

## 12. Changes after review
- <round: sha — what, for which comment>
