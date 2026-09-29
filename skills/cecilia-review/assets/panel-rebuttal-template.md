# Panel ballot — voter v<n> (round 2 = the vote; file keeps its v20 name)

Written by a `mode: panel-voter` agent to `tensura/tasks/<TASK>/votes/review/v<n>.json` and
`tensura/tasks/<TASK>/votes/verdict/v<n>.json` — its only two writes (`references/panel.md` §5). Every item
carries evidence the voter checked itself; an item without evidence is dropped by the tally. No
majority-guessing, no "others agree": you do not see the other ballots.

```json
{"voter": "v<n>", "model": "<model the host ran you on>", "stage": "review",
 "items": [
  {"id": "F-01", "vote": "agree", "severity": "BLOCKER", "safety": null,
   "evidence": "src/order/cancel.ts:88 — refund() runs before assertCancellable()", "reason": "double refund on retry"},
  {"id": "F-02", "vote": "disagree", "severity": null, "safety": null,
   "evidence": "tests/order.spec.ts:140 asserts 409 on second cancel", "reason": "already rejected"},
  {"id": "F-03", "vote": "abstain", "severity": null, "safety": "data-loss",
   "evidence": "migrations/0042.sql:12 — cannot tell if the backfill is idempotent without the table size", "reason": "needs a measurement"}]}
```

```json
{"voter": "v<n>", "model": "<model>", "stage": "verdict",
 "items": [{"id": "verdict", "vote": "disagree", "severity": null, "safety": null,
            "evidence": "F-01 real at <sha>; tests green at <sha> (test-summary.md)", "reason": "FAIL — a BLOCKER remains"}]}
```

`vote`: agree | disagree | abstain · `severity`: BLOCKER | SHOULD-FIX | NIT | null · `safety`: data-loss |
secret | destructive | null (set it whenever you see the risk, whatever your vote).

Return (≤ 10 lines): counts agree/disagree/abstain · any `NEW: severity · path:line · failure scenario` ·
`Rules: <hash> (PR-ids applied)` · STATUS and DEVIATIONS lines.
