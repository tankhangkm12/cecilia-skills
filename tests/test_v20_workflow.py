"""V20 workflow engine (skills/cecilia-orchestrator/scripts/workflow.py): options -> choose -> brief, rules hash,
fix-loop round limit, module write-set check. Stdlib only; temp workspaces with a minimal config + registry."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "cecilia-orchestrator" / "scripts"))
import workflow as W  # noqa: E402

REGISTRY = {
    "version": "20.0.0",
    "agent_types": {"writer": {"name": "writer"}, "tester": {"name": "tester"}, "reviewer": {"name": "reviewer"}},
    "roles": {
        "cecilia-dev-be": {"name": "cecilia-dev-be", "agent_type": "writer", "model": "balanced",
                           "lane": ["src/**"], "report": "tensura/reports/<TASK>/dev-be.md"},
        "cecilia-dev-fe": {"name": "cecilia-dev-fe", "agent_type": "writer", "model": "balanced",
                           "lane": ["web/**"], "report": "tensura/reports/<TASK>/dev-fe.md"},
        "cecilia-test": {"name": "cecilia-test", "agent_type": "tester", "model": "balanced", "lenses": "test"},
        "cecilia-review": {"name": "cecilia-review", "agent_type": "reviewer", "model": "strongest",
                           "lenses": "review"},
    },
    "flows": {"personal": {"name": "personal", "guide": "shared/flows/personal.md"}},
    "lenses": {"test": {n: {"name": n, "kind": "test"} for n in ("functional", "integration", "security")},
               "review": {n: {"name": n, "kind": "review"} for n in ("correctness", "security", "data", "redteam")}},
}
OPTIONS = {"options": [
    {"id": "A", "split": "layer",
     "units": [{"id": "U1", "role": "cecilia-dev-be", "writes": ["src/order/**"]},
               {"id": "U2", "role": "cecilia-dev-fe", "writes": ["web/src/order/**"]}],
     "test_lenses": ["functional"], "review_lenses": ["correctness", "security", "data"]},
    {"id": "B", "split": "module",
     "units": [{"id": "U1", "role": "cecilia-dev-be", "writes": ["src/order/**"]},
               {"id": "U2", "role": "cecilia-dev-be", "writes": ["src/export/**"]},
               {"id": "U3", "role": "cecilia-dev-fe", "writes": ["web/src/order/**"]}],
     "test_lenses": ["functional", "integration", "security"], "review_lenses": ["correctness", "security", "data"]},
]}


class WorkflowV20(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)
        (self.ws / ".cecilia").mkdir()
        (self.ws / ".cecilia" / "config.json").write_text(json.dumps({
            "roles": {r: True for r in REGISTRY["roles"]}, "flow": "personal",
            "fix_loop": {"max_rounds": 3}}), encoding="utf-8")
        (self.ws / ".cecilia" / "registry.json").write_text(json.dumps(REGISTRY), encoding="utf-8")
        (self.ws / "rules" / "roles").mkdir(parents=True)
        (self.ws / "rules" / "_project.md").write_text("- PR-01: no console.log in src\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, data=None):
        if data is not None:
            p = self.ws / "opts.json"
            p.write_text(json.dumps(data), encoding="utf-8")
            args = args + ("--input", str(p))
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = W.main([args[0], "--workspace", str(self.ws), "--task", "SHOP-42", *args[1:]])
        return code, out.getvalue(), err.getvalue()

    def test_options_choose_brief_header_matches_workflow(self):
        code, out, err = self.run_cli("options", data=OPTIONS)
        self.assertEqual(code, 0, err)
        doc = json.loads((self.ws / "tensura/tasks/SHOP-42/options.json").read_text(encoding="utf-8"))
        b = next(o for o in doc["options"] if o["id"] == "B")
        # dev 3 + test 3 + review 3x2 + judge 1 = 13; fix: 2 + 2 + (2x2 + 1) = 9
        self.assertEqual(b["estimate"]["agent_runs"], 22)
        self.assertEqual(b["estimate"]["input_tokens"], 22 * 26500)
        self.assertEqual(b["estimate"]["label"], "[projected]")
        self.assertIn("| **B**", (self.ws / "tensura/tasks/SHOP-42/options.md").read_text(encoding="utf-8"))
        self.assertEqual(self.run_cli("choose", "--option", "B")[0], 0)
        wf = json.loads((self.ws / "tensura/tasks/SHOP-42/workflow.json").read_text(encoding="utf-8"))
        canon = json.dumps(wf["option"], sort_keys=True, separators=(",", ":"))
        self.assertEqual(wf["hash"], hashlib.sha256(canon.encode()).hexdigest()[:12])
        self.assertEqual((wf["chosen"], wf["mode"], wf["flow"]), ("B", "standard", "personal"))
        code, brief, err = self.run_cli("brief", "--role", "cecilia-dev-be", "--unit", "U2")
        self.assertEqual(code, 0, err)
        rh = W.rules_hash(self.ws, "cecilia-dev-be", "personal", None)
        self.assertEqual(brief.splitlines()[0], f"[cecilia-brief TASK=SHOP-42 ROLE=cecilia-dev-be LENS=- UNIT=U2 "
                                                f"WORKFLOW={wf['hash']} ROUND=0 RULES={rh}]")
        self.assertIn("src/export/**", brief)
        self.assertNotIn("{{", brief)

    def test_brief_embeds_rules_and_hash_follows_rules_files(self):
        self.run_cli("options", data=OPTIONS)
        self.run_cli("choose", "--option", "A")
        _, first, _ = self.run_cli("brief", "--role", "cecilia-test", "--lens", "security")
        self.assertIn("## Rules (must follow)", first)
        self.assertIn("PR-01: no console.log in src", first)
        (self.ws / "rules" / "roles" / "test.md").write_text("- PR-01: every BUG line has a repro\n", encoding="utf-8")
        _, second, _ = self.run_cli("brief", "--role", "cecilia-test", "--lens", "security")
        self.assertIn("every BUG line has a repro", second)
        h1, h2 = (b.splitlines()[0].rsplit("RULES=", 1)[1] for b in (first, second))
        self.assertNotEqual(h1, h2)
        self.assertIn(f"Rules: {h2.rstrip(']')}", second)

    def test_round_refuses_the_fourth(self):
        for n in (1, 2, 3):
            code, out, _ = self.run_cli("round")
            self.assertEqual((code, json.loads(out)["round"]), (0, n))
        code, _, err = self.run_cli("round")
        self.assertEqual(code, 3)
        self.assertIn("max_rounds=3", err)
        run = json.loads((self.ws / "tensura/tasks/SHOP-42/run.json").read_text(encoding="utf-8"))
        self.assertEqual(run["round"], 3)

    def test_options_reject_overlapping_module_write_sets(self):
        bad = json.loads(json.dumps(OPTIONS))
        bad["options"][1]["units"][1]["writes"] = ["src/**"]
        code, _, err = self.run_cli("options", data=bad)
        self.assertEqual(code, 2)
        self.assertIn("overlap", err)
        self.assertFalse((self.ws / "tensura/tasks/SHOP-42/options.json").exists())

    def test_merge_tests_dedupes_lens_bug_tables(self):
        rep = self.ws / "tensura/reports/SHOP-42"
        rep.mkdir(parents=True)
        head = "## Bugs (open at this SHA)\n| ID | Title | Severity | Repro | Evidence |\n|---|---|---|---|---|\n"
        (rep / "test-functional.md").write_text(
            head + "| BUG-functional-01 | Login fails with empty password | BLOCKER | t::a | out |\n"
                   "## Re-test (rounds 1-3 only)\n| BUG-functional-00 | VERIFIED | abc | ok |\n", encoding="utf-8")
        (rep / "test-security.md").write_text(
            head + "| BUG-security-01 | login FAILS with empty password! | BLOCKER | t::b | out |\n"
                   "| BUG-security-02 | SQL injection in search | BLOCKER | t::c | out |\n", encoding="utf-8")
        code, out, err = self.run_cli("merge-tests")
        self.assertEqual((code, json.loads(out)["bugs"]), (0, 2), err)
        summary = (rep / "test-summary.md").read_text(encoding="utf-8")
        self.assertIn("test-functional.md BUG-functional-01; test-security.md BUG-security-01", summary)
        self.assertNotIn("VERIFIED", summary)

    def test_writer_brief_needs_a_chosen_workflow(self):
        code, _, err = self.run_cli("brief", "--role", "cecilia-dev-be")
        self.assertEqual(code, 2)
        self.assertIn("workflow.py options", err)


if __name__ == "__main__":
    unittest.main()
