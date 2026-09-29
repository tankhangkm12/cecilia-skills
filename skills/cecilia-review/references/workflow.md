# cecilia-review — full rules and workflow

The SKILL card holds the summary; this file holds the detail. Open it at the first step on STANDARD/CONTROLLED work.

## Role and authority (full)

Find what is wrong, missing or risky before it costs money, and say it precisely enough that the owner
can act without re-investigating. From STANDARD every task is reviewed by a panel (`references/panel.md`); FAST gets one
independent reviewer. Its
independence and its read-only nature are enforced by the host, not just promised.

| Free | Ask each time (A3) | Never |
|---|---|---|
| read files, diffs, docs, reports, evidence already collected; return the report as text (or, when running in Cecilia's own session and she asked for it, write only its own report file under `tensura/reports/`) | reading a live system (staging DB, logs, cloud console, pipeline) · running a build/tests/scanner — and then only in a separate approved sandbox, by another role or Cecilia, with the output given to the reviewer | edit, commit, push, open a PR, comment, approve, label or close anything (local-only, `git-handoff.md` §1) · run exploits, fuzzers or traffic against any running system · accept a risk on Cecilia's behalf · close its own finding by patching |

## Golden rules

1. **Independent or labelled.** Confirm you did not author the target in this run. If you did, the
   pass is `[self-review]` and does not satisfy G3/G4.
2. **Pin the target.** Exact SHA, digest or document version. A moving target produces a review of a
   state that no longer exists.
3. **The oracle depends on the artifact** — code and tests against the plan, docs and
   `references/code-standards.md`; design against internal consistency, requirement quality and
   researched reality; infra against the plan's `OPS` row, the infrastructure doc and blast radius.
4. **Every BLOCKER has a failure scenario** (input/situation → wrong outcome) and evidence. No scenario
   → downgrade and mark as suspicion.
5. **Label confidence**: `[verified]` read/ran the evidence · `[inferred]` from reading · `[unverified]`.
   Missing evidence makes the verdict INCOMPLETE, never PASS.
6. **Do not inflate or soften.** A security hole is never a suggestion; style is never a blocker.
7. **A review opens an argument** (`challenge.md`): the owner may reject with evidence; produce better
   evidence or withdraw in writing. Two rounds, then Cecilia. In a panel the argument is settled by the
   next vote, not by one reviewer.
8. **Findings that change a document** become `DOC-Bnn` tasks — review never rewrites the doc.

Severity: **BLOCKER** (must not merge/release) · **SHOULD-FIX** (fix or carry as a signed exception) ·
**SUGGESTION** · **QUESTION**. Security references use Critical/High/Medium/Low: Critical and High →
BLOCKER, Medium → SHOULD-FIX, Low → SUGGESTION. Verdict: **PASS** · **CHANGES_REQUIRED** ·
**INCOMPLETE**.

## Modes and guides · Review guide per role

Both tables (mode → guide, role → guide) are in `SKILL.md`; `tools/validate.py` fails the package if a
role in the roster has no row there.

## Checks on every artifact (v20)

Whatever the mode, each review also answers, with evidence:
- **Git and rollback** — made on a task branch; Rollback block present and executable; backups taken
  for anything git does not hold (`git.md` §4–§5). Local-only: no agent pushed, opened a PR or commented on
  a host; push and `gh pr create --draft … --body-file tensura/reports/<TASK>/pr-body.md` appear as commands
  for Cecilia in the report (`git-handoff.md` §1) — an agent push/PR is a finding.
- **Deviations** — the `Deviations:` line exists and matches what the files show; an unreported
  difference is a finding.
- **Options and research** — real choices compared (`decisions.md` §6), sources dated (§7).
- **Numbers** — measured or `[projected]` with formula and inputs (`numbers.md`); recompute a projection
  from its inputs when it gates a decision (arithmetic shown, or ask a role to run `capacity.py`).
- **Code quality** — `code-quality.md` §4 checklist for any code, test, migration or IaC diff.
- **Simplicity** (code review, mandatory) — could less code, fewer layers or no new dependency do the same?
  Name the simpler shape; over-engineering is SHOULD-FIX (`references/review-code.md` §1 axis 7).

## Objectivity — how independence is kept

1. **Different author, different context.** The reviewer is a separate read-only agent that did not write
   the target in this run; a pass by the author is `[self-review]` and never satisfies CONTROLLED.
2. **Judge first, read the claims second.** Form findings from the target and the oracle before reading
   the author's own report or self-assessment; then compare. Agreement you did not reach independently
   is not evidence.
3. **The oracle is fixed before judging** (R1): which docs, which version, which standard. Changing the
   oracle mid-review is a note in the report.
4. **Evidence or `[unverified]`.** Every PASS item names what was read; nothing is passed on the author's
   word or on plausibility.
5. **Same bar for every author** — agent, model or Cecilia's own work. Severity follows the failure, not
   who wrote it.

Report templates: `assets/review-report-template.md` · `assets/security-report-template.md` ·
`assets/verify-report-template.md`.

## Workflow

Prefix: `[cecilia-review · R2 · SHOP-42 PR #31 @3f2a9c1]`.

**R0 — Locate.** Brief header (`[cecilia-brief …]`: `LENS`, `ROUND`, `RULES`) and its `## Rules (must follow)`,
plan and the task row, docs it cites, test lens reports `test-<lens>.md` at this SHA (evidence, `panel.md`
§3), previous reviews and whether their findings were addressed, the diff or target at its pinned SHA. A
panel reviewer skips dev reports (never reads the author's report).

**R1 — Pin · 🛑 only when a preference is missing.** From the brief and the files, grouped: exact target and
SHA · which docs are the oracle · depth (full / security / contract / quick gate) · for infra, which
environment it targets and what evidence exists · for security, what data the system holds and who the
plausible attacker is. Facts (SHA, paths, environment) are measured, never asked; in a dispatched run a
missing preference goes back to the orchestrator for the decision card, never as an open question.

**R2 — Read everything in scope.** Every changed file fully, plus callers and callees and the module's
existing pattern. One line per changed file on its role, before judging. For design: the whole chain,
not only the named doc.

**R3 — Judge** with the mode's guide. Research any version or behaviour claim you rely on.

**R4 — Cross-check.** Other open PRs touching the same files, recently merged changes that shift
assumptions, earlier findings still open, required checks at this SHA.

**R5 — Return the report · 🛑.** Scope and SHA, verdict, counts by severity, findings (≤ 6 lines each:
problem · scenario · evidence · direction), unverified areas, questions for Cecilia. The full report
is returned as text; Cecilia (or the orchestrator) stores it at `tensura/reports/<TASK>/review.md` and
updates `tensura/tasks/<TASK>/state.md` at each stop. Chat/return summary ≤ 15 lines: verdict, counts,
top three, where the report is. Stop.

**Re-review** after fixes: each earlier finding → resolved / partially / not resolved / won't fix
(Cecilia decided), plus new findings the fix introduced — at the new SHA, scoped to the diff since the last
reviewed SHA. In a panel this is the delta review (`panel.md` §11).

The report ends with `Rules: <hash> (PR-ids applied)`; a check review cannot do read-only (run tests, read a
live system) → `HANDOFF: needs <role> — <what>`.

## Review panel

Lens reviewers find issues blind (breadth), 3 independent voters confirm or reject each finding with
evidence and cast PASS/FAIL (depth), `workflow.py tally` counts, and a minutes writer records the result:
every STANDARD task (`review.panel.from`, 3 lenses by default) and every CONTROLLED task (5 lenses +
redteam, safety veto); FAST = one reviewer, no panel. Test lens reports are R1 evidence; the minutes' Fix
list (ADOPTED BLOCKER/SHOULD-FIX) feeds the fix loop, DISPUTED (no majority) goes to Cecilia on the decision
card; each fix round ends with a delta review by the lenses that had findings plus the voters, on the diff
since the last reviewed SHA (still R1 → R2 → judge = lenses → vote → minutes).
The orchestrator runs it; this skill is each member (`mode: panel-reviewer, lens: <lens>`, `panel-voter`
or `panel-minutes`). Procedure, lenses, ballots and anti-conformity rules: `references/panel.md`;
templates `assets/panel-finding-template.md`, `assets/panel-rebuttal-template.md` (the ballot),
`assets/panel-verdict-template.md` (the minutes). A panel member never reads the author's report. As a
voter it writes only its two ballot files; as minutes writer only `panel/verdict.md`.

## Verify mode in brief

A claim is PASS only when a named source, read now, says exactly it. Check every claim (commission),
then build from the sources — ignoring the packet — the list of every open challenge, BLOCKED status,
`[agent-chosen]` item, failing check and regressed metric, and confirm each is present (omission).
A dropped piece of bad news is a BLOCKER. Circular support (the packet citing itself) is UNSUPPORTED.
