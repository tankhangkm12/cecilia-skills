# Workflow options — input for `workflow.py options` (v20)

The orchestrator transcribes the merged plan's units and option shapes (never its own design) into
`tensura/tasks/<TASK>/options-input.json`, runs `scripts/workflow.py options --task <TASK> --input
tensura/tasks/<TASK>/options-input.json`, then `workflow.py decision` puts the options on the ONE decision
card (`assets/decision-card.md`); her answer → `workflow.py answer --task <TASK> --option <ID>` freezes it.
Rules: `references/workflow.md` O1–O2.

```json
{"mode": "standard", "flow": "personal",
 "options": [
  {"id": "A", "title": "Lean — one writer per layer", "split": "layer",
   "summary": "dev-be and dev-fe in one wave; functional + integration tests; 3-lens panel.",
   "tradeoff": "cheapest; the order module and the export module are built by one agent in sequence",
   "units": [
     {"id": "U1", "role": "cecilia-dev-be", "scope": "B-01 FR-03..05", "writes": ["src/order/**", "src/export/**"]},
     {"id": "U2", "role": "cecilia-dev-fe", "scope": "B-01 SCR-02", "writes": ["web/src/order/**"]}],
   "test_lenses": ["functional", "integration"],
   "review_lenses": ["correctness", "data", "api-consumer"]},
  {"id": "B", "title": "Wide — split backend by module", "split": "module",
   "units": [
     {"id": "U1", "role": "cecilia-dev-be", "writes": ["src/order/**"]},
     {"id": "U2", "role": "cecilia-dev-be", "writes": ["src/export/**"]},
     {"id": "U3", "role": "cecilia-dev-fe", "writes": ["web/src/order/**"]}],
   "test_lenses": ["functional", "integration", "security", "ui"],
   "review_lenses": ["correctness", "security", "data", "api-consumer"],
   "models": {"cecilia-dev-be": "strongest"}},
  {"id": "C", "title": "Competing — two export designs", "split": "competing",
   "decision": "D-12 open: streaming vs batch export",
   "units": [
     {"id": "U1", "role": "cecilia-dev-be", "scope": "export, streaming", "writes": ["src/export/**"]},
     {"id": "U2", "role": "cecilia-dev-be", "scope": "export, batch", "writes": ["src/export/**"]}],
   "test_lenses": ["functional", "concurrency-perf"],
   "review_lenses": ["correctness", "performance", "simplicity"]}]}
```

Fields per option: `id` · `title` · `split` (`module` | `layer` | `competing`) · `units` (build agents:
`role`, `id`, `scope`, `writes` globs — default the role's lane —, `wave` default 1, `model`) ·
`test_lenses` (one cecilia-test agent per lens, or `{"lens", "model"}`) · `review_lenses` (one panel
reviewer per lens) · optional `summary`, `tradeoff`, `decision` (required for `competing`), `models`
(per role).

The script refuses: fewer than 2 or more than 3 options · a role not in the registry or off in
`.cecilia/config.json` · a test/review lens not in the registry · overlapping write sets inside one wave
of a `module`/`layer` split · `competing` without `decision` · a panel without `correctness`, or a
CONTROLLED panel without `redteam` · two identical options · FAST (no workflow; `brief --short`).
It warns: lens counts outside STANDARD 3–4 / CONTROLLED 5–6, equal agent counts in every option.

Each option gets `counts` and an `estimate`, all `[projected]` (the consensus runs of
`references/consensus.md` §8 are common to every option): agent runs = dev units + test lenses +
review lenses × 2 + 1 judge, plus one fix round (half dev + half test + half review lenses × 2 + 1,
halves rounded up); tokens ≈ runs × 26,500 new input and × 7,000 output; wall time ≈ (10 + build waves)
sequential steps × 75 s — a parallel wave is one step, so more agents cost tokens, not time.
