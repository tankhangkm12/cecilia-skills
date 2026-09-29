# Panel minutes (verdict) — <TASK> — <artifact>

> Date: YYYY-MM-DD · Role: review · Mode: panel-minutes · Model: <model, tier> · Status: WAITING_FOR_CECILIA
> Target: <branch@sha / diff path> · Oracle: <docs paths@version>
> Panel: <n> lens reviewers · lenses <list> · voters v1–v3 on <models> · independence <strong | weak>
> Round: <0 = first review | fix-n delta, <last reviewed sha>..<sha>> · Earlier F-ids: <RESOLVED / PARTIAL / NOT_RESOLVED each | none>
> Read: `votes/review-result.json`, `votes/verdict-result.json`, `panel/r1-all.md`, `panel/inputs.md` — the tally is recorded, never changed
> Deviations: <none — or where these minutes departed from `panel.md`, and why>

## Verdict: <PASS | CHANGES_REQUIRED | INCOMPLETE>
<one line why> · Verdict tally PASS x/3 · Adopted: BLOCKER n · SHOULD-FIX n · NIT n · Rejected n · Disputed n · Vetoes n

## Needs Cecilia (DISPUTED — no majority — and safety vetoes; they go on the decision card)
| F-id | Votes | Exact question | What would settle it | Severity if true · safety |
|---|---|---|---|---|

## Adopted
| F-id | Severity (tally) | `path:line` | Failure scenario (1 line) | Votes (agree x/3) | Decisive evidence |
|---|---|---|---|---|---|

## Fix list (read by the fix loop — ADOPTED BLOCKER and SHOULD-FIX only; DISPUTED never here)
| F-id | Severity | `path:line` | Failure scenario (1 line) | Owner (by lane) |
|---|---|---|---|---|

## Rejected
| F-id | Refuting evidence | Votes (disagree x/3) |
|---|---|---|

## Dissent kept
<minority votes with evidence that the majority outvoted — one line each, voter id and evidence; "None">

## Coverage
- Lenses run: … · lenses the diff needed but the panel did not have: …
- Unverified areas / what nobody checked: …

## Boundaries
The minutes record the vote only; nobody on the panel changes an outcome. Merging, releasing, accepting a risk or signing a SHOULD-FIX exception is
Cecilia's (A4).

Rules: <hash> (PR-ids applied)
