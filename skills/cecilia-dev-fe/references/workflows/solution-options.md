# Solution options — frontend behaviour the design leaves open

Use when `<app>-frontend.md` does not settle something the user can feel: where a piece of state lives ·
what a list does after a mutation · optimistic vs pessimistic update and its rollback · focus and
scroll behaviour across a flow · a multi-step form or wizard with partial saves · double submit and
concurrent actions on the same record · offline/stale behaviour · rendering strategy for a route
(client, server, static, revalidated) · virtualising or paginating a list that can grow · a real
algorithm on the client (sorting, grouping, diffing, scheduling).

A screen whose behaviour the design already fixes does not need this — implement it. Plain rendering of
documented data does not need this either.

If the design already decides it → implement it, do not reopen. If it decides it **and** you can name a
concrete failure — a state with no data to render it, a flow the router cannot express, a budget the
choice breaks — present (A) change per the finding / (B) keep the design, accept the named risk.

## Question (one per turn, then stop)

```markdown
**Understanding:** <1–2 sentences, SCR/CMP/EP ids>
**Flow** — mark each API call, each state write, each navigation:
1. … 2. …
**Options:**
- (A) … — gain / cost / new dependency? (a new dependency is a hard stop)
- (B) …
- (C) …
I lean to A because … (would change if …)
**Races & duplicates:**
| Spot | How it breaks for the user | Guard | My pick |
|---|---|---|---|
| double submit | two orders created | disable + in-handler guard + Idempotency-Key if the contract has one | … |
| stale list after mutation | user sees the deleted row | invalidate `orders` list on success | … |
| concurrent 401s | random logout | one shared refresh promise | … |
**States this adds:** which of loading / empty / error-per-code / permission / offline / submitting change
**Needs Cecilia:** product assumptions I cannot decide
```

Rules: options per `decisions.md` §6 (≥ 3 when three genuinely exist, same criteria, researched —
§7 — with numbers from `numbers.md` for load, latency, memory or bundle) · · every guard named, not "handle it carefully" · **no new dependency proposed
without an existing-stack alternative beside it** · nothing that requires a contract change is chosen
here — that is a contract gap (`api-contract.md` §8).

After the choice, build exactly that; a deviation sends you back here. The decision is recorded in the
report and proposed to `cecilia-design` as a doc update under "For other roles". `cecilia-test` must
receive the cases the choice creates — at minimum **"submit twice"** and **"two tabs acting on the same
record"** for whatever guard was picked.
