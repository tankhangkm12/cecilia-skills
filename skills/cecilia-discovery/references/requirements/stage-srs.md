# SRS → `tensura/docs/system/requirements.md`

Input: `tensura/docs/system/idea.md`. Format: IEEE 29148-lite skeleton, with requirements expressed as use cases
and/or user stories carrying Given/When/Then acceptance criteria. This is the contract every later
role cites by ID.

## Step 1 — Summarize understanding (≤ 15 lines)

Problem, actors, version-1 scope, hard constraints. Ask if correct (one question).

## Step 2 — Interview (≈ 8–15 questions, one per turn)

Go feature by feature from the in-scope table. For each feature, ask only what is still unknown:

1. **Who triggers it, preconditions, main flow, alternative flows, failure flows.**
2. **Business rules** — limits, formulas, eligibility, state transitions, time windows, rounding.
   Each rule becomes `BR-nn`. Numbers, not "reasonable".
3. **Data** — fields the user enters/sees, required/optional, formats, max lengths.
4. **Permissions** — which role, and ownership conditions ("only the order owner").
5. **Acceptance** — confirm the Given/When/Then set you drafted, especially negative cases.
6. **Non-functional** (once, globally, then per feature if different) — performance with numbers,
   availability, security, privacy, audit, accessibility, localization, compatibility, retention.
7. **Priority** — MoSCoW per requirement (Must/Should/Could/Won't for v1).

Classify each feature CORE vs CRUD (SKILL.md) and show the table before deep questions; CORE features
get more questions. Choosing a user-story vs use-case view per feature is Cecilia's call — ask once for
the whole document.

## Step 3 — Write rules

- IDs: `FR-nn`, `NFR-nn`, `BR-nn`, `UC-nn` / `US-nn`, `AC-nn`. Never renumber once published; retire
  with "~~FR-07~~ removed D-12".
- Every FR is **atomic, testable, unambiguous**: one "shall" per FR, no "etc.", "fast", "user-friendly",
  "as appropriate". Replace with numbers or enumerations.
- Every FR has ≥ 1 AC; every AC is Given/When/Then with concrete values, including at least one
  negative AC for each FR that can fail.
- Every NFR has a metric, a target and a measurement method.
- Glossary for every domain term; later docs use exactly these terms.
- Traceability matrix: idea scope row → FR/NFR → UC/US → AC.

## Exit gate

| # | Check | Result + evidence |
|---|---|---|
| 1 | Every in-scope row of stage 0 maps to ≥ 1 FR | |
| 2 | Every FR has ≥ 1 AC in Given/When/Then with concrete values; failing FRs have a negative AC | |
| 3 | No banned vague words in FR/NFR/BR (list any found) | |
| 4 | Every NFR has metric + target + measurement | |
| 5 | Every BR is referenced by ≥ 1 FR/UC | |
| 6 | Every actor from stage 0 appears in ≥ 1 UC/US | |
| 7 | Every FR has a priority and permission condition | |
| 8 | CORE features are flagged, ready for stage 3 option treatment | |
