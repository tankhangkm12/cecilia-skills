# Solution options — non-CRUD logic the docs leave open

Use when the LLD does not fix the algorithm/flow of something CORE: multi-step dependent operations
with compensation · state machine or decision rules (price, discount, quota, allocation, ranking) ·
money/stock/balance/quota · concurrency or retries (clients, queues, cron) · background jobs/external
calls in the flow · a real algorithm choice. CRUD with validation/filter/pagination does not need this.

If the LLD already decides it → implement it, do not reopen. If the LLD decides it but you see a
concrete failure case → present (A) change per your finding / (B) keep the doc, accept risk.

## Question (one per turn, then stop)

```markdown
**Understanding:** <1–2 sentences, IDs>
**Flow** — mark DB writes, external calls, transaction start/end:
1. … 2. …
**Algorithm:**
- (A) … — gain / cost / stack needed (existing or new → hard stop)
- (B) …
- (C) …
I lean to A because … (would change if …)
**Races & duplicates:**
| Spot | How it breaks | Named mechanism | My pick |
|---|---|---|---|
**Data & states:** new columns/tables/states; what is snapshotted
**Needs Cecilia:** business assumptions I cannot decide
```

Rules: options per `decisions.md` §6 (≥ 3 when three genuinely exist, same criteria, researched —
§7 — with numbers from `numbers.md` for load, latency, memory or bundle) · · named mechanisms (`code/data-concurrency.md`) · no external calls inside DB
transactions · new infrastructure always offered with an existing-stack alternative. After the choice,
code exactly that; deviation needed → back here. The decision is recorded in the report and proposed to
cecilia-design/plan as a doc update ("For other roles"). TEST must receive "same input twice" and
"two parallel actors" cases for the chosen mechanism.
