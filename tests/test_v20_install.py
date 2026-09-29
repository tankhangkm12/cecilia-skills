"""v20 install / CLI / rules / self-check: workspace init writes rules/ + registry.json + the orchestrator guide,
upgrade keeps Cecilia's rules, `rules lint` refuses duplicates and loosening, cecilia_check verifies the Rules hash.
    python3 -m unittest tests.test_v20_install -v"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import workspace_tools as W  # noqa: E402

PY = sys.executable
HAS_GIT = shutil.which("git") is not None
ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")


def git(root: Path, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, env=ENV)


def install(project: Path, *extra) -> subprocess.CompletedProcess:
    return subprocess.run([PY, str(ROOT / "tools/install.py"), "--project", str(project), "--workspace", "--host",
                           "claude", "--host", "antigravity", "--hook-form", "exec", "--apply", *extra],
                          capture_output=True, text=True)


@unittest.skipUnless(HAS_GIT, "git needed")
class WorkspaceInitV20(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = Path(tempfile.mkdtemp()).resolve()
        cls.P, cls.W = base / "shop", base / "shop.cecilia"
        (cls.P / "src").mkdir(parents=True)
        (cls.P / "src" / "a.py").write_text("x = 1\n")
        git(cls.P, "init", "-q", "-b", "main")
        git(cls.P, "add", "-A")
        git(cls.P, "commit", "-qm", "init")
        r = install(cls.P)
        assert r.returncode == 0, r.stdout[-800:] + r.stderr[-800:]

    def test_init_creates_rules_registry_and_orchestrator_guide(self):
        for rel in ("rules/_project.md", "rules/roles/dev-be.md", "rules/roles/test.md", "rules/flows/personal.md",
                    "rules/flows/team.md"):
            self.assertTrue((self.W / rel).is_file(), rel)
        self.assertEqual(W.lint_workspace(self.W), [])
        reg = json.loads((self.W / ".cecilia/registry.json").read_text())
        self.assertIn("cecilia-dev-be", reg["roles"])
        self.assertIn("team", reg["flows"])
        guide = (self.W / "CLAUDE.md").read_text()
        for phrase in ("cecilia-orchestrator", "Never do specialist work yourself", "workflow.py brief",
                       "rules/_project.md", "Current flow:** `personal`", str(self.P), "local-only"):
            self.assertIn(phrase, guide)
        self.assertIn("Cecilia chooses", (self.W / "AGENTS.md").read_text())
        self.assertEqual(json.loads((self.W / ".claude/settings.json").read_text()).get("agent"), "cecilia-orchestrator")
        cfg = json.loads((self.W / ".cecilia/config.json").read_text())
        self.assertEqual(cfg.get("flow"), "personal")
        self.assertEqual(sorted(p.name for p in self.P.iterdir()), [".git", "src"])      # project untouched

    def test_upgrade_keeps_edited_rules_and_adds_missing(self):
        mine = self.W / "rules/roles/dev-be.md"
        mine.write_text(mine.read_text() + "\n- PR-01: Money is integer cents\n")
        edited = mine.read_text()
        (self.W / "rules/flows/team.md").unlink()
        r = install(self.P, "--upgrade")
        self.assertEqual(r.returncode, 0, r.stderr[-800:])
        self.assertEqual(mine.read_text(), edited)
        self.assertTrue((self.W / "rules/flows/team.md").is_file())

    def test_flow_switch_needs_a_terminal(self):
        r = subprocess.run([PY, str(ROOT / "tools/workspace_tools.py"), "flow", "--workspace", str(self.W),
                            "--project", str(self.P), "--", "team"], capture_output=True, text=True, stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(json.loads((self.W / ".cecilia/config.json").read_text())["flow"], "personal")


class RulesLint(unittest.TestCase):
    def test_duplicate_id_and_loosening(self):
        text = W.rules_template("role", "cecilia-dev-be") + (
            "\n- PR-01: Money is integer cents\n- PR-01: Log no request bodies\n"
            "- PR-02: Agents may push to feature branches\n- PR-03: Never deploy to production\n")
        errs = W.lint_text("rules/roles/dev-be.md", text)
        self.assertTrue(any("duplicate id PR-01" in e for e in errs), errs)
        self.assertTrue(any("PR-02 loosens" in e for e in errs), errs)
        self.assertFalse(any("PR-03" in e for e in errs), errs)

    def test_check_block_and_size(self):
        ok = "- PR-01: No console.log\n\n```cecilia-check\n[{\"id\": \"PR-01\", \"forbid_regex\": \"console\\\\.log\\\\(\"}]\n```\n"
        self.assertEqual(W.lint_text("r.md", ok), [])
        bad = ok.replace('"PR-01", "forbid', '"PR-09", "forbid')
        self.assertTrue(W.lint_text("r.md", bad))
        self.assertTrue(any("bytes" in e for e in W.lint_text("r.md", ok + "x" * 3000)))

    def test_cli_lint_exit_code(self):
        ws = Path(tempfile.mkdtemp()).resolve()
        (ws / "rules").mkdir()
        (ws / "rules/_project.md").write_text("- PR-01: a\n- PR-01: b\n")
        r = subprocess.run([PY, str(ROOT / "tools/workspace_tools.py"), "rules", "--workspace", str(ws), "--project",
                            str(ws), "--", "lint"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("duplicate id PR-01", r.stdout)


@unittest.skipUnless(HAS_GIT, "git needed")
class RulesHashSelfCheck(unittest.TestCase):
    CHECK = str(ROOT / "shared/scripts/cecilia_check.py")

    def test_wrong_rules_hash_fails_right_hash_passes(self):
        base = Path(tempfile.mkdtemp()).resolve()
        proj, ws = base / "p", base / "p.cecilia"
        proj.mkdir()
        git(proj, "init", "-q", "-b", "main")
        git(proj, "commit", "-q", "--allow-empty", "-m", "init")
        (ws / ".cecilia").mkdir(parents=True)
        (ws / ".cecilia/config.json").write_text(json.dumps({"workspace": {"project": str(proj)}, "flow": "personal"}))
        (ws / "rules/roles").mkdir(parents=True)
        (ws / "rules/_project.md").write_text("- PR-01: Money is integer cents\n")
        (ws / "rules/roles/dev-be.md").write_text("- PR-02: Repositories return domain objects\n")
        report = ws / "tensura/reports/T-7/dev-be.md"
        report.parent.mkdir(parents=True)

        def run() -> dict:
            subprocess.run([PY, self.CHECK, "--task", "T-7", "--steps", "rules", "--offline"], cwd=ws,
                           capture_output=True, text=True, timeout=120)
            ev = json.loads((ws / "tensura/reports/T-7/evidence.json").read_text())
            return {s["step"]: s for s in ev["steps"]}["rules"]

        report.write_text("STATUS: DONE\nRules: 0123456789ab (PR-01, PR-02)\n")
        st = run()
        self.assertEqual(st["status"], "fail", st)
        good = W.rules_hash(ws, "cecilia-dev-be", "personal", None)
        report.write_text(f"STATUS: DONE\nRules: {good} (PR-01, PR-02)\n")
        self.assertEqual(run()["status"], "pass")


if __name__ == "__main__":
    unittest.main()
