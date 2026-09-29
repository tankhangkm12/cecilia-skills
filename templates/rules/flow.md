# Rules for the __NAME__ flow

<!-- cecilia-rules v20 · read by every role while `flow` in .cecilia/config.json is "__NAME__".
One rule per line: `- PR-nn: text` (ids unique in the file; `cecilia rules add --flow __NAME__ "text"`).
Optional machine checks: a fenced block with info string cecilia-check holding a JSON list of
{"id", "forbid_regex", "paths"} or {"id", "require_command"} objects.
Precedence: A3/A4 safety > project rules > role defaults > skill text. Rules only tighten. Only Cecilia edits rules/. -->
