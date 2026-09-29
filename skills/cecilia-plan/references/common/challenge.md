# Challenge — use challenge where it pays (common v20)

<!-- common v20 — canonical copy in shared/, synced into every skill by tools/sync_common.py. Do not edit a copy. -->

Challenge is a tool, not mandatory ceremony. Use it for CONTROLLED work, CORE/high-risk artifacts, or when a second viewpoint materially reduces risk. FAST work normally self-checks; STANDARD work challenges only the uncertain or consequential parts. Agreement nobody tested on high-risk work is momentum, not agreement.

## 1. Who challenges what

| Artifact | Owner | Challenged by |
|---|---|---|
| Idea, scope, SRS, as-built docs | discovery | design · test · review |
| HLD, LLD, threat model | design | dev-be · devops · review(security) |
| Database doc, migrations, DB-side code, performance claims | db (design while db is off) | dev-be · devops · review(database) |
| **API contract** | design | **dev-fe** · dev-be · test |
| Frontend architecture | design | dev-fe · test |
| UI design, tokens, exports | ui | dev-fe · test · review(ui) |
| **Execution plan** | plan | CONTROLLED: **dev-be · dev-fe · test · review** before G2; STANDARD: only relevant roles |
| Code / PR | dev-be · dev-fe | review · test |
| Tests, test plan | test | review · dev |
| Infra diff | devops | review(infra) · dev-be |
| Review findings | review | the artifact's owner |
| Briefing / G3 / G4 packet | orchestrator · devops | review(verify) |

## 2. The duty — before consuming an upstream artifact

Write **2–4 challenges**. Each one is:

- **Concrete** — names the section, file, line or ID.
- **Falsifiable** — predicts a failure: situation → wrong outcome, or a cost that lands later.
- **Actionable** — names an alternative and its cost.

No failure scenario → it is a question, ask it as one. Found nothing → say what you attacked:
*"Không phản đối HLD §4–§7; đã kiểm tra luồng hủy với BR-02, quyền sở hữu bảng `orders`, 3 call đồng bộ
về timeout."* "Looks good" with no list is the failure this file exists to prevent.

For FAST work, a self-check is enough. For STANDARD, one or two targeted challenges are enough when needed. Full exchange is for CONTROLLED/CORE: money, points, stock, quota ·
state machines · several actors on one record · races and duplicates · external calls that can fail
midway · irreversible actions · public contracts · schema · production · secrets.

## 3. The exchange — two rounds, then Cecilia

**Round 1.** Owner answers each: **ACCEPT** (what changes, file + section) · **REJECT** (evidence: doc
quote, code line, measurement, cited source) · **ESCALATE** (a business or priority call).
**Round 2.** Only open items. Each side writes one final position: the failure it predicts and what
evidence would make it drop the objection. **Then stop** — open items go to Cecilia:

```
| # | Item | Position A (role) | Position B (role) | Cost if A wrong | Cost if B wrong | Each side's pick |
```

Rules: silence is not agreement · no resolution by seniority, model, or who ran last · never split the
difference on a fact — find out which side is right · neither side checked → `[unverified]`, escalate ·
the challenger never edits the artifact · attack the artifact, not the agent — no praise, no apology.

## 4. Record

`tensura/reports/<TASK>/challenges.md` — append whole rows, never rewrite others' rows. Under the
orchestrator, agents return rows and the orchestrator appends them.

```
| # | Date | Artifact / ID | Challenger → Owner | Claim (failure scenario) | Response | Status | Decided by |
```

Status: `OPEN` (blocks the gate) · `ACCEPTED` · `REJECTED (evidence)` · `ESCALATED → Cecilia` ·
`DEFERRED (where tracked)`. An ACCEPTED row that changes a document becomes a `DOC-Bnn` task — a
challenge is closed by the file changing, not by the conversation.

## 5. Only one agent running

Challenge what you consume (§2), then challenge your own output once in writing — the two or three
ways it could be wrong and what would show it. Label it `[self-challenged]`: weaker than independent.
For CONTROLLED/CORE work, use an independent `cecilia-review` pass. For STANDARD, offer it when it adds confidence; FAST normally stops at self-check.
