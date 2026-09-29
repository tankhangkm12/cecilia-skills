import json, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import install  # noqa: E402


class AntigravityHookCommand(unittest.TestCase):
    def test_windows_uses_launcher_without_quotes(self):
        guard = Path("D:/w/k8s.cecilia/.cecilia/bin/cecilia_guard.py")
        cmd, body = install.antigravity_hook_command(
            guard, Path("D:/w/k8s.cecilia"), windows=True,
            python="C:/Users/Thanh Tan/AppData/Roaming/uv/tools/cecilia/Scripts/python.exe")
        self.assertNotIn('"', cmd)
        self.assertTrue(cmd.endswith("cecilia_guard_antigravity.cmd"))
        self.assertIn('"C:\\Users\\Thanh Tan\\AppData', body)
        self.assertIn("--host antigravity", body)
        self.assertIn("exit /b %ERRORLEVEL%", body)

    def test_posix_inline(self):
        cmd, body = install.antigravity_hook_command(Path("/w/.cecilia/bin/cecilia_guard.py"), windows=False,
                                                     python="/usr/bin/python3")
        self.assertIsNone(body)
        self.assertIn("--host antigravity", cmd)


if __name__ == "__main__":
    unittest.main()
