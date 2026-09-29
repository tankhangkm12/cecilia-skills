# Accessibility — designed in, measured, written down

Target: **WCAG 2.2 level AA** unless Cecilia records another level. The design can make most of these
impossible to get wrong in code — or impossible to get right. Cite the success criterion by number.

## 1. Checks the design owns

| Check | Requirement (WCAG 2.2) | How to record it |
|---|---|---|
| Text contrast | ≥ 4.5:1; large text (≥ 24 px, or ≥ 18.66 px bold) ≥ 3:1 — 1.4.3 | table: pair · ratio · pass |
| Non-text contrast | UI component boundaries, focus indicators, icons that carry meaning ≥ 3:1 — 1.4.11 | same table |
| Not colour alone | status, errors, links, charts also use text, icon or pattern — 1.4.1 | note per component |
| Focus visible | every interactive element has a designed focus style — 2.4.7; not hidden under sticky bars — 2.4.11 | focus state in each component spec |
| Target size | pointer targets ≥ 24×24 CSS px or enough spacing — 2.5.8 | component sizes |
| Reflow | usable at 320 CSS px width without two-way scrolling — 1.4.10 | narrowest breakpoint designed |
| Text spacing / zoom | layout survives larger text and spacing — 1.4.4, 1.4.12 | stress frame at 200 % |
| Labels | every input has a visible label (placeholder is not a label) — 3.3.2 | form specs |
| Errors | identified in text, next to the field, with how to fix — 3.3.1, 3.3.3 | error states |
| Dragging | any drag action has a single-pointer alternative — 2.5.7 | interaction notes |
| Motion | no essential meaning only in animation; respect reduced-motion — 2.3.3 (AAA, recommended) | motion tokens |
| Authentication | no memory/transcription puzzle as the only way in — 3.3.8 | login flow |

## 2. Measuring contrast

Compute the ratio from the two colours' relative luminance (the WCAG formula) — by a tool the session has
or by a short local script; never estimate by eye. Record every pair actually used, per theme (light and
dark separately). A pair that fails is fixed in the tokens, not per screen.

## 3. What code must still do

Semantic HTML, accessible names, keyboard handling, focus management on route change and dialogs, live
regions for async feedback — `cecilia-dev-fe`'s work, checked by `cecilia-review`. The UI doc lists
the expected focus order and the accessible name for icon-only buttons so dev-fe does not guess.
