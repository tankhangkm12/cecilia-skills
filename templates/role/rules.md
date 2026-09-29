# Rules for {{name}}

<!-- cecilia-rules v20 · only {{name}} reads this file (embedded in its brief), after rules/_project.md.
One rule per line: `- PR-nn: text` (ids unique in the file; `cecilia rules add --role {{short}} "text"`).
Optional machine checks: a fenced block with info string cecilia-check holding a JSON list of
{"id", "forbid_regex", "paths"} or {"id", "require_command"} objects.
Precedence: A3/A4 safety > project rules > role defaults > skill text. Rules only tighten. Only Cecilia edits rules/. -->
