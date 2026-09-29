# Design tokens and component specs

## 1. Tokens — two layers

| Layer | Example | Used by |
|---|---|---|
| **Primitive** — the raw palette and scales | `color.blue.600 = #1d4ed8`, `space.4 = 16px` | only by semantic tokens |
| **Semantic** — what it is for | `color.bg.surface`, `color.text.muted`, `color.action.primary`, `space.inset.md` | screens and components |

Screens and components use **semantic** tokens only; a theme (dark mode, a brand) swaps the primitive
behind them. Categories: colour (bg, text, border, action, status: success/warning/danger/info), typography
(family, size, weight, line-height per text style), spacing, radius, border width, elevation/shadow,
motion (duration, easing), breakpoints, z-index layers.

`design-tokens.json` (template `assets/design-tokens.json`) follows the Design Tokens Community Group shape
(`$value`, `$type`) so tools and code generators can read it. `cecilia-dev-fe` maps it to CSS variables or
the repo's theme (Tailwind config, a theme object) — the mapping is dev-fe's code.

Every colour pair that can appear together (text on surface, icon on button) is listed with its measured
contrast ratio in the UI doc (`accessibility.md`).

## 2. Component spec — one per `CMP`

```
CMP-11 · OrderStatusBadge
Purpose: shows one order status, colour + text (never colour alone)
Anatomy: container · icon (optional) · label
Variants: status = pending | paid | shipped | cancelled | refunded
Sizes: sm | md
States: default (non-interactive)
Tokens: bg color.status.<x>.subtle · text color.status.<x>.strong · radius.full · space.inset.xs
Content: label from the status enum — copy per value in §Copy
A11y: text always present; contrast ≥ 4.5:1 per variant (table)
Used in: SCR-04, SCR-07
```

Interactive components list every state: default, hover, focus-visible, active/pressed, disabled,
loading, error, selected/checked where relevant — each with its tokens.

## 3. Naming shared with code

- Component names are the ones dev-fe will use in code (`OrderStatusBadge`), with the `CMP` id.
- Variants are named like props (`size="sm"`, `status="paid"`).
- An existing component library in the repo wins: design with its components and variants, and list any
  new variant as a proposal.
