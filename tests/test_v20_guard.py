"""v20 guard: orchestrator lane, role lanes, workflow gate on Agent/Task, rules gate, rules/extension control.
    python3 -m unittest tests.test_v20_guard -v"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "guard"))
sys.path.insert(0, str(ROOT / "tools"))
import cecilia_guard as G  # noqa: E402
import guard_corpus as C  # noqa: E402

PY = sys.executable
GUARD = str(ROOT / "guard" / "cecilia_guard.py")
V20_KEYS = ("lanes", "orchestration", "rules", "flow", "fix_loop", "flows", "extensions")
REGISTRY = {
    "roles": {
        "cecilia-orchestrator": {"agent_type": "orchestrator", "lane": ["tensura/**"]},
        "cecilia-dev-be": {"agent_type": "writer", "lane": ["src/**", "server/**", "!**/*.test.*"]},
        "cecilia-dev-fe": {"agent_type": "writer", "lane": ["web/**", "src/components/**"]},
        "cecilia-test": {"agent_type": "tester", "lane": ["tests/**", "**/*.test.*"]},
        "cecilia-review": {"agent_type": "reviewer", "lane": []},
    },
    "agent_types": {"orchestrator": {"writes": "tensura-only"}, "writer": {"writes": "lane"},
                    "tester": {"writes": "lane"}, "reviewer": {"writes": "none"}},
}


def fixture(registry=True, v20_config=True, mode="standard") -> Path:
    root = C.build_fixture(Path(tempfile.mkdtemp()).resolve(), mode=mode)
    cfg = json.loads((root / ".cecilia/config.json").read_text())
    for k in V20_KEYS:
        cfg.pop(k, None)
    if v20_config:
        cfg.update({"flow": "personal", "rules": {"dir": "rules", "enforce": "gate"}, "fix_loop": {"max_rounds": 3},
                    "orchestration": {"orchestrator_writes": "tensura-only", "workflow_required_from": "standard"}})
    (root / ".cecilia/config.json").write_text(json.dumps(cfg))
    if registry:
        (root / ".cecilia/registry.json").write_text(json.dumps(REGISTRY))
    return root


def choose(root: Path, task="T1", option=None) -> str:
    option = option or {"id": "B", "split": "module", "agents": {"dev": 2, "test": 3}}
    h = hashlib.sha256(json.dumps(option, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:12]
    d = root / "tensura/tasks" / task
    d.mkdir(parents=True, exist_ok=True)
    (d / "workflow.json").write_text(json.dumps({"task": task, "mode": "standard", "flow": "personal", "chosen": "B",
                                                "option": option, "created": "2026-09-28", "hash": h}))
    return h


def header(role="cecilia-dev-be", task="T1", wf="none", rnd=0, rules="000000000000", lens="-"):
    return f"[cecilia-brief TASK={task} ROLE={role} LENS={lens} UNIT=api WORKFLOW={wf} ROUND={rnd} RULES={rules}]"


def transcript(root: Path, texts=(), reads=()) -> Path:
    t = root / "t.jsonl"
    lines = [json.dumps({"type": "user", "message": {"content": txt}}) for txt in texts]
    lines += [json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Read", "input": {"file_path": str(root / r)}}]}}) for r in reads]
    t.write_text("\n".join(lines) + "\n")
    return t


class Hook:
    def hook(self, payload: dict, workspace=None) -> tuple:
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
        cmd = [PY, GUARD, "--host", "claude"] + (["--workspace", str(workspace)] if workspace else [])
        r = subprocess.run(cmd, input=json.dumps(payload), capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        if not r.stdout.strip():
            return "allow", ""
        out = json.loads(r.stdout)["hookSpecificOutput"]
        return out["permissionDecision"], out["permissionDecisionReason"]

    def write(self, root, path, agent=None, cwd=None, t=None, workspace=None):
        data = {"tool_name": "Write", "tool_input": {"file_path": str(path), "content": "x = 1\n"},
                "cwd": str(cwd or root), "hook_event_name": "PreToolUse"}
        if agent:
            data["agent_type"] = agent
        if t:
            data["transcript_path"] = str(t)
        return self.hook(data, workspace)

    def bash(self, root, cmd, agent=None, t=None):
        data = {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(root), "hook_event_name": "PreToolUse"}
        if agent:
            data["agent_type"] = agent
        if t:
            data["transcript_path"] = str(t)
        return self.hook(data)

    def dispatch(self, root, role, prompt, tool="Agent"):
        return self.hook({"tool_name": tool, "tool_input": {"subagent_type": role, "prompt": prompt,
                                                            "description": "x"},
                          "cwd": str(root), "hook_event_name": "PreToolUse"})


class Lanes(Hook, unittest.TestCase):
    def test_orchestrator_writes_only_tensura(self):
        root = fixture()
        d, why = self.write(root, root / "src/app.ts", agent="cecilia-orchestrator")
        self.assertEqual(d, "deny")
        self.assertIn("dispatch", why)
        self.assertEqual(self.write(root, root / "tensura/tasks/T1/notes.md", agent="cecilia-orchestrator")[0], "allow")
        self.assertEqual(self.bash(root, "echo x > src/app.ts", agent="cecilia-orchestrator")[0], "deny")
        self.assertEqual(self.bash(root, "echo x > tensura/tasks/T1/state.md", agent="cecilia-orchestrator")[0], "allow")
        self.assertEqual(self.write(root, root / "src/app.ts")[0], "allow")          # main thread without agent: v19.2

    def test_orchestrator_workspace_mode(self):
        base = Path(tempfile.mkdtemp()).resolve()
        proj = C.build_fixture(base / "shop")
        ws = base / "shop.cecilia"
        (ws / ".cecilia").mkdir(parents=True)
        (ws / ".cecilia/config.json").write_text(json.dumps({"workspace": {"project": str(proj)}, "flow": "personal"}))
        (ws / ".cecilia/registry.json").write_text(json.dumps(REGISTRY))
        self.assertEqual(self.write(ws, proj / "src/app.ts", agent="cecilia-orchestrator", workspace=ws)[0], "deny")
        self.assertEqual(self.write(ws, ws / "tensura/tasks/T1/notes.md", agent="cecilia-orchestrator", workspace=ws)[0],
                         "allow")
        self.assertEqual(self.write(ws, proj / "src/app.ts", agent="cecilia-dev-be", workspace=ws)[0], "allow")

    def test_role_lane(self):
        root = fixture()
        d, why = self.write(root, root / "src/app.ts", agent="cecilia-dev-fe")
        self.assertEqual(d, "deny")
        self.assertIn("HANDOFF: needs cecilia-dev-be", why)
        self.assertEqual(self.write(root, root / "web/page.tsx", agent="cecilia-dev-fe")[0], "allow")
        self.assertEqual(self.write(root, root / "tensura/reports/T1/dev-fe.md", agent="cecilia-dev-fe")[0], "allow")
        self.assertEqual(self.write(root, root / "src/a.test.ts", agent="cecilia-dev-be")[0], "deny")   # ! exclude
        self.assertEqual(self.write(root, root / "src/a.test.ts", agent="cecilia-test")[0], "allow")
        self.assertEqual(self.write(root, root / "src/app.ts", agent="cecilia-review")[0], "deny")
        self.assertEqual(self.bash(root, "echo x > src/app.ts", agent="cecilia-dev-fe")[0], "deny")
        self.assertEqual(self.write(root, root / "src/app.ts", agent="some-other-agent")[0], "allow")

    def test_config_lanes_without_registry_and_v19_fallback(self):
        root = fixture(registry=False)
        cfg = json.loads((root / ".cecilia/config.json").read_text())
        cfg["lanes"] = {"cecilia-dev-fe": ["web/**"]}
        (root / ".cecilia/config.json").write_text(json.dumps(cfg))
        self.assertEqual(self.write(root, root / "src/app.ts", agent="cecilia-dev-fe")[0], "deny")
        old = fixture(registry=False, v20_config=False)
        self.assertEqual(self.write(old, old / "src/app.ts", agent="cecilia-orchestrator")[0], "allow")
        self.assertEqual(self.write(old, old / "src/app.ts", agent="cecilia-dev-fe")[0], "allow")


class WorkflowGate(Hook, unittest.TestCase):
    def test_standard_needs_chosen_workflow(self):
        root = fixture()
        d, why = self.dispatch(root, "cecilia-dev-be", "Build the API\nmore")
        self.assertEqual(d, "deny")
        self.assertIn("workflow.py", why)
        self.assertEqual(self.dispatch(root, "cecilia-dev-be", header() + "\nbrief")[0], "deny")   # no workflow.json
        h = choose(root)
        self.assertEqual(self.dispatch(root, "cecilia-dev-be", header(wf=h) + "\nbrief")[0], "allow")
        self.assertEqual(self.dispatch(root, "cecilia-dev-be", header(wf=h) + "\nbrief", tool="Task")[0], "allow")
        self.assertEqual(self.dispatch(root, "cecilia-dev-be", header(wf="abcdef012345") + "\n")[0], "deny")
        self.assertEqual(self.dispatch(root, "cecilia-test", header(wf=h) + "\n")[0], "deny")     # ROLE mismatch
        self.assertEqual(self.dispatch(root, "cecilia-dev-be", header(wf=h, rnd=3) + "\n")[0], "allow")
        d, why = self.dispatch(root, "cecilia-dev-be", header(wf=h, rnd=4) + "\n")
        self.assertEqual(d, "deny")
        self.assertIn("options", why)
        self.assertEqual(self.dispatch(root, "cecilia-review", "Review the diff")[0], "allow")    # reviewer: no gate
        self.assertEqual(self.dispatch(root, "general-purpose", "anything")[0], "allow")

    def test_edited_workflow_and_fast(self):
        root = fixture()
        h = choose(root)
        f = root / "tensura/tasks/T1/workflow.json"
        wf = json.loads(f.read_text())
        wf["option"]["agents"]["dev"] = 9
        f.write_text(json.dumps(wf))
        self.assertEqual(self.dispatch(root, "cecilia-dev-be", header(wf=h) + "\n")[0], "deny")
        fast = fixture(mode="fast")
        self.assertEqual(self.dispatch(fast, "cecilia-dev-be", "Fix the typo in src/app.ts")[0], "allow")
        self.assertEqual(self.dispatch(fixture(registry=False), "cecilia-dev-be", "no registry")[0], "allow")


class RulesGate(Hook, unittest.TestCase):
    def test_first_write_needs_rules(self):
        root = fixture()
        empty = transcript(root)
        d, why = self.write(root, root / "src/b.ts", agent="cecilia-dev-be", t=empty)
        self.assertEqual(d, "deny")
        self.assertIn("rules/_project.md", why)
        self.assertEqual(self.bash(root, "echo x > src/b.ts", agent="cecilia-dev-be", t=empty)[0], "deny")
        self.assertEqual(self.bash(root, "ls src", agent="cecilia-dev-be", t=empty)[0], "allow")   # no write
        current = G.rules_hash(root, "cecilia-dev-be", "personal", None)
        stale = transcript(root, [header(rules="0123456789ab")])
        self.assertEqual(self.write(root, root / "src/b.ts", agent="cecilia-dev-be", t=stale)[0], "deny")
        briefed = transcript(root, [header(rules=current) + "\nThe brief"])
        self.assertEqual(self.write(root, root / "src/b.ts", agent="cecilia-dev-be", t=briefed)[0], "allow")
        read = transcript(root, reads=["rules/_project.md", "rules/roles/dev-be.md"])
        self.assertEqual(self.write(root, root / "src/b.ts", agent="cecilia-dev-be", t=read)[0], "allow")
        half = transcript(root, reads=["rules/_project.md"])
        self.assertEqual(self.write(root, root / "src/b.ts", agent="cecilia-dev-be", t=half)[0], "deny")
        self.assertEqual(self.write(root, root / "src/b.ts", agent="cecilia-dev-be")[0], "allow")   # no transcript

    def test_rules_hash_matches_spec(self):
        root = fixture()
        want = hashlib.sha256()
        for rel in ("rules/_project.md", "rules/roles/dev-be.md"):
            want.update(rel.encode() + b"\n" + (root / rel).read_bytes() + b"\n")
        self.assertEqual(G.rules_hash(root, "cecilia-dev-be", "personal", None), want.hexdigest()[:12])


class ControlPaths(Hook, unittest.TestCase):
    def test_rules_and_extensions_are_cecilias(self):
        root = fixture()
        read = transcript(root, reads=["rules/_project.md", "rules/roles/dev-be.md"])
        for cmd in ("echo x > rules/_project.md", "cecilia rules add 'PR-9: x'", "cecilia flow team",
                    "cecilia extension apply x", "echo {} > .cecilia/extensions/registry/roles/x.json"):
            with self.subTest(cmd=cmd):
                self.assertEqual(self.bash(root, cmd, agent="cecilia-dev-be", t=read)[0], "deny")
        for cmd in ("cecilia rules list", "cecilia rules lint", "cecilia extension check x"):
            with self.subTest(cmd=cmd):
                self.assertEqual(self.bash(root, cmd, agent="cecilia-dev-be", t=read)[0], "allow")
        self.assertEqual(self.write(root, root / "rules/roles/dev-be.md", agent="cecilia-orchestrator")[0], "deny")
        self.assertEqual(self.write(root, root / "rules/_project.md")[0], "deny")

    def test_version(self):
        self.assertEqual(G.VERSION, "20.2.0")
        self.assertEqual(G.POLICY["version"], "20.2.0")


if __name__ == "__main__":
    unittest.main()
