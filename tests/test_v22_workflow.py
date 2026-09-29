"""V22 (20.2) ballot provenance in workflow.py tally/decision: the last .cecilia/provenance.jsonl writer of each
ballot decides verified / unverified / discarded. Stdlib only; reuses the v21 fixtures."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
import test_v21_workflow as V21  # noqa: E402

TASK, item = V21.TASK, V21.item


class WorkflowV22(V21.WorkflowV21):
    """Reuses the v21 fixtures; the inherited v21 tests are switched off below."""

    def prov(self, stage, voter, agent, actor, host="antigravity", model="flash", path=None):
        rec = {"ts": "2026-09-29T10:00:00+00:00", "host": host,
               "path": path or f"tensura/tasks/{TASK}/votes/{stage}/{voter}.json",
               "agent": agent, "actor": actor, "model": model}
        with (self.ws / ".cecilia" / "provenance.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

    def three(self, stage="plan"):
        self.ballot(stage, "v1", [item("P1", "agree")], model="opus")
        self.ballot(stage, "v2", [item("P1", "agree")], model="sonnet")
        self.ballot(stage, "v3", [item("P1", "disagree")], model="sonnet")

    def tally(self, stage="plan"):
        code, out, err = self.cli("tally", "--stage", stage)
        self.assertEqual(code, 0, err)
        return json.loads(out)

    def test_verified_via_distinct_actors(self):
        self.three()
        self.prov("plan", "v1", "cecilia-plan", "conv-a")
        self.prov("plan", "v2", "plan", "conv-b")                 # short role name is normalised
        self.prov("plan", "v3", "cecilia-plan", "conv-c", path=f"tensura\\tasks\\{TASK}\\votes\\plan\\v3.json")
        res = self.tally()
        self.assertEqual(res["independence"], "verified")
        self.assertEqual({k: res["provenance"][k] for k in ("verified", "unverified", "discarded", "actors")},
                         {"verified": 3, "unverified": 0, "discarded": 0, "actors": 3})
        self.assertNotIn("WARNING", (self.task / "votes" / "plan-result.md").read_text(encoding="utf-8"))

    def test_verified_needs_two_models(self):
        self.ballot("plan", "v1", [item("P1", "agree")], model="flash")
        self.ballot("plan", "v2", [item("P1", "agree")], model="flash")
        self.prov("plan", "v1", "cecilia-plan", "conv-a")
        self.prov("plan", "v2", "cecilia-plan", "conv-b")
        res = self.tally()
        self.assertEqual((res["independence"], res["provenance"]["verified"]), ("weak", 2))

    def test_orchestrator_written_ballot_discarded(self):
        self.three()
        self.prov("plan", "v1", "cecilia-plan", "conv-a")
        self.prov("plan", "v2", "cecilia-plan", "conv-b")
        self.prov("plan", "v3", "cecilia-plan", "conv-c")
        self.prov("plan", "v3", "", "conv-main")                  # last writer: antigravity main agent
        res = self.tally()
        self.assertEqual(res["valid_voters"], 2)
        self.assertEqual(res["items"][0]["result"], "adopted")
        d = [x for x in res["discarded"] if x["voter"] == "v3"]
        self.assertEqual(d[0]["reason"], "written by the orchestrator")
        self.assertEqual(res["provenance"]["discarded"], 1)
        # an explicit cecilia-orchestrator on any host, too
        self.prov("plan", "v2", "cecilia-orchestrator", "sess-1", host="claude")
        code, _, err = self.cli("tally", "--stage", "plan")
        self.assertEqual(code, 2)
        self.assertIn("written by the orchestrator", err)

    def test_same_actor_second_ballot_not_verified(self):
        self.three()
        self.prov("plan", "v1", "cecilia-plan", "conv-a")
        self.prov("plan", "v2", "cecilia-plan", "conv-a")
        self.prov("plan", "v3", "cecilia-plan", "conv-c")
        res = self.tally()
        st = {v["voter"]: v["provenance"] for v in res["voters"]}
        self.assertEqual(st, {"v1": "verified", "v2": "unverified", "v3": "verified"})
        self.assertEqual(res["independence"], "strong")
        self.assertEqual((res["provenance"]["actors"], res["provenance"]["unverified"]), (2, 1))
        self.assertIn("same actor as v1", res["unverified"][0]["reason"])

    def test_wrong_role_is_unverified(self):
        self.three(stage="rootcause")
        self.prov("rootcause", "v1", "cecilia-devops", "conv-a")
        self.prov("rootcause", "v2", "cecilia-discovery", "conv-b")
        self.prov("rootcause", "v3", "cecilia-dev-be", "conv-c")
        res = self.tally("rootcause")
        self.assertEqual({v["voter"]: v["provenance"] for v in res["voters"]}["v3"], "unverified")
        self.assertEqual(res["independence"], "strong")

    def test_require_mode_discards_missing(self):
        self.config({"consensus": {"provenance": "require"}})
        self.three()
        self.prov("plan", "v1", "cecilia-plan", "conv-a")
        self.prov("plan", "v2", "cecilia-plan", "conv-b")
        res = self.tally()
        self.assertEqual(res["valid_voters"], 2)
        self.assertEqual([x["voter"] for x in res["discarded"]], ["v3"])
        self.assertIn("no provenance line", res["discarded"][0]["reason"])
        self.assertEqual(res["independence"], "verified")
        # warn (default) keeps it, counted as unverified
        self.config({})
        res = self.tally()
        self.assertEqual((res["valid_voters"], res["provenance"]["unverified"], res["independence"]),
                         (3, 1, "strong"))

    def test_no_log_keeps_v21_behaviour(self):
        self.three()
        res = self.tally()
        self.assertEqual((res["valid_voters"], res["independence"], res["discarded"]), (3, "strong", []))
        self.assertEqual(res["provenance"]["unverified"], 3)
        self.assertFalse(res["provenance"]["log"])

    def test_card_warning(self):
        res = self.prepare_card()                                 # no provenance log -> unverified ballots
        card = res["card"]
        self.assertEqual(card["provenance"]["plan"]["unverified"], 3)
        md = (self.ws / "tensura" / "decisions" / f"{TASK}.md").read_text(encoding="utf-8")
        self.assertIn("WARNING: independence not verified (plan)", md)
        self.assertIn("plan: 0 verified, 3 unverified", md)
        self.assertTrue(md.isascii())
        self.assertTrue(any("independence not verified" in w for w in res["warnings"]))
        # all verified -> no warning, independence verified
        for v, a in (("v1", "c1"), ("v2", "c2"), ("v3", "c3")):
            self.prov("plan", v, "cecilia-plan", a)
        self.assertEqual(self.cli("tally", "--stage", "plan")[0], 0)
        card = json.loads(self.cli("decision")[1])["card"]
        self.assertEqual(card["independence"], "verified")
        md = (self.ws / "tensura" / "decisions" / f"{TASK}.md").read_text(encoding="utf-8")
        self.assertNotIn("WARNING", md)

    # --- brief for consensus voters (p1-p3 / v1-v3 / h1-h3) -------------------------------------------------------

    def chosen(self):
        p = self.ws / "opts.json"
        p.write_text(json.dumps(V21.OPTIONS), encoding="utf-8")
        self.assertEqual(self.cli("options", "--input", str(p))[0], 0)
        self.assertEqual(self.cli("choose", "--option", "B")[0], 0)
        return json.loads((self.task / "workflow.json").read_text(encoding="utf-8"))["hash"]

    def test_brief_voter_unit_without_workflow_unit(self):
        h = self.chosen()
        for unit in ("v1", "h2"):
            code, out, err = self.cli("brief", "--role", "cecilia-review", "--unit", unit, "--short")
            self.assertEqual(code, 0, err)
            header = out.splitlines()[0]
            self.assertIn(f"UNIT={unit} ", header)
            self.assertIn(f"WORKFLOW={h} ", header)
            self.assertIn("ROLE=cecilia-review ", header)

    def test_brief_voter_unit_wrong_role_or_unknown_unit_refused(self):
        self.chosen()
        for role, unit in (("cecilia-dev-be", "v1"), ("cecilia-review", "p1"), ("cecilia-review", "U9"),
                           ("cecilia-review", "v10")):
            code, _, err = self.cli("brief", "--role", role, "--unit", unit, "--short")
            self.assertEqual(code, 2, (role, unit))
            self.assertIn("is not a", err)
        self.assertEqual(self.cli("brief", "--role", "cecilia-dev-be", "--unit", "U2", "--short")[0], 0)


# keep only the v22 tests in this module (the v21 ones run in their own module)
for _n in [n for n in vars(V21.WorkflowV21) if n.startswith("test_")]:
    setattr(WorkflowV22, _n, None)

if __name__ == "__main__":
    unittest.main()
