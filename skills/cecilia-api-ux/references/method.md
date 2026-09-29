# API experience review — method

## 1. What is judged

The **consumer's cost** of using the API for a real task: how many calls and waits, how much they must know,
how often they are refused, what happens when something fails, and whether tomorrow's release breaks them.
Correctness against the contract is `cecilia-test`'s; security is `cecilia-review` security mode's.

## 2. Personas (pick those that exist)

| Persona | Cares about | Typical pain |
|---|---|---|
| Frontend / mobile developer | calls per screen, one error format, predictable pagination, types that map to UI | waterfalls, N+1, over-fetch on mobile data, ad-hoc error bodies |
| End user (through the UI) | time to content, never losing input, never paying twice, clear next step on failure | spinners in series, "please retry" loops, silent double orders |
| Third-party / integration client | stability, idempotent retries, webhooks, rate limits they can plan for | breaking changes, 429 without Retry-After, no replay protection |
| Internal service (microservices) | timeouts, partial failure, eventual consistency windows | cascading waits, read-your-writes gaps |

## 3. Oracles

Requirements (journeys, NFRs with numbers) · API contract · frontend screens/states · data model · expected load
(users, peak factor) · the project's decision log. A number the oracle does not give is asked, never invented.

## 4. The pass

1. Personas × top tasks (3–8), each with expected load (per minute at peak).
2. Static scan (`apikit.py summary`) — consistency findings are cheap and certain.
3. Journeys (`consumer-journeys.md`) — calls, stages, critical path, N+1, payload.
4. DX (`dx-checklist.md`).
5. Contention (`contention.md`) for every shared mutable thing the tasks touch.
6. Latency and failure (`latency-failure.md`).
7. Evolution (`evolution.md`) when the contract changed.

## 5. Scorecard per task (report §2)

| Task | Persona | Requests | Stages | p95 path | Rejection @ peak | Failure handling | Verdict |
|---|---|---|---|---|---|---|---|
| Checkout | end user | 4 | 3 | 450 ms | 22 % @ 5/s/SKU | lost cart on 409 | BLOCKER |

Targets unless the requirements say otherwise (state them in the report): a screen's first content ≤ 2
sequential stages and ≤ 1 s p95 on the server side; rejection visible to users ≤ 1 % at expected peak; every
state-changing call safe to retry; one error format; no breaking change without a version.

## 6. Findings (`AUX-nn`)

```
AUX-03 · BLOCKER · checkout · end user
What they experience: 1 in 5 checkouts in a flash sale ends in "please try again"; the cart is kept but the
  voucher is dropped.
Evidence: POST /orders uses version-checked stock update (OrderService.java:88); window ≈ 40 ms;
  peak 5 writes/s per SKU → capacity.py contention: 18 % per attempt, 3.3 % after 1 retry [projected].
Owner: cecilia-design (contract: reservation flow) → Cecilia decides; cecilia-dev-be (conditional update).
Acceptance: rejection ≤ 1 % at 5 writes/s per SKU, measured with the local replay in contention.md §5.
Options: (a) conditional decrement (b) reservation + TTL (c) queue per SKU (d) keep — see report §4.
```

## 7. Routing and the loop

| Finding touches | Owner | Needs Cecilia? |
|---|---|---|
| contract shape, new endpoint, status codes, versioning | cecilia-design | **yes** — public contract (CONTROLLED trigger) |
| server-side N+1, lock scope, retry inside the service, missing index | cecilia-dev-be / cecilia-db | no, inside the task envelope |
| how the UI waits, retries, keeps input | cecilia-dev-fe | no, inside the task envelope |
| NFR target itself (what "fast" means) | Cecilia | yes |

Round 1 → owner fixes → re-measure. Round 2 → re-measure. Still failing → options to Cecilia, stop.
