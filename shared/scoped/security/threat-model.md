# Threat modelling — STRIDE per boundary and per flow

<!-- scoped source: shared/scoped/security/threat-model.md — synced by tools/sync_common.py. Do not edit a copy. -->

## 1. Trust boundaries, in ASCII

```
 internet
    │  ← B1: anonymous, hostile, unlimited attempts
 [gateway]  auth, rate limit, TLS termination
    │  ← B2: authenticated, but the identity is a claim until verified per request
 [order-svc] ──→ B4: SQL, ORM ──→ (orders db)
    │  ← B3: service-to-service; does the callee trust the caller's headers?
 [payment partner]  ← B5: their failure is your inconsistency
 [CI] ──→ B6: build-time access to secrets and to what ships
```

Every arrow crossing a boundary carries: what data · which identity · what happens if the caller
lies. That third column is the threat model in miniature.

## 2. STRIDE, with what it actually means here

| | Threat | The question that finds it |
|---|---|---|
| **S** | Spoofing | can someone act as another user or service? token replay, no `aud`/`iss` check, long expiry, no revocation, internal services trusting an `X-User-Id` header |
| **T** | Tampering | can data be changed in transit or at rest by someone who should not? mass assignment, unsigned webhooks, client-supplied prices or totals, mutable audit rows |
| **R** | Repudiation | can someone deny doing it? no audit trail on money or state changes, logs without actor and requestId, logs a user can edit |
| **I** | Information disclosure | what leaks? IDOR, over-fetching DTOs, stack traces, error messages that distinguish "no such user" from "wrong password", PII in logs, public buckets, verbose 500s |
| **D** | Denial of service | what is unbounded? no rate limit, unbounded page size, unbounded upload, expensive search, a regex on user input, an N+1 behind a public endpoint |
| **E** | Elevation of privilege | how does a normal user become an admin? role from a client-supplied field, missing ownership check, an admin endpoint behind obscurity only, a mass-assignable `role` |

Run it per boundary **and** per CORE flow (money, state machines, anything with several actors on one
record). A flow-level threat is invisible at the boundary level: "cancel an order twice in parallel
and get refunded twice" crosses no boundary and appears in no endpoint list.

## 3. Threat format

```markdown
### THR-07 · High · Elevation of privilege · B2 · EP-14 `PATCH /users/{id}`
- **Actor:** any authenticated customer
- **Precondition:** knows another user's id — visible in the order list response [verified: order-api.md §4.2]
- **Steps:** send PATCH with `{"role":"ADMIN"}` to their own id; the DTO is bound to the entity
- **Result:** self-elevation to admin; full data access
- **Likelihood:** High — needs no special tooling, one request
- **Impact:** High — full account takeover of the tenant's data
- **Control CTL-07:** whitelist DTO fields, never bind entities from requests; `role` changes only
  through an admin-only endpoint with its own audit row
- **Cost of the control:** one DTO and one endpoint; no schema change
```

A threat without Actor / Precondition / Steps / Result is not ready to be reported.

## 4. Where to look first, by system shape

| Shape | The classic finding |
|---|---|
| Multi-tenant | every query missing a tenant filter; one shared cache key |
| Marketplace / multi-actor | buyer acting on a seller's resource; ownership checked in the UI only |
| Money or points | double-spend under concurrency; totals computed client-side |
| File upload | type trusted from the client, path traversal, public storage, no size cap |
| Webhooks in | no signature check, no replay window, no idempotency |
| Background jobs | run as a superuser; input from a queue never validated |
| Admin panels | protected by not being linked |
| Mobile/SPA | secrets in the bundle, authorisation decided in the client |

## 5. Controls

A control names **where it lives** (gateway, middleware, service, database constraint, infrastructure)
and **who implements it** (`cecilia-dev-be`, `cecilia-dev-fe`, `cecilia-devops`). Prefer, in order:

1. **Structural** — the database makes it impossible (constraint, foreign key, row-level rule).
2. **Systematic** — one place every request passes: a guard, an interceptor, a policy layer.
3. **Per-endpoint** — a check on each handler; correct, but someone will forget one.
4. **Procedural** — a rule people must remember; the weakest, and it needs a test to survive.

A control at level 3 or 4 on a Critical threat carries a required test case, named in the report so
`cecilia-test` picks it up. Otherwise it decays the first time the code is refactored.
