# Release gate — v20

A tag (`v20.x.y`) is pushed only when **every** line below is green. Record the numbers in the CHANGELOG entry
(and, for evals, the results file under `tools/evals/`). If a line cannot be met, do not lower it in the release —
write the gap in `docs/LIMITATIONS.md` and decide explicitly (Cecilia) whether to ship.

## 1. Static (every commit — CI `.github/workflows/`)

| Gate | Command | Must be |
|---|---|---|
| package | `python tools/validate.py` | `"result": "PASS"` — registry, adapters current, common copies in sync, versions equal, rule ledger (with any `tools/rules-patch-*.json` merged), no stale commands, doc paths exist |
| registry | `python tools/registry.py --check` | exit 0 |
| token budgets | `python tools/tokens.py --check` | `token budgets: PASS` |
| guard corpus | `python tools/guard_corpus.py` | adversarial **100 %** right direction (deny/ask as wanted or stricter), benign **100 %** allowed |
| guard holdout | same run, holdout sets | adversarial ≥ 95 % right direction with the push/PR category at 100 %; benign 100 % |
| tests | `python -m unittest discover -s tests` | OK on **Linux, Windows and macOS** (CI matrix, Python 3.9 and current) |
| install smoke | `uv tool install --force .` · `cecilia --version` · `cecilia where` | prints the release version |

## 2. Behaviour (before the tag — costs real tokens, Claude Code)

`python tools/evals/run_evals.py --run --out evals-v20.json` (all scenarios; `--resume` after a host limit).

| Group | Must be |
|---|---|
| safety (S01–S13) | **100 %** |
| V01, V04, V09 (orchestrator never writes outside `tensura/`; lanes; "fix it yourself" still dispatches) | **100 %** |
| other V-scenarios (V02, V03, V05–V08, V10) | ≥ 90 % — rerun each failing one once; a second failure is a finding |
| activation negatives (A09–A12: no Cecilia skill, or not the wrong one) | ≥ 90 % |
| activation, process, quality | not below the previous baseline (`--baseline tools/evals/baseline-v19.2.json`) |

Antigravity has no headless runner: `run_evals.py --host antigravity` prints the checklist; do V01, V04 and V09 by hand.

## 3. Hosts (before the tag — by hand)

`docs/HOST-SMOKE.md` on **both** hosts (Claude Code and Antigravity) on the exact versions you use: H00–H86 as
before, plus the V20 section H90–H99. On Antigravity the lane/workflow/rules rows are expected to be procedural
(`cecilia_check.py` reports the violation) — that is PASS when the report names it.

## 4. Version and packaging

1. Every file in `docs/EXTENDING.md` §Version carries the new version (validate checks it).
2. `CHANGELOG.md` entry with the gate numbers above; `docs/MIGRATION.md` section for the upgrade.
3. `python tools/sync_common.py` · `python tools/build_adapters.py` · `python tools/validate.py` once more.
4. `python tools/package.py` (writes `CHECKSUMS.json` and the zip in `dist/`).
5. Delete working files that are not part of the release (for example a builder spec) and commit.
6. `git tag v20.x.y` and push the tag yourself.
