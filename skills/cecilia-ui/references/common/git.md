# Git flow, checkpoints, backup and rollback (common v20)

<!-- common v20 — canonical copy in shared/, synced into every skill by tools/sync_common.py. Do not edit a copy. -->

Every change is made so that Cecilia can undo it at any moment. Git is the backup for everything it
tracks; `tensura/backups/` is the backup for what it does not.

## 1. Branch model

`git.model` in `.cecilia/config.json`: `auto` (default) · `gitflow` · `github`. The repository's own
convention (CONTRIBUTING, `git branch -r`, history) wins; note it once in the report.

| Model | Long-lived | Task branches from | Merge target |
|---|---|---|---|
| **gitflow** (`auto` picks it when `develop` exists, or the repo has no convention yet) | `main` (released), `develop` (integration) | `develop`; `hotfix/*` from `main`; `release/*` from `develop` | `develop` (hotfix → `main` and `develop`) |
| **github** (`auto` picks it when there is only `main`/`master`) | `main` | `main` | `main` |

Task branch names — `<type>/<TASK>-<nn>-<desc>`:

| Type | For |
|---|---|
| `feature/` | a batch of new behaviour (any role: backend, frontend, db, infra) |
| `bugfix/` · `hotfix/` | a fix · an urgent fix to released code (gitflow: from `main`) |
| `refactor/` · `test/` · `docs/` · `ci/` · `infra/` · `chore/` | as named |
| `int/<TASK>` | local only: merge of a parallel wave's branches for combined tests (`parallel.md` §4) |
| `backup/<TASK>-<n>` | local only: a named checkpoint before a risky rewrite (§3) |

Parallel writers on one task use one branch each, per role and unit: `feature/SHOP-42-01-dev-be-order`,
`feature/SHOP-42-01-dev-be-payment`, `feature/SHOP-42-01-dev-fe-web`.

In the `team` flow the branch name follows `flows.team.branch_pattern` (e.g. `feature/{ticket}-{slug}`) and
every commit subject must match `flows.team.commit_pattern` (`flows/team.md`); that replaces the defaults
here where they differ.

Never create `develop`, `release/*` or any branch on the remote (A4 — Cecilia creates remote branches). Creating `develop`
locally for a repo that has none is a decision — ask once, record it as `D-nn`.

## 2. Before the first edit — every task, every mode

```
git status --porcelain            # unrelated changes? → ask; never stash or commit Cecilia's work silently
git fetch                         # A0
git switch -c <task-branch> origin/<base>     # or from local base if there is no remote
git rev-parse HEAD                # record: start SHA  → report "Rollback" section
```

The guard refuses edits on protected branches, on a detached HEAD and outside a git repository (while
`git.require_task_branch` is true). Worktrees for parallel roles are created the same way:
`git worktree add .worktrees/<role>-<scope> -b <task-branch> <base>`.

## 3. Checkpoints during the work

- **Commit per step** — one logical change, builds, passes its focused test:
  ```
  <type>(<scope>): <imperative summary> [<TASK>]

  <why; requirement IDs / doc sections>
  ```
  Types: `feat fix refactor perf test docs chore build ci style`. Never commit secrets, `.env`, build
  output, dumps or commented-out code. Never `--no-verify` — a failing hook is fixed or reported.
- **Before a risky rewrite** (large refactor, rebase, generated-code regeneration, mass rename): create
  `git branch backup/<TASK>-<n>` at the current commit. Local, instant, deletable later (A3 if unpushed
  work would be lost).
- After Cecilia has looked at a PR, add commits; do not rewrite reviewed ones.
- Committing is local and reversible: A2. If the plan says Cecilia commits herself, leave changes
  uncommitted and list them.

## 4. Backup of what git does not hold

Before changing anything git cannot restore — take the backup, check it exists and is non-empty, record
it, then proceed:

| Thing | Backup | Restore command in the report |
|---|---|---|
| local database (migration, data fix, seed reset) | `pg_dump -Fc` / `mysqldump --single-transaction` via `docker compose exec` into `tensura/backups/<TASK>/<db>-<time>.dump` | `pg_restore --clean -d <db> <file>` / `mysql <db> < <file>` |
| a git-ignored or generated file you will overwrite (local config, fixtures) | copy to `tensura/backups/<TASK>/` | `cp` back |
| Penpot/Figma page you will change heavily | export the page/board first into `tensura/backups/<TASK>/` | re-import or redraw from export |

`tensura/backups/` must be git-ignored (dumps can hold personal data); check `.gitignore` and ask Cecilia
to add it if missing. Shared/staging data is backed up only by Cecilia or devops through an approved A3
action; production is Cecilia's (A4).

## 5. Rollback — always written, never improvised

Every report ends its evidence with:

```
Rollback: branch <task-branch> from <base>@<start-sha>; commits <sha1..shaN>
  undo all, keep history:   git revert --no-edit <start-sha>..HEAD
  discard the branch (A3):  git switch <base> && git branch -D <task-branch>
  back to a checkpoint (A3): git reset --hard <sha>
  data:                     <restore command from §4, or "none touched">
```

Running a rollback that discards work is A3; reverting a merged change on a protected branch is A4
(Cecilia merges the revert).

Handing work over (local-only, rebase, PR text, commands for Cecilia): `git-handoff.md`.
