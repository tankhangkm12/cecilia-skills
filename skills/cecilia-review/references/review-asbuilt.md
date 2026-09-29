# Reviewing as-built documentation

Produced by `cecilia-discovery` (or by anyone reverse-engineering a system). The oracle here is
**the code**, not a specification — so this review inverts the usual question. For a design document
you ask "is this a good design?". Here you ask: **"is this what the system actually does?"**

Why it is worth a dedicated pass: every later role will trust this document. A design document that is
wrong produces an argument; an as-built document that is wrong produces confident work built on a
false model of a live system, and nobody suspects the document until something breaks in production.

## 1. Axes, heaviest first (report in this order)

1. **Spot-check the claims against the code — this is the review.** Pick 8–12 claims and verify each
   one yourself in the source. Bias the sample deliberately toward: anything labelled
   `[verified from code]` that would be expensive if wrong (money, permissions, state transitions,
   contracts) · claims with no file reference · claims about *absence* ("no retry", "no validation"),
   which are the easiest to get wrong and the most dangerous. Report the hit rate honestly:
   `9/11 confirmed, 1 wrong (§4.2), 1 could not verify`. A document with two wrong claims in a sample
   of ten is not a small problem — it is an unusable oracle, and that is the finding.
2. **Label honesty.** Every claim that a later role could act on carries a label, and each label is
   earned: `[verified from code]` with a locatable file and symbol · `[inferred]` with its reasoning
   visible · `[unknown]` with an owner. Findings here: unlabelled behavioural prose · `[verified]`
   claims with no citation · an inference presented as fact · a label upgraded by Cecilia's "I think
   so" without being rewritten as `[verified — Cecilia]`.
3. **Smoothing.** The characteristic failure of this document type: prose that flows across a step the
   author could not actually follow. Look for connective phrases doing load-bearing work —
   "the result is then processed", "this is handled by the service layer", "the event is consumed
   downstream" — with no file behind them. Each one is a gap wearing a sentence.
4. **The three required sections exist and are populated**: Contradictions, Unknowns, Not followed.
   A document without them claims a completeness no reverse-engineering pass can have. An empty
   "Contradictions" table on a system older than a year is itself suspicious — say so.
5. **Source vs runtime is distinguished.** Schema claims from a migrations folder are not claims about
   the live database; config claims from `.env.example` are not claims about the deployed environment.
   Check whether the document says which it read, and whether drift was looked for where it could.
6. **Coverage matches the claim.** The header says a depth; the content must not exceed it. A document
   that says "survey depth" but states transaction boundaries per endpoint has either done more work
   than it admits or invented the detail — find out which.
7. **IDs are usable downstream.** `FR-nn` / `BR-nn` derived from behaviour are stable, unique, and each
   points at the code that justifies it. A `BR-nn` for a rule that is only in a comment and not enforced
   is a contradiction row, not a business rule — this is a common and consequential mix-up.
8. **The undocumented and the surprising survived the write-up.** Debug routes, unauthenticated admin
   endpoints, legacy aliases, dual code paths behind a flag. A tidy document that omits them has
   optimised for looking good, which is the one thing this document must never do.
9. **Risk map quality** — each row names a failure, not a preference; has evidence; and states
   likelihood and impact with a reason rather than a bare letter. Refactor wishes masquerading as risks
   dilute the rows that matter.
10. **Dead code claims.** "Unused" is a finding only with evidence that covers reflection, DI, config
    dispatch, cron, feature flags, other repos and external callers. Otherwise it must read
    `no caller found in this repo [unknown]`. This one matters because "unused" invites deletion.

## 2. Severity

| Level | Meaning | Examples |
|---|---|---|
| **Blocker** | later roles would be misled | a `[verified]` claim contradicted by the code · a flow smoothed over a gap · a missing Unknowns section · a rule stated as enforced that the code does not enforce · "unused" with no evidence |
| **Should-fix** | usable but risky | inference presented without its reasoning · no file references · runtime vs source not distinguished · depth claimed above what was done |
| **Suggestion** | ordering, naming, structure |
| **Question** | needs the author or Cecilia | "was the live schema read, or only the migrations?" |

A wrong claim about the system is always more severe than a missing one. Missing is visible; wrong is
invisible and inherited.

## 3. Finding format

```markdown
### A-1 · Blocker · `tensura/docs/modules/order/order-design.md` §4.2 · Claim contradicted by code
- **Problem:** the document states cancel is refused for SHIPPED orders [verified from code], but the
  guard checks `status !== DELIVERED` only — SHIPPED orders can be cancelled.
- **Failure scenario:** a test suite written from this document asserts a 409 for SHIPPED and fails;
  worse, a dev batch "preserving existing behaviour" preserves behaviour that was never there.
- **Evidence:** `order.service.ts:142` reads `if (order.status === OrderStatus.DELIVERED) throw …`
  [verified — read this session]
- **Suggested direction:** correct §4.2 and re-check the other status guards in the same file; the
  error suggests the status enum was read once and reused from memory.
```

## 4. Also report

- **Spot-check table:** `claim · document section · verified? · evidence` — the whole sample, including
  the confirmed ones, so the hit rate is auditable rather than asserted.
- **Confidence assessment:** your own estimate of how much of each document is safe to build on, and
  the areas you would not yet trust.
- **Good:** 1–3 specific things worth keeping — an honest `[unknown]` in an awkward place, a
  contradiction caught, a surprising endpoint documented.
- **What the next role must be told** before using these documents as an oracle.

## 5. Verdict

**Usable as an oracle** / **usable for <areas> only** / **not yet — re-verify <areas> first**.

Say it plainly. `cecilia-plan` is about to build a plan on this, and "mostly fine" is not a basis for
deciding which parts of a live system to touch.
