#!/usr/bin/env python3
"""Workflow engine and optional run ledger for cecilia-orchestrator (v20). Bookkeeping only.

V20 workflow (task files under <workspace>/tensura/tasks/<TASK>/, DESIGN-V20 §4):

    workflow.py options --task SHOP-42 --input opts.json     validate 2-3 options, add [projected] estimates,
                                                              write options.json + options.md
    workflow.py choose  --task SHOP-42 --option B [--replace] freeze Cecilia's choice -> workflow.json/.md (+hash)
    workflow.py brief   --task SHOP-42 --role cecilia-dev-be [--unit U1] [--lens security] [--short] [--out]
                                                              header line + filled brief + ## Rules (must follow)
    workflow.py round   --task SHOP-42 [--show]               next fix round; exit 3 past fix_loop.max_rounds
    workflow.py agent   start|done --task SHOP-42 --id dev-be-U1-r0 [--role R --lens L --unit U]
                        [--state done|blocked|waiting|failed --sha S --tokens N]     run.json bookkeeping
    workflow.py merge-tests --task SHOP-42                    BUG lines of test-*.md -> test-summary.md (deduped)

V21 consensus and inbox (20.1, references/consensus.md; ballots in tensura/tasks/<TASK>/votes/<stage>/<voter>.json):

    workflow.py tally --task SHOP-42 --stage plan|review|rootcause|verdict
                        drop ballots/items without evidence, majority = more than half of the valid voters,
                        safety vetoes (CONTROLLED, or consensus.safety_veto "always") -> votes/<stage>-result.json/.md
                        provenance (20.2): the last .cecilia/provenance.jsonl writer of each ballot must be a voter
                        role with its own actor ("verified"); ballots written by the orchestrator are discarded;
                        consensus.provenance "warn" (default) keeps unverified ballots, "require" discards them
    workflow.py suggest-mode --task SHOP-42                   scope.json signals -> {suggested, why, command}
    workflow.py decision --task SHOP-42                       ONE card -> tensura/decisions/SHOP-42.json/.md
    workflow.py answer --task SHOP-42 --option B [--answers '{"Q1":"disagree"}'] [--by NAME] [--replace]
                                                              record the answer, then `choose` that option
    workflow.py inbox add --prompt TEXT [--source S] | list [--status new|taken|done]
                    | take ID --task SHOP-42 | done ID      queued prompts in tensura/inbox/<id>.json

The workspace is `--workspace DIR`, else the nearest folder above the cwd holding `.cecilia/config.json`.
The registry is `<ws>/.cecilia/registry.json`, else the source repo `registry/` via `tools/registry.py`, else
a minimal built-in copy. Exit codes: 0 ok · 2 invalid input or refused · 3 fix-loop round limit reached.

v18 ledger (unchanged; one active run per project, reconcile before resume, action keys never repeat):

    workflow.py plan-waves tasks.json [--max-writers N] [--resources --task SHOP-42 --db-name app]
    workflow.py --db .cecilia/run.sqlite new RUN-1 /abs/project
    workflow.py --db ... wave-add RUN-1 W1 wave.json | wave-start RUN-1 W1 | wave-done RUN-1 W1 "<evidence>"
    workflow.py --db ... transition RUN-1 WAITING_FOR_CECILIA "<checkpoint>"
    workflow.py --db ... reconcile RUN-1 "<what was checked>" ; transition RUN-1 RUNNING "<decision ref>"
    workflow.py --db ... action-begin RUN-1 pr-B01 "gh pr create --draft ..."
    workflow.py --db ... action-result RUN-1 pr-B01 SUCCEEDED "https://github.com/.../pull/31"
    workflow.py --db ... show RUN-1

It is NOT an approval authority, a scheduler or a lock service: anyone who can edit the files can edit the
data. Approvals live in .cecilia/approvals/ and are Cecilia's; the guard checks the brief header against
workflow.json on Claude Code, and cecilia_check.py reports mismatches on every host.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as _dt
import hashlib
import importlib.util
import json
import math
import re
import sqlite3
import sys
from pathlib import Path

TRANSITIONS = {
    "RUNNING": {"WAITING_FOR_CECILIA", "BLOCKED", "COMPLETED", "CANCELLED"},
    "WAITING_FOR_CECILIA": {"RUNNING", "BLOCKED", "CANCELLED"},
    "BLOCKED": {"RUNNING", "WAITING_FOR_CECILIA", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}


def now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def exact_path(s: str) -> str:
    p = Path(s)
    if not s or p.is_absolute() or ".." in p.parts or any(c in s for c in "*?[]\\") or p.as_posix() == ".":
        raise ValueError(f"output {s!r} must be an exact relative path (expand globs first)")
    return p.as_posix()


def overlap(a: str, b: str) -> bool:
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def plan_waves(tasks: list[dict], max_writers=None) -> list[list[str]]:
    """Group tasks into waves: dependencies first, no path overlap inside a wave, `exclusive` alone,
    at most `max_writers` tasks with a non-empty `writes` list per wave when a cap is given (v20 default: no cap;
    read-only tasks are free)."""
    if not tasks:
        raise ValueError("empty task list")
    ids = [t.get("id") for t in tasks]
    if any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids)):
        raise ValueError("task ids must be unique non-empty strings")
    todo = {}
    for t in tasks:
        deps = set(t.get("depends_on", []))
        if not deps <= set(ids) or t["id"] in deps:
            raise ValueError(f"task {t['id']}: unknown or self dependency")
        todo[t["id"]] = {"deps": deps, "writes": [exact_path(x) for x in t.get("writes", [])],
                         "exclusive": bool(t.get("exclusive"))}
    done: set[str] = set()
    waves = []
    while todo:
        ready = [i for i, t in todo.items() if t["deps"] <= done]
        if not ready:
            raise ValueError("dependency cycle among: " + ", ".join(sorted(todo)))
        chosen, paths = [], []
        for i in ready:
            t = todo[i]
            if any(overlap(a, b) for a in paths for b in t["writes"]):
                continue
            if chosen and (t["exclusive"] or any(todo[c]["exclusive"] for c in chosen)):
                continue
            if max_writers and t["writes"] and sum(1 for c in chosen if todo[c]["writes"]) >= max_writers:
                continue
            chosen.append(i)
            paths += t["writes"]
        waves.append(chosen)
        done.update(chosen)
        for i in chosen:
            del todo[i]
    return waves


def assign_resources(waves, task="TASK", db_name="app"):
    """Per-member runtime isolation inside each wave: port block, compose project, database names."""
    out = {}
    k = 0
    for wave in waves:              # blocks are unique across the whole run: a slow wave-1 server never
        for member in wave:         # collides with a wave-2 member
            k += 1
            slug = "".join(ch if ch.isalnum() else "_" for ch in member).lower()
            out[member] = {"ports": f"{3000 + 100 * k}-{3000 + 100 * k + 99}",
                           "db_port": 5432 + k, "compose_project": f"{task}-{member}".lower(),
                           "database": f"{db_name}_{slug}", "test_database": f"{db_name}_{slug}_test",
                           "browser_session": member}
    return out


class Ledger:
    def __init__(self, path: str | Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), timeout=5, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, project TEXT NOT NULL, state TEXT NOT NULL,
                subject TEXT, reconciled INTEGER NOT NULL DEFAULT 0, checkpoint TEXT);
            CREATE UNIQUE INDEX IF NOT EXISTS one_active ON runs(project)
                WHERE state NOT IN ('COMPLETED','CANCELLED');
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY, run TEXT NOT NULL REFERENCES runs(id),
                at TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS waves(run TEXT NOT NULL REFERENCES runs(id), id TEXT NOT NULL,
                state TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(run, id));
            CREATE TABLE IF NOT EXISTS actions(run TEXT NOT NULL REFERENCES runs(id), key TEXT NOT NULL,
                intent TEXT NOT NULL, state TEXT NOT NULL, receipt TEXT, PRIMARY KEY(run, key));
        """)

    def close(self):
        self.db.close()

    @contextlib.contextmanager
    def tx(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def _event(self, run, kind, payload):
        self.db.execute("INSERT INTO events(run, at, kind, payload) VALUES(?,?,?,?)",
                        (run, now(), kind, json.dumps(payload, sort_keys=True, ensure_ascii=False)))

    def get(self, run):
        row = self.db.execute("SELECT * FROM runs WHERE id=?", (run,)).fetchone()
        if row is None:
            raise ValueError(f"unknown run {run}")
        return dict(row)

    def _running(self, run):
        r = self.get(run)
        if r["state"] != "RUNNING":
            raise ValueError(f"run {run} is {r['state']}, not RUNNING")
        return r

    def new(self, run, project):
        if not run.strip():
            raise ValueError("run id empty")
        p = Path(project)
        if not p.is_dir():
            raise ValueError("project folder must exist")
        with self.tx():
            self.db.execute("INSERT INTO runs(id, project, state) VALUES(?,?,?)",
                            (run, str(p.resolve()), "RUNNING"))
            self._event(run, "new", {"project": str(p.resolve())})

    def set_subject(self, run, subject):
        if not subject.strip():
            raise ValueError("subject empty")
        with self.tx():
            self._running(run)
            self.db.execute("UPDATE runs SET subject=? WHERE id=?", (subject, run))
            self._event(run, "subject", {"subject": subject, "note": "evidence for older subjects is stale"})

    def reconcile(self, run, note):
        if not note.strip():
            raise ValueError("say what was reconciled")
        with self.tx():
            r = self.get(run)
            if r["state"] not in {"WAITING_FOR_CECILIA", "BLOCKED"}:
                raise ValueError("only a waiting or blocked run is reconciled")
            self.db.execute("UPDATE runs SET reconciled=1 WHERE id=?", (run,))
            self._event(run, "reconcile", {"note": note})

    def transition(self, run, state, note):
        if not note.strip():
            raise ValueError("a checkpoint or reason is required")
        with self.tx():
            r = self.get(run)
            if state not in TRANSITIONS.get(r["state"], set()):
                raise ValueError(f"cannot go from {r['state']} to {state}")
            if state == "RUNNING" and not r["reconciled"]:
                raise ValueError("reconcile before resuming")
            if state == "COMPLETED":
                if self.db.execute("SELECT 1 FROM waves WHERE run=? AND state!='DONE'", (run,)).fetchone():
                    raise ValueError("a wave is not DONE")
                if self.db.execute("SELECT 1 FROM actions WHERE run=? AND state IN ('IN_FLIGHT','UNKNOWN')",
                                   (run,)).fetchone():
                    raise ValueError("an outward action is still in flight or unknown — reconcile it first")
            self.db.execute("UPDATE runs SET state=?, checkpoint=?, reconciled=0 WHERE id=?", (state, note, run))
            self._event(run, "transition", {"from": r["state"], "to": state, "checkpoint": note,
                                            "cleanup": "not performed by the ledger"})

    def wave_add(self, run, wid, payload):
        tasks = payload.get("tasks", [])
        internal = {t.get("id") for t in tasks}
        local = [dict(t, depends_on=[d for d in t.get("depends_on", []) if d in internal]) for t in tasks]
        if len(plan_waves(local)) != 1:
            raise ValueError("these tasks cannot run together (dependency, overlap or exclusive) — split the wave")
        with self.tx():
            self._running(run)
            for dep in payload.get("depends_on_waves", []):
                if dep == wid or not self.db.execute("SELECT 1 FROM waves WHERE run=? AND id=?",
                                                     (run, dep)).fetchone():
                    raise ValueError(f"wave dependency {dep} missing or self")
            self.db.execute("INSERT INTO waves VALUES(?,?,?,?)",
                            (run, wid, "PENDING", json.dumps(payload, sort_keys=True, ensure_ascii=False)))
            self._event(run, "wave-add", {"id": wid, "tasks": [t.get("id") for t in tasks]})

    def wave_start(self, run, wid):
        with self.tx():
            self._running(run)
            row = self.db.execute("SELECT payload FROM waves WHERE run=? AND id=?", (run, wid)).fetchone()
            if not row:
                raise ValueError(f"unknown wave {wid}")
            for dep in json.loads(row["payload"]).get("depends_on_waves", []):
                d = self.db.execute("SELECT state FROM waves WHERE run=? AND id=?", (run, dep)).fetchone()
                if not d or d["state"] != "DONE":
                    raise ValueError(f"wave {dep} is not DONE")
            if self.db.execute("SELECT 1 FROM waves WHERE run=? AND state='RUNNING'", (run,)).fetchone():
                raise ValueError("another wave is running")
            if not self.db.execute("UPDATE waves SET state='RUNNING' WHERE run=? AND id=? AND state='PENDING'",
                                   (run, wid)).rowcount:
                raise ValueError(f"wave {wid} is not PENDING")
            self._event(run, "wave-start", {"id": wid})

    def wave_done(self, run, wid, evidence):
        if not evidence.strip():
            raise ValueError("evidence reference required")
        with self.tx():
            self._running(run)
            if not self.db.execute("UPDATE waves SET state='DONE' WHERE run=? AND id=? AND state='RUNNING'",
                                   (run, wid)).rowcount:
                raise ValueError(f"wave {wid} is not RUNNING")
            self._event(run, "wave-done", {"id": wid, "evidence": evidence})

    def action_begin(self, run, key, intent):
        if not key.strip() or not intent.strip():
            raise ValueError("key and intent required")
        with self.tx():
            project = self._running(run)["project"]
            old = self.db.execute("SELECT a.* FROM actions a JOIN runs r ON a.run=r.id WHERE r.project=? AND a.key=?",
                                  (project, key)).fetchone()
            if old:
                raise ValueError(f"action {key} already exists ({old['state']}) — check the remote side and the "
                                 "receipt; never repeat it blindly")
            self.db.execute("INSERT INTO actions VALUES(?,?,?,?,NULL)", (run, key, intent, "IN_FLIGHT"))
            self._event(run, "action-begin", {"key": key, "intent": intent})

    def action_result(self, run, key, state, receipt):
        if state not in {"SUCCEEDED", "FAILED", "UNKNOWN"} or not receipt.strip():
            raise ValueError("state SUCCEEDED|FAILED|UNKNOWN and a receipt are required")
        with self.tx():
            self.get(run)
            if not self.db.execute("UPDATE actions SET state=?, receipt=? WHERE run=? AND key=? "
                                   "AND state IN ('IN_FLIGHT','UNKNOWN')", (state, receipt, run, key)).rowcount:
                raise ValueError(f"action {key} missing or already settled")
            self._event(run, "action-result", {"key": key, "state": state, "receipt": receipt})

    def show(self, run):
        return {
            "run": self.get(run),
            "waves": [dict(x) for x in self.db.execute("SELECT * FROM waves WHERE run=?", (run,))],
            "actions": [dict(x) for x in self.db.execute("SELECT * FROM actions WHERE run=?", (run,))],
            "events": [dict(x) for x in self.db.execute("SELECT * FROM events WHERE run=? ORDER BY seq", (run,))],
        }


# ----------------------------------------------------------------------------------------------------------
# V20 workflow engine: options -> choose -> brief -> agent/round -> merge-tests (DESIGN-V20 §4)
# ----------------------------------------------------------------------------------------------------------

MODES = {"fast": 0, "standard": 1, "controlled": 2}
SPLITS = ("module", "layer", "competing")
AGENT_STATES = ("done", "blocked", "waiting", "failed", "cancelled")
TOKENS_IN_PER_RUN = 26500           # new input tokens per agent run (planning constant, SPEC v20)
TOKENS_OUT_PER_RUN = 7000           # output tokens per agent run
SECONDS_PER_STEP = 75               # one sequential step (a whole parallel wave counts once)
BASE_STEPS = 10                     # integrate, test, R1, R2, judge, fix, re-integrate, re-test, re-review, judge
TASK_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$")
BRIEF_MARK = "<!-- BRIEF START -->"
HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "assets" / "agent-brief-template.md"


class RoundLimit(Exception):
    """A fix round past fix_loop.max_rounds (exit 3)."""


# --- rules hash: DESIGN-V20 §3 algorithm, copied (guard and cecilia_check carry the same function) ---------------

def short(name: str) -> str:
    return name[len("cecilia-"):] if name.startswith("cecilia-") else name


def rules_files(role, flow: str, lens) -> list:
    return ["rules/_project.md"] + ([f"rules/roles/{short(role)}.md"] if role else []) + \
           [f"rules/flows/{flow}.md"] + ([f"rules/lenses/{lens}.md"] if lens else [])


def rules_hash(ws: Path, role, flow: str, lens) -> str:
    files = ["rules/_project.md"] + ([f"rules/roles/{short(role)}.md"] if role else []) + \
            [f"rules/flows/{flow}.md"] + ([f"rules/lenses/{lens}.md"] if lens else [])
    h = hashlib.sha256()
    for rel in files:
        p = ws / rel
        if p.is_file():
            h.update(rel.encode() + b"\n" + p.read_bytes() + b"\n")
    return h.hexdigest()[:12]


def option_hash(option: dict) -> str:
    """workflow.json `hash`: first 12 hex of sha256 over the canonical JSON of `option` (DESIGN-V20 §4)."""
    canon = json.dumps(option, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:12]


# --- workspace, config, registry ---------------------------------------------------------------------------

def find_workspace(given=None) -> Path:
    if given:
        ws = Path(given).resolve()
        if not (ws / ".cecilia" / "config.json").is_file():
            raise ValueError(f"{ws} has no .cecilia/config.json")
        return ws
    here = Path.cwd().resolve()
    for d in (here, *here.parents):
        if (d / ".cecilia" / "config.json").is_file():
            return d
    raise ValueError("no workspace: pass --workspace or run inside a folder with .cecilia/config.json")


def read_json(path: Path, what: str):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise ValueError(f"{what} missing: {path}")
    except ValueError as e:
        raise ValueError(f"{what} is not valid JSON ({path}): {e}")


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_config(ws: Path) -> dict:
    cfg = read_json(ws / ".cecilia" / "config.json", "config")
    if not isinstance(cfg, dict):
        raise ValueError(".cecilia/config.json must be an object")
    return cfg


def work_mode(ws: Path) -> str:
    f = ws / ".cecilia" / "mode.json"
    try:
        m = str(json.loads(f.read_text(encoding="utf-8-sig")).get("mode", "standard")).lower()
    except (OSError, ValueError, AttributeError):
        return "standard"
    return m if m in MODES else "standard"


def workflow_required(cfg: dict, mode: str) -> bool:
    frm = str((cfg.get("orchestration") or {}).get("workflow_required_from", "standard")).lower()
    return MODES.get(mode, 1) >= MODES.get(frm, 1)


def max_rounds(cfg: dict) -> int:
    try:
        return int((cfg.get("fix_loop") or {}).get("max_rounds", 3))
    except (TypeError, ValueError):
        return 3


def _fallback_registry() -> dict:
    """Minimal built-in registry: used only when neither .cecilia/registry.json nor the repo registry exists."""
    types = {"cecilia-discovery": "writer", "cecilia-design": "writer", "cecilia-plan": "writer",
             "cecilia-db": "writer", "cecilia-dev-be": "writer", "cecilia-dev-fe": "writer", "cecilia-ui": "writer",
             "cecilia-test": "tester", "cecilia-review": "reviewer", "cecilia-devops": "writer",
             "cecilia-api-ux": "reviewer", "cecilia-extend": "writer"}
    strong = {"cecilia-discovery", "cecilia-design", "cecilia-plan", "cecilia-db", "cecilia-ui", "cecilia-review",
              "cecilia-devops", "cecilia-api-ux"}
    roles = {n: {"name": n, "agent_type": t, "model": "strongest" if n in strong else "balanced",
                 "default_on": n not in {"cecilia-ui", "cecilia-extend"},
                 "report": f"tensura/reports/<TASK>/{short(n)}.md", "lane": [],
                 "lenses": {"cecilia-test": "test", "cecilia-review": "review"}.get(n)}
             for n, t in types.items()}
    test = {n: {"name": n, "kind": "test", "guide": f"skills/cecilia-test/references/lenses/{n}.md"}
            for n in ("functional", "integration", "concurrency-perf", "security", "ui", "database", "infra")}
    review = {n: {"name": n, "kind": "review", "guide": f"skills/cecilia-review/references/panel.md#{n}"}
              for n in ("correctness", "security", "data", "performance", "api-consumer", "tests", "operations",
                        "ui", "simplicity", "redteam")}
    flows = {"personal": {"name": "personal", "guide": "shared/flows/personal.md", "settings": {}},
             "team": {"name": "team", "guide": "shared/flows/team.md", "settings": {}}}
    return {"version": "builtin", "agent_types": {}, "roles": roles, "flows": flows,
            "lenses": {"test": test, "review": review}}


def _as_map(x) -> dict:
    if isinstance(x, dict):
        return x
    if isinstance(x, list):
        return {i["name"]: i for i in x if isinstance(i, dict) and isinstance(i.get("name"), str)}
    return {}


def normalize_registry(reg: dict, source: str) -> dict:
    lenses = reg.get("lenses") if isinstance(reg.get("lenses"), dict) else {}
    return {"version": reg.get("version"), "source": source, "agent_types": _as_map(reg.get("agent_types")),
            "roles": _as_map(reg.get("roles")), "flows": _as_map(reg.get("flows")),
            "lenses": {"test": _as_map(lenses.get("test")), "review": _as_map(lenses.get("review"))}}


def load_registry(ws: Path) -> dict:
    snap = ws / ".cecilia" / "registry.json"
    if snap.is_file():
        return normalize_registry(read_json(snap, "registry snapshot"), "workspace")
    repo = HERE.parents[2]
    mod_path = repo / "tools" / "registry.py"
    if mod_path.is_file() and (repo / "registry").is_dir():
        try:
            spec = importlib.util.spec_from_file_location("cecilia_registry", str(mod_path))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            ext = ws / ".cecilia" / "extensions"
            reg = mod.load(repo, extensions=ext) if ext.is_dir() else mod.load(repo)
            return normalize_registry(reg, "repo")
        except Exception as e:  # a registry mid-edit must not break bookkeeping; say so
            print(f"warning: repo registry unusable ({e}); using the built-in registry", file=sys.stderr)
    return normalize_registry(_fallback_registry(), "builtin")


def role_enabled(cfg: dict, reg: dict, role: str) -> bool:
    roles = cfg.get("roles")
    if isinstance(roles, dict) and role in roles:
        return bool(roles[role])
    return bool(reg["roles"].get(role, {}).get("default_on", True))


def agent_type(reg: dict, role: str) -> str:
    return str(reg["roles"].get(role, {}).get("agent_type", "writer"))


def default_model(cfg: dict, reg: dict, role: str) -> str:
    models = cfg.get("models") if isinstance(cfg.get("models"), dict) else {}
    return str(models.get(role) or reg["roles"].get(role, {}).get("model") or "inherit")


def lane(cfg: dict, reg: dict, role: str) -> list:
    lanes = cfg.get("lanes") if isinstance(cfg.get("lanes"), dict) else {}
    got = lanes.get(role, lanes.get(short(role)))
    if isinstance(got, list):
        return [str(x) for x in got]
    return [str(x) for x in reg["roles"].get(role, {}).get("lane") or []]


def task_dir(ws: Path, task: str) -> Path:
    if not TASK_RE.match(task or ""):
        raise ValueError(f"task id {task!r}: letters, digits, '.', '_' or '-' only")
    return ws / "tensura" / "tasks" / task


def reports_dir(ws: Path, task: str) -> Path:
    task_dir(ws, task)
    return ws / "tensura" / "reports" / task


# --- write-set overlap (conservative: compares the literal prefix before the first wildcard) -------------

def _glob_root(g: str):
    g = g.strip().replace("\\", "/")
    if not g or g.startswith("!"):
        return None
    parts = []
    for part in g.split("/"):
        if any(c in part for c in "*?[{"):
            break
        if part not in ("", "."):
            parts.append(part)
    return "/".join(parts)


def sets_overlap(a: list, b: list):
    for x in a:
        ra = _glob_root(x)
        if ra is None:
            continue
        for y in b:
            rb = _glob_root(y)
            if rb is None:
                continue
            if ra == "" or rb == "" or overlap(ra, rb):
                return x, y
    return None


# --- options ------------------------------------------------------------------------------------------------

def _half(n: int) -> int:
    return int(math.ceil(n / 2.0))


def estimate(dev: int, test: int, review: int, rounds: int, build_waves: int) -> dict:
    judge = 1 if review else 0
    first = dev + test + review * rounds + judge
    fix = _half(dev) + _half(test) + ((_half(review) * rounds + 1) if review else 0)
    runs = first + fix
    steps = BASE_STEPS + max(1, build_waves)
    secs = steps * SECONDS_PER_STEP
    return {"label": "[projected]", "agent_runs": runs, "first_pass_runs": first, "fix_round_runs": fix,
            "input_tokens": runs * TOKENS_IN_PER_RUN, "output_tokens": runs * TOKENS_OUT_PER_RUN,
            "sequential_steps": steps, "wall_seconds": secs,
            "basis": (f"runs = dev {dev} + test {test} + review {review}x{rounds} + judge {judge}; one fix round "
                      f"assumed = half dev + half test + (half review x{rounds} + 1); tokens = runs x "
                      f"{TOKENS_IN_PER_RUN} new input / x {TOKENS_OUT_PER_RUN} output; wall = {steps} sequential "
                      f"steps x {SECONDS_PER_STEP} s (a parallel wave is one step)")}


def _entry(x, key: str) -> dict:
    if isinstance(x, str):
        return {key: x}
    if isinstance(x, dict) and isinstance(x.get(key), str):
        return dict(x)
    raise ValueError(f"expected a {key} name or an object with `{key}`, got {x!r}")


def parallel_caps(cfg: dict) -> dict:
    """parallel.limits.{dev,test,review} (null = no cap); a legacy parallel.max_writers caps dev (DESIGN-V20 §2)."""
    par = cfg.get("parallel") if isinstance(cfg.get("parallel"), dict) else {}
    lim = par.get("limits") if isinstance(par.get("limits"), dict) else {}
    caps = {}
    for k in ("dev", "test", "review"):
        v = lim.get(k)
        if v is None and k == "dev":
            v = par.get("max_writers")
        if isinstance(v, int) and not isinstance(v, bool) and v > 0:
            caps[k] = v
    return caps


def build_options(ws: Path, cfg: dict, reg: dict, data: dict, task: str) -> dict:
    errs, warns = [], []
    caps = parallel_caps(cfg)
    file_mode = work_mode(ws)
    mode = str(data.get("mode") or file_mode).lower()
    if mode not in MODES:
        raise ValueError(f"mode {mode!r} must be fast, standard or controlled")
    if mode != file_mode:
        warns.append(f"mode {mode} differs from .cecilia/mode.json ({file_mode}); Cecilia switches the mode "
                     "with `cecilia mode`, the guard reads the file")
    if not workflow_required(cfg, mode):
        raise ValueError(f"{mode.upper()} needs no workflow: dispatch one role with a 3-line brief "
                         "(`workflow.py brief --short`)")
    flow = str(data.get("flow") or cfg.get("flow") or "personal")
    if reg["flows"] and flow not in reg["flows"]:
        errs.append(f"flow {flow!r} is not in the registry ({', '.join(sorted(reg['flows']))})")
    opts = data.get("options")
    limit = 3
    try:
        limit = max(2, min(3, int((cfg.get("orchestration") or {}).get("options", 3))))
    except (TypeError, ValueError):
        pass
    if not isinstance(opts, list) or not 2 <= len(opts) <= limit:
        raise ValueError(f"give 2-{limit} options (got {len(opts) if isinstance(opts, list) else 'none'})")
    panel = (cfg.get("review") or {}).get("panel") or {}
    rounds = int(panel.get("rounds", 2) or 2)
    judge_model = str(panel.get("judge_model") or "strongest")
    cfg_test_lenses = (cfg.get("test") or {}).get("lenses")
    out, seen_ids, shapes = [], set(), {}
    for n, raw in enumerate(opts, 1):
        if not isinstance(raw, dict):
            errs.append(f"option #{n} must be an object")
            continue
        oid = str(raw.get("id") or chr(64 + n))
        tag = f"option {oid}"
        if not ID_RE.match(oid) or oid in seen_ids:
            errs.append(f"{tag}: id must be unique, letters/digits/._-")
        seen_ids.add(oid)
        split = raw.get("split")
        if split not in SPLITS:
            errs.append(f"{tag}: split must be one of {', '.join(SPLITS)}")
        if split == "competing" and not str(raw.get("decision") or "").strip():
            errs.append(f"{tag}: a competing split needs `decision` — the open design decision it settles, or "
                        "'Cecilia asked'")
        role_models = raw.get("models") if isinstance(raw.get("models"), dict) else {}
        units, unit_ids = [], set()
        raw_units = raw.get("units")
        if not isinstance(raw_units, list) or not raw_units:
            errs.append(f"{tag}: `units` (the build agents) must be a non-empty list")
            raw_units = []
        for k, u in enumerate(raw_units, 1):
            if not isinstance(u, dict) or not isinstance(u.get("role"), str):
                errs.append(f"{tag}: unit #{k} needs a `role`")
                continue
            role = u["role"]
            uid = str(u.get("id") or f"U{k}")
            if not ID_RE.match(uid) or uid in unit_ids:
                errs.append(f"{tag}: unit id {uid!r} must be unique, letters/digits/._-")
            unit_ids.add(uid)
            if role not in reg["roles"]:
                errs.append(f"{tag}: {uid} role {role} is not in the registry")
                continue
            if not role_enabled(cfg, reg, role):
                errs.append(f"{tag}: {uid} role {role} is off in .cecilia/config.json — turn it on or use its "
                            "fallback owner")
            if agent_type(reg, role) != "writer":
                errs.append(f"{tag}: {uid} role {role} is a {agent_type(reg, role)}; test and review go in "
                            "`test_lenses` / `review_lenses`")
            writes = u.get("writes")
            writes = [str(w) for w in writes] if isinstance(writes, list) else lane(cfg, reg, role)
            try:
                wave = int(u.get("wave", 1))
            except (TypeError, ValueError):
                wave = 0
            if wave < 1:
                errs.append(f"{tag}: {uid} wave must be an integer >= 1")
            units.append({"id": uid, "role": role, "scope": str(u.get("scope") or ""), "writes": writes,
                          "wave": max(wave, 1),
                          "model": str(u.get("model") or role_models.get(role) or default_model(cfg, reg, role))})
        if split in ("module", "layer"):
            for i, a in enumerate(units):
                for b in units[i + 1:]:
                    if a["wave"] != b["wave"]:
                        continue
                    for x in (a, b):
                        if not x["writes"]:
                            errs.append(f"{tag}: {x['id']} ({x['role']}) has no write set; a {split} split "
                                        "compares write sets path by path")
                    hit = sets_overlap(a["writes"], b["writes"])
                    if hit:
                        errs.append(f"{tag}: {split} split write sets overlap in wave {a['wave']}: "
                                    f"{a['id']} {hit[0]} vs {b['id']} {hit[1]} — narrow them or move one to a "
                                    "later wave")
        tests = []
        test_on = role_enabled(cfg, reg, "cecilia-test") and "cecilia-test" in reg["roles"]
        for t in raw.get("test_lenses") or []:
            try:
                e = _entry(t, "lens")
            except ValueError as ex:
                errs.append(f"{tag}: {ex}")
                continue
            if e["lens"] not in reg["lenses"]["test"]:
                errs.append(f"{tag}: test lens {e['lens']} is not in the registry")
            elif isinstance(cfg_test_lenses, list) and e["lens"] not in cfg_test_lenses:
                warns.append(f"{tag}: test lens {e['lens']} is not in config test.lenses")
            if not test_on:
                errs.append(f"{tag}: test lenses need cecilia-test, which is off")
            tests.append({"lens": e["lens"], "role": "cecilia-test",
                          "model": str(e.get("model") or role_models.get("cecilia-test")
                                       or default_model(cfg, reg, "cecilia-test"))})
        if [x["lens"] for x in tests] != list(dict.fromkeys(x["lens"] for x in tests)):
            errs.append(f"{tag}: a test lens is listed twice")
        if not tests and test_on:
            warns.append(f"{tag}: no test lens — the test wave is skipped")
        rlenses = []
        for r in raw.get("review_lenses") or []:
            try:
                rlenses.append(_entry(r, "lens")["lens"])
            except ValueError as ex:
                errs.append(f"{tag}: {ex}")
        review_on = role_enabled(cfg, reg, "cecilia-review") and "cecilia-review" in reg["roles"]
        for lz in rlenses:
            if lz not in reg["lenses"]["review"]:
                errs.append(f"{tag}: review lens {lz} is not in the registry")
        if len(set(rlenses)) != len(rlenses):
            errs.append(f"{tag}: a review lens is listed twice")
        if rlenses and not review_on:
            errs.append(f"{tag}: review lenses need cecilia-review, which is off")
        if review_on:
            if "correctness" not in rlenses:
                errs.append(f"{tag}: the review panel always has the correctness lens")
            if mode == "controlled" and "redteam" not in rlenses:
                errs.append(f"{tag}: CONTROLLED panels always have redteam")
            lo, hi = (5, 6) if mode == "controlled" else (3, 4)
            if not lo <= len(rlenses) <= hi:
                warns.append(f"{tag}: {len(rlenses)} review lenses; {mode.upper()} uses {lo}-{hi} "
                             "(say why to Cecilia)")
        waves = sorted({u["wave"] for u in units}) or [1]
        per_wave = max([sum(1 for u in units if u["wave"] == w) for w in waves] or [0])
        for kind, n in (("dev", per_wave), ("test", len(tests)), ("review", len(rlenses))):
            if kind in caps and n > caps[kind]:
                errs.append(f"{tag}: {n} {kind} agents at once, config caps {kind} at {caps[kind]} "
                            "(parallel.limits / max_writers) — use more waves or ask Cecilia to raise it")
        by_role: dict = {}
        for u in units:
            by_role[u["role"]] = by_role.get(u["role"], 0) + 1
        if tests:
            by_role["cecilia-test"] = len(tests)
        if rlenses:
            by_role["cecilia-review"] = len(rlenses) * rounds + 1
        counts = {"dev": len(units), "test": len(tests), "review": len(rlenses), "judge": 1 if rlenses else 0,
                  "by_role": by_role}
        shape = json.dumps([counts, split, [t["lens"] for t in tests], sorted(rlenses)], sort_keys=True)
        if shape in shapes:
            errs.append(f"{tag}: same agents, split and lenses as option {shapes[shape]} — options must differ")
        shapes[shape] = oid
        option = {"id": oid, "title": str(raw.get("title") or raw.get("label") or oid), "summary": str(raw.get("summary") or ""),
                  "tradeoff": str(raw.get("tradeoff") or ""), "split": split,
                  "decision": str(raw.get("decision") or ""), "units": units, "build_waves": len(waves),
                  "test": tests,
                  "review": {"lenses": rlenses, "rounds": rounds, "model": default_model(cfg, reg, "cecilia-review"),
                             "judge_model": judge_model, "redteam": "redteam" in rlenses},
                  "fix_loop": {"max_rounds": max_rounds(cfg),
                               "severities": (cfg.get("fix_loop") or {}).get("severities", ["BLOCKER", "SHOULD-FIX"])},
                  "counts": counts,
                  "estimate": estimate(len(units), len(tests), len(rlenses), rounds, len(waves))}
        for k in ("risk", "rollback"):          # v21 decision card fields; only when given (hash unchanged otherwise)
            if isinstance(raw.get(k), str) and raw[k].strip():
                option[k] = raw[k].strip()
        if raw.get("recommended") is True or (isinstance(data.get("recommended"), str) and data["recommended"] == oid):
            option["recommended"] = True
        out.append(option)
    if sum(1 for o in out if o.get("recommended")) > 1:
        errs.append("only one option can be `recommended`")
    kinds = {json.dumps({k: v for k, v in o["counts"].items() if k != "by_role"}, sort_keys=True) for o in out}
    if len(out) > 1 and len(kinds) == 1:
        warns.append("every option has the same number of agents per kind; options normally differ in counts")
    if errs:
        raise ValueError("options rejected:\n  - " + "\n  - ".join(errs))
    return {"task": task, "mode": mode, "flow": flow, "created": now(), "registry": reg["source"],
            "options": out, "warnings": warns}


def _fmt_tokens(n: int) -> str:
    return f"{n / 1000:.0f}k" if n < 1_000_000 else f"{n / 1_000_000:.2f}M"


def _counts_line(o: dict) -> str:
    return " · ".join(f"{short(r)}×{c}" for r, c in o["counts"]["by_role"].items())


def options_md(doc: dict) -> str:
    L = [f"# Workflow options — {doc['task']}", "",
         f"Mode **{doc['mode'].upper()}** · flow `{doc['flow']}` · created {doc['created']} · "
         "all estimates `[projected]` (`numbers.md`)", "",
         "| Option | Split | Agents | Test lenses | Review lenses | Agent runs | Tokens in / out | Wall time |",
         "|---|---|---|---|---|---|---|---|"]
    for o in doc["options"]:
        e = o["estimate"]
        L.append(f"| **{o['id']}** {o['title']} | {o['split']} | {_counts_line(o)} | "
                 f"{', '.join(t['lens'] for t in o['test']) or '—'} | {', '.join(o['review']['lenses']) or '—'} | "
                 f"{e['agent_runs']} [projected] | {_fmt_tokens(e['input_tokens'])} / "
                 f"{_fmt_tokens(e['output_tokens'])} [projected] | ~{math.ceil(e['wall_seconds'] / 60)} min "
                 "[projected] |")
    for o in doc["options"]:
        L += ["", f"## Option {o['id']} — {o['title']}", ""]
        if o["summary"]:
            L.append(o["summary"])
        if o["tradeoff"]:
            L.append(f"Trade-off: {o['tradeoff']}")
        if o["decision"]:
            L.append(f"Competing because: {o['decision']}")
        L += ["", "| Unit | Role | Wave | Writes | Model |", "|---|---|---|---|---|"]
        for u in o["units"]:
            L.append(f"| {u['id']} | {u['role']} | W{u['wave']} | {', '.join(u['writes']) or '(lane)'} | "
                     f"{u['model']} |")
        for t in o["test"]:
            L.append(f"| test-{t['lens']} | cecilia-test | test | tests only | {t['model']} |")
        if o["review"]["lenses"]:
            L.append(f"| panel | cecilia-review × {len(o['review']['lenses'])} lenses × {o['review']['rounds']} "
                     f"rounds | review | none | {o['review']['model']} (judge {o['review']['judge_model']}) |")
        L += ["", f"Fix loop: max {o['fix_loop']['max_rounds']} rounds on judge-ACCEPTED "
                  f"{' + '.join(o['fix_loop']['severities'])}. Estimate: {o['estimate']['basis']}."]
    if doc["warnings"]:
        L += ["", "## Warnings", ""] + [f"- {w}" for w in doc["warnings"]]
    L += ["", "Cecilia chooses; then `workflow.py choose --task " + doc["task"] + " --option <ID>`.", ""]
    return "\n".join(L)


def cmd_options(ws: Path, task: str, input_path: str) -> dict:
    cfg, reg = load_config(ws), load_registry(ws)
    data = read_json(Path(input_path), "options input")
    if not isinstance(data, dict):
        raise ValueError("options input must be an object with `options`")
    doc = build_options(ws, cfg, reg, data, task)
    d = task_dir(ws, task)
    write_json(d / "options.json", doc)
    (d / "options.md").write_text(options_md(doc), encoding="utf-8")
    return {"ok": True, "options": [{"id": o["id"], "agent_runs": o["estimate"]["agent_runs"]} for o in doc["options"]],
            "warnings": doc["warnings"], "path": str(d / "options.md")}


# --- choose ---------------------------------------------------------------------------------------------

def workflow_md(wf: dict) -> str:
    o = wf["option"]
    L = [f"# Workflow — {wf['task']}", "",
         f"Chosen option **{wf['chosen']}** ({o['title']}) · mode {wf['mode'].upper()} · flow `{wf['flow']}` · "
         f"hash `{wf['hash']}` · frozen {wf['created']}", "",
         "Every brief header carries `WORKFLOW=" + wf["hash"] + "`. A change of plan = new options + a new choice.",
         "", "| Wave | Unit | Role | Writes | Model |", "|---|---|---|---|---|"]
    for u in sorted(o["units"], key=lambda x: (x["wave"], x["id"])):
        L.append(f"| W{u['wave']} | {u['id']} | {u['role']} | {', '.join(u['writes']) or '(lane)'} | {u['model']} |")
    L.append(f"| integrate | int/{wf['task']} | orchestrator (git) · conflicts → dev integrator | — | — |")
    for t in o["test"]:
        L.append(f"| test | {t['lens']} | cecilia-test | tests only | {t['model']} |")
    if o["review"]["lenses"]:
        L.append(f"| review | {', '.join(o['review']['lenses'])} | cecilia-review × {o['review']['rounds']} rounds "
                 f"+ judge | none | {o['review']['model']} / judge {o['review']['judge_model']} |")
    e = o["estimate"]
    L += ["", f"Fix loop: max {o['fix_loop']['max_rounds']} rounds · estimate {e['agent_runs']} agent runs, "
              f"{_fmt_tokens(e['input_tokens'])} in / {_fmt_tokens(e['output_tokens'])} out, "
              f"~{math.ceil(e['wall_seconds'] / 60)} min [projected]", ""]
    return "\n".join(L)


def cmd_choose(ws: Path, task: str, option_id: str, replace: bool) -> dict:
    d = task_dir(ws, task)
    doc = read_json(d / "options.json", "options.json (run `workflow.py options` first)")
    opt = next((o for o in doc.get("options", []) if o.get("id") == option_id), None)
    if opt is None:
        raise ValueError(f"no option {option_id!r} in options.json "
                         f"({', '.join(str(o.get('id')) for o in doc.get('options', []))})")
    wf_path = d / "workflow.json"
    if wf_path.is_file() and not replace:
        old = read_json(wf_path, "workflow.json")
        raise ValueError(f"workflow.json already chose {old.get('chosen')} ({old.get('hash')}); pass --replace "
                         "only when Cecilia changed her choice (briefs with the old hash stop working)")
    wf = {"task": task, "mode": doc.get("mode", "standard"), "flow": doc.get("flow", "personal"),
          "chosen": option_id, "option": opt, "created": now(), "hash": option_hash(opt)}
    write_json(wf_path, wf)
    (d / "workflow.md").write_text(workflow_md(wf), encoding="utf-8")
    run = d / "run.json"
    if not run.is_file():
        write_json(run, {"task": task, "round": 0, "agents": []})
    return {"ok": True, "chosen": option_id, "hash": wf["hash"], "path": str(wf_path)}


# --- run.json: round and agents --------------------------------------------------------------------------

def load_run(ws: Path, task: str) -> dict:
    p = task_dir(ws, task) / "run.json"
    if not p.is_file():
        return {"task": task, "round": 0, "agents": []}
    run = read_json(p, "run.json")
    run.setdefault("round", 0)
    run.setdefault("agents", [])
    return run


def cmd_round(ws: Path, task: str, show: bool) -> dict:
    cfg = load_config(ws)
    run = load_run(ws, task)
    cur, limit = int(run.get("round", 0)), max_rounds(cfg)
    if show:
        return {"task": task, "round": cur, "max_rounds": limit}
    if cur + 1 > limit:
        raise RoundLimit(f"fix round {cur + 1} would exceed fix_loop.max_rounds={limit}: stop the loop and give "
                         "Cecilia options (what is still open, re-plan, accept with a recorded risk, or stop)")
    run["round"] = cur + 1
    write_json(task_dir(ws, task) / "run.json", run)
    return {"task": task, "round": cur + 1, "max_rounds": limit}


def cmd_agent(ws: Path, a) -> dict:
    run = load_run(ws, a.task)
    agents = run["agents"]
    if not a.id or not ID_RE.match(a.id.replace(":", "-")):
        raise ValueError("--id must be a short id, e.g. dev-be-U1-r0")
    found = next((x for x in agents if x.get("id") == a.id), None)
    if a.action == "start":
        if found:
            raise ValueError(f"agent {a.id} already recorded ({found.get('state')}); use a new id per launch "
                             "(suffix -r<round>)")
        if not a.role:
            raise ValueError("start needs --role")
        agents.append({"id": a.id, "role": a.role, "lens": a.lens or None, "unit": a.unit or None,
                       "round": int(run.get("round", 0)), "state": "running", "sha": a.sha or None,
                       "started": now(), "ended": None, "tokens": a.tokens})
    else:
        if not found:
            raise ValueError(f"agent {a.id} was never started")
        if a.state not in AGENT_STATES:
            raise ValueError(f"--state must be one of {', '.join(AGENT_STATES)}")
        found.update({"state": a.state, "ended": now()})
        if a.sha:
            found["sha"] = a.sha
        if a.tokens is not None:
            found["tokens"] = a.tokens
    write_json(task_dir(ws, a.task) / "run.json", run)
    return {"ok": True, "id": a.id, "running": sum(1 for x in agents if x.get("state") == "running")}


# --- brief -----------------------------------------------------------------------------------------------

SHORT_BODY = """Task: <one sentence — what to change and the acceptance check> ({{MODE}}, flow {{FLOW}}).
Where: code in <project path> on branch <task branch> (your lane: {{WRITES}}); report to {{REPORT}}.
Done when: <the focused check passes>; return the ≤ 15-line block of your skill, ending with `Rules: {{RULES}} (PR-ids applied)`.

## Rules (must follow)

{{RULES_TEXT}}
"""


def rules_text(ws: Path, role, flow: str, lens, cap: int) -> str:
    parts = []
    for rel in rules_files(role, flow, lens):
        p = ws / rel
        if p.is_file():
            body = p.read_text(encoding="utf-8", errors="replace").strip()
            if cap and len(body.encode("utf-8")) > cap:
                print(f"warning: {rel} is larger than rules.max_bytes_per_file ({cap})", file=sys.stderr)
            parts.append(f"### {rel}\n\n{body or '(empty)'}")
    if not parts:
        parts.append("(no project rules files yet — role defaults apply)")
    return "\n\n".join(parts)


VOTER_UNIT_RX = re.compile(r"^[pvh][1-9]$")
VOTER_UNIT_ROLES = {"p": ("cecilia-plan",), "v": ("cecilia-review",),
                    "h": ("cecilia-discovery", "cecilia-devops", "cecilia-review")}


def voter_unit(unit, role: str) -> bool:
    """Consensus ids (planner p1.., voter v1.., hypothesis h1..) are briefed without a workflow unit."""
    return bool(unit and VOTER_UNIT_RX.match(unit) and role in VOTER_UNIT_ROLES[unit[0]])


def cmd_brief(ws: Path, a) -> str:
    cfg, reg = load_config(ws), load_registry(ws)
    role = a.role
    if role not in reg["roles"]:
        raise ValueError(f"role {role} is not in the registry")
    if not role_enabled(cfg, reg, role):
        raise ValueError(f"{role} is off in .cecilia/config.json — never dispatch or imitate an off role; offer "
                         "'turn it on, or use the fallback'")
    d = task_dir(ws, a.task)
    wf = read_json(d / "workflow.json", "workflow.json") if (d / "workflow.json").is_file() else None
    mode = (wf or {}).get("mode") or work_mode(ws)
    flow = (wf or {}).get("flow") or str(cfg.get("flow") or "personal")
    kind = agent_type(reg, role)
    if wf is None and not a.short and kind in ("writer", "tester") and workflow_required(cfg, mode):
        raise ValueError(f"{mode.upper()}: no workflow.json for {a.task} — run `workflow.py options` and "
                         "`workflow.py choose` (Cecilia picks) before briefing a writer or tester")
    lens = a.lens or None
    if lens:
        lk = reg["roles"][role].get("lenses")
        kinds = [lk] if lk in ("test", "review") else ["test", "review"]
        if not any(lens in reg["lenses"][k] for k in kinds):
            raise ValueError(f"lens {lens} is not a {'/'.join(kinds)} lens in the registry")
    rnd = a.round if a.round is not None else int(load_run(ws, a.task).get("round", 0))
    if rnd < 0 or rnd > max_rounds(cfg):
        raise RoundLimit(f"ROUND={rnd} is past fix_loop.max_rounds={max_rounds(cfg)}: stop and give Cecilia options")
    unit = a.unit or None
    writes, model = lane(cfg, reg, role), default_model(cfg, reg, role)
    if wf:
        opt = wf.get("option") or {}
        u = next((x for x in opt.get("units", []) if x.get("id") == unit), None) if unit else None
        if unit and u is None and voter_unit(unit, role):
            pass        # consensus voter p1-p3 / v1-v3 / h1-h3: role lane and model, no workflow unit needed
        elif unit:
            if u is None or u.get("role") != role:
                raise ValueError(f"unit {unit} is not a {role} unit of workflow option {wf.get('chosen')}")
            writes, model = u.get("writes") or writes, u.get("model") or model
        elif role == "cecilia-test" and lens:
            model = next((t.get("model") for t in opt.get("test", []) if t.get("lens") == lens), model)
        elif role == "cecilia-review":
            model = (opt.get("review") or {}).get("model") or model
    rhash = rules_hash(ws, role, flow, lens)
    header = (f"[cecilia-brief TASK={a.task} ROLE={role} LENS={lens or '-'} UNIT={unit or '-'} "
              f"WORKFLOW={(wf or {}).get('hash') or 'none'} ROUND={rnd} RULES={rhash}]")
    rep = str(reg["roles"][role].get("report") or f"tensura/reports/<TASK>/{short(role)}.md").replace("<TASK>", a.task)
    if lens and role == "cecilia-test":
        rep = f"tensura/reports/{a.task}/test-{lens}.md"
    elif lens:
        rep = f"tensura/tasks/{a.task}/panel/r1-{lens}.md"
    if unit:
        rep = rep[:-3] + f"-{unit}.md" if rep.endswith(".md") else rep
    lens_guide = "-"
    if lens:
        for k in ("test", "review"):
            if lens in reg["lenses"][k]:
                lens_guide = str(reg["lenses"][k][lens].get("guide") or "-")
                m = re.match(r"^skills/([^/]+)/(.+)$", lens_guide)
                if m:  # repo path -> path inside the role's installed skill
                    lens_guide = f"{m.group(2)} (in the {m.group(1)} skill)"
                break
    flow_guide = str(reg["flows"].get(flow, {}).get("guide") or f"shared/flows/{flow}.md")
    cap = int((cfg.get("rules") or {}).get("max_bytes_per_file", 0) or 0)
    fill = {"TASK": a.task, "ROLE": role, "ROLE_SHORT": short(role), "LENS": lens or "-", "UNIT": unit or "-",
            "WORKFLOW": (wf or {}).get("hash") or "none", "ROUND": str(rnd), "RULES": rhash, "MODE": mode.upper(),
            "FLOW": flow, "FLOW_GUIDE": flow_guide, "MODEL": model, "WRITES": " ".join(f"`{w}`" for w in writes) or "(role lane)",
            "REPORT": rep, "LENS_GUIDE": lens_guide, "DATE": _dt.date.today().isoformat(),
            "RULES_TEXT": rules_text(ws, role, flow, lens, cap)}
    if a.short:
        body = SHORT_BODY
    else:
        text = TEMPLATE.read_text(encoding="utf-8")
        if BRIEF_MARK not in text:
            raise ValueError(f"{TEMPLATE} has no {BRIEF_MARK} marker")
        body = text.split(BRIEF_MARK, 1)[1].lstrip("\n")
        if body.startswith("[cecilia-brief"):
            body = body.split("\n", 1)[1] if "\n" in body else ""
    for k, v in fill.items():
        body = body.replace("{{" + k + "}}", v)
    out = header + "\n" + body.rstrip() + "\n"
    if a.out:
        name = f"{short(role)}{'-' + lens if lens else ''}{'-' + unit if unit else ''}-r{rnd}.md"
        p = d / "briefs" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(out, encoding="utf-8")
        print(f"brief written: {p}", file=sys.stderr)
    return out


# --- merge-tests -------------------------------------------------------------------------------------------

BUG_LINE = re.compile(r"^\s*(?:[-*+]\s+|#{1,6}\s+|\|\s*)?(?:\*\*)?(BUG-(?:[a-z][a-z-]*-)?\d+)(?:\*\*)?\s*"
                      r"[—–:|·\-]\s*(.+?)\s*$")
RETEST = {"verified", "reopened", "still_open", "still open"}
SEVERITY = re.compile(r"^\s*[\[(](blocker|critical|high|medium|low|should-fix|suggestion)[\])]\s*", re.I)


SEV_CELL = re.compile(r"\b(blocker|critical|high|medium|low|should-fix|suggestion)\b", re.I)


def norm_title(t: str) -> str:
    t = SEVERITY.sub("", t.split("|")[0])
    t = re.sub(r"[^\w\s]", " ", t.lower(), flags=re.UNICODE)
    return " ".join(t.split())


def bug_section(text: str) -> list:
    """Lines of the `## Bugs` section when the report has one (cecilia-test lens template), else all lines."""
    lines = text.splitlines()
    start = next((i for i, x in enumerate(lines) if re.match(r"^##\s+Bugs\b", x, re.I)), None)
    if start is None:
        return lines
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return lines[start + 1:end]


def cmd_merge_tests(ws: Path, task: str) -> dict:
    rdir = reports_dir(ws, task)
    files = sorted(p for p in rdir.glob("test-*.md") if p.name != "test-summary.md")
    if not files:
        raise ValueError(f"no test-*.md reports in {rdir}")
    bugs: dict = {}
    for f in files:
        for line in bug_section(f.read_text(encoding="utf-8", errors="replace")):
            m = BUG_LINE.match(line)
            if not m:
                continue
            title = m.group(2).split("|")[0].strip()
            key = norm_title(title)
            if not key or key.replace("_", " ") in RETEST or key in RETEST:
                continue
            b = bugs.setdefault(key, {"title": SEVERITY.sub("", title), "severity": "", "sources": []})
            sev = SEVERITY.match(title) or SEV_CELL.search("|".join(m.group(2).split("|")[1:]))
            if sev and not b["severity"]:
                b["severity"] = sev.group(1).upper()
            src = f"{f.name} {m.group(1)}"
            if src not in b["sources"]:
                b["sources"].append(src)
    L = [f"# Test summary — {task}", "",
         f"Merged {now()} from {len(files)} lens report(s): {', '.join(p.name for p in files)}. "
         f"{len(bugs)} distinct bug(s) after de-duplication by normalized title.", ""]
    if bugs:
        L += ["| # | Bug | Severity | Found by | Raised |", "|---|---|---|---|---|"]
        for i, b in enumerate(bugs.values(), 1):
            L.append(f"| S-{i:02d} | {b['title']} | {b['severity'] or '—'} | {'; '.join(b['sources'])} | "
                     f"×{len(b['sources'])} |")
    else:
        L.append("No BUG lines found.")
    L.append("")
    (rdir / "test-summary.md").write_text("\n".join(L), encoding="utf-8")
    return {"ok": True, "reports": len(files), "bugs": len(bugs), "path": str(rdir / "test-summary.md")}


# ----------------------------------------------------------------------------------------------------------
# V21 consensus: tally -> suggest-mode -> decision -> answer, plus the prompt inbox (20.1)
# ----------------------------------------------------------------------------------------------------------

CONSENSUS_DEFAULTS = {"stages": ["plan", "review", "rootcause", "verdict"], "size": 3, "from_mode": "standard",
                      "models": [], "safety_veto": True, "provenance": "warn"}
AUTOMATION_DEFAULTS = {"auto_discovery": True, "self_retry": 2}
STAGES = ("plan", "review", "rootcause", "verdict")
VOTES = ("agree", "disagree", "abstain")
SEVERITIES = ("BLOCKER", "SHOULD-FIX", "NIT")          # most severe first
SIGNALS = ("live_cluster", "secrets", "production", "migration", "destructive", "multi_service")
INBOX_STATES = ("new", "taken", "done")


def guard_mode(ws: Path) -> str:
    """The mode as the guard reads it (guard load_mode): missing -> standard, malformed/unknown -> controlled."""
    f = ws / ".cecilia" / "mode.json"
    if not f.is_file():
        return "standard"
    try:
        m = json.loads(f.read_text(encoding="utf-8-sig")).get("mode", "standard")
    except Exception:
        return "controlled"
    m = str(m).lower()
    return m if m in MODES else "controlled"


def consensus_config(cfg: dict) -> dict:
    got = cfg.get("consensus") if isinstance(cfg.get("consensus"), dict) else {}
    out = dict(CONSENSUS_DEFAULTS)
    out.update({k: v for k, v in got.items() if k in CONSENSUS_DEFAULTS})
    if not isinstance(out["models"], list):
        out["models"] = []
    out["provenance"] = "require" if str(out.get("provenance")).strip().lower() == "require" else "warn"
    return out


def automation_config(cfg: dict) -> dict:
    got = cfg.get("automation") if isinstance(cfg.get("automation"), dict) else {}
    out = dict(AUTOMATION_DEFAULTS)
    out.update({k: v for k, v in got.items() if k in AUTOMATION_DEFAULTS})
    return out


def veto_active(cons: dict, mode: str) -> bool:
    """consensus.safety_veto: true = on in CONTROLLED, "always" = every mode, false = never."""
    v = cons.get("safety_veto", True)
    if isinstance(v, str):
        if v.strip().lower() == "always":
            return True
        v = v.strip().lower() in ("true", "on", "yes", "1")
    return bool(v) and mode == "controlled"


def _str(x) -> str:
    return x.strip() if isinstance(x, str) else ""


def _null(x):
    s = _str(x)
    return None if not s or s.lower() in ("null", "none", "-") else s


# --- tally ---------------------------------------------------------------------------------------------------

def read_ballots(vdir: Path, stage: str):
    """-> (ballots, invalid, discarded). A ballot keeps only items with a known vote and non-empty evidence."""
    ballots, invalid, discarded, seen = [], [], [], set()
    for f in sorted(vdir.glob("*.json")) if vdir.is_dir() else []:
        try:
            b = json.loads(f.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as e:
            invalid.append({"file": f.name, "reason": f"not valid JSON: {e}"})
            continue
        if not isinstance(b, dict):
            invalid.append({"file": f.name, "reason": "a ballot must be an object"})
            continue
        voter = _str(b.get("voter"))
        if not voter:
            invalid.append({"file": f.name, "reason": "missing `voter`"})
            continue
        if _str(b.get("stage")) != stage:
            invalid.append({"file": f.name, "reason": f"stage {b.get('stage')!r} is not {stage!r}"})
            continue
        if not isinstance(b.get("items"), list):
            invalid.append({"file": f.name, "reason": "`items` must be a list"})
            continue
        if voter in seen:
            invalid.append({"file": f.name, "reason": f"voter {voter} already has a ballot"})
            continue
        seen.add(voter)
        items, ids = [], set()
        for n, it in enumerate(b["items"], 1):
            iid = _str(it.get("id")) if isinstance(it, dict) else ""
            why = None
            if not iid:
                why = f"item #{n} has no id"
            elif iid in ids:
                why = "item listed twice (first kept)"
            elif _str(it.get("vote")).lower() not in VOTES:
                why = f"vote {it.get('vote')!r} is not agree/disagree/abstain"
            elif not _str(it.get("evidence")):
                why = "no evidence (path, command or file:line)"
            else:
                sev = _null(it.get("severity"))
                if sev is not None and sev.upper() not in SEVERITIES:
                    why = f"severity {sev!r} is not BLOCKER/SHOULD-FIX/NIT/null"
            if why:
                discarded.append({"voter": voter, "item": iid or f"#{n}", "reason": why})
                continue
            ids.add(iid)
            sev = _null(it.get("severity"))
            items.append({"id": iid, "vote": _str(it.get("vote")).lower(),
                          "severity": sev.upper() if sev else None, "safety": _null(it.get("safety")),
                          "evidence": _str(it.get("evidence")), "reason": _str(it.get("reason"))})
        ballots.append({"voter": voter, "model": _str(b.get("model")) or "(host default)", "items": items,
                        "file": f.name})
    return ballots, invalid, discarded


# --- provenance (20.2): who really wrote each ballot ----------------------------------------------------------

VOTER_ROLES = {"plan": ("cecilia-plan",), "review": ("cecilia-review",), "verdict": ("cecilia-review",),
               "rootcause": ("cecilia-review", "cecilia-discovery", "cecilia-devops")}
ORCHESTRATOR = "cecilia-orchestrator"
WHOLE_BALLOT = "(whole ballot)"


def _prov_key(ws: Path, p) -> str:
    """Workspace-relative, forward slashes, lower case (Windows paths differ in case and separators)."""
    s = str(p or "").strip().replace("\\", "/")
    root = str(ws).replace("\\", "/").rstrip("/")
    if root and s.lower().startswith(root.lower() + "/"):
        s = s[len(root) + 1:]
    while s.startswith("./"):
        s = s[2:]
    return s.lstrip("/").lower()


def read_provenance(ws: Path):
    """-> (last line per path key, log present). Unparseable lines are skipped: the log is best effort."""
    f = ws / ".cecilia" / "provenance.jsonl"
    last: dict = {}
    if not f.is_file():
        return last, False
    try:
        text = f.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return last, False
    for line in text.splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict) and _str(rec.get("path")):
            last[_prov_key(ws, rec["path"])] = rec
    return last, True


def _role(agent) -> str:
    s = _str(agent).lower()
    return s if not s or s.startswith("cecilia-") else f"cecilia-{s}"


def apply_provenance(ws: Path, vdir: Path, stage: str, ballots: list, require: bool):
    """Mark each ballot verified/unverified from its LAST provenance line; drop orchestrator-written ballots (and,
    with consensus.provenance "require", every unverified one). -> (kept, discarded, unverified, summary)."""
    log, present = read_provenance(ws)
    roles = VOTER_ROLES.get(stage, ())
    kept, discarded, unverified, claimed = [], [], [], {}
    for b in ballots:
        rec = log.get(_prov_key(ws, (vdir / b["file"]).relative_to(ws).as_posix()))
        agent = _role(rec.get("agent")) if rec else ""
        actor = _str(rec.get("actor")) if rec else ""
        host = _str(rec.get("host")).lower() if rec else ""
        why, drop = None, False
        if rec is None:
            why = "no provenance line" + ("" if present else " (.cecilia/provenance.jsonl is missing)")
        elif agent == ORCHESTRATOR or (not agent and host == "antigravity"):
            why, drop = "written by the orchestrator", True
        elif agent not in roles:
            why = f"last written by {agent or '(no role)'}, not a {stage} voter ({'/'.join(roles)})"
        elif not actor:
            why = "no actor recorded"
        elif actor in claimed:
            why = f"same actor as {claimed[actor]}"
        b["actor"] = actor or None
        if why is None:
            b["provenance"] = "verified"
            if b["items"]:
                claimed[actor] = b["voter"]
            kept.append(b)
            continue
        if drop or require:
            discarded.append({"voter": b["voter"], "item": WHOLE_BALLOT, "file": b["file"],
                              "reason": why if drop else f"{why} (consensus.provenance require)"})
            continue
        b["provenance"], b["provenance_note"] = "unverified", why
        kept.append(b)
        if b["items"]:
            unverified.append({"voter": b["voter"], "file": b["file"], "reason": why})
    counted = [b for b in kept if b["items"]]
    summary = {"verified": sum(1 for b in counted if b["provenance"] == "verified"),
               "unverified": sum(1 for b in counted if b["provenance"] != "verified"),
               "discarded": len(discarded),
               "actors": len({b["actor"] for b in counted if b["actor"]}),
               "mode": "require" if require else "warn", "log": present}
    return kept, discarded, unverified, summary


def tally(ballots: list, stage: str, veto_on: bool) -> dict:
    valid = [b for b in ballots if b["items"]]
    n = len(valid)
    order: list = []
    per: dict = {}
    for b in valid:
        for it in b["items"]:
            if it["id"] not in per:
                order.append(it["id"])
                per[it["id"]] = []
            per[it["id"]].append((b, it))
    items, vetoes = [], []
    for iid in order:
        votes = per[iid]
        agree = [(b, it) for b, it in votes if it["vote"] == "agree"]
        disagree = [(b, it) for b, it in votes if it["vote"] == "disagree"]
        abstain = len(votes) - len(agree) - len(disagree)
        result = "adopted" if len(agree) > n / 2 else "rejected" if len(disagree) > n / 2 else "open"
        row = {"id": iid, "agree": len(agree), "disagree": len(disagree), "abstain": abstain,
               "silent": n - len(votes), "result": result,
               "voters": {"agree": [b["voter"] for b, _ in agree], "disagree": [b["voter"] for b, _ in disagree]},
               "reasons": [f"{b['voter']} ({it['vote']}): {it['reason'] or '-'} [{it['evidence']}]"
                           for b, it in votes],
               "safety": sorted({it["safety"] for _, it in votes if it["safety"]})}
        if stage == "review":
            counts: dict = {}
            for _, it in agree:
                if it["severity"]:
                    counts[it["severity"]] = counts.get(it["severity"], 0) + 1
            row["severity"] = (min(counts, key=lambda s: (-counts[s], SEVERITIES.index(s))) if counts else None)
        if veto_on:
            flagged = votes if stage == "review" else agree     # review: any voter flagging the finding
            for b, it in flagged:
                if it["safety"]:
                    vetoes.append({"stage": stage, "item": iid, "safety": it["safety"],
                                   "reason": it["reason"] or it["evidence"], "voter": b["voter"],
                                   "result": result})
        row["veto"] = any(v["item"] == iid for v in vetoes)
        items.append(row)
    models = sorted({b["model"] for b in valid})
    voters = []
    for b in valid:
        v = {"voter": b["voter"], "model": b["model"], "items": len(b["items"])}
        if "provenance" in b:
            v["provenance"] = b["provenance"]
            if b.get("provenance_note"):
                v["provenance_note"] = b["provenance_note"]
        voters.append(v)
    # verified: every valid ballot was written by a voter role with its own actor (so >= 2 distinct actors)
    verified = n >= 2 and all(b.get("provenance") == "verified" for b in valid)
    independence = ("verified" if verified and len(models) >= 2 else "strong" if len(models) >= 2 else "weak")
    return {"valid_voters": n, "voters": voters,
            "items": items, "vetoes": vetoes, "models": models,
            "independence": independence,
            "summary": {k: sum(1 for i in items if i["result"] == k) for k in ("adopted", "rejected", "open")}}


def provenance_warning(pv: dict, stage: str = "") -> str:
    return (f"WARNING: independence not verified{' (' + stage + ')' if stage else ''} - "
            f"{pv.get('unverified', 0)} ballot(s) without a verified voter writer, {pv.get('discarded', 0)} discarded"
            " (written by the orchestrator or without provenance). Weigh the votes accordingly.")


def tally_md(res: dict) -> str:
    L = [f"# Tally - {res['task']} / {res['stage']}", "",
         f"Created {res['created']} - mode {res['mode'].upper()} - safety veto {'ON' if res['safety_veto'] else 'off'}"
         f" - independence {res['independence']} (models: {', '.join(res['models']) or '-'})", "",
         f"Valid voters: {res['valid_voters']} ({', '.join(v['voter'] for v in res['voters']) or '-'}). "
         f"Majority = more than half of the valid voters.", ""]
    L += ["| Item | Agree | Disagree | Abstain/silent | Result | " + ("Severity | " if res["stage"] == "review" else "")
          + "Safety |", "|---|---|---|---|---|" + ("---|" if res["stage"] == "review" else "") + "---|"]
    for i in res["items"]:
        L.append(f"| {i['id']} | {i['agree']} | {i['disagree']} | {i['abstain'] + i['silent']} | "
                 f"{i['result']}{' (VETO)' if i['veto'] else ''} | "
                 + (f"{i.get('severity') or '-'} | " if res["stage"] == "review" else "")
                 + f"{', '.join(i['safety']) or '-'} |")
    if res["vetoes"]:
        L += ["", "## Safety vetoes (never outvoted)", ""]
        L += [f"- {v['item']}: {v['safety']} - {v['reason']} ({v['voter']})" for v in res["vetoes"]]
    if res["independence"] == "weak":
        L += ["", "Independence is weak: every valid voter ran on the same model."]
    pv = res.get("provenance")
    if pv:
        L += ["", f"Provenance: {pv['verified']} verified, {pv['unverified']} unverified, {pv['discarded']} discarded"
                  f" ballot(s), {pv['actors']} distinct actor(s) (consensus.provenance {pv.get('mode', 'warn')})."]
        if pv["unverified"] or pv["discarded"]:
            L.append(provenance_warning(pv))
        L += [f"- {x['voter']} unverified: {x['reason']}" for x in res.get("unverified") or []]
    if res["invalid"] or res["discarded"]:
        L += ["", "## Ignored", ""]
        L += [f"- ballot {x['file']}: {x['reason']}" for x in res["invalid"]]
        L += [f"- ballot {x['file']} ({x['voter']}): {x['reason']}" if x.get("item") == WHOLE_BALLOT
              else f"- {x['voter']} item {x['item']}: {x['reason']}" for x in res["discarded"]]
    L.append("")
    return "\n".join(L)


def cmd_tally(ws: Path, task: str, stage: str) -> dict:
    if stage not in STAGES:
        raise ValueError(f"stage {stage!r} must be one of {', '.join(STAGES)}")
    cfg = load_config(ws)
    cons, mode = consensus_config(cfg), guard_mode(ws)
    d = task_dir(ws, task)
    vdir = d / "votes" / stage
    ballots, invalid, discarded = read_ballots(vdir, stage)
    ballots, dropped, unverified, prov = apply_provenance(ws, vdir, stage, ballots, cons["provenance"] == "require")
    discarded = dropped + discarded
    veto_on = veto_active(cons, mode)
    t = tally(ballots, stage, veto_on)
    ignored = [f"{x['file']}: {x['reason']}" for x in invalid] + \
              [f"{x['voter']}/{x['item']}: {x['reason']}" for x in discarded]
    if t["valid_voters"] < 2:
        raise ValueError(f"{t['valid_voters']} valid voter(s) in {vdir} - a tally needs at least 2"
                         + ("; ignored: " + "; ".join(ignored) if ignored else ""))
    res = {"task": task, "stage": stage, "created": now(), "mode": mode, "safety_veto": veto_on,
           "valid_voters": t["valid_voters"], "voters": t["voters"], "models": t["models"],
           "independence": t["independence"], "summary": t["summary"], "items": t["items"],
           "vetoes": t["vetoes"], "invalid": invalid, "discarded": discarded,
           "provenance": prov, "unverified": unverified}
    if stage not in [str(s) for s in cons.get("stages") or []]:
        res["warning"] = f"stage {stage} is not in consensus.stages of .cecilia/config.json"
    write_json(d / "votes" / f"{stage}-result.json", res)
    (d / "votes" / f"{stage}-result.md").write_text(tally_md(res), encoding="utf-8")
    return res


# --- suggest-mode --------------------------------------------------------------------------------------------

def suggest_mode(scope, current: str) -> dict:
    sig = (scope or {}).get("signals") if isinstance((scope or {}).get("signals"), dict) else {}
    hits = [s for s in SIGNALS if sig.get(s) is True]
    if hits:
        sug, why = "controlled", "scope signals: " + ", ".join(hits)
    elif scope and (str(scope.get("size", "")).lower() == "tiny" or scope.get("tiny") is True):
        sug, why = "fast", "scope says the change is tiny and no risk signal is set"
    elif scope:
        sug, why = "standard", "no risk signal in scope.json"
    else:
        sug, why = current, "no scope.json yet - keeping the current mode"
    return {"current": current, "suggested": sug, "why": why, "signals": hits,
            "command": f"cecilia mode {sug}" if MODES[sug] > MODES.get(current, 1) else None}


def cmd_suggest_mode(ws: Path, task: str) -> dict:
    load_config(ws)
    scope = read_json(task_dir(ws, task) / "scope.json", "scope.json (discovery writes it)")
    if not isinstance(scope, dict):
        raise ValueError("scope.json must be an object")
    return suggest_mode(scope, guard_mode(ws))


# --- decision card -------------------------------------------------------------------------------------------

def _lines(x) -> list:
    if isinstance(x, list):
        return [str(i) for i in x if str(i).strip()]
    return [str(x)] if isinstance(x, str) and x.strip() else []


def build_card(ws: Path, task: str) -> tuple:
    cfg = load_config(ws)
    cons, mode = consensus_config(cfg), guard_mode(ws)
    d = task_dir(ws, task)
    warns = []
    scope = None
    if (d / "scope.json").is_file():
        scope = read_json(d / "scope.json", "scope.json")
        if not isinstance(scope, dict):
            raise ValueError("scope.json must be an object")
    else:
        warns.append("no scope.json: discovery has not written the scope - goal / not doing / done when are empty")
    opts = read_json(d / "options.json", "options.json (run `workflow.py options` first)")
    if not isinstance(opts, dict) or not isinstance(opts.get("options"), list) or not opts["options"]:
        raise ValueError("options.json has no options")
    tallies = {}
    vdir = d / "votes"
    for st in STAGES:
        p = vdir / f"{st}-result.json"
        if p.is_file():
            tallies[st] = read_json(p, p.name)
    if "plan" not in tallies:
        warns.append("no plan tally (votes/plan-result.json): options carry no votes and no open questions")
    plan = tallies.get("plan") or {}
    plan_items = {i.get("id"): i for i in plan.get("items", []) if isinstance(i, dict)}
    nvoters = int(plan.get("valid_voters") or 0)
    # options
    ids = [str(o.get("id")) for o in opts["options"]]
    rec_id = next((str(o.get("id")) for o in opts["options"] if o.get("recommended") is True), None)
    if rec_id is None and isinstance(opts.get("recommended"), str):
        rec_id = opts["recommended"]
    if rec_id not in ids:
        rec_id = ids[0]
    options = []
    for o in opts["options"]:
        oid = str(o.get("id"))
        it = plan_items.get(oid)
        options.append({"id": oid, "title": str(o.get("title") or oid),
                        "summary": str(o.get("summary") or o.get("tradeoff") or ""),
                        "risk": str(o.get("risk") or o.get("tradeoff") or ""),
                        "rollback": str(o.get("rollback") or ""),
                        "votes": f"{it.get('agree', 0)}/{nvoters}" if it else "-",
                        "recommended": oid == rec_id})
    # models
    models = []
    for k, m in enumerate(cons["models"], 1):
        models.append({"role": f"voter {k}", "model": str(m), "why": "consensus.models in .cecilia/config.json"})
    if not models:
        seen = set()
        for t in tallies.values():
            for v in t.get("voters", []):
                if v.get("voter") not in seen:
                    seen.add(v.get("voter"))
                    models.append({"role": f"voter {v.get('voter')}", "model": str(v.get("model")),
                                   "why": "ballot (consensus.models is empty: host default)"})
    rec = next(o for o in opts["options"] if str(o.get("id")) == rec_id)
    for u in rec.get("units") or []:
        if isinstance(u, dict):
            models.append({"role": f"{u.get('role')} {u.get('id')}", "model": str(u.get("model") or "inherit"),
                           "why": f"options.json option {rec_id}"})
    rv = rec.get("review") if isinstance(rec.get("review"), dict) else {}
    if rv.get("lenses"):
        models.append({"role": "cecilia-review panel", "model": str(rv.get("model") or "inherit"),
                       "why": f"options.json option {rec_id} (judge {rv.get('judge_model') or '-'})"})
    # independence
    rank = {"weak": 0, "strong": 1, "verified": 2}
    provenance = {st: t["provenance"] for st, t in tallies.items() if isinstance(t.get("provenance"), dict)}
    warns += [provenance_warning(pv, st) for st, pv in provenance.items() if pv.get("unverified") or pv.get("discarded")]
    if tallies:
        independence = min((str(t.get("independence")) for t in tallies.values()), key=lambda x: rank.get(x, 0))
        independence = independence if independence in rank else "weak"
    else:
        independence = "strong" if len({str(m) for m in cons["models"]}) >= 2 else "weak"
    # questions: open plan items (not option ids), then vetoes
    questions = []
    for iid, it in plan_items.items():
        if iid in ids or it.get("result") != "open":
            continue
        a, dis = int(it.get("agree", 0)), int(it.get("disagree", 0))
        default = "agree" if a > dis else "disagree"
        why = (f"{a} agree / {dis} disagree of {nvoters} voters; "
               + ("default follows the larger side" if a != dis else "tie: the safer choice is not to do the step"))
        reasons = "; ".join(it.get("reasons") or [])
        questions.append({"id": f"Q{len(questions) + 1}", "item": iid,
                          "text": f"Plan item {iid} has no majority. Keep it? ({reasons or 'no reasons given'})",
                          "choices": [{"id": "agree", "text": "Keep the step"},
                                      {"id": "disagree", "text": "Drop the step"}],
                          "default": default, "why": why})
    vetoes, seen_v = [], set()
    for st, t in tallies.items():
        for v in t.get("vetoes", []):
            vetoes.append({k: v.get(k) for k in ("stage", "item", "safety", "reason", "voter")})
            key = (v.get("stage"), v.get("item"))
            if key in seen_v:
                continue
            seen_v.add(key)
            questions.append({"id": f"V{len(seen_v)}", "item": v.get("item"), "stage": v.get("stage"),
                              "text": f"Safety veto ({v.get('safety')}) on {v.get('stage')} item {v.get('item')}: "
                                      f"{v.get('reason')}",
                              "choices": [{"id": "safeguard", "text": "Proceed with the safeguard"},
                                          {"id": "drop", "text": "Drop this step"}],
                              "default": "safeguard",
                              "why": "a safety flag is never outvoted; the step runs only with the safeguard"})
    sc = scope or {}
    card = {"task": task, "status": "open", "created": now(),
            "scope": {"goal": str(sc.get("goal") or ""), "out_of_scope": _lines(sc.get("out_of_scope")),
                      "done_when": _lines(sc.get("done_when"))},
            "mode": suggest_mode(scope, mode), "models": models, "options": options, "questions": questions,
            "vetoes": vetoes, "independence": independence, "provenance": provenance, "answer": None}
    card["mode"].pop("signals", None)
    return card, warns


def card_md(card: dict) -> str:
    sc, m = card["scope"], card["mode"]
    L = [f"# Decision - {card['task']}", "", f"Status: {card['status']} - created {card['created']}", "",
         "## Scope", "", f"Goal: {sc['goal'] or '(not written yet)'}", "", "Not doing:"]
    L += [f"- {x}" for x in sc["out_of_scope"]] or ["- (nothing listed)"]
    L += ["", "Done when:"] + ([f"- {x}" for x in sc["done_when"]] or ["- (nothing listed)"])
    L += ["", "## Mode", "", f"Current {m['current'].upper()}, suggested {m['suggested'].upper()} ({m['why']})."]
    if m.get("command"):
        L.append(f"To switch, run in your own terminal: `{m['command']}`")
    L += ["", "## Options", "", "| Id | Option | Votes | Risk | Rollback | |", "|---|---|---|---|---|---|"]
    for o in card["options"]:
        L.append(f"| **{o['id']}** | {o['title']}{' - ' + o['summary'] if o['summary'] else ''} | {o['votes']} | "
                 f"{o['risk'] or '-'} | {o['rollback'] or '-'} | {'recommended' if o['recommended'] else ''} |")
    if card["models"]:
        L += ["", "## Models", ""] + [f"- {x['role']}: {x['model']} ({x['why']})" for x in card["models"]]
    L += ["", "## Questions", ""]
    if card["questions"]:
        for q in card["questions"]:
            ch = " / ".join(f"`{c['id']}` {c['text']}" for c in q["choices"])
            L.append(f"- **{q['id']}** {q['text']}  ")
            L.append(f"  Choices: {ch}. Default: `{q['default']}` ({q['why']}).")
    else:
        L.append("- none: every plan item has a majority")
    L += ["", "## Safety vetoes", ""]
    L += [f"- {v['stage']} {v['item']}: {v['safety']} - {v['reason']} ({v['voter']})" for v in card["vetoes"]] \
        or ["- none"]
    L += ["", f"Independence: {card['independence']}"
          + (" - the voters shared one model; weigh the votes accordingly." if card["independence"] == "weak" else
             " - every ballot was written by its own voter agent." if card["independence"] == "verified" else "")]
    for st, pv in (card.get("provenance") or {}).items():
        L.append(f"- {st}: {pv.get('verified', 0)} verified, {pv.get('unverified', 0)} unverified, "
                 f"{pv.get('discarded', 0)} discarded ballot(s), {pv.get('actors', 0)} distinct actor(s)")
    for st, pv in (card.get("provenance") or {}).items():
        if pv.get("unverified") or pv.get("discarded"):
            L += ["", provenance_warning(pv, st)
                  + f" See tensura/tasks/{card['task']}/votes/{st}-result.md."]
    L.append("")
    if card.get("answer"):
        a = card["answer"]
        L += ["## Answer", "", f"Option {a['option']} by {a['by']} at {a['at']}; answers: "
              + (", ".join(f"{k}={v}" for k, v in a["answers"].items()) or "none"), ""]
    else:
        L += ["Reply with the option id (e.g. A) and any answers that differ from the defaults.", ""]
    return "\n".join(L)


def decisions_dir(ws: Path) -> Path:
    return ws / "tensura" / "decisions"


def cmd_decision(ws: Path, task: str) -> dict:
    card, warns = build_card(ws, task)
    p = decisions_dir(ws) / f"{task}.json"
    if p.is_file():
        old = read_json(p, "decision card")
        if isinstance(old, dict) and old.get("status") == "answered":
            raise ValueError(f"the decision card for {task} is already answered ({(old.get('answer') or {}).get('option')})"
                             " - a new plan needs new options and a new task card")
    write_json(p, card)
    (p.with_suffix(".md")).write_text(card_md(card), encoding="utf-8")
    return {"ok": True, "path": str(p), "md": str(p.with_suffix(".md")), "warnings": warns, "card": card}


def cmd_answer(ws: Path, task: str, option: str, answers_raw, by, replace: bool) -> dict:
    task_dir(ws, task)
    p = decisions_dir(ws) / f"{task}.json"
    if not p.is_file():
        raise ValueError(f"no decision card for {task}: run `workflow.py decision --task {task}` first")
    card = read_json(p, "decision card")
    if card.get("status") == "answered":
        raise ValueError(f"the decision card for {task} is already answered")
    ids = [str(o.get("id")) for o in card.get("options", [])]
    if option not in ids:
        raise ValueError(f"unknown option {option!r}; the card offers {', '.join(ids)}")
    given = {}
    if answers_raw:
        try:
            given = json.loads(answers_raw)
        except ValueError as e:
            raise ValueError(f"--answers is not valid JSON: {e}")
        if not isinstance(given, dict):
            raise ValueError('--answers must be an object, e.g. {"Q1": "disagree"}')
    qs = {q["id"]: q for q in card.get("questions", [])}
    for k, v in given.items():
        if k not in qs:
            raise ValueError(f"unknown question {k!r}; the card asks {', '.join(qs) or 'nothing'}")
        if v not in [c["id"] for c in qs[k]["choices"]]:
            raise ValueError(f"{k}: choice {v!r} is not one of {', '.join(c['id'] for c in qs[k]['choices'])}")
    answers = {k: given.get(k, q["default"]) for k, q in qs.items()}
    chosen = cmd_choose(ws, task, option, replace)      # raises -> the card stays open
    card["status"] = "answered"
    card["answer"] = {"option": option, "answers": answers, "by": by or "Cecilia", "at": now()}
    write_json(p, card)
    p.with_suffix(".md").write_text(card_md(card), encoding="utf-8")
    return {"ok": True, "task": task, "option": option, "answers": answers, "hash": chosen["hash"],
            "workflow": chosen["path"], "path": str(p)}


# --- inbox ------------------------------------------------------------------------------------------------------

def inbox_dir(ws: Path) -> Path:
    return ws / "tensura" / "inbox"


def _inbox_file(ws: Path, iid: str) -> Path:
    if not ID_RE.match(iid or ""):
        raise ValueError(f"inbox id {iid!r} is not valid")
    p = inbox_dir(ws) / f"{iid}.json"
    if not p.is_file():
        raise ValueError(f"no inbox item {iid}")
    return p


def cmd_inbox(ws: Path, a):
    if a.action == "add":
        prompt = (a.prompt or "").strip()
        if not prompt:
            raise ValueError("--prompt is empty")
        import secrets
        stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
        d = inbox_dir(ws)
        while True:
            iid = f"IN-{stamp}-{secrets.token_hex(2)}"
            if not (d / f"{iid}.json").exists():
                break
        item = {"id": iid, "prompt": prompt, "source": a.source or "cli", "created": now(), "status": "new",
                "task": None}
        write_json(d / f"{iid}.json", item)
        return item
    if a.action == "list":
        if a.status and a.status not in INBOX_STATES:
            raise ValueError(f"--status must be one of {', '.join(INBOX_STATES)}")
        items = []
        for f in sorted(inbox_dir(ws).glob("*.json")) if inbox_dir(ws).is_dir() else []:
            try:
                it = json.loads(f.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                print(f"warning: {f.name} is not valid JSON", file=sys.stderr)
                continue
            if isinstance(it, dict) and (not a.status or it.get("status") == a.status):
                items.append(it)
        items.sort(key=lambda x: (str(x.get("created") or ""), str(x.get("id") or "")), reverse=True)
        return items
    p = _inbox_file(ws, a.id)
    item = read_json(p, "inbox item")
    if a.action == "take":
        task_dir(ws, a.task)
        if item.get("status") != "new":
            raise ValueError(f"{a.id} is {item.get('status')} (task {item.get('task')}), not new")
        item.update({"status": "taken", "task": a.task, "taken": now()})
    else:
        if item.get("status") == "done":
            raise ValueError(f"{a.id} is already done")
        item.update({"status": "done", "done": now()})
    write_json(p, item)
    return item


def _utf8_console() -> None:
    """Windows consoles default to a legacy code page; keep output readable and crash-free."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


V20_COMMANDS = ("options", "choose", "brief", "round", "agent", "merge-tests")


def _v20_parsers(sub) -> None:
    def add(name, help_):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--workspace", default=None, help="workspace root (default: nearest .cecilia/config.json)")
        p.add_argument("--task", required=True)
        return p
    p = add("options", "validate 2-3 options, add [projected] estimates, write options.json/.md")
    p.add_argument("--input", required=True, help="JSON: {mode?, flow?, options: [...]} (assets/options-template.md)")
    p = add("choose", "freeze Cecilia's choice into workflow.json (+hash)")
    p.add_argument("--option", required=True)
    p.add_argument("--replace", action="store_true", help="Cecilia changed her choice")
    p = add("brief", "print a brief: header line, filled template, ## Rules (must follow)")
    p.add_argument("--role", required=True)
    p.add_argument("--lens", default=None)
    p.add_argument("--unit", default=None)
    p.add_argument("--round", type=int, default=None, help="default: run.json round")
    p.add_argument("--short", action="store_true", help="FAST: 3-line brief (header and rules still included)")
    p.add_argument("--out", action="store_true", help="also write tensura/tasks/<TASK>/briefs/<name>.md")
    p = add("round", "start the next fix round (exit 3 past fix_loop.max_rounds)")
    p.add_argument("--show", action="store_true")
    p = add("agent", "record an agent launch / return in run.json")
    p.add_argument("action", choices=("start", "done"))
    p.add_argument("--id", required=True)
    p.add_argument("--role", default=None)
    p.add_argument("--lens", default=None)
    p.add_argument("--unit", default=None)
    p.add_argument("--state", default="done")
    p.add_argument("--sha", default=None)
    p.add_argument("--tokens", type=int, default=None)
    add("merge-tests", "merge BUG lines of test-*.md into test-summary.md")
    # v21 consensus + inbox
    p = add("tally", "count the ballots of votes/<stage>/ -> votes/<stage>-result.json/.md")
    p.add_argument("--stage", required=True, choices=STAGES)
    add("suggest-mode", "suggest a work mode from scope.json signals")
    add("decision", "assemble the ONE decision card -> tensura/decisions/<TASK>.json/.md")
    p = add("answer", "record the human's answer in the card, then choose that option")
    p.add_argument("--option", required=True)
    p.add_argument("--answers", default=None, help='JSON object of question id -> choice id, e.g. {"Q1":"disagree"}')
    p.add_argument("--by", default=None, help="who answered (default Cecilia)")
    p.add_argument("--replace", action="store_true", help="replace an existing workflow.json")
    ib = sub.add_parser("inbox", help="queued prompts in tensura/inbox/")
    ib.add_argument("--workspace", default=None, help="workspace root (default: nearest .cecilia/config.json)")
    isub = ib.add_subparsers(dest="action", required=True)

    def iadd(name, help_):
        q = isub.add_parser(name, help=help_)
        q.add_argument("--workspace", default=argparse.SUPPRESS, help="workspace root")
        return q
    q = iadd("add", "queue a prompt")
    q.add_argument("--prompt", required=True)
    q.add_argument("--source", default="cli")
    q = iadd("list", "print queued prompts as a JSON array, newest first")
    q.add_argument("--status", default=None, choices=INBOX_STATES)
    q = iadd("take", "mark a prompt taken by a task")
    q.add_argument("id")
    q.add_argument("--task", required=True)
    q = iadd("done", "mark a prompt done")
    q.add_argument("id")


V21_COMMANDS = ("tally", "suggest-mode", "decision", "answer", "inbox")


def run_v21(a) -> int:
    ws = find_workspace(a.workspace)
    if a.cmd == "tally":
        res = cmd_tally(ws, a.task, a.stage)
        if res.get("warning"):
            print(f"warning: {res['warning']}", file=sys.stderr)
    elif a.cmd == "suggest-mode":
        res = cmd_suggest_mode(ws, a.task)
    elif a.cmd == "decision":
        res = cmd_decision(ws, a.task)
        for w in res["warnings"]:
            print(f"warning: {w}", file=sys.stderr)
    elif a.cmd == "answer":
        res = cmd_answer(ws, a.task, a.option, a.answers, a.by, a.replace)
    else:
        res = cmd_inbox(ws, a)
    print(json.dumps(res, ensure_ascii=False, indent=2 if a.cmd in ("tally", "inbox") else None))
    return 0


def run_v20(a) -> int:
    ws = find_workspace(a.workspace)
    if a.cmd == "options":
        res = cmd_options(ws, a.task, a.input)
        for w in res["warnings"]:
            print(f"warning: {w}", file=sys.stderr)
    elif a.cmd == "choose":
        res = cmd_choose(ws, a.task, a.option, a.replace)
    elif a.cmd == "brief":
        sys.stdout.write(cmd_brief(ws, a))
        return 0
    elif a.cmd == "round":
        res = cmd_round(ws, a.task, a.show)
    elif a.cmd == "agent":
        res = cmd_agent(ws, a)
    else:
        res = cmd_merge_tests(ws, a.task)
    print(json.dumps(res, ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    _utf8_console()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db")
    sub = ap.add_subparsers(dest="cmd", required=True)
    spec = {"new": ["run", "project"], "show": ["run"], "set-subject": ["run", "subject"],
            "reconcile": ["run", "note"], "transition": ["run", "state", "note"],
            "wave-add": ["run", "wave", "json_file"], "wave-start": ["run", "wave"],
            "wave-done": ["run", "wave", "evidence"], "action-begin": ["run", "key", "intent"],
            "action-result": ["run", "key", "state", "receipt"], "plan-waves": ["json_file"]}
    for name, args in spec.items():
        p = sub.add_parser(name)
        for x in args:
            p.add_argument(x)
        if name == "plan-waves":
            p.add_argument("--max-writers", type=int, default=None)
            p.add_argument("--resources", action="store_true")
            p.add_argument("--task", default="TASK")
            p.add_argument("--db-name", default="app")
    _v20_parsers(sub)
    a = ap.parse_args(argv)
    try:
        if a.cmd in V20_COMMANDS:
            return run_v20(a)
        if a.cmd in V21_COMMANDS:
            return run_v21(a)
        if a.cmd == "plan-waves":
            waves = plan_waves(json.loads(Path(a.json_file).read_text(encoding="utf-8"))["tasks"], a.max_writers)
            if a.resources:
                print(json.dumps({"waves": waves, "resources": assign_resources(waves, a.task, a.db_name)}, indent=2))
            else:
                print(json.dumps(waves))
            return 0
        if not a.db:
            ap.error("--db is required for ledger commands")
        led = Ledger(a.db)
        try:
            if a.cmd == "show":
                print(json.dumps(led.show(a.run), indent=2, ensure_ascii=False))
                return 0
            {
                "new": lambda: led.new(a.run, a.project),
                "set-subject": lambda: led.set_subject(a.run, a.subject),
                "reconcile": lambda: led.reconcile(a.run, a.note),
                "transition": lambda: led.transition(a.run, a.state, a.note),
                "wave-add": lambda: led.wave_add(a.run, a.wave, json.loads(Path(a.json_file).read_text(encoding="utf-8-sig"))),
                "wave-start": lambda: led.wave_start(a.run, a.wave),
                "wave-done": lambda: led.wave_done(a.run, a.wave, a.evidence),
                "action-begin": lambda: led.action_begin(a.run, a.key, a.intent),
                "action-result": lambda: led.action_result(a.run, a.key, a.state, a.receipt),
            }[a.cmd]()
            print(json.dumps({"ok": True, "operation": a.cmd}))
            return 0
        finally:
            led.close()
    except RoundLimit as e:
        print(f"STOP: {e}", file=sys.stderr)
        return 3
    except (ValueError, KeyError, TypeError, OSError, sqlite3.Error) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
