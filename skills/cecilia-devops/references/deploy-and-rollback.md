# Deploy, verify, roll back

The rule that outranks the rest of this file: **nothing is done until the rollback has been rehearsed**
(§4). Everything else here exists to make that rehearsal possible.

## 1. Build once, promote the artifact

The same immutable artifact moves through environments; it is never rebuilt per environment.

```
commit ──► build image ──► tag by digest ──► staging ──► (same digest) ──► production
                             ▲
                   environment differences live in config, never in the image
```

- Deploy by **digest** (`app@sha256:…`), not by a moving tag. `:latest` and a re-pointed `:v1.5` make
  "what is running" unanswerable and rollback unreliable.
- Nothing environment-specific baked into the image: no URLs, no feature flags, no secrets, no build
  args carrying config. If the image differs between staging and prod, staging tested nothing.
- Keep enough previous artifacts to roll back to. Registry retention that deletes the previous image
  is a rollback that will fail when it is needed; check it and say so.

## 2. Choose the strategy with Cecilia, never by default

| Strategy | Costs | Use when |
|---|---|---|
| Recreate | downtime for the whole rollout | single instance, downtime acceptable and scheduled |
| Rolling | two versions live at once | the default for stateless services — **requires backward-compatible contracts and schema** |
| Blue/green | double the resources during the switch | instant switch and instant revert matter more than cost |
| Canary | slowest, needs metrics to judge on | risk is high and there is real traffic to judge with |

Rolling and canary mean old and new run together: the API contract, the event schema and the database
schema must all be compatible in both directions for the overlap. If they are not, the strategy is
wrong or the change must be split — that is a question for Cecilia, and usually a `cecilia-dev-be` / `cecilia-dev-fe`
change (expand/contract migrations), not an infrastructure trick.

## 3. Database changes are not rollbackable — plan them separately

Code rolls back; data does not. Never couple them in one step.

1. **Expand** — add the new column/table/index, nullable or defaulted, deploy, done. Old code still works.
2. **Migrate & dual-write** — new code writes both shapes; backfill in batches, off-peak, resumable.
3. **Contract** — only after the new code has run long enough that rolling back to the old one is no
   longer wanted. Dropping anything is a separate, explicitly approved step.

Before any migration against real data: a backup taken **in this session** and verified to exist, the
expected lock duration on the largest affected table, and a stated answer for what happens if it is
interrupted halfway. No answer to any of the three → do not run it.

## 4. Definition of done — the three proofs

An apply to staging (or any environment) is finished only when all three are in the report with
evidence. Two out of three is not done.

**Proof 1 — it is actually alive.** Not "the rollout succeeded". Readiness and health return 200,
*and* one real request through the real path returns the right answer, *and* the service's own
dependencies (DB, cache, broker, upstream) are connected. Record request → response.

**Proof 2 — the rollback ran and worked.** Actually execute it:

```
1. Note the current revision/digest and the replica count   ← read, write it down
2. Run the rollback command                                  ← the exact one in the PR
3. Verify the previous version is serving                    ← proof 1, again
4. Roll forward to the intended version
5. Verify again
```

Record the timings and anything surprising. A rollback that needed a manual step, or took minutes
longer than expected, is a finding for the report and for the infrastructure doc. If rehearsing is
genuinely impossible (a one-way migration, a provider with no revert), say so explicitly, write what
the recovery procedure would be instead, and get Cecilia's decision — do not quietly skip it.

**Proof 3 — you can see it.** Logs arrive at the log destination with the right labels, metrics
appear, and the alert that should fire for this service exists and is not muted
(`observability.md`). A deployment nobody can observe is one that fails silently.

## 5. Production promotion

Cecilia runs it (`authority.md` §1). Hand her, in one message: the exact promotion command with the
digest, the pre-flight checks to run first, what she should see when it works, the rollback command,
and the number to watch for the next few minutes. Then wait for her result and record it.

Do not promote "because staging is green" without saying what is different between the two
environments — data volume, traffic shape, real integrations, scale. That difference is the risk, and
it belongs in the message.

## 6. Checklist before opening the PR

- [ ] Artifact is immutable, referenced by digest, and the previous one still exists
- [ ] Strategy chosen with Cecilia; contract/schema compatible for the overlap if rolling or canary
- [ ] Migration, if any, split expand/migrate/contract, with a verified backup
- [ ] Proof 1, 2 and 3 in the report with evidence, rollback actually executed
- [ ] Rollback command in the PR body, copy-pasteable, with its prerequisites
- [ ] Blast radius stated in the PR, including what is *not* affected
- [ ] the infrastructure doc updated: strategy, rollback, what the rehearsal showed
