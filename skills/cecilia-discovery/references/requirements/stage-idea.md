# Idea, feasibility, scope → `tensura/docs/system/idea.md`

Goal: from a one-line idea, settle **what is built for whom, whether it is worth it, and exactly what
version 1 contains**. The point is to avoid building the wrong thing.

## Step 1 — Identify the project (first questions)

- Type: web app · mobile app · internal API/service · data pipeline · integration · internal tool · hybrid.
  Later stages depend on it (a pipeline has no screens).
- Greenfield or brownfield. Brownfield → Step 1b.

### Step 1b — Current-system inventory (brownfield only)

Read reachable code/schema/docs yourself, then present this table for Cecilia to correct (one question):

| Item | Content |
|---|---|
| Existing system (stack, architecture, data size) | |
| Existing data the new part must use | |
| APIs with real clients (contract frozen) | |
| Current auth/permission mechanism | |
| Must not break | |
| Current pain to fix along the way | |

No access → say so; every row becomes an assumption.

## Step 2 — Six topics (≈ 6–9 questions, one per turn)

1. **Real problem** — how do people cope today? "Fine" is a signal worth saying out loud.
2. **Actors** — role, goal, frequency.
3. **Main journey** of the key actor — steps from discovery to goal; where they drop off.
4. **Scale & constraints** — users, transactions/day, team size, timeline, infra budget, hard deadlines.
5. **Mandatory constraints** — legal, personal data, legacy integrations, user devices.
6. **Success criteria** — numbers, not adjectives.

## Step 3 — Prepare, then ask Cecilia to decide

Do these yourself, present them as proposals, and ask Cecilia to confirm/edit (one question each):

**3.1 Honest feasibility:** unrealistic parts · more expensive than expected · uncontrollable
dependencies · who built something similar and how (research, cite) · most likely point of failure.

**3.2 Often-forgotten business areas** — judge each for this project and turn relevant ones into
scope proposals:

| # | Area | Self-question |
|---|---|---|
| 1 | Account lifecycle | reset password, change email, lock/unlock, delete, data handover |
| 2 | Org structure | departments/branches/tenants? |
| 3 | Notifications | channels, opt-out, anti-spam |
| 4 | Search & filter | scope of search |
| 5 | Import/export | reports, CSV, bulk import |
| 6 | Backup & restore | **one row per data store** (DB, object storage, cache, search index) with RPO/RTO |
| 7 | Operators | what admins see/do; separate endpoints? |
| 8 | Audit log | which actions need who/when/from→to |
| 9 | Limits & abuse | rate limits, max sizes/counts |
| 10 | Personal data | collected fields, visibility, deletion on request, never-log fields |

**3.3 In/out scope proposal** — every feature named anywhere ends in exactly one table; each
out-of-scope row has a concrete reason and "revisit when".

## Step 4 — Write

Template `assets/idea.md`. Record decisions in `DECISIONS.md`.

## Exit gate

| # | Check | Result + evidence |
|---|---|---|
| 1 | Every actor has ≥ 1 in- or out-of-scope row serving them | |
| 2 | Every feature named in the journey or in option tables is in in- or out-scope | |
| 3 | Every out-of-scope row has a concrete reason | |
| 4 | All 10 forgotten-area rows judged; non-applicable rows say why | |
| 5 | Success criteria are numbers | |
| 6 | Each expected data store has its own backup row | |
