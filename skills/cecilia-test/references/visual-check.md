# Visual check — see what you built (v20)

Code that compiles is not a finished screen. This loop opens the running app in a real browser, captures
every screen × state × breakpoint, and turns "looks right" into evidence: screenshots, console errors,
pixel difference from the design, contrast numbers, guideline findings.

## 1. Which browser tool

`.cecilia/config.json` → `ui.browser`:

| Value | Use |
|---|---|
| `"playwright-cli"` (default) | the `playwright-cli` command — short commands, snapshots saved to files, few tokens |
| `"playwright-mcp"` | the Playwright MCP tools (`browser_navigate`, `browser_resize`, `browser_take_screenshot`, `browser_console_messages`, …) — same loop and evidence, but **one browser shared by every agent**: only one member per wave uses it; allowed origins are the server's own settings (Cecilia's); copy each screenshot into the evidence folder |
| `"none"` | no browser: say so, mark visual rows `[unverified]` and list what Cecilia should check by eye |

**Is it installed?** `playwright-cli --version`; else `npx --no-install playwright cli --version` (then use
`npx playwright cli` in every command). Neither → do not install on your own. Quote both as A3 in one
numbered message — in Cecilia's session wait for her answer; as a sub-agent return the quotes, finish
everything else and mark the visual rows `[unverified] — browser not installed`:

```text
1. npm install -g @playwright/cli@latest          (installs the CLI, ~20 MB)
2. playwright-cli install-browser chromium        (downloads Chromium, ~150 MB)
```

The MCP server is host configuration — Cecilia adds it herself; you only say which one and why.

## 2. Guard rails (the guard enforces most of them)

- **Local pages only.** `.playwright/cli.config.json` in the main checkout (created by the installer,
  Cecilia's file — the guard blocks edits) allows only `localhost` / `127.0.0.1` origins. **Always open
  with `--config=<main checkout>/.playwright/cli.config.json`** (absolute path); if that file does not
  exist, stop and tell Cecilia — without it the browser can reach any site. Opening another site,
  `attach` to Cecilia's real browser, a `--profile`, another `--config` or `run-code` needs her yes (A3).
  A page that must call a remote API during the check → mock it with `route` (§4) or ask.
- **Your session and server only.** Always `-s=<member>` — the browser session in your brief's RUNTIME
  block, or your role name (`dev-fe`, `test`) when there is no brief. Never `close-all` / `kill-all` —
  they stop other members' browsers (A3). Start the dev server on your own port, check the port is free
  first, note its process id, and stop it when you finish — never leave it running when you report.
- **CONTROLLED:** the dev server command, `playwright-cli -s=<member> *` and the `uikit.py` calls must be
  in the batch scope's `commands`; if they are not, the visual rows are `[unverified]` and the missing
  commands are a scope question for Cecilia.
- **No real accounts.** Test users and seed data only. `state-save` files hold tokens: only when
  `.playwright-cli/` is in `.gitignore`; never commit or report their content.
- **Evidence location.** `<main checkout>/tensura/reports/<TASK>/ui/` by absolute path — the main
  checkout is your brief's documents-and-reports path, or the repository root when there is no brief.
  Never inside a worktree. Name: `<SCR>-<state>-<width>.png`. Screenshots are evidence, not source: they
  stay out of commits unless Cecilia asks (the installer suggests ignoring `tensura/reports/*/ui/`).

## 3. The loop

`UIKIT` below is this skill's script: `.claude/skills/<role>/scripts/uikit.py` (Claude Code),
`.agents/skills/<role>/scripts/uikit.py` (Antigravity) or the same under the global skills folder. Use
`python3` (Windows: `py` or `python`).

```bash
S=dev-fe-B02                                   # your session name
PORT=3100 npm run dev                          # your own port block (parallel.md §2), in the background;
                                               # note its process id — stop it at the end
playwright-cli -s=$S open http://localhost:3100/orders --config=/repo/.playwright/cli.config.json
playwright-cli -s=$S snapshot                  # roles, names, refs — cheap; read this before screenshots
playwright-cli -s=$S resize 390 844            # breakpoints: the design's, else 390x844 · 768x1024 · 1440x900
playwright-cli -s=$S screenshot --filename=<WORKDIR>/reports/SHOP-42/ui/SCR-03-empty-390.png
playwright-cli -s=$S console warning           # errors and warnings are findings
playwright-cli -s=$S close                     # then stop the dev server you started
```

1. **Snapshot first, screenshots for looks.** The snapshot (accessibility tree) finds missing labels,
   wrong roles and broken structure for a fraction of the tokens. Look at a screenshot only to judge
   layout, spacing, colour and overflow.
2. **Every state, not just the happy one.** Drive states with mocks from the contract (§4) and with
   emulation: `set-color-scheme dark`, `set-reduced-motion reduce`, `set-forced-colors active`,
   `open --mobile`.
3. **Real content.** Long Vietnamese names, 0 / 1 / many rows, very long money values.
4. **Compare with the design** when an export exists. Exports live in the main checkout at
   `tensura/docs/apps/<app>/ui-exports/<SCR>-<slug>--<state>--<breakpoint>.png` (cecilia-ui handoff);
   the breakpoint names map to widths in `<app>-ui.md`. Capture at the export's width and height, then
   `python3 $UIKIT diff <export.png> <shot> --out <shot>-diff.png` — report the percentage and the
   difference box; look at the diff image before judging. PNG at 1x only: an SVG export or an @2x image
   is compared by eye (structure), not by pixels.
5. **Measure contrast** of every text/background pair you introduced:
   `python3 $UIKIT contrast "#6b7280" "#ffffff"` (AA: 4.5 text, 3 large text and UI parts).
6. **Guidelines.** Check the changed files against `references/web-interface-guidelines.md`.
7. **dev-fe:** fix, re-capture, re-measure — at most 3 polish rounds per screen, then report what remains
   (a failing build or command still follows `parallel.md` §7). **cecilia-test:** never fix — each defect
   is a `BUG-nn` with the screenshot as evidence.

## 4. States from the contract

Mock the endpoint with the documented error — never invent a shape:

```bash
playwright-cli -s=$S route "**/api/orders/*/cancel" --status=409 --body='{"code":"ORDER_ALREADY_PAID","message":"…"}'
playwright-cli -s=$S route "**/api/orders" --body='[]'           # empty state
playwright-cli -s=$S unroute                                     # back to the real API / app mock
```

Slow network / loading: route with the app's own delay mock, or capture right after the action.

## 5. Evidence in the report

| SCR | state | width | screenshot | console | diff vs design | contrast | guidelines |
|---|---|---|---|---|---|---|---|
| SCR-03 | empty | 390 | `ui/SCR-03-empty-390.png` | 0 errors | 1.8 % (box 12–380, 400–470) | 2 pairs ≥ 4.5 | 0 findings |

Rows you could not capture say why and stay `[unverified]`. Pixel percentages are progress numbers, not
pass marks, unless Cecilia set a `--max-percent` for the task.
