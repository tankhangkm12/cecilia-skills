"""Cecilia 20.2 host (Antigravity-first): generated hooks.json (MCP + dispatch matcher, PreInvocation), installer
render and upgrade recognition, agent models/tools from the registry, workspace model overrides, doctor coverage /
agy version / global leftovers / MCP names, `cecilia open --agy`.
    python3 -m unittest tests.test_v22_host -q"""
import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "guard"))
sys.path.insert(0, str(ROOT / "src"))
import build_adapters as B  # noqa: E402
import install  # noqa: E402
import cecilia_doctor as D  # noqa: E402
from cecilia import cli  # noqa: E402

OLD_MATCHER = "run_command|write_to_file|replace_file_content|multi_replace_file_content"


def tmpdir() -> Path:
    return Path(tempfile.mkdtemp()).resolve()


def old_hooks(command: str) -> dict:
    """The 19.x-20.1 Antigravity hooks.json shape."""
    return {"cecilia-guard": {"PreToolUse": [{"matcher": OLD_MATCHER, "hooks": [
        {"type": "command", "command": command, "timeout": 30}]}]}}


def handlers(data: dict) -> list:
    return [h for entries in data["cecilia-guard"].values() for e in entries for h in e["hooks"]]


def agent_md(name: str) -> str:
    return (ROOT / f"adapters/antigravity/agents/{name}/agent.md").read_text(encoding="utf-8")


def frontmatter_tools(text: str) -> list:
    head = text.split("\n---", 1)[0]
    m = re.search(r"^tools:\n((?:  - .*\n)+)", head + "\n", re.M)
    return [ln.strip()[2:] for ln in m.group(1).splitlines()] if m else []


class GeneratedHooks(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / "adapters/antigravity/hooks.json").read_text(encoding="utf-8"))

    def test_generated_file_is_current(self):
        files = B.antigravity_files(B.registry())
        self.assertEqual(files["adapters/antigravity/hooks.json"],
                         (ROOT / "adapters/antigravity/hooks.json").read_text(encoding="utf-8"))

    def test_matcher_covers_mcp_and_dispatch(self):
        pre = self.data["cecilia-guard"]["PreToolUse"]
        self.assertEqual(len(pre), 1)
        matcher = pre[0]["matcher"]
        self.assertNotEqual(matcher, "*")
        for tool in ("run_command", "write_to_file", "replace_file_content", "multi_replace_file_content",
                     "call_mcp_tool", "invoke_subagent", "define_subagent"):
            self.assertIsNotNone(re.fullmatch(f"(?:{matcher})", tool), tool)
        for tool in ("view_file", "list_dir", "grep_search"):
            self.assertIsNone(re.fullmatch(f"(?:{matcher})", tool), tool)

    def test_pre_invocation_same_guard_no_stop(self):
        g = self.data["cecilia-guard"]
        self.assertIn("PreInvocation", g)
        self.assertNotIn("Stop", g)
        self.assertNotIn("matcher", g["PreInvocation"][0])
        self.assertEqual({h["command"] for h in handlers(self.data)}, {"__CECILIA_GUARD_COMMAND__"})
        self.assertFalse(D.antigravity_coverage_problems(
            json.loads(json.dumps(self.data).replace("__CECILIA_GUARD_COMMAND__", "python3 /x/cecilia_guard.py"))))


class InstallRender(unittest.TestCase):
    def test_posix_every_handler_filled(self):
        guard = Path("/w/shop.cecilia/.cecilia/bin/cecilia_guard.py")
        data = json.loads(install.render_antigravity_hooks(guard, Path("/w/shop.cecilia"), windows=False,
                                                           python="python3"))
        cmds = {h["command"] for h in handlers(data)}
        self.assertEqual(cmds, {"python3 /w/shop.cecilia/.cecilia/bin/cecilia_guard.py --host antigravity "
                                "--workspace /w/shop.cecilia"})
        self.assertIn("PreInvocation", data["cecilia-guard"])

    def test_windows_inline_and_launcher(self):
        guard = Path("D:/w/shop.cecilia/.cecilia/bin/cecilia_guard.py")
        data = json.loads(install.render_antigravity_hooks(guard, Path("D:/w/shop.cecilia"), windows=True,
                                                           python="python"))
        cmds = {h["command"] for h in handlers(data)}
        self.assertEqual(len(cmds), 1)
        cmd = cmds.pop()
        self.assertNotIn('"', cmd)
        self.assertTrue(cmd.startswith("python D:\\w\\shop.cecilia\\.cecilia\\bin\\cecilia_guard.py"), cmd)
        base = tmpdir()
        guard = base / "My Work" / "shop.cecilia" / ".cecilia" / "bin" / "cecilia_guard.py"
        plan = install.Plan(base / "My Work" / "shop.cecilia", "t")
        data = json.loads(install.render_antigravity_hooks(guard, guard.parents[2], plan=plan, windows=True,
                                                           python="python"))
        cmds = {h["command"] for h in handlers(data)}
        self.assertEqual(len(cmds), 1)
        self.assertTrue(cmds.pop().endswith(install.AG_LAUNCHER))
        self.assertTrue(any(str(d).endswith(install.AG_LAUNCHER) for d, _ in plan.create))


class Recognition(unittest.TestCase):
    def setUp(self):
        self.d = tmpdir()
        self.guard = self.d / ".cecilia/bin/cecilia_guard.py"
        self.new = install.render_antigravity_hooks(self.guard, windows=False, python="python3")
        self.f = self.d / "hooks.json"

    def check(self, data) -> bool:
        self.f.write_text(json.dumps(data))
        return install.only_cecilia_settings(self.f, self.new)

    def test_old_and_new_shapes(self):
        for cmd in (f"python3 {self.guard.as_posix()} --host antigravity",
                    r"D:\w\k8s.cecilia\.cecilia\bin\cecilia_guard_antigravity.cmd",
                    f'"C:/Py/python.exe" "{self.guard.as_posix()}" --host antigravity --workspace "D:/w"'):
            self.assertTrue(self.check(old_hooks(cmd)), cmd)
        self.assertTrue(self.check(json.loads(self.new)))

    def test_customised_is_not_replaced(self):
        data = json.loads(self.new)
        data["cecilia-guard"]["PreToolUse"][0]["matcher"] = "*"
        self.assertFalse(self.check(data))
        data = json.loads(self.new)
        data["cecilia-guard"]["Stop"] = [{"hooks": [{"type": "command", "command": "notify"}]}]
        self.assertFalse(self.check(data))
        data = json.loads(self.new)
        data["cecilia-guard"]["PreToolUse"][0]["hooks"].append({"type": "command", "command": "mine"})
        self.assertFalse(self.check(data))
        data = json.loads(self.new)
        data["mine"] = {}
        self.assertFalse(self.check(data))

    def test_upgrade_replaces_20_1_hooks(self):
        base = tmpdir()
        proj, ws = base / "shop", base / "shop.cecilia"
        proj.mkdir()
        install.choose_hook_form("exec")
        install.apply(install.build_workspace(proj, ws, {"antigravity"}, python="python3"))
        hooks = ws / ".agents/hooks.json"
        hooks.write_text(json.dumps(old_hooks(f"python3 {(ws / '.cecilia/bin/cecilia_guard.py').as_posix()} "
                                              "--host antigravity")))
        plan = install.build_workspace(proj, ws, {"antigravity"}, upgrade=True, python="python3")
        self.assertIn(hooks, [d for d, _ in plan.replace])
        install.apply(plan)
        data = json.loads(hooks.read_text())
        self.assertIn("PreInvocation", data["cecilia-guard"])
        self.assertIn("call_mcp_tool", data["cecilia-guard"]["PreToolUse"][0]["matcher"])


class AgentFiles(unittest.TestCase):
    def test_models(self):
        for name in ("cecilia-orchestrator", "cecilia-plan", "cecilia-review"):
            self.assertRegex(agent_md(name), r"(?m)^model: pro$", name)
        for name in ("cecilia-dev-be", "cecilia-devops", "cecilia-api-ux", "cecilia-ui", "cecilia-test"):
            self.assertRegex(agent_md(name), r"(?m)^model: inherit$", name)

    def test_tools(self):
        orch = frontmatter_tools(agent_md("cecilia-orchestrator"))
        for t in ("invoke_subagent", "manage_subagents", "send_message"):
            self.assertIn(t, orch)
        for t in ("call_mcp_tool", "define_subagent"):
            self.assertNotIn(t, orch)
        for name in ("devops", "discovery", "db", "test", "dev-be", "dev-fe"):
            self.assertIn("call_mcp_tool", frontmatter_tools(agent_md(f"cecilia-{name}")), name)
        for name in ("plan", "review", "design", "extend", "api-ux", "ui"):
            self.assertNotIn("call_mcp_tool", frontmatter_tools(agent_md(f"cecilia-{name}")), name)

    def test_with_agent_model(self):
        text = agent_md("cecilia-dev-be")
        out = install.with_agent_model(text, "flash")
        self.assertRegex(out, r"(?m)^model: flash$")
        self.assertNotRegex(out, r"(?m)^model: inherit$")
        self.assertEqual(out.count("\n"), text.count("\n"))
        self.assertIn("model: pro\n---", install.with_agent_model("---\nname: x\n---\nbody model: y\n", "pro"))

    def test_config_override(self):
        base = tmpdir()
        proj, ws = base / "shop", base / "shop.cecilia"
        proj.mkdir()
        install.choose_hook_form("exec")
        install.apply(install.build_workspace(proj, ws, {"antigravity"}, python="python3"))
        cfg_file = ws / ".cecilia/config.json"
        cfg = json.loads(cfg_file.read_text())
        cfg["antigravity"] = dict(cfg.get("antigravity") or {},
                                  models={"dev-be": "flash", "cecilia-plan": "inherit", "review": "bad value"})
        cfg_file.write_text(json.dumps(cfg))
        plan = install.build_workspace(proj, ws, {"antigravity"}, upgrade=True, python="python3")
        replaced = {d: s for d, s in plan.replace}
        be = replaced[ws / ".agents/agents/cecilia-dev-be/agent.md"]
        self.assertRegex(be, r"(?m)^model: flash$")
        self.assertRegex(replaced[ws / ".agents/agents/cecilia-plan/agent.md"], r"(?m)^model: inherit$")
        self.assertNotIn(ws / ".agents/agents/cecilia-review/agent.md", replaced)
        self.assertTrue(any("antigravity.models.review" in n for n in plan.notes))


class Doctor(unittest.TestCase):
    def setUp(self):
        D.RESULTS.clear()
        self.home = tmpdir()
        self.env = mock.patch.dict(os.environ, {"HOME": str(self.home), "USERPROFILE": str(self.home)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        D.RESULTS.clear()

    def results(self, check):
        return [r for r in D.RESULTS if r["check"] == check]

    def test_old_hooks_fail_coverage(self):
        root = tmpdir()
        (root / ".agents").mkdir()
        (root / ".agents/hooks.json").write_text(json.dumps(old_hooks("python3 /nope/cecilia_guard.py --host antigravity")))
        D.check_antigravity_hook(root)
        cov = self.results("antigravity coverage")
        self.assertEqual(cov[0]["status"], "FAIL")
        self.assertIn("call_mcp_tool", cov[0]["detail"])
        self.assertIn("PreInvocation", cov[0]["detail"])
        self.assertIn("cecilia upgrade", cov[0]["fix"])

    def test_new_hooks_pass_coverage(self):
        data = json.loads(install.render_antigravity_hooks(Path("/x/cecilia_guard.py"), windows=False, python="python3"))
        D.check_antigravity_coverage(data)
        self.assertEqual(self.results("antigravity coverage")[0]["status"], "OK")
        D.RESULTS.clear()
        D.check_antigravity_coverage({"cecilia-guard": "garbage"})     # odd file: reported, never raises
        self.assertEqual(self.results("antigravity coverage")[0]["status"], "FAIL")

    def test_version_helpers(self):
        self.assertEqual(D.parse_agy_version("agy version 1.2.12 (abc)"), (1, 2, 12))
        self.assertIsNone(D.parse_agy_version("no version"))
        self.assertTrue(D.version_at_least((1, 2, 12)))
        self.assertTrue(D.version_at_least((1, 2, 7)))
        self.assertFalse(D.version_at_least((1, 2, 6)))
        self.assertFalse(D.version_at_least(None))

    def test_agy_version_check(self):
        run = mock.Mock(return_value=mock.Mock(stdout="1.2.5\n", stderr=""))
        with mock.patch.object(D, "find_agy", return_value="/bin/agy"), mock.patch.object(D.subprocess, "run", run):
            D.check_agy_version()
        self.assertEqual(self.results("agy version")[0]["status"], "WARN")
        self.assertEqual(run.call_args[0][0], ["/bin/agy", "--version"])
        self.assertEqual(run.call_args[1]["timeout"], 5.0)
        D.RESULTS.clear()
        with mock.patch.object(D, "find_agy", return_value=None):
            D.check_agy_version()
        self.assertEqual(self.results("agy version")[0]["status"], "INFO")

    def test_global_leftovers(self):
        cfg = self.home / ".gemini/config"
        (cfg / "agents/cecilia-orchestrator").mkdir(parents=True)
        (cfg / "hooks.json").write_text(json.dumps(old_hooks(f"python3 {(self.home / 'gone/cecilia_guard.py').as_posix()}")))
        D.check_antigravity_global()
        r = self.results("agy global")[0]
        self.assertEqual(r["status"], "WARN")
        self.assertIn("cecilia-orchestrator", r["detail"])
        self.assertIn("hooks.json", r["detail"])
        D.RESULTS.clear()
        (cfg / "hooks.json").write_text("{not json")
        D.check_antigravity_global()                                    # parse error: WARN, never raises
        self.assertEqual(self.results("agy global")[0]["status"], "WARN")

    def test_mcp_names_only(self):
        cfg = self.home / ".gemini/config"
        cfg.mkdir(parents=True)
        (cfg / "mcp_config.json").write_text(json.dumps({"mcpServers": {
            "kubernetes": {"command": "k8s-mcp", "env": {"TOKEN": "supersecretvalue123456"}}, "proxmox": {}}}))
        root = tmpdir()
        (root / ".agents/agents/cecilia-devops").mkdir(parents=True)
        (root / ".agents/agents/cecilia-devops/agent.md").write_text("---\ntools:\n  - call_mcp_tool\n---\n")
        D.check_antigravity_mcp(root)
        r = self.results("agy MCP")[0]
        self.assertEqual(r["status"], "INFO")
        self.assertIn("kubernetes, proxmox", r["detail"])
        self.assertIn("devops", r["detail"])
        self.assertNotIn("supersecret", r["detail"])
        self.assertNotIn("k8s-mcp", r["detail"])


class OpenAgy(unittest.TestCase):
    def setUp(self):
        base = tmpdir()
        self.proj, self.ws = base / "shop", base / "shop.cecilia"
        self.proj.mkdir()
        (self.ws / ".cecilia").mkdir(parents=True)
        (self.ws / ".cecilia/config.json").write_text(json.dumps({"workspace": {"project": str(self.proj)}}))

    def run_open(self, args, agy="C:/Tools/agy.cmd"):
        call = mock.Mock(return_value=0)
        out = io.StringIO()
        with mock.patch.object(cli, "find_agy", return_value=agy), mock.patch.object(cli.subprocess, "call", call), \
                contextlib.redirect_stdout(out):
            rc = cli.cmd_open(args)
        return rc, call, out.getvalue()

    def test_agy_argv_and_cwd(self):
        rc, call, out = self.run_open([str(self.ws), "--agy", "--skip-permissions"])
        self.assertEqual(rc, 0)
        self.assertEqual(call.call_args[0][0], ["C:/Tools/agy.cmd", "--dangerously-skip-permissions"])
        self.assertEqual(call.call_args[1]["cwd"], str(self.ws))
        self.assertIn("WITHOUT Cecilia", out)
        rc, call, _ = self.run_open([str(self.proj), "--agy"])
        self.assertEqual(call.call_args[0][0], ["C:/Tools/agy.cmd"])
        self.assertEqual(call.call_args[1]["cwd"], str(self.ws))

    def test_agy_missing_and_plain_open(self):
        rc, call, out = self.run_open([str(self.ws), "--agy"], agy=None)
        self.assertEqual(rc, 1)
        call.assert_not_called()
        rc, call, out = self.run_open([str(self.ws)])
        self.assertEqual(rc, 0)
        call.assert_not_called()
        self.assertIn("--agy", out)

    def test_find_agy_windows_shims(self):
        seen = []

        def which(name):
            seen.append(name)
            return "C:/npm/agy.cmd" if name == "agy.cmd" else None
        with mock.patch.object(cli.shutil, "which", which):
            self.assertEqual(cli.find_agy(), "C:/npm/agy.cmd")
        self.assertEqual(seen, ["agy", "agy.cmd"])


if __name__ == "__main__":
    unittest.main()
