# Reviewing UI design — before frontend code is written

Target: the app's UI design doc (`<app>-ui.md`), `design-tokens.json` and the images in `ui-exports/`.
The reviewer judges from these files, not from the design tool, so the review is the same whether the
design was made in Penpot, Figma or Markdown — and stays read-only. A design file the exports do not
reflect is itself a finding.

## 1. Oracles

Requirements (journeys, FR/UC, AC) · the frontend architecture (SCR list, states, CMP tree) · the API
contract (fields, error codes) · WCAG 2.2 at the level recorded in the doc · `DECISIONS.md`.

## 2. Checks, heaviest first

| # | Check | Failure it catches |
|---|---|---|
| 1 | Every user-facing FR/UC has a flow and screens; every flow branch (failure, cancel, back, timeout) ends somewhere sensible | dead ends, journeys nobody designed |
| 2 | Every SCR × state from the frontend architecture is designed — count them from `ui-exports/` file names and the doc's state tables | the state dev-fe will invent under pressure |
| 3 | Every error code a screen can receive has a message and a recovery; messages match the contract's codes | generic "something went wrong" everywhere |
| 4 | Contrast: **recompute** the ratio from the hex values with the WCAG luminance formula for the pairs in the doc's table (show the working; if you cannot calculate reliably, mark `[unverified]` and ask for a contrast run by another role); non-text contrast for inputs, focus rings, meaningful icons | text that fails WCAG in one theme only |
| 5 | Focus states designed for every interactive component; targets ≥ 24×24 CSS px; nothing conveyed by colour alone; labels on every input | inaccessible by construction |
| 6 | Only semantic tokens on screens; tokens file consistent with the doc; no raw values | themes that cannot be switched, drift between screens |
| 7 | Components: every one used has a spec with all interactive states; names match `CMP` ids and the code's names | dev-fe building three versions of one button |
| 8 | Responsive: each agreed breakpoint designed; reflow at 320 px | broken mobile layout |
| 9 | Real content: long Vietnamese text, 0/1/many, big numbers and money | truncation and overflow in production |
| 10 | Data shown maps to contract fields; missing data is a listed gap, not an invented field | UI that needs an API that does not exist |
| 11 | Unapproved copy and choices are marked `[agent-chosen — needs review]` | agent decisions passing as Cecilia's |
| 12 | Component specs against `web-interface-guidelines.md` (focus, forms, motion/reduced motion, touch, long and empty content); the priority note at its top applies | patterns dev-fe will have to rework |
| 13 | `ui.style` / inspiration used only where brand and design system were silent; no other brand's logo, name, signature colours or copy; sources named | a design that copies someone else or overrides decisions |

## 3. Severity

| Level | Examples |
|---|---|
| **Blocker** | a required state or error missing on a CORE flow · text contrast failing the target on a primary screen · a flow with no way back from an error · a screen depending on data the contract lacks with no gap row |
| **Should-fix** | focus states missing on secondary components · raw values instead of tokens · a breakpoint not designed · unapproved copy not marked |
| **Suggestion** | visual polish, spacing rhythm, naming |
| **Question** | "should cancelled orders be hidden or greyed out?" |

## 4. Also report

- **State coverage table**: `SCR · states required · states designed · exports present · gap`.
- **Contrast table**: `pair · theme · ratio claimed · ratio recomputed · pass`.
- After dev-fe builds: `review-frontend.md` §2 checks the code against this design; differences between
  exports and the running UI are findings for whichever side is wrong.
