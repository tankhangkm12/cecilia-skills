# Reviewing an execution plan

The plan is the contract dev, test, review and devops execute against. A defect here is not caught by
any later gate — every role executes it faithfully and the damage shows up as rework across several
PRs. Judge it against the documents it claims to plan from, never against taste.

Inputs: `tensura/plans/<TASK>-<slug>.md`, the documents it cites (read them, do not trust the plan's
summary of them), the repo structure, `tensura/reports/<TASK>/README.md` and `challenges.md`, and the
current state of any batch already running.

## 1. Axes, heaviest first (report in this order)

1. **Traceability is complete both ways.** Every in-scope requirement id from the docs appears in
   exactly one batch, or in "out of scope" with a reason. And in reverse: every task in the plan cites
   an id that exists in the docs — a task tracing to nothing is invented work. Check the sum, not a
   sample: list the ids in the docs, the ids in the plan, and the difference in both directions.
2. **Batch independence.** Each batch, merged alone, leaves the repo green: it builds, existing tests
   pass, and it contains no half-feature that only works once a later batch lands. A batch that needs
   a later one to compile is a dependency the plan is hiding.
3. **Dependency order is real and acyclic.** Follow each `depends on` to the batch that produces what
   it needs. Look for: cycles · a dependency on something no batch produces · a test task that depends
   on code merged in a batch scheduled after it · an `OPS-Bnn` that depends on a deploy target nobody
   creates · a `DOC-Bnn` that blocks a batch it is inside.
4. **Parallel claims survive the file lists.** Two tasks marked parallel must not share expected files
   — and the usual collisions are the ones people forget: DI modules, routers, migration sequence, lock
   files, i18n bundles, shared enums, the error catalog, the plan's own status table. Also check the
   plan says which mode it is written for: separate working trees, or a single orchestrated workspace
   where parallelism does not exist.
5. **Every role the work needs has rows.** Delivery-path work with no `OPS-Bnn` (a new deployable, a
   new env var or secret name, a migration to run in an environment, a CI step, monitoring an `NFR`
   requires). Behaviour changes with no `TEST` row. Decisions that changed a document with no
   `DOC-Bnn`. A batch with no review row where the change is CORE.
6. **Batch size is reviewable.** One purpose per batch; no refactor mixed into a feature; a PR a
   reviewer can read in one pass. Oversized batches are where review quality silently dies.
7. **Doc issues were settled, not deferred.** The plan's decisions table shows each gap, ambiguity or
   contradiction found in the docs and how it was resolved, with who decided. An item still marked
   open while the batch depending on it is scheduled to start is a Blocker.
8. **`[agent-chosen — needs review]` items** anywhere in the plan or the decisions it cites, unconfirmed
   while work is planned on top of them.
9. **Status honesty.** Rows claiming `MERGED`/`DONE` that the git host or the reports contradict; rows
   `IN_PROGRESS` with no owner or no recent report; an ops row `MERGED` but never `APPLIED`; a batch
   `DONE` with an open `DOC-Bnn` or an open Blocker in a review report.
10. **Branches and conventions** follow the repo, else `common/git.md`; base branch stated.
11. **Scope blocks are sound.** Every batch has a `cecilia-scope` block; its `write` list covers every
    path the batch's tasks name (including lockfiles, generated clients, registries) and nothing more;
    its `commands` are local; `environments` is `["local"]` unless Cecilia asked otherwise; no block
    grants `.cecilia/`, hook, permission or CI-protection paths.
12. **Cross-repo work is expressible.** If the epic spans repos, each batch names the repo per row and
    the merge order between its PRs; otherwise "green after merge" has no meaning.
13. **No time estimates** (Cecilia's rule) and no task that is really a decision in disguise
    ("investigate whether…" is a question for her, not a batch).

## 2. Severity

| Level | Meaning | Examples |
|---|---|---|
| **Blocker** | executing this plan produces rework or a broken repo | a requirement in no batch · a dependency cycle · a batch that cannot be green alone · parallel tasks sharing a migration or DI file · a batch scheduled on an unresolved doc contradiction · a root cause or fix premise stated as fact with no `[verified]` evidence (the plan must measure first) · a destructive or recovery step without a tested rollback |
| **Should-fix** | works, but costs later | oversized batch · missing `DOC`/`TEST` row for a real change · stale status rows · vague "done when" |
| **Suggestion** | ordering or grouping that would read better |
| **Question** | cannot judge without context | "is `payments` in this epic's scope at all?" |

## 3. Finding format

```markdown
### P-1 · Blocker · `tensura/plans/SHOP-42-cancel.md` §6 · Dependency order
- **Problem:** TEST-B02 depends on DEV-B02 MERGED, but B-02 is scheduled before B-01, and DEV-B02
  imports the error catalog created in DEV-B01.
- **Failure scenario:** the test agent starts, the branch does not compile, it reports BLOCKED, and the
  batch has to be re-cut mid-run — after the dev PR is already open.
- **Evidence:** plan §5 order table; plan §6 expected files for DEV-B01 lists `src/common/errors/**`,
  which DEV-B02 imports per LLD §3.2 [verified]
- **Suggested direction:** either move the error catalog into B-02, or make B-01 a prerequisite batch.
```

## 4. Also report

- **Coverage table:** `requirement id · batch · role tasks · status` — the whole set, so the gap is
  visible rather than asserted.
- **Dependency graph** as ASCII, if the plan has more than three batches.
- **What this plan does not cover**, stated plainly: requirements deferred, roles absent, environments
  untouched.
- **Good:** 1–3 specific things worth keeping.

## 5. Re-reviewing after the plan changes

Read the plan's "Plan changes" table first, then verify only what moved — plus the two things a plan
edit breaks most often: traceability (an id dropped when a batch was re-cut) and dependency order (a
batch moved earlier than what it needs).
