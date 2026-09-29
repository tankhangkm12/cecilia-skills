# Observability

The test: at 3am, with only the dashboards and the logs, can someone tell **whether** it is broken,
**what** is broken, and **whether the last change caused it**? Build toward those three answers and
nothing else.

## 1. Health endpoints — two, not one

| Endpoint | Answers | Failing means |
|---|---|---|
| **liveness** | is the process wedged? | restart it |
| **readiness** | can it serve traffic right now? (deps connected, migrations done, warm) | take it out of the load balancer, do **not** restart |

One endpoint for both causes restart loops: a dependency blip restarts a healthy process, which then
fails readiness again on boot. Readiness checks dependencies; liveness never does — otherwise a slow
database restarts every instance at once.

The handlers are `cecilia-dev-be` / `cecilia-dev-fe`'s to write (path ownership in SKILL.md). This skill specifies what
they must answer and wires the probes, with timeouts and thresholds that tolerate a normal hiccup.

## 2. What to collect, in priority order

1. **The four that catch most outages**: request rate, error rate, latency (p50/p95/p99 — never the
   mean, which hides everything), and saturation (CPU, memory, connections, queue depth, disk).
2. **Business signals that fail loudly when the system is technically fine**: orders per minute,
   payments succeeded, jobs processed. These catch the outage where every health check is green and
   nothing is actually happening.
3. **Dependencies**: latency and error rate per external call, and whether the circuit is open.
4. **Deploy markers** — an annotation on every dashboard at every deploy. Half of all "what
   happened?" questions are answered by the marker sitting exactly where the line bent.

## 3. Logs

Structured (JSON), one event per line, with a correlation id threaded through every service so one
request can be followed end to end. Level means something: `error` is for things a human should look
at, and a service logging errors that nobody acts on has taught everyone to ignore its errors.

Never in a log: secrets, tokens, passwords, full card numbers, personal data beyond what is needed,
whole request bodies "just in case". Redact at the logger (`cecilia-dev-be` / `cecilia-dev-fe` wraps it), not at the
destination — by then it has been written to disk.

Retention and cost are a decision, not a default. Ask: how long, at what volume, what does it cost,
and what is the sampling rate for high-volume debug output.

## 4. Alerts

An alert is a promise that a human will act. Anything that does not meet that bar is a dashboard, not
an alert.

- **Alert on symptoms, not causes.** "Checkout error rate above 2% for 5 minutes" is actionable;
  "CPU at 85%" is a fact that may mean nothing.
- Every alert carries: what is wrong, which environment (`ENV-nn`), the impact in user terms, a link
  to the dashboard, and the first thing to check. An alert without a next step wakes someone up to
  read a number.
- **Tune the threshold and the duration together.** Most false pages are a real threshold with no
  patience — a five-minute window removes the blips without hiding an outage.
- Cecilia decides what pages a human versus what waits for morning. Ask; never assume anything is
  worth waking someone for.
- Review after every incident (`incidents.md` §5): did an alert fire, was it early enough, was it
  actionable? Alerts nobody acted on get deleted — silence that is trusted is worth more than
  coverage that is ignored.

## 5. The minimum, when there is no budget for more

Even the smallest setup needs: liveness + readiness wired to the orchestrator · logs shipped
somewhere searchable and outliving the container · error rate and latency visible per service ·
deploy markers · one alert on the user-facing symptom that matters most · uptime checked from
outside the system, because a monitor inside the failing thing reports nothing while it is down.

## 6. Checklist

- [ ] Liveness and readiness separate, with sensible timeouts; readiness checks dependencies, liveness does not
- [ ] Rate, errors, latency (p95/p99) and saturation collected per service
- [ ] At least one business-level signal
- [ ] Correlation id through every service; logs structured, redacted at the logger
- [ ] Deploy markers on the dashboards
- [ ] Every alert actionable, symptom-based, with environment and next step
- [ ] Retention, sampling and cost decided by Cecilia, written in the infrastructure doc
- [ ] Proof 3 of `deploy-and-rollback.md` §4 checked after the apply: it can actually be seen
