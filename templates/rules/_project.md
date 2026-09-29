# Project rules

<!-- cecilia-rules v20 · every role and the orchestrator read this file.
One rule per line: `- PR-nn: text` (ids unique in the file; `cecilia rules add --project "text"` picks the next).
Optional machine checks for cecilia_check.py: a fenced block with info string cecilia-check holding a JSON list,
  [{"id": "PR-01", "forbid_regex": "console\\.log\\(", "paths": ["src/**"]}, {"id": "PR-02", "require_command": "npm run lint"}]
Precedence: A3/A4 safety > project rules > role defaults > skill text. Rules only tighten: a rule that allows
push, PR, merge, production or secrets is a lint error (`cecilia rules lint`). Only Cecilia edits rules/. -->
