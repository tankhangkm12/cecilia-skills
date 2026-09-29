# Review guide — {{name}} output (v20)

How `cecilia-review` (and each panel lens) judges what {{name}} produces: {{produces_md}}.
The reviewer is read-only; every finding cites a file:line or a quoted passage and gets a severity.

## 1. Inputs the reviewer reads

- The brief (header `ROLE={{name}}`) and its `## Rules (must follow)` block — the rules are review criteria too.
- The role's report `{{report}}` and the outputs it lists.
- The inputs the role consumed: {{consumes_md}}.

## 2. Checks (each → PASS / finding)

1. **Brief and scope.** Every output traces to the brief; nothing "while here"; nothing outside the lane
   {{lane_md}} (a write outside it = BLOCKER).
2. **Rules.** The report ends with `Rules: <hash> (PR-ids)` and the hash matches the brief's `RULES=`; each applied
   project rule is visibly met (machine checks in `cecilia-check` blocks re-run).
3. **Evidence.** Claims labelled; "passed" only with a run on this SHA; numbers carry inputs.
4. **Decisions.** No business/contract/schema/architecture decision taken silently — options were given.
5. **Handoffs.** Work that belongs to another role was handed off (`HANDOFF:`), not done.
6. TODO(extend): the role-specific quality checks (correctness of its own artefact, completeness, style).

## 3. Severity

**BLOCKER** wrong or unsafe output, lane or A3/A4 breach, broken rule · **SHOULD-FIX** gap an acceptance criterion
needs · **SUGGESTION** simpler/clearer · **QUESTION** cannot judge without an answer.
