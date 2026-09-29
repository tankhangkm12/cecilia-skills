# cecilia-discovery — full rules and workflow

The SKILL card holds the summary; this file holds the detail. Open it at the first step on STANDARD/CONTROLLED work.

## Golden rules

1. **Describe what exists, not what should.** Onboard records the strange thing the code does, cites
   where, and notes the doubt. A tidied-up as-built document is worse than none.
2. **Label every behavioural claim** (`references/onboard/confidence-labels.md`): `[verified from
   code]` · `[verified at runtime]` · `[inferred]` · `[unknown — needs <who>]`. Never upgrade a label
   without new evidence.
3. **Contradictions are recorded, not resolved.** Code vs docs vs comments vs names — both sides
   quoted, Cecilia decides.
4. **Requirements describe the problem, not the solution.** No stack, tables, endpoints or components.
5. **Every requirement is testable** — a pass/fail check exists, with concrete values, and at least one
   negative AC when it can fail. NFRs are numbers with a scale basis: users now and in 12/24 months,
   peak rps, data per user, retention — asked from Cecilia, then projected (`numbers.md`). "Nhanh", "thân thiện", "phù hợp", "v.v." are rejected on sight.
6. **The agent decides nothing** about scope, priority, rules or limits. Options, recommendation,
   Cecilia picks. Wording and layout are yours.
7. **Scope out is written down**, each row with its reason and "revisit when".
8. **Challenge** upstream input and your own output (`challenge.md` §5).

## Scope — S0 to S2 (orchestrator O0, one-line prompt)

Cecilia wrote one short prompt; you turn it into facts so that nobody has to ask her for details. You
never ask her anything in this mode — no "what do you want?", no "describe more". What you can measure you
measure; what only she can choose (a preference or a risk) you write as a question with choices and a
recommended default, for the decision card.

**S0 — Read the prompt and locate.** Her prompt verbatim (from the brief), `tensura/docs/`,
`tensura/conventions.md`, `tensura/lessons.md`, README, the repo tree, `git log` of the paths the prompt
names. ≤ 10 minutes of reading, wide and shallow.

**S1 — Measure.** Read-only only: search and read code, configs, manifests, migrations, tests, CI files;
for a live cluster or database only the read-only queries the guard runs without a prompt (get, describe,
list, `EXPLAIN` without `ANALYZE`) — never secret values, never exec, never a write. A read that needs
Cecilia's A3 approval is not run: record it as an assumption with `verified: false` and the exact command
that would verify it (the planners turn it into a measurement batch).

**S2 — Write `tensura/tasks/<TASK>/scope.json`** (and a ≤ 15-line return):

```json
{"task": "<TASK>", "goal": "<one sentence, her intent in checkable words>",
 "out_of_scope": ["<what this task will not touch, and why>"],
 "constraints": ["<measured: versions, public contracts, SLAs, deadlines she stated>"],
 "done_when": ["<checkable: a test, a command and its expected output, a metric>"],
 "assumptions": [{"text": "<claim>", "verified": true, "evidence": "<path:line | command + output>"},
                 {"text": "<claim>", "verified": false, "evidence": "<the command that would verify it>"}],
 "signals": {"live_cluster": false, "secrets": false, "production": false, "migration": false,
             "destructive": false, "multi_service": false},
 "questions": [{"text": "<preference/risk only>", "choices": ["a", "b"], "default": "a", "why": "<one line>"}]}
```

- **signals** decide the mode (`workflow.py suggest-mode`): set each from evidence — `live_cluster` (the task
  touches a running cluster/VM), `secrets` (credentials, keys, tokens in scope), `production` (a production
  environment or its data), `migration` (schema or data migration), `destructive` (deletes, drops,
  overwrites, irreversible ops), `multi_service` (more than one deployable changes). Unsure → `true`, with
  the reason in an assumption; a wrongly low signal is the expensive error.
- **goal / done_when** in her words made checkable; never widen them "while here" — anything extra goes to
  `out_of_scope` or a question.
- Labels as everywhere in this skill: an assumption is `verified: true` only with evidence you read or ran now.
- `questions` (optional key) holds only preferences and risk choices (e.g. keep or drop the legacy
  endpoint); a fact is never a question. They reach the decision card through the merged plan.

## Onboard — K0 to K7

At every 🛑 stop, update `tensura/tasks/<TASK>/state.md`.

**K0 — Locate.** What exists: `tensura/`, README, docs, ADRs, OpenAPI, ERDs, and how old each is
(`git log` on those paths). ≤ 10 lines. Report the host capabilities you found
(`common/capabilities.md` §2).

**K1 — Interview · 🛑 G1.** Only what K0 did not answer, grouped: scope (whole system / one service /
one flow) · why she needs it (takeover · planning a change · audit — decides depth) · what runtime
access she will approve per action (run app, staging DB, logs) · who else knows the system · what is
already known to be wrong · output language. Tell her now what this pass **cannot** recover: intent.

**K2 — Survey · wide and shallow** (`references/onboard/survey.md`). Entry points, routes, schema and
migrations, jobs, consumers, outbound calls, config key names (never values), dependencies, test map,
git churn. Produce the system map (`assets/system-map.md`) with its **Not found** table. Stop and show
it: the map usually changes what is worth documenting deeply.

**K3 — Deep read, per service · 🛑 per service.** Follow real paths end to end
(`references/onboard/as-built.md`). Record what is enforced and where: validation, permission checks,
transaction boundaries, retries, idempotency, uniqueness by constraint vs by code.

**K4 — Write as-built docs** into `tensura/docs/` with the same names design produces, each with the
as-built header and labels. Assign `FR`/`BR` from observed behaviour and say they were derived from
code, not approved by anyone. `DECISIONS.md` rows found in code are marked
`[reconstructed — never approved by Cecilia]`.

**K5 — Contradictions, unknowns, not-followed flows** — each unknown names who could answer it.

**K6 — Risk map** (`references/onboard/risk-map.md`), ranked by impact × how quietly it fails, each
row with evidence and the next step (a test, a review, a plan task). No fixes, no refactor wishes.

**K7 — Handover · 🛑.** Full report to `tensura/reports/<TASK>/discovery.md` + chat summary (≤ 15 lines): what is documented at what confidence, top risks,
honest limits. One question: deepen an area · plan a change (`cecilia-plan`) · independent check of
the as-built docs (`cecilia-review` mode=design) · design on top (`cecilia-design`).

## Requirements — Q0 to Q6

At every 🛑 stop, update `tensura/tasks/<TASK>/state.md`.

**Q0 — Locate.** Read `tensura/docs/` (especially `system-map.md` for brownfield), `DECISIONS.md`,
the brief or ticket. ≤ 10 lines of what is settled and what is missing.

**Q1 — Problem · 🛑.** Grouped gate (`references/requirements/stage-idea.md`): who has the problem and
what it costs today · all actors, including admin, support, jobs and partner systems · what "solved"
looks like, checkably · what is out · constraints (budget, deadline, regulation, systems that cannot
change) · how success is measured in production.

**Q2 — Write `idea.md`** (`assets/idea.md`). Scope in/out tables with reasons; honest
feasibility; the ten often-forgotten areas judged one by one.

**Q3 — Requirements · 🛑, in passes** — one pass per actor or journey
(`references/requirements/stage-srs.md`). Steps, data, what can go wrong at each step, who may do it,
what happens on failure. Every answer becomes `FR`/`BR`/`NFR`; every `FR` gets `AC`s in
Given/When/Then with concrete values, including a negative case.

**Q4 — CORE pass.** Mark CORE anything touching money, points, stock or quota · multi-step state ·
several actors on one record · duplicates and races · external calls that can fail midway · rules the
business may change. CORE requirements get their failure paths written in full.

**Q5 — Quality gate.** Run the SRS exit gate and print every row with evidence; then the metrics
(requirements with ≥1 AC / total · failing the quality test / total). A failing requirement is fixed
or listed open — never counted as passing.

**Q6 — Report · 🛑 G1.** Full report to `tensura/reports/<TASK>/discovery.md`, chat/return ≤ 15 lines. Control block, decisions needed, metrics, challenges, what design and test
must know. Cecilia approving the SRS is G1 for the design and plan that follow.

## Handover

| To | Must contain |
|---|---|
| design | every `FR`/`BR` with failure paths, `NFR` with numbers and measurement method, CORE marks, permission rules per action |
| test | `AC`s in Given/When/Then with concrete values, negative cases |
| plan | priorities, scope out, CORE list, as-built confidence of each area |
| review | the as-built docs and the commit SHA they describe |

Supporting: `references/traceability.md` (forward/backward checks), `references/decision-log.md`,
templates in `assets/`.
