# Review panel — lens reviewers find, three voters decide, the minutes record

One reviewer misses what its angle does not look at; one agent ruling alone has too much power. So:
**independent** lens reviewers find issues blind (breadth); the orchestrator **anonymizes** them; **3
independent voters** re-derive every finding and vote with evidence (depth); `workflow.py tally` counts; a
**minutes writer** records and changes nothing. Cecilia decides what the vote cannot (open items, vetoes, A4).

Procedure for a lens reviewer (`mode: panel-reviewer, lens: <lens>`), a voter (`mode: panel-voter`) and the
minutes writer (`mode: panel-minutes`, formerly the judge). Orchestrator side: `panel-run.md`,
`consensus.md` (cecilia-orchestrator); lenses frozen in `workflow.json`.

## 1. When (v20)

| Mode | Review | Form |
|---|---|---|
| CONTROLLED | **panel, always** — `reviewers.controlled` lenses (default 5) **+ redteam**, 3 voters, safety veto on | full |
| STANDARD | **panel, always** (`review.panel.from: "standard"`) — `reviewers.standard` lenses (default 3; the chosen option may say 4), 3 voters | full |
| FAST | **one reviewer** — a single independent review (`workflow.md` R0–R5), no panel, no vote | — |

Config (`.cecilia/config.json`, Cecilia's file — agents never write it):

```json
"review": {"panel": {"from": "standard", "reviewers": {"standard": 3, "controlled": 5},
                     "redteam_in": ["controlled"], "rounds": 2, "judge_model": "strongest"}},
"consensus": {"stages": ["plan", "review", "rootcause", "verdict"], "size": 3, "models": [], "safety_veto": true}
```

`from`: lowest mode with a panel (FAST never) · `reviewers`: lens reviewers per mode, redteam on top in
`redteam_in` modes · `rounds`: 2 = lenses + vote, 1 = light form (§8) · `judge_model`: the minutes writer's
model · `consensus.models`: one per voter (`[]` = host default → independence `weak`; a legacy
`cross_model` counts as one entry; never guess a name the host does not list).

## 2. Lenses

One section per lens; the registry points at each (`panel.md#<lens>`). Each names what the lens asks,
when the orchestrator picks it, and the **test lens report** that is its R1 evidence (§3).

### correctness
Does it do exactly what the requirements/AC/contract say — every ID, error code, state transition, edge
case? Anything implemented that traces to no ID? **Pick:** always. **Test evidence:** `test-functional.md`.

### security
AuthN/authZ and ownership (IDOR), injection, input validation, secrets, personal data in responses/logs,
CORS, rate limits. **Pick:** auth, permissions, user input, secrets, personal data, external calls.
**Test evidence:** `test-security.md`.

### data
Transaction scope, races (read-compute-write, check-then-act), migrations (locks, backfill, rollback),
idempotency of retries/consumers, events inside transactions. **Pick:** DB code, schema/migrations,
queues, money/stock/quota. **Test evidence:** `test-database.md`, `test-concurrency-perf.md`, `test-integration.md`.

### performance
N+1, unbounded queries/lists, missing index for a new query, per-row work in loops, memory growth, scale
traps on hot paths; numbers or `[projected]`. **Pick:** queries, list endpoints, loops over data, caching,
hot paths. **Test evidence:** `test-concurrency-perf.md`, `test-database.md`.

### api-consumer
Can a client use it correctly: shape, errors, pagination, retries, versioning? When `cecilia-api-ux` is on,
this lens **is** api-ux — its `AUX-nn` report enters round 1 as this lens's findings, no extra reviewer.
**Pick:** public/internal API contract changes. **Test evidence:** `test-integration.md`.

### tests
Would the tests catch a planted bug (flip a condition, drop a check, off-by-one)? Which cases are missing —
error paths, boundaries, concurrency? Reviews the test lens reports themselves (`review-tests.md` §5).
**Pick:** any behaviour change; mandatory when tests are thin. **Test evidence:** every `test-<lens>.md`.

### operations
Deploy order, rollback path, config/env/flags, observability (logs, metrics, alerts), backward
compatibility during rollout. **Pick:** CI/CD, IaC, config, migrations with deploy order, new services.
**Test evidence:** `test-infra.md`.

### ui
Loading/empty/error/partial states, a11y (keyboard, contrast, labels), responsive, matches UI doc.
**Pick:** frontend only. **Test evidence:** `test-ui.md` and its screenshots.

### simplicity
Could this be done with less code, fewer layers, no new dependency? Dead code, speculative options,
pass-through layers. Over-engineering is **SHOULD-FIX**. **Pick:** new dependency, new layer/abstraction,
large diff. **Test evidence:** none needed.

### redteam
Tries to **break** the change: hostile input, odd order of calls, partial failure, concurrency, abuse of a
legitimate feature. Not required to be fair or balanced — but every claim needs a concrete failure
scenario. **Pick:** always in `redteam_in` modes (CONTROLLED); on request otherwise. **Test evidence:**
`test-security.md`, `test-concurrency-perf.md` — and what no lens tested.

**Selection rules** (the orchestrator picks, from what the diff actually touches; frozen in `workflow.json`):
1. `correctness` always; `redteam` on top in `redteam_in` modes.
2. Fill the remaining slots by risk: security → data → api-consumer → operations → performance → tests →
   ui → simplicity, skipping any lens the diff does not touch.
3. Never more lenses than `reviewers`; an important lens that does not fit → say so to Cecilia with the
   cost of one more reviewer (she may choose an option with more).
4. Every reviewer, whatever its lens, also answers the simplicity question in one line (SKILL rule 9).
5. Models: lens reviewers use the workflow's review model; the 3 voters get different models when
   `consensus.models` lists them (§5).

## 3. Round 1 — independent, parallel

**Inputs (and only these):** the pinned SHA/diff · the docs and requirements that are the oracle ·
deterministic tool results (tests, lint, `cecilia_check.py` `evidence.json`) · **the test lens reports**
`tensura/reports/<TASK>/test-<lens>.md` (and the merged `test-summary.md`) · `panel/inputs.md`.
**Not given, not read:** the author's report or self-assessment, other reviewers' files, earlier panel
rounds. Judge first; there are no claims to read second.

**Test lens reports are evidence, not verdicts.** Read the ones your lens lists (§2). A report counts only
at the pinned SHA (other SHA → context, `[unverified]` here). Cite a test by path/name as evidence for or
against a finding; a claim "covered by test X" is `[verified]` only after reading what X asserts. An open
`BUG-<lens>-nn` is already in the fix loop — cite it, never re-file it; a finding it misses (wider scope,
another path) is yours. A lens the diff needed but no tester ran goes under "Not covered".

Each reviewer:
- answers its lens's questions (§2) against the oracle; may report a severe issue outside its lens,
  labelled `outside lens`;
- writes each finding `P-nn` with severity, `file:line`, **failure scenario (input → wrong outcome)**,
  evidence with its label (`[verified]` / `[inferred]` / `[unverified]`), and **what evidence would make
  it withdraw the finding**;
- lists what it attacked that holds, and what it could not check;
- returns the report as text (template `assets/panel-finding-template.md`); the orchestrator stores it as
  `tensura/tasks/<TASK>/panel/r1-<lens>.md`. In Cecilia's own session, if asked, a reviewer writes only its own panel file.

No finding without a failure scenario above SUGGESTION. "Could be a problem" is a QUESTION.

## 4. Anonymize (orchestrator)

After **every** lens reviewer has returned, the orchestrator merges all findings into
`tensura/tasks/<TASK>/panel/r1-all.md`: IDs `F-01…`, sorted by severity then file, **no lens names, no
model names, no reviewer order**. Two findings merge into one F-id only when they name the same place and
the same failure; the merged entry says "raised independently ×2". The F-id → lens/P-nn mapping goes to
`panel/map.md`, which no voter and not the minutes writer reads.

## 5. Round 2 — the vote (3 independent voters, one wave)

Each voter is its own cecilia-review subagent (Claude Code Agent/Task, Antigravity `invoke_subagent`;
`mode: panel-voter`, brief header `ROLE=cecilia-review UNIT=v1`–`v3`), never a lens reviewer of this round,
never the author, on the model `consensus.models` gives it. It reads `panel/r1-all.md`,
`panel/inputs.md`, the target at the pinned SHA and the oracle — never `map.md`, the `r1-<lens>` files,
another ballot or the author's report — and **re-derives every F-id** with read-only tools (read the line,
trace the caller, check the test). It writes exactly two files (`assets/panel-rebuttal-template.md` is the
ballot shape):

- `tensura/tasks/<TASK>/votes/review/v<n>.json` — per F-id `agree` (the failure is real) / `disagree` (not
  real — the refuting line, test or doc as evidence) / `abstain` (cannot check — say why); `severity`
  BLOCKER | SHOULD-FIX | NIT from the failure scenario (SUGGESTION/QUESTION → NIT); `safety` data-loss |
  secret | destructive | null; `evidence` it checked itself; a one-line `reason`.
- `tensura/tasks/<TASK>/votes/verdict/v<n>.json` — one item `verdict`: agree = PASS (in its own view nothing
  real remains at BLOCKER/SHOULD-FIX and the checks are green at the SHA), disagree = FAIL.

A severe issue nobody raised goes in its return as `NEW: severity · path:line · failure scenario`; the
orchestrator adds it as an F-id and the three vote on it — one voter alone never adopts a finding.

### Anti-conformity rules
1. **Evidence or nothing.** The tally drops an item without evidence, so the panel still decides each
   finding on evidence, never on votes without it. "I think so", "the other reviewers agree" and "the
   author probably handled it" are not evidence.
2. **Blind and anonymous.** Voters never see who wrote a finding, nor each other's ballots — seniority,
   model and lens carry no weight.
3. **Dissent is kept.** A `disagree` with evidence stays in the result and the minutes; in CONTROLLED a
   single voter's `safety` concern is a veto — never outvoted, it goes to Cecilia.
4. **Redteam is not bound to be fair** — it is bound to be concrete; its findings face the same vote.
5. **No softening to agree.** Severity follows the failure scenario, not the mood of the panel.
6. **Independence is stated.** One model for all voters → `independence: weak` in the minutes and on the card.
   `tally` checks each ballot was written by its own voter subagent (provenance): the orchestrator's is
   discarded, an unverified one → "independence unverified" on the card. Write your ballots yourself.

## 6. Tally and minutes

The orchestrator runs `workflow.py tally --stage review` and `--stage verdict` (majority = strictly more
than half of the valid voters). The **minutes writer** — a fresh cecilia-review agent on `judge_model`
that took no part and cast no ballot — reads `votes/review-result.json`, `votes/verdict-result.json`,
`panel/r1-all.md` and `panel/inputs.md` and writes `tensura/reports/<TASK>/panel/verdict.md`
(`assets/panel-verdict-template.md`), returning the same text:

- **ADOPTED** (majority agree) — severity from the tally, votes `x/3`, the decisive evidence line;
- **REJECTED** (majority disagree) — with the refuting evidence;
- **DISPUTED** (no majority) — goes to Cecilia with **the exact question** and what would settle it, on the
  decision card; **vetoes** likewise;
- **Verdict:** an adopted BLOCKER, or a FAIL verdict tally → **CHANGES_REQUIRED**; a DISPUTED item that would
  be a BLOCKER if true, or missing evidence → **INCOMPLETE** (unless already CHANGES_REQUIRED, where it is
  listed as open); a PASS verdict tally with nothing adopted at BLOCKER/SHOULD-FIX → **PASS**;
- the **Fix list** (§11) the fix loop reads.

It records the tally and never changes an outcome, merges, approves a release, accepts a risk or signs an
exception — Cecilia does (A4).

## 7. File layout

```
tensura/tasks/<TASK>/panel/     (orchestrator)
  inputs.md          pinned SHA/diff, oracle docs@version, tool results, lenses chosen and why
  r1-<lens>.md       lens report per reviewer (raw)
  map.md             F-id → lens + P-nn (nobody on the panel reads it)
  r1-all.md          anonymized findings F-01…
  fix-<n>/           the same for fix round n (1-3), scoped to the delta (§11)
tensura/tasks/<TASK>/votes/     (voters; the tally writes *-result.{json,md})
  review/v<n>.json · verdict/v<n>.json · review-result.* · verdict-result.*
tensura/reports/<TASK>/panel/   (minutes writer)
  verdict.md         the minutes — the review of record for G3/G4 · fix-<n>/verdict.md per delta round
```

A later round's ballots replace the earlier ones (same voter ids); the minutes keep the history.
`tensura/tasks/<TASK>/state.md` and any G3/G4 packet cite `panel/verdict.md` and `votes/verdict-result.json`.

## 8. Cost and the light form

Full panel ≈ **N lenses + 3 voters + 1 minutes writer** agent runs: STANDARD 3 → 7 runs, CONTROLLED 5 +
redteam → 10 runs. The cost is on the decision card; a delta review (§11) costs only the lenses that had
findings, the 3 voters and the minutes.

**Light form** (only when the chosen option says so, or `rounds: 1`): 2 lenses (`correctness` + the lens the
diff most needs) + 3 voters + minutes. With `consensus.size` below 3 (Cecilia's config) there is no
majority to trust: every finding the minutes would adopt is re-derived by the minutes writer and marked so.

## 9. Hosts

Members never talk to each other or spawn agents; files carry every step. Sequential hosts run the same
steps one fresh agent at a time. No sub-agent tool → no independent panel or vote; say so and offer one
independent review in a new session.

## 10. How Cecilia reads the verdict

Verdict line and counts → **Needs Cecilia** (DISPUTED and vetoes, each an exact question — they are on the
decision card) → **Adopted** by severity with votes (BLOCKER/SHOULD-FIX go to the fix loop, §11) →
**Rejected** with the refuting evidence (she may reopen any) → **Dissent kept** → **Coverage** (lenses run,
voter models and independence, what nobody checked; a missing lens is not a PASS for it). Merging,
accepting a risk, signing a SHOULD-FIX exception and releasing stay Cecilia's (A4).

## 11. Fix loop — the minutes feed it, a delta review closes it (v20)

**Minutes → fix loop.** The **Fix list** holds every ADOPTED finding whose severity is in
`fix_loop.severities` (BLOCKER, SHOULD-FIX): `F-id · severity · path:line · failure scenario · owner (by
lane)`. The orchestrator sends it, with the open `BUG-<lens>-nn` rows from `test-summary.md`, to the owning
writers as fix round `ROUND=n` (max `fix_loop.max_rounds` = 3). **DISPUTED goes to Cecilia**, never to
the fix loop. NIT stays in the report. An owner may reject a finding with evidence instead of fixing it
(`challenge.md`); the next vote answers that evidence.

**Delta review** of the new SHA, still R1 → R2 → judge — lenses → voters → minutes, files under `fix-<n>/`:
- **Who:** only the lenses that had findings on the Fix list (the orchestrator maps F-ids to lenses with
  `map.md`; redteam included when it had one), then the 3 voters `v1`–`v3`. No new lens unless the fix
  touched an area no lens covered — then the orchestrator puts it on the card.
- **Scope:** the diff from the last reviewed SHA to the new SHA, the lines of the lens's own earlier
  findings, and the re-run test lens reports at the new SHA. Not the whole change again.
- **Lenses:** each earlier F-id → `RESOLVED` / `PARTIAL` / `NOT_RESOLVED` with evidence at the new SHA, plus
  new findings the fix introduced (new F-ids continue the numbering; old F-ids are kept).
- **Vote:** every open F-id (earlier ones not agreed RESOLVED, and the new ones) and the verdict item.
- **Minutes:** same rules (§6); a new Fix list. Empty list, verdict PASS, nothing DISPUTED → the loop
  ends. Rounds exhausted with the list non-empty, a FAIL with nothing left to fix, or anything DISPUTED →
  stop; Cecilia gets options on the card (`fix_loop.on_exhausted`).
