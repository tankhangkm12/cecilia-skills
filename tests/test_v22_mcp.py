"""Cecilia 20.2 — Antigravity-first MCP runner + control tools.  python3 -m unittest tests.test_v22_mcp -q
Never starts the real `agy` or `claude`."""
from __future__ import annotations

import datetime as dt
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from cecilia import mcp_server as M  # noqa: E402
from test_v21_approve import CLEAN, DEFECTS, Workspace  # noqa: E402

PY = sys.executable
APPROVE = str(ROOT / "guard" / "cecilia_approve.py")
MODE = str(ROOT / "guard" / "cecilia_mode.py")


def make_ws(base: Path, name="shop", agents=True) -> Path:
    proj = base / name
    proj.mkdir(parents=True)
    ws = base / f"{name}.cecilia"
    (ws / ".cecilia").mkdir(parents=True)
    (ws / ".cecilia" / "config.json").write_text(json.dumps({"workspace": {"project": str(proj)}}), encoding="utf-8")
    (ws / "tensura").mkdir()
    if agents:
        (ws / ".agents").mkdir()
    return ws


def call(name, **args):
    res = M.call_tool(name, args)
    text = res["content"][0]["text"]
    return res["isError"], (json.loads(text) if not res["isError"] else text)


def iso(seconds_ago=0):
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=seconds_ago)).isoformat(timespec="seconds")


def set_cfg(ws: Path, **mcp):
    f = ws / ".cecilia" / "config.json"
    cfg = json.loads(f.read_text())
    cfg.setdefault("mcp", {}).update(mcp)
    f.write_text(json.dumps(cfg))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name).resolve()
        self.ws = make_ws(self.base)
        self.agy_home = self.base / "agyhome"
        env = mock.patch.dict(os.environ, {"CECILIA_AGY_HOME": str(self.agy_home),
                                           "CECILIA_MCP_CONFIG": str(self.base / "no-mcp.json")})
        env.start()
        self.addCleanup(env.stop)
        for k in ("CECILIA_MCP_CONTROL", "CECILIA_AGY", "CECILIA_MCP"):
            os.environ.pop(k, None)

    def tearDown(self):
        self.tmp.cleanup()

    # a fake agy brain tree
    def conversation(self, cid, entries, age=0):
        logs = self.agy_home / "brain" / cid / ".system_generated" / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        (logs / "transcript.jsonl").write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
        if age:
            t = time.time() - age
            for p in (logs / "transcript.jsonl", self.agy_home / "brain" / cid):
                os.utime(p, (t, t))

    def agy_run(self, rid="R1", message="[via cecilia-mcp] build it", out=b"", err=b"", pid=None, started=None,
                **extra):
        d = self.ws / "tensura" / "runs"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{rid}.out").write_bytes(out)
        (d / f"{rid}.err").write_bytes(err)
        rec = {"id": rid, "prompt": "build it", "pid": pid, "started": started or iso(60), "status": "running",
               "session_id": None, "conversation_id": None, "host": "agy", "tasks": [],
               "turns": [{"n": 1, "kind": "start", "message": message, "pid": pid, "started": started or iso(60),
                          "out_offset": 0, "err_offset": 0}]}
        rec.update(extra)
        (d / f"{rid}.json").write_text(json.dumps(rec), encoding="utf-8")


def transcript(prompt="[via cecilia-mcp] build it", answer="Decision card written: tensura/decisions/SHOP-42.md"):
    return [{"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": prompt},
            {"type": "PLANNER_RESPONSE", "source": "MODEL", "content": "Reading tensura/tasks/SHOP-42/scope.json"},
            {"type": "TOOL_CALL", "source": "MODEL", "content": {"name": "view_file"}},
            {"type": "PLANNER_RESPONSE", "source": "MODEL", "content": [{"text": answer}]}]


class AutoHost(Base):
    def test_auto_picks_agy_then_claude_then_inbox(self):
        seen = {}

        def fake_spawn(ws, rec, message, kind, resume=None):
            seen.update(host=rec["host"], message=message, kind=kind)
            return {"n": 1, "pid": 4242}
        with mock.patch.object(M, "find_agy", return_value="/opt/agy"), \
                mock.patch.object(M, "find_claude", return_value="/opt/claude"), \
                mock.patch.object(M, "spawn_agy", side_effect=fake_spawn):
            err, out = call("cecilia_start_task", workspace=str(self.ws), prompt="build it")
        self.assertFalse(err, out)
        self.assertEqual((out["host"], seen["host"]), ("agy", "agy"))
        self.assertEqual(seen["message"], "[via cecilia-mcp] build it")
        shutil.rmtree(self.ws / ".agents")                        # no .agents/ -> not agy
        (self.ws / ".claude").mkdir()
        with mock.patch.object(M, "find_agy", return_value="/opt/agy"), \
                mock.patch.object(M, "find_claude", return_value="/opt/claude"), \
                mock.patch.object(M, "spawn_claude", return_value={"n": 1, "pid": 1}):
            self.assertEqual(call("cecilia_start_task", workspace=str(self.ws), prompt="x")[1]["host"], "claude")
        with mock.patch.object(M, "find_agy", return_value=None), mock.patch.object(M, "find_claude",
                                                                                    return_value=None):
            self.assertEqual(call("cecilia_start_task", workspace=str(self.ws), prompt="x")[1]["host"], "inbox")

    def test_agy_missing(self):
        with mock.patch.object(M, "find_agy", return_value=None):
            err, out = call("cecilia_start_task", workspace=str(self.ws), prompt="x", host="agy")
        self.assertTrue(err)
        self.assertIn("agy", out)
        with mock.patch.object(M, "find_agy", return_value=None), \
                mock.patch.object(M, "find_claude", return_value=None):
            self.assertEqual(call("cecilia_start_task", workspace=str(self.ws), prompt="x")[1]["host"], "inbox")


class Argv(Base):
    def test_args_skip_permissions_on_off_timeout_resume(self):
        a = M.agy_args(self.ws, "[via cecilia-mcp] hi")
        self.assertEqual(a, ["-p", "[via cecilia-mcp] hi", "--agent", "cecilia-orchestrator", "--output-format",
                             "json", "--print-timeout", "60m", "--dangerously-skip-permissions"])
        set_cfg(self.ws, agy_skip_permissions=False, agy_timeout_min=15)
        a = M.agy_args(self.ws, "m", resume="conv-123")
        self.assertNotIn("--dangerously-skip-permissions", a)
        self.assertIn("15m", a)
        self.assertEqual(a[-2:], ["--conversation", "conv-123"])
        (self.base / "u.json").write_text(json.dumps({"mcp": {"agy_timeout_min": 5}}))   # user-level fallback
        set_cfg(self.ws, agy_timeout_min=None)
        cfg = json.loads((self.ws / ".cecilia" / "config.json").read_text())
        del cfg["mcp"]["agy_timeout_min"]
        (self.ws / ".cecilia" / "config.json").write_text(json.dumps(cfg))
        with mock.patch.dict(os.environ, {"CECILIA_MCP_CONFIG": str(self.base / "u.json")}):
            self.assertIn("5m", M.agy_args(self.ws, "m"))

    def test_popen_stdin_devnull_and_env(self):
        seen = {}

        class P:
            pid = 99

            def poll(self):
                return None

        def fake_popen(cmd, **kw):
            seen.update(cmd=cmd, **kw)
            return P()
        rec = {"id": "R9", "host": "agy", "turns": []}
        with mock.patch.object(M, "find_agy", return_value="/opt/agy"), \
                mock.patch.object(M.subprocess, "Popen", side_effect=fake_popen), \
                mock.patch.dict(os.environ, {"CECILIA_MCP": "1"}):
            turn = M.spawn_agy(self.ws, rec, "[via cecilia-mcp] go", "start")
        M._PROCS.pop("R9", None)
        self.assertIs(seen["stdin"], subprocess.DEVNULL)
        self.assertEqual(seen["cmd"][0], "/opt/agy")
        self.assertEqual(seen["cmd"][1:3], ["-p", "[via cecilia-mcp] go"])
        self.assertEqual(Path(seen["cwd"]), self.ws)
        self.assertNotIn("CECILIA_MCP", seen["env"])               # runs never get the control unlock
        self.assertEqual(seen["env"]["CECILIA_VIA"], "mcp")
        self.assertEqual(Path(seen["stdout"].name).name, "R9.out")
        self.assertEqual(Path(seen["stderr"].name).name, "R9.err")
        self.assertEqual(turn["pid"], 99)

    def test_cmd_shim(self):
        d = self.base / "npm"
        (d / "node_modules" / "agy" / "bin").mkdir(parents=True)
        exe = d / "node_modules" / "agy" / "bin" / "agy.exe"
        exe.write_text("x")
        shim = d / "agy.cmd"
        shim.write_text('@ECHO off\r\nSETLOCAL\r\n"%dp0%\\node_modules\\agy\\bin\\agy.exe"   %*\r\n')
        self.assertEqual(M.agy_launcher(str(shim)), ([str(exe)], False))
        shim.write_text('@"%~dp0\\node.exe" "%~dp0\\node_modules\\agy\\cli.js" %*\r\n')
        (d / "node.exe").write_text("x")
        (d / "node_modules" / "agy" / "cli.js").write_text("x")
        self.assertEqual(M.agy_launcher(str(shim)), ([str(d / "node.exe"), str(d / "node_modules" / "agy" /
                                                                                   "cli.js")], False))
        shim.write_text("@echo off\r\ncall something-else %*\r\n")
        self.assertEqual(M.agy_launcher(str(shim)), ([str(shim)], True))
        line = M.cmd_shim_line([str(shim), "-p", "fix a & b | c\nnext line", "--agent", "x"])
        self.assertIn('"-p" "fix a & b | c next line"', line)
        self.assertIn("/d /v:off /s /c", line)
        for bad in ('say "hi"', "100% done"):
            with self.assertRaises(M.ToolError):
                M.cmd_shim_line([str(shim), "-p", bad])


@unittest.skipIf(os.name == "nt", "posix fake agy script")
class FakeAgy(Base):
    def test_run_finish_send_conversation(self):
        bindir = self.base / "bin"
        bindir.mkdir()
        fake = bindir / "agy"
        fake.write_text(
            f"#!{PY}\n"
            "import json, os, sys\n"
            "stdin_null = os.path.samestat(os.fstat(0), os.stat(os.devnull))\n"
            "n = len([f for f in os.listdir('tensura') if f.startswith('args-')])\n"
            "json.dump({'argv': sys.argv[1:], 'stdin_null': stdin_null, 'mcp': os.environ.get('CECILIA_MCP')},\n"
            "          open(f'tensura/args-{n}.json', 'w'))\n"
            "print('Loading agy...')\n"
            "print(json.dumps({'conversation_id': 'conv-77', 'status': 'SUCCESS',\n"
            "                  'response': 'Card ready. Run `cecilia approve tensura/plans/p.md --task SHOP-42`.',\n"
            "                  'error': None, 'usage': {'input_tokens': 10}}))\n", encoding="utf-8")
        fake.chmod(0o755)
        with mock.patch.dict(os.environ, {"PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
                                          "CECILIA_MCP": "1"}):
            err, out = call("cecilia_start_task", workspace=str(self.ws), prompt="build it")
            self.assertFalse(err, out)
            self.assertEqual(out["host"], "agy")
            rid = out["run_id"]
            v = self._wait(rid)
            self.assertEqual(v["status"], "finished", v)
            self.assertEqual(v["conversation_id"], "conv-77")
            self.assertEqual(v["conversation_from"], "json output")
            self.assertIn("Card ready", v["result"])
            self.assertEqual(v["usage"], {"input_tokens": 10})
            self.assertTrue(any("cecilia approve" in c for c in v["human_commands"]))
            err, out = call("cecilia_send", workspace=str(self.ws), run_id=rid, message="and tests")
            self.assertFalse(err, out)
            self.assertEqual(out["session_id"], "conv-77")
            v = self._wait(rid)
            self.assertEqual(v["turns"], 2)
        a0 = json.loads((self.ws / "tensura" / "args-0.json").read_text())
        a1 = json.loads((self.ws / "tensura" / "args-1.json").read_text())
        self.assertTrue(a0["stdin_null"])
        self.assertIsNone(a0["mcp"])
        self.assertEqual(a0["argv"][:8], ["-p", "[via cecilia-mcp] build it", "--agent", "cecilia-orchestrator",
                                          "--output-format", "json", "--print-timeout", "60m"])
        self.assertIn("--dangerously-skip-permissions", a0["argv"])
        self.assertNotIn("--conversation", a0["argv"])
        self.assertEqual(a1["argv"][1], "[via cecilia-mcp] and tests")
        self.assertEqual(a1["argv"][-2:], ["--conversation", "conv-77"])

    def test_cancel_kills_agy(self):
        p = subprocess.Popen(["sleep", "30"], start_new_session=True)
        self.addCleanup(lambda: (p.kill(), p.wait()))
        self.agy_run(pid=p.pid, started=iso(5))
        M._PROCS["R1"] = p
        self.addCleanup(M._PROCS.pop, "R1", None)
        self.assertEqual(call("cecilia_run", workspace=str(self.ws), run_id="R1")[1]["status"], "running")
        err, out = call("cecilia_cancel", workspace=str(self.ws), run_id="R1")
        self.assertFalse(err, out)
        self.assertTrue(out["killed"])
        p.wait(timeout=10)
        self.assertEqual(call("cecilia_run", workspace=str(self.ws), run_id="R1")[1]["status"], "cancelled")

    def test_wall_clock_timeout(self):
        p = subprocess.Popen(["sleep", "30"], start_new_session=True)
        self.addCleanup(lambda: (p.kill(), p.wait()))
        M._PROCS["R1"] = p
        self.addCleanup(M._PROCS.pop, "R1", None)
        set_cfg(self.ws, agy_timeout_min=1)
        self.agy_run(pid=p.pid, started=iso(3600))
        v = call("cecilia_run", workspace=str(self.ws), run_id="R1")[1]
        self.assertEqual(v["status"], "failed")
        self.assertIn("wall-clock", v["hint"])
        p.wait(timeout=10)

    def _wait(self, rid):
        for _ in range(100):
            err, v = call("cecilia_run", workspace=str(self.ws), run_id=rid)
            if v["status"] != "running":
                return v
            time.sleep(0.1)
        return v


class Envelope(Base):
    def test_parse_variants(self):
        self.assertIsNone(M.parse_envelope(b""))
        self.assertIsNone(M.parse_envelope(b"just text\n"))
        env = {"conversation_id": "c-1", "status": "SUCCESS", "response": "ok"}
        self.assertEqual(M.parse_envelope(json.dumps(env).encode()), env)
        self.assertEqual(M.parse_envelope(b"banner\n" + json.dumps(env, indent=2).encode() + b"\ntrailer"), env)

    def test_error_and_waiting(self):
        self.agy_run(out=json.dumps({"conversation_id": "c-err", "status": "ERROR", "response": "",
                                     "error": "quota exceeded"}).encode(), err=b"warn: something\n")
        v = call("cecilia_run", workspace=str(self.ws), run_id="R1")[1]
        self.assertEqual((v["status"], v["agy_status"], v["error"]), ("failed", "ERROR", "quota exceeded"))
        self.assertEqual(v["output_other"], ["warn: something"])
        self.agy_run("R2", out=json.dumps({"conversation_id": "c-w", "status": "WAITING",
                                           "response": "need approval"}).encode())
        v = call("cecilia_run", workspace=str(self.ws), run_id="R2")[1]
        self.assertEqual(v["status"], "finished")
        self.assertIn("waiting", v["hint"])

    def test_no_output_no_transcript_fails(self):
        self.agy_run(err=b"Error: not logged in\n")
        v = call("cecilia_run", workspace=str(self.ws), run_id="R1")[1]
        self.assertEqual(v["status"], "failed")
        self.assertIn("not logged in", v["output_other"][0])
        self.assertIn("stderr", v["hint"])


class Recovery(Base):
    def test_last_conversations_map(self):
        self.conversation("c-main", transcript())
        self.conversation("c-old", transcript(answer="old"), age=7200)
        cache = self.agy_home / "cache"
        cache.mkdir(parents=True)
        (cache / "last_conversations.json").write_text(json.dumps(
            {str(self.base / "elsewhere"): {"conversationId": "c-old"},
             str(self.ws): {"conversationId": "c-main", "updatedAt": "now"}}))
        self.agy_run()
        err, v = call("cecilia_run", workspace=str(self.ws), run_id="R1")
        self.assertFalse(err, v)
        self.assertEqual(v["status"], "finished")
        self.assertEqual(v["conversation_id"], "c-main")
        self.assertEqual(v["conversation_from"], "last_conversations.json")
        self.assertTrue(v["recovered_from_transcript"])
        self.assertEqual(v["result"], "Decision card written: tensura/decisions/SHOP-42.md")
        self.assertEqual(v["tasks"], ["SHOP-42"])
        self.assertIn("transcript", v["hint"])
        rec = json.loads((self.ws / "tensura" / "runs" / "R1.json").read_text())
        self.assertEqual((rec["conversation_id"], rec["session_id"], rec["status"]), ("c-main", "c-main", "finished"))

    def test_last_conversations_list_and_file_uri(self):
        self.conversation("c-list", transcript())
        cache = self.agy_home / "cache"
        cache.mkdir(parents=True)
        uri = "file://" + ("/" if not str(self.ws).startswith("/") else "") + str(self.ws).replace("\\", "/")
        for shape in ([{"cwd": str(self.ws), "conversation_id": "c-list"}],
                      {"conversations": [{"workspacePaths": [uri], "id": "c-list"}]},
                      {uri: "c-list"}):
            with self.subTest(shape=shape):
                self.assertEqual(M.last_conversation_ids(shape, self.ws), ["c-list"])
        self.assertEqual(M.last_conversation_ids({"weird": 1, "x": [None, 3]}, self.ws), [])

    def test_brain_scan_prefers_prompt_then_skips_subagents(self):
        self.conversation("c-stale", transcript(answer="stale"), age=7200)
        self.conversation("c-main", transcript())
        time.sleep(0.02)
        self.conversation("c-sub", [{"type": "USER_INPUT", "content": "[cecilia-brief TASK=SHOP-42 ROLE=dev-be]\n..."},
                                    {"type": "PLANNER_RESPONSE", "content": "sub answer"}])
        self.agy_run()
        v = call("cecilia_run", workspace=str(self.ws), run_id="R1")[1]
        self.assertEqual((v["conversation_id"], v["conversation_from"]), ("c-main", "transcript (prompt match)"))
        self.assertEqual(v["status"], "finished")
        # prompt not found (e.g. agy rewrote it): newest non-subagent conversation since the start
        self.agy_run("R2", message="[via cecilia-mcp] something else")
        cid, how = M.recover_conversation(self.ws, iso(60), "[via cecilia-mcp] something else", exclude={"c-zzz"})
        self.assertEqual((cid, how), ("c-main", "brain (newest since start)"))
        self.assertEqual(M.recover_conversation(self.ws, iso(60), "x", exclude={"c-main"}), (None, None))

    def test_running_while_alive_and_resume_turn(self):
        self.conversation("c-main", transcript())
        self.agy_run(pid=os.getpid(), started=iso(5))
        v = call("cecilia_run", workspace=str(self.ws), run_id="R1")[1]
        self.assertEqual((v["status"], v["result"]), ("running", None))
        self.assertEqual(v["conversation_id"], "c-main")            # recovered while running, for cecilia_send later
        # second turn resumed the conversation; answer only counts after our follow-up message
        rec = json.loads((self.ws / "tensura" / "runs" / "R1.json").read_text())
        rec["pid"] = None
        rec["turns"].append({"n": 2, "kind": "send", "message": "[via cecilia-mcp] and tests", "pid": None,
                             "started": iso(1), "out_offset": 0, "err_offset": 0, "resume": "c-main",
                             "transcript_len": 4})
        (self.ws / "tensura" / "runs" / "R1.json").write_text(json.dumps(rec))
        v = call("cecilia_run", workspace=str(self.ws), run_id="R1")[1]
        self.assertEqual(v["status"], "failed")                     # no new answer for turn 2
        self.conversation("c-main", transcript() + [{"type": "USER_INPUT", "content": "[via cecilia-mcp] and tests"},
                                                    {"type": "PLANNER_RESPONSE", "content": "tests added"}])
        v = call("cecilia_run", workspace=str(self.ws), run_id="R1")[1]
        self.assertEqual((v["status"], v["result"]), ("finished", "tests added"))

    def test_send_uses_conversation(self):
        self.agy_run(out=json.dumps({"conversation_id": "conv-5", "status": "SUCCESS", "response": "ok"}).encode())
        seen = {}

        def fake_spawn(ws, rec, message, kind, resume=None):
            seen.update(resume=resume, message=message, host=rec["host"])
            return {"n": 2, "pid": 1}
        with mock.patch.object(M, "spawn_agy", side_effect=fake_spawn), \
                mock.patch.object(M, "spawn_claude", side_effect=AssertionError("wrong host")):
            err, out = call("cecilia_send", workspace=str(self.ws), run_id="R1", message="more")
        self.assertFalse(err, out)
        self.assertEqual(seen, {"resume": "conv-5", "message": "[via cecilia-mcp] more", "host": "agy"})


class Control(Base):
    def run_ok(self, stdout="done", code=0):
        calls = []

        def fake_run(cmd, **kw):
            calls.append((cmd, kw))
            return subprocess.CompletedProcess(cmd, code, stdout=stdout, stderr="")
        return calls, mock.patch.object(M.subprocess, "run", side_effect=fake_run)

    def audit_lines(self):
        f = self.ws / "tensura" / "audit" / "control.jsonl"
        return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines()] if f.is_file() else []

    def test_each_control_tool_runs_cli_with_yes(self):
        (self.ws / "tensura" / "plans").mkdir()
        (self.ws / "tensura" / "plans" / "p.md").write_text("plan", encoding="utf-8")
        (self.ws / "tensura" / "extensions" / "new-role").mkdir(parents=True)
        cases = [
            ("cecilia_mode", {"mode": "controlled"}, ["mode", "--yes", "--by", "mcp", "controlled"]),
            ("cecilia_approve", {"plan": "plans/p.md", "all": True, "hours": 24},
             ["approve", "--yes", "--by", "mcp", str(self.ws / "tensura" / "plans" / "p.md"), "--all", "--hours",
              "24"]),
            ("cecilia_flow", {"flow": "team"}, ["flow", "--yes", "--by", "mcp", "team"]),
            ("cecilia_rules_add", {"text": "Run  the unit tests\nbefore a report", "role": "dev-be"},
             ["rules", "add", "--yes", "--by", "mcp", "--role", "dev-be", "Run the unit tests before a report"]),
            ("cecilia_extension_apply", {"dir": "new-role"},
             ["extension", "apply", "--yes", "--by", "mcp", str(self.ws / "tensura" / "extensions" / "new-role")]),
            ("cecilia_push", {"args": ["origin", "-u", "feature/x"]},
             ["push", "--yes", "--by", "mcp", "origin", "-u", "feature/x"]),
        ]
        for name, args, expect in cases:
            with self.subTest(name):
                calls, patch = self.run_ok()
                with patch, mock.patch.dict(os.environ, {"CECILIA_MCP": ""}):
                    err, out = call(name, workspace=str(self.ws), **args)
                self.assertFalse(err, out)
                cmd, kw = calls[0]
                self.assertEqual(cmd[:3], [sys.executable, "-m", "cecilia.cli"])
                self.assertEqual(cmd[3:], expect)
                self.assertEqual(kw["env"]["CECILIA_MCP"], "1")
                self.assertEqual(Path(kw["cwd"]), self.ws)
                self.assertIs(kw["stdin"], subprocess.DEVNULL)
                self.assertEqual(out["output"], "done")
        lines = self.audit_lines()
        self.assertEqual([x["command"] for x in lines],
                         ["mode", "approve", "flow", "rules add", "extension apply", "push"])
        self.assertEqual({x["by"] for x in lines}, {"mcp"})
        self.assertEqual({x["result"] for x in lines}, {"ok"})
        self.assertEqual(lines[0]["args"], ["controlled"])
        self.assertTrue(all(set(x) >= {"ts", "by", "command", "args", "result"} for x in lines))

    def test_failure_returns_output_and_audits(self):
        (self.ws / "tensura" / "plans").mkdir()
        (self.ws / "tensura" / "plans" / "p.md").write_text("plan", encoding="utf-8")
        calls, patch = self.run_ok(stdout="ERROR [K8S-7-B01] unresolved variable $X\nApproval blocked", code=1)
        with patch:
            err, out = call("cecilia_approve", workspace=str(self.ws), plan="tensura/plans/p.md", task="K8S-7-B01")
        self.assertTrue(err)
        self.assertIn("unresolved variable $X", out)
        self.assertEqual(self.audit_lines()[-1]["result"], "failed")
        self.assertEqual(self.audit_lines()[-1]["exit"], 1)
        calls, patch = self.run_ok(stdout="usage: ... error: unrecognized arguments: --yes --by mcp", code=2)
        with patch:
            err, out = call("cecilia_mode", workspace=str(self.ws), mode="fast")
        self.assertIn("cecilia upgrade", out)

    def test_argument_validation(self):
        calls, patch = self.run_ok()
        with patch:
            for name, args in [("cecilia_mode", {"mode": "yolo"}),
                               ("cecilia_approve", {"plan": "../.cecilia/config.json"}),
                               ("cecilia_approve", {"plan": "plans/missing.md"}),
                               ("cecilia_rules_add", {"text": "x"}),
                               ("cecilia_rules_add", {"text": "x", "role": "dev-be", "project": True}),
                               ("cecilia_flow", {"flow": "Team; rm -rf"}),
                               ("cecilia_extension_apply", {"dir": "nope"}),
                               ("cecilia_push", {"args": ["--force"]}),
                               ("cecilia_push", {"args": ["-f"]}),
                               ("cecilia_push", {"args": ["origin", "+main"]}),
                               ("cecilia_push", {"args": ["origin", ":main"]}),
                               ("cecilia_push", {"args": ["--receive-pack=sh -c id"]}),
                               ("cecilia_push", {"args": ["ext::sh -c id"]}),
                               ("cecilia_push", {"args": ["https://evil.example/x.git"]}),
                               ("cecilia_push", {"args": "origin"})]:
                with self.subTest(name=name, args=args):
                    self.assertTrue(call(name, workspace=str(self.ws), **args)[0])
        self.assertEqual(calls, [])

    def test_control_none_hides_tools_and_refuses(self):
        base = {t["name"] for t in M.tools_list()}
        self.assertTrue(set(M.CONTROL_TOOLS) <= base)
        (self.base / "u.json").write_text(json.dumps({"mcp": {"control": "none"}}))
        with mock.patch.dict(os.environ, {"CECILIA_MCP_CONFIG": str(self.base / "u.json")}):
            names = {t["name"] for t in M.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
                     ["result"]["tools"]}
            self.assertFalse(names & set(M.CONTROL_TOOLS))
            self.assertIn("cecilia_start_task", names)
            r = M.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                          "params": {"name": "cecilia_mode", "arguments": {"workspace": str(self.ws), "mode": "fast"}}})
            self.assertEqual(r["error"]["code"], -32602)
        with mock.patch.dict(os.environ, {"CECILIA_MCP_CONTROL": "mode,approve"}):
            names = {t["name"] for t in M.tools_list()}
            self.assertEqual(names & set(M.CONTROL_TOOLS), {"cecilia_mode", "cecilia_approve"})
        with mock.patch.dict(os.environ, {"CECILIA_MCP_CONTROL": "bogus"}):
            self.assertFalse({t["name"] for t in M.tools_list()} & set(M.CONTROL_TOOLS))   # fails closed
        set_cfg(self.ws, control="none")                              # per-workspace switch
        calls, patch = self.run_ok()
        with patch:
            err, out = call("cecilia_mode", workspace=str(self.ws), mode="fast")
        self.assertTrue(err)
        self.assertIn("human-only", out)
        self.assertEqual(calls, [])
        st = call("cecilia_status", workspace=str(self.ws))[1]
        self.assertEqual(st["control_tools"], [])
        self.assertIn("cecilia approve", st["human_only"])

    def test_real_cli_mode_end_to_end(self):
        """cecilia_mode -> `python -m cecilia.cli mode --yes --by mcp controlled` -> .cecilia/bin/cecilia_mode.py."""
        (self.ws / ".cecilia" / "bin").mkdir()
        shutil.copy(MODE, self.ws / ".cecilia" / "bin" / "cecilia_mode.py")
        err, out = call("cecilia_mode", workspace=str(self.ws), mode="controlled")
        self.assertFalse(err, out)
        rec = json.loads((self.ws / ".cecilia" / "mode.json").read_text())
        self.assertEqual((rec["mode"], rec["set_by"]), ("controlled", "mcp"))
        self.assertEqual(self.audit_lines()[-1]["result"], "ok")
        self.assertNotIn("CECILIA_MCP", os.environ)                 # the server's own env is untouched


def run(cmd, cwd, mcp=False, **kw):
    env = {k: v for k, v in os.environ.items() if k != "CECILIA_MCP"}
    env["PYTHONPATH"] = str(ROOT / "src")
    if mcp:
        env["CECILIA_MCP"] = "1"
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL,
                          timeout=120, **kw)


class YesPath(unittest.TestCase):
    """`--yes --by` on the human-only commands: refused without CECILIA_MCP=1, non-interactive with it."""

    def setUp(self):
        self.w = Workspace()

    def test_approve_yes_refused_without_env(self):
        plan = self.w.plan(CLEAN)
        r = run([PY, APPROVE, str(plan), "--yes", "--by", "mcp"], self.w.ws)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--yes is only for the Cecilia MCP server", r.stderr)
        self.assertEqual(self.w.approvals(), [])
        r = run([PY, APPROVE, str(plan), "--by", "mcp"], self.w.ws, mcp=True)
        self.assertEqual(r.returncode, 2)

    def test_approve_yes_with_env(self):
        plan = self.w.plan(CLEAN)
        r = run([PY, APPROVE, str(plan), "--yes", "--by", "mcp"], self.w.ws, mcp=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.w.approvals(), ["K8S-7-B01"])
        rec = json.loads((self.w.ws / ".cecilia" / "approvals" / "K8S-7-B01.json").read_text())
        self.assertEqual((rec["approved_by"], rec["non_interactive"]), ("mcp", True))

    def test_approve_all_yes_and_lint_still_blocks(self):
        scopes = [dict(CLEAN, task=f"K8S-7-B0{i}") for i in (1, 2)]
        plan = self.w.plan(*scopes)
        r = run([PY, APPROVE, str(plan), "--all", "--yes", "--by", "mcp"], self.w.ws, mcp=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.w.approvals(), ["K8S-7-B01", "K8S-7-B02"])
        w2 = Workspace()
        bad = w2.plan(dict(CLEAN, commands=[DEFECTS["swallow"][0]]))
        r = run([PY, APPROVE, str(bad), "--yes", "--by", "mcp"], w2.ws, mcp=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("|| true", r.stdout)
        self.assertEqual(w2.approvals(), [])

    def test_interactive_path_unchanged(self):
        plan = self.w.plan(CLEAN)
        r = run([PY, APPROVE, str(plan)], self.w.ws, mcp=True)          # env alone does not skip the terminal
        self.assertEqual(r.returncode, 2)
        self.assertIn("interactive terminal", r.stderr)

    def test_mode_yes(self):
        r = run([PY, MODE, "fast", "--yes", "--by", "mcp"], self.w.ws)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--yes is only for the Cecilia MCP server", r.stderr)
        self.assertFalse((self.w.ws / ".cecilia" / "mode.json").exists())
        r = run([PY, MODE, "fast"], self.w.ws, mcp=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn("interactive terminal", r.stderr)
        r = run([PY, MODE, "fast", "--yes", "--by", "mcp"], self.w.ws, mcp=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads((self.w.ws / ".cecilia" / "mode.json").read_text())["set_by"], "mcp")
        r = run([PY, MODE, "push", "--yes"], self.w.ws)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--yes is only", r.stderr)

    def test_cli_flow_and_rules_yes(self):
        cli = [PY, "-m", "cecilia.cli"]
        r = run(cli + ["flow", "team", "--yes", "--by", "mcp"], self.w.ws)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--yes is only for the Cecilia MCP server", r.stderr)
        for sub in (["push", "--yes"], ["mode", "fast", "--yes"], ["approve", "x.md", "--yes"],
                    ["extension", "apply", "x", "--yes"], ["rules", "add", "--project", "x", "--yes"]):
            with self.subTest(sub):
                r = run(cli + sub, self.w.ws)
                self.assertEqual(r.returncode, 2)
                self.assertIn("--yes is only", r.stderr)
        r = run(cli + ["flow", "team", "--yes", "--by", "mcp"], self.w.ws, mcp=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads((self.w.ws / ".cecilia" / "config.json").read_text())["flow"], "team")
        r = run(cli + ["flow", "nosuch", "--yes", "--by", "mcp"], self.w.ws, mcp=True)
        self.assertEqual(r.returncode, 2)
        r = run(cli + ["rules", "add", "--yes", "--by", "mcp", "--project", "Run the unit tests before a report"],
                self.w.ws, mcp=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Run the unit tests before a report", (self.w.ws / "rules" / "_project.md").read_text())
        r = run(cli + ["rules", "add", "--yes", "--by", "mcp", "--project", "Pushing to main is fine without asking"],
                self.w.ws, mcp=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("loosens", r.stdout)
        r = run(cli + ["rules", "list", "--yes"], self.w.ws, mcp=True)
        self.assertEqual(r.returncode, 2)


class Config(unittest.TestCase):
    def test_print_config_has_antigravity(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(M.main(["--print-config"]), 0)
        out = buf.getvalue()
        self.assertIn("Antigravity", out)
        self.assertIn("mcp_config.json", out)
        self.assertIn('"command": "cecilia"', out)
        self.assertIn("CECILIA_MCP_CONTROL", out)

    def test_instructions(self):
        r = M.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})["result"]["instructions"]
        for needle in ("agy", "human-only", "control.jsonl", "cecilia_approve", "transcript"):
            self.assertIn(needle, r)


if __name__ == "__main__":
    unittest.main()
