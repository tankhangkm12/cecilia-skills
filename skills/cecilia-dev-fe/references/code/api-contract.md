# Consuming the API contract — mock, envelope, error codes, auth, retries

`<unit>-api.yaml` is the contract and it is **read-only here**. The frontend builds against it, never
edits it, and never calls anything it does not contain. Anything missing is a **contract gap** (§8),
not something to work around locally. `<unit>-api.md` and the repo win over the defaults below.

## 1. The mock is generated, never written

```
<unit>-api.yaml ──generate──► mock server / handlers ──► the app in dev
```

- Generated from the contract with a tool (Prism, MSW + an OpenAPI generator, orval, whatever the repo
  already has). **A hand-written mock is a second contract**, and it drifts silently until integration.
- Regenerate whenever the contract version changes; record in the report **which version this batch
  was built against** (`common/parallel.md` — the plan tracks it).
- The mock must serve every documented response, including **each error code**, not just 200. A mock
  that only returns success cannot exercise the states the design requires.
- At the planned integration point, re-verify the same screen list against the real API. Any
  difference between mock and real is a **finding**, never a quiet local fix.

## 2. The envelope, as the client sees it

```json
{ "success": true, "data": {...}, "message": "OK", "errorCode": null,
  "requestId": "req_01H8XKPM3QF9", "timestamp": "2026-08-30T09:14:22.117Z" }
```

- Unwrap once, in **one** client layer — never `response.data.data` scattered through components.
- `success` ⇔ 2xx, `data` is null on error, `errorCode` is the thing you branch on. **Never branch on
  `message`** — it is human text, it is translated, and it changes without notice.
- Paged: `data.items` + `data.pagination` (offset `page/pageSize/totalItems/totalPages`, or cursor
  `nextCursor/hasMore/limit`). Use whichever the contract declares; do not invent client-side paging
  over a cursor API.
- Exempt endpoints (files, streams, SSE, webhooks) have no envelope — the contract says which.

## 3. Error codes drive the UI, one code at a time

For every endpoint a screen calls, list **every** `errorCode` it may return and give each one a state
and a message. This table belongs in the implementation brief (F3) and in the PR:

| errorCode | HTTP | What the user sees | Where |
|---|---|---|---|
| `VALIDATION_FAILED` | 400 | field-level errors from `data.fields[]`, focus the first | the form |
| `UNAUTHENTICATED` | 401 | refresh once, then the login route (§5) | global |
| `PERMISSION_DENIED` | 403 | the permission state the design names — not a generic toast | the screen |
| `*_NOT_FOUND` | 404 | the empty/not-found state, not an error banner | the screen |
| `*_ALREADY_*` (conflict) | 409 | recoverable message + what to do next | inline |
| `RATE_LIMIT_EXCEEDED` | 429 | retry-after wording, submit disabled until then | inline |
| `INTERNAL_ERROR` / 5xx | 5xx | generic failure + `requestId` (§4), retry affordance | inline or global |

Rules: an error code with no designed message is a **question for `cecilia-design`**, not an invented
string · `VALIDATION_FAILED` maps `data.fields[].field` onto form fields by name — an unmapped field
still has to be shown, never swallowed · never show a raw `errorCode` to a user, and never show a stack.

## 4. requestId — read it, show it, report it

The server generates it; the client only **reads** it. Keep the `requestId` from the failing response
and put it in the error UI for 5xx (small, copyable) and in every bug report. It is what lets
`cecilia-dev-be` find the exact server log line — a bug report without it costs a round trip.

## 5. Auth and token refresh

- Read the scheme from the contract (bearer, cookie). Storage rules are in `security-logging.md` §B.
- On `401`: refresh **once**, then retry the original request once. Still 401 → clear session and go to
  the login route. Never loop.
- **Concurrent 401s share one refresh.** Queue the waiting requests behind a single in-flight refresh
  promise; firing N refreshes for N parallel calls invalidates tokens and logs the user out at random.
- `403` is not `401`: never refresh, never redirect to login — it is a permission state the design owns.

## 6. Retries, idempotency and double submit

| Case | Rule |
|---|---|
| `GET` | auto-retry is acceptable — bounded (≤ 2), exponential backoff, only on network error / 502 / 503 / 504 |
| `POST` / `PATCH` / `DELETE` | **never auto-retry** unless the contract defines an `Idempotency-Key` for it |
| contract defines `Idempotency-Key` | generate one per user intent (not per attempt), reuse it across retries of that same intent |
| double click / double submit | disable the control while in flight **and** guard in the handler; a disabled button alone is not a guard |
| `429` | respect `Retry-After`; never hammer |

Optimistic updates only where the design says so, and every one needs its **rollback path** written —
what the UI shows if the call fails after the optimistic change.

## 7. After a mutation, stale data is a bug

Name, in the brief, what each mutation invalidates or refetches — the list it came from, the counters,
the detail view, anything derived. "It refreshes on next navigation" is a decision, not a default; if
the design does not settle it, it is a question (F2).

## 8. Contract gaps — the only correct response to something missing

A field, endpoint, error code or shape the screen needs and the contract does not have:

1. Build what the contract **does** promise, leaving the gap visible in the UI state the design names.
2. Record it in the report under "For other roles" → `cecilia-design`, naming the `SCR`/`EP` ids.
3. Never add the field to a local type "for now", never call an endpoint absent from the `.yaml`, never
   patch the generated client by hand.

A local workaround is invisible at integration and expensive exactly then — that is the cost
`common/parallel.md` exists to avoid.
