# Decision card — `tensura/decisions/<TASK>.md` (v20, 20.1)

Written by `scripts/workflow.py decision --task <TASK>` (never by hand) from `scope.json`, `suggest-mode`,
the models, `options.json`, the plan tally and the vetoes; answered with `workflow.py answer`. It is the
**only** place a task asks Cecilia anything: preferences and risk choices, never facts
(`references/consensus.md` §7). Its shape, for reading and for checking what the script wrote:

```markdown
# <TASK> — decision needed · status: open

**Goal:** <one line from scope.json> · **Done when:** <done_when, ≤ 3> · **Out of scope:** <out_of_scope>

**Mode:** now STANDARD → suggested **CONTROLLED** — live_cluster, migration (scope.json signals).
Run it yourself in a terminal: `cecilia mode controlled` — then `cecilia approve tensura/plans/<TASK>.md --all`.

| Option | What runs | Models | Cost [projected] | Plan votes | |
|---|---|---|---|---|---|
| **A — Lean** | dev-be ×1 ‖ dev-fe ×1 · tests functional, integration · review 3 lenses + 3 voters | plan opus/sonnet/sonnet · dev sonnet | 14 runs · ~370k tok · ~16 min | 3/3 | **recommended** |
| B — Wide | dev-be ×2 by module ‖ dev-fe · + security tests · review 4 lenses + 3 voters | dev-be opus | 19 runs · ~500k tok · ~16 min | 2/3 | |

**Questions** (default pre-selected — answering only the option letter accepts them all)
1. Q1 — Rollback for the orders migration? **(a) down-migration + backup (default, 2/3)** · (b) forward-fix only — why: p2 found no down path for the enum change.

**Safety veto (never outvoted):** v3 — F-07 `DELETE` without tenant filter could drop other tenants' rows (data-loss).
**Independence:** weak — every voter ran on one model.

Answer: `A` · or `B, Q1=b` · or name a model to change.
```

Recording (orchestrator): `workflow.py answer --task <TASK> --option A [--answers '{"Q1":"b"}'] [--by Cecilia]`
→ status `answered`, `workflow.json` frozen. A card already `answered` (e.g. through the MCP server) is her
decision: read it, never re-ask.
