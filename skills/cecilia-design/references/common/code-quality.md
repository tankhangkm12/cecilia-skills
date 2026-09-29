# Code quality — small, clear, fast where it matters (common v20)

<!-- common v20 — canonical copy in shared/, synced into every skill by tools/sync_common.py. Do not edit a copy. -->

Applies to every role that writes code, tests, migrations, pipelines or IaC. The repository's linter,
formatter and conventions win on style; these rules win on substance unless the docs say otherwise.

## 1. Write less

1. **Smallest diff that fully solves the task.** No unrelated reformatting, renames or "cleanups".
2. **Reuse before writing.** Search the repo for an existing helper, component, query or pattern; use it
   or say in one line why not.
3. **No dead code**: no commented-out blocks, unused imports/params/exports, unreachable branches, TODO
   without an issue ID. Remove what your change made unused.
4. **No duplication**: the second copy of logic becomes one function; the third is a finding.
5. **No speculative generality**: no option, abstraction, layer or config key nobody asked for.
6. **Dependencies are a decision** (A3 to install; `decisions.md` §6 for options): prefer the standard
   library and what the repo already has.

## 2. Write clearly

- Names say what, in the domain's words; functions do one thing; early returns over nesting.
- Size signals (per language references): function > ~40 lines, file > ~300–400 lines, > 3 levels of
  nesting, > 4 parameters, cyclomatic complexity > ~10 → split by reason, or say in the brief why not.
- Types precise at boundaries; errors handled where they can be handled, typed/coded where they cross a
  boundary; no swallowed exceptions.
- Comments explain *why* (a workaround, a business rule with its ID), never *what*.

## 3. Fast where it matters — measured

- **Correct and simple first.** Optimise only a path that is hot (profile, APM, `EXPLAIN`, bundle report)
  or that a requirement's number (NFR) says is too slow.
- Avoid the known scale traps from the start: N+1 queries, unbounded lists or page sizes, work inside
  loops that can be batched, unnecessary re-renders on large lists, blocking I/O on hot paths, loading a
  whole table/file into memory, missing timeouts.
- An optimisation ships with its before/after numbers (`numbers.md`) and keeps readability; a clever
  line that saves nothing measurable is a defect.

## 4. Self-check before handing over

```
[ ] diff contains only the task          [ ] no dead / duplicated code
[ ] reused what existed, or said why not [ ] names and sizes within the signals
[ ] errors handled, nothing swallowed    [ ] no scale trap on a hot path
[ ] lint + format + type-check clean     [ ] tests for the behaviour changed
[ ] optimisation claims have numbers     [ ] Deviations line written
```

`cecilia-review` judges the same list (review-code §quality); a failed item is a finding, not a style note.
