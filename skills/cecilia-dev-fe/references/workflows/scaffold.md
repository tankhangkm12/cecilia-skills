# Scaffold — new app, route group or feature module

Build from `<app>-frontend.md` and the API contract. Everything the docs do not settle is asked in grouped gates
(`common/decisions.md` §2).

## 1. Decisions to confirm before creating anything

New feature module vs inside an existing one (same screens / same change cadence → existing) ·
folder and routing structure · for a new app the **stack as a set**, asked as ONE question with 2–3
complete bundles (framework + router + data-fetching/cache layer + state library + styling/design
system + package manager + runtime version + lint/format), each researched with a recommendation —
never six separate fragments and never six at once · rendering strategy per route group (client,
server, static, revalidated) if the design is silent · where the design system comes from (existing
package, or built here) · how the **mock is generated from the contract** and how the app switches
between mock / local backend / staging · which budgets apply (bundle per entry, interaction latency)
and where they are recorded.

A new dependency in any bundle is a hard stop (`common/core.md` §2) — it ships to every visitor.

## 2. Build order — vertical slice, not horizontal layers

1. **Skeleton that runs**: routing shell, design-system/theme provider, the API client with envelope
   unwrapping and `errorCode` handling in one place, auth/session wiring, global error boundary and
   the designed error/loading fallbacks, i18n if the design requires it, lint/format config agreed
   with Cecilia, and the generated mock wired up.
2. **One complete screen end to end** for the first planned `SCR` — route → data fetch against the
   mock → every documented state → verified manually.
3. Then the remaining `SCR` ids of the batch.

Minimum per feature module: route(s) · screen component(s) · the components the design names (`CMP`
ids) · its data hooks/queries · its types generated or derived from the contract · its strings.
Nothing speculative — no empty folders "for later", no generic base components with one usage, no
unrequested README or examples.

## 3. Day one vs later

Day one: what the batch's `SCR` ids need, plus the skeleton above. Later (propose, do not build):
theming beyond what is designed, animation systems, storybook, analytics, service worker/offline,
micro-frontend splitting — unless the design requires them now.

## 4. Checks before the gate

- Runs locally with documented commands, against the mock **and** against a real backend by config.
- A missing required env var makes the app fail loudly at startup, not silently at runtime.
- The API client is the only place that knows the envelope shape; no component unwraps responses.
- No component imports another feature module's internals; shared code sits where the design says.
- Nothing secret in a public env var or the bundle (`security-logging.md` §D).
- Lint/format pass; type-check clean; existing tests green.
- First budget measurement recorded as the baseline (`common/evidence.md`) — a baseline invented later
  is worthless.
