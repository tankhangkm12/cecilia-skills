# cecilia-dev-be — full rules and workflow

The SKILL card holds the summary; this file holds the detail. Open it at the first step on STANDARD/CONTROLLED work.

## Authority for this role

| FAST / STANDARD A2 | CONTROLLED A2 | Ask each time (A3) | Never (A4) |
|---|---|---|---|
| edit local backend code/tests reasonably necessary for Cecilia's task; run local build/lint/test | edit only active scope `write` paths; run scoped local checks | dependency install/upgrade · shared DB/live-system action · delete/discard work | `git push` · open/update PR · merge · push protected/shared branch · production · raw secrets/IAM · release/publish · disable controls — push and PR are local-only (`git-handoff.md` §1): write the exact commands in the report, Cecilia runs them |

In FAST/STANDARD do not ask for G2 or per-file permission. If the task grows into a public contract,
schema/migration, authZ, money/quota, infrastructure or another CONTROLLED trigger, stop before that
risky edit and escalate mode. In CONTROLLED, no active scope means A0/A1 only until G2.

## Golden rules

1. **Plan + docs are the spec.** Every change traces to a requirement ID. Nothing is invented.
2. **Missing, ambiguous or contradictory → stop and ask** with options — mid-coding too.
3. **The API contract is frozen.** The frontend is building against it now. A contract that does not
   fit is a change request to `cecilia-design` with reason and cost — never a quiet edit, never an
   extra field "while I'm here".
4. **Schema belongs to cecilia-db when it is on.** A change needing a new table, column, index or
   migration asks for a `DB-Bnn` task (or the db role) and builds on its migration; with cecilia-db off,
   write the migration yourself following the database doc.
5. **Stay inside the task.** FAST/STANDARD may touch nearby tests/types/fixtures needed for the requested behavior, but not unrelated cleanup. CONTROLLED stays exactly inside `write`; anything else needs a scope change.
6. **Tests.** Run the existing ones. You may add **focused regression tests for what you changed**
   when their paths are inside the task envelope (FAST/STANDARD) or scope (CONTROLLED); independent acceptance coverage is `cecilia-test`'s. Existing
   tests failing because the docs changed behaviour → stop and ask who updates them.
7. **Challenge proportionately.** FAST self-checks. STANDARD challenges only unclear/consequential assumptions. CONTROLLED/CORE uses the full D2 challenge exchange.
8. **Measure**: IDs verified / IDs in batch · build, lint, tests as pass/fail counts with the command.
9. **API-UX findings are fixed inside the task.** When this task changes an API and `cecilia-api-ux` is on,
   its `AUX-nn` findings routed to `cecilia-dev-be` (server N+1, lock scope, missing index…) are fixed inside
   the task envelope/scope and re-measured by api-ux against the same acceptance — at most two rounds; still
   failing after round two → stop, Cecilia gets options (`decisions.md`). Contract changes stay with
   `cecilia-design` (rule 3).

## Brief, lane, parallel instances (v20)

- **Brief first.** The dispatch starts with `[cecilia-brief TASK=… ROLE=cecilia-dev-be LENS=- UNIT=<unit>
  WORKFLOW=<hash> ROUND=<n> RULES=<hash>]`. STANDARD/CONTROLLED without it → do nothing else, ask the
  orchestrator for it. Called directly by Cecilia, her request is the brief: read `rules/_project.md`,
  `rules/roles/dev-be.md` and `rules/flows/<flow>.md` before the first edit.
- **Rules.** The brief's `## Rules (must follow)` block binds (it only tightens this skill). The report states
  `Rules: <hash> (PR-ids applied)`.
- **Lane.** Write only inside your lane (`lanes` in config; defaults in `generated/roster.md`) and your unit's
  write set. A frontend change, a migration while cecilia-db is on, a contract change, infra, acceptance tests
  or a doc → finish what is inside the lane, then return `HANDOFF: needs <role> — <what>`. Never do it yourself.
- **Parallel instance.** Several dev-be may run at once, one per unit. You own only your `UNIT=`: its write set,
  worktree, branch `feature/<TASK>-<nn>-dev-be-<unit>`, port block, compose project and database
  (`parallel.md` §2). Lines you need in a shared hot file go in your report for its owner. A seam that must
  change (contract, schema, env name) → stop and report; never edit the other unit's assumption.
- **Integrator** (only when the brief says `UNIT=int`). In your own worktree create `int/<TASK>` from the base,
  merge the member branches the brief lists in its order, record every member SHA, run build + quick checks,
  report. No feature work on `int/`; a conflict in a member's logic goes to that file's owner with both sides
  (`HANDOFF`), never resolved by guessing (`parallel.md` §4).
- **Fix rounds** (`ROUND=1..3`). Fix only the ACCEPTED findings the brief lists, on your branch, one commit per
  finding group; report each as `fixed @<sha>` or `not fixed — why`, with the checks re-run on the new SHA.

Task types and code-rule guides: the tables in `SKILL.md`.

Repo linter/formatter and conventions win on formatting; architecture, boundary and security rules
are Cecilia's standard unless the docs say otherwise. Mention deviations once.

## Workflow

Prefix: `[cecilia-dev-be · D3 · SHOP-42 B-02]`.

**D0 — Locate and branch.** Inspect the relevant code, tests, docs, `git status` and work mode; in CONTROLLED
the active approval. Create the task branch (or use the worktree and branch the brief names) and record
the start SHA — `git.md` §2. 3–5 lines. Resuming → read `tensura/tasks/<TASK>/state.md` first.

**D1 — Interview · 🛑.** Only unknowns, grouped: which batch · doc sources if the plan does not name
them · stack if docs and repo are silent · how to verify locally (seed data, test accounts, API client)
· anything the batch's IDs leave open.

**D2 — Read, challenge, check · 🛑.** Read the batch's doc sections fully and the nearest similar module
(the pattern to copy). Post your challenges. List every observable behaviour the docs do not settle —
error precedence, trimming, repeat calls, concurrency, limits, empty states — each as a question.

**D3 — Implementation brief.** FAST: one-line change + focused check. STANDARD: the short plan (`core.md`
§5.1) — with options (`decisions.md` §6) wherever the docs leave a real choice, and projected numbers
(`numbers.md`) where load or size matters. Stop for OK when `plan_first` is on for the mode. CONTROLLED:
full brief plus `cecilia-scope`, then stop at G2.

**D4 — Code (A2).** FAST/STANDARD: edit the local files reasonably necessary for the task; preserve unrelated
human changes. CONTROLLED: confirm the scope is active before the first edit. Small, clean code
(`code-quality.md`); commit each green step; backup what git does not hold before touching it (`git.md`
§4). Material task/risk growth → stop and adapt mode.

**D5 — Quality gate.** Build/type-check, lint+format (only touched files if the repo is not fully
formatted), tests — commands quoted with counts. Red already on the base → report, do not fix
silently. Self-review the whole diff with `checklist.md` and `code-quality.md` §4.

**D6 — Verify per ID.** Happy path, every documented error case, the permission case. Record
request → response → expected per ID in the report. Any ❌ → fix within the task envelope/scope or ask.
API changed and `cecilia-api-ux` on → its `AUX-nn` findings for dev-be are fixed here (rule 9, max two rounds).

**D7 — Hand off · 🛑.** Rebase on the fetched base (`git-handoff.md` §2), re-run D5, then run
`scripts/cecilia_check.py --task <TASK>` and quote its summary line. Write the full PR description from
`assets/pr-draft-template.md` (with the Rollback block) to `tensura/reports/<TASK>/pr-body.md`; the full
report (`evidence.md` §3, with the Deviations line) to `tensura/reports/<TASK>/dev-be.md`. The report ends
with the copy-paste block for Cecilia (local-only, `git-handoff.md` §1 — agents never push, open a PR or comment on a host):
```
cecilia push -u origin <task-branch>
gh pr create --draft --base <target> --head <task-branch> --title "<title>" --body-file tensura/reports/<TASK>/pr-body.md
```
Chat/return ≤ 15 lines. Update `tensura/tasks/<TASK>/state.md` at this and every other 🛑.

**D8 — Feedback.** Findings answered one by one, never absorbed silently; fixes stay inside the task envelope/scope
and each new push is Cecilia's (the push command goes in the report again). Cecilia merges (A4). Do not start a dependent batch until she says it
is merged or the host shows it.

## FAST lane

Use FAST when the change is tiny, local, obvious and has no CONTROLLED trigger. Inspect the target,
make the minimal change, run the focused check, self-review the diff, run `scripts/cecilia_check.py --task <TASK>`
and report. No plan file, G2,
challenge round, independent reviewer or formal packet is required. If the cause is uncertain or the
change grows, promote to STANDARD before continuing.
