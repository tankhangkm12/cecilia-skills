# What may be run, where, and with whose approval

This file applies `common/core.md` §2 to environments. It is narrower than v14's version: live reads
need Cecilia's yes, every non-production change is approved one action at a time, and production is
entirely hers — there is no emergency door for the agent.

## 1. The three tiers

| Tier | Environments | The agent may |
|---|---|---|
| **Local / static** | the repo on this machine, local containers | Inside the approved scope (A2): lint, validate, `docker build`, `helm lint/template`, `terraform fmt/validate`, local compose. Say what you ran. |
| **Live, non-prod** | dev, test, staging, preview, ephemeral | **Read** (`get`, `describe`, `logs`, `terraform plan` against real state, `helm diff`, pipeline history) — A3, one quote naming the context; Cecilia may approve a read-only session for one environment as a recorded exception. **Change** (`apply`, `deploy`, `rollout`, `scale`, `restart`, `create`, `destroy`, migration, CI variable) — A3, **one quote per action, every time** (§3). |
| **Production** | prod and anything customers touch | **Nothing.** A4: every command — reads with production credentials included — is composed for Cecilia with its verification and rollback, and she runs it. The agent may analyse output she pastes or telemetry she exposes read-only. |

An environment nobody has classified is production until Cecilia says otherwise. If the same cluster
holds both staging and prod namespaces, the tier follows the namespace, and one wrong `--context`
away from prod is reason to state the context in the approval quote.

## 2. Before any state-changing command, know the real state

Never apply against an assumption. Run the read equivalent first (itself an A3 read unless a
read-only session was approved) — `terraform plan`,
`helm diff`, `kubectl diff`, `docker compose config` — and put the actual diff in the approval
request. A plan that shows unexpected destroys or replacements is a stop, not a detail: report it and
ask before proceeding, because drift means someone changed something by hand and nobody wrote it down.

## 3. The approval quote

Approval is per action, not per plan. "Go ahead with the deploy" does not approve the three commands
around it. Quote each one like this and wait:

```
🛑 XIN DUYỆT — apply · ENV-02 staging · SHOP-42

Lệnh:      helm upgrade --install orders ./charts/orders -n staging -f values.staging.yaml
Ngữ cảnh:  kubectl context = gke_acme_staging
Thay đổi:  Deployment orders (image v1.4.2 → v1.5.0), thêm HPA 2–6 pod
Nổ tới đâu: orders ở staging gián đoạn ~20s khi rollout; không chạm DB, không chạm dịch vụ khác
Hoàn tác:  helm rollback orders -n staging   (về revision 7, đã kiểm tra tồn tại)
Xác nhận khỏi: /healthz trả 200 và 1 lượt POST /orders thật thành công
Chi phí:   +2 pod tối đa ≈ không đáng kể

Duyệt lệnh này? (không phải duyệt cả đợt)
```

Rules: one command per quote · the rollback must be verified to exist *before* asking (revision
present, previous image tag still in the registry, state backup taken) · no rollback path means the
action is not approvable yet, say that instead of asking · re-quote if anything changed since the
last approval · never batch several applies into one approval to save turns.

Nobody answering (scheduled run, background) → do all local and already-approved work, write the report with each
pending approval quoted in full, and stop. A gate is never passed because nobody replied.

## 4. During an incident

v14 had a narrow "undo door" letting the agent roll back production itself. **v16+ removes it**, by
Cecilia's rule: the agent never acts on production, even to undo. What it does instead, fast:

1. Collect evidence from what it can read (repo, recent deploy records, telemetry Cecilia exposes).
2. Compose the smallest reversal — previous revision, previous replica count, previous flag value —
   as a §3 quote, with the previous state **as observed** (or "not observed — verify first" and the
   read command to observe it).
3. Hand it to Cecilia, wait for her to run it and report back, then verify recovery from what she
   shares and open `INC-nn` (`incidents.md`).

A ready-to-run command with its check is usually faster than an agent with production access, and it
keeps production credentials out of every agent session.

## 5. Things that are never the agent's, in any environment

Deleting or recreating a stateful resource (database, volume, bucket, queue with data) · anything
against real customer data · rotating, revoking or issuing a credential · changing IAM, roles or
policies · DNS and certificates · billing, account, quota or region settings · branch protection,
required checks, or who may deploy · disabling a security control, an audit log or a backup ·
`--force`, `--auto-approve`, `--no-verify`, `-f` on a destroy, or any flag whose purpose is to skip a
confirmation · deleting or editing CI history, job logs or audit trails.

For each of these, and for everything in production, the skill produces the command, the reasoning
and the verification steps, and Cecilia runs it. "I only needed one command" is exactly how these go wrong.

## 6. Recording

Every state-changing command that ran goes into the report: timestamp, environment (`ENV-nn`),
command, who approved it, result, and whether the rollback was rehearsed. Every command handed to
Cecilia is recorded the same way, marked `handed to Cecilia`, with her reported result once she comes
back. An apply with no record did not happen, and the next agent will believe the repo instead of
reality.
