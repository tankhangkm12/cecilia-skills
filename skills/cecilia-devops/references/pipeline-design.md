# CI pipeline design

A pipeline exists to answer one question — *is this commit safe to promote?* — quickly enough that
people wait for the answer instead of working around it.

## 1. Stage order — cheapest and most decisive first

```
lint/format ─► type/compile ─► unit ─► build image ─► integration ─► contract/API ─► e2e ─► scan ─► publish
   seconds        seconds      1-2m       1-3m           2-5m           1-2m         5m+    1-2m
```

Fail fast: a formatting error should never cost an e2e run. Run independent early stages in parallel
where the platform allows it; keep the *dependencies* honest so nothing runs against an artifact that
was not built.

**Build the image once**, in the pipeline, and have every later stage use that exact artifact
(`deploy-and-rollback.md` §1). A pipeline that rebuilds per stage tests something it will not ship.

## 2. What belongs in which trigger

| Trigger | Runs | Why |
|---|---|---|
| Every push to a PR branch | lint, type, unit, build, integration | the feedback loop developers actually wait for |
| PR ready / merge queue | + contract, e2e, security scan | expensive checks once the change is real |
| Merge to `develop` | full suite + publish artifact + deploy to dev | the artifact that will be promoted |
| Tag / release branch | promote existing artifact, no rebuild | see §1 |
| Nightly | e2e against a fuller dataset, dependency audit, image rescan | catches rot and newly-disclosed CVEs |

Cecilia decides what blocks a merge. Present it as a table — check, blocks or warns, typical duration
— and let her pick; a check that warns forever is noise, and a check that blocks on something flaky
teaches people to bypass it.

## 3. Speed, honestly

Slow pipelines get worked around, so speed is a correctness concern. In order of usual payoff:

1. **Cache what is deterministic**: package downloads, build layers, compiler output. Key the cache on
   the lockfile hash, never on a branch name. Always have a cache-miss path that still works.
2. **Run independent jobs in parallel**, and shard long test suites.
3. **Skip by path** only where it is provably safe (docs-only changes). Path filters that skip tests
   for source changes are how a red main branch happens.
4. **Right-size the runner** before adding complexity.
5. Measure before and after, and put both numbers in the PR. "Should be faster" is not a result.

Never speed a pipeline up by removing a check, lowering a coverage gate, or adding `continue-on-error`
— those are decisions for Cecilia, stated as such, with what is being given up.

## 4. Flaky tests

A flaky check is worse than a missing one: it trains everyone to re-run without reading. On a flake:
quarantine it explicitly (named, tracked, with an owner and a date), tell `cecilia-test` via the
report, and never add a blanket retry to hide it. Retries are acceptable only around genuinely
external, idempotent steps — and each one is Cecilia's call, recorded with the reason.

## 5. Security in the pipeline

- **Least privilege by default**: read-only token for ordinary jobs, write scopes only on the job
  that needs them, scoped to the branch that needs them.
- **Never expose secrets to untrusted code.** Pull requests from forks must not get secrets, and
  triggers that run with elevated permissions on untrusted input are a well-known way to lose a repo.
- **Pin what executes**: third-party actions/plugins by commit SHA, base images by digest, tool
  versions explicitly. A moving reference is someone else's ability to run code in your pipeline.
- Scans that belong: dependency audit, image/OS vulnerability scan, secret scan over the diff, IaC
  misconfiguration scan. Each one blocks or warns — Cecilia decides which, per §2.
- Build provenance and an SBOM if the project needs it; ask rather than assume.

## 6. Pipeline hygiene

Every job states its timeout · no job runs forever waiting on a prompt · concurrency groups cancel
superseded runs on the same branch · logs say which version of what ran, and never print a secret ·
the pipeline file is reviewed like code and changed on a `ci/<TASK>-<desc>` branch like everything
else · a red pipeline on the target branch is reported, never worked around, and never fixed silently
as part of an unrelated change.

## 7. Checklist

- [ ] Cheapest checks first; nothing expensive runs after a guaranteed failure
- [ ] Image built once and reused by later stages
- [ ] What blocks a merge was chosen by Cecilia and written down
- [ ] Caches keyed on lockfiles, cache-miss path works
- [ ] Tokens least-privilege; fork PRs get no secrets; actions and images pinned
- [ ] Every job has a timeout; superseded runs are cancelled
- [ ] Before/after durations recorded if this was a speed change
- [ ] No check was weakened without Cecilia's explicit decision in the PR
