# Test report — <TASK> — lens <lens>

> Lens: <lens> · Unit: <unit | -> · Round: <0-3> · SHA: <sha tested> · Agent: <run.json id> · Date: YYYY-MM-DD
> Oracle: <docs paths@version, contract version, NFR ids> · Environment: <ports, DB name, compose project, tool versions>
> Verdict: <PASS | FAIL | BLOCKED> · Tests: <total> · pass <n> · fail <n> · skip <n> · blocked <n> · flaky <n>

## Commands
<exact commands, one per line, runnable from the worktree>

## Coverage
<the lens's own table (see `references/lenses/<lens>.md` §Report); uncovered IDs with the reason>

## Bugs (open at this SHA)
<!-- Parsed by `workflow.py merge-tests`: keep the header and 5 columns exactly; one row per open bug; none → keep the header, no rows.
     Severity uses the fix-loop scale: BLOCKER (Critical/High) · SHOULD-FIX (Medium) · SUGGESTION (Low). -->
| ID | Title | Severity | Repro | Evidence |
|---|---|---|---|---|
| BUG-<lens>-01 | <behaviour-level title (violated ID)> | <BLOCKER / SHOULD-FIX / SUGGESTION> | <test path::name, or command> | <assertion output / screenshot / bug file path> |

## Re-test (rounds 1-3 only)
| ID | Status (VERIFIED / REOPENED / STILL_OPEN) | SHA | Evidence |
|---|---|---|---|

## Limits
<what this lens could not run and why (`[unverified]`), A3 requests, flaky reruns with every attempt>

## For other roles
<`HANDOFF: needs <role> — <what>` lines for anything outside this lens or outside the test lane>

Rules: <hash> (<PR-ids applied>)
