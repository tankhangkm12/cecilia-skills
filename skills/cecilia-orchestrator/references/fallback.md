# Host differences and fallbacks (v20)

Both hosts are equal: Claude Code (Agent/Task tool, hooks) and Antigravity (`invoke_subagent`,
`mainAgent: true`). What changes between them is how a rule is enforced, never the rule. The
orchestrator **never** falls back to doing a role's work itself — not in a host without sub-agents, not
to save time, not in FAST.

## 1. Enforcement per host

| Rule | Claude Code | Antigravity (20.2) |
|---|---|---|
| orchestrator writes only `tensura/`, no MCP tools | guard DENY (agent identity from the hook) | guard DENY (identity from the brief header in each subagent's first message; no header = orchestrator) |
| role lanes | guard DENY + `HANDOFF` hint | guard DENY + `HANDOFF` hint |
| workflow gate (header hash, ROUND ≤ max) | guard checks every writer/tester dispatch | guard checks every `invoke_subagent` / `define_subagent` |
| rules gate (RULES hash read before the first write) | guard | guard; the report ends with `Rules: <hash>` |
| ballots from real voters | `tally` checks `.cecilia/provenance.jsonl` | same |
| showing the ONE decision card | AskUserQuestion | `ask_question` |

Antigravity details (dispatch, failures, MCP, votes): `antigravity.md`. With `antigravity.identity: "off"` in
the config the Antigravity gates fall back to procedure (20.1): say once, at O0 of the first task, "Trên
Antigravity các cổng lane/workflow/rules đang là quy trình; `cecilia_check.py` sẽ báo vi phạm."

**A dispatch that fails** (agent not found, not allowed, host error) is never a reason to do the work: stop,
report the exact error and `cecilia doctor`.

## 2. Parallel limits

No configured cap (`parallel.limits.* = null`); the chosen option sets the numbers. The host limit
still applies (Claude Code: 20 concurrent sub-agents). A wave bigger than the host limit is launched in
chunks, in the same order, and the extra step is said to Cecilia once (it changes the time estimate,
not the result). A user config that still has `parallel.max_writers` caps the dev units per wave.

## 3. No sub-agent tool at all (plain chat, an IDE agent without sub-agents)

Offer two ways, once:

- **Separate sessions (keeps the parallelism):** `workflow.py brief … --out` writes each member's brief
  to `tensura/tasks/<TASK>/briefs/`; create the worktrees; give Cecilia one line per member to start a
  new session in that worktree with the role agent and "follow the brief at <path>". Each session writes
  its report; you collect, check, integrate and run the next wave as usual.
- **Cecilia drives one role directly:** she invokes the role skill in her own session for this step;
  you resume coordination from the report it writes.

Never offer "I will do it myself in this session". A review panel cannot be independent without
separate agents — say so and offer one independent review in a new session instead.

## 4. No git worktree

Code writers of one wave serialize (document writers and read-only units may still share a wave);
the workflow numbers still say what depends on what. Say it once and give Cecilia the new time estimate.

## 5. Model choice not available

The host cannot set a model per agent → say so once, record `model: session default (requested <X>)`
in the run log, and warn where it matters (consensus voters — independence becomes weak on the card —, minutes writer, redteam, a CORE unit Cecilia wanted on the strongest tier).
