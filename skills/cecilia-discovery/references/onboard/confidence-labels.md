# Evidence and confidence — the rule every sentence obeys

An as-built document is trusted by every later role. A wrong sentence here does not cause one mistake;
it causes a class of mistakes, all pointing the same way, with nobody suspecting the document.

## 1. The three labels

| Label | Means | You may use it when |
|---|---|---|
| `[verified from code]` | you read the actual path and it does this | you followed it end to end in the source you can cite, file and symbol |
| `[verified at runtime]` | you observed it | you ran it, read the live schema, or read a real log/trace — say which |
| `[inferred]` | reasoning from what you read | a name, a pattern, a partial path, a convention elsewhere in the repo |
| `[unknown — needs <who>]` | the code cannot tell you | intent, a magic number, dead-looking code, an external contract you cannot see |

Unlabelled prose reads as verified. That is the default failure of this skill, so: **label anything a
later role could act on**. Structural description ("the project uses NestJS modules") needs no label;
behaviour, rules, numbers, ownership and guarantees always do.

## 2. What each label costs to earn

- **`[verified from code]`** — you can quote the file and the symbol, and you followed every branch
  that matters, not only the happy path. "The handler validates input" is verified only if you read
  the validator, including what it lets through.
- **`[verified at runtime]`** — you name what you ran or read, and when. A live schema read three days
  ago is still runtime evidence; say the date.
- **`[inferred]`** — you state the reasoning in the document, in half a line: *"the queue is presumed
  at-least-once [inferred: no dedup key anywhere in the consumer]"*. An inference with no visible
  reasoning is indistinguishable from a guess.
- **`[unknown]`** — you name who could answer it. An unknown with no owner never gets closed.

## 3. Never upgrade a label without new evidence

Re-reading the same file more carefully does not turn `[inferred]` into `[verified]`; running it does.
Cecilia saying "yes I think that's right" turns it into `[verified — Cecilia, <date>]`, which is a
different and weaker claim than the code saying so, and is written as such.

## 4. Source vs runtime, when they disagree

Runtime wins, and both are recorded:

| Claim about | Source says | Runtime says | Write |
|---|---|---|---|
| schema | migrations folder | live `information_schema` | runtime, and flag the drift as a finding |
| config | `.env.example`, defaults in code | the deployed environment | runtime, note what the default would have been |
| routes | the router file | what the running app exposes | runtime, note anything registered dynamically |
| behaviour | the code path | an observed log/trace | both — a difference here usually means a branch you have not found |

Could only read source → the claim is `[inferred]` about the running system, even when it is
`[verified from code]` about the repository. Those are two different statements; keep them apart.

## 5. The honesty tests

Before a document leaves this skill, three questions, answered in the report:

1. **Which flows did I follow completely, and which did I sample?** Sampled flows are not verified.
2. **Which `[verified]` claim rests on a single reading, with no second path confirming it?**
3. **Where did I lose the thread and write around it?** That place goes in the gaps list, not into
   smooth prose. "The payment result is then processed" is how a document hides that you could not
   find the processor.

## 6. Dead code and code that only looks dead

A path with no visible caller is `[unknown]`, not "unused". Callers hide in reflection, DI containers,
config-driven dispatch, cron definitions, feature flags, other repositories, and in partners calling
an endpoint nobody documented. Write: *"no caller found in this repo [unknown — needs Cecilia:
external callers?]"*. Declaring code dead is a decision with a deletion attached; it is not yours.
