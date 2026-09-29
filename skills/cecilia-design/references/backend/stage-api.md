# API contract → `<unit>-api.md` + `<unit>-api.yaml` (path per `references/common/workspace.md` §2.1; `<unit>` = module in a monolith, service in microservices)

Input: LLD + DB of the service. The contract lets frontend and backend build in parallel and still fit:
every field has a type, constraints and a real example. YAML = OpenAPI 3.1 importable into Swagger/Postman.

## Step 1 — Work backwards from screens

Screen → data shown → user actions → endpoints. Never generate CRUD from tables (you get unused
endpoints and miss the ones screens need). Internal APIs without screens → start from LLD operations.

## Step 2 — Six decisions before YAML (one question each, skip what HLD already decided)

1. Prefix and versioning (`/api/v1`)
2. Response shape (Cecilia's envelope standard as recommended option, with its closed exemption list)
3. Pagination: offset or cursor (and stable sort key)
4. Error body shape and business error-code catalog
5. Idempotency for create/payment endpoints: mechanism, key storage, TTL, replay behaviour
6. Naming: plural nouns, kebab/snake in path, camelCase/snake_case in body

## Step 3 — Cross-check against stage 4 BEFORE writing YAML

| Stage 4 decision | What it demands from the DB | Current DDL OK? | Action |
|---|---|---|---|
| Multi-step upload (presigned URL) | child row before parent → nullable FK or staging table | | |
| Idempotency-Key | key column + UNIQUE + expiry column | | |
| Cursor pagination | immutable sort column + index | | |

Conflict → stop, print the conflict table (`traceability.md`), ask whether to change DB or API flow.

## Step 4 — Summary `.md` (template `assets/api.md`)

`# · method · path · purpose · permission (with ownership condition) · LLD § · screens · status codes`.
**Permission column never empty.** For endpoints touching a specific resource, write the ownership
condition ("user, only when `order.user_id` = caller"), not just a role — prevents IDOR by design.
Shared error table: `code · HTTP · meaning · user message`.

## Step 5 — YAML

`components/schemas` for every entity · `securitySchemes` + per-endpoint `security` · real
request/response examples (never `"string"`) · example body for every error · descriptions in chat
language · every field typed and constrained (`maxLength`, `minimum`, `enum`, `format`) · every list
paginated. Validate with a parser if available.

## Step 6 — Consumer review (optional but recommended)

After the contract draft, Cecilia can ask for (or the orchestrator dispatches) `cecilia-api-ux`. It reviews the
contract as its consumers experience it — calls and sequential depth per screen, contention/rejection rates on
hot keys, error DX (can a client act on each error), breaking changes against the previous version — and
returns `AUX-nn` findings with owner and measurable acceptance. Findings on the contract come back to this role
as change requests; **contract changes remain Cecilia's decision** (Change mode once she approves). Record in
the report which findings were applied, rejected or still open.

## Exit gate

| # | Check | Result + evidence |
|---|---|---|
| 1 | Every endpoint traces to an LLD operation / FR | |
| 2 | Every LLD operation has an endpoint or event (list both directions) | |
| 3 | Every screen has endpoints to display and to act | |
| 4 | Permission column complete; resource endpoints state ownership | |
| 5 | Every endpoint has ≥ 1 error case | |
| 6 | Every field typed + constrained; every list paginated | |
| 7 | Step 3 cross-check done (state which 3 checks and results) | |
| 8 | YAML parses (if a tool exists) | |
