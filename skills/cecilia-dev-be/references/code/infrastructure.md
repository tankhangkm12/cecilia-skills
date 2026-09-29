# Wrap every external dependency (ports & adapters)

Cecilia's rule: wrap it behind a clear interface so the code does not depend on it and it can be
replaced. This is the one abstraction allowed without asking.

## 1. What must be wrapped
Message brokers (Kafka, RabbitMQ, NATS) · RPC clients (gRPC, TCP) · outbound HTTP (axios, httpx,
requests, RestTemplate, WebClient) · cache (Redis) · storage (S3, MinIO, GCS) · mail/SMS/push · payment
gateways · ORM/DB drivers · logger · clock, random, uuid · config/env/secret stores · search/vector engines.
Outside your process or non-deterministic → wrap.

## 2. Shape
```
PORT     interface in business language, in the INNER layer (domain/application), owned by its user
ADAPTER  implementation that knows the SDK, in infrastructure
WIRING   DI binds port ↔ adapter in module/config
```

## 3. Ports speak business, not SDK
```ts
// ❌ fake wrapping — Kafka shape leaks
interface KafkaService { send(topic: string, key: string, value: Buffer): Promise<RecordMetadata> }
// ✅
interface DomainEventPublisher { publish(event: DomainEvent): Promise<void>; publishAll(events: DomainEvent[]): Promise<void> }
// ✅
interface PaymentGateway { charge(cmd: ChargeCommand): Promise<PaymentResult>; refund(cmd: RefundCommand): Promise<RefundResult> }
```
Test: switching Kafka → RabbitMQ changes the port? Then it is not wrapped.

## 4. Every adapter does five things
1. Calls the SDK — the only place that knows it exists.
2. Maps our model ↔ SDK model; SDK types never leave the adapter.
3. Translates SDK errors into our exceptions.
4. Timeout on every call; retry only if idempotent, with backoff and max attempts.
5. Logs at the boundary with requestId and measures call duration.

```ts
export class StripePaymentGateway implements PaymentGateway {
  constructor(private readonly stripe: Stripe, private readonly logger: AppLogger) {}
  async charge(cmd: ChargeCommand): Promise<PaymentResult> {
    try {
      const res = await this.stripe.paymentIntents.create(
        { amount: cmd.amountMinor, currency: cmd.currency, customer: cmd.customerRef },
        { timeout: 10_000, idempotencyKey: cmd.idempotencyKey },
      );
      return this.toPaymentResult(res);
    } catch (err) {
      this.logger.warn('stripe charge failed', { ref: cmd.idempotencyKey, err });
      throw ExternalServiceException.from('PAYMENT_GATEWAY_UNAVAILABLE', err);
    }
  }
}
```

## 5. Config — one door
Env/secret reads happen only in the config module · validated at startup, fail fast (zod/Joi,
Pydantic `BaseSettings`, `@ConfigurationProperties` + `@Validated`) · injected as typed objects ·
secrets never have defaults · `.env.example` lists keys with fake values.

## 6. Logger — wrapped too
Business code calls `AppLogger` (`debug/info/warn/error(msg, ctx)`), never winston/pino/logback/structlog
directly: one place to add requestId, redaction, backend changes.

## 7. Checklist
- [ ] No business file imports an external SDK/ORM
- [ ] Ports named in business terms; switching tech does not change them
- [ ] Ports in inner layer, adapters in infrastructure
- [ ] Adapters translate errors, set timeouts, never leak SDK types
- [ ] Env access only in config module
- [ ] Clock/random/uuid injected
- [ ] Services can be unit-tested by mocking ports (no real infrastructure)
