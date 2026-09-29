"""V21 consensus + inbox in skills/cecilia-orchestrator/scripts/workflow.py: tally, suggest-mode, decision, answer,
inbox. Stdlib only; temp workspaces with a minimal config + registry (same fixtures as test_v20_workflow)."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "cecilia-orchestrator" / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import workflow as W  # noqa: E402
from test_v20_workflow import OPTIONS, REGISTRY  # noqa: E402

TASK = "SHOP-42"


def item(iid, vote, evidence="src/order.py:12", **kw):
    return dict({"id": iid, "vote": vote, "evidence": evidence, "reason": f"{vote} on {iid}"}, **kw)


class WorkflowV21(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)
        (self.ws / ".cecilia").mkdir()
        self.config({})
        (self.ws / ".cecilia" / "registry.json").write_text(json.dumps(REGISTRY), encoding="utf-8")
        self.task = self.ws / "tensura" / "tasks" / TASK

    def tearDown(self):
        self.tmp.cleanup()

    def config(self, extra):
        cfg = {"roles": {r: True for r in REGISTRY["roles"]}, "flow": "personal", "fix_loop": {"max_rounds": 3}}
        cfg.update(extra)
        (self.ws / ".cecilia" / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    def mode(self, m):
        (self.ws / ".cecilia" / "mode.json").write_text(json.dumps({"mode": m}), encoding="utf-8")

    def cli(self, *args, task=True):
        out, err = io.StringIO(), io.StringIO()
        argv = [args[0], "--workspace", str(self.ws)] + (["--task", TASK] if task else []) + list(args[1:])
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = W.main(argv)
        return code, out.getvalue(), err.getvalue()

    def ballot(self, stage, voter, items, model="opus", **kw):
        d = self.task / "votes" / stage
        d.mkdir(parents=True, exist_ok=True)
        b = dict({"voter": voter, "model": model, "stage": stage, "items": items}, **kw)
        (d / f"{voter}.json").write_text(json.dumps(b), encoding="utf-8")

    def result(self, stage):
        return json.loads((self.task / "votes" / f"{stage}-result.json").read_text(encoding="utf-8"))

    # --- tally --------------------------------------------------------------------------------------------------

    def test_tally_majority_open_rejected(self):
        self.ballot("plan", "v1", [item("P1", "agree"), item("P2", "agree"), item("P3", "disagree")], model="opus")
        self.ballot("plan", "v2", [item("P1", "agree"), item("P2", "disagree"), item("P3", "disagree")],
                    model="sonnet")
        self.ballot("plan", "v3", [item("P1", "disagree"), item("P2", "abstain"), item("P3", "agree")],
                    model="sonnet")
        code, out, err = self.cli("tally", "--stage", "plan")
        self.assertEqual(code, 0, err)
        res = json.loads(out)
        got = {i["id"]: i["result"] for i in res["items"]}
        self.assertEqual(got, {"P1": "adopted", "P2": "open", "P3": "rejected"})
        self.assertEqual((res["valid_voters"], res["independence"]), (3, "strong"))
        self.assertEqual(res["vetoes"], [])
        self.assertTrue((self.task / "votes" / "plan-result.md").is_file())
        self.assertEqual(self.result("plan")["summary"], {"adopted": 1, "rejected": 1, "open": 1})

    def test_evidence_less_ballot_is_discarded(self):
        self.ballot("plan", "v1", [item("P1", "agree")])
        self.ballot("plan", "v2", [item("P1", "agree")], model="sonnet")
        self.ballot("plan", "v3", [item("P1", "disagree", evidence="  ")])
        (self.task / "votes" / "plan" / "broken.json").write_text("{not json", encoding="utf-8")
        (self.task / "votes" / "plan" / "v4.json").write_text(json.dumps(
            {"voter": "v4", "model": "haiku", "stage": "review", "items": [item("P1", "disagree")]}), encoding="utf-8")
        code, out, err = self.cli("tally", "--stage", "plan")
        self.assertEqual(code, 0, err)
        res = json.loads(out)
        self.assertEqual(res["valid_voters"], 2)
        self.assertEqual([d["voter"] for d in res["discarded"]], ["v3"])
        self.assertEqual(sorted(x["file"] for x in res["invalid"]), ["broken.json", "v4.json"])
        self.assertEqual(res["items"][0]["result"], "adopted")

    def test_fewer_than_two_valid_voters_exit_2(self):
        self.ballot("plan", "v1", [item("P1", "agree")])
        self.ballot("plan", "v2", [item("P1", "agree", evidence="")])
        code, _, err = self.cli("tally", "--stage", "plan")
        self.assertEqual(code, 2)
        self.assertIn("at least 2", err)
        self.assertFalse((self.task / "votes" / "plan-result.json").exists())

    def test_safety_veto_in_controlled_never_outvoted(self):
        self.mode("controlled")
        self.ballot("plan", "v1", [item("P1", "agree", safety="data-loss")], model="opus")
        self.ballot("plan", "v2", [item("P1", "disagree")], model="sonnet")
        self.ballot("plan", "v3", [item("P1", "disagree")], model="haiku")
        code, out, err = self.cli("tally", "--stage", "plan")
        self.assertEqual(code, 0, err)
        res = json.loads(out)
        self.assertTrue(res["safety_veto"])
        self.assertEqual(res["items"][0]["result"], "rejected")
        self.assertEqual([(v["item"], v["safety"], v["voter"]) for v in res["vetoes"]], [("P1", "data-loss", "v1")])
        # STANDARD: the veto is off unless config says "always"
        self.mode("standard")
        self.assertEqual(json.loads(self.cli("tally", "--stage", "plan")[1])["vetoes"], [])
        self.config({"consensus": {"safety_veto": "always"}})
        self.assertEqual(len(json.loads(self.cli("tally", "--stage", "plan")[1])["vetoes"]), 1)

    def test_review_severity_and_weak_independence(self):
        self.ballot("review", "r1", [item("F1", "agree", severity="SHOULD-FIX")], model="sonnet")
        self.ballot("review", "r2", [item("F1", "agree", severity="BLOCKER")], model="sonnet")
        self.ballot("review", "r3", [item("F1", "agree", severity="NIT"), item("F2", "disagree")], model="sonnet")
        code, out, err = self.cli("tally", "--stage", "review")
        self.assertEqual(code, 0, err)
        res = json.loads(out)
        self.assertEqual(res["independence"], "weak")
        f1 = next(i for i in res["items"] if i["id"] == "F1")
        self.assertEqual((f1["result"], f1["severity"]), ("adopted", "BLOCKER"))   # 1-1-1 tie -> more severe
        self.assertIn("weak", (self.task / "votes" / "review-result.md").read_text(encoding="utf-8"))

    # --- suggest-mode ---------------------------------------------------------------------------------------------

    def scope(self, **signals):
        self.task.mkdir(parents=True, exist_ok=True)
        (self.task / "scope.json").write_text(json.dumps({
            "task": TASK, "goal": "Export orders as CSV", "out_of_scope": ["PDF export"],
            "done_when": ["GET /orders.csv returns 200"], "signals": signals}), encoding="utf-8")

    def test_suggest_mode_from_signals(self):
        self.scope(production=True, secrets=False, migration=True)
        code, out, err = self.cli("suggest-mode")
        self.assertEqual(code, 0, err)
        res = json.loads(out)
        self.assertEqual((res["suggested"], res["command"]), ("controlled", "cecilia mode controlled"))
        self.assertIn("production", res["why"])
        self.scope()
        res = json.loads(self.cli("suggest-mode")[1])
        self.assertEqual((res["suggested"], res["command"]), ("standard", None))
        (self.task / "scope.json").unlink()
        self.assertEqual(self.cli("suggest-mode")[0], 2)

    # --- decision + answer ------------------------------------------------------------------------------------------

    def prepare_card(self):
        self.scope(live_cluster=True)
        p = self.ws / "opts.json"
        opts = json.loads(json.dumps(OPTIONS))
        opts["options"][1]["recommended"] = True
        opts["options"][1]["risk"] = "export touches the order query"
        p.write_text(json.dumps(opts), encoding="utf-8")
        self.assertEqual(self.cli("options", "--input", str(p))[0], 0)
        self.ballot("plan", "v1", [item("A", "disagree"), item("B", "agree"), item("P7", "agree")], model="opus")
        self.ballot("plan", "v2", [item("A", "agree"), item("B", "agree"), item("P7", "disagree")], model="sonnet")
        self.ballot("plan", "v3", [item("B", "agree"), item("P7", "abstain")], model="sonnet")
        self.assertEqual(self.cli("tally", "--stage", "plan")[0], 0)
        code, out, err = self.cli("decision")
        self.assertEqual(code, 0, err)
        return json.loads(out)

    def test_decision_card_assembled(self):
        res = self.prepare_card()
        card = json.loads((self.ws / "tensura" / "decisions" / f"{TASK}.json").read_text(encoding="utf-8"))
        self.assertEqual(card, res["card"])
        self.assertEqual(card["status"], "open")
        self.assertEqual(card["scope"]["goal"], "Export orders as CSV")
        self.assertEqual((card["mode"]["suggested"], card["mode"]["command"]), ("controlled", "cecilia mode controlled"))
        opts = {o["id"]: o for o in card["options"]}
        self.assertEqual((opts["A"]["votes"], opts["B"]["votes"]), ("1/3", "3/3"))
        self.assertTrue(opts["B"]["recommended"] and not opts["A"]["recommended"])
        self.assertEqual(opts["B"]["risk"], "export touches the order query")
        qs = card["questions"]
        self.assertEqual([(q["id"], q["item"]) for q in qs], [("Q1", "P7")])     # option ids are not questions
        self.assertEqual(qs[0]["default"], "disagree")                           # 1-1 tie -> the safer side
        self.assertEqual(card["independence"], "strong")
        md = (self.ws / "tensura" / "decisions" / f"{TASK}.md").read_text(encoding="utf-8")
        for s in ("Goal: Export orders as CSV", "PDF export", "cecilia mode controlled", "| **B** |", "Q1",
                  "Reply with the option id (e.g. A)"):
            self.assertIn(s, md)
        self.assertTrue(md.isascii())

    def test_answer_creates_workflow_and_answers_card(self):
        self.prepare_card()
        code, out, err = self.cli("answer", "--option", "B", "--answers", '{"Q1": "agree"}', "--by", "Cecilia")
        self.assertEqual(code, 0, err)
        wf = json.loads((self.task / "workflow.json").read_text(encoding="utf-8"))
        self.assertEqual(wf["chosen"], "B")
        card = json.loads((self.ws / "tensura" / "decisions" / f"{TASK}.json").read_text(encoding="utf-8"))
        self.assertEqual(card["status"], "answered")
        self.assertEqual((card["answer"]["option"], card["answer"]["answers"], card["answer"]["by"]),
                         ("B", {"Q1": "agree"}, "Cecilia"))
        self.assertEqual(json.loads(out)["hash"], wf["hash"])
        self.assertEqual(self.cli("answer", "--option", "A")[0], 2)             # already answered

    def test_answer_refuses_bad_option_and_bad_answers(self):
        self.assertEqual(self.cli("answer", "--option", "B")[0], 2)             # no card yet
        self.prepare_card()
        code, _, err = self.cli("answer", "--option", "Z")
        self.assertEqual(code, 2)
        self.assertIn("unknown option", err)
        self.assertEqual(self.cli("answer", "--option", "B", "--answers", '{"Q9": "agree"}')[0], 2)
        self.assertEqual(self.cli("answer", "--option", "B", "--answers", '{"Q1": "maybe"}')[0], 2)
        self.assertFalse((self.task / "workflow.json").exists())
        card = json.loads((self.ws / "tensura" / "decisions" / f"{TASK}.json").read_text(encoding="utf-8"))
        self.assertEqual((card["status"], card["answer"]), ("open", None))

    def test_answer_leaves_card_open_when_choose_fails(self):
        self.prepare_card()
        self.assertEqual(self.cli("choose", "--option", "A")[0], 0)            # workflow.json already frozen
        code, _, err = self.cli("answer", "--option", "B")
        self.assertEqual(code, 2)
        self.assertIn("already chose", err)
        card = json.loads((self.ws / "tensura" / "decisions" / f"{TASK}.json").read_text(encoding="utf-8"))
        self.assertEqual(card["status"], "open")

    def test_veto_becomes_a_question(self):
        self.prepare_card()
        self.mode("controlled")                     # after `options`: the fixture options are STANDARD panels
        self.ballot("review", "r1", [item("F1", "disagree", safety="secret")], model="opus")
        self.ballot("review", "r2", [item("F1", "disagree")], model="sonnet")
        self.assertEqual(self.cli("tally", "--stage", "review")[0], 0)
        card = json.loads(self.cli("decision")[1])["card"]
        self.assertEqual([(v["stage"], v["item"], v["safety"]) for v in card["vetoes"]], [("review", "F1", "secret")])
        v = next(q for q in card["questions"] if q["id"] == "V1")
        self.assertEqual([c["id"] for c in v["choices"]], ["safeguard", "drop"])
        self.assertIsNone(card["mode"]["command"])                              # already CONTROLLED

    # --- inbox ------------------------------------------------------------------------------------------------------

    def test_inbox_add_list_take_done(self):
        code, out, err = self.cli("inbox", "add", "--prompt", "add CSV export", "--source", "mcp", task=False)
        self.assertEqual(code, 0, err)
        first = json.loads(out)
        self.assertRegex(first["id"], r"^IN-\d{8}-\d{6}-[0-9a-f]{4}$")
        self.assertEqual((first["status"], first["task"], first["source"]), ("new", None, "mcp"))
        second = json.loads(self.cli("inbox", "add", "--prompt", "fix login", task=False)[1])
        p = self.ws / "tensura" / "inbox" / f"{second['id']}.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        data["created"] = "2999-01-01T00:00:00+00:00"                          # force the order
        p.write_text(json.dumps(data), encoding="utf-8")
        listed = json.loads(self.cli("inbox", "list", task=False)[1])
        self.assertEqual([x["id"] for x in listed], [second["id"], first["id"]])
        out = self.cli("inbox", "take", first["id"], "--task", TASK, task=False)[1]
        self.assertEqual((json.loads(out)["status"], json.loads(out)["task"]), ("taken", TASK))
        self.assertEqual(self.cli("inbox", "take", first["id"], "--task", TASK, task=False)[0], 2)
        self.assertEqual([x["id"] for x in json.loads(self.cli("inbox", "list", "--status", "new", task=False)[1])],
                         [second["id"]])
        self.assertEqual(json.loads(self.cli("inbox", "done", first["id"], task=False)[1])["status"], "done")
        self.assertEqual(self.cli("inbox", "done", first["id"], task=False)[0], 2)
        self.assertEqual(self.cli("inbox", "done", "../../x", task=False)[0], 2)
        # --workspace after the action works too
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = W.main(["inbox", "list", "--workspace", str(self.ws), "--status", "done"])
        self.assertEqual((code, [x["id"] for x in json.loads(out.getvalue())]), (0, [first["id"]]))


if __name__ == "__main__":
    unittest.main()
