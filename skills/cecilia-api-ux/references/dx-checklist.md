# Developer experience checklist

Each line is judged from the contract (and the code for behaviour the contract hides). A failed line is a
finding with the persona it hurts.

| # | Check | Why the consumer cares |
|---|---|---|
| 1 | One error format everywhere (e.g. RFC 9457 problem+json): stable machine `code`, human `message`, field errors | one parser; actionable UI messages |
| 2 | Each error code tells the client what to do (fix input, re-auth, retry after N s, contact support) | no dead ends |
| 3 | 4xx vs 5xx used correctly; 409 conflict, 422 validation, 429 rate limit with `Retry-After` | correct retry logic |
| 4 | State-changing calls that create/charge accept an Idempotency-Key and return the first result on replay | safe retries after timeouts |
| 5 | One pagination convention (cursor for feeds/large, offset for small admin lists), stable sort, `next` link/cursor | infinite scroll without duplicates/gaps |
| 6 | Filtering/sorting parameters named and typed consistently | no per-endpoint learning |
| 7 | One naming style for paths and fields; plural resources; no verbs in paths except commands | predictability |
| 8 | Money as string decimal or integer minor units + currency; never float | no rounding bugs |
| 9 | Timestamps RFC 3339 with offset; dates as dates; one timezone rule | no off-by-one-day |
| 10 | IDs opaque strings; never sequential IDs leaking business volume where it matters | security, flexibility |
| 11 | Enums documented; clients told to tolerate unknown values | forward compatibility |
| 12 | Nullable vs absent defined; empty list vs null consistent | fewer null checks |
| 13 | Auth: minimal steps, token refresh documented, 401 vs 403 distinct | fewer login loops |
| 14 | Long operations: 202 + status resource (or webhook/SSE), not a 60 s request | no timeouts |
| 15 | Rate limits documented with headers (`RateLimit-*`/`X-RateLimit-*`) | clients can pace |
| 16 | Versioning rule stated; deprecations with `Deprecation`/`Sunset` headers and dates | planned upgrades |
| 17 | Examples for every request/response; a sandbox or seed data | faster integration |
| 18 | Bulk operations for things done in bulk (import, mark all read) | no N calls from the client |
