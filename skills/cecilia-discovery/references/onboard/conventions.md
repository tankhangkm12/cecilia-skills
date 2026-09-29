# Project conventions page — `tensura/conventions.md`

One page (≤ 80 lines) every role reads before its first edit. It saves each role from re-surveying the repo and
keeps new code looking like the old code. Derived from the code, never invented; each line cites where it was seen.

## How to build it (K0 + K2, read-only)
1. Package manager and scripts: lockfile, `package.json` scripts / `pyproject` / `Makefile` / CI steps → the exact
   commands for install (for Cecilia), lint, format, typecheck, unit test, one test, build, run locally.
2. Layout: where features, tests, migrations, configs live (3–10 lines of tree).
3. Naming: files, classes, functions, DB tables/columns, API paths, env vars — with one real example each.
4. Patterns in use: error handling, logging, validation, DI, data access (ORM/raw), state management, API client,
   i18n, feature flags — one line + one file path each.
5. Testing style: framework, fixtures/factories, where mocks live, naming of test files, coverage tool.
6. Git: branch naming seen in history, commit message style (conventional commits?), PR template if any.
7. "Do not": deprecated modules, generated files never edited by hand, folders owned by other teams.
8. Unknowns: what could not be determined (and who might know).

## Format
```
# Conventions — <project> (as of <commit>, <date>)
## Commands      lint: … · test: … · one test: … · build: … · run: …
## Layout        …
## Naming        …
## Patterns      …
## Tests         …
## Git           …
## Do not        …
## Unknown       …
```
Refresh it at K7 of every onboarding and whenever a role finds it wrong (the role writes a `CONV-nn` note in its
report; discovery or Cecilia updates the page). Never copy secrets or config values into it.
