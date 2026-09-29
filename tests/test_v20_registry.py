"""v20 registry: loads and validates, roster compatibility, config defaults and migration, extensions."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import registry as REG  # noqa: E402
import roster as R  # noqa: E402

PY = sys.executable
# Files other builders write in parallel; their absence is expected until they land.
PENDING = ("skills/cecilia-extend/SKILL.md", "shared/flows/", "skills/cecilia-test/references/lenses/",
           "skills/cecilia-review/references/panel.md")


def real_errors(errs):
    return [e for e in errs if not any(p in e for p in PENDING)]


class Registry(unittest.TestCase):
    def test_loads_and_validates(self):
        reg = REG.load()
        self.assertEqual(len(reg["roles"]), 13)
        self.assertEqual(set(reg["agent_types"]), {"orchestrator", "writer", "tester", "reviewer"})
        self.assertEqual(set(reg["flows"]), {"personal", "team"})
        self.assertEqual(len(reg["lenses"]["test"]), 7)
        self.assertEqual(len(reg["lenses"]["review"]), 10)
        self.assertEqual(real_errors(REG.validate(reg)), [])
        snap = REG.compile(reg)
        self.assertEqual(snap["version"], "20.2.0")
        self.assertEqual(snap["roles"]["cecilia-dev-be"]["writes"], "lane")
        self.assertNotIn("_source", json.dumps(snap))
        self.assertEqual(REG.short("cecilia-dev-be"), "dev-be")
        self.assertEqual(REG.default_lanes(reg)["cecilia-extend"], ["tensura/extensions/**"])
        self.assertEqual(REG.default_lanes(reg)["cecilia-review"], [])

    def test_schema_errors_are_reported(self):
        reg = REG.load()
        reg["roles"]["cecilia-db"]["agent_type"] = "wizard"
        reg["roles"]["cecilia-db"]["lane"] = ["ok/**", 3]
        del reg["flows"]["team"]["steps"][-1]
        errs = REG.validate(reg)
        self.assertTrue(any("unknown agent_type 'wizard'" in e for e in errs), errs)
        self.assertTrue(any("lane globs" in e for e in errs), errs)
        self.assertTrue(any("flows/team" in e and "finish" in e for e in errs), errs)

    def test_extension_merges_and_collision_is_an_error(self):
        ext = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, ext, True)
        role = json.loads((ROOT / "registry/roles/cecilia-extend.json").read_text(encoding="utf-8"))
        (ext / "registry/roles").mkdir(parents=True)
        for name in ("cecilia-mobile", "cecilia-db"):          # a new role, and one that collides with core
            obj = dict(role, name=name, rules_slot=f"rules/roles/{REG.short(name)}.md")
            (ext / f"registry/roles/{name}.json").write_text(json.dumps(obj), encoding="utf-8")
        (ext / "skills/cecilia-mobile").mkdir(parents=True)
        (ext / "skills/cecilia-mobile/SKILL.md").write_text("# mobile\n", encoding="utf-8")
        reg = REG.load(extensions=ext)
        self.assertIn("cecilia-mobile", reg["roles"])
        self.assertEqual(reg["roles"]["cecilia-db"]["agent_type"], "writer")   # core wins
        errs = real_errors(REG.validate(reg))
        self.assertEqual(len(errs), 1, errs)
        self.assertIn("collides with the core registry", errs[0])
        self.assertIn("cecilia-mobile", REG.compile(reg)["extensions"])
        r = subprocess.run([PY, str(ROOT / "tools/registry.py"), "--check", "--extensions", str(ext)],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 1)
        self.assertIn("collides", r.stdout)


class RosterCompat(unittest.TestCase):
    def test_public_names(self):
        self.assertEqual(R.VERSION, "20.2.0")
        self.assertNotIn(R.ORCHESTRATOR, R.ROLES)
        self.assertEqual(R.ROLES["cecilia-extend"][0], "docs")
        self.assertEqual(R.DEFAULT_OFF, {"cecilia-ui"})
        self.assertEqual(len(R.all_names()), 13)
        self.assertEqual(R.DEFAULT_MODELS["cecilia-dev-be"], "balanced")
        self.assertIn("never", R.ORCH_DESC.lower())
        self.assertIn("playwright-cli", R.UI_BROWSERS)
        self.assertIn("default_profiles", R.policy())

    def test_default_config_has_v20_keys(self):
        cfg = R.default_config()
        for key in R.V20_KEYS:
            self.assertIn(key, cfg)
        self.assertEqual(cfg["flow"], "personal")
        self.assertEqual(cfg["flows"]["team"]["max_pr_lines"], 400)
        self.assertNotIn("max_writers", cfg["parallel"])
        self.assertEqual(cfg["parallel"]["limits"], {"dev": None, "test": None, "review": None})
        self.assertEqual(cfg["test"]["lenses"], ["functional", "integration", "concurrency-perf", "security", "ui",
                                                 "database", "infra"])
        self.assertEqual(set(cfg["lanes"]), set(R.all_names()))
        self.assertEqual(cfg["fix_loop"]["max_rounds"], 3)
        self.assertTrue(cfg["roles"]["cecilia-extend"])

    def test_migrate_keeps_user_values(self):
        old = {"roles": {"cecilia-ui": True}, "parallel": {"max_writers": 5, "wave_checkin": "ask"},
               "review": {"panel": {"reviewers": 4, "auto_in": ["controlled"]}},
               "lanes": {"cecilia-dev-be": ["api/**"]}, "models": {"cecilia-db": "fast"}}
        new, changes = R.migrate_config(old)
        self.assertEqual(new["parallel"]["max_writers"], 5)
        self.assertEqual(new["parallel"]["wave_checkin"], "ask")
        self.assertIn("limits", new["parallel"])
        self.assertEqual(new["review"]["panel"]["reviewers"], 4)
        self.assertEqual(new["lanes"]["cecilia-dev-be"], ["api/**"])
        self.assertIn("cecilia-extend", new["lanes"])
        self.assertEqual(new["models"]["cecilia-db"], "fast")
        self.assertTrue(new["roles"]["cecilia-ui"])
        self.assertTrue(new["roles"]["cecilia-extend"])
        self.assertEqual(new["flow"], "personal")
        self.assertIn("fix_loop", [c[0] for c in changes])
        again, changes2 = R.migrate_config(new)
        self.assertEqual((again, changes2), (new, []))


class Adapters(unittest.TestCase):
    def test_generated_files_are_current(self):
        r = subprocess.run([PY, str(ROOT / "tools/build_adapters.py"), "--check"], capture_output=True, text=True,
                           encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_orchestrator_is_main_thread_and_dispatches_every_role(self):
        settings = json.loads((ROOT / "adapters/claude-code/settings.cecilia.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["agent"], "cecilia-orchestrator")
        self.assertIn("Agent|Task", settings["hooks"]["PreToolUse"][0]["matcher"])
        orch = (ROOT / "adapters/claude-code/agents/cecilia-orchestrator.md").read_text(encoding="utf-8")
        for name in R.ROLES:
            self.assertIn(name, orch.split("\n")[3])
        ag = (ROOT / "adapters/antigravity/agents/cecilia-orchestrator/agent.md").read_text(encoding="utf-8")
        self.assertIn("mainAgent: true", ag)
        for name in ("roster.md", "lenses.md", "flows.md"):
            self.assertTrue((ROOT / "shared/generated" / name).is_file(), name)


if __name__ == "__main__":
    unittest.main()
