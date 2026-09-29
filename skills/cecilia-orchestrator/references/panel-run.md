# Running the review by consensus and the fix loop (orchestrator side, v20)

Lens reviewers find issues (breadth); 3 independent voters decide which are real and how severe (depth);
`workflow.py tally` counts; a minutes writer records. Procedure, lenses and ballot rules: cecilia-review
`panel.md` and `references/consensus.md` §6 — you run it, you never review, vote or rule in it.

**When:** every STANDARD and CONTROLLED task (`review.panel.from`, default `standard`) with the lenses
frozen in `workflow.json`: STANDARD `review.panel.reviewers.standard` lenses (3–4, chosen by the diff),
CONTROLLED `reviewers.controlled` (5–6) **+ redteam** (`redteam_in`). `correctness` always. FAST → one
independent reviewer, no vote. The cost (lenses + 3 voters + 1 minutes writer per round) is on the card.

1. **Inputs.** Pin the SHA (`int/<TASK>` or the single member branch). Write
   `tensura/tasks/<TASK>/panel/inputs.md`: diff path @ SHA, oracle docs @ version, deterministic results
   (tests, lint, `cecilia_check.py` `evidence.json`), the `test-<lens>.md` reports + merged summary, the
   lenses and why. `api-consumer` with `cecilia-api-ux` on → the api-ux report is that lens.
2. **Lenses — blind, one wave.** `workflow.py brief --role cecilia-review --lens <lens>` per lens + the
   PANEL block (`assets/panel-brief-blocks.md`); launch every reviewer in the same message. Never give them
   the author's report or each other's output. Each returns its findings (P-nn) as text; store them as
   `tensura/tasks/<TASK>/panel/r1-<lens>.md` only after **all** have returned.
3. **Anonymize.** Merge into `tensura/tasks/<TASK>/panel/r1-all.md`: IDs `F-01…`, no lens, model or reviewer
   order; merge two findings only when place and failure are the same ("raised independently ×2").
   Mapping → `panel/map.md` (no voter and not the minutes writer reads it).
4. **Vote — 3 voters, one wave.** Fresh cecilia-review subagents (`--role cecilia-review --unit v<n>`, no
   lens), never a lens reviewer of this round and never the author, models per `consensus.models` + the VOTE
   block. Each re-derives every F-id against the target and writes `tensura/tasks/<TASK>/votes/review/v<n>.json` and
   `votes/verdict/v<n>.json` (evidence per item; `safety` when it applies).
5. **Tally.** `workflow.py tally --task <TASK> --stage review`, then `--stage verdict`. Never edit a ballot.
6. **Minutes.** One more fresh cecilia-review agent (MINUTES block) writes
   `tensura/reports/<TASK>/panel/verdict.md` from the two results: adopted → Fix list; rejected → with the
   refuting evidence; open → DISPUTED; vetoes. It changes no outcome.
7. **Collect.** Adopted BLOCKER + SHOULD-FIX (`fix_loop.severities`) → the fix loop. Open (DISPUTED) items
   and vetoes → the decision card (`workflow.py decision`), never a free-form question. NIT stays in the
   report. `state.md` and any G3/G4 packet cite `panel/verdict.md` and `votes/verdict-result.json`.

**Fix loop** (max `fix_loop.max_rounds` = 3): `references/workflow.md` O4 — each round = `workflow.py
round`, owners fix the Fix list + open `BUG-<lens>-nn`, re-integrate, re-test affected lenses, then a
**delta review** (steps 2–6 under `panel/fix-<n>/`) by only the lenses that had findings, with the same
voter ids `v1`–`v3` (their new ballots replace the old; the minutes keep the history). The verdict tally of
the last round is the final verdict.

Nobody on the panel — and not you — merges, approves a release or accepts a risk (A4, Cecilia).

Hosts: sub-agents never talk to each other — you relay every step through files. A host that runs them
one at a time: same briefs in sequence, each a fresh context; store `r1-<lens>` files only after the last
lens reviewer returned. One model for every voter → the card says `independence: weak`; a ballot its voter
subagent did not write is discarded or marked unverified (`consensus.md` §1).
