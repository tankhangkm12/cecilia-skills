# Git hand-off — local-only, rebase, PR text (common v20)

<!-- common v20 — canonical copy in shared/, synced into every skill by tools/sync_common.py. Do not edit a copy. -->

Open at the hand-off step. Branches, checkpoints, backup and rollback: `git.md`.

## 1. Local-only: nothing leaves the machine from an agent

Everything an agent does stays local — commits, task branches, `tensura/`, `.cecilia/`, `rules/`, worktrees.

- **Workspace mode (default):** every Cecilia file lives in the workspace next to the project
  (`<project>.cecilia/`, `workspace.md` §2.4). The project holds **nothing** of Cecilia's — no `tensura/`, no
  skills, no hooks, and no entries in `.git/info/exclude`; there is nothing to exclude and nothing to leak.
  Worktrees for parallel writers live in `<workspace>/.worktrees/`.
- **In-project layout (legacy option):** older installs keep `tensura/`, `.cecilia/`, `.worktrees/` and the
  skills inside the project; those paths are then listed in `.git/info/exclude` and never committed.

In both, the optional push lock (`cecilia push-lock on`, Cecilia's command) makes every `git push` from the
project fail until Cecilia runs `cecilia push …` herself.

A4 for agents (the guard denies them): `git push` in any form · creating/deleting remote branches or tags ·
opening, editing, approving, merging a PR/MR · review comments · releases · changing remotes, push URLs or
`pushInsteadOf` · `git add -f` of an excluded path.

Allowed: `git fetch` (A0) · read-only `gh pr view --comments` / `gh api` GET of a PR (A0) · `git pull` /
`git merge origin/…` (A3 — changes the working tree).

What the agent does instead — in the report, as a copy-paste block for Cecilia, with **absolute paths** (she may
run it from any folder; `gh` must run inside the project):
```
cecilia push -u origin <task-branch>
cd "<project>" && gh pr create --draft --base <target> --head <task-branch> --title "<title>" --body-file "<workspace>/tensura/reports/<TASK>/pr-body.md"
```
Before handing over, confirm no Cecilia file is staged or committed (`scripts/cecilia_check.py --task <TASK>`
checks it). The active flow shapes the hand-off (`flows/<flow>.md` § handoff): `personal` → the commands above;
`team` → branch, commit and PR-body rules from `flows.team`, PR size limit, stacked PRs when too big.

## 2. Rebase before a Draft PR

`git fetch` → `git branch backup/<TASK>-<n>` → `git rebase origin/<target>`. Per conflict read both
sides and the commit that caused the other side; keep both changes by default; never take ours/theirs
for a whole file blindly. Semantic conflict (both sides change the same behaviour, or the other side
contradicts the docs) → `git rebase --abort` and ask. Lockfiles: take the target's, regenerate.
Migration numbering clash: renumber **yours**, never a merged one. Re-run the quality gate after.

## 3. Draft PR content

Write the full description from the role's PR template (`pr-draft-template.md` in its assets; in the `team`
flow the project's template at `flows.team.pr_template` wins) to
`tensura/reports/<TASK>/pr-body.md`, including the Rollback block. Hand Cecilia the push and
`gh pr create --draft … --body-file …` / `glab mr create --draft …` commands (§1); she runs them. No reviewers
unless she names them.

Review feedback (Cecilia pastes or points to it; in the `team` flow the agent may read it with read-only
`gh pr view --comments` / `gh api` GET): one new commit per group of comments; never reply on the host;
feedback that contradicts the docs is asked about, not applied. Do not start a batch that depends on
this PR until Cecilia says it is merged or the host shows it merged.
