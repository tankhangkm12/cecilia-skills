"""v20.2 guard on Antigravity: call_mcp_tool / invoke_subagent / define_subagent normalisation, identity from the
transcript (+ cache), PreInvocation injectSteps, provenance, guard.agent_may_run.
    python3 -m unittest tests.test_v22_guard -v"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "guard"))
sys.path.insert(0, str(ROOT / "tests"))
import cecilia_guard as G  # noqa: E402
from test_v20_guard import GUARD, PY, REGISTRY, Hook, choose, fixture, header  # noqa: E402

ORCH = "cecilia-orchestrator"
DEVOPS = "cecilia-devops"
REG = json.loads(json.dumps(REGISTRY))
REG["roles"][DEVOPS] = {"agent_type": "writer", "lane": ["ops/**", "infra/**"]}
REG["roles"]["cecilia-ext-audit"] = {"agent_type": "writer", "lane": ["audit/**"], "source": "extension"}


def agy_fixture(**cfg_extra) -> Path:
    root = fixture()
    (root / ".cecilia/registry.json").write_text(json.dumps(REG))
    if cfg_extra:
        f = root / ".cecilia/config.json"
        cfg = json.loads(f.read_text())
        for k, v in cfg_extra.items():
            if isinstance(v, dict):
                cfg.setdefault(k, {}).update(v)
            else:
                cfg[k] = v
        f.write_text(json.dumps(cfg))
    return root


def agy_transcript(root: Path, first: str, name="t-agy.jsonl", planner=True, junk=True) -> Path:
    """An Antigravity transcript: the first USER_INPUT is what the parent sent (a brief for a subagent)."""
    t = root / name
    lines = []
    if junk:
        lines += ["{not json", json.dumps(["a list entry"]), json.dumps({"type": "SYSTEM", "content": {"x": 1}})]
    lines.append(json.dumps({"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": first}))
    if planner:
        lines.append(json.dumps({"type": "PLANNER_RESPONSE", "source": "MODEL",
                                 "content": [{"text": header(role="cecilia-dev-be")}]}))   # after: ignored
    t.write_text("\n".join(lines) + "\n")
    return t


class AgyHook(Hook):
    def agy(self, root, tool=None, args=None, conv="conv-1", t=None, extra=None) -> dict:
        data = {"conversationId": conv, "workspacePaths": [str(root)], "modelName": "gemini-3.8-flash",
                "artifactDirectoryPath": str(root / "art")}
        if tool is not None:
            data.update({"toolCall": {"name": tool, "args": args or {}}, "stepIdx": 3})
        if t is not None:
            data["transcriptPath"] = str(t)
        data.update(extra or {})
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
        r = subprocess.run([PY, GUARD, "--host", "antigravity"], input=json.dumps(data), capture_output=True,
                           text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def mcp(self, root, tool="pods_list", server="kubernetes", arguments=None, **kw) -> dict:
        return self.agy(root, "call_mcp_tool", {"ServerName": server, "ToolName": tool,
                                                "Arguments": arguments if arguments is not None else {}}, **kw)


class Extract(unittest.TestCase):
    def ex(self, tool, args):
        return G.extract("antigravity", {"toolCall": {"name": tool, "args": args}, "workspacePaths": ["/w"]})

    def test_call_mcp_tool(self):
        k, p, _ = self.ex("call_mcp_tool", {"ServerName": "kubernetes", "ToolName": "pods_delete",
                                            "Arguments": {"name": "api-0"}})
        self.assertEqual((k, p), ("mcp", ("mcp__kubernetes__pods_delete", {"name": "api-0"})))
        k, p, _ = self.ex("call_mcp_tool", {"server_name": "proxmox", "tool_name": "vm_list",
                                            "arguments": '{"node": "pve1"}'})
        self.assertEqual(p, ("mcp__proxmox__vm_list", {"node": "pve1"}))              # snake_case + JSON string
        self.assertEqual(self.ex("call_mcp_tool", {"ServerName": "a", "ToolName": "b", "Arguments": "{bad"})[1],
                         ("mcp__a__b", {"_raw": "{bad"}))
        self.assertEqual(self.ex("call_mcp_tool", {"ToolName": "b"})[1], ("", {}))       # no server: denied later

    def test_dispatch_and_others(self):
        k, p, _ = self.ex("invoke_subagent", {"TypeName": DEVOPS, "Task": "[cecilia-brief ...]\nwork"})
        self.assertEqual(k, "dispatch")
        self.assertEqual(p, {"subagent_type": DEVOPS, "prompt": "[cecilia-brief ...]\nwork", "_host": "antigravity",
                             "_tool": "invoke_subagent"})
        p = self.ex("invoke_subagent", {"TypeName": "x", "Foo": "short", "Bar": "the longest string argument"})[1]
        self.assertEqual(p["prompt"], "the longest string argument")
        p = self.ex("define_subagent", {"name": "helper", "SystemPrompt": "do it all"})[1]
        self.assertEqual((p["subagent_type"], p["_tool"]), ("helper", "define_subagent"))
        self.assertEqual(self.ex("send_message", {"Message": "hi"})[0], "other")
        k, p, cwd = G.extract("antigravity", {"invocationNum": 0, "initialNumSteps": 1, "workspacePaths": ["/w"]})
        self.assertEqual((k, p, cwd), ("prompt", None, Path("/w")))


class Identity(AgyHook, unittest.TestCase):
    def test_orchestrator_mcp_denied_devops_allowed(self):
        root = agy_fixture()
        out = self.mcp(root, arguments='{"namespace": "prod"}')                       # no transcript: main agent
        self.assertEqual(out["decision"], "deny")
        self.assertIn("orchestrator: MCP tool 'mcp__kubernetes__pods_list'", out["reason"])
        t = agy_transcript(root, header(role="devops") + "\nScale the api deployment.")   # short ROLE name
        self.assertEqual(self.mcp(root, conv="sub-1", t=t)["decision"], "ask")          # reading: host decides
        out = self.mcp(root, tool="pods_delete", conv="sub-1", t=t)
        self.assertEqual(out["decision"], "force_ask")                                  # A3
        noheader = agy_transcript(root, "Please fix the cluster", name="main.jsonl")
        self.assertEqual(self.mcp(root, conv="main-1", t=noheader)["decision"], "deny")
        self.assertEqual(self.agy(root, "call_mcp_tool", {"ToolName": "x"}, conv="sub-1", t=t)["decision"], "deny")

    def test_main_agent_config_and_ask(self):
        root = agy_fixture(antigravity={"main_agent": "", "ask": "ask"})
        self.assertEqual(self.mcp(root)["decision"], "ask")                             # no main agent role
        out = self.mcp(root, tool="pods_delete")
        self.assertEqual(out["decision"], "ask")                                        # plain ask (skip-permissions)
        self.assertIn("A3", out["reason"])

    def test_identity_cache(self):
        root = agy_fixture()
        t = agy_transcript(root, header(role=DEVOPS) + "\nwork", name="sub.jsonl")
        self.assertEqual(self.mcp(root, conv="sub-9", t=t)["decision"], "ask")
        cache = json.loads((root / ".cecilia/agy-identity.json").read_text())
        self.assertEqual(cache["sub-9"]["role"], DEVOPS)
        t.unlink()
        self.assertEqual(self.mcp(root, conv="sub-9", t=t)["decision"], "ask")          # from the cache
        self.assertEqual(self.mcp(root, conv="other", t=t)["decision"], "deny")         # unreadable: main agent
        early = agy_transcript(root, "hello", name="early.jsonl", planner=False)
        self.mcp(root, conv="early", t=early)
        self.assertNotIn("early", json.loads((root / ".cecilia/agy-identity.json").read_text()))  # not final
        self.assertEqual(G._brief_role('x [cecilia-brief TASK=T1 ROLE=db LENS=- ROUND=zz] y'), "cecilia-db")

    def test_identity_off(self):
        root = agy_fixture(antigravity={"identity": "off"})
        self.assertEqual(self.mcp(root)["decision"], "ask")                             # 20.1 behaviour
        self.assertEqual(self.agy(root, "invoke_subagent", {"TypeName": "teamwork_preview",
                                                             "Prompt": "do it"})["decision"], "ask")
        self.assertEqual(self.agy(root, extra={"invocationNum": 0}), {})
        self.assertFalse((root / ".cecilia/agy-identity.json").exists())


class Dispatch(AgyHook, unittest.TestCase):
    def test_unknown_and_define_denied_for_orchestrator(self):
        root = agy_fixture()
        for name in ("teamwork_preview", "self", "research", "general", "", ORCH):
            with self.subTest(name=name):
                out = self.agy(root, "invoke_subagent", {"TypeName": name, "Prompt": "do the work"})
                self.assertEqual(out["decision"], "deny")
                self.assertIn("dispatch only Cecilia roles: invoke_subagent TypeName=cecilia-<role>", out["reason"])
                self.assertIn("STOP and report", out["reason"])
        out = self.agy(root, "define_subagent", {"name": "cecilia-devops", "Instructions": "you run kubectl"})
        self.assertEqual(out["decision"], "deny")
        self.assertIn("define_subagent", out["reason"])
        self.assertEqual(self.agy(root, "invoke_subagent", {"TypeName": "cecilia-ui", "Prompt": "x"})["decision"],
                         "deny")                                                        # disabled in config
        self.assertEqual(self.agy(root, "invoke_subagent", {"TypeName": "cecilia-review",
                                                             "Prompt": "Review the diff"})["decision"], "ask")
        self.assertEqual(self.agy(root, "invoke_subagent", {"TypeName": "cecilia-ext-audit",
                                                             "Prompt": "x"})["decision"], "deny")    # gated writer
        t = agy_transcript(root, header(role=DEVOPS) + "\nwork", name="sub.jsonl")
        self.assertEqual(self.agy(root, "invoke_subagent", {"TypeName": "general", "Prompt": "x"}, conv="s",
                                  t=t)["decision"], "ask")                             # only the orchestrator

    def test_workflow_gate_on_invoke_subagent(self):
        root = agy_fixture()
        out = self.agy(root, "invoke_subagent", {"TypeName": DEVOPS, "Prompt": "Scale the api"})
        self.assertEqual(out["decision"], "deny")
        self.assertIn("workflow gate", out["reason"])
        h = choose(root)
        ok = {"TypeName": DEVOPS, "Task": header(role=DEVOPS, wf=h) + "\nScale the api"}
        self.assertEqual(self.agy(root, "invoke_subagent", ok)["decision"], "ask")
        bad = {"TypeName": DEVOPS, "Task": header(role=DEVOPS, wf=h, rnd=4) + "\n"}
        self.assertIn("fix loop", self.agy(root, "invoke_subagent", bad)["reason"])
        ext = {"TypeName": "cecilia-ext-audit", "Message": header(role="cecilia-ext-audit", wf=h) + "\n"}
        self.assertEqual(self.agy(root, "invoke_subagent", ext)["decision"], "ask")    # extension role


class PreInvocation(AgyHook, unittest.TestCase):
    def test_orchestrator_reminder(self):
        root = agy_fixture()
        (root / "tensura/decisions").mkdir(parents=True)
        (root / "tensura/decisions/T1.json").write_text(json.dumps({"status": "open"}))
        (root / "tensura/decisions/T0.json").write_text(json.dumps({"status": "answered"}))
        (root / "tensura/inbox").mkdir(parents=True)
        (root / "tensura/inbox/IN-1.json").write_text(json.dumps({"status": "new"}))
        for n in (0, 25, 50):
            out = self.agy(root, extra={"invocationNum": n, "initialNumSteps": 1})
            msg = out["injectSteps"][0]["ephemeralMessage"]
            self.assertIn("coordinator only", msg)
            self.assertIn("invoke_subagent", msg)
            self.assertIn("Open decision cards: 1; new inbox items: 1", msg)
        self.assertEqual(self.agy(root, extra={"invocationNum": 3}), {})

    def test_subagent_reminder(self):
        root = agy_fixture()
        t = agy_transcript(root, header(role=DEVOPS) + "\nwork", name="sub.jsonl")
        msg = self.agy(root, conv="s", t=t, extra={"invocationNum": 0})["injectSteps"][0]["ephemeralMessage"]
        self.assertIn(DEVOPS, msg)
        self.assertIn("ops/**", msg)
        self.assertEqual(self.agy(root, conv="s", t=t, extra={"invocationNum": 1}), {})
        self.assertEqual(self.agy(root, conv="s", t=t, extra={"invocationNum": 25}), {})


class RulesAndProvenance(AgyHook, unittest.TestCase):
    def lines(self, root):
        f = root / ".cecilia/provenance.jsonl"
        return [json.loads(x) for x in f.read_text().splitlines()] if f.is_file() else []

    def test_provenance_antigravity(self):
        root = agy_fixture()
        out = self.agy(root, "write_to_file", {"TargetFile": str(root / "tensura/tasks/T1/notes.md"),
                                               "CodeContent": "x"}, conv="main-7")
        self.assertEqual(out["decision"], "allow")
        rec = self.lines(root)[-1]
        self.assertEqual({k: rec[k] for k in ("host", "path", "agent", "actor", "model")},
                         {"host": "antigravity", "path": "tensura/tasks/T1/notes.md", "agent": ORCH,
                          "actor": "main-7", "model": "gemini-3.8-flash"})
        self.assertIn("ts", rec)
        self.assertEqual(self.agy(root, "run_command", {"CommandLine": "echo x > tensura/tasks/T1/state.md",
                                                        "Cwd": str(root)}, conv="main-7")["decision"], "ask")
        self.assertEqual(self.lines(root)[-1]["path"], "tensura/tasks/T1/state.md")
        n = len(self.lines(root))
        self.assertEqual(self.agy(root, "write_to_file", {"TargetFile": str(root / "tensura/plans/p.md")})["decision"],
                         "deny")                                                        # not the orchestrator's
        self.assertEqual(self.agy(root, "run_command", {"CommandLine": "ls tensura", "Cwd": str(root)})["decision"],
                         "ask")
        self.assertEqual(len(self.lines(root)), n)                                      # nothing for deny / reads

    def test_provenance_claude(self):
        root = agy_fixture()
        d = self.hook({"tool_name": "Write", "tool_input": {"file_path": str(root / "tensura/tasks/T1/x.md"),
                                                             "content": "x"},
                       "cwd": str(root), "hook_event_name": "PreToolUse", "agent_type": ORCH, "session_id": "s1"})
        self.assertEqual(d[0], "allow")
        rec = self.lines(root)[-1]
        self.assertEqual((rec["host"], rec["path"], rec["agent"], rec["actor"]),
                         ("claude", "tensura/tasks/T1/x.md", ORCH, "s1:" + ORCH))
        self.write(root, root / "src/app.ts")                                           # not tensura/: no line
        self.assertEqual(self.lines(root)[-1]["path"], "tensura/tasks/T1/x.md")

    def test_rules_gate_and_lane_on_antigravity(self):
        root = agy_fixture()
        good = G.rules_hash(root, DEVOPS, "personal", None)
        t = agy_transcript(root, header(role=DEVOPS, rules=good) + "\nwork", name="ok.jsonl")
        self.assertEqual(self.agy(root, "write_to_file", {"TargetFile": str(root / "ops/run.md")}, conv="a",
                                  t=t)["decision"], "allow")
        out = self.agy(root, "write_to_file", {"TargetFile": str(root / "src/app.ts")}, conv="a", t=t)
        self.assertEqual(out["decision"], "deny")                                       # outside the devops lane
        self.assertIn("HANDOFF", out["reason"])
        stale = agy_transcript(root, header(role=DEVOPS) + "\nwork", name="stale.jsonl")
        out = self.agy(root, "write_to_file", {"TargetFile": str(root / "ops/run.md")}, conv="b", t=stale)
        self.assertEqual(out["decision"], "deny")
        self.assertIn("rules gate", out["reason"])


class AgentMayRun(unittest.TestCase):
    def setUp(self):
        self.saved = G.AGENT

    def tearDown(self):
        G.AGENT = self.saved

    def cmd(self, root, command, agent=ORCH):
        G.AGENT = agent
        return G.decide_command(command, root, root)[0] or "allow"

    def test_open_approve(self):
        root = agy_fixture()
        self.assertEqual(self.cmd(root, "cecilia approve T1"), "deny")
        self.assertEqual(self.cmd(root, "python guard/cecilia_approve.py T1", agent="cecilia-dev-be"), "deny")
        f = root / ".cecilia/config.json"
        cfg = json.loads(f.read_text())
        cfg.setdefault("guard", {})["agent_may_run"] = ["approve", "rules add"]
        f.write_text(json.dumps(cfg))
        self.assertEqual(self.cmd(root, "cecilia approve T1"), "allow")
        self.assertEqual(self.cmd(root, "python guard/cecilia_approve.py T1", agent="cecilia-dev-be"), "allow")
        self.assertEqual(self.cmd(root, "cecilia mode fast"), "deny")                  # not listed
        self.assertEqual(self.cmd(root, "python guard/cecilia_mode.py fast", agent="cecilia-dev-be"), "deny")
        self.assertEqual(self.cmd(root, "cecilia push"), "deny")
        self.assertEqual(self.cmd(root, "cecilia rules add --role dev-be PR-02"), "allow")
        self.assertEqual(self.cmd(root, "cecilia rules rm PR-01"), "deny")
        self.assertEqual(self.cmd(root, "cecilia flow team"), "deny")
        self.assertEqual(self.cmd(root, "git push origin feature/T1-x"), "deny")       # unrelated rules unchanged


if __name__ == "__main__":
    unittest.main()
