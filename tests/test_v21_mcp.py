"""Cecilia 20.1 — `cecilia mcp` server (src/cecilia/mcp_server.py). Never spawns the real `claude`."""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cecilia import mcp_server as M  # noqa: E402


def make_ws(base: Path, name="shop") -> Path:
    proj = base / name
    proj.mkdir(parents=True)
    ws = base / f"{name}.cecilia"
    (ws / ".cecilia").mkdir(parents=True)
    (ws / ".cecilia" / "config.json").write_text(json.dumps({"workspace": {"project": str(proj)}}), encoding="utf-8")
    (ws / "tensura").mkdir()
    return ws


def call(name, **args):
    res = M.call_tool(name, args)
    text = res["content"][0]["text"]
    return res["isError"], (json.loads(text) if not res["isError"] else text)


SAMPLE = [
    {"type": "system", "subtype": "init", "session_id": "sess-1", "model": "opus"},
    {"type": "assistant", "message": {"content": [{"type": "text", "text": "Reading the scope."},
                                                  {"type": "tool_use", "name": "Write",
                                                   "input": {"file_path": "tensura/tasks/SHOP-42/scope.json"}}]}},
    {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}},
    {"type": "assistant", "message": {"content": [{"type": "text", "text": "Card ready. Please run "
                                                   "`cecilia approve tensura/plans/p.md --task SHOP-42` yourself."}]}},
    {"type": "result", "subtype": "success", "is_error": False, "result": "Decision card written.",
     "total_cost_usd": 0.25, "session_id": "sess-1", "num_turns": 4},
]


def write_run(ws: Path, rid="R1", events=SAMPLE, pid=None, status="running", extra=b""):
    d = ws / "tensura" / "runs"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{rid}.jsonl").write_bytes(b"".join(json.dumps(e).encode() + b"\n" for e in events) + extra)
    rec = {"id": rid, "prompt": "p", "pid": pid, "started": "2026-09-29T10:00:00+00:00", "status": status,
           "session_id": None, "turns": [{"n": 1, "kind": "start", "pid": pid, "offset": 0}]}
    (d / f"{rid}.json").write_text(json.dumps(rec), encoding="utf-8")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name).resolve()
        self.ws = make_ws(self.base)

    def tearDown(self):
        self.tmp.cleanup()


class Protocol(unittest.TestCase):
    def test_initialize_versions(self):
        r = M.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                      "params": {"protocolVersion": "2024-11-05", "capabilities": {}}})["result"]
        self.assertEqual(r["protocolVersion"], "2024-11-05")
        self.assertEqual(r["serverInfo"], {"name": "cecilia", "version": M.__version__})
        self.assertEqual(r["capabilities"], {"tools": {}})
        self.assertIn("human-only", r["instructions"])
        r = M.handle({"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {"protocolVersion": "1999-01-01"}})
        self.assertEqual(r["result"]["protocolVersion"], "2025-06-18")

    def test_tools_list_has_no_human_only_tools(self):
        with mock.patch.dict(os.environ, {"CECILIA_MCP_CONTROL": "none"}):     # 20.2: control tools switched off
            names = {t["name"] for t in M.handle({"jsonrpc": "2.0", "id": 1,
                                                  "method": "tools/list"})["result"]["tools"]}
        self.assertEqual(names, {"cecilia_workspaces", "cecilia_status", "cecilia_start_task", "cecilia_run",
                                 "cecilia_send", "cecilia_decision", "cecilia_decide", "cecilia_read",
                                 "cecilia_cancel"})
        for bad in ("approve", "mode", "flow", "push", "rules", "extension", "exec", "write"):
            self.assertFalse(any(bad in n for n in names), bad)

    def test_unknown_method_and_tool(self):
        self.assertEqual(M.handle({"jsonrpc": "2.0", "id": 3, "method": "nope"})["error"]["code"], -32601)
        self.assertEqual(M.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                                   "params": {"name": "cecilia_exec"}})["error"]["code"], -32602)
        self.assertIsNone(M.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_stdio_subprocess(self):
        msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "ping"},
                {"jsonrpc": "2.0", "id": 4, "method": "bogus"},
                {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                 "params": {"name": "cecilia_status", "arguments": {}}}]
        data = "".join(json.dumps(m) + "\n" for m in msgs) + "{not json\n"
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), CECILIA_MCP_CONTROL="none")
        p = subprocess.run([sys.executable, "-m", "cecilia.mcp_server"], input=data.encode("utf-8"),
                           capture_output=True, env=env, timeout=60)
        out = [json.loads(x) for x in p.stdout.decode("utf-8").splitlines() if x.strip()]
        self.assertEqual([o.get("id") for o in out], [1, 2, 3, 4, 5, None])
        self.assertEqual(out[0]["result"]["protocolVersion"], "2025-03-26")
        self.assertEqual(len(out[1]["result"]["tools"]), 9)
        self.assertEqual(out[2]["result"], {})
        self.assertEqual(out[3]["error"]["code"], -32601)
        self.assertTrue(out[4]["result"]["isError"])
        self.assertEqual(out[5]["error"]["code"], -32700)
        self.assertIn(b"cecilia-mcp", p.stderr)


class Workspaces(Base):
    def test_registry_name_and_scan(self):
        reg = self.base / "workspaces.json"
        reg.write_text(json.dumps({"workspaces": [{"workspace": str(self.ws), "project": str(self.base / "shop"),
                                                   "name": "shop", "updated": "x"}]}), encoding="utf-8")
        with mock.patch.object(M, "registry_file", return_value=reg):
            err, out = call("cecilia_workspaces", root=str(self.base))
            self.assertFalse(err)
            self.assertTrue(out["workspaces"][0]["exists"])
            self.assertEqual([w["workspace"] for w in out["scanned"]["workspaces"]], [str(self.ws)])
            self.assertEqual(M.resolve_workspace("shop"), self.ws)
        self.assertEqual(M.resolve_workspace(str(self.base / "shop")), self.ws)       # project path works too
        with self.assertRaises(M.ToolError):
            M.resolve_workspace(str(self.base / "nothing"))

    def test_status(self):
        t = self.ws / "tensura" / "tasks" / "SHOP-42"
        t.mkdir(parents=True)
        (t / "state.md").write_text("# SHOP-42\nphase: plan\n", encoding="utf-8")
        (t / "scope.json").write_text("{}", encoding="utf-8")
        done = self.ws / "tensura" / "tasks" / "SHOP-1"
        done.mkdir()
        (done / "state.md").write_text("status: done\n", encoding="utf-8")
        d = self.ws / "tensura" / "decisions"
        d.mkdir()
        (d / "SHOP-42.json").write_text(json.dumps({"task": "SHOP-42", "status": "open", "options": [
            {"id": "A"}, {"id": "B", "recommended": True}], "questions": [{"id": "Q1"}]}), encoding="utf-8")
        (self.ws / ".cecilia" / "mode.json").write_text("{broken", encoding="utf-8")
        err, out = call("cecilia_status", workspace=str(self.ws))
        self.assertFalse(err, out)
        self.assertEqual(out["mode"], "controlled")                        # malformed -> controlled, like the guard
        self.assertEqual([x["task"] for x in out["open_tasks"]], ["SHOP-42"])
        self.assertEqual(out["open_tasks"][0]["phase"], "scoped")
        self.assertEqual(out["closed_tasks"], 1)
        self.assertEqual(out["open_decisions"][0]["recommended"], "B")


class StartTask(Base):
    def test_inbox_via_workflow(self):
        err, out = call("cecilia_start_task", workspace=str(self.ws), prompt="--add a cart page", host="inbox")
        self.assertFalse(err, out)
        files = list((self.ws / "tensura" / "inbox").glob("*.json"))
        self.assertEqual(len(files), 1)
        item = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertEqual(item["source"], "mcp")
        self.assertEqual(item["status"], "new")
        self.assertTrue(item["prompt"].startswith("[via cecilia-mcp] --add a cart page"))

    def test_inbox_fallback_when_workflow_lacks_inbox(self):
        with mock.patch.object(M, "run_workflow", return_value=(2, "error: argument cmd: invalid choice: 'inbox'")):
            err, out = call("cecilia_start_task", workspace=str(self.ws), prompt="x", host="inbox")
        self.assertFalse(err, out)
        item = out["item"]
        self.assertEqual(set(item), {"id", "prompt", "source", "created", "status", "task"})
        self.assertTrue((self.ws / "tensura" / "inbox" / f"{item['id']}.json").is_file())

    def test_auto_without_claude_goes_to_inbox(self):
        with mock.patch.object(M, "find_claude", return_value=None):
            err, out = call("cecilia_start_task", workspace=str(self.ws), prompt="x")
        self.assertEqual(out["host"], "inbox")

    def test_claude_missing_and_bypass_refused(self):
        with mock.patch.object(M, "find_claude", return_value=None):
            err, out = call("cecilia_start_task", workspace=str(self.ws), prompt="x", host="claude")
        self.assertTrue(err)
        cfg = json.loads((self.ws / ".cecilia" / "config.json").read_text())
        cfg["mcp"] = {"permission_mode": "bypassPermissions"}
        (self.ws / ".cecilia" / "config.json").write_text(json.dumps(cfg))
        with mock.patch.object(M, "find_claude", return_value="/bin/true"):
            err, out = call("cecilia_start_task", workspace=str(self.ws), prompt="x", host="claude")
        self.assertTrue(err)
        self.assertIn("never bypasses", out)

    @unittest.skipIf(os.name == "nt", "posix fake claude script")
    def test_spawn_with_fake_claude_then_resume_and_cancel(self):
        bindir = self.base / "bin"
        bindir.mkdir()
        fake = bindir / "claude"
        fake.write_text(
            "#!/bin/sh\n"
            "echo \"$@\" > \"$PWD/tensura/args-$$.txt\"\n"
            "prompt=$(cat)\n"
            "case \"$prompt\" in *SLEEP*) sleep 30;; esac\n"
            "echo '{\"type\":\"system\",\"subtype\":\"init\",\"session_id\":\"s-9\"}'\n"
            "printf '%s\\n' \"{\\\"type\\\":\\\"assistant\\\",\\\"message\\\":{\\\"content\\\":[{\\\"type\\\":\\\"text\\\","
            "\\\"text\\\":\\\"got it\\\"}]}}\"\n"
            "echo '{\"type\":\"result\",\"subtype\":\"success\",\"is_error\":false,\"result\":\"done\","
            "\"total_cost_usd\":0.5,\"session_id\":\"s-9\"}'\n", encoding="utf-8")
        fake.chmod(0o755)
        (self.ws / ".claude").mkdir()
        with mock.patch.dict(os.environ, {"PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"}):
            err, out = call("cecilia_start_task", workspace=str(self.ws), prompt="build it")
            self.assertFalse(err, out)
            self.assertEqual(out["host"], "claude")
            rid = out["run_id"]
            view = self._wait(rid)
            self.assertEqual(view["status"], "finished")
            self.assertEqual(view["session_id"], "s-9")
            self.assertEqual(view["total_cost_usd"], 0.5)
            err, out = call("cecilia_send", workspace=str(self.ws), run_id=rid, message="and tests")
            self.assertFalse(err, out)
            view = self._wait(rid)
            self.assertEqual(view["turns"], 2)
            self.assertEqual(view["total_cost_usd"], 1.0)
            args = " ".join(p.read_text() for p in (self.ws / "tensura").glob("args-*.txt"))
            self.assertIn("--resume s-9", args)
            self.assertIn("--permission-mode acceptEdits", args)
            self.assertIn("--agent cecilia-orchestrator", args)
            self.assertNotIn("dangerously", args)
            self.assertNotIn("bypass", args)
            err, out = call("cecilia_send", workspace=str(self.ws), run_id=rid, message="SLEEP")
            self.assertFalse(err, out)
            err, out = call("cecilia_send", workspace=str(self.ws), run_id=rid, message="again")
            self.assertTrue(err)
            self.assertIn("wait until the run finishes", out)
            err, out = call("cecilia_cancel", workspace=str(self.ws), run_id=rid)
            self.assertFalse(err, out)
            self.assertTrue(out["killed"])
            self.assertEqual(call("cecilia_run", workspace=str(self.ws), run_id=rid)[1]["status"], "cancelled")

    def _wait(self, rid):
        for _ in range(100):
            err, view = call("cecilia_run", workspace=str(self.ws), run_id=rid)
            if view["status"] != "running":
                return view
            time.sleep(0.1)
        return view


class RunParsing(Base):
    def test_finished_run(self):
        write_run(self.ws, extra=b"some stderr line\n")
        err, v = call("cecilia_run", workspace=str(self.ws), run_id="R1", tail=1)
        self.assertFalse(err, v)
        self.assertEqual(v["status"], "finished")
        self.assertEqual(v["session_id"], "sess-1")
        self.assertEqual(len(v["assistant_tail"]), 1)
        self.assertEqual(v["result"], "Decision card written.")
        self.assertEqual(v["cost_usd"], 0.25)
        self.assertEqual(v["tasks"], ["SHOP-42"])
        self.assertTrue(any("cecilia approve" in c for c in v["human_commands"]))
        self.assertEqual(v["output_other"], ["some stderr line"])
        rec = json.loads((self.ws / "tensura" / "runs" / "R1.json").read_text())
        self.assertEqual((rec["session_id"], rec["status"]), ("sess-1", "finished"))

    def test_failed_and_running(self):
        write_run(self.ws, "R2", SAMPLE[:-1] + [{"type": "result", "subtype": "error_max_turns", "is_error": True}])
        self.assertEqual(call("cecilia_run", workspace=str(self.ws), run_id="R2")[1]["status"], "failed")
        write_run(self.ws, "R3", SAMPLE[:2], pid=os.getpid())
        self.assertEqual(call("cecilia_run", workspace=str(self.ws), run_id="R3")[1]["status"], "running")
        write_run(self.ws, "R4", SAMPLE[:2], pid=None)
        self.assertEqual(call("cecilia_run", workspace=str(self.ws), run_id="R4")[1]["status"], "failed")
        self.assertTrue(call("cecilia_run", workspace=str(self.ws), run_id="../x")[0])

    def test_send_rules(self):
        write_run(self.ws, "R3", SAMPLE[:2], pid=os.getpid())
        err, out = call("cecilia_send", workspace=str(self.ws), run_id="R3", message="hi")
        self.assertTrue(err)
        self.assertIn("wait until the run finishes", out)
        write_run(self.ws, "R5", [{"type": "result", "is_error": True, "subtype": "error"}])
        err, out = call("cecilia_send", workspace=str(self.ws), run_id="R5", message="hi")
        self.assertTrue(err)
        self.assertIn("no session", out)
        write_run(self.ws, "R1")
        seen = {}

        def fake_spawn(ws, rec, message, kind, resume=None):
            seen.update(message=message, resume=resume, kind=kind)
            return {"n": 2, "pid": 1}
        with mock.patch.object(M, "spawn_claude", side_effect=fake_spawn):
            err, out = call("cecilia_send", workspace=str(self.ws), run_id="R1", message="add tests")
        self.assertFalse(err, out)
        self.assertEqual(seen, {"message": "[via cecilia-mcp] add tests", "resume": "sess-1", "kind": "send"})


class Decide(Base):
    def test_decision_and_decide(self):
        d = self.ws / "tensura" / "decisions"
        d.mkdir()
        (d / "SHOP-42.md").write_text("# Decision SHOP-42\npassword: hunter2hunter\n", encoding="utf-8")
        (d / "SHOP-42.json").write_text(json.dumps({"task": "SHOP-42", "status": "open"}), encoding="utf-8")
        err, out = call("cecilia_decision", workspace=str(self.ws), task="SHOP-42")
        self.assertFalse(err, out)
        self.assertIn("[REDACTED]", out["markdown"])
        self.assertNotIn("hunter2", out["markdown"])
        self.assertTrue(call("cecilia_decision", workspace=str(self.ws), task="NOPE")[0])
        write_run(self.ws, "R1")
        calls, seen = [], {}

        def fake_run(cmd, **kw):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout='{"ok": true}', stderr="")

        def fake_spawn(ws, rec, message, kind, resume=None):
            seen.update(message=message, resume=resume, run=rec["id"])
            return {"n": 2, "pid": 1}
        with mock.patch.object(M.subprocess, "run", side_effect=fake_run), \
                mock.patch.object(M, "spawn_claude", side_effect=fake_spawn):
            err, out = call("cecilia_decide", workspace=str(self.ws), task="SHOP-42", option="B",
                            answers={"Q1": "disagree"})
        self.assertFalse(err, out)
        cmd = calls[0]
        self.assertTrue(cmd[1].endswith("workflow.py"))
        self.assertEqual(cmd[2:7], ["answer", "--task=SHOP-42", "--option=B", '--answers={"Q1": "disagree"}',
                                    "--by=mcp"])
        self.assertEqual(cmd[-2:], ["--workspace", str(self.ws)])
        self.assertEqual(seen["run"], "R1")
        self.assertEqual(seen["resume"], "sess-1")
        self.assertIn('Decision recorded on the card for SHOP-42: option B {"Q1": "disagree"}. Continue the workflow.',
                      seen["message"])

    def test_decide_refused(self):
        with mock.patch.object(M.subprocess, "run", return_value=subprocess.CompletedProcess(
                [], 2, stdout="", stderr="no decision card")):
            err, out = call("cecilia_decide", workspace=str(self.ws), task="SHOP-42", option="Z")
        self.assertTrue(err)
        self.assertIn("no decision card", out)


class Read(Base):
    def test_confinement(self):
        (self.ws / "tensura" / "plans").mkdir()
        (self.ws / "tensura" / "plans" / "p.md").write_text("plan", encoding="utf-8")
        (self.ws / ".cecilia" / "secret.txt").write_text("x", encoding="utf-8")
        err, out = call("cecilia_read", workspace=str(self.ws), path="plans/p.md")
        self.assertEqual((err, out["content"]), (False, "plan"))
        self.assertFalse(call("cecilia_read", workspace=str(self.ws), path="tensura\\plans\\p.md")[0])
        self.assertIn("p.md", call("cecilia_read", workspace=str(self.ws), path="plans")[1]["entries"])
        for bad in ("../.cecilia/secret.txt", "plans/../../.cecilia/secret.txt", "/etc/passwd",
                    str(self.ws / ".cecilia" / "secret.txt"), "C:/Windows/win.ini", "~/.ssh/id_rsa"):
            self.assertTrue(call("cecilia_read", workspace=str(self.ws), path=bad)[0], bad)
        if os.name != "nt":
            os.symlink(self.ws / ".cecilia", self.ws / "tensura" / "link")
            err, out = call("cecilia_read", workspace=str(self.ws), path="link/secret.txt")
            self.assertTrue(err)
            self.assertIn("escapes", out)

    def test_size_cap(self):
        (self.ws / "tensura" / "big.txt").write_text("a" * (M.MAX_READ + 10), encoding="utf-8")
        out = call("cecilia_read", workspace=str(self.ws), path="big.txt")[1]
        self.assertTrue(out["truncated"])
        self.assertEqual(len(out["content"]), M.MAX_READ)

    def test_redaction(self):
        text = ("Authorization: Bearer abcdefghijklmnop123\n"
                "API_KEY=sk-live-1234567890abcdef\n"
                '{"client_secret": "s3cr3t-value", "input_tokens": 1234}\n'
                "db_password: hunter2\n"
                "-----BEGIN RSA PRIVATE KEY-----\nMIIEow\nabc\n-----END RSA PRIVATE KEY-----\n"
                "github ghp_abcdefghijklmnopqrstuvwxyz0123\n"
                "author: Jane\n"
                "---\napiVersion: v1\nkind: Secret\nmetadata:\n  name: db\ndata:\n  user: YWRtaW4=\n"
                "  pass: cGFzc3dvcmQxMjM=\ntype: Opaque\n")
        (self.ws / "tensura" / "s.md").write_text(text, encoding="utf-8")
        out = call("cecilia_read", workspace=str(self.ws), path="s.md")[1]["content"]
        for secret in ("abcdefghijklmnop123", "sk-live", "s3cr3t", "hunter2", "MIIEow", "ghp_abc", "YWRtaW4",
                       "cGFzc3dvcmQ"):
            self.assertNotIn(secret, out, secret)
        for keep in ("input_tokens\": 1234", "author: Jane", "name: db", "type: Opaque", "BEGIN RSA PRIVATE KEY"):
            self.assertIn(keep, out, keep)


class Http(Base):
    def setUp(self):
        super().setUp()
        quiet = mock.patch.object(M, "log")
        quiet.start()
        self.addCleanup(quiet.stop)
        self.srv = M.make_http_server("127.0.0.1", 0)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        super().tearDown()

    def req(self, body=None, method="POST", origin=None, path="/mcp"):
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, method=method,
                                   headers={"Content-Type": "application/json",
                                            "Accept": "application/json, text/event-stream"})
        if origin:
            r.add_header("Origin", origin)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(r, timeout=10) as resp:
                raw = resp.read()
                return resp.status, dict(resp.headers), (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), None

    def test_initialize_and_origin(self):
        code, headers, body = self.req({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                        "params": {"protocolVersion": "2025-06-18"}}, origin="http://localhost:3000")
        self.assertEqual(code, 200)
        self.assertEqual(body["result"]["serverInfo"]["name"], "cecilia")
        self.assertIn("application/json", headers.get("Content-Type"))
        self.assertTrue(headers.get("Mcp-Session-Id"))
        code, _, body = self.req({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual((code, len(body["result"]["tools"])), (200, len(M.tools_list())))
        self.assertEqual(self.req({"jsonrpc": "2.0", "id": 3, "method": "ping"}, origin="https://evil.example")[0],
                         403)
        self.assertEqual(self.req({"jsonrpc": "2.0", "id": 3, "method": "ping"},
                                  origin="http://localhost.evil.example")[0], 403)
        self.assertEqual(self.req({"jsonrpc": "2.0", "method": "notifications/initialized"})[0], 202)
        self.assertEqual(self.req(method="GET")[0], 405)
        self.assertEqual(self.req(method="DELETE")[0], 405)
        self.assertEqual(self.req({"jsonrpc": "2.0", "id": 1, "method": "ping"}, path="/other")[0], 404)

    def test_bind_refused(self):
        self.assertEqual(M.parse_bind("8765"), ("127.0.0.1", 8765))
        self.assertEqual(M.parse_bind("localhost:9000"), ("127.0.0.1", 9000))
        for bad in ("0.0.0.0:8765", "192.168.1.5:8765", "[::]:8765", "example.com:80"):
            with self.assertRaises(ValueError):
                M.parse_bind(bad)
        err = io.StringIO()
        with mock.patch.object(sys, "stderr", err):
            self.assertEqual(M.main(["--http", "0.0.0.0:8765"]), 2)
        self.assertIn("127.0.0.1 only", err.getvalue())


class Cli(unittest.TestCase):
    def test_print_config(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(M.main(["--print-config"]), 0)
        out = buf.getvalue()
        self.assertIn('"command": "cecilia"', out)
        self.assertIn('"args": [\n        "mcp"', out)
        self.assertIn("http://127.0.0.1:8765/mcp", out)
        self.assertIn("claude mcp add cecilia -- cecilia mcp", out)

    def test_cli_dispatch(self):
        from cecilia import cli
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(cli.main(["mcp", "--print-config"]), 0)
        self.assertIn("mcpServers", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
