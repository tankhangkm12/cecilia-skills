# The report surface — schema, upsert, provenance, degradation

The briefing may also live outside `tensura/`, on a surface Cecilia opens: Google Sheets + Google
Docs, or Notion. **Publishing there is an A3 action every time** (`common/core.md` §5.3): quote the
destination (workspace, document, tabs) and what data class goes out, and wait for her yes — unless
she recorded an exception for exactly that destination. It is published only after
`cecilia-review` (verify mode) returned PASS on the draft. This skill is the only writer. The surface is a **mirror** of primary sources under `tensura/`,
never a second source of truth — when the two disagree, `tensura/` wins and the surface is corrected.

## 1. Which surface

Use the MCP Cecilia has connected. If more than one is connected, ask once (`common/decisions.md`) which she
wants; record the answer in `DECISIONS.md` as `D-nn` so it is not re-asked. Typical split:

- **Google Sheets** — the living tracker (tabs below). Best for rows Cecilia filters and sorts.
- **Google Docs** — the narrative briefing (the `common/evidence.md` shape). Best for reading.
- **Notion** — can hold both: databases for the tracker tabs, a page for the narrative.

## 2. Sheets schema — one workbook per epic, five tabs

Every tab's first columns are `key` and `synced_from` and `synced_at` (provenance, §4). `key` is what
makes a write an update instead of a duplicate.

| Tab | key | Columns |
|---|---|---|
| **Status** | batch id | batch · role · state (TODO/DOING/DRAFT_PR/READY/MERGED/BLOCKED) · progress (done/total) · blocker · report |
| **Metrics** | `M-nn` | date · batch · role · metric · value · formula · source · label |
| **Decisions** | decision ref | opened · what needs deciding · options · recommendation (whose) · `[agent-chosen]`? · status |
| **Challenges** | `C-nn` | date · artifact/id · challenger→owner · claim · status · decided-by |
| **Delivery** | PR/branch | role · branch · PR state · target · rollback rehearsed? (devops) · link |

The Metrics, Challenges tabs are mirrors of `metrics.md` and `challenges.md` — same ids, so a reader
can go from a surface row straight to the log row. Never compute a new number on the surface; copy the
computed one with its `M-nn`.

## 3. Docs / Notion narrative

One document per epic, overwritten in place each run (its version history is the audit trail). Sections
are exactly the briefing's (`briefing-method.md` §2): control block, decision queue, measured, quality
posture, what each area needs. A Notion page uses the same headings; the tracker tabs become linked
Notion databases.

## 4. Upsert and provenance — the rule that stops duplication and lies

- **Upsert by key.** Read the tab, find the row whose `key` matches, update it; only insert when no
  row matches. A re-run of the same briefing must leave the row count unchanged.
- **Provenance on every row and section.** `synced_from` = the `tensura/` path the value came from;
  `synced_at` = the timestamp of this sync. Every cell is traceable back to a source file — this is
  also what lets `cecilia-review (verify mode)` confirm the surface against `tensura/`.
- **Never edit by hand-shaped guesses.** If a value cannot be read from a source, the cell is left as
  `[unverified]` with a note, never filled to look complete.
- **Deletes are tombstones, not removals.** A batch dropped from the plan is marked `DROPPED` with the
  decision ref, not deleted — the history stays legible.

## 5. Secrets and data exposure

The surface is more widely shared than the repo. Never write a secret value, token, credential,
connection string or customer datum onto it (`common/core.md` §2). State once in the narrative what data
class is synced outward (ids, statuses, metrics, challenge text) so Cecilia sees the exposure. If a
source report contains a secret, that is itself a finding for `cecilia-review`/`cecilia-devops`, and
the value is never carried onto the surface.

## 6. When no MCP is connected

Degrade in the open (`common/capabilities.md` §3): write the full briefing to
`tensura/reports/<TASK>/<date>-briefing.md`, and tell Cecilia in one line that it was not synced
to any surface and what to connect to enable it. Never emulate a publish, never claim a link that does
not exist.
