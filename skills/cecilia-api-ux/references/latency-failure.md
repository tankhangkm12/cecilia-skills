# Latency and failure — what the consumer waits for and what happens when it breaks

## 1. Per task latency budget

critical path = Σ over sequential stages of the slowest call in that stage (server p95 + network).
Server p95 per call comes from measurements (APM/logs) or `capacity.py throughput` inputs; network RTT by
client type (LAN 1–5 ms, 4G 50–150 ms, cross-region 100–250 ms). Flag tasks whose critical path exceeds the
NFR, and name the stage that dominates.

## 2. Timeouts and retries across hops

- Every hop has a timeout shorter than its caller's (gateway > service > DB); retries only at one layer.
- Retry budget: attempts × timeout < caller's timeout; jittered backoff.
- A user-facing request never waits on a non-essential downstream (recommendations, analytics): async or
  degrade.

## 3. Partial failure — ask per task

| Question | Good answer |
|---|---|
| If service X is down, does the screen still show the rest? | yes, with a clear placeholder |
| If the write succeeded but the response was lost, can the client find out? | idempotent retry or status lookup |
| Is a failed step compensated (payment taken, order failed)? | saga/compensation documented |
| Does the client learn about eventual results? | status endpoint, webhook, or push |

## 4. Consistency the user can see

- **Read-your-writes:** after a successful write, does the next read (list, detail) show it? Replicas, caches
  and read models can lag — measure or state the window, and say what the UI shows meanwhile.
- **Monotonic reads:** can a refresh show older data than the last one (different replicas)?
- **Cross-service:** order placed in one service, stock/payment/notification in others — what can the user
  see mid-way, for how long?

## 5. Caching

Cacheable GETs have `Cache-Control`/`ETag`; conditional requests (304) documented; personalised data never
cached publicly; invalidation after writes stated.
