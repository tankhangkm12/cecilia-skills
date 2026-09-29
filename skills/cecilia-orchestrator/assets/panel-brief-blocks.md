# Review by consensus — PANEL, VOTE and MINUTES blocks for the briefs

Used by `references/brief-roles.md` §"Review panel briefs". Copy the block for the member, fill the
`<…>`, place it after block 5 of a normal cecilia-review brief. Procedure: cecilia-review `panel.md`;
ballots and tally: `references/consensus.md`. `<P>` = `tensura/tasks/<TASK>/panel`.

Lens reviewer (one per lens, all in one wave; fix round n: `<P>/fix-<n>/`):

```
PANEL: mode: panel-reviewer, lens: <lens> · <first review | fix-<n> delta, <old sha>..<sha>> · READ-ONLY.
Follow panel.md §2 (your lens) and §3. Read ONLY: <diff path @ SHA>, <oracle docs @ version>,
<tool results: tests, lint, evidence.json>, <P>/inputs.md.
Do NOT read: the author's report, any other file under panel/ or votes/, earlier reviews of this target.
Every finding P-nn: severity, file:line, failure scenario (input -> wrong outcome), evidence, and what
would make you withdraw it. Answer the simplicity question. Return the report as text (panel-finding
template); the orchestrator stores it. End with STATUS and DEVIATIONS lines.
```

Voter (3 fresh agents, one wave; never a lens reviewer of this round, never the author):

```
VOTE: mode: panel-voter · you are v<n> of 3 · model <model> · independent.
Read: <P>/r1-all.md, <P>/inputs.md, the target @ <SHA> and the oracle; re-derive every F-id yourself
with read-only tools. Do NOT read: <P>/map.md, r1-<lens> files, other ballots, the author's report.
Write ONLY two files (panel.md §5): tensura/tasks/<TASK>/votes/review/v<n>.json — every F-id agree
(real) / disagree (not real) / abstain, severity BLOCKER|SHOULD-FIX|NIT, safety data-loss|secret|
destructive|null, evidence you checked (file:line, test, command) and a one-line reason — and
tensura/tasks/<TASK>/votes/verdict/v<n>.json — item "verdict", agree = PASS. No evidence -> the tally
drops the item. "Others agree" is not evidence. Return ≤ 10 lines. End with STATUS and DEVIATIONS lines.
```

Minutes writer (one fresh agent after `workflow.py tally --stage review` and `--stage verdict`):

```
MINUTES: mode: panel-minutes · you took no part in this review and cast no ballot.
Read: tensura/tasks/<TASK>/votes/review-result.json, votes/verdict-result.json, <P>/r1-all.md,
<P>/inputs.md. Write ONLY tensura/reports/<TASK>/panel/verdict.md (panel-verdict template): adopted
findings by severity with votes (2/3) -> Fix list (BLOCKER, SHOULD-FIX; owner by lane); rejected with the
refuting evidence; open (no majority) -> DISPUTED with the exact question for Cecilia; vetoes; independence.
You record the tally — you never change an outcome, merge, approve a release or accept a risk (A4).
End with STATUS and DEVIATIONS lines.
```
