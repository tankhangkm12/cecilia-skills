# Draft PR — cecilia-devops

Title: `ci(<scope>): <summary> [<TASK>]` or `build(<scope>): …` / `chore(infra): …`

Cecilia reads this before anyone else. It must answer "what breaks if this is wrong" without her
opening a single file. Secret **names** only — never a value.

---

## What and why

One paragraph: the problem, and what this changes. Cite the doc/plan section or the `INC-nn` that
asked for it.

## Blast radius

| Environment | What changes | Interruption | What is NOT affected |
|---|---|---|---|
| ENV-02 staging | … | ~20s rollout | DB, other services |

Say what is *not* affected too — that is half the reassurance, and writing it forces the check.

## Commands

```bash
# Apply
<exact command, with context/namespace/profile/region explicit>

# Rollback  ← verified to exist on <date>: <evidence, e.g. helm history shows revision 7>
<exact command>

# Verify recovery
<exact check and what a healthy result looks like>
```

## Evidence from the run (`deploy-and-rollback.md` §4)

| Proof | Result | Evidence |
|---|---|---|
| 1. Alive | ✅ / ❌ | `/healthz` 200; `POST /orders` → 201, id 8831 |
| 2. **Rollback rehearsed** | ✅ / ❌ | rolled back to rev 7 at 10:41, served traffic, rolled forward 10:44 |
| 3. Observable | ✅ / ❌ | logs in <destination> with `env=staging`; alert `orders-5xx` exists, not muted |

Any ❌ must be explained here, not left for review to find. Not rehearsable → say why and what the
recovery procedure is instead, with Cecilia's decision.

## Files

| Path | Change | Why |
|---|---|---|

Anything in `cecilia-dev-be` / `cecilia-dev-fe`'s column that needs changing → list it here as a **request**, with the
files, and say it is not included in this PR.

## Secrets touched

| Name | Environment | Source | New or existing | Rotation owner |
|---|---|---|---|---|

No values. Confirm the secret scan over the diff ran and was clean.

## Static gate (Y5)

| Check | Tool | Result |
|---|---|---|
| workflow/pipeline lint | | ✅ / ⚠️ `[unverified]` — tool not available |
| Dockerfile lint | | |
| manifest validate / `helm template` | | |
| `terraform fmt -check` / `validate` / `plan` | | |
| secret scan over diff | | |

`[unverified]` is a valid row; "passed" without a tool is not.

## Cost

Delta per month, what drives it, and whether it is within the ceiling Cecilia set. "None" if none.

## Risks and what I would still like to check

Two to four concrete items: problem → consequence → what would settle it. Including doubts about the
approach requested — say it once, clearly, then follow her decision.

## Docs

The infrastructure doc updated: sections <n>. Decisions added to `tensura/docs/DECISIONS.md`: `D-nn`.

---

Pushing, opening this PR, marking it Ready and every later push are Cecilia's (A4 for agents, local-only,
`common/git-handoff.md` §1): this body goes to `tensura/reports/<TASK>/pr-body.md` and the report carries the push and
`gh pr create --draft … --body-file …` commands for her to run. **Production
promotion is hers to run** — the commands above are written for her, not executed
(`authority.md` §1).
