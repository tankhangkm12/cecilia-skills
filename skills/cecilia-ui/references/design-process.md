# Design process — from flows to finished screens

## 1. Inputs, and what to do when one is missing

| Input | From | Missing → |
|---|---|---|
| journeys, FR/UC, AC | requirements | ask; or design from Cecilia's brief and mark every screen `[inferred]` |
| SCR list, states per screen, CMP tree, routes | frontend architecture (`cecilia-design`) | write the SCR inventory yourself (`workspace.md` §4: first writer creates ids) and send gaps to design |
| data per screen, error codes | API contract | design with placeholders, list each as a contract gap |
| brand, existing kit | Cecilia / repo | propose a neutral token set as an option, not a decision |

## 2. Flows and wireframes (U3) — structure before style

Flow per journey, ASCII, with every branch — success, failure, cancel, back, timeout:

```
[SCR-03 Cart] --checkout--> [SCR-05 Payment] --ok--> [SCR-06 Done]
                                   |--declined (PAYMENT_DECLINED)--> [SCR-05 error state] --retry--> ...
                                   '--session expired--> [SCR-01 Login] --back--> [SCR-05, cart kept]
```

Wireframe per screen: layout regions, content priority, primary action, where feedback appears. No
colour, no imagery. Check with Cecilia (🛑) — this is the cheapest moment to change anything.

## 3. Visual design (U5)

- **Hierarchy**: one primary action per screen; size, weight and position say what matters.
- **Spacing** from the token scale only (4/8-based); alignment to a grid per breakpoint.
- **Typography**: a small type scale; line length 45–90 characters for reading text.
- **Feedback**: every action shows pending, success and failure where the user is looking.
- **States** (from the frontend architecture), each designed: loading (skeleton vs spinner — one rule for
  the app), empty (first use vs no results — different copy and action), partial, each error code
  (message + recovery), permission-denied, offline/stale, submitting, success.
- **Breakpoints**: at least the narrowest supported width and desktop; say what reflows, collapses, hides.
- **Stress test**: longest realistic name and text in Vietnamese and every other language shipped, 0/1/
  many items, large numbers and money, missing images, slow network.

## 4. Copy

Microcopy is product language: propose it, mark it `[agent-chosen — needs review]` until Cecilia
approves, and keep error messages consistent with the contract's error codes (one message per code).

## 5. Exit gate (U6) — print every row with evidence

| # | Check |
|---|---|
| 1 | Every `SCR` in scope has every state from the frontend architecture designed (or "shared pattern X") |
| 2 | Every screen at every agreed breakpoint |
| 3 | Only tokens on screens — no raw colour, size or spacing values |
| 4 | Every component used has a spec with all its interactive states, named with its `CMP` id |
| 5 | Contrast measured for every text/background and UI/background pair used; all meet the target level |
| 6 | Focus order and visible focus shown for every interactive screen; targets ≥ 24×24 CSS px |
| 7 | Stress content applied (long text, 0/1/many, errors) |
| 8 | Every data element maps to a contract field, or is a listed gap |
| 9 | Exports exist for every SCR × state (or "Markdown — n/a"); tokens file current |
| 10 | Copy that is not yet approved is marked `[agent-chosen — needs review]` |
