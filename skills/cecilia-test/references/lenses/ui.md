# Lens: ui (cecilia-test v20)

Brief header `LENS=ui`. Shared lens rules (files, isolation, report, lane): `../workflow.md` §Lenses.

## Attacks
What the user actually sees and can do: every screen in every state, at every breakpoint, by keyboard
and screen reader, with the console clean.

## Oracle
Frontend design `<app>-frontend.md` (screens, states, breakpoints) · UI doc and tokens · SRS AC for the
journeys · WCAG level Cecilia chose · `../web-interface-guidelines.md`.

## Techniques
- **Real browser** per `../visual-check.md` with `ui.browser` (`playwright-cli` default), own session
  `-s=test-ui-<unit>`, `--config` = the main checkout's `.playwright/cli.config.json`, local origins only.
- **States:** loading, empty, error, partial, offline, forbidden-hidden actions, long text; each driven
  from the contract (route mocks per `visual-check.md` §4), one screenshot per case `<SCR>-<state>-<width>.png`.
- **Breakpoints** from the design doc (else 360, 768, 1280); no horizontal scroll, no clipped controls.
- **a11y:** keyboard-only path through each journey, focus visible and in order, labels and roles,
  contrast numbers from `scripts/uikit.py`; an automated checker (axe) when the repo has one.
- **Console and network:** zero errors/warnings not explained; no failed requests in the happy path.
- Pixel diff against the design export where one exists (`uikit.py`).
- Critical journeys as E2E in the repo's framework (`@playwright/test`, Cypress); the CLI is for evidence.

## Files
E2E specs in `<repo e2e root>/ui/...` or suffix `.ui`; screenshots in
`<main checkout>/tensura/reports/<TASK>/ui/` (evidence, never committed).

## Environment
Own dev-server port from RUNTIME (check it is free, note the pid, stop it before reporting), own browser
session; never `close-all` / `kill-all`. Browser missing → visual rows `[unverified]` and the install quote (A3).

## Report
`tensura/reports/<TASK>/test-ui.md`: table `screen · state · width · screenshot · console · a11y · result`,
BUG table (`BUG-ui-nn`).

## Never
Restyle or fix a component (`HANDOFF: needs cecilia-dev-fe` / `cecilia-ui`) · open non-local sites or
Cecilia's real browser without her yes · use real accounts.
