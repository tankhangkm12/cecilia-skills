# cecilia-design — full rules and workflow

The SKILL card holds the summary; this file holds the detail. Open it at the first step on STANDARD/CONTROLLED work.

## Golden rules

1. **Interview before writing**, in grouped gates. Only what the SRS and decisions do not settle.
2. **The agent decides nothing** consequential. At least three researched options on the same criteria,
   with numbers and a separate recommendation (`decisions.md` §6–§7; `references/backend/architecture-options.md`,
   `core-flow-options.md`, `frontend/fe-options.md`).
   Cecilia's usual defaults (`references/backend/design-standards.md`) are offered as the recommended
   option — never applied silently. Low-stakes conventions may be one "approve this table" question.
3. **Research before proposing** (`decisions.md` §7): search how others solved it, current versions and
   behaviour from official docs with date, known pitfalls — or the option is `[unverified]`.
3b. **Size it before choosing.** NFRs and architecture choices carry projections — users, rps, data
   growth, connections, instances, cost — from `scripts/capacity.py` or a shown calculation (`numbers.md`).
4. **Every requirement lands or is explicitly out** (`references/traceability.md`): FR/BR → LLD section
   → table/constraint → endpoint → screen.
5. **Rules enforced only in code are not enforced.** "Exactly one", "never duplicate" → UNIQUE, CHECK,
   PK or an atomic update — or it is documented as a race.
6. **The contract is a promise.** Once approved, both sides build on it. Changing it is a decision with
   an impact table, a new version, and every dependent batch told.
7. **Contradictions stop the work.** A later decision that breaks an earlier document → conflict table,
   ask. Never patch silently, never cascade edits.
8. **Diagrams are ASCII** in code blocks.
9. **Measure**: FR+BR with an LLD section / in scope · endpoints fully specified / total · screens fully
   specified / total · threats with a control / total.

## Modes

| Cecilia says | Mode | Stages |
|---|---|---|
| "thiết kế backend", "HLD", "LLD", "schema", "API" | **Backend** | S-HLD → S-LLD (one module per run) → S-DB (cecilia-db when on) → S-API, strict order |
| "thiết kế frontend", "màn hình", "state" | **Frontend** | S-FE |
| "threat model", "phân quyền", "an toàn chưa" | **Security** | S-SEC |
| "sửa thiết kế", "đổi contract", a challenge was ACCEPTED | **Change** | S-CHG |

A forced jump (e.g. API before LLD) is recorded in "Assumptions & risks" with what is being guessed.

Prefix every message: `[cecilia-design · S-LLD · order-svc]`.

## Every stage, the same seven steps

1. **Locate.** Read the SRS, existing docs, `DECISIONS.md`. ≤ 15 lines: what is decided, what is
   `[agent-chosen — needs review]`, which stage continues.
2. **Challenge upstream** — 2–4 concrete objections (a requirement with no failure path, an NFR with no
   number, a rule two concurrent requests break). Record them.
3. **Interview · 🛑** the stage's topics, grouped.
4. **Write** from the template; drop sections that do not apply rather than leaving them empty.
5. **Exit gate** — run the stage's gate table and print every row with evidence (section names,
   tables, endpoint numbers). Never "all consistent" without the rows.
6. **Report** — full report to `tensura/reports/<TASK>/design.md`; chat/return ≤ 15 lines; update
   `tensura/docs/README.md`.
7. **Stop · 🛑** — Cecilia approves the stage (part of G1 for HIGH-risk work) or asks for changes. Update
   `tensura/tasks/<TASK>/state.md` at each stop.

| Stage | Output | Guide | Template |
|---|---|---|---|
| S-HLD | `architecture.md` (+ each `<svc>-overview.md` in microservices) | `references/backend/stage-hld.md` | `assets/architecture.md` |
| S-LLD | `<module>-design.md` | `references/backend/stage-lld.md` | `assets/module-design.md` |
| S-DB | `<unit>-database.md` — **only while cecilia-db is off**; otherwise hand the module design to cecilia-db | `references/backend/stage-db.md` | `assets/database.md` |
| S-API | `<unit>-api.md` + `.yaml` | `references/backend/stage-api.md` | `assets/api.md` |
| S-FE | `<app>-frontend.md` | `references/frontend/frontend-design.md` | `assets/frontend.md` |
| S-SEC | `security.md` | `references/security/threat-model.md`, `authz-matrix.md` | `assets/security.md` |

The layout (`docs_layout` in `.cecilia/config.json`) decides where each file goes
(`references/common/workspace.md` §2). In microservices, S-HLD also writes one `<svc>-overview.md` per
service: the modules it owns, its database, who calls it and what it calls.

## The contract stage is different

Before S-API is called done:

- every endpoint has request, response, **every error with code and status**, auth and ownership rule,
  pagination and limits, idempotency where a retry could duplicate an effect
- error codes come from one catalog and each maps to exactly one status
- the `.yaml` is valid and can generate a mock — that mock is what `cecilia-dev-fe` builds against
- dev-fe (or Cecilia) has challenged it once: is anything missing that a screen needs
- it carries a version; the plan records which batch was built against which version (and its hash)

After the contract draft, Cecilia can ask for (or the orchestrator dispatches) `cecilia-api-ux`: it reviews
the contract as its consumers experience it — calls per screen, contention/rejection rates, error DX, breaking
changes — and returns `AUX-nn` findings. Contract changes remain Cecilia's decision (Change mode when approved).

## Frontend mode in one paragraph

Screens `SCR-nn` with purpose, actor, data, actions, permissions and the `FR` they serve; for every
screen the full state table (loading, empty, partial, **each error code it can receive**,
permission-denied, offline/stale, submitting, success); component tree `CMP-nn`; one owner for every
piece of state (server cache · global · URL · form · derived); routes with guards and deep-link
behaviour; forms whose client rules name the server rule they mirror; budgets as numbers with how they
are measured. A screen that needs something the contract lacks goes into **Contract gaps** — never a
local workaround. Full guide: `references/frontend/frontend-design.md`.

## Security mode in one paragraph

Interview what the data is worth, who the plausible attacker is, what compliance applies and what
controls exist. Draw trust boundaries; STRIDE per boundary and per CORE flow; every `THR-nn` has a
scenario, likelihood and impact **with reasons**, and a control `CTL-nn` or an explicit request for
Cecilia to accept the risk (dated in `DECISIONS.md`). Then the authZ matrix: every endpoint × actor,
with the ownership condition. The design never runs scans or exploits; that is review's audit, with
A3 approval.

## Change mode

Before editing any approved document: the impact table — which sections, tables, endpoints, screens,
tests, batches and PRs the change touches, and which work already built on the old version. Cecilia
approves the change and the new version; then edit, bump the version, add the `D-nn` row with
"Replaces", and list every dependent task that must be re-checked. Never edit an approved contract
"just to match the code".

Supporting: `references/decision-log.md`, `references/traceability.md`.
