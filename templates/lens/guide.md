# Lens: {{name}} ({{owner}} v20)

Brief header `LENS={{name}}`. {{summary}}
Shared lens rules (files, isolation, report, lane): {{shared_rules}}. A lens is one angle of the same role — it
never adds permissions; project rules for it are in `rules/lenses/{{name}}.md`.

## When

Pick this lens when the change touches: {{when}}.

## Oracle

What "correct" means for this lens — the requirement, contract, doc or standard every finding is measured against.
TODO(extend): the documents and IDs this lens reads.

## Techniques

TODO(extend): 4–8 concrete checks, each with what to try and what result is expected.

## Environment

Local only (own ports, own data). Shared/staging targets are A3; production and third parties never.

## Report

`tensura/reports/<TASK>/{{report_name}}.md`: what was checked, evidence per check (`[verified]` with the command or
file:line), findings with severity **BLOCKER** / **SHOULD-FIX** / **SUGGESTION** / **QUESTION**, ending with
`Rules: <hash> (PR-ids applied)`.

## Never

Change code or docs (a fix is `HANDOFF: needs <role> — <what>`) · test or touch anything not local · report "passed"
for a check that did not run on this SHA.
