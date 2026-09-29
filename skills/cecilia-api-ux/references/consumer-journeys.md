# Consumer journeys — calls per task

## 1. Write the call script

For each task, what a correct client must call, in order, with what it waits for:

```
Order list (mobile, 20 rows):
  GET /orders?limit=20                       ─ stage 1
  GET /products/{id}  ×20   (thumbnails)     ─ stage 2 (needs order items)
  GET /shops/{id}     ×7    (shop names)     ─ stage 2 (parallel)
```
`apikit.py journey --screen "Order list" --calls "GET /orders > GET /products/{id} x20, GET /shops/{id} x7" --latency-ms 60,90,180`

Read the script from the contract and the frontend design; confirm against the frontend code if it exists
(`grep` the API client). A step the contract cannot serve → a gap, not a guess.

## 2. What to flag

| Pattern | Cost | Typical fix (options, not decisions) |
|---|---|---|
| **Sequential stages > 2** for first content | each stage adds a full round trip (mobile: 100–300 ms) | include/expand, composite endpoint, BFF |
| **N+1 on the client** (`xN`) | N requests, connection limits, battery | batch endpoint (`GET /products?ids=`), embed summary fields |
| **Over-fetch** | payload × rows on mobile | sparse fields (`fields=`), smaller list DTO |
| **Under-fetch** | extra call per screen | add the 2–3 fields every screen needs to the list DTO |
| **Chatty writes** | N calls to save one form | one command endpoint for the task |
| **Client-side joins across services** | the client re-implements the domain | read model / BFF owned by the backend |
| **Polling for a result** | wasted calls, delay | 202 + status URL with Retry-After, webhook, SSE |

## 3. Numbers to put in the scorecard

- requests (total), stages (sequential depth), critical path = Σ slowest call per stage;
- payload per request and per screen (`capacity.py bandwidth` for totals at peak);
- server work: `capacity.py throughput` with the extra requests the pattern creates at peak rps.

## 4. BFF / composite endpoint — when it is worth it

Worth it when ≥ 3 screens need the same join, or a mobile client pays > 2 stages. Not worth it when one
screen needs it and an `include` parameter solves it. Cost: one more thing to deploy and version; caching gets
harder. Always offer "keep" with its measured cost.
