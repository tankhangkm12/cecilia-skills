# Planning method

## 1. Hierarchy

```
Epic E-01  (one business capability)
└── Batch B-01  (= one reviewable PR per role output; one-sentence goal; repo green after merge)
    ├── BE-B01     implement IDs …            → feat-be/<TASK>-01-<desc>   (scope SHOP-42-B01)
    ├── FE-B01     implement SCR …            → feat-fe/<TASK>-01-<desc>   (scope SHOP-42-B01)
    ├── TEST-B01   independent tests for IDs  → test/<TASK>-01-<desc>      (scope SHOP-42-B01)
    ├── REV-B01-C  review BE/FE PRs           → review report (read-only, no scope)
    ├── REV-B01-T  review TEST-B01            → review report
    ├── OPS-B01    delivery path (only if needed) → ci/ or infra/<TASK>-<desc>
    └── REV-B01-O  review OPS-B01             → review report
```

Default sequence inside a batch (propose it; Cecilia may change it):
`G2 (scope approved) → BE ‖ FE (against the contract mock) → integration candidate → TEST (cases
designed in parallel, run on the candidate) → REV → G3 packet → Cecilia merges → [OPS → REV(infra) →
A3 applies to non-prod → rollback rehearsed] → batch DONE`.
Alternatives to offer: test-first (TEST writes failing acceptance tests from the docs before dev) ·
review only at epic end (cheaper, later feedback). Do not force product code to merge before its
regression tests just to preserve a role order — dependent PRs or one combined branch are fine if the
repo allows them.

Every batch ends with its `cecilia-scope` block (`common/core.md` §5.2): the union of its writing tasks'
paths, the commands they run, `environments: ["local"]` unless Cecilia asks for more.

**When a batch gets an `OPS-Bnn` row** — plan it, do not assume it: a new service or deployable unit ·
a new env var, secret name or config key · a new external dependency to run (DB, broker, cache) ·
a migration that must run in a real environment · a new build/test step CI must execute · new
monitoring or alerting the docs require (`NFR-nn` on uptime, latency, cost). None of these → no OPS
row; say so in the plan so nobody looks for one. Infrastructure work with no application batch behind
it (pipeline rebuild, cluster upgrade, cost work, incident follow-up) is its own batch with only an
`OPS-Bnn` row.

`OPS-Bnn` never contains application source changes. Delivery path needs an app change (a readiness
handler, a config key read) → that is a `BE-Bnn` or `FE-Bnn` row in the same batch, sequenced before OPS, per the
ownership table in `cecilia-devops`' SKILL.md ("Path ownership"). If cecilia-devops is not
in use on this project, keep the OPS row and name Cecilia (or the person who owns delivery) as owner.

## 2. Cutting batches

- **Reviewable in one sitting.** Guideline: a PR a reviewer can read in one pass. If a batch covers
  too many IDs or files, split it. No time estimates — describe size by IDs and expected files only.
- **Green after merge on its own:** build, lint and existing tests pass; no half-feature that breaks
  the build. Use feature flags only if tensura/docs/Cecilia allow.
- **One purpose per batch**; never mix refactor with feature.
- Typical order (docs and architecture decide): schema/migration → domain/model → service/use case →
  API/handler → UI → integration/cross-module wiring.
- **An OPS row depends on the code it delivers** (`OPS-B02 needs BE-B02 MERGED`), and a batch that
  cannot be verified without a running environment depends on the OPS row that provides it — say which
  way round it is, and never leave both waiting on each other.
- **A `DOC-Bnn` row whenever the batch changes what a document says** — a decision taken mid-batch, an
  ACCEPTED challenge, a review doc-issue. Owner: design. It blocks the batch's `DONE`, not its PRs.
- **Parallelism needs separate worktrees.** Mark `Parallel: yes` only when the two tasks will run in
  separate git worktrees (or by different people), against a frozen contract, with disjoint paths
  (`common/parallel.md` §2). Say whether the host was smoke-tested for parallel writers; if not, the
  column describes independence, not speed.
- **Dependencies** explicit (`B-03 needs B-02 merged`). Parallel only when no dependency AND expected
  file lists do not overlap (shared registries, routers, DI modules, migration index, lock files,
  i18n files count as overlap).
- Every requirement ID lands in exactly one batch (or explicitly out of scope). Sum of batches = full
  traceability table.
- Cross-cutting prerequisites the docs require (error catalog, envelope interceptor, config module)
  become their own early batch if missing in the repo.
- **Local-only handoff.** No batch has a push, PR or host-comment step for an agent; the final batch
  ends with the push + `gh pr create --draft … --body-file …` commands for Cecilia (`common/git-handoff.md` §1), and
  the plan names `tensura/tasks/<TASK>/state.md`.
- Out-of-doc work (refactors, perf, bugs found) is never planned silently; it goes to "Proposals" with
  options until Cecilia approves.

## 3. What each task row must contain

| Field | Rule |
|---|---|
| ID | `DB-B02`, `BE-B02`, `UI-B02`, `FE-B02`, `TEST-B02`, `REV-B02-C`, `REV-B02-T`, `OPS-B02`, `REV-B02-O`, `DOC-B02`, `DSC-B02`, `DSG-B02` |
| Role | db / dev-be / ui / dev-fe / test / review / devops / design (doc tasks) / discovery (as-built tasks) — only roles on in `.cecilia/config.json`; an off role's rows go to its fallback owner (`workspace.md` §1) |
| Confidence | brownfield only: the label of the docs this task stands on — `[verified]` tasks are planned normally, `[inferred]` tasks carry the risk, `[unknown]` tasks are blocked until answered |
| Repo | only when the epic spans several repos: which repo, and the merge order among the batch's PRs |
| Covers | requirement IDs + doc sections |
| Inputs | docs sections, prior batch outputs |
| Expected files | exact paths or `dir/**` — they become the scope block (for overlap detection and the guard) — test tasks list test paths, ops tasks list pipeline/manifest/IaC paths |
| Branch | repo convention, else `common/git.md` (`feat-be/` `feat-fe/` · `test/` · `ci/` or `infra/`) |
| Environment | ops tasks only: target `ENV-nn` and whether production is in scope (default: no) |
| Depends on | task IDs |
| Parallel | yes/no (+ with which) |
| Done when | concrete: PR merged / report written with no Blocker open / TCs executed |
| Owner | agent or person name, filled when claimed |

## 4. Status values (shared with all roles)

`TODO` → `IN_PROGRESS` → `READY_FOR_REVIEW` → `READY_FOR_CECILIA` (G3 packet) → `MERGED` → `DONE`, or `BLOCKED: <reason>`.
Review tasks: `TODO` → `IN_PROGRESS` → `REPORTED (blockers: n)` → `DONE` (no open Blocker).
Ops tasks add `APPLIED (<ENV-nn>)` between `MERGED` and `DONE`; `DONE` requires the rollback to have
been rehearsed and recorded, not only the PR merged.
Claiming: a role sets `IN_PROGRESS | <agent name> | <date>` on its own row before starting.

## 5. Docs written by others

Record each source with path/link, version or commit, date read. External docs (Notion, Drive, PDF)
can change silently → note it in risks and re-check before each batch starts (Track mode does this).
