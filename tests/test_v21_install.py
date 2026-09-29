"""Cecilia 20.1 install/doctor/setup: PATH-python hook commands, old-form upgrades, doctor secret scan and
interpreter check, new-version helpers, ~/.cecilia/workspaces.json, infra at the project root.
    python3 -m unittest tests.test_v21_install -q"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "guard"))
sys.path.insert(0, str(ROOT / "src"))
import install  # noqa: E402
import setup as S  # noqa: E402
import cecilia_doctor as D  # noqa: E402
import cecilia_guard as G  # noqa: E402
from cecilia import cli  # noqa: E402


def tmpdir() -> Path:
    return Path(tempfile.mkdtemp()).resolve()


class HookCommands(unittest.TestCase):
    def setUp(self):
        self._form = dict(install.HOOK_FORM)
        self._over = dict(install.HOOK_PYTHON)
        install.HOOK_PYTHON["override"] = None

    def tearDown(self):
        install.HOOK_FORM.clear()
        install.HOOK_FORM.update(self._form)
        install.HOOK_PYTHON.clear()
        install.HOOK_PYTHON.update(self._over)

    def test_windows_no_space_is_inline_without_quotes(self):
        ws = Path("D:/agent-workspace/proxmox-homelab/k8s.cecilia")
        cmd, body = install.antigravity_hook_command(ws / ".cecilia/bin/cecilia_guard.py", ws, windows=True)
        self.assertIsNone(body)
        self.assertEqual(cmd, r"python D:\agent-workspace\proxmox-homelab\k8s.cecilia\.cecilia\bin\cecilia_guard.py "
                              r"--host antigravity --workspace D:\agent-workspace\proxmox-homelab\k8s.cecilia")
        self.assertNotIn('"', cmd)

    def test_windows_space_uses_launcher(self):
        ws = Path("C:/Users/Thanh Tan/k8s.cecilia")
        cmd, body = install.antigravity_hook_command(ws / ".cecilia/bin/cecilia_guard.py", ws, windows=True)
        self.assertNotIn('"', cmd)
        self.assertTrue(cmd.endswith(r"\cecilia_guard_antigravity.cmd"))
        self.assertIn(r'python "C:\Users\Thanh Tan\k8s.cecilia\.cecilia\bin\cecilia_guard.py" --host antigravity '
                      r'--workspace "C:\Users\Thanh Tan\k8s.cecilia"', body)

    def test_windows_launcher_calls_configured_interpreter(self):
        ws = Path("C:/Users/Thanh Tan/k8s.cecilia")
        _, body = install.antigravity_hook_command(ws / ".cecilia/bin/cecilia_guard.py", ws, windows=True,
                                                   python="C:/Program Files/Python312/python.exe")
        self.assertIn(r'"C:\Program Files\Python312\python.exe" "C:\Users', body)

    def test_posix_python3_inline(self):
        cmd, body = install.antigravity_hook_command(Path("/w/x.cecilia/.cecilia/bin/cecilia_guard.py"),
                                                     Path("/w/x.cecilia"), windows=False)
        self.assertIsNone(body)
        self.assertEqual(cmd, "python3 /w/x.cecilia/.cecilia/bin/cecilia_guard.py --host antigravity "
                              "--workspace /w/x.cecilia")
        cmd, _ = install.antigravity_hook_command(Path("/w/my ws/.cecilia/bin/cecilia_guard.py"), windows=False)
        self.assertEqual(cmd, 'python3 "/w/my ws/.cecilia/bin/cecilia_guard.py" --host antigravity')

    def test_configured_absolute_interpreter(self):
        ws = Path("D:/w/k8s.cecilia")
        cmd, body = install.antigravity_hook_command(ws / ".cecilia/bin/cecilia_guard.py", ws, windows=True,
                                                     python="C:/Python312/python.exe")
        self.assertIsNone(body)
        self.assertTrue(cmd.startswith("C:\\Python312\\python.exe D:\\w\\k8s.cecilia\\"), cmd)
        cmd, _ = install.antigravity_hook_command(Path("/w/.cecilia/bin/cecilia_guard.py"), windows=False,
                                                  python="/opt/py/bin/python3.12")
        self.assertTrue(cmd.startswith("/opt/py/bin/python3.12 /w/"))

    def test_config_guard_python_and_override(self):
        ws = tmpdir()
        (ws / ".cecilia").mkdir()
        self.assertEqual(install.configured_python(ws, windows=True), "python")
        self.assertEqual(install.configured_python(ws, windows=False), "python3")
        (ws / ".cecilia/config.json").write_text(json.dumps({"guard": {"python": "/opt/py/bin/python3"}}))
        self.assertEqual(install.configured_python(ws), "/opt/py/bin/python3")
        self.assertEqual(install.configured_python(ws, "py312"), "py312")
        self.assertTrue(install.set_config_python(ws / ".cecilia/config.json", "python"))
        self.assertFalse(install.set_config_python(ws / ".cecilia/config.json", "python"))
        self.assertEqual(json.loads((ws / ".cecilia/config.json").read_text())["guard"]["python"], "python")

    def test_claude_exec_and_shell_forms(self):
        guard, ws = Path("/w/k.cecilia/.cecilia/bin/cecilia_guard.py"), Path("/w/k.cecilia")
        install.choose_hook_form("exec")
        h = json.loads(install.render_claude_settings(guard, ws, Path("/w/k"), python="python3"))
        hook = h["hooks"]["PreToolUse"][0]["hooks"][0]
        self.assertEqual(hook["command"], "python3")
        self.assertEqual(hook["args"], [str(guard), "--host", "claude", "--workspace", str(ws)])
        install.choose_hook_form("shell")
        h = json.loads(install.render_claude_settings(guard, python="python"))
        cmd = h["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        self.assertEqual(cmd, f'python "{guard.as_posix()}" --host claude')
        h = json.loads(install.render_claude_settings(guard, python="C:/Program Files/Py/python.exe"))
        self.assertTrue(h["hooks"]["PreToolUse"][0]["hooks"][0]["command"].startswith('"C:/Program Files/Py/python.exe" '))


class OldFormsUpgrade(unittest.TestCase):
    def _new_hooks(self, guard: Path) -> str:
        return install.render_antigravity_hooks(guard, windows=False, python="python3")

    def test_only_cecilia_settings_recognises_old_antigravity_forms(self):
        d = tmpdir()
        guard = d / ".cecilia/bin/cecilia_guard.py"
        new = self._new_hooks(guard)
        old_forms = [
            f'"C:/Users/Thanh Tan/AppData/Roaming/uv/tools/cecilia/Scripts/python.exe" "{guard.as_posix()}" '
            '--host antigravity --workspace "D:/w/k8s.cecilia"',
            r"D:\w\k8s.cecilia\.cecilia\bin\cecilia_guard_antigravity.cmd",
            f"/usr/bin/python3 {guard.as_posix()} --host antigravity",
        ]
        for old in old_forms:
            data = json.loads(new)
            data["cecilia-guard"]["PreToolUse"][0]["hooks"][0]["command"] = old
            f = d / "hooks.json"
            f.write_text(json.dumps(data))
            self.assertTrue(install.only_cecilia_settings(f, new), old)
        data = json.loads(new)
        data["other"] = {}
        f.write_text(json.dumps(data))
        self.assertFalse(install.only_cecilia_settings(f, new))

    def test_only_cecilia_settings_recognises_old_claude_forms(self):
        d = tmpdir()
        guard = d / ".cecilia/bin/cecilia_guard.py"
        install.choose_hook_form("exec")
        new = install.render_claude_settings(guard, python="python3")
        for cmd, args in (("C:\\Users\\Thanh Tan\\uv\\python.exe", [str(guard), "--host", "claude"]),
                          (f'"/usr/bin/python3" "{guard.as_posix()}" --host claude', None)):
            data = json.loads(new)
            for ev in data["hooks"].values():
                h = ev[0]["hooks"][0]
                h["command"] = cmd
                if args is None:
                    h.pop("args", None)
                else:
                    h["args"] = args
            f = d / "settings.json"
            f.write_text(json.dumps(data))
            self.assertTrue(install.only_cecilia_settings(f, new), cmd)

    def test_upgrade_replaces_old_hooks_and_retires_launcher(self):
        base = tmpdir()
        proj, ws = base / "shop", base / "shop.cecilia"
        proj.mkdir()
        install.choose_hook_form("exec")
        plan = install.build_workspace(proj, ws, {"antigravity"}, python="python3")
        install.apply(plan)
        hooks = ws / ".agents/hooks.json"
        data = json.loads(hooks.read_text())
        data["cecilia-guard"]["PreToolUse"][0]["hooks"][0]["command"] = \
            str(ws / ".cecilia/bin/cecilia_guard_antigravity.cmd").replace("/", "\\")
        hooks.write_text(json.dumps(data))
        (ws / ".cecilia/bin/cecilia_guard_antigravity.cmd").write_text("@echo off\n")
        plan = install.build_workspace(proj, ws, {"antigravity"}, upgrade=True, python="python3")
        self.assertIn(hooks, [d for d, _ in plan.replace])
        self.assertIn(ws / ".cecilia/bin/cecilia_guard_antigravity.cmd", plan.retire)
        self.assertEqual(plan.register, (ws, proj))
        install.apply(plan)
        cmd = json.loads(hooks.read_text())["cecilia-guard"]["PreToolUse"][0]["hooks"][0]["command"]
        self.assertTrue(cmd.startswith("python3 "), cmd)

    def test_python_option_stored_in_config(self):
        base = tmpdir()
        proj, ws = base / "shop", base / "shop.cecilia"
        proj.mkdir()
        install.choose_hook_form("exec")
        plan = install.build_workspace(proj, ws, {"claude"}, python="/opt/py/bin/python3")
        install.apply(plan)
        cfg = json.loads((ws / ".cecilia/config.json").read_text())
        self.assertEqual(cfg["guard"]["python"], "/opt/py/bin/python3")
        self.assertEqual(cfg["workspace"]["project"], str(proj))
        s = json.loads((ws / ".claude/settings.json").read_text())
        self.assertEqual(s["hooks"]["PreToolUse"][0]["hooks"][0]["command"], "/opt/py/bin/python3")
        plan = install.build_workspace(proj, ws, {"claude"}, upgrade=True)      # no --python: config is used
        self.assertIsNone(plan.set_python)
        self.assertEqual(install.configured_python(ws), "/opt/py/bin/python3")


class DoctorChecks(unittest.TestCase):
    def setUp(self):
        D.RESULTS.clear()

    def test_secret_scan_ignores_dates_but_flags_tokens(self):
        self.assertIsNone(D.secret_kind("claudeCodeFirstTokenDate", "2025-06-01T12:34:56.789Z"))
        self.assertIsNone(D.secret_kind("tokenExpiresAt", "abcdefghijklmnopqrstu"))
        self.assertIsNone(D.secret_kind("token_count", "12345678901234567890"))
        self.assertIsNone(D.secret_kind("apiToken", "short"))
        self.assertIsNone(D.secret_kind("apiToken", "true"))
        self.assertIsNone(D.secret_kind("GITHUB_TOKEN", "${GITHUB_TOKEN}"))
        self.assertEqual(D.secret_kind("apiToken", "abcd1234efgh5678ijkl"), "secret-like value")
        self.assertEqual(D.secret_kind("x", "ghp_" + "a1" * 15), "GitHub token")

    def test_mcp_scan_on_a_claude_json(self):
        d = tmpdir()
        (d / ".mcp.json").write_text(json.dumps({"claudeCodeFirstTokenDate": "2025-06-01T12:34:56.789Z",
                                                 "numStartups": 42, "hasCompletedOnboarding": True,
                                                 "mcpServers": {"x": {"env": {"API_TOKEN": "abcd1234efgh5678ijkl"}}}}))
        old = os.environ.get("HOME"), os.environ.get("USERPROFILE")
        os.environ["HOME"] = os.environ["USERPROFILE"] = str(d / "nohome")
        try:
            D.check_mcp(d, {})
        finally:
            for k, v in zip(("HOME", "USERPROFILE"), old):
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        r = [x for x in D.RESULTS if x["check"] == "MCP secrets"][0]
        self.assertEqual(r["status"], "WARN")
        self.assertIn("API_TOKEN", r["detail"])
        self.assertNotIn("FirstTokenDate", r["detail"])

    def test_interpreter_check(self):
        self.assertTrue(D.check_interpreter(sys.executable))
        self.assertFalse(D.check_interpreter("no-such-python-xyz"))
        self.assertEqual(D.RESULTS[-1]["status"], "FAIL")
        self.assertIn("python.org", D.RESULTS[-1]["fix"])
        self.assertEqual(D.configured_python({"guard": {"python": "/x/py"}}), "/x/py")
        self.assertIn(D.configured_python({}), {"python", "python3"})

    def test_antigravity_quote_rule(self):
        self.assertIsNotNone(D.antigravity_quote_problem('"C:/py.exe" "D:/g.py" --host antigravity', True))
        self.assertIsNone(D.antigravity_quote_problem(r"python D:\w\g.py --host antigravity", True))
        self.assertIsNone(D.antigravity_quote_problem(r"D:\w\cecilia_guard_antigravity.cmd", True))
        self.assertIsNone(D.antigravity_quote_problem('python3 "/w/my ws/g.py"', False))
        d = tmpdir()
        (d / "l.cmd").write_text('@echo off\nrem x\npython "D:\\w s\\g.py" --host antigravity\nexit /b %ERRORLEVEL%\n')
        self.assertEqual(D.launcher_command(d / "l.cmd"), 'python "D:\\w s\\g.py" --host antigravity')

    def test_known_config_keys(self):
        d = tmpdir()
        (d / ".cecilia").mkdir()
        from roster import default_config
        cfg = default_config()
        cfg.update(consensus={}, automation={}, mcp={}, guard={"python": "python"})
        (d / ".cecilia/config.json").write_text(json.dumps(cfg))
        D.check_config(d)
        self.assertFalse([r for r in D.RESULTS if "unknown key" in r["detail"]])


class VersionNotice(unittest.TestCase):
    def test_version_helpers(self):
        self.assertEqual(D.parse_version("v20.1.0"), (20, 1, 0))
        self.assertEqual(D.parse_version("refs/tags/v20.1"), (20, 1, 0))
        self.assertIsNone(D.parse_version("v21.0.0-rc1"))
        tags = ["refs/tags/v19.2.0", "refs/tags/v20.0.1", "refs/tags/v20.1.0", "refs/tags/v20.1.0^{}",
                "refs/tags/v20.10.0", "refs/tags/latest"]
        self.assertEqual(D.newest_tag(tags, "20.0.1"), "v20.10.0")
        self.assertIsNone(D.newest_tag(tags, "20.10.0"))
        self.assertIsNone(D.newest_tag([], "20.0.1"))

    def test_uv_receipt(self):
        d = tmpdir()
        (d / "uv-receipt.toml").write_text('[tool]\nrequirements = [{ name = "cecilia", git = '
                                           '"https://github.com/acme/cecilia?tag=v20.0.1" }]\n')
        self.assertEqual(D.uv_receipt_url([d]), "https://github.com/acme/cecilia")
        (d / "uv-receipt.toml").write_text('requirements = [{ name = "cecilia", git = "https://github.com/acme/c@v20" }]')
        self.assertEqual(D.uv_receipt_url([d]), "https://github.com/acme/c")
        self.assertIsNone(D.uv_receipt_url([tmpdir()]))

    def test_update_check_never_fails(self):
        D.RESULTS.clear()
        os.environ["CECILIA_NO_UPDATE_CHECK"] = "1"
        try:
            D.check_update()
        finally:
            os.environ.pop("CECILIA_NO_UPDATE_CHECK")
        self.assertEqual(D.RESULTS, [])


class WorkspaceRegistry(unittest.TestCase):
    def test_register_and_dedupe(self):
        f = tmpdir() / "sub" / "workspaces.json"
        install.register_workspace(Path("/w/a.cecilia"), Path("/w/a"), path=f)
        install.register_workspace(Path("/w/b.cecilia"), Path("/w/b"), name="bee", path=f)
        install.register_workspace(Path("/w/a.cecilia"), Path("/w/a2"), path=f)
        data = json.loads(f.read_text())
        self.assertEqual(set(data), {"workspaces"})
        items = data["workspaces"]
        self.assertEqual(len(items), 2)
        a = [w for w in items if w["workspace"] == str(Path("/w/a.cecilia"))][0]
        self.assertEqual(set(a), {"workspace", "project", "name", "updated"})
        self.assertEqual(a["project"], str(Path("/w/a2")))
        self.assertEqual(a["name"], "a2")
        self.assertEqual(install.read_workspaces(f), items)

    def test_cli_reads_env_file(self):
        f = tmpdir() / "workspaces.json"
        before = os.environ.get("CECILIA_WORKSPACES")
        os.environ["CECILIA_WORKSPACES"] = str(f)
        try:
            install.register_workspace(Path("/w/a.cecilia"), Path("/w/a"))
            self.assertEqual([w["name"] for w in cli.registered_workspaces()], ["a"])
        finally:
            if before is None:
                os.environ.pop("CECILIA_WORKSPACES", None)
            else:
                os.environ["CECILIA_WORKSPACES"] = before

    def test_split_python(self):
        self.assertEqual(cli.split_python(["shop", "--python", "py", "--dry-run"]), (["shop", "--dry-run"], "py"))
        self.assertEqual(cli.split_python(["--python=C:/P/python.exe"]), ([], "C:/P/python.exe"))
        self.assertEqual(cli.split_python(["--all"]), (["--all"], None))


class InfraAtRoot(unittest.TestCase):
    def test_root_infra_detected_and_lanes_profile_cover_root(self):
        proj = tmpdir()
        (proj / "deployment.yaml").write_text("apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: x\n")
        (proj / "kustomization.yaml").write_text("resources:\n- deployment.yaml\n")
        (proj / "notes.yaml").write_text("a: 1\n")
        found = S.detect(proj)
        self.assertEqual(found["root_infra"], ["deployment.yaml", "kustomization.yaml"])
        cfg, why = S.propose(proj, found, home=proj.parent / (proj.name + ".cecilia"))
        self.assertTrue(cfg["roles"]["cecilia-devops"])
        lane = cfg["lanes"]["cecilia-devops"]
        base = json.loads((ROOT / "registry/roles/cecilia-devops.json").read_text())["lane"]
        self.assertEqual(lane[:len(base)], base)
        for g in ("**/*.yaml", "**/*.yml", "**/*.tf", "**/*.tfvars", "**/Chart.yaml", "**/values*.yaml",
                  "**/kustomization.yaml"):
            self.assertIn(g, lane)
        infra = [p for p in cfg["profiles"] if p["name"] == "infra"][0]
        self.assertTrue(G.matches("deployment.yaml", infra["paths"]))
        self.assertTrue(G.matches("main.tf", infra["paths"]))
        self.assertTrue(G.matches("deployment.yaml", lane))
        self.assertTrue(any("infra root" in w for w in why))

    def test_no_root_infra_for_app_repo(self):
        proj = tmpdir()
        (proj / "package.json").write_text('{"dependencies": {"express": "1"}}')
        (proj / "config.yaml").write_text("port: 1\n")
        found = S.detect(proj)
        self.assertEqual(found["root_infra"], [])
        cfg, _ = S.propose(proj, found)
        self.assertNotIn("**/*.yaml", cfg["lanes"].get("cecilia-devops", []))

    def test_terraform_root(self):
        proj = tmpdir()
        (proj / "main.tf").write_text('resource "x" "y" {}\n')
        self.assertEqual(S.detect_root_infra(proj), ["main.tf"])


if __name__ == "__main__":
    unittest.main()
