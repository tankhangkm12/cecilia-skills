# LLD → `<module>-design.md` (one module per run; path per `references/common/workspace.md` §2.1)

Input: `architecture.md`, `requirements.md`. A good LLD lets a dev code without inventing: every number, enum,
error code and step order is written. Prose without numbers is useless — each dev invents differently.

> Easiest stage to fail invisibly: the document looks complete while its most important decisions
> (how stock is held, how duplicates are stopped, how a half-failed flow is compensated) were made by
> the machine. Every such decision goes through `core-flow-options.md` and Cecilia.

## Step 1 — Pick the service, summarize (≤ 15 lines)

Ask which service first. Then: responsible for / not responsible for · calls / called by · screens
depending on it · data it owns · FR/BR IDs it implements.

## Step 2 — Classify every operation BEFORE asking

| Operation | FR/BR | CORE signals hit | Class |
|---|---|---|---|
| List products | FR-02 | none | CRUD |
| Place order | FR-05, BR-03 | money · stock · state machine · race | **CORE** |

Show it, ask if anything is missing and whether the classification is right. Unsure → CORE.

## Step 3 — Interview (grouped gates)

**3.1 Baseline (≈ 5–7):** framework/libs for this service if HLD left open · storage, cache, broker ·
auth applied here · error handling & retry toward other services · concrete limits (page size,
timeouts, field lengths, upload size) · v1 vs later.

**3.2 CORE operations — at least one question each, never merged, never "same as above":**
run `references/backend/core-flow-options.md` for each. Stop; write that section only after Cecilia picks.

**3.3 Conventions** (one bundled approval question): internal structure per architecture level,
error-code naming, constants table — using `design-standards.md` as recommended defaults.

## Step 4 — Write

Boundaries with sibling docs: column details → stage 4 doc (LLD lists tables, key columns, needed
indexes); request/response schemas → stage 5 doc (LLD writes `METHOD /path` next to each flow).

**CRUD:** one table `entity · operation · who (ownership condition) · validation · notes`.

**CORE:** one section each, all eight parts:
1. Purpose & trigger (FR/BR IDs)
2. Chosen option — what Cecilia chose, what was rejected, why (D-nn)
3. Main flow — ASCII sequence diagram
4. State machine — `state · event · new state · who may trigger`
5. Errors & edge cases — `situation · system does · user sees`, must cover: out of stock/limit ·
   external timeout · double click · two users on one record · orphan data after mid-flow failure
6. Transactions & consistency — transaction scope, locks and type, accepted delays, compensation
7. Sync vs background — returns now / queued, retries and spacing, final failure destination (DLQ? who is alerted)
8. Proposed code structure — components with one-line responsibility, matching the chosen architecture level. No real code.

Remaining sections: constants & config (every value a dev must not choose) · enums & states · events
emitted/consumed (topic, payload fields+types, key, when) · error codes (code, HTTP, when, user message)
· **handoff to stage 4**: every "exactly one X" / "never duplicate Y" / "only one of two may be null"
sentence, to become a UNIQUE/CHECK/PK · Doubts · Assumptions & risks.

## Exit gate

| # | Check | Result + evidence |
|---|---|---|
| 1 | Every CORE op has all 8 parts and "chosen option" names Cecilia's choice | |
| 2 | No CORE decision made by the agent unless labelled `[agent-chosen — needs review]` | |
| 3 | Every state has an entry and exit; no trap states | |
| 4 | Every CORE flow covers the 5 mandatory edge cases | |
| 5 | No "appropriate/reasonable/TBD" instead of numbers (outside Assumptions) | |
| 6 | Every related screen maps to a flow | |
| 7 | Every FR/BR of this service has a section | |
| 8 | Stage 3 handoff list exists (non-empty if any uniqueness rule exists) | |
