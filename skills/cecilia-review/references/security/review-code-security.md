# Security review of code — against the model, not against a feeling

The threat model says what should be true. This pass checks whether it is, in the code, with
citations. Where no model exists, build the minimal one first (`threat-model.md` §2–§3) — reviewing
code for "security issues" with no model produces a list of habits, not a list of risks.

## 1. Order of reading

1. **The boundary code**: guards, middleware, interceptors, the auth layer, the gateway config. One
   flaw here outweighs fifty in handlers.
2. **The endpoints in the authZ matrix** whose ownership condition needs a join, plus every endpoint
   added since the last review.
3. **The CORE flows**: money, state machines, anything several actors touch.
4. **The edges**: file upload, webhooks in, background consumers, anything parsing user input.
5. Only then, breadth.

## 2. What to verify, with the evidence each needs

| Area | Verify | Evidence |
|---|---|---|
| AuthN | token validated per request: signature, `exp`, `aud`/`iss`; revocation path exists | the verification code, cited |
| AuthZ | the matrix's condition is in the query, not after it | the repository method, cited |
| Input | validated at the boundary with a whitelist; lengths, ranges, array sizes bounded | the DTO/schema |
| Injection | parameterised queries; sort/filter columns whitelisted; no string-built SQL, no dynamic `eval`, no shell interpolation | each query builder in the sample |
| Output | DTOs exclude sensitive fields; errors do not distinguish existence; no stack traces to clients | the response mapping |
| Secrets | read only from config; none in code, defaults, tests, logs or committed files | a repo-wide search, and the config module |
| Logging | actor and requestId present on money and state changes; PII, tokens and payment data redacted | the logger wrapper and its redaction list |
| Crypto | standard library, current algorithms, no home-made anything; password hashing is a slow KDF with a salt | the hashing and token code |
| Sessions | expiry, refresh, invalidation on logout and on password change | the session code |
| Rate limits | present where the threat model says; per-actor, not only per-IP | the config, cited |
| Concurrency | money and state transitions are atomic (`data-concurrency`) — a race is a security bug when it moves money | the transaction and the constraint |
| Frontend | authorisation never decided in the client alone; tokens not in `localStorage` if the model says otherwise; no dangerous HTML injection | the guard and the render path |

## 3. Reporting

Severity from `SKILL.md`. Every finding carries the attack scenario, not just the pattern:

```markdown
### F-3 · High · `order.repository.ts:88` · Missing ownership in query (THR-07, EP-14)
- **Problem:** `findById(id)` loads by primary key; ownership is checked afterwards in the service,
  and the object is logged before that check.
- **Attack:** a customer requests another customer's order id → the check rejects the response, but
  the full order (including the buyer's address) is already in the application log, which support
  staff and the log pipeline can read.
- **Evidence:** repository line 88; logger call in `order.service.ts:41` [verified]
- **Control:** `findByIdAndOwner(id, actorId)` — ownership in the query (CTL-07, level 2)
- **Test to keep it fixed:** TC — customer A requests B's order → 404 and nothing in the log
```

Findings that need a fix become plan tasks (`SEC-Bnn` for the analysis, `BE-`/`FE-Bnn` for the change).
This skill writes none of them itself.
