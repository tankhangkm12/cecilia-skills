# Handoff to cecilia-dev-fe — and changing a design later

## 1. What dev-fe receives

| Artifact | Path (`workspace.md` §2.1) | Contains |
|---|---|---|
| UI design doc | `apps/<app>/<app>-ui.md` | tool + link + version, screen index, per SCR × state notes, component specs, copy, a11y tables, gaps |
| Tokens | `apps/<app>/design-tokens.json` | semantic + primitive tokens, light/dark |
| Exports | `apps/<app>/ui-exports/SCR-04-order-list--empty--mobile.png` | one image per SCR × state × breakpoint (not for Markdown) |

File names in `ui-exports/`: `<SCR>-<slug>--<state>--<breakpoint>.<png|svg>`, lower-kebab-case, so a
reviewer can check coverage by listing the folder.

## 2. Handoff note (end of `<app>-ui.md`)

- What is final, what is `[agent-chosen — needs review]`, what is waiting on a gap.
- Components new vs reused from the library, and which variants are new.
- Tokens added or changed since the last handoff (dev-fe updates the theme mapping).
- Anything the code must do that the picture cannot show: focus order, animations, what is lazy-loaded.

## 3. Review before build

Recommend an independent `cecilia-review` pass in ui mode (`review-ui.md`) before dev-fe starts a
screen that matters (CORE flow, new design system, many screens). The reviewer reads the doc, the tokens
and the exports — not the design tool — so the review works the same for Penpot, Figma and Markdown.

## 4. Changing an approved design

Like the contract: a change after dev-fe has started gets an impact table — which SCR, CMP, tokens and
dev-fe batches it touches — Cecilia approves, the doc's version bumps, the export files are replaced, and
the change is a `D-nn`. dev-fe never learns about a changed design from a new picture alone.
