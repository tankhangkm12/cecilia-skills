# Reviewing infrastructure and delivery-path changes

Targets: CI/CD pipeline definitions, Dockerfiles and image builds, deploy manifests (Kubernetes, Helm,
Kustomize, Compose), IaC (Terraform, Pulumi, CDK), environment and secret **wiring**, monitoring and
alert configuration as code, and incident follow-up actions.

This review judges a change that can break production without any application code changing. The
question is never "is this elegant" but **"what happens when this is wrong, and can it be undone"**.

Never run an apply, a deploy or any command that changes an environment. Read-only inspection
(`terraform plan` output supplied by devops, `helm template`, `kubectl get -o yaml`, pipeline history)
is judged as evidence; if it was not supplied, say so and label the finding `[unverified]`.

## 1. Axes, heaviest first (report in this order)

1. **Blast radius honestly stated.** The PR says what breaks if this is wrong, for which environment,
   and for whom. A change whose blast radius is understated is a Blocker on its own — every later
   judgement depends on it. Check the claim against the diff: a manifest touching a shared namespace,
   ingress, node pool, IAM role, security group, DNS or database is wider than one service.
2. **Rollback exists, is exact, and was rehearsed.** A named command, not "redeploy the previous
   version". Evidence that it ran and the service came back (`cecilia-devops/references/deploy-and-rollback.md`
   §4 if that skill is in use). An unrehearsed rollback on a change that can take a service down is a
   Blocker. Also: is the rollback still valid after this change (a migration that the old code cannot
   read makes the rollback a lie).
3. **Irreversibility.** Anything in the diff that cannot be undone by the rollback: destructive IaC
   changes (`terraform plan` showing destroy/replace on stateful resources), storage or volume
   deletion, retention shortened, a migration run forward with no down path, a deleted DNS record, a
   revoked credential. Each one must be named in the PR and approved in the moment by Cecilia.
4. **Secrets.** No secret value anywhere: not in the diff, not in a committed `.env`, not in a manifest
   literal, not in pipeline logs (`echo`, `set -x`, printing a config dump), not in a Terraform state
   file or plan output committed to the repo. Only names and references. Also check: secret pulled from
   the intended store, scoped to the intended environment, and not exposed to pull requests from forks.
   A leaked value is a Blocker **and** a rotation request, never "remove it in a follow-up".
5. **Environment isolation.** The change targets the environment the plan says (`ENV-nn`) and cannot
   reach another: no production endpoint, cluster, bucket, database, credential or account id in a
   non-production path, no shared state between environments, no default that falls back to production
   when a variable is missing. A pipeline that deploys on a branch pattern wider than intended belongs
   here too.
6. **Pipeline integrity.** Gates cannot be skipped silently: build, lint, tests and security scans
   actually run on the code being shipped (not a stale cache, not `continue-on-error`, not a step whose
   failure is swallowed). Third-party actions/images pinned by digest or exact version, not a moving
   tag. Permissions least-privilege (token scopes, OIDC role trust conditions). Cache keys cannot poison
   another branch. Untrusted input (PR titles, branch names) never interpolated into a shell step.
7. **Image and runtime hygiene.** Base image pinned and maintained; no build secrets in layers;
   non-root user; healthcheck; resource requests/limits present and plausible; replica count and
   rollout strategy match the availability the docs require; probes that cannot pass during startup
   (readiness identical to liveness, timeout shorter than the real boot) — a classic outage.
8. **Drift and reality.** The repo is supposed to be the source of truth: was existing drift between
   repo and environment recorded before this change, and does this change overwrite something a human
   set by hand? An IaC change proposed against an unknown current state is `[unverified]`, not approved.
9. **Observability of the change.** After this lands, can anyone tell it broke? Logs still arriving,
   metrics and dashboards updated for renamed services, alerts that fire on the new failure mode, and
   an alert route with an owner. An alert nobody receives is not monitoring.
10. **Cost.** Recurring cost delta stated; anything that scales without a ceiling (autoscaling max,
    retention, log volume, egress, always-on managed service) named with its ceiling.
11. **Traceability & docs.** The change cites its plan task (`OPS-Bnn`) and the requirement it serves
    (`NFR-nn`, an `ENV-nn` target, or an `INC-nn` follow-up). the infrastructure docs updated to match what
    now exists. Nothing in the diff that traces to nothing.
12. **Boundary.** No application source in an infra PR (and no infra file in a dev PR) — see the path
    ownership table in `cecilia-devops`. A needed app change must appear as a request, not an edit.

## 2. Severity

| Level | Meaning | Examples |
|---|---|---|
| **Blocker** | must not be applied as is | secret value in the diff or logs · no rollback for a change that can take a service down · irreversible destroy not named and approved · non-prod path reaching production · a quality gate silently disabled · probe/rollout config that guarantees downtime |
| **Should-fix** | works today, will hurt | unpinned action or base image · no resource limits · missing alert for the new failure mode · cost with no ceiling · the infrastructure doc not updated |
| **Suggestion** | optional improvement | pipeline duration, layer caching, manifest structure |
| **Question** | cannot judge without context | "is this cluster shared with staging?" |

Infrastructure findings are not downgraded because "it is only staging": a staging change that can
reach production data, credentials or DNS is judged as production. State that reasoning when you use it.

## 3. Finding format

```markdown
### I-1 · Blocker · `.github/workflows/deploy.yml:34` · Environment isolation (ENV-02, OPS-B01)
- **Problem:** the deploy job takes `AWS_ROLE` from a repository-level variable with no environment
  scoping, and the default points at the production account.
- **Failure scenario:** a staging deploy triggered from any branch assumes the production role and
  applies the staging manifest to the production cluster — one command, no confirmation, no rollback
  rehearsed for production.
- **Evidence:** workflow lines 30–38; no `environment:` key on the job; `vars.AWS_ROLE` default in
  repo settings quoted by devops report 2026-09-18 [inferred — could not read repo settings]
- **Suggested direction:** scope the credential to a GitHub Environment with required reviewers, and
  assert the account id at the start of the job.
```

## 4. Also report

- **Change walkthrough:** one line per changed file: what it controls and which environment it affects.
- **Apply/rollback pair:** quote both commands as the PR states them, and say whether evidence of the
  rehearsal was supplied.
- **Verdict per environment:** `ENV-nn · safe to apply / not yet / needs Cecilia's approval in the moment`.
- **Good:** 1–3 specific things worth keeping.
- **Out of scope, noticed only:** existing pipeline or manifest problems the diff did not introduce.

## 5. Reviewing a postmortem / incident follow-up

Inputs: the incident report (`INC-nn`), the timeline, and the actions it proposes.

| # | Check |
|---|---|
| 1 | Timeline is evidence-based (log lines, deploy times, alert timestamps), not reconstructed from memory |
| 2 | Cause chain reaches a mechanism, not a person; "human error" is a finding about the system that allowed it |
| 3 | Detection is examined separately from the cause: what noticed it, how long that took, what should have |
| 4 | Each action is concrete, owned, and traced into the plan as a task (`OPS-Bnn`) — an action with no task row will not happen |
| 5 | The action actually prevents recurrence, rather than adding a step someone must remember |
| 6 | Anything that got worse during recovery (a rollback that failed, a runbook that was wrong) is recorded |
| 7 | Risks knowingly accepted are listed for Cecilia to accept explicitly |

Verdict: **actions sufficient** / **insufficient — the same incident can recur via <path>** / **cannot
judge without <evidence>**.
