# Core coding principles (frontend)

## 1. Language in code
Identifiers, files, folders, routes, component names, event names: **English**. Comments and
docstrings: chat language (repo convention wins). **User-facing strings never live in a component** —
they come from the i18n catalog or a strings module, so they can be translated and reviewed without
touching logic.

## 2. Comments — four kinds, each in its place
| Kind | Where | Content |
|---|---|---|
| Docstring | every exported component, hook, or utility | what it renders or returns, props/args, what it throws or suspends on |
| Doc reference | top of a component implementing a screen; next to a business rule | `Per shop-frontend.md §3.2 (SCR-04, CMP-11)` |
| Step comments | inside multi-step flows (submit handlers, wizards, optimistic updates) | numbered steps matching the doc/PR flow |
| Why | non-obvious choices: a workaround, a forced re-render, an odd dependency array, a browser quirk | the reason, not a restatement |

Never: restating code (`// set loading true`), commented-out code, names/dates (git has them), `TODO`
without a task id. Test: deleting the comment loses no information → delete it.

```tsx
/**
 * Cancel-order action for the order detail screen.
 * Per shop-frontend.md §4.1 (SCR-12, CMP-30); endpoint EP-08.
 * Renders: confirming · submitting · error-per-code · success.
 */
function useCancelOrder(orderId: string) {
  // Step 1: guard double submit — in-handler, not only the disabled button
  // Step 2: POST EP-08 with the intent's Idempotency-Key (api-contract.md §6)
  // Step 3: on success invalidate the orders list + this detail (api-contract.md §7)
  // Step 4: map each errorCode to its designed state; 403 → permission state, never login redirect
}
```

## 3. Functions and components
- One job; soft ceiling ~30 lines for a function → extract well-named helpers or child components.
- Guard clauses / early return; happy path at the lowest indentation; nesting ≤ 2 levels.
- > 3 parameters → a named object. No boolean flag props that switch a component's behaviour — that is
  two components wearing one name (split them).
- Never mutate props, state or input parameters.
- Shorter wins only when equally clear: no nested ternaries in JSX beyond one level, no abbreviations,
  never drop a state branch for brevity. Unsure → the more readable form.

## 4. Strict types
- `strict` on; **no `any`** (use `unknown` + narrowing); no `as` to silence the compiler; no
  `@ts-ignore` without a why-comment and a task id.
- **API types are generated from `<unit>-api.yaml` or derived from it** — never hand-maintained
  duplicates that drift from the contract.
- Props are typed exactly: no `object`, no index signatures standing in for a real shape, no optional
  props that are actually required.
- Anything crossing the boundary (API response, URL params, `localStorage`, a third-party callback) is
  `unknown` until it is validated or narrowed. A response is not typed just because you wrote a type.

## 5. Composition over abstraction
Prefer composition (children, slots, render props) to configuration flags. Extract a shared component
or hook only when: ≥ 2 real usages exist · it wraps an external dependency · the design system defines
it · Cecilia asked. A one-usage "reusable" component is a guess about the future that makes today's
code harder to read. Splitting a long component into local sub-components needs no abstraction at all.

## 6. Errors
- Never swallow. No empty `catch`, no `catch → return null` without surfacing something.
- **`errorCode` is the branch, `message` is for humans** (`api-contract.md` §3). Every code an endpoint
  can return has a designed state; an unmapped code still renders something honest, never a blank.
- The API client translates transport errors (`AxiosError`, `fetch` rejection, timeout, abort) into the
  app's error shape **once** — raw SDK errors never reach a component.
- An aborted request is not an error: an unmount or a superseded query is discarded silently.
- Every route has an **error boundary** whose fallback is a designed state; a boundary that renders a
  bare string is an unfinished state, not a safety net.
- Throwing to a boundary is for render-time failures. A failed user action is **state**, shown in
  place — not an exception that blanks the screen.

## 7. Immutability & side effects
`const` by default; never mutate state or props in place (new object/array, or the library's updater) ·
keep render pure — no fetching, no writing storage, no DOM measurement during render · side effects live
in event handlers or effects, not in render paths · no module-level mutable state shared across
components · clock, random and id generators are injected or wrapped, so a screen is reproducible.

## 8. Async
- One style: `async/await` with an explicit loading state; no floating promises.
- Every request can be **cancelled**, and every effect that starts one cleans it up on unmount or when
  its inputs change — an unguarded `setState` after unmount is a bug and often a leak.
- **Out-of-order responses**: a slower earlier request must never overwrite a newer result. Key the
  result by its input, or abort the previous one.
- Independent work runs in parallel (`Promise.all`), dependent work is sequential and says why.
- Retries only where `api-contract.md` §6 allows them, with backoff and a max.
- Effects have correct, complete dependencies; an effect that exists to synchronise state that could be
  derived during render should not exist.

## 9. Naming
| Thing | Style | Examples |
|---|---|---|
| Component files | PascalCase or kebab per repo, consistently | `OrderDetail.tsx` / `order-detail.tsx` |
| Components | PascalCase | `OrderDetail`, `CancelOrderDialog` |
| Hooks | `use` + intent | `useCancelOrder`, `useOrderList` |
| Handlers | `handle<Thing><Event>` / prop `on<Thing><Event>` | `handleSubmitClick`, `onOrderCancel` |
| Booleans | `is/has/can/should` | `isSubmitting`, `canCancel` |
| Constants | UPPER_SNAKE | `MAX_PAGE_SIZE` |
| Routes | plural kebab | `/orders/:id/cancel` |
| Test ids | stable, intent-named | `order-cancel-submit` |
| Public env vars | the framework's public prefix, and **public by definition** | `NEXT_PUBLIC_API_BASE_URL` |

Folders group by **feature**, not by file type: `features/orders/` beats a global `components/` holding
everything. Shared UI lives where the design system says.

Banned: `data2`, `temp`, `tmp`, `obj`, `doStuff`, `handle` alone, `Wrapper`/`Container` with no meaning,
bare `manager`/`helper`, catch-all `utils`/`common` files (split by topic: `date.util.ts`,
`money.util.ts`). If you must open the file to know what it does, rename it.

## 10. Size and shape — thresholds that are signals, not laws

Every number here is a **stop-and-think line**, not a lint rule: crossing it means asking one question,
and the answer may legitimately be "this file is fine". What is never fine is crossing it without
noticing. A codebase does not become unmaintainable by one bad component; it becomes unmaintainable by
fifty reasonable additions that nobody was asked to justify.

| Unit | Signal | The question it forces | What it usually means |
|---|---|---|---|
| Function / handler | ~30 lines · nesting > 2 · > 3 params | already covered in §3 | — |
| **Component file** | ~300–400 lines | "how many reasons does this file have to change?" | more than one → split by reason, never by line count |
| **Component props** | > 7 props, or ≥ 2 boolean flags | "is this one component or three?" | flags usually mark hidden variants |
| **Hook** | > 3 pieces of state · both fetching and orchestrating UI | "is there a data hook hiding inside this UI hook?" | one hook doing the data layer's job and the screen's |
| **Effects in one component** | > 2 | "which of these is derived state pretending to be an effect?" | synchronising what render could compute |
| **Prop drilling depth** | passed through > 2 components untouched | "who actually owns this state?" | state placed above the level the design named |
| **JSX nesting** | deeply nested conditional blocks in one return | "is a branch here really a separate component?" | variants that deserve names |

**Split by reason, never by size.** Cutting a 600-line screen into `OrderDetailPart1` and `Part2` makes
the metric green and the code worse. The correct cut follows a reason to change: a different actor, a
different state owner, a different part of the design. If you cannot name the reason, do not split —
say so in the PR and leave it, with the reason you could not.

**The test that replaces all the numbers.** To change one screen behaviour, how many files must you
open — and is there a file you open whose relevance you cannot explain in one sentence? Two or three
files, each obviously relevant, is healthy. Seven files, two of which you open "because something
breaks otherwise", is the real defect, whatever the line counts say.

**Adding to something already over the line** is where debt compounds. Touching a component already
past a signal → say so in the implementation brief (F3) with one sentence: keep it and why, or split it
first as its own task. Never silently make a known-heavy component heavier; that is the move that turns
a 400-line screen into a 2000-line one, one innocent change at a time.
