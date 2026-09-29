# Panel round 1 — <TASK> — lens <lens>

> Date: YYYY-MM-DD · Role: review · Mode: panel-reviewer · Lens: <lens> · Round: 1 (blind) · Model: <model>
> Target: <branch@sha / diff path> · Oracle: <requirements / docs paths@version>
> Inputs read: <diff, docs, tool results (tests, lint, evidence.json), test lens reports `test-<lens>.md` @sha — paths>
> Delta (fix round only): <last reviewed sha>..<sha> · earlier F-ids: <F-nn RESOLVED / PARTIAL / NOT_RESOLVED — evidence>
> Not read (by rule): the author's report, other reviewers' files
> Deviations: <none — or where this pass departed from the brief, and why>

## Lens questions
| Question (from `panel.md` §2) | Answer | Evidence |
|---|---|---|

## Findings
### P-01 · <BLOCKER | SHOULD-FIX | SUGGESTION | QUESTION> · `path:line` · <lens | outside lens> (<IDs>)
- **Claim:** <what is wrong, one line>
- **Failure scenario:** <input / situation> → <wrong outcome>
- **Evidence:** <line read, path traced, test, doc § — [verified | inferred | unverified]>
- **Would withdraw if:** <the evidence that would refute this>

## Simplicity (every lens)
<Could less code, fewer layers or no new dependency do it? "Yes — where / how" (SHOULD-FIX) or "No — why">

## Attacked and holds
<what was checked and why it stands — "looks fine" is not an answer>

## Not covered / unverified
<what this reviewer could not check, and why>

Rules: <hash> (PR-ids applied)
