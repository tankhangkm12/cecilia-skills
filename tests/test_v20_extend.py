"""v20 cecilia-extend: tools/scaffold.py proposals validate against the registry; collisions, missing keys and
overwrites are refused.   python3 -m unittest tests.test_v20_extend"""
from __future__ import annotations

import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import scaffold as S  # noqa: E402


def run(*args) -> tuple:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = S.main(list(args))
    return code, out.getvalue() + err.getvalue()


def fill_todos(folder: Path) -> None:
    for p in folder.rglob("*"):
        if p.is_file() and p.suffix in {".md", ".json"}:
            text = p.read_text(encoding="utf-8").replace("TODO(extend)", "Filled")
            p.write_text(text, encoding="utf-8")


class ExtendScaffold(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cecilia-extend-"))
        self.ws = self.tmp / "shop.cecilia"
        (self.ws / ".cecilia").mkdir(parents=True)
        (self.ws / ".cecilia" / "config.json").write_text("{}", encoding="utf-8")
        self.ext = self.ws / "tensura" / "extensions"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_role_and_flow_proposals_validate(self):
        code, out = run("role", "Data Eng", "--workspace", str(self.ws), "--lane", "pipelines/**",
                        "--describe", "Builds data pipelines inside its lane")
        self.assertEqual(code, 0, out)
        prop = self.ext / "cecilia-data-eng"
        manifest = json.loads((prop / "registry/roles/cecilia-data-eng.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["lane"], ["pipelines/**"])
        self.assertIs(manifest["default_on"], True)
        self.assertEqual(manifest["rules_slot"], "rules/roles/data-eng.md")
        card = (prop / "skills/cecilia-data-eng/SKILL.md").read_text(encoding="utf-8")
        self.assertNotRegex(card, r"\{\{")
        self.assertLessEqual(len(card.encode("utf-8")), 5000)
        self.assertIn("**Read first:** `references/common/core-min.md`", card)
        self.assertTrue((prop / "rules/roles/data-eng.md").is_file())
        self.assertFalse((self.ws / ".cecilia" / "extensions").exists(), "scaffold must never write .cecilia/")

        code, out = run("flow", "release-train", "--workspace", str(self.ws), "--describe", "Weekly release train")
        self.assertEqual(code, 0, out)
        guide = (self.ext / "release-train/flows/release-train.md").read_text(encoding="utf-8")
        for step in ("intake", "plan", "approve", "dispatch", "review", "handoff", "finish"):
            self.assertRegex(guide, rf"(?m)^## {step}$")

        # --check is strict about TODO(extend); after filling, both proposals pass
        self.assertEqual(run("--check", str(self.ext / "release-train"))[0], 1)
        for name in ("cecilia-data-eng", "release-train"):
            fill_todos(self.ext / name)
            code, out = run("--check", str(self.ext / name))
            self.assertEqual(code, 0, out)

    def test_missing_key_and_collision_fail(self):
        self.assertEqual(run("lens", "a11y", "--kind", "test", "--workspace", str(self.ws))[0], 0)
        lens = self.ext / "a11y"
        fill_todos(lens)
        mf = lens / "registry/lenses/test/a11y.json"
        obj = json.loads(mf.read_text(encoding="utf-8"))
        del obj["when"]
        mf.write_text(json.dumps(obj), encoding="utf-8")
        code, out = run("--check", str(lens))
        self.assertEqual(code, 1)
        self.assertIn("missing key 'when'", out)

        # the scaffold refuses a core name up front ...
        code, out = run("role", "db", "--workspace", str(self.ws))
        self.assertEqual(code, 1)
        self.assertIn("already exists in the core registry", out)
        # ... and a hand-made proposal that reuses a core name fails the check
        code, _ = run("flow", "hotfix", "--workspace", str(self.ws))
        self.assertEqual(code, 0)
        hot = self.ext / "hotfix"
        fill_todos(hot)
        (hot / "registry/flows/hotfix.json").rename(hot / "registry/flows/team.json")
        mf = hot / "registry/flows/team.json"
        mf.write_text(re.sub(r'"name": "hotfix"', '"name": "team"', mf.read_text(encoding="utf-8")), encoding="utf-8")
        code, out = run("--check", str(hot))
        self.assertEqual(code, 1)
        self.assertIn("collides", out)

    def test_refuses_overwrite_without_force(self):
        args = ("flow", "hotfix", "--workspace", str(self.ws))
        self.assertEqual(run(*args)[0], 0)
        guide = self.ext / "hotfix/flows/hotfix.md"
        guide.write_text(guide.read_text(encoding="utf-8") + "\nCecilia's edit\n", encoding="utf-8")
        code, out = run(*args)
        self.assertEqual(code, 1)
        self.assertIn("refusing to overwrite", out)
        self.assertIn("Cecilia's edit", guide.read_text(encoding="utf-8"))
        self.assertEqual(run(*args, "--force")[0], 0)
        self.assertNotIn("Cecilia's edit", guide.read_text(encoding="utf-8"))

    def test_never_writes_control_paths(self):
        code, out = run("flow", "x", "--out", str(self.ws / ".cecilia" / "extensions" / "x"))
        self.assertEqual(code, 1)
        self.assertIn("never writes under .cecilia", out)

    def test_repo_target_on_a_copy(self):
        repo = self.tmp / "repo"
        for d in ("registry", "skills", "shared"):
            shutil.copytree(ROOT / d, repo / d, ignore=shutil.ignore_patterns("__pycache__"))
        code, out = run("role", "mobile", "--target", "repo", "--out", str(repo), "--lane", "mobile/**",
                        "--describe", "Implements the mobile app inside its lane")
        self.assertEqual(code, 0, out)
        self.assertTrue((repo / "skills/cecilia-mobile/references/review-guide.md").is_file())
        self.assertTrue((repo / "registry/roles/cecilia-mobile.json").is_file())


if __name__ == "__main__":
    unittest.main()
