# {{name}} — workflow (v20)

Detail behind the card. Keep one responsibility: {{purpose}}

## When the orchestrator dispatches this role

{{dispatch_when}}

Not for: {{not_for}}

## Contract (same interface as every Cecilia role)

| Item | Value |
|---|---|
| Agent type | `{{agent_type}}` (permissions come from the agent type, not from this file) |
| Lane (may write) | {{lane_md}} + `tensura/reports|tasks|backups/<TASK>/**` |
| Consumes | {{consumes_md}} |
| Produces | {{produces_md}} |
| Report | `{{report}}` |
| Rules slot | `rules/roles/{{short}}.md` (Cecilia edits it; read-only for agents) |
| Reviewed with | `review-guide.md` (next to this file) |

## Steps

**{{prefix}}0 — Locate.** Read the brief header (`TASK`, `ROLE`, `LENS`, `UNIT`, `WORKFLOW`, `ROUND`, `RULES`), its
`## Rules (must follow)` block and the inputs it names. Missing header on STANDARD/CONTROLLED → ask for it and stop.
Record the start SHA when you touch a git project.

**{{prefix}}1 — Interview 🛑.** Ask only what the brief leaves open.
TODO(extend): list the 3–6 questions this role must have answered before it works.

**{{prefix}}2 — Plan.** The smallest change that meets the brief; each output mapped to an acceptance criterion.
A real choice → ≥ 3 options (`references/common/decisions.md`); Cecilia picks.

**{{prefix}}3 — Work.** Only inside the lane. Needs a file outside it → stop, `HANDOFF: needs <role> — <what>`.
TODO(extend): the role's own method (checklists, commands it runs locally, templates it fills).

**{{prefix}}4 — Verify.** Run the checks that prove the outputs (numbers, commands, paths); label each result.
TODO(extend): the concrete checks and their pass criteria.

**{{prefix}}5 — Report 🛑.** Write `{{report}}`: what changed, evidence, rollback, open decisions, then the standard
closing lines — `Rules: <hash> (PR-ids applied)`, `HANDOFF:` when the lane stopped you, `Deviations:`.
Chat reply ≤ 15 lines.

## Never

- Write outside the lane, edit `rules/` or `.cecilia/`, or run `cecilia …` control commands.
- Push, open a PR, publish, or touch production — write the commands for Cecilia instead.
- Decide what Cecilia decides (business rule, contract, schema, architecture, dependency).
