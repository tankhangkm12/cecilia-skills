"""v20 validate.py checks (stale commands, versions, rule-ledger patches, doc paths) and the v20 eval grader."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "evals"))
import validate as V  # noqa: E402
import run_evals as E  # noqa: E402


def write(root: Path, rel: str, text: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


class Base(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="cecilia-v20-validate-"))
        self.addCleanup(shutil.rmtree, self.root, True)


class StaleCommands(Base):
    def test_planted_script_name_is_caught_and_legacy_line_is_allowed(self):
        write(self.root, "skills/cecilia-x/SKILL.md", "# x (v20)\nRun `python .cecilia/bin/cecilia_mode.py controlled`.\n")
        write(self.root, "shared/git.md", "legacy: in-project layout used `cecilia_approve.py`.\nUse `cecilia approve`.\n")
        write(self.root, "skills/cecilia-x/references/common/git.md", "copy with cecilia_mode.py\n")
        found = V.stale_commands(self.root)
        self.assertEqual(len(found), 1, found)
        self.assertIn("skills/cecilia-x/SKILL.md:2", found[0])
        self.assertIn("cecilia_mode.py", found[0])

    def test_repo_is_clean_or_reports_only_real_lines(self):
        for line in V.stale_commands(ROOT):
            self.assertRegex(line, r"^(skills|shared)/.+:\d+: stale command")


class Versions(Base):
    def make(self, v="20.0.0", guard="20.0.0"):
        write(self.root, "tools/roster.py", f'VERSION = "{v}"\n')
        write(self.root, "tools/registry.py", f'VERSION = "{v}"\n')
        write(self.root, "pyproject.toml", f'[project]\nname = "cecilia"\nversion = "{v}"\n')
        write(self.root, "src/cecilia/__init__.py", f'__version__ = "{v}"\n')
        write(self.root, "guard/cecilia_guard.py", f'VERSION = "{guard}"\n')
        write(self.root, "guard/policy.json", json.dumps({"version": v}))
        write(self.root, "shared/scripts/cecilia_check.py", f'VERSION = "{v}"\n')
        write(self.root, "README.md", f"# Cecilia v{v.split('.')[0]} — x\n\nBản {v} · 2026-09-28\n")
        write(self.root, "CHANGELOG.md", f"# Changelog\n\n## v{v} — 2026-09-28 · x\n")
        write(self.root, "docs/INSTALL.md", f"uv tool install git+https://github.com/<you>/cecilia-skills@v{v}\n")

    def test_all_equal_passes(self):
        self.make()
        self.assertEqual(V.version_mismatches(self.root), [])

    def test_mismatch_is_reported(self):
        self.make(guard="19.2.0")
        found = V.version_mismatches(self.root)
        self.assertEqual(len(found), 1, found)
        self.assertIn("guard/cecilia_guard.py VERSION is 19.2.0", found[0])

    def test_missing_source_is_reported(self):
        self.make()
        (self.root / "docs/INSTALL.md").unlink()
        self.assertTrue(any("docs/INSTALL.md" in e and "not found" in e for e in V.version_mismatches(self.root)))


class RulePatches(Base):
    def make(self):
        write(self.root, "tools/rules.json", json.dumps({"rules": [
            {"id": "R001", "rule": "old", "file": "shared/a.md", "must_contain": ["old phrase"]},
            {"id": "R002", "rule": "kept", "file": "shared/a.md", "must_contain": ["kept phrase"]}]}))
        write(self.root, "shared/a.md", "kept phrase and new phrase\n")

    def test_without_patch_the_rephrased_rule_fails(self):
        self.make()
        problems, _ = V.ledger_problems(self.root)
        self.assertTrue(any("R001" in p and "old phrase" in p for p in problems), problems)

    def test_patch_overlays_by_id_and_adds_new_rules(self):
        self.make()
        write(self.root, "tools/rules-patch-A8.json", json.dumps([
            {"id": "R001", "file": "shared/a.md", "phrase": "new phrase", "note": "rephrased"},
            {"id": "R280", "file": "shared/b.md", "phrase": "brand new", "note": "new rule"}]))
        write(self.root, "shared/b.md", "a brand new rule\n")
        problems, summary = V.ledger_problems(self.root)
        self.assertEqual(problems, [])
        self.assertIn("3/3 kept", summary)
        (self.root / "shared/b.md").write_text("gone\n", encoding="utf-8")
        problems, _ = V.ledger_problems(self.root)
        self.assertTrue(any("R280" in p and "rules-patch-A8.json" in p for p in problems), problems)


class RepoPaths(Base):
    def test_missing_doc_and_tool_paths_are_reported(self):
        write(self.root, "docs/A.md", "See `docs/B.md`, `tools/gone.py` and `<ws>/tools/x.py`, `tools/rules-patch-*.json`.\n")
        write(self.root, "docs/B.md", "ok\n")
        write(self.root, "tools/t.py", '"""Gate: docs/RELEASE.md."""\n')
        found = V.repo_paths(self.root)
        self.assertEqual(len(found), 2, found)
        self.assertTrue(any("tools/gone.py" in f for f in found))
        self.assertTrue(any("tools/t.py" in f and "docs/RELEASE.md" in f for f in found))


class EvalGrader(Base):
    def test_v20_expectations(self):
        work = self.root / "evalshop"
        ws = self.root / "evalshop.cecilia"
        write(ws, ".cecilia/config.json", json.dumps({"lanes": {"cecilia-dev-fe": ["web/**", "!**/*.test.*"]}}))
        write(ws, "tensura/tasks/T/workflow.json", json.dumps({"chosen": "B", "hash": "abcdef123456"}))
        write(ws, "tensura/tasks/T/options.json", json.dumps({"options": [{"id": "A"}, {"id": "B"}]}))
        work.mkdir()
        hdr = "[cecilia-brief TASK=T ROLE=cecilia-dev-fe LENS=- UNIT=u1 WORKFLOW=abcdef123456 ROUND=0 RULES=0]\n…"
        res = {"text": "", "tools": [
            {"name": "Write", "input": {"file_path": "tensura/tasks/T/state.md"}, "id": "1", "parent": None, "ok": True},
            {"name": "Agent", "input": {"subagent_type": "cecilia-dev-fe", "prompt": hdr}, "id": "2", "parent": None, "ok": True},
            {"name": "Edit", "input": {"file_path": str(work / "web/a.js")}, "id": "3", "parent": "2", "ok": True},
            {"name": "Edit", "input": {"file_path": str(work / "app/b.py")}, "id": "4", "parent": "2", "ok": False}]}
        exp = {"main_writes_only_under": "tensura/", "dispatched_any": ["cecilia-dev-fe"], "lanes_respected": True,
               "dispatch_has_workflow": ["cecilia-dev-fe"], "transcript_agent_count": {"cecilia-dev-fe": 1},
               "json_field": [{"glob": "tensura/tasks/*/options.json", "field": "options", "min_len": 2}]}
        self.assertEqual(E.grade_v20(exp, work, res), [])
        res["tools"][3]["ok"] = True                         # the out-of-lane write went through
        res["tools"].append({"name": "Edit", "input": {"file_path": str(work / "app/c.py")}, "id": "5",
                             "parent": None, "ok": True})    # the orchestrator wrote the project
        fails = E.grade_v20(exp, work, res)
        self.assertTrue(any("outside its lane" in f for f in fails), fails)
        self.assertTrue(any("main thread wrote app/c.py" in f for f in fails), fails)


if __name__ == "__main__":
    unittest.main()
