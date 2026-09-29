# Decision log → `tensura/docs/DECISIONS.md`

<!-- scoped source: shared/scoped/docs/decision-log.md — synced by tools/sync_common.py. Do not edit a copy. -->

The design chain spans many sessions; this file is the project's memory of why things are the way they are.

```markdown
# Decisions — <project>

| ID | Date | Stage | Question | Decision | Decided by | Why | Affects | Replaces |
|---|---|---|---|---|---|---|---|---|
| D-01 | 2026-09-04 | 0 | Mobile app in v1? | No, responsive web | Cecilia | 2 devs | HLD, API | |
| D-02 | 2026-09-04 | 2 | Architecture | Modular monolith | Cecilia | ~500 orders/day | LLD, DB | |
| D-03 | 2026-09-05 | 4 | PK type | UUIDv7 | [agent-chosen — needs review] | "up to you"; needs time ordering | DB, API | |

## Chain status
- [x] Stage 0 — done 2026-09-04
- [ ] Stage 3 (order) — in progress, stopped at Q4

## Pending questions
| # | Stage | Question | Options | Recommendation |
|---|---|---|---|---|
```

- **Decided by** is the most important column. Agent choices must carry `[agent-chosen — needs review]`
  and be listed at the top of the stage doc's Assumptions & risks.
- **Affects** tells which docs to re-check if this row changes.
- Changing an earlier decision: add a new row with "Replaces D-02" — never delete history; then check
  every doc in the old row's Affects, print the conflict table (`traceability.md`), ask whether to
  apply. **Never cascade edits automatically**; Cecilia must see the blast radius first.
