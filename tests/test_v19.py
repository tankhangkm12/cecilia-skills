"""Regression tests for what v19 adds: local-only, compound state, path profiles, shell write scope,
tool rules, push lock, doctor, config migration, corpus gate.   python3 -m unittest discover -s tests -v"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "guard"))
sys.path.insert(0, str(ROOT / "tools"))
import cecilia_guard as G  # noqa: E402
import cecilia_mode as M  # noqa: E402
import guard_corpus as C  # noqa: E402
import roster as R  # noqa: E402

PY = sys.executable
GUARD = str(ROOT / "guard" / "cecilia_guard.py")
HAS_GIT = shutil.which("git") is not None


def utc(hours=0):
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=hours)).isoformat(timespec="seconds")


def fixture(**kw) -> Path:
    return C.build_fixture(Path(tempfile.mkdtemp()).resolve(), **kw)


def set_config(root: Path, **changes):
    cfg = json.loads((root / ".cecilia/config.json").read_text())
    for k, v in changes.items():
        cfg[k] = v
    (root / ".cecilia/config.json").write_text(json.dumps(cfg))


def approve(root: Path, write, task="T-B01"):
    rec = {"task": task, "write": list(write), "commands": [], "environments": ["local"], "approved_by": "Cecilia",
           "approved_at": utc(), "expires_at": utc(24), "revoked": False}
    (root / ".cecilia/approvals" / f"{task}.json").write_text(json.dumps(rec))


def git(root: Path, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                          env=dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                                   GIT_COMMITTER_EMAIL="t@t"))


class CorpusGate(unittest.TestCase):
    """The release gate: every adversarial command asked/denied, every everyday command untouched."""

    def test_corpus(self):
        res = C.run()
        s = res["summary"]
        misses = [f"{c['want']}->{c['got']}: {c['cmd']}" for k in ("adversarial", "benign") for c in res[k] if not c["ok"]]
        self.assertGreaterEqual(len(res["adversarial"]), 120)
        self.assertGreaterEqual(len(res["benign"]), 80)
        self.assertGreaterEqual(s["adversarial_rate"], 0.95, misses)
        self.assertEqual(s["benign_rate"], 1.0, misses)
        push = s["by_category"]["push"].split("/")
        self.assertEqual(push[0], push[1], misses)
        self.assertGreaterEqual(int(push[1]), 25)
        self.assertLess(s["median_ms"], 100)


class LocalOnly(unittest.TestCase):
    def test_off_restores_a3_asks(self):
        root = fixture()
        set_config(root, git={"require_task_branch": True, "local_only": False})
        for cmd in ("git push origin feature/x", "gh pr create --fill", "git remote add up https://x/y.git"):
            with self.subTest(cmd=cmd):
                self.assertEqual(G.decide_command(cmd, root, root)[0], "ask")
        self.assertEqual(G.decide_command("git push origin main", root, root)[0], "deny")   # A4 either way
        self.assertEqual(G.decide_mcp("mcp__github__create_pull_request", root)[0], "ask")

    def test_git_host_mcp_through_a_gateway(self):
        root = fixture()
        self.assertEqual(G.decide_mcp("mcp__mcp-gateway__github-create_pull_request", root)[0], "deny")
        self.assertIsNone(G.decide_mcp("mcp__mcp-gateway__context7-query-docs", root)[0])
        self.assertIsNone(G.decide_mcp("mcp__mcp-gateway__context7-resolve-library-id", root)[0])
        self.assertIsNone(G.decide_mcp("mcp__MCP_DOCKER__sequentialthinking", root)[0])

    @unittest.skipUnless(HAS_GIT, "git not installed")
    def test_staged_cecilia_files_block_the_commit(self):
        root = Path(tempfile.mkdtemp()).resolve()
        git(root, "init", "-q", "-b", "feature/x")
        git(root, "commit", "-q", "--allow-empty", "-m", "init")
        (root / ".cecilia").mkdir()
        (root / ".cecilia/config.json").write_text(json.dumps(R.default_config()))
        (root / "src").mkdir()
        (root / "src/a.ts").write_text("a\n")
        git(root, "add", "src/a.ts")
        self.assertIsNone(G.decide_command("git commit -m 'feat: a'", root, root)[0])
        git(root, "add", "-f", ".cecilia/config.json")
        d, why = G.decide_command("git commit -m 'feat: a'", root, root)
        self.assertEqual(d, "deny")
        self.assertIn(".cecilia/config.json", why)
        self.assertIn("git restore --staged", why)
        git(root, "restore", "--staged", ".cecilia/config.json")
        self.assertIsNone(G.decide_command("git commit -m 'feat: a'", root, root)[0])

    def test_force_adding_cecilia_paths(self):
        root = fixture()
        for cmd in ("git add -f .cecilia/config.json", "git add --force tensura/reports/T/x.md", "git add -f ."):
            with self.subTest(cmd=cmd):
                self.assertEqual(G.decide_command(cmd, root, root)[0], "deny")
        self.assertIsNone(G.decide_command("git add -f dist/keep.txt", root, root)[0])


class CompoundState(unittest.TestCase):
    def test_switch_then_history_write(self):
        root = fixture()
        self.assertEqual(G.decide_command("git switch main && git merge feature/x", root, root)[0], "deny")
        self.assertIsNone(G.decide_command("git switch -c feature/y && git commit -m x", root, root)[0])
        self.assertIsNone(G.decide_command("git checkout -b feature/z develop && git merge feature/x", root, root)[0])

    def test_cd_then_write(self):
        root = fixture()
        d, _ = G.decide_command("cd .github/workflows && echo x >> ci.yml", root, root)
        self.assertEqual(d, "ask")
        self.assertIsNone(G.decide_command("cd src && echo x > notes.md", root, root)[0])

    def test_shell_writes_obey_git_flow(self):
        root = fixture(branch="main")
        self.assertEqual(G.decide_command("echo x > src/notes.md", root, root)[0], "deny")
        self.assertIsNone(G.decide_command("echo x > tensura/reports/T/x.md", root, root)[0])   # exempt
        self.assertIsNone(G.decide_command("npm test > /tmp/t.log 2>&1", root, root)[0])           # outside project

    def test_explain_shows_segments(self):
        root = fixture()
        r = subprocess.run([PY, GUARD, "--explain", "git switch main && git merge x", "--cwd", str(root)],
                           capture_output=True, text=True)
        out = json.loads(r.stdout)
        self.assertEqual(out["decision"], "deny")
        self.assertTrue(any(s.get("branch") == "main" for s in out["segments"]))


class Profiles(unittest.TestCase):
    def test_edit_tool_levels(self):
        root = fixture()
        self.assertIsNone(G.decide_write(str(root / "src/app.ts"), root, root)[0])
        self.assertEqual(G.decide_write(str(root / ".github/workflows/ci.yml"), root, root)[0], "ask")
        self.assertEqual(G.decide_write(str(root / "prisma/migrations/001/m.sql"), root, root)[0], "ask")
        self.assertEqual(G.decide_write(str(root / "services/api/Dockerfile"), root, root)[0], "ask")

    def test_controlled_profile_needs_scope(self):
        root = fixture()
        set_config(root, profiles=[{"name": "infra", "level": "controlled", "paths": ["infra/**"]}])
        self.assertEqual(G.decide_write(str(root / "infra/main.tf"), root, root)[0], "deny")
        self.assertEqual(G.decide_command("echo x > infra/main.tf", root, root)[0], "deny")
        approve(root, ["infra/**"])
        self.assertIsNone(G.decide_write(str(root / "infra/main.tf"), root, root)[0])
        self.assertIsNone(G.decide_command("echo x > infra/main.tf", root, root)[0])
        self.assertIsNone(G.decide_write(str(root / "src/app.ts"), root, root)[0])       # app stays light

    def test_ask_profile_covered_by_scope(self):
        root = fixture()
        approve(root, [".github/workflows/**"])
        self.assertIsNone(G.decide_write(str(root / ".github/workflows/ci.yml"), root, root)[0])

    def test_deny_profile_and_global_controlled(self):
        root = fixture(mode="controlled")
        self.assertEqual(G.decide_write(str(root / "src/app.ts"), root, root)[0], "deny")    # mode wins
        self.assertEqual(G.decide_command("sed -i s/a/b/ src/app.ts", root, root)[0], "deny")
        approve(root, ["src/**"])
        self.assertIsNone(G.decide_command("sed -i s/a/b/ src/app.ts", root, root)[0])
        set_config(root, profiles=[{"name": "legal", "level": "deny", "paths": ["LICENSE"]}])
        self.assertEqual(G.decide_write(str(root / "LICENSE"), root, root)[0], "deny")

    def test_guard_extra_from_config(self):
        root = fixture()
        set_config(root, guard={"live_tools": ["acmectl"]})
        self.assertEqual(G.decide_command("acmectl rollout api", root, root)[0], "ask")
        self.assertIsNone(G.decide_command("acmectl rollout api", fixture(), fixture())[0])


class ToolRules(unittest.TestCase):
    RULE = {"id": "docs-first", "tools": ["*context7*"], "enforce": "gate", "when": "code uses a library API"}

    def transcript(self, tmp: Path, calls):
        t = tmp / "t.jsonl"
        lines = []
        for name, inp in calls:
            lines.append(json.dumps({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": name, "input": inp}]}}))
        t.write_text("\n".join(lines) + "\n")
        return t

    def edit(self, root, transcript, new, old="", agent=None, path="src/app.ts"):
        data = {"tool_name": "Edit", "tool_input": {"file_path": str(root / path), "old_string": old, "new_string": new},
                "cwd": str(root), "transcript_path": str(transcript), "hook_event_name": "PreToolUse"}
        if agent:
            data["agent_type"] = agent
        return G.check_tool_rules(data, [str(root / path)], root, root)

    def test_gate(self):
        root = fixture()
        set_config(root, tool_rules=[self.RULE])
        empty = self.transcript(root, [])
        self.assertEqual(self.edit(root, empty, "import axios from 'axios'\n")[0], "deny")
        self.assertIsNone(self.edit(root, empty, "import { x } from './x'\nimport y from '@/y'\n")[0])
        self.assertIsNone(self.edit(root, empty, "const a = 2\n")[0])
        self.assertIsNone(self.edit(root, empty, "import React from 'react'\n", old="import React from 'react'\n")[0])
        looked = self.transcript(root, [("mcp__mcp-gateway__context7-query-docs",
                                         {"context7CompatibleLibraryID": "/axios/axios", "topic": "interceptors"})])
        self.assertIsNone(self.edit(root, looked, "import axios from 'axios'\n")[0])
        self.assertEqual(self.edit(root, looked, "import dayjs from 'dayjs'\n")[0], "deny")
        py = self.transcript(root, [])
        self.assertEqual(self.edit(root, py, "import requests\n", path="svc/a.py")[0], "deny")
        self.assertIsNone(self.edit(root, py, "import os, json\nfrom pathlib import Path\n", path="svc/a.py")[0])
        self.assertIsNone(self.edit(root, empty, "import axios from 'axios'\n", path="README.md")[0])

    def test_roles_filter_and_report_mode(self):
        root = fixture()
        set_config(root, tool_rules=[dict(self.RULE, roles=["cecilia-dev-fe"])])
        empty = self.transcript(root, [])
        self.assertIsNone(self.edit(root, empty, "import axios from 'axios'\n", agent="cecilia-test")[0])
        self.assertEqual(self.edit(root, empty, "import axios from 'axios'\n", agent="cecilia-dev-fe")[0], "deny")
        set_config(root, tool_rules=[dict(self.RULE, enforce="report")])
        self.assertIsNone(self.edit(root, empty, "import axios from 'axios'\n")[0])

    def test_hook_end_to_end_and_reminder(self):
        root = fixture()
        set_config(root, tool_rules=[self.RULE])
        t = self.transcript(root, [])
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(root / "src/b.ts"),
                                                         "content": "import lodash from 'lodash'\n"},
                   "cwd": str(root), "transcript_path": str(t)}
        r = subprocess.run([PY, GUARD, "--host", "claude"], input=json.dumps(payload), capture_output=True, text=True,
                           env=dict(os.environ, CLAUDE_PROJECT_DIR=str(root)))
        out = json.loads(r.stdout)["hookSpecificOutput"]
        self.assertEqual(out["permissionDecision"], "deny")
        self.assertIn("lodash", out["permissionDecisionReason"])
        r = subprocess.run([PY, GUARD, "--host", "claude"], input=json.dumps({"hook_event_name": "UserPromptSubmit",
                                                                              "cwd": str(root), "prompt": "hi"}),
                           capture_output=True, text=True, env=dict(os.environ, CLAUDE_PROJECT_DIR=str(root)))
        self.assertIn("docs-first", json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"])
        set_config(root, tool_rules=[])
        r = subprocess.run([PY, GUARD, "--host", "claude"], input=json.dumps({"hook_event_name": "UserPromptSubmit",
                                                                              "cwd": str(root)}),
                           capture_output=True, text=True, env=dict(os.environ, CLAUDE_PROJECT_DIR=str(root)))
        self.assertEqual(r.stdout.strip(), "")


class FailClosed(unittest.TestCase):
    def test_missing_policy_denies_everything(self):
        tmp = Path(tempfile.mkdtemp())
        shutil.copy(GUARD, tmp / "cecilia_guard.py")
        root = fixture()
        for host, payload in (("claude", {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(root)}),
                              ("antigravity", {"toolCall": {"name": "run_command", "args": {"CommandLine": "ls"}},
                                               "workspacePaths": [str(root)]})):
            r = subprocess.run([PY, str(tmp / "cecilia_guard.py"), "--host", host], input=json.dumps(payload),
                               capture_output=True, text=True)
            self.assertIn('"deny"', r.stdout, host)
            self.assertIn("policy.json", r.stdout)


@unittest.skipUnless(HAS_GIT, "git not installed")
class PushLock(unittest.TestCase):
    def test_lock_blocks_every_push_form_and_restores(self):
        base = Path(tempfile.mkdtemp()).resolve()
        git(base, "init", "-q", "--bare", "remote.git")
        work = base / "work"
        work.mkdir()
        git(work, "init", "-q", "-b", "main")
        git(work, "commit", "-q", "--allow-empty", "-m", "init")
        git(work, "remote", "add", "origin", "../remote.git")
        git(work, "remote", "add", "gh", "https://github.com/example/none.git")
        git(work, "config", "remote.gh.pushurl", str(base / "remote.git"))
        (work / ".cecilia").mkdir()
        M.set_push_lock(work, True)
        self.assertTrue(M.push_lock_status(work))
        for target in ("origin", "gh", "../remote.git", str(base / "remote.git")):
            with self.subTest(target=target):
                self.assertNotEqual(git(work, "push", target, "main").returncode, 0)
        self.assertEqual(git(work, "fetch", "origin").returncode, 0)          # fetch still works
        M.set_push_lock(work, False)
        self.assertFalse(M.push_lock_status(work))
        self.assertEqual(git(work, "config", "--get", "remote.gh.pushurl").stdout.strip(), str(base / "remote.git"))
        self.assertEqual(git(work, "push", "origin", "main").returncode, 0)

    def test_agent_cannot_unlock(self):
        root = fixture()
        for cmd in ("git config --unset-all url.cecilia-push-locked-run-cecilia-mode-push://.pushinsteadof",
                    "python .cecilia/bin/cecilia_mode.py --push-lock off",
                    "python .cecilia/bin/cecilia_mode.py push origin feature/x",
                    "git config --remove-section url.cecilia-push-locked-run-cecilia-mode-push://",
                    "sed -i s/pushinsteadof//g .git/config"):
            with self.subTest(cmd=cmd):
                self.assertEqual(G.decide_command(cmd, root, root)[0], "deny")


class ConfigMigration(unittest.TestCase):
    def test_migrate_keeps_what_cecilia_set(self):
        old = {"roles": {"cecilia-ui": True, "cecilia-db": False}, "git": {"protected": ["main"]}, "models": {}}
        new, changes = R.migrate_config(old)
        self.assertTrue(new["roles"]["cecilia-ui"])
        self.assertFalse(new["roles"]["cecilia-db"])
        self.assertEqual(new["git"]["protected"], ["main"])
        self.assertTrue(new["git"]["local_only"])
        self.assertIn("profiles", new)
        self.assertEqual(new["models"]["cecilia-design"], "strongest")
        keys = [c[0] for c in changes]
        self.assertIn("profiles", keys)
        again, changes2 = R.migrate_config(new)
        self.assertEqual(changes2, [])
        self.assertEqual(again, new)


class Doctor(unittest.TestCase):
    def test_flags_plaintext_tokens_without_printing_them(self):
        root = fixture()
        (root / ".mcp.json").write_text(json.dumps({"mcpServers": {"gw": {
            "serverUrl": "http://10.0.0.5/mcp", "headers": {"Authorization": "Bearer sk-bf-cddcbae1-d05e-4e18-9433-a72878460e22"}},
            "pen": {"serverUrl": "https://design.example/mcp?userToken=eyJhbGciOiJBMjU2S1ciLCJlbmMiOiJBMjU2R0NNIn0.abcdefghijklmnop"},
            "ok": {"headers": {"Authorization": "Bearer ${GW_TOKEN}"}}}}))
        r = subprocess.run([PY, str(ROOT / "guard/cecilia_doctor.py"), "--json", "--project", str(root)],
                           capture_output=True, text=True, env=dict(os.environ, HOME=str(root), USERPROFILE=str(root)))
        out = json.loads(r.stdout)
        leak = next(x for x in out["results"] if x["check"] == "MCP secrets")
        self.assertEqual(leak["status"], "WARN")
        self.assertIn("mcpServers.gw.headers.Authorization", leak["detail"])
        self.assertNotIn("cddcbae1", r.stdout)
        self.assertNotIn("eyJhbGci", r.stdout)
        self.assertIn("mcpServers.pen.serverUrl", leak["detail"])
        self.assertNotIn("mcpServers.ok", leak["detail"])

    def test_guard_allows_doctor_but_not_fix(self):
        root = fixture()
        self.assertIsNone(G.decide_command("python .cecilia/bin/cecilia_doctor.py", root, root)[0])
        self.assertEqual(G.decide_command("python .cecilia/bin/cecilia_doctor.py --fix", root, root)[0], "deny")

    def test_tool_rule_without_provider_warns(self):
        root = fixture()
        set_config(root, tool_rules=[{"id": "docs-first", "tools": ["*context7*"], "enforce": "gate"}])
        r = subprocess.run([PY, str(ROOT / "guard/cecilia_doctor.py"), "--json", "--project", str(root)],
                           capture_output=True, text=True, env=dict(os.environ, HOME=str(root), USERPROFILE=str(root)))
        out = json.loads(r.stdout)
        self.assertTrue(any(x["check"] == "tool rule" and x["status"] == "WARN" for x in out["results"]))


@unittest.skipUnless(HAS_GIT and shutil.which("node"), "git and node needed")
class QualityCheck(unittest.TestCase):
    CHECK = str(ROOT / "shared/scripts/cecilia_check.py")

    def repo(self, scripts: dict, deps: dict | None = None) -> Path:
        root = Path(tempfile.mkdtemp()).resolve()
        git(root, "init", "-q", "-b", "feature/x")
        git(root, "commit", "-q", "--allow-empty", "-m", "init")
        git(root, "branch", "develop")
        (root / "package.json").write_text(json.dumps({"name": "fx", "scripts": scripts, "dependencies": deps or {}}))
        return root

    def run_check(self, root, *extra):
        return subprocess.run([PY, self.CHECK, "--task", "T-1", "--project", str(root), "--offline", "--base", "develop",
                               *extra], capture_output=True, text=True, timeout=300)

    def test_plan_uses_only_what_the_repo_defines(self):
        root = self.repo({"lint": "node -e 0", "test": "node -e 0", "dev": "vite"})
        out = subprocess.run([PY, self.CHECK, "--task", "T-1", "--project", str(root), "--plan"], capture_output=True,
                             text=True).stdout
        self.assertIn("npm run lint", out)
        self.assertIn("npm run test", out)
        self.assertIn("build     (nothing defined)", out)

    def test_evidence_records_pass_and_fail(self):
        root = self.repo({"lint": "node -e 0", "test": "node -e \"console.log('2 passed');process.exit(3)\""})
        r = self.run_check(root, "--steps", "lint,test")
        self.assertEqual(r.returncode, 1)
        ev = json.loads((root / "tensura/reports/T-1/evidence.json").read_text())
        st = {s["step"]: s for s in ev["steps"]}
        self.assertEqual(st["lint"]["status"], "pass")
        self.assertEqual(st["test"]["status"], "fail")
        self.assertEqual(st["test"]["exit"], 3)
        self.assertIn("2 passed", st["test"]["tail"])
        self.assertEqual(ev["sha"], git(root, "rev-parse", "HEAD").stdout.strip())
        self.assertLessEqual(len(r.stdout.strip().splitlines()), 15)

    def test_secrets_and_typosquat(self):
        root = self.repo({}, {"loadsh": "^1.0.0", "react": "^18"})
        (root / "leak.js").write_text('const k = "AKIAABCDEFGHIJKLMNOP";\n')
        (root / ".env.example").write_text("API_KEY=\n")
        r = self.run_check(root, "--steps", "secrets,deps")
        ev = json.loads((root / "tensura/reports/T-1/evidence.json").read_text())
        st = {s["step"]: s for s in ev["steps"]}
        self.assertEqual(st["secrets"]["status"], "fail")
        self.assertIn("leak.js", st["secrets"]["files"])
        self.assertNotIn("AKIAABCDEFGHIJKLMNOP", r.stdout + json.dumps(ev))     # never echoes the secret
        self.assertEqual(st["deps"]["status"], "fail")
        self.assertTrue(any("lodash" in f for f in st["deps"]["flags"]))
        self.assertFalse(any("react" in f for f in st["deps"]["flags"]))


class ApiUx(unittest.TestCase):
    KIT = ROOT / "skills/cecilia-api-ux/scripts/apikit.py"
    FIX = ROOT / "tests/fixtures/api"

    def kit(self, *args):
        r = subprocess.run([PY, str(self.KIT), *args, "--json"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_summary_finds_the_planted_problems(self):
        r = self.kit("summary", str(self.FIX / "shop-v1.yaml"))
        text = json.dumps(r["findings"])
        for needle in ("money as a JSON number", "Idempotency-Key", "pagination parameter names", "error body shapes",
                       "without 409", "mixed field naming"):
            self.assertIn(needle, text)

    def test_diff_finds_breaking_changes(self):
        r = self.kit("diff", str(self.FIX / "shop-v1.yaml"), str(self.FIX / "shop-v2.yaml"))
        breaking = [x["change"] for x in r if x["breaking"]]
        self.assertTrue(any("shop_id" in b for b in breaking))
        self.assertTrue(any("addressId" in b for b in breaking))
        self.assertTrue(any("shipped" in x["change"] and not x["breaking"] for x in r))

    def test_journey_counts_stages_and_n_plus_one(self):
        r = self.kit("journey", "--calls", "GET /cart > GET /products/{id} x12, GET /vouchers > POST /orders",
                     "--latency-ms", "60,80,150")
        self.assertEqual((r["requests"], r["stages"]), (15, 3))
        self.assertEqual(r["critical_path_ms"], [180.0, 240.0, 450.0])
        self.assertEqual(r["n_plus_one"], ["GET /products/{id} ×12"])

    def test_builtin_yaml_reader_matches_pyyaml(self):
        sys.path.insert(0, str(self.KIT.parent))
        import apikit
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")
        for f in ("shop-v1.yaml", "shop-v2.yaml"):
            text = (self.FIX / f).read_text()
            self.assertEqual(apikit.mini_yaml(text), yaml.safe_load(text), f)


class CapacityV19(unittest.TestCase):
    CAP = ROOT / "shared/scripts/capacity.py"

    def cap(self, *args):
        r = subprocess.run([PY, str(self.CAP), *args, "--json"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return [json.loads(x) for x in re.split(r"(?<=\})\s*\n(?=\{)", r.stdout.strip())]

    def test_contention_matches_poisson(self):
        out = self.cap("contention", "--rps-per-key", "0.1,5,200", "--window-ms", "50", "--retries", "0")[0]
        per = [r["conflict per attempt"] for r in out["results"]]
        self.assertEqual(per, ["0.5%", "22.1%", "100.0%"])
        self.assertEqual(out["results"][0]["verdict"], "fine")
        self.assertIn("redesign", out["results"][2]["verdict"])

    def test_forecast_and_threshold(self):
        common = ["--users", "20000,50000,100000", "--monthly-growth", "0.03,0.08,0.15", "--rows-per-user-month", "2,4,8",
                  "--row-bytes", "180", "--index-bytes-per-row", "90", "--ram-gb", "16", "--rto-minutes", "60",
                  "--restore-mbps", "100,200,400"]
        out = self.cap("forecast", *common)
        self.assertEqual(len(out), 2)
        months = {(r["scenario"], r["month"]) for r in out[0]["results"]}
        self.assertIn(("high", 36), months)
        th = self.cap("threshold", *common)[0]["results"]
        hot = next(r for r in th if r["threshold"].startswith("hot set"))
        self.assertTrue(hot["high"].startswith("month"))

    def test_docsize_and_restore(self):
        d = self.cap("docsize", "--fields", "_id:objectId,status:string=8,createdAt:date")[0]
        doc = next(r for r in d["results"] if "document" in r["field"])
        self.assertEqual(doc["bytes"], 5 + (1 + 3 + 1 + 12) + (1 + 6 + 1 + 4 + 8 + 1) + (1 + 9 + 1 + 8))
        r = self.cap("restore", "--data-gb", "10,500,1000", "--restore-mbps", "200", "--rto-minutes", "60")[0]
        self.assertEqual([x["within RTO?"] for x in r["results"]], ["yes", "NO", "NO"])


class RealHomeUntouched(unittest.TestCase):
    """Guards the 18.1 incident: nothing in the suite may write the real ~/.gemini or ~/.claude."""

    def test_home_not_written(self):
        home = Path.home()
        watched = [home / ".gemini" / "config" / "skills", home / ".gemini" / "config" / "hooks.json",
                   home / ".gemini" / "antigravity-cli" / "skills"]
        before = {str(p): (p.exists(), p.stat().st_mtime if p.exists() else 0) for p in watched}
        r = subprocess.run([PY, str(ROOT / "tools/install.py"), "--global", "--home", tempfile.mkdtemp(),
                            "--host", "antigravity", "--host", "claude", "--apply"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        after = {str(p): (p.exists(), p.stat().st_mtime if p.exists() else 0) for p in watched}
        self.assertEqual(before, after)

    def test_home_needs_global(self):
        r = subprocess.run([PY, str(ROOT / "tools/install.py"), "--project", tempfile.mkdtemp(), "--home", "/tmp",
                            "--host", "claude"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(HAS_GIT, "git needed")
class WorkspaceMode(unittest.TestCase):
    """v19 workspace mode: Cecilia lives in <project>.cecilia/, the project folder gets nothing."""

    @classmethod
    def setUpClass(cls):
        base = Path(tempfile.mkdtemp()).resolve()
        cls.P = base / "shop"
        (cls.P / "app").mkdir(parents=True)
        (cls.P / "app" / "a.py").write_text("x = 1\n")
        (cls.P / ".github" / "workflows").mkdir(parents=True)
        (cls.P / ".github" / "workflows" / "ci.yml").write_text("name: ci\n")
        git(cls.P, "init", "-q", "-b", "main")
        git(cls.P, "add", "-A")
        git(cls.P, "commit", "-qm", "init")
        r = subprocess.run([PY, str(ROOT / "tools/install.py"), "--project", str(cls.P), "--workspace", "--host", "claude",
                            "--host", "antigravity", "--hook-form", "exec", "--apply"], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout[-800:] + r.stderr[-800:]
        cls.W = base / "shop.cecilia"
        cls.guard = cls.W / ".cecilia/bin/cecilia_guard.py"

    def hook(self, payload: dict, host="claude") -> str:
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
        r = subprocess.run([PY, str(self.guard), "--host", host, "--workspace", str(self.W)], input=json.dumps(payload),
                           capture_output=True, text=True, env=env)
        out = r.stdout
        for word in ("deny", "ask"):
            if f'"{word}"' in out:
                return word
        return "allow" if r.returncode == 0 else "error"

    def edit(self, path: Path, cwd=None) -> str:
        return self.hook({"tool_name": "Edit", "tool_input": {"file_path": str(path)}, "cwd": str(cwd or self.W)})

    def bash(self, cmd: str, cwd=None) -> str:
        return self.hook({"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(cwd or self.W)})

    def test_project_untouched(self):
        self.assertEqual(sorted(p.name for p in self.P.iterdir()), [".git", ".github", "app"])
        self.assertEqual(git(self.P, "status", "--porcelain").stdout, "")
        self.assertFalse((self.P / ".git/info/exclude").read_text().count("Cecilia"))
        cfg = json.loads((self.W / ".cecilia/config.json").read_text())
        self.assertEqual(cfg["workspace"]["project"], str(self.P))
        s = json.loads((self.W / ".claude/settings.json").read_text())
        self.assertEqual(s["permissions"]["additionalDirectories"], [str(self.P)])
        self.assertIn("--workspace", s["hooks"]["PreToolUse"][0]["hooks"][0]["args"])
        self.assertTrue(any(r.startswith("Read(//") for r in s["permissions"]["deny"]))
        self.assertIn("--workspace", (self.W / ".agents/hooks.json").read_text())

    def test_writes(self):
        self.assertEqual(self.edit(self.P / "app/a.py"), "deny")                 # main is protected
        git(self.P, "switch", "-qc", "bugfix/T-1")
        try:
            self.assertEqual(self.edit(self.P / "app/a.py"), "allow")
            self.assertEqual(self.edit(self.P / ".github/workflows/ci.yml"), "ask")   # infra profile
            self.assertEqual(self.edit(self.W / "tensura/reports/T-1/dev-be.md"), "allow")
            for p in (self.W / ".cecilia/mode.json", self.W / ".claude/settings.json", self.W / ".claude/skills/x.md",
                      self.W / ".agents/hooks.json", self.W / "CLAUDE.md", self.P / "tensura/r.md",
                      self.P / ".claude/skills/cecilia-x/SKILL.md", Path("/etc/cecilia-x")):
                self.assertEqual(self.edit(p), "deny", p)
        finally:
            git(self.P, "switch", "-q", "main")

    def test_symlink_into_controls(self):
        self.assertEqual(self.bash(f'ln -s "{self.W}/.cecilia" "{self.P}/cfg"', cwd=self.P), "deny")
        link = self.P / "cfglink"
        try:
            link.symlink_to(self.W / ".cecilia", target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("no symlinks here")
        git(self.P, "switch", "-qc", "bugfix/T-2")
        try:
            self.assertEqual(self.edit(link / "mode.json", cwd=self.P), "deny")
        finally:
            link.unlink()
            git(self.P, "switch", "-q", "main")

    def test_commands(self):
        self.assertEqual(self.bash(f'cd "{self.P}" && git push origin HEAD'), "deny")
        self.assertEqual(self.bash(f'git -C "{self.P}" status'), "allow")
        self.assertEqual(self.bash(f'echo x > "{self.W}/.cecilia/config.json"', cwd=self.P), "deny")
        ag = {"toolCall": {"name": "run_command", "args": {"CommandLine": "git push", "Cwd": str(self.P)}},
              "workspacePaths": [str(self.W), str(self.P)]}
        self.assertEqual(self.hook(ag, "antigravity"), "deny")

    def test_mode_and_check_find_the_project(self):
        self.assertEqual(M.git_root(self.W), self.P)
        r = subprocess.run([PY, str(self.W / ".claude/skills/cecilia-dev-be/scripts/cecilia_check.py"), "--task", "T-9",
                            "--steps", "secrets", "--offline"], cwd=self.W, capture_output=True, text=True)
        self.assertTrue((self.W / "tensura/reports/T-9/evidence.json").is_file(), r.stdout + r.stderr)
        self.assertFalse((self.P / "tensura").exists())
        ev = json.loads((self.W / "tensura/reports/T-9/evidence.json").read_text())
        self.assertEqual(ev["project"], str(self.P))

    def test_doctor(self):
        r = subprocess.run([PY, str(self.W / ".cecilia/bin/cecilia_doctor.py"), "--json", "--project", str(self.W)],
                           capture_output=True, text=True)
        res = {x["check"]: x["status"] for x in json.loads(r.stdout)["results"]}
        self.assertEqual(res.get("project untouched"), "OK")
        self.assertEqual(res.get("claude hook live"), "OK")
        self.assertEqual(res.get("antigravity hook live"), "OK")
        self.assertNotIn("FAIL", res.values())


class ContentSecrets(unittest.TestCase):
    """v19.2: the write hook refuses text that carries a real-looking credential."""

    def setUp(self):
        self.root = fixture()

    def write(self, text: str, host="claude") -> str:
        if host == "claude":
            data = {"tool_name": "Write", "tool_input": {"file_path": str(self.root / "src/a.py"), "content": text},
                    "cwd": str(self.root)}
        else:
            data = {"toolCall": {"name": "write_to_file", "args": {"TargetFile": str(self.root / "src/a.py"),
                                                                   "CodeContent": text}},
                    "workspacePaths": [str(self.root)]}
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.root))
        r = subprocess.run([PY, GUARD, "--host", host], input=json.dumps(data), capture_output=True, text=True, env=env)
        return "deny" if '"deny"' in r.stdout else "ok"

    def test_blocks_real_looking_keys(self):
        for text in ('AWS_KEY = "AKIA2E0A8F3B7C9D1E5F"', "-----BEGIN OPENSSH PRIVATE KEY-----\nabc",
                     'token = "ghp_' + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8" + '"',
                     'DB = "postgres://app:Zq9!vT4#pL2@db.internal:5432/app"'):
            self.assertEqual(self.write(text), "deny", text)
        self.assertEqual(self.write('k = "AKIA2E0A8F3B7C9D1E5F"', "antigravity"), "deny")

    def test_allows_placeholders(self):
        for text in ('key = os.environ["AWS_ACCESS_KEY_ID"]', 'AWS = "AKIAIOSFODNN7EXAMPLE"',
                     'DB = "postgres://user:password@localhost:5432/app"', "print('hello')"):
            self.assertEqual(self.write(text), "ok", text)


class WorkspaceTools(unittest.TestCase):
    """v19.2: status, lessons, scorecard, clean read the workspace; setup proposes a scale."""

    def setUp(self):
        base = Path(tempfile.mkdtemp()).resolve()
        self.ws, self.proj = base / "p.cecilia", base / "p"
        (self.ws / ".cecilia").mkdir(parents=True)
        (self.ws / "tensura/tasks/T-1").mkdir(parents=True)
        (self.ws / "tensura/reports/T-1").mkdir(parents=True)
        (self.ws / "tensura/tasks/T-1/state.md").write_text("Goal: g\nMode: standard\nNext: n\nPending: choose X\n")
        (self.ws / "tensura/reports/T-1/dev-be.md").write_text("Deviations: extra helper\n")
        (self.ws / "tensura/lessons.md").write_text("- L-01 keep money in cents [generic?]\n- L-02 local only [project]\n")
        self.proj.mkdir()
        git(self.proj, "init", "-q")

    def run_tool(self, *args) -> str:
        r = subprocess.run([PY, str(ROOT / "tools/workspace_tools.py"), *args, "--workspace", str(self.ws),
                            "--project", str(self.proj)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_views(self):
        self.assertIn("WAITING FOR YOU: choose X", self.run_tool("status"))
        out = self.run_tool("lessons")
        self.assertIn("L-01", out)
        self.assertNotIn("L-02", out)
        self.assertRegex(self.run_tool("scorecard"), r"cecilia-dev-be\s+1\s+1")
        self.assertIn("Nothing to clean", self.run_tool("clean"))

    def test_scale(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import setup as S  # noqa: E402
        found = {"backend": ["package.json"], "frontend": [], "api": [], "db": [], "infra": [], "tests": [],
                 "git": True, "mcp": {"context7": False, "sequential": False, "servers": []},
                 "services": 1, "source_files": 40}
        cfg, _ = S.propose(self.proj, found, self.ws)
        self.assertEqual(cfg["scale"], "small")
        self.assertFalse(cfg["roles"]["cecilia-plan"])
        found.update(services=4, source_files=5000)
        cfg, _ = S.propose(self.proj, found, self.ws)
        self.assertEqual((cfg["scale"], cfg["docs_layout"], cfg["review"]["panel"]["reviewers"]["standard"]), ("large", "microservices", 4))
