# Flow — {{name}} (v20)

{{summary}}

Active when `flow` in `.cecilia/config.json` is `{{name}}` (Cecilia switches it with `cecilia flow {{name}}`; agents
never do). A flow is **process only**: it says what happens at each of the 7 steps. It never changes a role's
expertise, an agent type's permissions or the guard's A3/A4 rules, and it never relaxes local-only. Settings live
in `flows.{{name}}` of the config; project rules for this flow in `rules/flows/{{name}}.md`.

Every step below says: **who** acts (orchestrator / which role / Cecilia), **what** they read and write, and the
**exit** condition. Keep each section short; anything the personal flow already does can say "as personal".

## intake

Where the task comes from and how it is recorded (`tensura/tasks/<TASK>/state.md`).
TODO(extend): source of the task (chat, ticket, file), required fields, how the TASK id is chosen.

## plan

How the orchestrator turns the task into options (`workflow.py options`) — agents per kind, split, lenses,
time/token projection.
TODO(extend): anything this flow adds or restricts (extra doc, size limit, who must be consulted).

## approve

What Cecilia (or whoever the flow names) approves before any writer is dispatched (`workflow.py choose`;
CONTROLLED also `cecilia approve`).
TODO(extend): approvers and escalation triggers.

## dispatch

How briefs are issued (`workflow.py brief`, one header line per agent) and which conventions the writers follow.
TODO(extend): branch/commit conventions, parallelism notes.

## review

Tests by lens, review panel (from STANDARD), fix loop (≤ 3 rounds, then options for Cecilia).
TODO(extend): extra review inputs (e.g. comments from people) and how they become findings.

## handoff

What is handed to Cecilia: report, commands she runs herself (push, PR — local-only), docs to export.
TODO(extend): handoff package for this flow.

## finish

How the task is closed: state, lessons, clean-up list (never deletes on its own).
TODO(extend): closing checklist.
