# Writing the as-built documents

Same file names and shape as `cecilia-design` produces, so the rest of the set consumes them without
knowing how they were made — plus a header and labels that make their nature impossible to miss.

## 1. The header every as-built document carries

```markdown
> **As-built** — reverse-engineered from code, not a specification anyone wrote.
> Source: repo <name> @ <commit sha> · read on <date> · runtime evidence: <what you read live, or "none">
> Confidence: `[verified from code]` · `[verified at runtime]` · `[inferred]` · `[unknown — needs <who>]`
> IDs below were assigned by this pass from observed behaviour, so later roles can cite it.
> They are **not** requirements anyone approved. Anything unlabelled is structural, not behavioural.
```

The commit sha matters: this document describes one state of a moving system, and six weeks later
someone needs to know which state.

## 2. Which document gets what

| File | As-built means | Assign |
|---|---|---|
| `requirements.md` | behaviour the system **exhibits**, written as requirements so later roles can cite it | `FR-nn` per observed behaviour · `BR-nn` per rule actually enforced in code · `AC-nn` only for behaviour you verified, in Given/When/Then |
| `architecture.md` | the real topology: deployables, what calls what, data ownership, the infrastructure actually in use | — |
| `<module>-design.md` | the real flows, step by step, with the file and symbol where each step lives | — |
| `<unit>-database.md` | the schema **as it exists** — including columns nobody uses and constraints that exist only in code | — |
| `<unit>-api.md` + `.yaml` | endpoints as they actually respond, including undocumented ones and inconsistent error shapes | — |
| `system-map.md` § Tests (as-built) | what is tested today and what is not — a coverage truth, not a plan | — |
| the infrastructure doc | only if you can read the delivery path; otherwise leave it out and say so | — |

Do not create a document you cannot fill at a useful depth. An empty database doc is worse than a line in
`tensura/README.md` saying the database was not in scope.

## 3. Writing rules specific to as-built

- **Cite location, not just behaviour.** *"Cancel is refused for SHIPPED orders (`order.service.ts:142`)
  [verified from code]"*. A later role that disagrees needs to reach the same line in one step.
- **Record what is enforced and where**, because that is what breaks: validation in the DTO, the
  controller, the service or nowhere · permission checks per endpoint, with the ownership condition ·
  transaction boundaries (and any external call inside one) · retries, timeouts, idempotency keys ·
  uniqueness enforced by a DB constraint vs by a code check (the second one is a race, and it is a
  finding for the risk map).
- **Inconsistency is content, not noise.** Three error shapes across four endpoints is exactly what a
  later role must know. Write all three; do not describe "the" error format.
- **Never smooth a flow you could not follow.** Write `[unknown]` at the exact step: *"…then the
  payment result is handled by <not found: no subscriber to `payment.settled` in this repo>
  [unknown — needs Cecilia: is there another repo?]"*.
- **Undocumented and surprising endpoints stay in.** A debug route, an admin endpoint with no auth, a
  legacy alias — these are the highest-value lines in the whole document.
- **Names lie; behaviour does not.** `validateUser()` that also mutates and sends an email is written
  as what it does. Then note the mismatch as a finding — naming is a code issue for later, but a
  document that repeats a misleading name has passed the lie on.
- **Business rules get `BR-nn` only if the code enforces them.** A rule stated in a comment but not
  enforced is a contradiction row, not a `BR`.

## 4. The three extra sections, at the end of every as-built document

```markdown
## Contradictions
| # | Claim A (source) | Claim B (source) | Which is running | Note |
|---|---|---|---|---|
| X-01 | comment says refund within 7 days (`refund.service.ts:12`) | code checks 14 days (line 30) | code [verified] | needs Cecilia: which is the business rule |

## Unknowns
| # | Question | Where it matters | Who could answer | Blocks |
|---|---|---|---|---|
| U-03 | what is `user.type == 3`? | permission checks in 4 endpoints | Cecilia / original author | any change to permissions |

## Not followed
<flows sampled rather than traced, and where the thread was lost — the honest boundary of this pass>
```

These three sections are the reason an as-built document can be trusted. A version without them
claims completeness it does not have.

## 5. Handover shape

`tensura/README.md` gets: which parts are documented, at what depth, as of which commit, and what is
explicitly out of scope. `tensura/docs/README.md` gets the per-document status table with a
confidence column — the share of each document that is `[verified]` versus `[inferred]`, stated
roughly and honestly. `tensura/docs/DECISIONS.md` starts as a `D-nn` list of decisions **found in the
code**, each marked `[reconstructed — never approved by Cecilia]`, because a later role must not read
them as settled policy.
