"""v20.1 approval linter + --all.  python3 -m unittest tests.test_v21_approve -q"""
import argparse
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "guard"))
import cecilia_approve as A  # noqa: E402

PY = sys.executable
APPROVE = str(ROOT / "guard" / "cecilia_approve.py")

CLEAN = {
    "task": "K8S-7-B01",
    "write": ["manifests/kong/**", "tensura/reports/K8S-7/**"],
    "commands": [
        "POD=$(kubectl -n dev get pod -l app=kong -o name | head -1); test -n \"$POD\" && kubectl -n dev describe $POD",
        "cp /var/lib/etcd/snap.db /backup/snap.db && sha256sum /var/lib/etcd/snap.db | sed 's#/var/lib/etcd#/backup#' > /tmp/s",
        "sha256sum -c /tmp/s",
        "rm -f /var/lib/etcd/snap.db",
        "kubectl get secrets -A -o name",
        "for n in a b; do echo $n; done",
        "ssh node1 'crictl pods --name $POD_NAME'",
        "awk '{print $NF}' /tmp/x",
    ],
    "vars": {"POD_NAME": "kong-7d9f8c6b5-abcde"},
    "environments": ["local"],
    "expires_hours": 24,
}

DEFECTS = {
    "unset_var": ('test -z "$(ssh node1 sudo crictl pods -q --id $POD_SANDBOX_ID)"', "$POD_SANDBOX_ID"),
    "unset_var_remote": ("ssh node1 'test -z \"$(ip link | grep $VETH_NAME)\"'", "$VETH_NAME"),
    "unset_braced": ('test -z "$(ls /var/lib/kubelet/pods/${POD_UID})"', "$POD_UID"),
    "placeholder": ("kubectl -n dev delete pod kong-xxx --wait", "xxx"),
    "angle": ("kubectl -n dev logs <pod-name>", "<...>"),
    "swallow": ("calicoctl ipam release --ip=10.0.0.5 || true", "swallowed"),
    "swallow_ps": ("Remove-Item C:\\x -ErrorAction SilentlyContinue", "swallowed"),
    "delete": ("rm -f /backup/etcd-snapshot.db", "deletes before any verification"),
    "secrets": ("kubectl get all,cm,secret,pvc -A -o yaml > /tmp/cluster-dump.yaml", "Secret"),
    "etcd_secrets": ("etcdctl get /registry/secrets --prefix", "Secret"),
}


def scope_block(scope):
    return "```cecilia-scope\n" + json.dumps(scope, indent=2) + "\n```\n"


class Workspace:
    """temp dir: <tmp>/k8s (project) + <tmp>/k8s.cecilia (workspace with config pointing at it)."""

    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.proj = self.tmp / "k8s"
        (self.proj / "manifests").mkdir(parents=True)
        self.ws = self.tmp / "k8s.cecilia"
        (self.ws / ".cecilia").mkdir(parents=True)
        (self.ws / ".cecilia" / "config.json").write_text(json.dumps({"workspace": {"project": str(self.proj)}}))
        (self.ws / "tensura" / "plans").mkdir(parents=True)

    def plan(self, *scopes, text="# Plan\n\n## Root cause\nkong crashloops [verified] by kubectl logs\n\n"):
        p = self.ws / "tensura" / "plans" / "K8S-7.md"
        p.write_text(text + "".join(scope_block(s) for s in scopes), encoding="utf-8")
        return p

    def approvals(self):
        return sorted(f.stem for f in (self.ws / ".cecilia" / "approvals").glob("*.json"))


def errors(scope, proj):
    return [m for lvl, m in A.lint_scope(scope, proj, "") if lvl == A.ERROR]


def run_approve(ws, plan, answer, **kw):
    ns = argparse.Namespace(plan=str(plan), task=kw.get("task"), all=kw.get("all", False), hours=None)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = A.cmd_approve(ns, ws, ask=lambda _p: answer, tty_check=lambda: None)
    return rc, buf.getvalue()


class Lint(unittest.TestCase):
    def setUp(self):
        self.w = Workspace()

    def test_clean_scope_has_no_error(self):
        self.assertEqual(errors(CLEAN, self.w.proj), [])

    def test_each_defect_flagged(self):
        for name, (cmd, needle) in DEFECTS.items():
            with self.subTest(name):
                s = dict(CLEAN, commands=[cmd], vars={})
                errs = errors(s, self.w.proj)
                self.assertTrue(errs, f"{name} not flagged")
                self.assertTrue(any(needle in e for e in errs), errs)
                self.assertTrue(any(cmd in e for e in errs), "message names the offending command")

    def test_vars_key_resolves_variable(self):
        cmd = DEFECTS["unset_var"][0]
        self.assertTrue(errors(dict(CLEAN, commands=[cmd], vars={}), self.w.proj))
        self.assertEqual(errors(dict(CLEAN, commands=[cmd], vars={"POD_SANDBOX_ID": "3f2a9c"}), self.w.proj), [])

    def test_assignment_forms(self):
        ok = ["X=1; echo $X", "export X=1 && echo ${X}", "read -r X; echo $X", "for X in a; do echo $X; done",
              "$X = 'a'; Write-Output $X", "$env:X = 'a'; echo $env:X", "echo ${X:-default}", "echo $HOME $PWD $1 $?",
              "echo $env:USERPROFILE", "jq -r '.[$k]' --arg k v f.json"]
        for c in ok:
            with self.subTest(c):
                self.assertEqual(errors(dict(CLEAN, commands=[c], vars={}), self.w.proj), [])
        self.assertTrue(errors(dict(CLEAN, commands=["echo $X; X=1"], vars={}), self.w.proj))   # used before set

    def test_write_path_doubling_project_folder(self):
        errs = errors(dict(CLEAN, write=["k8s/manifests/kong/**"]), self.w.proj)
        self.assertTrue(any("project folder name" in e for e in errs), errs)
        (self.w.proj / "k8s").mkdir()                    # a real k8s/ subfolder makes the path legitimate
        self.assertEqual(errors(dict(CLEAN, write=["k8s/manifests/kong/**"]), self.w.proj), [])

    def test_delete_after_verify_ok_and_subcommand_rm_ignored(self):
        self.assertEqual(errors(dict(CLEAN, commands=["cmp a b && rm -f a"]), self.w.proj), [])
        self.assertEqual(errors(dict(CLEAN, commands=["etcdutl snapshot status s.db", "rm s.db.old"]), self.w.proj), [])
        self.assertEqual(errors(dict(CLEAN, commands=["docker rm old-box", "git rm -r --cached x"]), self.w.proj), [])
        self.assertTrue(errors(dict(CLEAN, commands=["rm -f a && cmp a b"]), self.w.proj))

    def test_secret_names_allowed(self):
        for c in ("kubectl get secrets -A -o name", "kubectl get secret -n dev", "kubectl get all -A -o yaml"):
            with self.subTest(c):
                self.assertEqual(errors(dict(CLEAN, commands=[c]), self.w.proj), [])

    def test_root_cause_warning(self):
        plan = "# P\n## Root cause\nprobably DNS\n## Steps\nx [verified]\n"
        lv = A.lint_scope(CLEAN, self.w.proj, plan)
        self.assertEqual([lvl for lvl, _ in lv], [A.WARN])
        vi = "# P\n## Nguyên nhân\nDNS hỏng\n"
        self.assertEqual([lvl for lvl, _ in A.lint_scope(CLEAN, self.w.proj, vi)], [A.WARN])
        self.assertEqual(A.lint_scope(CLEAN, self.w.proj, "## Root cause\nDNS [verified] dig\n"), [])

    def test_lint_cli(self):
        bad = self.w.plan(CLEAN, dict(CLEAN, task="K8S-7-B02", commands=[DEFECTS["placeholder"][0]]))
        r = subprocess.run([PY, APPROVE, "lint", str(bad)], capture_output=True, text=True, cwd=self.w.ws)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("[K8S-7-B02]", r.stdout)
        self.assertIn("kong-xxx", r.stdout)
        self.assertIn("send the plan back to cecilia-plan", r.stdout.lower())
        self.assertEqual(self.w.approvals(), [])
        good = self.w.plan(CLEAN)
        r = subprocess.run([PY, APPROVE, "lint", str(good)], capture_output=True, text=True, cwd=self.w.ws)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class ApproveAll(unittest.TestCase):
    def setUp(self):
        self.w = Workspace()
        self.scopes = [dict(CLEAN, task=f"K8S-7-B0{i}") for i in (1, 2, 3)]

    def test_all_approves_every_block(self):
        plan = self.w.plan(*self.scopes)
        rc, out = run_approve(self.w.ws, plan, "approve 3", all=True)
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.w.approvals(), ["K8S-7-B01", "K8S-7-B02", "K8S-7-B03"])
        for t in ("K8S-7-B01", "K8S-7-B02", "K8S-7-B03"):
            self.assertIn(t, out)
        rec = json.loads((self.w.ws / ".cecilia" / "approvals" / "K8S-7-B02.json").read_text())
        for key in ("task", "write", "commands", "environments", "approved_by", "approved_at", "expires_at",
                    "plan", "plan_sha256", "block_sha256", "revoked", "tool"):
            self.assertIn(key, rec)
        self.assertNotIn("vars", rec)                     # record format unchanged

    def test_all_needs_confirmation(self):
        plan = self.w.plan(*self.scopes)
        rc, out = run_approve(self.w.ws, plan, "K8S-7-B01", all=True)
        self.assertEqual(rc, 1)
        self.assertIn("Cancelled", out)
        self.assertEqual(self.w.approvals(), [])

    def test_one_error_blocks_everything(self):
        bad = dict(CLEAN, task="K8S-7-B02", commands=[DEFECTS["swallow"][0]])
        plan = self.w.plan(self.scopes[0], bad, self.scopes[2])
        rc, out = run_approve(self.w.ws, plan, "approve 3", all=True)
        self.assertEqual(rc, 1)
        self.assertIn("[K8S-7-B02]", out)
        self.assertIn("|| true", out)
        self.assertEqual(self.w.approvals(), [])

    def test_task_still_works_and_is_linted(self):
        bad = dict(CLEAN, task="K8S-7-B02", write=["k8s/manifests/**"])
        plan = self.w.plan(self.scopes[0], bad)
        rc, out = run_approve(self.w.ws, plan, "K8S-7-B01", task="K8S-7-B01")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.w.approvals(), ["K8S-7-B01"])
        rc, out = run_approve(self.w.ws, plan, "K8S-7-B02", task="K8S-7-B02")
        self.assertEqual(rc, 1)
        self.assertIn("project folder name", out)
        self.assertEqual(self.w.approvals(), ["K8S-7-B01"])

    def test_several_blocks_without_flag_asks_to_choose(self):
        plan = self.w.plan(*self.scopes)
        rc, out = run_approve(self.w.ws, plan, "approve 3")
        self.assertEqual(rc, 1)
        self.assertIn("--all", out)
        self.assertEqual(self.w.approvals(), [])

    def test_all_refuses_without_terminal(self):
        plan = self.w.plan(*self.scopes)
        r = subprocess.run([PY, APPROVE, str(plan), "--all"], input="approve 3\n", capture_output=True, text=True,
                           cwd=self.w.ws)
        self.assertEqual(r.returncode, 2)
        self.assertIn("interactive terminal", r.stderr)
        self.assertEqual(self.w.approvals(), [])


if __name__ == "__main__":
    unittest.main()
