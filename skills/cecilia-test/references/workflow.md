# cecilia-test — full rules and workflow

The SKILL card holds the summary; this file holds the detail. Open it at the first step on STANDARD/CONTROLLED work.
From STANDARD every tester runs with one **lens** (brief header `LENS=<lens>`); the shared lens rules are §Lenses
below, the lens's own scope and techniques are `references/lenses/<lens>.md`.

## Authority (detail)

| Free (A0/A1) | FAST / STANDARD A2 | CONTROLLED A2 | A3 / A4 boundary |
|---|---|---|---|
| read code/docs/results; draft test plan/cases/reports | write relevant local test code/fixtures/config under the task envelope; run local/disposable tests | only approved test paths/commands/environments | A3: staging/shared load/security tests, dependency install. A4: push/PR (local-only, `git-handoff.md` §1 — write the commands for Cecilia), production/real customer data, product-code changes, secrets/IAM, merge/release |

FAST may simply run/add the focused regression check. STANDARD uses the coverage needed for the
requested behavior. CONTROLLED uses pinned SHA evidence and exact scope.

## Golden rules (detail)

1. **Independent.** Do not test code you wrote in this run. If that cannot be avoided, label it
   `[self-tested]`; it does not count as independent evidence for G3.
2. **Docs are the oracle.** Every case cites an `AC`/`FR`/`BR`/error code/`NFR`. Code and docs disagree
   → a finding (bug or doc issue), never an assertion of what the code does.
3. **Missing expected behaviour → ask**, with options. Never invent the expected result.
4. **Challenge the oracle first**: 2–4 objections — an AC with no negative case, an error code no flow
   can produce, a rule two requests can break at once.
5. **Trustworthy tests**: deterministic, isolated, synthetic data, no sleeps as synchronisation, no
   real external services unless the level needs it and Cecilia approved the environment.
6. **Never hide a failure.** Flaky → at most two reruns, every attempt reported. A product-bug test
   stays failing unless Cecilia decides to mark it with the framework's expected-failure pointing at
   the `BUG`.
7. **Pin what you tested**: source SHA (or integrated candidate), contract version, environment,
   fixtures, tool versions. A result belongs to that revision only.
8. **Needs something that does not exist** (an environment, a seeded DB, a container, a pipeline step)
   → a request to `cecilia-devops` or Cecilia in the report, never a change you make yourself.
9. **Test code is code** — task branch (`git.md`), `code-quality.md`, own ports and test database when
   running beside other roles (`parallel.md` §2). Performance and capacity checks compare measured
   numbers with the NFR and with the `[projected]` figures they were designed from (`numbers.md`).
10. **UI is tested where users see it.** Frontend cases run in the browser `ui.browser` names
    (`visual-check.md`), each state driven from the contract, with a screenshot per case and the console
    checked; the browser session is your own (`-s=<member>`). Automated E2E suites stay in the repo's
    framework (e.g. `@playwright/test`); the CLI is for exploring and evidence.

Modes and their guides: the table in `SKILL.md`.

## Lenses (v20)

Seven lenses, one guide each: `references/lenses/<lens>.md` (functional, integration, concurrency-perf,
security, ui, database, infra); "when to pick" is in `shared/generated/lenses.md`. The orchestrator picks
lenses in the chosen workflow option; several testers run at once, one lens (and one unit) each.

1. **Read the header.** `[cecilia-brief TASK=… ROLE=cecilia-test LENS=<lens> UNIT=<unit|-> WORKFLOW=… ROUND=<0-3> RULES=<hash>]`.
   `LENS=-` (FAST or a v19-style brief) → no lens: T0–T7 as below, report `test.md`. Unknown lens → stop and ask.
2. **Rules first.** Read the brief's `## Rules (must follow)` (project, `rules/roles/test.md`, flow and
   `rules/lenses/<lens>.md`); they tighten this skill, never loosen A3/A4.
3. **Stay in the lens.** Design, write and run only what the lens guide covers. A risk you notice outside
   it → one line `HANDOFF: needs cecilia-test LENS=<lens> — <what>` in the report, not a test you write.
4. **Own files.** Test files in a lens-owned place: `<repo test root>/<lens>/…`, or the repo's co-located
   convention with the lens as suffix (`*.<lens>.spec.ts`, `test_<area>_<lens>.py`). Never edit another
   lens's files; a shared helper/fixture change → `HANDOFF` to the orchestrator (one lens will own it).
5. **Own environment.** Ports, compose project `-p <TASK>-test-<lens>`, DB `<db>_test_<lens>`, cache dir
   and browser session `-s=test-<lens>` from the brief's RUNTIME block (`parallel.md` §2). Start what you
   need, stop it before reporting.
6. **Lane.** Writes only inside the test lane (`lanes` in config; `shared/generated/roster.md`) and
   `tensura/reports|tasks|backups/<TASK>/`. Product code, migrations, IaC, CI config, `.env` are never
   yours — a failing check there is a `BUG` plus `HANDOFF: needs <role> — <what>`. The guard denies
   writes outside the lane; do not look for another way.
7. **Report** `tensura/reports/<TASK>/test-<lens>.md` from `assets/test-lens-report.md`: header with
   SHA and counts, lens coverage table, the **BUG table** `| ID | Title | Severity | Repro | Evidence |`
   with ids `BUG-<lens>-nn` (stable across rounds, never renumbered), severity on the fix-loop scale
   (Critical/High → BLOCKER, Medium → SHOULD-FIX, Low → SUGGESTION). `workflow.py merge-tests` merges
   every lens file into `test-summary.md`; keep the header and 5 columns exact. A Critical/High bug also gets its
   own file (`references/bug-report.md`).
8. **Fix rounds** (`ROUND=1..3`). Only the lenses that had open bugs, or whose area the fix touched, are
   re-dispatched. At the new SHA: re-run the lens suite, fill the **Re-test** table
   (`VERIFIED` / `REOPENED` / `STILL_OPEN` per `BUG-<lens>-nn`), add new bugs the fix introduced. The BUG
   table lists only what is open at this SHA.
9. **End lines.** The report ends with `Rules: <hash> (PR-ids applied)` and, when the lane stopped you,
   `HANDOFF: needs <role> — <what>`.

## Workflow

Prefix: `[cecilia-test · T2 · SHOP-42 B-01]`. At every 🛑, update `tensura/tasks/<TASK>/state.md`.

**T0 — Locate.** `git fetch`; task branch or the brief's worktree (`git.md` §2); plan row and dependencies, SRS ACs, LLD, contract, `test-plan.md`,
dev reports (including manual verification), review reports, open `BUG`s, existing test cases, the
target branch/SHA, selected work mode and, in CONTROLLED, whether the batch scope is approved. 3–5 lines. Target not stable yet → case design
may proceed; execution waits.

**T1 — Interview · 🛑.** Only unknowns, grouped: scope (batch, IDs, PR/SHA) · levels for this task ·
environment (local containers, test DB, accounts, seed data) · frameworks if the repo has none ·
severity policy if no test plan · NFR numbers and whether any shared environment is approved.

**T2 — Test design · 🛑.** Backend against the contract and LLD, frontend against every state in
`<app>-frontend.md`, security controls against `security.md`. Build `tensura/reports/<TASK>/test-cases-<area>.md`
with `references/test-design.md` (boundaries, errors, races, repeats, permissions; traceability).
In CONTROLLED, show the test paths for the `cecilia-scope` block. In FAST/STANDARD, a concise test plan is enough if
the plan did not include them. Wait.

**T3 — Write tests (A2).** In CONTROLLED confirm the scope is active; FAST/STANDARD need no G2; write tests per `references/test-levels.md`,
branch/commits per `git.md` if allowed.

**T4 — Run and triage.** Relevant suites and the full existing suite. Each failure, with evidence:
test bug (fix the test) · product bug (`BUG-nn` via `references/bug-report.md`) · doc ambiguity (ask)
· environment/flaky (≤ 2 reruns, reported).

**T5 — Run report.** With a lens: `tensura/reports/<TASK>/test-<lens>.md` (§Lenses 7). Without: `tensura/reports/<TASK>/<date>-test-run-<topic>.md`: SHA/candidate, environment,
commands, passed/failed/skipped/blocked/flaky with denominators, ACs covered and uncovered, perf vs
NFR, bugs, limitations.

**T6 — Check and hand off · 🛑.** Rebase, re-run, PR text from `assets/pr-draft-template.md` (ID → TC →
test file) into `tensura/reports/<TASK>/pr-body.md` (with a lens: `pr-body-test-<lens>.md`, merged by the orchestrator). Run `scripts/cecilia_check.py --task <TASK>` and quote its
summary line. Full report to `tensura/reports/<TASK>/test.md` (links the run report; with a lens, `test-<lens>.md` only — `merge-tests` writes `test.md`); chat/return ≤ 15 lines;
update `tensura/tasks/<TASK>/state.md`. Push and Draft PR are Cecilia's (local-only, `git-handoff.md` §1): write the exact
push and `gh pr create --draft … --body-file tensura/reports/<TASK>/pr-body.md` commands in the report. Agents never
push, open a PR or comment on a host.

**T7 — After merge.** Update the row, tell plan and dev about open bugs.

**Blocks G3** whenever a required check is failing or unrun. The exception route is a written risk
decision by Cecilia, carried in the G3 packet — never a reclassified skip.
