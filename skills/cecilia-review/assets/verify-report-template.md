# Verification — <TASK> briefing of <YYYY-MM-DD>

> **VERIFY · <TASK> · <PASS | FAIL (n blockers, m should-fix)>**
> Checked: <draft path> against <count> sources
> Commission: <n> claims — <p> PASS · <f> FAIL · <u> UNSUPPORTED
> Omission: <n> items in sources — <k> missing from the briefing
> Blockers: <the one that matters most, named — or "none">
> Next: <cecilia-orchestrator (briefing) fixes and re-submits | publish approved>

Independence: <checked by a different agent than the author | `[self-verified — weaker]`>

## 1. Commission — each claim against its source

| # | Claim in the briefing | Source cited | What the source says | Verdict |
|---|---|---|---|---|
| 1 | coverage 72.4% for order module | `metrics.md` M-07 | 64.2% (412/642), branch coverage | **FAIL** — wrong value and wrong metric |
| 2 | B-02 merged | plan status table | B-02 = DRAFT_PR | **FAIL** — not merged |
| 3 | payment area reviewed, no blockers | — | no review report exists for payment | **UNSUPPORTED** |

Verdicts: `PASS` (source says exactly this) · `FAIL` (source says otherwise) · `UNSUPPORTED` (no source
says it). See `references/verify/verification-method.md` §2.

## 2. Omission — what the sources hold and the briefing must carry

| # | Item found in sources | Where | In the briefing? |
|---|---|---|---|
| 1 | C-08 ESCALATED to Cecilia | `challenges.md` | **MISSING** |
| 2 | B-03 BLOCKED on staging access | plan status table | yes |
| 3 | p95 regressed 240ms → 310ms | `metrics.md` M-11 vs M-08 | **MISSING** |

## 3. Discrepancies to fix

| # | Severity | What is wrong | Source of truth | Fix |
|---|---|---|---|---|
| D-1 | BLOCKER | coverage stated 72.4%, log says 64.2% | `metrics.md` M-07 | quote M-07 as written |
| D-2 | BLOCKER | C-08 (ESCALATED) absent from the decision queue | `challenges.md` C-08 | add to "Needs your decision", first |
| D-3 | SHOULD-FIX | progress "most of B-02 done" | plan status table | state done/total with the denominator |

## 4. Verdict

<PASS — publishable> | <FAIL — n blockers must be fixed against the sources, then re-verify. This note
is not edited; the next pass gets its own note.>
