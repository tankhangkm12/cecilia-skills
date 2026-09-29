# Frontend option tables — present, never decide

Research current versions before quoting them (`common/capabilities.md`). Repo convention wins over every
table here; say so once and move on.

## 1. Rendering strategy — decided by requirements, not taste

| Option | Fits when | Starts to hurt when |
|---|---|---|
| SPA (client-rendered) | authenticated app behind a login, SEO irrelevant | first paint matters, or the device is weak |
| SSR | SEO, share previews, fast first paint on slow devices | needs a server, and every data call is now on the critical path |
| SSG / ISR | content that changes rarely | personalised or frequently changing data |
| Hybrid per route | mixed needs — the common real answer | two mental models in one codebase; the team must know which route is which |

Ask which requirement forces it: SEO (`NFR`), first-paint target, or offline. No requirement forces
it → the cheapest to operate wins, and that is usually the repo's existing choice.

## 2. Server state

| Option | Fits | Cost |
|---|---|---|
| Query/cache library (TanStack Query, RTK Query, SWR) | anything with lists, refetching, mutations | a cache to understand: keys, invalidation, staleness |
| Hand-rolled fetch + local state | one or two screens | you will rebuild caching badly, later, under pressure |
| Full client store for server data (Redux as cache) | rarely the right answer today | double bookkeeping between store and server |

The question that settles it: after a mutation, what must refresh, and how does the user know it did?

## 3. Client state

Keep it small and say where each thing lives (`SKILL.md` rule 6):

| Kind | Belongs in | Sign it is in the wrong place |
|---|---|---|
| Filters, tabs, pagination, opened item | **URL** | refresh or a shared link loses the view |
| Auth/session, theme, locale | one global store | it is threaded through ten component layers |
| Form values | form library, per form | a global store that only one screen reads |
| Server data | server cache | it goes stale and nobody knows who refreshes it |
| Derived (totals, filtered lists) | computed at render | it disagrees with its source after an edit |

## 4. Forms

Library vs hand-rolled: a library once there are more than ~3 fields, cross-field rules, or async
validation. Schema shared with the backend types where the stack allows it — and the client rules
**mirror** `BR-nn`, never invent rules the server does not enforce.

## 5. Component boundaries

Split by **who owns the data**, not by size:

- **Route/screen** — owns data fetching and layout for one `SCR`.
- **Feature component** — one behaviour, owns its local state, receives data as props.
- **Primitive** — no app knowledge, no data fetching; from the design system where one exists.

A component that fetches *and* renders *and* decides layout for other components is three components.
The signal is the same one the code rules use: more than one reason to change.

## 6. Error, empty and loading — design them once

Define these as shared patterns in `<app>-frontend.md`, so every screen references them instead of inventing:

| Pattern | Decide once |
|---|---|
| Full-page loading vs skeleton vs inline spinner | which, and at what delay threshold |
| Empty state | illustration/text/action — and the difference between "no data yet" and "no results for this filter" |
| Error by class | network · 4xx business (`errorCode` → message) · 401/403 · 5xx · timeout |
| Retry | which errors offer it, how many times, with what backoff |
| Stale data | shown with an indicator, or hidden — one rule for the app |
| Toast vs inline | which outcomes announce themselves, and which stay next to the field |

## 7. Accessibility and budgets

State the level (e.g. WCAG 2.2 AA) and what is actually checked: keyboard path through every flow ·
focus visible and managed on route change and dialog open · labels and error association on forms ·
contrast · motion preference. Budgets as numbers with the tool that measures them, so
`cecilia-dev-fe` can be held to them (`common/evidence.md`) rather than asked to "keep it fast".
