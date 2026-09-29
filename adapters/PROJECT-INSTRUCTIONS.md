# Cecilia v18.1 — project instructions (paste into CLAUDE.md and/or AGENTS.md)

This project uses the Cecilia v18.1 skills (`cecilia-orchestrator`, `cecilia-discovery`, `cecilia-design`,
`cecilia-plan`, `cecilia-db`, `cecilia-dev-be`, `cecilia-dev-fe`, `cecilia-ui`, `cecilia-test`,
`cecilia-review`, `cecilia-devops`). Every skill starts from its `references/common/core.md`.
`.cecilia/config.json` says which roles are on and how this project works; never edit it — the user does.

- **The user decides.** Real choices come as ≥ 3 researched options on the same criteria, with numbers
  and a separate recommendation. Search the web for versions, library behaviour and existing solutions
  before proposing. Numbers are measured or computed (`scripts/capacity.py`), never guessed.
- **Plan first.** STANDARD and CONTROLLED show a short plan (steps, branch, files, checks, backup, stop
  condition) and wait for OK before editing (`plan_first` in the config). FAST may act directly.
- **Git flow, always.** Edit only on a task branch (`feature/…`, `bugfix/…`, `hotfix/…`), never on
  `main`, `develop`, `release/*` or a detached HEAD; record the start SHA; commit per step; back up what
  git does not hold (local DB dump, ignored files) into `tensura/backups/` before changing it. Every report
  ends with a Rollback block and a `Deviations:` line.
- **Parallel when independent.** Work that writes different files and shares only settled seams runs at
  the same time, each in its own worktree/branch/ports/DB, then is integrated and tested together.
- **See the UI before calling it done.** Frontend changes are opened in the browser `ui.browser` names
  (Playwright CLI by default, local pages only, own session), every state and breakpoint captured,
  contrast and pixel difference measured (`scripts/uikit.py`), checked against the web interface
  guidelines. A style guide (`ui.style`) only fills what the approved design leaves open.
- **Small, clean code.** Minimal diff, no dead or duplicated code, reuse what exists, optimise only
  measured hot paths.
- Anything that leaves the machine, costs money, touches a shared/live system, installs dependencies,
  deletes data, pushes, opens PRs/comments or applies migrations to a shared database is **A3**: show
  the exact action and wait for yes for that action (several may be listed in one numbered message).
- Never merge into protected branches, mutate production, change IAM, handle raw secrets, publish a
  release or force-push a shared branch — **A4**, the user does it.
- A guard or permission refusal is the system working. Report it; do not work around it.
- Docs live under `tensura/docs/` in the `docs_layout` the config names. Talk to the user in their language.
