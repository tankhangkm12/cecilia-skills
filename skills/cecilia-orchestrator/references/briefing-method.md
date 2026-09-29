# How to build the briefing — synthesis, not narration

The briefing is the one place Cecilia looks to steer. It is assembled from the roles' own outputs and
adds no judgement of its own; its whole value is selection, ordering and citation. The test for every
line is `common/evidence.md`'s: **would Cecilia act differently if this line were missing?** No → it does
not belong.

## 1. Sources, and nothing outside them

Build only from files under `tensura/` and the git/PR state:

| Section of the briefing | Built from |
|---|---|
| Progress | plan status table · `metrics.md` (progress rows) · PR states |
| Decisions needed | `challenges.md` (`ESCALATED`) · every `[agent-chosen — needs review]` in reports/plan/`DECISIONS.md` |
| Quality posture | `cecilia-review` reports (findings by severity) · `metrics.md` (coverage, perf, defects) · `OPEN` challenges |
| Open solutions | reports' "Needs your decision" · design/dev option tables not yet chosen |
| What each area still needs | reports' "For other roles" lines · unmet dependencies in the plan |

A claim with no row in one of these is not synthesized — it is asked. Never infer a status from
silence: a role that wrote no report is *"no report yet"*, not *"on track"*.

## 2. Shape — `common/evidence.md` §3, reused

The briefing IS a report and obeys `common/evidence.md`: the control block first, then the five
sections, within the caps. One addition and one only: a **decision queue** that gathers every open
decision across all roles into one numbered list, `[agent-chosen — needs review]` items first, each
with the options and the recommendation **as the owning role wrote them** — never re-argued here.

```
> BRIEFING · <TASK> · as of <date> · <STATUS>
> Done: <what is merged/approved, with the measured number and its M-nn>
> Now: <what is in flight, which batch, which role, where it stopped>
> Blocked: <what cannot move and by what — or "nothing">
> Decide: <count of open decisions; the one that blocks most, named>
> Next: <the single next action and who owns it>
> Deviations: <every deviation the roles reported since the last briefing — or "none reported">
```

## 3. Quality posture — assembled, never authored

State quality as three quoted numbers plus the open list, each cited:

- coverage / tests: from `metrics.md` (value, formula, source, `M-nn`) — never estimated.
- review findings: counts by severity from the latest `cecilia-review` report, with the report path.
- open challenges: `OPEN` rows from `challenges.md`, by id.

Then one honest line per area with **no** review or tests yet: *"payment module — not yet reviewed,
no coverage figure."* That sentence is the finding. Never write "quality is good"; that judgement is
`cecilia-review`'s, and this skill only carries it.

## 4. Bad news first — the omission guard

Before writing anything else, list, from the sources: every `BLOCKED`, every `OPEN` challenge, every
`[agent-chosen — needs review]`, every failing gate, every metric that regressed against its previous
value. Each one must appear in the briefing. `cecilia-review (verify mode)` checks this list against what the
briefing actually contains (its omission pass) — an item in the sources but not in the briefing is a
verification failure, not a stylistic choice.

## 5. Movement, not snapshots

A number alone does not steer; its change does. Every metric carries its previous value and the batch
it moved in (`common/evidence.md` §1): `coverage 72.4% (was 68.1% at B-02)`. Progress is `tasks MERGED / total`
per batch, from the plan status table, with the denominator. No effort, no time, no story points
(`common/evidence.md` §1).

## 6. What never enters the briefing

Effort or duration · adjectives standing in for numbers · a status inferred from silence · a quality
verdict this skill authored · any secret value · anything not traceable to a source file. When a fact
Cecilia needs cannot be sourced, the briefing says so — *"integration status for B-03 unknown; no
report filed"* — which is more useful than a confident guess.
