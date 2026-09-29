# <app> — UI design

> Version <x.y> · Updated: <YYYY-MM-DD> · Owner: cecilia-ui
> Tool: <Penpot project "<name>" | Figma file <url> | Markdown> (`D-nn`) · Design file version/date: <…>
> Inputs: `requirements.md` §<n> · `<app>-frontend.md` v<n> · `<unit>-api.yaml` v<n> · tokens: `design-tokens.json`
> Accessibility target: WCAG 2.2 AA · Breakpoints: <e.g. 360, 768, 1280> · Themes: <light | light+dark>
> Confidence: `[verified]` `[inferred]` `[unverified]` · `[agent-chosen — needs review]` marks unapproved choices

## 1. Flows
```
<ASCII flow per journey, every branch: success, failure, cancel, back, timeout>
```

## 2. Screen index
| SCR | Name | Serves (FR/UC) | States designed / required | Breakpoints | Exports |
|---|---|---|---|---|---|

## 3. Per screen
### SCR-01 — <name>
**Wireframe** (low-fi, approved <date>)
```
<ASCII layout>
```
**States**
| State | What the user sees | Copy | Action / recovery | Export |
|---|---|---|---|---|
| loading | | | | |
| empty — first use | | | | |
| empty — no results | | | | |
| partial | | | | |
| error `<CODE>` | | | | |
| permission denied | | | | |
| offline / stale | | | | |
| submitting | | | | |
| success | | | | |

**Responsive:** <what reflows / collapses / hides per breakpoint>
**Focus order:** <1 → 2 → …> · **Icon-only buttons' accessible names:** <…>

## 4. Components
| CMP | Name (as in code) | Variants | Sizes | States | Tokens | New / from library |
|---|---|---|---|---|---|---|

## 5. Tokens
Summary of `design-tokens.json`: groups, what changed since last handoff.

## 6. Accessibility
| Pair (foreground / background) | Theme | Ratio | Needed | Pass |
|---|---|---|---|---|

Other checks (target size, reflow 320 px, not colour alone, labels, errors): <result per item>

## 7. Copy
| Key | Text (vi) | Text (other languages) | Status |
|---|---|---|---|

## 8. Gaps *(to cecilia-design)*
| # | Screen | Needs | Contract / frontend architecture provides | Proposed change | Blocks |
|---|---|---|---|---|---|

## 9. Handoff note
- Final / pending: · New components/variants: · Token changes: · Behaviour the pictures cannot show:
