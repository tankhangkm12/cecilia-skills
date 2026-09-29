# Reconcile mode — existing documents vs the running system

Used when documents already exist but are suspected stale. The output is **a difference table plus a
recommendation per row** — never a rewritten document. Rewriting is a `DOC-Bnn` task, owned by
`cecilia-design`, and only after Cecilia decides which side is right.

## 1. Before comparing anything

Establish what the documents claim to be: their date, their commit if recorded, their author, and
whether anyone still trusts them (ask — one question). A document nobody has trusted for a year is a
historical artifact; comparing it line by line is wasted effort. Ask what to do with it: retire it,
or reconcile it.

## 2. The difference table

| # | Topic | Document says | System does | Evidence | Which is wrong | Recommendation |
|---|---|---|---|---|---|---|
| Δ-01 | refund window | 7 days (SRS §4.2) | 14 days | `refund.service.ts:30` [verified from code] | unknown — a business call | ask Cecilia: fix docs, or fix code |

The "Which is wrong" column is usually **unknown**, and saying so is the point: the code may have
drifted from an approved requirement (fix the code) or the requirement may have changed in a meeting
that never reached the document (fix the document). Only Cecilia knows which.

## 3. The three kinds of drift, and what each implies

| Kind | Meaning | Usual resolution |
|---|---|---|
| **Document ahead** — describes something not built | a plan that was written down and never delivered | move it to a backlog or out of scope; it is not documentation |
| **Document behind** — system changed, docs did not | the ordinary case | `DOC-Bnn` task once Cecilia confirms the code is correct |
| **Both wrong** — neither matches what is needed | a rule changed and both records missed it | a design decision, not a doc fix |

## 4. Rules

- Never edit an existing document in this mode. Produce the table; the edit is a separate, owned task.
- Never assume the code is right. It is the *current* truth, which is not the same as the *intended*
  truth — that difference is the entire reason this mode exists.
- A document section you could not check gets `[unverified]` in the table, not silence.
- Where the code has drifted from something that looks like a deliberate rule (money, permissions,
  retention, contracts), raise it to the risk map too: a silent drift in those areas usually means
  someone has been relying on the wrong number.
