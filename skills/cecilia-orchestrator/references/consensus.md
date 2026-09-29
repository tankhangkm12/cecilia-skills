# Consensus — three independent agents settle the important parts (v20, 20.2)

One agent — the orchestrator included — has too much power when it alone plans, diagnoses or rules on a
review. From STANDARD the four decisions that steer a task are settled by **3 independent agents who
vote with evidence**, counted by a script, never by you:

| Stage | Question | Voters | Ballot items |
|---|---|---|---|
| `plan` (O1) | which root cause, approach, batch order, rollback? | the 3 competing planners | `<point>-p<n>` per decision point of each plan |
| `rootcause` (O0/O1, infra and hard bugs) | which hypothesis explains the failure? | the 3 diagnosers | `h1` · `h2` · `h3` |
| `review` (O4; CONTROLLED plan review O1b) | is each finding real, and how severe? | 3 fresh cecilia-review voters | the F-ids of `panel/r1-all.md` |
| `verdict` (last review round) | PASS or FAIL? | the same 3 review voters | `verdict` (agree = PASS) |

**Not voted:** tests (they have real runs — a red test is a fact), facts discovery measured (`scope.json`),
and A3/A4 (Cecilia's). FAST: no consensus (`consensus.from_mode`, default `standard`).

Config (`.cecilia/config.json`, read-only for agents; defaults apply when absent):
`"consensus": {"stages": ["plan","review","rootcause","verdict"], "size": 3, "from_mode": "standard",
"models": [], "safety_veto": true, "provenance": "warn"}`.

## 1. Independence

- **One wave, separate subagents.** The 3 agents of a stage are launched in the same message, each a fresh
  subagent — Claude Code Agent/Task, Antigravity `invoke_subagent` (`antigravity.md`) — with its own brief from
  `workflow.py brief --role <role> --unit <p1|h1|v1…>`, so its header line carries `ROLE` and `UNIT`. None reads another's ballot; plans and hypotheses carry no model or agent name
  (the brief only says which file is the reader's own).
- **Models** — `consensus.models` (e.g. `["opus","sonnet","sonnet"]`) gives voter n its model; `[]` = the
  host default for all. You choose them from config and `models.md` without asking; they appear on the
  decision card, where Cecilia may override one in her answer. Fewer than 2 distinct models → the tally says
  `independence: weak` and the card must say so in one line. No sub-agent tool → the 3 run in sequence in
  fresh sessions; no fresh context at all → consensus is impossible: say so on the card (never simulate it).
- **Provenance is checked.** The guard logs who wrote each file (`.cecilia/provenance.jsonl`: role from the
  brief header, actor = the subagent's own session). `tally` accepts a ballot as verified only when its last
  writer is a voter role of that stage with an actor no other ballot used. A ballot written by the
  orchestrator is **discarded**; an unverified one (no log line, another role, shared actor) is kept but
  marked (`consensus.provenance: "warn"`, default) or discarded (`"require"`), and the result and the card
  print "independence unverified" with the reason. You never write, copy or repair a ballot — a missing one
  means re-dispatch that voter.
- **Voter ids** are stable: planners `p1`–`p3`, diagnosers `h1`–`h3`, review voters `v1`–`v3`. A later
  round writes the same file names, so the tally always counts the latest round; the minutes and
  `fix-<n>/` files keep the history.

## 2. The ballot — `tensura/tasks/<TASK>/votes/<stage>/<voter>.json`

Each voter writes exactly this one file (and nothing else under `votes/`):

```json
{"voter": "v2", "model": "sonnet", "stage": "review",
 "items": [{"id": "F-03", "vote": "agree", "severity": "BLOCKER", "safety": null,
            "evidence": "src/order/cancel.ts:88", "reason": "refund issued before the status check"},
           {"id": "F-04", "vote": "disagree", "severity": null, "safety": null,
            "evidence": "tests/order.spec.ts:140 asserts 409", "reason": "the double cancel is already rejected"}]}
```

- `vote`: `agree` | `disagree` | `abstain`. For `review` agree = the finding is real; for `verdict` the one
  item `verdict` agree = PASS; for `plan`/`rootcause` agree = adopt this point/hypothesis.
- **`evidence` is mandatory** — a path, a command and its output, or `file:line` the voter itself checked.
  The tally drops an item without evidence (and a ballot with none). "The others agree" is not evidence.
- `severity` (review only): `BLOCKER` | `SHOULD-FIX` | `NIT`. `safety`: `data-loss` | `secret` |
  `destructive` | null — set it whenever the voter sees that risk, whatever its vote.

## 3. The tally — `scripts/workflow.py tally --task <TASK> --stage <stage>`

Majority = **strictly more than half of the valid voters**. The script writes
`votes/<stage>-result.{json,md}` and prints the JSON: each item `adopted` / `rejected` / `open`
(no majority), its votes (`2/3`), severity, and the `vetoes`. You run it and read it; you never edit a
ballot, recount, or overrule a result. Open items become questions on the decision card, with the item
that has the most agree votes as the pre-selected default.

**Safety veto** (`safety_veto: true`, mode CONTROLLED): one voter's agree/finding carrying `safety` is
never outvoted — the tally lists it under `vetoes` and it goes to the card as Cecilia's decision. In
STANDARD it is counted like any vote, but a confirmed safety item is a CONTROLLED trigger → the card
proposes the mode rise.

## 4. Stage `plan` (O1)

1. **Compete** — 3 cecilia-plan agents in one wave (`workflow.py brief --role cecilia-plan --unit p<n>` +
   the CONSENSUS block below), same `scope.json`, each writes `tensura/plans/<TASK>-p<n>.md` with the fixed
   decision-point table (cecilia-plan `workflow.md` §Consensus).
2. **Critique** — one wave again (fresh agents, same models): each planner reads the other two plans,
   checks their claims against the repo, and writes `votes/plan/p<n>.json`, voting on every decision point
   of the other two plans (its own: `abstain`). A point is adopted when both other planners agree with evidence.
3. `workflow.py tally --task <TASK> --stage plan`.
4. **Merge** — ONE cecilia-plan agent (fresh, strongest model) writes `tensura/plans/<TASK>.md` from the
   adopted points only, with units and 2–3 option shapes; open points and vetoes are listed as questions
   with their choices, never settled by it. You transcribe its shapes into `options-input.json`.

**Root causes need `[verified]` evidence** — an adopted root cause resting on `[inferred]` evidence, or none
adopted, makes the first batch a **measurement batch** (read-only checks that confirm or refute it) before
any fix batch.

**CONTROLLED plan review (O1b).** Plan lenses (cecilia-review `review-plan.md`, plus security or data by
the scope signals) find issues in the merged plan; 3 review voters vote as in §6; confirmed BLOCKERs go back
to the merger once; open items and vetoes go on the card. STANDARD: the critique round is the plan review.

## 5. Stage `rootcause` (infra, incidents, hard bugs)

When `scope.json` has `live_cluster`/`production` signals, or discovery could not verify the cause of a bug:
3 diagnosers of the owning role (dev-be, dev-fe, db or devops by lane; read-only, A3 for any live read) each
write `tensura/reports/<TASK>/rootcause-h<n>.md` — one hypothesis, its evidence, and the measurement that
would refute it. Then each votes on the other two (`votes/rootcause/h<n>.json`, own = abstain) →
`tally --stage rootcause`. The adopted hypothesis is the planners' root-cause point; none adopted → the
plan starts with the discriminating measurements.

## 6. Stages `review` and `verdict` (O4)

Lens reviewers keep the **breadth** (`panel-run.md`): each lens finds issues blind. Then 3 fresh cecilia-review
voter subagents (`--unit v<n>`; never a lens reviewer of this round, never the author) each re-derive every F-id of
`tensura/tasks/<TASK>/panel/r1-all.md` against the target and write `votes/review/v<n>.json` plus
`votes/verdict/v<n>.json` (PASS only if, in its own view, nothing confirmed at BLOCKER/SHOULD-FIX remains and
the checks are green at the SHA). `tally --stage review` then `--stage verdict`. One more cecilia-review agent
— the **minutes writer** (formerly the judge) — turns both results into `tensura/reports/<TASK>/panel/verdict.md`:
adopted findings → Fix list, rejected → with the refuting evidence, open → DISPUTED questions for the card,
vetoes → card. It changes no outcome. Adopted BLOCKER/SHOULD-FIX → fix loop; each delta round repeats
lenses → voters → minutes on the new SHA; the verdict tally of the last round is the final verdict.

## 7. The decision card (O2)

`workflow.py suggest-mode --task <TASK>` then `workflow.py decision --task <TASK>` → `tensura/decisions/<TASK>.{json,md}`
(`assets/decision-card.md`): scope (goal, out of scope, done when), mode now / suggested / why / the exact
`cecilia mode …` command, models per role with why, the options with votes and the recommended one, the
questions (open points) with defaults, vetoes, independence.

- **Show it once.** Claude Code: AskUserQuestion — first question the options (`A — <title> (recommended)`,
  description = agents, lenses, models, `[projected]` cost, votes), then up to three card questions with
  the default first; the rest stay on the card with their defaults. Antigravity: `ask_question`; otherwise
  the card text. One reply like `A` = option A with every default.
- **Record it**: `workflow.py answer --task <TASK> --option A [--answers '{"Q2":"b"}'] [--by Cecilia]` — it
  marks the card `answered` and freezes `workflow.json` (it runs `choose`). A model override → put it in
  `options-input.json`, re-run `options` + `decision`, then `answer`.
- **Mode rise** — the card carries `cecilia mode controlled`; Cecilia runs it herself. CONTROLLED writers
  also need her `cecilia approve tensura/plans/<plan>.md --all` (one run, human only). You wait; you never
  run either or give her a command that does a write the guard blocked.
- **MCP** — an external LLM may answer the card for her through the Cecilia MCP server; a card whose status
  is `answered` is her decision — read it, do not ask again.
- Later stops (open review items, rounds exhausted) re-issue the same card with `workflow.py decision` —
  never a free-form question. A3 action quotes are still relayed verbatim (`relay.md` §8).

## 8. Cost

Plan: 3 planners + 3 critiques + 1 merger = 7 runs. Rootcause: 3 + 3. Review round: N lenses + 3 voters + 1
minutes (was N × 2 + 1 judge). The cost is shown on the card before Cecilia answers.

## CONSENSUS block (paste after block 5 of the brief)

```
CONSENSUS: stage <plan|rootcause|review|verdict> · you are <p1|h1|v1…> of 3 · independent — never read
another voter's ballot, never ask who wrote what; write your ballot yourself (the tally checks who wrote
it). <Compete: write <file> | Vote: read <files>, write ONLY tensura/tasks/<TASK>/votes/<stage>/<voter>.json>. Every item needs evidence you checked yourself (path,
command + output, file:line); no evidence → the tally drops it. Mark `safety` for data-loss, secret or
destructive risk. End with STATUS and DEVIATIONS lines.
```
