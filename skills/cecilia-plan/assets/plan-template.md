# Plan — <TASK> — <epic title>

> State: `DRAFT` | `IN APPROVAL` | `ACTIVE` (see §11 — only Cecilia's approval makes a batch active) · Last updated: <YYYY-MM-DD>
> Repo: <url/path> · Base branch: `<branch>` · Plan delivery: <file only | PR (commands for Cecilia — local-only, `git-handoff.md` §1)>
> Handoff: the final batch ends with the push + `gh pr create --draft … --body-file tensura/reports/<TASK>/pr-body.md` commands for Cecilia — no push step · State: `tensura/tasks/<TASK>/state.md`
> Commits by: <agents, locally inside the scope | Cecilia> · Output language: <chat language / repo convention>
> Environments in scope for agents: `local` <, `ENV-02 staging` (every apply still A3)> · Production: **never agents** (A4)
> Parallel: units with disjoint write sets; the number of agents per wave comes from the option Cecilia chose (no configured cap unless `parallel.limits` is set) · waves in §<n> · one branch per unit

## 1. Sources
| Doc | Location | Sections used | Version / commit / date read | Confidence |
|---|---|---|---|---|

## 2. Scope
**In scope:** <bullets with IDs>
**Out of scope:** <bullets with reason> — stated so nobody assumes it was done

**Simpler option considered:** <the simplest approach that would also meet the goal; why this plan is not simpler>

## 3. Requirements traceability
| ID | Doc § | Requirement (near-verbatim) | Batch | Dev task | TEST task | OPS task | Status |
|---|---|---|---|---|---|---|---|
| FR-01 | SRS §3.1 | | B-01 | BE-B01 | TEST-B01 | — | TODO |
| NFR-03 | SRS §5.2 | p95 < 300ms at 50 rps | B-01 | — | TEST-B01 | OPS-B01 | TODO |

## 4. Decisions, clarifications and recorded exceptions
| ID | Question / exception | Decision (Cecilia's words for exceptions: pattern, scope, expiry) | Decided by / date |
|---|---|---|---|
| P-D01 | LLD §4.2 says 409, API §2.5 says 422 | 409, API doc to be fixed (DOC-B01) | Cecilia 2026-09-17 |

## 5. Batches
| Batch | Goal (one sentence) | IDs | Depends on | Parallel with (+ proof) | Contract version | Scope id |
|---|---|---|---|---|---|---|
| B-01 | | | — | — | `order-api.yaml` v3 (sha256 …) | `<TASK>-B01` |

Sequence per batch: `G2 → BE ‖ FE → integration candidate → TEST → REV → G3 → Cecilia merges`
`[→ OPS → REV(infra) → A3 applies to ENV-nn → rollback rehearsed]` <or the variant Cecilia chose>

Batches with no delivery-path work: <list, so nobody looks for a missing OPS row>

## 6. Tasks and status
Each role edits only its own row.

| Task | Role | Covers | Inputs | Expected files (exact) | Commands | Branch | Depends on | Done when | Status | Owner | PR / report |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BE-B01 | dev-be | FR-01, BR-02 | LLD §4.1 | `src/modules/order/**`, `src/app.module.ts` | `npm test -- order`, `npm run lint` | `feat-be/<TASK>-01-…` | scope active | PR text ready, checks green, IDs verified | TODO | | |
| FE-B01 | dev-fe | SCR-02 | web-frontend.md §3, contract v3 | `web/src/order/**` | `pnpm test order`, `pnpm build` | `feat-fe/<TASK>-01-…` | scope active | same, budgets measured | TODO | | |
| TEST-B01 | test | AC-01..03 | test plan §4 | `test/order/**` | `npm run test:int -- order` | `test/<TASK>-01-…` | BE-B01, FE-B01 on candidate | run report on candidate SHA | TODO | | |
| REV-B01-C | review | BE/FE PRs | plan, docs | — (read-only) | — | — | code frozen at SHA | report, 0 open BLOCKER | TODO | | |
| OPS-B01 | devops | NFR-03, env var `ORDER_TTL` | LLD §7, infrastructure doc §3 | `.github/workflows/order.yml`, `deploy/order/**` | `actionlint`, `helm lint deploy/order` | `infra/<TASK>-01-…` | BE-B01 merged | applied to ENV-02 via A3 + rollback rehearsed | TODO | | |
| DOC-B01 | design | P-D01, C-07 | LLD §4.1 | `tensura/docs/modules/order/order-api.md` | — | — | — | doc updated, gate re-run | TODO | | |

Status: `TODO` → `IN_PROGRESS` → `READY_FOR_REVIEW` → `READY_FOR_CECILIA` (G3 packet) → `MERGED` → `DONE`,
or `BLOCKED: <reason>`. Ops rows add `APPLIED (<ENV-nn>)`; `DONE` needs the rollback rehearsed.

## 7. Risks
| # | Risk | Impact | Mitigation / owner |
|---|---|---|---|

## 8. Proposals outside the docs (await Cecilia)
| # | Proposal | Why | Options | State |
|---|---|---|---|---|

## 9. Open questions
| # | Question | Options | Recommendation | Blocks |
|---|---|---|---|---|

## 10. Plan changes
| Date | Change | Reason | Approved by |
|---|---|---|---|

## 11. Approvals (filled after Cecilia approves — never by an agent on its own)
| Scope id | Approved at | By | Evidence (`.cecilia/approvals/<id>.json` or her quoted words) | Expires |
|---|---|---|---|---|

## 12. Scope blocks — what Cecilia approves (G2)

Approve a batch by running in your own terminal:
`cecilia approve tensura/plans/<this file> --task <TASK>-B01`

```cecilia-scope
{
  "task": "<TASK>-B01",
  "write": [
    "src/modules/order/**",
    "src/app.module.ts",
    "web/src/order/**",
    "test/order/**",
    "tensura/reports/<TASK>/**"
  ],
  "commands": ["npm test -- order", "npm run lint", "pnpm test order", "pnpm build", "npm run test:int -- order",
               "PORT=3100 npm run dev", "playwright-cli -s=<TASK>-fe *", "python3 .claude/skills/cecilia-dev-fe/scripts/uikit.py *"],
  "environments": ["local"],
  "expires_hours": 72
}
```
