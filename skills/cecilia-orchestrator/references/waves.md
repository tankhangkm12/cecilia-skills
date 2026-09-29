# Computing the waves (v20)

A **wave** is a set of role agents launched together because none can invalidate another's
assumptions (`common/parallel.md` §2–3). The grouping is computed from written inputs — the
ownership table (`common/workspace.md` §1), the plan's exact paths and the approved scopes — not
argued from intuition, because intuition is what lets two agents overwrite each other.

## 1. The algorithm — at O1 for every option, and again whenever the units change

1. **Units.** One unit per role *per scope*: dev-be on B-01 and on B-02 are two units; three test agents
   on three lenses are three units. Several instances of one role are normal (3 × dev-be on disjoint
   modules, 5 × cecilia-test on different lenses); each unit gets its own brief (`--unit` / `--lens`).
2. **Read and write sets as paths.** From the plan's rows and the scope blocks — `src/order/**` and
   `web/src/order/**`, not "backend" and "frontend". A unit whose write set cannot be written as paths
   is not ready: that is a plan gap.
3. **Dependency edges.** B depends on A when B reads what A writes. Plus the fixed edges:

   | Edge | Why |
   |---|---|
   | everything → discovery | the truth and the requirements settle first |
   | dev-fe, design(frontend) data wiring → design(backend) contract | the contract is the seam |
   | db (schema) → design(backend) module design | the schema implements the module design |
   | dev-be data access → db schema/migrations for its batch | code built on a schema still moving breaks |
   | ui → design(frontend) screen list, when that doc exists | states and SCR ids come from it |
   | dev-fe screens → ui design for those SCR | dev-fe builds what was designed, not a guess |
   | any writer → an approved scope for its batch | no G2, no code |
   | test (execution) → the dev units it tests | the code must stop moving |
   | review → every writer of its target | a moving target is worthless to review |
   | review(verify) → the packet or briefing it checks | verify reads a finished draft |
   | devops apply → everything in flight | the environment moves under everyone |

4. **Wave 1** = units with no unmet dependency; each next wave = units whose dependencies are all in
   earlier waves.
5. **Split for disjointness.** Compare write sets pairwise inside the wave; any overlap moves one unit
   to the next wave (prefer the one fewer later units depend on). Re-check after each move.
6. **Exclusions path comparison cannot see:** no writer beside its reviewer · a role that is off in
   `.cecilia/config.json` is never a unit · a devops apply is alone
   in its wave · discovery is alone in its wave · plan is alone in its wave · two units rewriting any
   shared file never share a wave (append-only logs are written by the orchestrator anyway).
7. **Isolation.** Code writers: one git worktree each at `<root>/.worktrees/<role>-<scope>/`.
   Document writers: the main checkout, their own files only. Read-only units: nothing.
8. **No configured cap** (`parallel.limits.* = null`, v20): the chosen option sets how many agents run;
   only the host limit applies (Claude Code: 20 concurrent) and a legacy `parallel.max_writers` in a user
   config still caps dev units. Assign each code writer its branch, port block, compose project and DB name.
9. **Write the proof** for every wave with more than one member. No proof → the wave is wrong; go back
   to step 5.

`scripts/workflow.py options` refuses overlapping write sets inside one wave of a `module`/`layer` split;
the optional helper `scripts/workflow.py plan-waves <tasks.json> --resources` does steps 3–5 mechanically
(cycles, path overlap, port blocks). Neither understands meaning; the plan still has to be right.

**Competing units** (split `competing`) build the same seam two ways on separate branches in the same wave;
their write sets overlap by design, so they are never merged together — the 3 review voters vote
which one to keep (`consensus.md`; a tie or veto goes on Cecilia's card) and only that branch goes into `int/<TASK>`.

## 2. The proof, verbatim in the O2 table

```
W<n> parallel — <contract name> v<version> (<hash>) frozen (<D-nn>, <date>)
  write lists compared <date> — disjoint (<unit>: <paths> · <unit>: <paths>)
  scopes active — <task ids> (approved <date> by Cecilia)
  isolation — <unit>: <worktree path> · <unit>: <worktree path>
```

Never write: *"they don't really overlap"* (compare paths or serialize) · *"the contract is basically
stable"* (frozen = a decision id and a date) · *"we'll sort out conflicts at merge"*.

## 3. When Cecilia serializes

She may split any wave, for any reason, including one she does not give. Record it in the run log and
do not propose the merge again in this run. Split, never merge: the orchestrator may always run a
wave's members one at a time; it may never put together what the algorithm separated.

## 4. Degrading

| Missing | Effect | Say once |
|---|---|---|
| Sub-agent tool | members run as separate sessions from brief files, never by you (`references/fallback.md` §3) | the wave numbers still say what depends on what |
| `git worktree` or not a git repo | code writers serialize | document writers and read-only units may still share a wave |
| Guard not installed | scope is procedural | the first report lists which limits are PROCEDURAL |

## 5. Waves that are wrong

| Wave | Why |
|---|---|
| dev-be ‖ dev-fe before the contract is frozen | both are guessing at the seam |
| dev-be ‖ review of that same code | the reviewer reads a moving target |
| test (running) ‖ dev on the same batch | results describe a state that no longer exists |
| tests on member branches when there is an `int/<TASK>` | the combination is what ships; test the integration SHA |
| two dev-be units in one module | they collide in the router and DI module every time |
| db migrations ‖ dev-be on the same tables | code and schema move under each other |
| ui ‖ dev-fe on the same SCR | the picture changes while it is being built |
| any wave containing a devops apply with others | the environment moves under everyone |
| plan ‖ anything it plans | the plan is the input the others read |
| a writer whose batch has no active scope | nothing it writes is approved |
