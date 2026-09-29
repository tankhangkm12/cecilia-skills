# Third-party material in Cecilia v20

Vendored text is pinned to one upstream commit so that it never changes under you. Each file keeps
its licence text at the end. To update: re-vendor from a newer commit, review the diff, bump the
commit in the file header and here.

| In this package | Upstream | Commit (date) | Licence | Changes |
|---|---|---|---|---|
| `shared/scoped/frontend/web-interface-guidelines.md` (→ dev-fe, ui, test, review) | [vercel-labs/web-interface-guidelines](https://github.com/vercel-labs/web-interface-guidelines) `command.md` | `e3d624baaf29dc1fc645aff3e38f03e564d2d6b1` (2026-08-17) | MIT © 2025 Vercel Labs | slash-command frontmatter and `$ARGUMENTS` line removed; Cecilia priority note added on top |
| `shared/scoped/frontend/style/taste.md` | [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) `skills/taste-skill-v1/SKILL.md` | `c184364c58658b2f131b4ae8bd3d206cabb3deee` (2026-09-23) | MIT © 2026 Leonxlnx | frontmatter removed; "Cecilia overrides" block added on top |
| `shared/scoped/frontend/style/minimalist.md` | same repo, `skills/minimalist-skill/SKILL.md` | same | MIT | same |
| `shared/scoped/frontend/style/soft.md` | same repo, `skills/soft-skill/SKILL.md` | same | MIT | same |
| `shared/scoped/frontend/style/brutalist.md` | same repo, `skills/brutalist-skill/SKILL.md` | same | MIT | same |
| `shared/scoped/frontend/style/redesign.md` | same repo, `skills/redesign-skill/SKILL.md` | same | MIT | same |

Not vendored, used as external tools when Cecilia installs them (A3):

| Tool | Where | Licence |
|---|---|---|
| Playwright CLI (`@playwright/cli`, command `playwright-cli`), checked with 0.1.21 | [microsoft/playwright-cli](https://github.com/microsoft/playwright-cli) | Apache-2.0 |
| Playwright MCP (optional, `ui.browser: "playwright-mcp"`) | [microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp) | Apache-2.0 |

Written for Cecilia (no upstream text): `visual-check.md`, `image-to-code.md`, `uikit.py`,
`playwright-cli.config.json`. The large taste-skill v2 (`design-taste-frontend`, ~87 KB) and the image
generation skills were deliberately not included.
