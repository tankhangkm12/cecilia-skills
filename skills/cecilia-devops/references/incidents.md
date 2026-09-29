# Incidents — something is broken now

This replaces Y1–Y6 while an incident is live. The production rules do not relax because it is
urgent: the agent reads what it is allowed to read and **changes nothing** — every production command,
reversal included, is prepared for Cecilia to run (`authority.md` §4). Most of the
damage done during incidents is done by someone in a hurry who changed a second thing before knowing
what the first one did.

Open `INC-nn` immediately and write as you go — the timeline is worthless reconstructed afterwards.

## N0 — Establish the facts (only what you may read)

Three answers, in this order, each with where it was read from:

1. **What is the user-visible impact?** Which users, which operation, since when, how bad —
   errors, slowness, or silently wrong results (the worst kind, and the one health checks miss).
2. **What changed?** Deploys, config changes, feature flags, migrations, infrastructure applies,
   certificate or credential expiry, a dependency's own incident, a traffic change. Start at the
   moment impact began and look backwards — `git log`, deploy history, pipeline runs, the audit trail.
   Deploy markers on the dashboard usually answer this in seconds.
3. **What is the current state?** Replicas, revision/digest, restarts, resource pressure, queue
   depth, dependency health, error signature. Read it; never remember it.

Say plainly when something could not be read, and what that leaves uncertain.

## N1 — Report to Cecilia and ask

One short message, no speculation dressed as fact:

```
🔴 INC-03 · ENV-03 prod · từ 14:02 (+22 phút)
Ảnh hưởng: ~40% request /checkout trả 500; các luồng khác bình thường [verified]
Nghi vấn: deploy orders v1.5.0 lúc 13:58, trùng thời điểm [verified: marker + deploy log]
Trạng thái: 6/6 pod Running, 0 restart, p99 DB bình thường [verified]
Chưa đọc được: log của payment-gateway (không có quyền)

Đề xuất (bạn chạy): rollback orders về revision 7 — hoàn tác thuần
  Lệnh:     helm rollback orders 7 -n prod   # context: gke_acme_prod
  Hoàn tác của hoàn tác: helm rollback orders 8 -n prod
  Khỏi khi: tỉ lệ 500 của /checkout về < 0.5% trong 5 phút
Bạn chạy lệnh này và báo lại kết quả; tôi sẽ kiểm tra theo điều kiện "Khỏi khi".
```

Then wait. If she is not there: keep reading what you may, keep writing the timeline, change nothing.

## N2 — Stabilise: one action, then stop

Reversal before diagnosis. Getting users working again is not the same as understanding the bug, and
trying to do both at once is how the second outage happens.

- Exactly **one** action, run by Cecilia — preferably a pure reversal: roll back, restore a replica
  count, re-enable what was just disabled.
- Then **verify** with the recovery check that was stated before the action ran, from the output or
  telemetry she shares.
- It did not help → **stop**. Do not try a second thing. Report what changed, what it did, and what
  the next options are. Two unverified changes and nobody can tell which did what.
- A forward change — a hotfix, a config edit, a scale-up — is a different decision with more risk;
  compose it separately with that risk stated, and let her choose.

## N3 — Recovery confirmed

State the evidence, not the feeling: the metric that identified the impact is back to normal, for a
stated period, read directly. Then mark the incident stable in `INC-nn` with the timestamp, and say
clearly that the **cause is not yet fixed** — a rollback hides a bug, it does not remove it. The
thing that broke will be redeployed by someone unless it is tracked.

## N4 — Handover, if it is still open

If the chain stops here (Cecilia leaves, another agent takes over), `INC-nn` must hold enough to
continue cold: timeline with timestamps and sources, what was ruled out and how, every action taken
and by whom, current state, and the next two things worth checking. Nothing in an agent's memory,
all of it in the file.

## N5 — Postmortem

Written after recovery, calmly, blameless. People act reasonably given what they can see; if someone
made a wrong call, the question is what made the wrong call look right.

| Section | Content |
|---|---|
| Impact | who, what, how long, how measured |
| Timeline | first symptom → detection → each action → recovery, with timestamps and sources |
| Cause | the mechanism, at the level where an action can be taken. Keep asking "and why was that possible?" past the first plausible answer |
| Detection | how it was found, and how long it took. Found by a customer → that is a finding of its own |
| What went well | preserve what worked — the rollback that existed, the marker that pinned the deploy |
| Where luck helped | the parts that would have been much worse with different timing |
| Actions | each one concrete, owned, and assigned a role: `cecilia-dev-be` / `cecilia-dev-fe` (code), `cecilia-devops` (infra, alerting), `cecilia-test` (regression), `cecilia-design` (the design assumption that did not hold) |

Actions go through the normal route — a plan batch or an `infra/` PR. A postmortem whose actions are
never scheduled is a document that records the same outage twice.

**Every incident asks two questions of this skill's own work:** would the alert have caught it sooner
(`observability.md` §4), and was the rollback actually rehearsed (`deploy-and-rollback.md` §4)? If
the rollback failed or surprised anyone during the incident, that is the first action item.

## Template

`assets/incident-report-template.md` → `tensura/reports/<TASK>/<date>-devops-incident-INC-nn-<slug>.md`.
Secrets appear by **name only**, always (`secrets.md` §4).
