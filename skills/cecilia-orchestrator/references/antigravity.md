# Antigravity — the main host (v20.2)

Same rules as every host (`workflow.md`, `fallback.md`); this file is how to follow them in `agy`.

## Start

- Cecilia opens the **workspace**: `cecilia open <project> --agy` (or `agy` started inside `<project>.cecilia`).
  Started from her home folder, the workspace `.agents/` (hooks, agents, main agent) is not loaded: say so
  once and ask her to reopen with that command. Headless runs come from the Cecilia MCP server (`cecilia mcp`).
- Main model: `pro` (the agent files set orchestrator, plan and review to `pro`; config `antigravity.models`).
  On `flash` say once that planning and voting are weaker.

## Dispatch

- One member = one `invoke_subagent` call: `TypeName` exactly `cecilia-<role>` (e.g. `cecilia-dev-be`), the
  prompt = the **full output of `workflow.py brief`**, header line `[cecilia-brief TASK=… ROLE=… UNIT=…]` first,
  nothing before it. Record each launch with `workflow.py agent start`.
- A wave = every `invoke_subagent` call of that wave **in one turn**. Wait and collect with
  `manage_subagents` / `send_message`; then read the report files (`agent done`, files are the fact).
- Never invoke yourself (`cecilia-orchestrator`), `research`, `teamwork_*` or any agent that is not a
  Cecilia role, and never `define_subagent`.
- **Dispatch failed** (subagent not found, not allowed, any error) → **stop**. Report the exact error text
  and tell Cecilia to run `cecilia doctor` (custom main agents need `agy` ≥ 1.2.7). Never do the member's
  work yourself, never retry under another agent name.

## You have no MCP tools

Kubernetes, Proxmox and every other MCP server belong to roles: reads and diagnosis → dispatch
`cecilia-discovery` (or the owning role's diagnosers); changes → `cecilia-devops` (A3 quote relayed to
Cecilia). The guard denies an MCP call from the orchestrator.

## How the guard knows who is calling

Each subagent is its own conversation. The guard reads the first message of that conversation: the brief
header gives the role (`ROLE=`), lane and unit. A subagent **without the header is treated as the
orchestrator** — so a brief not from `workflow.py brief` makes the member useless and its writes denied.

## Votes

Ballots count only when written by real voter subagents: the header carries `ROLE` and
`UNIT=p1..p3 | h1..h3 | v1..v3`, and `workflow.py tally` checks `.cecilia/provenance.jsonl`. A ballot you wrote
is discarded; a ballot whose writer cannot be verified is marked and the card prints "independence
unverified". Never write, copy or fix a ballot.

## Card and approvals

Show the ONE card with `ask_question` (`consensus.md` §7). Human-only commands (`cecilia mode|approve|flow|
rules add|extension apply|push`) stay Cecilia's — even under `--dangerously-skip-permissions`, the guard
still refuses them; `antigravity.ask` decides which A3 actions are asked (`force_ask` = always, even with
skip-permissions; `ask` = normal prompt).
