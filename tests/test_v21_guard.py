"""v20.1 guard: orchestrator command allowlist, orchestrator MCP deny, narrowed orchestrator lane, secret dumps.
    python3 -m unittest tests.test_v21_guard -v"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "guard"))
sys.path.insert(0, str(ROOT / "tests"))
import cecilia_guard as G  # noqa: E402
from test_v20_guard import REGISTRY, Hook, fixture  # noqa: E402

ORCH = "cecilia-orchestrator"
WORKFLOW = ".claude/skills/cecilia-orchestrator/scripts/workflow.py"


def set_config(root: Path, **orchestration) -> None:
    f = root / ".cecilia/config.json"
    cfg = json.loads(f.read_text())
    cfg.setdefault("orchestration", {}).update(orchestration)
    f.write_text(json.dumps(cfg))


class AgentCase(unittest.TestCase):
    """Judge in-process as a given agent (the hook's `agent_type`)."""

    def setUp(self):
        self.saved = G.AGENT
        self.root = fixture()

    def tearDown(self):
        G.AGENT = self.saved

    def cmd(self, command, agent=ORCH, root=None):
        G.AGENT = agent or ""
        root = root or self.root
        d, why = G.decide_command(command, root, root)
        return d or "allow", why


class OrchestratorCommands(AgentCase):
    def test_allowed(self):
        for c in ("cecilia status", f"python {WORKFLOW} brief --task T1 --role cecilia-dev-be",
                  "py -3 C:\\Users\\me\\.claude\\skills\\cecilia-orchestrator\\scripts\\workflow.py options --task T1",
                  "python3 scripts/cecilia_check.py evidence", "git status", "git log --oneline -5 | head -3",
                  "git merge --no-ff feature/T1-api", "git merge --abort", "git switch -c int/T1",
                  "git checkout -b feature/T1-ui", "git branch feature/T2-x", "git branch --list",
                  "git worktree list", "git worktree add ../w feature/T1-api", "ls -la tensura", "cat README.md",
                  "grep -rn TODO src | wc -l", "find . -name '*.md'", "Get-ChildItem tensura", "pwd && echo ok"):
            with self.subTest(c=c):
                self.assertEqual(self.cmd(c)[0], "allow", self.cmd(c)[1])

    def test_denied_specialist_work(self):
        for c in ("kubectl get pods", "ssh host uptime", "python -c 'print(1)'", "python -m pytest",
                  "curl https://example.com", "find . -name x -delete", "find . -exec cat {} ;",
                  "ls && kubectl delete pod x", "powershell -Command kubectl get pods", "bash -c 'ls; helm list'",
                  "cat README.md | xargs rm", "npm test", "python tensura/tasks/T1/scripts/workflow.py brief",
                  "python evil.py", "git checkout -- src/app.ts", "git checkout .", "git branch -D feature/x",
                  "git commit -m x", "git fetch", "echo $(kubectl get ns)"):
            with self.subTest(c=c):
                d, why = self.cmd(c)
                self.assertEqual(d, "deny", why)
        d, why = self.cmd("kubectl get pods")
        self.assertIn("orchestrator: 'kubectl get pods' is specialist work", why)
        self.assertIn("workflow.py brief", why)

    def test_existing_rules_still_apply(self):
        self.assertIn("cecilia approve", self.cmd("cecilia approve T1")[1])          # human-only stays denied
        self.assertEqual(self.cmd("cecilia mode fast")[0], "deny")
        self.assertEqual(self.cmd("git push origin feature/T1-x")[0], "deny")         # local-only
        self.assertEqual(self.cmd("cat .env")[0], "deny")                             # secret file
        self.assertEqual(self.cmd("git worktree remove ../w")[0], "ask")              # A3 kept, stricter wins

    def test_extra_commands_from_config(self):
        self.assertEqual(self.cmd("npm test")[0], "deny")
        set_config(self.root, orchestrator_commands=["npm", "jq.exe"])
        self.assertEqual(self.cmd("npm test")[0], "allow")
        self.assertEqual(self.cmd("cat x.json | jq .a")[0], "allow")
        self.assertEqual(self.cmd("npm install left-pad")[0], "ask")                  # base decision on top

    def test_other_agents_unaffected(self):
        self.assertEqual(self.cmd("npm test", agent="cecilia-dev-be")[0], "allow")
        self.assertEqual(self.cmd("python -m pytest -q", agent="cecilia-test")[0], "allow")
        self.assertEqual(self.cmd("kubectl get pods", agent="cecilia-devops")[0], "ask")
        self.assertEqual(self.cmd("npm test", agent="")[0], "allow")                  # main thread, no agent
        old = fixture(registry=False, v20_config=False)                               # v19.2: gates off
        self.assertEqual(self.cmd("npm test", root=old)[0], "allow")


class OrchestratorLane(Hook, unittest.TestCase):
    def test_narrowed_lane(self):
        root = fixture()
        ok = ("tensura/tasks/T1/state.md", "tensura/decisions/T1.json", "tensura/inbox/q1.json",
              "tensura/runs/r1.jsonl", "tensura/state.md", "tensura/lessons.md",
              "tensura/reports/T1/orchestration-T1.md", "tensura/reports/T1/panel/r1-all.md")
        for rel in ok:
            with self.subTest(rel=rel):
                self.assertEqual(self.write(root, root / rel, agent=ORCH)[0], "allow")
        owners = {"tensura/plans/p.md": "cecilia-plan", "tensura/docs/system/x.md": "cecilia-discovery",
                  "tensura/extensions/e.json": "cecilia-extend", "tensura/tasks/T1/votes/plan/a.json": "cecilia-review",
                  "tensura/tasks/T1/review-code.md": "cecilia-review", "tensura/reports/T1/panel/verdict.md":
                  "cecilia-review", "tensura/reports/T1/dev-be.md": "report"}
        for rel, owner in owners.items():
            with self.subTest(rel=rel):
                d, why = self.write(root, root / rel, agent=ORCH)
                self.assertEqual(d, "deny")
                self.assertIn(owner, why)
        self.assertEqual(self.bash(root, "echo x > tensura/plans/p.md", agent=ORCH)[0], "deny")
        self.assertEqual(self.bash(root, "echo x > tensura/tasks/T1/state.md", agent=ORCH)[0], "allow")
        self.assertEqual(self.write(root, root / "tensura/tasks/T1/votes/plan/a.json", agent="cecilia-review")[0],
                         "allow")                                                      # the voters' own files

    def test_fallbacks(self):
        root = fixture(registry=False)                                                 # no registry snapshot
        self.assertEqual(self.write(root, root / "tensura/plans/p.md", agent=ORCH)[0], "deny")
        self.assertEqual(self.write(root, root / "tensura/tasks/T1/state.md", agent=ORCH)[0], "allow")
        stale = fixture()                                                              # older snapshot: tensura/**
        reg = json.loads(json.dumps(REGISTRY))
        reg["roles"][ORCH]["lane"] = ["tensura/**"]
        (stale / ".cecilia/registry.json").write_text(json.dumps(reg))
        self.assertEqual(self.write(stale, stale / "tensura/docs/a.md", agent=ORCH)[0], "deny")
        narrow = fixture()                                                             # config can narrow further
        cfg = json.loads((narrow / ".cecilia/config.json").read_text())
        cfg["lanes"] = {ORCH: ["tensura/tasks/**"]}
        (narrow / ".cecilia/config.json").write_text(json.dumps(cfg))
        self.assertEqual(self.write(narrow, narrow / "tensura/decisions/T1.json", agent=ORCH)[0], "deny")

    def test_registry_lane_matches_guard(self):
        role = json.loads((ROOT / "registry/roles/cecilia-orchestrator.json").read_text())
        self.assertEqual(role["lane"], G.ORCH_LANE)


class OrchestratorMcp(Hook, unittest.TestCase):
    def mcp(self, root, tool, agent):
        return self.hook({"tool_name": tool, "tool_input": {}, "cwd": str(root), "hook_event_name": "PreToolUse",
                          "agent_type": agent})

    def test_mcp_denied_unless_listed(self):
        root = fixture()
        d, why = self.mcp(root, "mcp__kubernetes__pods_list", ORCH)
        self.assertEqual(d, "deny")
        self.assertIn("dispatch", why)
        self.assertEqual(self.mcp(root, "mcp__kubernetes__pods_list", "cecilia-devops")[0], "allow")
        set_config(root, orchestrator_mcp=["mcp__context7__*"])
        self.assertEqual(self.mcp(root, "mcp__context7__query-docs", ORCH)[0], "allow")
        self.assertEqual(self.mcp(root, "mcp__kubernetes__pods_list", ORCH)[0], "deny")


class SecretDumps(AgentCase):
    def test_dump_asks_and_disk_denies(self):
        for agent in ("", "cecilia-devops"):
            d, why = self.cmd("kubectl get all,cm,secret -o yaml", agent=agent)
            self.assertEqual(d, "ask")
            self.assertIn("prints secret values into the transcript", why)
        self.assertEqual(self.cmd("oc get secret/db -ojsonpath={.data.pw}", agent="")[0], "ask")
        for c in ("kubectl get all,cm,secret -o yaml > dump.yaml", "kubectl get secrets.v1 -o json | tee s.json",
                  "kubectl get cm,secret --output=go-template={{.data}} >> /tmp/s.txt"):
            with self.subTest(c=c):
                d, why = self.cmd(c, agent="")
                self.assertEqual(d, "deny")
                self.assertIn("writes cluster secrets to disk in plain text", why)

    def test_not_a_dump(self):
        pol = G.POLICY
        for c in ("kubectl get all,cm,secret", "kubectl get cm -o yaml", "kubectl describe secret db",
                  "kubectl get secret/db -o name", "etcdctl get /registry/pods --prefix",
                  "etcdctl get '' --prefix --keys-only"):
            with self.subTest(c=c):
                self.assertIsNone(G.secret_dump(G.split_segments(c)[0], pol))
        self.assertNotIn("transcript", self.cmd("kubectl get all,cm,secret", agent="")[1])
        self.assertEqual(self.cmd("etcdctl get /registry/pods --prefix", agent="")[0], "allow")

    def test_etcd_secrets_denied(self):
        for c in ("etcdctl get /registry/secrets/default/db", "etcdctl get '' --prefix",
                  "ETCDCTL_API=3 etcdctl --endpoints=https://10.0.0.1:2379 get /registry/secrets --prefix"):
            with self.subTest(c=c):
                self.assertEqual(self.cmd(c, agent="")[0], "deny")


if __name__ == "__main__":
    unittest.main()
