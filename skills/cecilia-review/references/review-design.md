# Reviewing design documents

Scope: whole chain when available (idea → SRS → HLD → LLD → DB → API → test plan) even if one doc is named,
because most defects are cross-stage.

## 1. Requirement quality (SRS; IEEE 29148 characteristics)
Each FR/NFR/BR is: necessary · unambiguous (no "fast", "user-friendly", "etc.", "as appropriate") ·
complete (actor, trigger, data, failure flows, permission) · singular (one "shall") · feasible · verifiable
(ACs in Given/When/Then with concrete values incl. negative ACs; NFR metric + target + method) · correct ·
consistent (no conflicts with other requirements/glossary) · traceable (IDs, source). Also: glossary terms
used consistently, priorities set, actors all served, out-of-scope explicit.

## 2. Cross-stage consistency (traceability)
Forward: every in-scope item → FR → service → LLD section → table/constraint → endpoint/event → test case.
Backward: later decisions breaking earlier docs (e.g. presigned upload vs NOT NULL FK; cursor pagination vs
unstable sort column; idempotency without unique key storage). LLD "exactly one / never duplicate" rules → named
UNIQUE/CHECK. Every error code → test case. Decisions log entries → where implemented; agent-chosen entries
still unconfirmed. Screens ↔ endpoints both ways. Permission column complete with ownership conditions.
Print a conflict table: `doc · section · says · conflicts with · proposed fix`.

## 3. Architecture & data soundness
Data ownership single per dataset · boundaries match change cadence · sync chains/temporal coupling · every
infra component justified by a flow · CORE operations have ≥ 2 options considered and a named concurrency/
idempotency mechanism · transactions never span external calls · state machines without trap states · compensation
for multi-step flows · schema: normalization, constraints, index-per-query, money/time types, migration and
rollback, growth plan · API: envelope/errors/pagination/idempotency consistent, every field constrained, every
list paginated · security table (IDOR, PII at rest, secrets, uploads, never-log fields, rate limits) · ops table
(environments, migrations under traffic, rollback, health/alerts) · backups per data store with RPO/RTO.

## 4. Reality check — research (mandatory for any technology claim)
Follow `common/capabilities.md`. For each technology/version/pattern relied upon, verify: exists and behaves as
described in that version · support/LTS window and license · known limits, pitfalls, breaking changes, CVEs ·
operational burden versus team size · comparable real-world usage · concrete syntax chosen does what the
decision says (e.g. UUID function version, hashing algorithm, pagination query). NFR targets achievable with the
proposed design at the stated scale (back-of-envelope: requests/s × latency × instances; data growth × retention).
Cite sources in findings; no access → `[unverified]` + what to check.

## 4b. Options and numbers

Every consequential choice in the design shows ≥ 3 options when three genuinely exist (or says why
fewer), compared on the same criteria, with the recommendation separate and a note of what would change
it (`decisions.md` §6). NFRs and sizing carry projections with formula, inputs and low/expected/high
(`numbers.md`). A design that states "scales well" or picks a technology without a comparison is a
SHOULD-FIX; a choice that fails its own projection is a BLOCKER.

## 5. Feasibility vs context
Team size/skills, timeline, budget, compliance, legacy constraints from stage 0. Missing context needed to judge
→ ask Cecilia (grouped gates) before concluding.

## 6. Severity for design findings
Blocker: contradiction between stages, requirement not verifiable/implementable, data-ownership conflict,
missing concurrency mechanism on money/stock, security gap by design, technology claim proven false. Should-fix:
vague wording with limited impact, missing index/limit, weak doubt/assumption sections. Suggestion: structure,
wording. Question: business context needed.
