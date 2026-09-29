# Image to code — build a screen from a picture (v20)

For a screenshot, mockup, photo of a sketch or design export that Cecilia gives as the spec. The goal is
the **design system behind the picture** — tokens and components the repo can reuse — not a pixel copy.

## 0. What is the picture? (ask once if unclear)

| Kind | Target |
|---|---|
| **Spec** — Cecilia's own design / an approved export | match it: tokens, spacing, every visible detail; diff it (§5) |
| **Reference** — "làm giống kiểu này", another product | take the *structure and feel* only. Another brand's identity (logo, name, signature colours, illustrations, copy) is never copied (cecilia-ui A4) |
| **Sketch / wireframe** | structure only; visuals come from the design system |

## 1. Inventory (write it before code)

- Regions top to bottom, and which existing components (`CMP`) each maps to. Reuse before creating.
- Every element's role: heading, text, button, link, input, image, icon, list/table row.
- States **visible** in the picture, and the states the screen needs but the picture does not show
  (loading, empty, error, disabled, focus, hover, long text). Missing ones: use the design's shared
  pattern, or ask — never guess in silence.
- Breakpoint the picture shows; the others you must decide (ask or follow the design).

## 2. Tokens, measured

```bash
python3 $UIKIT palette ref.png --tokens <path>/design-tokens.json   # colours → nearest token, ΔE
python3 $UIKIT contrast "#1f2937" "#ffffff"                          # every text/background pair
```

(`$UIKIT` = this skill's `scripts/uikit.py`, see `visual-check.md` §3; Windows: `py`.)

- ΔE < 2.3 → it *is* that token. 2.3–5 → probably the token; use it and note it. > 5 → no token matches:
  ask (new token, or map to an existing one) — never a raw hex in a component.
- Type sizes, spacing and radii: measure in pixels from the image (scale factor = image width ÷ the
  viewport it shows), then snap to the repo's scale (e.g. 4 px steps). Report measured → chosen.
- No design tokens in the repo yet → propose a small set (colour roles, type scale, spacing scale) as a
  decision for Cecilia before building many screens.

## 3. Build

Structure first (semantic HTML, layout with flex/grid, no absolute positioning to imitate the picture),
then tokens, then states. Real content from the contract or fixtures, not the picture's lorem ipsum.
Images and icons: the repo's icon set and local placeholders — never hotlink the picture's assets.
Names, prices and dates come from the contract or fixtures — never copied from someone else's picture.

## 4. Accessibility at the same time

Labels, focus order, keyboard, contrast ≥ AA, target size, `prefers-reduced-motion` — a faithful copy of
an inaccessible picture is still a defect (report the conflict, propose the accessible variant).

## 5. Verify against the picture

Render at the picture's CSS viewport — its pixel size divided by its scale (a 2780 px wide @2x
screenshot is a 1390 px viewport): `playwright-cli resize <w> <h>`, screenshot, then (1x pictures):

```bash
python3 $UIKIT diff ref.png shot.png --out shot-diff.png
```

Spec: iterate until the remaining difference is explained (fonts, live data, anti-aliasing) — report the
percentage and box per round (max 3 polish rounds, then report). Reference/sketch: no pixel target; report the
structure check and what was deliberately different.

## 6. Report

Picture kind · components reused / created · tokens mapped (ΔE) and new tokens proposed · measured →
chosen sizes · states not shown in the picture and how each was resolved · diff % per screen · contrast
pairs · open questions.
