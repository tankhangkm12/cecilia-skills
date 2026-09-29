# cecilia-extend — workflow (v20)

Detail behind the card. One responsibility: turn Cecilia's wish for a new role, flow or lens into a checked
**proposal** that uses the same interface as everything already in the registry. Applying it is hers.

## Layers (SOLID) — what each artefact may and may not do

| Artefact | Is | Declared by | Never |
|---|---|---|---|
| **Role** | expertise — a skill a host agent runs | `registry/roles/cecilia-<name>.json` + `skills/cecilia-<name>/` | grant itself tools (permissions come from its agent type), write outside its lane |
| **Flow** ("chế độ") | process — what happens at the 7 steps | `registry/flows/<name>.json` + its guide | grant permissions, relax A3/A4 or local-only |
| **Lens** | one angle of `cecilia-test` or `cecilia-review` | `registry/lenses/<test|review>/<name>.json` + its guide | add permissions or a new agent — it runs as an instance of the existing role |
| Agent type | permissions (writer · tester · reviewer · orchestrator) | core only | — (not scaffolded; pick an existing one) |
| Guard / adapters | enforcement / host format | generated from the registry | hand-edited per extension |

Adding = one manifest + its files. Tables (`shared/generated/*.md`), host agent files and the compiled
`.cecilia/registry.json` are generated from manifests — never edit a table to "register" something.

## X0 — Locate

- Read the brief header and `## Rules (must follow)`.
- `cecilia where` → `package data: <DATA>`. The tools are `<DATA>/tools/scaffold.py` and `<DATA>/tools/registry.py`
  (run them with the Python `cecilia where` prints).
- Existing names: `<ws>/.cecilia/registry.json` (roles, flows, lenses, lanes; `extensions` lists applied ones) or
  `python <DATA>/tools/registry.py` (core). Proposals already waiting: `tensura/extensions/*/`.

## X1 — Interview 🛑 (only what the request leaves open; one numbered list)

| # | Question | Fills |
|---|---|---|
| 1 | What exactly should it do — one sentence, one responsibility? What is it **not** for (which role does that)? | description / summary, `not_for` |
| 2 | Role: which inputs does it read and which outputs does it produce (artefact names as in the roster)? | `consumes`, `produces` |
| 3 | Role: which paths may it write (`tensura/…` = workspace, others = project)? Overlap with another role's lane? | `lane` (`--lane`) |
| 4 | Role: does it build (writer), test (tester) or only judge (reviewer, read-only)? | `agent_type` |
| 5 | How will `cecilia-review` judge its output — the 3–6 checks a reviewer must run? | `review-guide.md` §2 |
| 6 | Any project rules from day one (become `rules/…` lines Cecilia adds with `cecilia rules add`)? | rules slot |
| 7 | When should the orchestrator dispatch it (task signals), or when is the lens picked (what the diff touches)? | `dispatch_when` / `when` |
| 8 | Flow: for each of intake · plan · approve · dispatch · review · handoff · finish — what differs from `personal`? Settings with defaults? | flow guide, `settings` |
| 9 | Name (kebab-case; roles get `cecilia-`). | name |

## X2 — Options 🛑

Always offer the lighter alternatives first (same criteria: effort, what changes for every task, reversibility):
1. **A project rule** in `rules/` (Cecilia adds it; nothing to install).
2. **A lens** of `cecilia-test` / `cecilia-review` (a new angle, no new agent).
3. **A flow** (a different process, same roles).
4. **A new role** (a new expertise with its own lane).
Recommend one in a line; Cecilia picks.

## X3 — Scaffold (proposal target)

```bash
python <DATA>/tools/scaffold.py role <name> --agent-type writer|tester|reviewer --lane "<glob>" … \
       --consumes <a> … --produces <b> … --describe "<one line, no ': '>" --when "<dispatch signal>"
python <DATA>/tools/scaffold.py flow <name> --describe "<one line>"
python <DATA>/tools/scaffold.py lens <name> --kind test|review --describe "<one line>" --when "<what it touches>"
```
`--workspace <ws>` if not run inside it. Output folder: `tensura/extensions/<name>/` (roles: `cecilia-<name>`),
laid out like `.cecilia/extensions/`:

```
registry/roles/cecilia-<name>.json · skills/cecilia-<name>/{SKILL.md, references/workflow.md, references/review-guide.md}
registry/flows/<name>.json · flows/<name>.md
registry/lenses/<kind>/<name>.json · lenses/<kind>/<name>.md
rules/roles/<short>.md · rules/flows/<name>.md · rules/lenses/<name>.md   empty rules slot (Cecilia fills it)
```
The tool refuses a name that exists in the core registry or in applied extensions, and refuses to overwrite files
without `--force`. It validates right away and lists the `TODO(extend)` markers left to fill.

## X4 — Fill

Replace every `TODO(extend)` with the interview answers. Keep: every manifest key, `rules_slot` path, the 7
`## <step>` sections of a flow guide, the v20 card shape (frontmatter `name` + `description` ≤ 450 chars without
": ", title with v20, **Read first** line, Authority table, short rules, workflow summary, ≤ 5 KB — detail goes to
`references/workflow.md`). Do not add keys, tools or permissions the templates do not have.

## X5 — Check

`python <DATA>/tools/scaffold.py --check tensura/extensions/<name>` → must print `PASS`. It runs the registry
validation (core + this overlay, collisions, agent type, skill folder, guides, flow sections, lens kind), the card
rules, leftover `{{…}}` and `TODO(extend)` markers. FAIL → fix and re-run; never hand over a FAIL.

## X6 — Report 🛑

`tensura/reports/<TASK>/extend.md`: request → option chosen · file tree · key values (name, agent type, lane,
consumes/produces, when) · check output · what changes for Cecilia after applying (new agent, new lens in the
options, new `cecilia flow <name>` choice, new rules file). Chat ≤ 15 lines, ending with the command she runs:

```
cecilia extension apply tensura/extensions/<name>
```
The agent never runs it (human-only; the guard denies it) and never copies files into `.cecilia/` itself.

## Interface checklist (every item must hold before X6)

**Role** — [ ] one responsibility, one-sentence description (≤ 450 chars, no ": ") · [ ] all 14 manifest keys
(`name agent_type kind description default_on model consumes produces lane report review_guide rules_slot lenses
overrides`) · [ ] `agent_type` is an existing one; `overrides` all `null` unless Cecilia asked · [ ] reviewer ⇒
`lane: []` · [ ] lane as narrow as the job, no overlap with another role unless Cecilia agreed · [ ] report
`tensura/reports/<TASK>/<short>.md` · [ ] `rules_slot` `rules/roles/<short>.md` · [ ] review guide checks lane,
rules line, evidence and the role's own quality · [ ] card rules brief header, lane → `HANDOFF:`, `Rules:` line.

**Flow** — [ ] process only (no tools, no permissions) · [ ] all 7 steps in `steps` and one `## <step>` section
each · [ ] `settings` hold defaults only (Cecilia edits `flows.<name>` in config) · [ ] local-only, A3/A4 and the
fix-loop limit unchanged.

**Lens** — [ ] belongs to `cecilia-test` (`--kind test`) or `cecilia-review` (`--kind review`) · [ ] `when` names
what a change must touch · [ ] guide has When · Oracle · Techniques · Environment · Report · Never · [ ] report
`tensura/reports/<TASK>/<kind>-<name>.md` · [ ] no environment beyond local.

## Repo target — extending Cecilia itself (maintainers, from the source repo)

Only when Cecilia asks to change the Cecilia package (A3 each time: it writes outside `tensura/`):
```bash
python3 tools/scaffold.py role <name> --target repo …     # registry/roles/…, skills/cecilia-<name>/…
python3 tools/scaffold.py flow <name> --target repo …     # registry/flows/…, shared/flows/<name>.md
python3 tools/scaffold.py lens <name> --kind test|review --target repo   # skills/cecilia-<test|review>/references/lenses/
```
Then fill the `TODO(extend)` markers and run, in order: `python3 tools/sync_common.py` (copies `shared/` into the
new skill's `references/common/` and `scripts/`) · `python3 tools/build_adapters.py` (host agents + generated
tables) · `python3 tools/validate.py` (PASS) · `python3 -m unittest discover -s tests`. Add a token-budget scenario
(`tools/token_budget.json`) and ledger rules (`tools/rules.json`) when the role has mandatory rules. `--out DIR`
points the repo target at a copy of the repo (used by the tests).
