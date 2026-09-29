# Core coding principles (all languages)

## 1. Language in code
Identifiers, files, folders, tables, columns, endpoints, events: **English**. Log messages: English.
Comments, docstrings, user-facing messages: chat language (repo convention wins). User-facing
messages live in a catalog/enum, not hard-coded in logic.

## 2. Comments — four kinds, each in its place
| Kind | Where | Content |
|---|---|---|
| Docstring | every public/exported function, class, method | what it does, params, return, errors thrown (language-standard format) |
| Doc reference | top of class/function implementing a requirement; next to a business rule | `Per LLD order §4.1 (FR-05, BR-02)` |
| Step comments | inside multi-step flows (use cases, handlers, jobs, algorithms) | numbered steps matching the doc/PR flow |
| Why | non-obvious choices: workaround, lock, mandatory order, odd value, partner quirk | the reason, not a restatement |

Never: restating code (`// increment i`), commented-out code, names/dates (git has them), `TODO`
without a task id. Test: deleting the comment loses no information → delete it.

```ts
/**
 * Cancels an order on behalf of its buyer.
 * Per LLD order §4.1 (FR-05, BR-02).
 * @throws OrderNotFoundException  order does not exist or is not owned by caller
 * @throws BusinessRuleException    status does not allow cancel (BR-02)
 */
async cancel(orderId: string, actor: Actor): Promise<Order> {
  // Step 1: load with ownership in the query (IDOR protection, 404 instead of 403)
  // Step 2: guard status (BR-02)
  // Step 3: atomic transition PENDING→CANCELLED; 0 rows = concurrent change (D-07)
  // Step 4: enqueue OrderCancelled in outbox inside the same transaction
}
```

## 3. Functions
- One job; soft ceiling ~30 lines → extract well-named private functions.
- Guard clauses / early return; happy path at the lowest indentation; nesting ≤ 2 levels.
- > 3 parameters → a named object/DTO. No boolean flag parameters that switch behaviour (split the function).
- Never mutate input parameters.
- Shorter wins only when equally clear: no nested ternaries, no multi-step one-liners, no abbreviations,
  never drop a validation for brevity. Unsure → the more readable form.

## 4. Strict types
| Lang | Rule |
|---|---|
| TypeScript | `strict`; **no `any`** (use `unknown` + narrowing); no `as` casts to silence the compiler |
| Python | full type hints for params and returns; Pydantic/dataclass for structured data; no `dict[str, Any]` payloads; mypy/pyright strict |
| Java | concrete generics, no raw types; **no `Map<String,Object>` DTOs**; `Optional<T>` for absent return values, never return null from public methods |
External data (HTTP, messages, config, partner responses) passes a validation layer before becoming an internal type.

## 5. SOLID as a tool
**S** and **O** first (maintainability). Abstractions (interface, base class, strategy, factory) only
when: wrapping an external dependency · ≥ 2 real implementations exist · Cecilia asked. Otherwise concrete
classes. Splitting a long function into private helpers is SRP and needs no interface. L: implementations
do not throw new kinds or tighten preconditions. I: small caller-shaped interfaces. D: inner layers own
interfaces, outer layers implement them.

## 6. Errors
- Domain exceptions only; never throw bare `Error`/`Exception`/`RuntimeException`.
- Each carries `errorCode` (UPPER_SNAKE, from one catalog), HTTP status, user message, log context.
- One global handler maps exceptions → envelope. Controllers never try/catch to format errors.
- try/catch only where you really handle (fallback, retry, add context and rethrow). No empty catch,
  no `catch → return null` without logging.
- SDK errors are translated in the adapter; `AxiosError`/`SQLException`/`KafkaJSError` never reach services.

Tree: `AppException` → `ValidationException 400` · `UnauthorizedException 401` · `ForbiddenException 403` ·
`NotFoundException 404` · `ConflictException 409` · `BusinessRuleException 422` · `ExternalServiceException 502/503`.

## 7. Immutability & side effects
`const`/`final`/frozen by default · pure calculation functions; side effects (DB, events, HTTP) in the
orchestrating layer · no global mutable state · clock, random, id generators are injected dependencies.

## 8. Async
One style per codebase (TS async/await; Python async end-to-end, no blocking calls in the loop; Java
blocking or reactive, not both) · run independent work in parallel (`Promise.all`, `asyncio.gather`/
`TaskGroup`, `CompletableFuture.allOf`) · every outbound call has a timeout · retry only idempotent
operations, with backoff and a max.

## 9. Naming
**Files carry a role suffix**; separator follows the language:
| Lang | Style | Examples |
|---|---|---|
| TS | kebab-case | `user-profile.service.ts`, `create-user.dto.ts`, `user.repository.port.ts` |
| Python | snake_case | `user_profile_service.py`, `user_repository_port.py` |
| Java | PascalCase | `UserProfileService.java`, `UserJpaAdapter.java` |

Folders: TS kebab, Python snake, Java lowercase packages; plural for collections (`modules/`, `dto/`).
Identifiers: classes PascalCase; functions/vars camelCase (TS/Java) or snake_case (Python); constants
UPPER_SNAKE; booleans `is/has/can/should`; no `Async` suffix; no `I` prefix on interfaces; Java port
`UserRepository` → adapter `UserRepositoryJpaAdapter`.
Data/contract: tables plural snake_case · FK `<singular>_id` · money columns state unit (`amount_minor`,
`total_vnd`) · time columns `_at` · endpoints plural kebab (`POST /orders/:id/cancel`) · events
`<domain>.<entity>.<action>` · errorCode `USER_NOT_FOUND` · env vars prefixed `DB_URL`, `JWT_SECRET`.
Repository methods read as intent: `findOverdueInvoices()`, `findByIdAndOwner(id, userId)` — not
`findByDueDateLessThanAndStatusNot()`.
Banned: `data2`, `temp`, `tmp`, `res2`, `obj`, `doStuff`, `handle`, `process`, bare `manager`/`helper`,
catch-all `utils`/`common` files (split by topic: `date.util.ts`, `money.util.ts`). If you must open the
file to know what it does, rename it.

## 10. Size and shape — thresholds that are signals, not laws

Every number here is a **stop-and-think line**, not a lint rule: crossing it means asking one question,
and the answer may legitimately be "this file is fine". What is never fine is crossing it without
noticing. Code does not become unmaintainable by one bad function; it becomes unmaintainable by
fifty reasonable additions that nobody was asked to justify.

| Unit | Signal | The question it forces | What it usually means |
|---|---|---|---|
| Function | ~30 lines · nesting > 2 · > 3 params | already covered in §3 | — |
| **File** | ~300–400 lines | "how many reasons does this file have to change?" | more than one → split by reason, never by line count |
| **Class / service** | > 7 public methods | "is there a second use case hiding in here?" | a cohesive group of methods wants its own service |
| **Constructor** | > 5 injected dependencies | "what is this orchestrating that it should not?" | the classic sign a service took over another's job |
| **Module** | owns > 5 tables · two endpoint groups sharing no data | "is this one capability or two?" | boundary drawn around a noun, not around a behaviour |
| **Call depth** | A → B → C → D inside one module | "which of these layers adds a decision?" | pass-through layers that only forward arguments |
| **Branching** | a business rule spread across nested conditions in a service | "should this rule live in the domain?" | rules leaking out of the domain into orchestration |

**Split by reason, never by size.** Cutting a 600-line file into `order.service.part1` and
`.part2` makes the metric green and the code worse. The correct cut follows a reason to change:
a different actor, a different lifecycle, a different rule owner. If you cannot name the reason, do
not split — say so in the PR and leave it, with the reason you could not.

**The test that replaces all the numbers.** To change one business rule, how many files must you
open — and is there a file you open whose relevance you cannot explain in one sentence? Two or three
files, each obviously relevant, is healthy. Seven files, two of which you open "because something
breaks otherwise", is the real defect, whatever the line counts say.

**Adding to something already over the line** is where debt compounds. Touching a file or class
already past a signal → say so in the implementation brief (D3) with one sentence: keep it and why,
or split it first as its own task. Never silently make a known-heavy file heavier; that is the move
that turns a 400-line file into a 2000-line one, one innocent change at a time.
