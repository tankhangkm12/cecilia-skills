# Infrastructure — <system or service>

> Task: <TASK> · Owner: cecilia-devops · Updated: <YYYY-MM-DD> · Status: DRAFT | APPROVED
> Sources: `tensura/docs/system/architecture.md` §7 (infrastructure components), §10 (environments + delivery expectations),
> §11 (NFR mechanisms) · `tensura/plans/<TASK>-<slug>.md` `OPS-Bnn`
> Every resource, environment and alert below traces to one of: a flow in the HLD, an `NFR-nn`, an
> `ENV-nn` Cecilia approved, or an `INC-nn` follow-up. Anything tracing to nothing is a question, not a row.
> Confidence: `[verified]` = read from the live system this session · `[inferred]` · `[unverified]`

Drop any section that does not apply rather than leaving it empty. No secret values anywhere —
names only.

## 1. Delivery path

```
commit ──► CI (<platform>) ──► image <registry>/<name>@sha256 ──► ENV-01 dev
                                                              └─► ENV-02 staging ──► ENV-03 prod
```

Build once, promote by digest. What triggers what, and who presses which button.

## 2. Environments

| Id | Name | Tier | Purpose | Data | Who deploys | Secret source | Cost |
|---|---|---|---|---|---|---|---|

**Differences from production**, each with the risk it leaves untested:

| Difference | Risk it leaves untested |
|---|---|

## 3. Pipeline

| Stage | Runs on | Blocks merge? | Typical duration | Notes |
|---|---|---|---|---|

Decided by Cecilia on <date>: what blocks, what warns. Quarantined/flaky checks and their owners.

## 4. Runtime topology

ASCII diagram: services, replicas, data stores, queues, ingress, external dependencies.

```
```

Per workload: replicas, resource requests/limits, autoscaling range, disruption budget.

## 5. Configuration and secrets

| Key | Type | ENV-01 | ENV-02 | ENV-03 | Source | Consumer | Rotation owner / cadence |
|---|---|---|---|---|---|---|---|

Values never appear here. How each secret reaches its consumer (env var, mount, stdin), and what
breaks during a rotation.

## 6. Deploy and rollback

- Strategy: <recreate / rolling / blue-green / canary> — chosen by Cecilia on <date>, because …
- Deploy command (per environment):
- **Rollback command:**
- Rollback rehearsed: <date> · result · how long it took · anything surprising
- Contract/schema compatibility required for the overlap: <yes/no, what>
- Migration approach if any: expand → migrate → contract, with the backup procedure

## 7. Observability

| Signal | Where | Alert? | Threshold + duration | Who is notified | First thing to check |
|---|---|---|---|---|---|

Health/readiness endpoints and their semantics. Log destination, retention, sampling. Dashboard links.
Deploy markers: how they get there.

## 8. Operations runbook

Enough that someone woken at 3am needs only this page.

- **How to tell it is healthy:** exact checks and what "normal" looks like
- **Deploy:** command + verification
- **Roll back:** command + verification + prerequisites
- **Scale up/down:** command + safe range
- **Common failures:** symptom → most likely cause → first action
- **Who to escalate to**

## 9. Cost

Current run rate per environment, what drives it, the ceiling Cecilia set, and what to turn off
first if it must come down.

## 10. Risks, assumptions and open items

| # | Item | Impact | Status |
|---|---|---|---|

Items marked `[agent-chosen — needs review]` first. Known drift between IaC and reality goes here
until it is resolved.

## 11. Decisions

Recorded in `tensura/docs/DECISIONS.md` as `D-nn`; listed here with dates and who decided.
