# Environments

Every environment gets an id (`ENV-nn`, `common/workspace.md` §4) so a report, a PR or an approval quote
can never be ambiguous about which one is meant. "Staging" in one team's mouth is another's
production.

## 1. The environment table — write it once, keep it current

Lives in the infrastructure doc and is quoted in the Y1 interview:

| Id | Name | Tier | Purpose | Data | Who deploys | Secret source | Cost |
|---|---|---|---|---|---|---|---|
| ENV-01 | dev | non-prod | integration of merged work | synthetic | pipeline, automatic | CI store | low |
| ENV-02 | staging | non-prod | pre-release verification | anonymised copy | pipeline, on approval | SSM `/staging/*` | medium |
| ENV-03 | prod | **production** | customers | real | **Cecilia only** | SSM `/prod/*` | — |

The **Tier** column is what `authority.md` reads. Anything not classified is production until Cecilia
says otherwise. An environment holding real customer data is production whatever it is called, and a
"staging" that talks to a live payment gateway or sends real email is production for those purposes —
say so rather than letting the name decide.

## 2. Parity — know the differences, do not pretend they do not exist

Identical environments are not the goal; **known** differences are. What must match, because
differing here makes staging meaningless: the artifact (same digest), runtime and OS versions,
schema version, configuration *shape*, and the topology of dependencies.

What legitimately differs: scale, data volume and shape, real third-party integrations vs sandboxes,
domains and certificates, retention, cost ceiling.

Every legitimate difference goes in the table above with one line on the risk it leaves unTested.
That list is what goes into the production promotion message (`deploy-and-rollback.md` §5) — it is
the honest answer to "staging was fine, why did prod break".

## 3. Configuration

One source of truth per environment, in the repo where it is not secret, in the manager where it is
(`secrets.md`). Same key names everywhere so a grep finds every consumer. No environment-specific
branching inside application code — `if (env === 'prod')` moves a deployment decision into code that
nobody reviews as a deployment.

Config is validated at startup and the process fails fast if something is missing or malformed. A
service that boots with a silently-absent setting fails later, in production, in a way nobody traces
back here. New key → `.env.example` plus every environment's source, in the same PR.

## 4. Ephemeral and preview environments

Worth it when reviewers need to click the change. Rules that keep them from becoming a bill: created
from the same artifact, seeded with synthetic data only, **automatic expiry** (destroy on PR close,
plus a hard TTL for abandoned ones), named after the PR, and never able to reach production data,
queues or third-party accounts. Verify the teardown actually works before shipping the creation path
— the failure mode is silent accumulation.

## 5. Changing an environment

Any environment change follows the same route as code: `infra/<TASK>-<desc>` branch, PR, review.
Manual changes made directly to a live environment are drift, and drift is what turns a `terraform
plan` into a surprise destroy six weeks later. If drift is found at Y2, report it with the diff,
propose either importing it into IaC or reverting it, and let Cecilia choose — never silently
overwrite someone's fix.

## 6. Checklist

- [ ] Every environment has an `ENV-nn`, a tier, and a named deployer
- [ ] Anything unclassified treated as production
- [ ] Differences from production listed with the risk each one leaves unTested
- [ ] Config keys identical across environments; new keys in `.env.example` + every source
- [ ] Ephemeral environments expire automatically and cannot reach production
- [ ] Drift between IaC and reality reported, not silently reconciled
