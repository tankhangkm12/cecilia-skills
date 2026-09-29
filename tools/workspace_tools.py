#!/usr/bin/env python3
"""Workspace tools for Cecilia (v20): status, lessons, scorecard, clean, flow, rules, extension.

Called by the `cecilia` command:
    cecilia status [workspace]          open tasks (state.md + workflow.json + run.json), branch, worktrees, refusals
    cecilia lessons [--all DIR]         `[generic?]` lessons Cecilia may promote into the skills
    cecilia scorecard [workspace]       per role: reports, deviations, self-check results, guard refusals
    cecilia clean [--apply] [--days N]  finished worktrees, old backups — lists; --apply asks, then removes
    cecilia flow [personal|team]        show the flow, or switch it (human only: type the flow name)
    cecilia rules list|show [role]|lint the workspace rules/ folder (read-only)
    cecilia rules add --role R "text"   add a rule (also --project / --flow F / --lens L; human only)
    cecilia extension list|check DIR|apply DIR   proposals from cecilia-extend (apply: human only, then upgrade)

Everything that changes Cecilia's control files (flow, rules add, extension apply) needs an interactive
terminal; the guard also denies agents running those commands.

Python ≥ 3.9, standard library only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path


def git(project: Path, *args: str) -> str:
    try:
        r = subprocess.run(["git", "-C", str(project), *args], capture_output=True, text=True, timeout=30,
                           env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"))
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def field(text: str, *names: str) -> str:
    for n in names:
        m = re.search(rf"^\s*[-*]?\s*\**{re.escape(n)}\**\s*:\s*(.+)$", text, re.I | re.M)
        if m:
            return m.group(1).strip()
    return ""


def tasks(ws: Path) -> list[dict]:
    out = []
    for f in sorted((ws / "tensura" / "tasks").glob("*/state.md")):
        text = f.read_text(encoding="utf-8", errors="replace")
        out.append({"task": f.parent.name, "goal": field(text, "Goal"), "mode": field(text, "Mode"),
                    "branch": field(text, "Branch"), "next": field(text, "Next", "Next step"),
                    "pending": field(text, "Pending", "Pending decisions", "Waiting for Cecilia", "Decisions pending"),
                    "updated": dt.datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")})
    return out


def _json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def load_cfg(ws: Path) -> dict:
    cfg = _json(ws / ".cecilia" / "config.json")
    return cfg if isinstance(cfg, dict) else {}


def load_reg(ws: Path) -> dict:
    """The compiled registry the installer wrote (`.cecilia/registry.json`); {} when absent."""
    reg = _json(ws / ".cecilia" / "registry.json")
    return reg if isinstance(reg, dict) else {}


def task_run_lines(ws: Path, task: str, cfg: dict) -> list[str]:
    """v20: flow, chosen workflow option + hash, fix round and agents (state per agent) of one task."""
    d = ws / "tensura" / "tasks" / task
    wf, run = _json(d / "workflow.json"), _json(d / "run.json")
    out = []
    if isinstance(wf, dict):
        opt = wf.get("option") if isinstance(wf.get("option"), dict) else {}
        label = opt.get("name") or opt.get("title") or opt.get("id") or ""
        out.append(f"flow {wf.get('flow') or cfg.get('flow') or 'personal'} · workflow {wf.get('chosen') or '-'}"
                   + (f" ({str(label)[:40]})" if label and label != wf.get("chosen") else "")
                   + f" · hash {wf.get('hash') or '-'}")
    elif (d / "options.json").is_file():
        out.append("workflow options written — WAITING FOR YOU to choose one")
    if isinstance(run, dict):
        agents = [a for a in run.get("agents") or [] if isinstance(a, dict)]
        max_rounds = ((cfg.get("fix_loop") or {}) if isinstance(cfg.get("fix_loop"), dict) else {}).get("max_rounds", 3)
        states = Counter(str(a.get("state") or "?") for a in agents)
        out.append(f"fix round {run.get('round', 0)}/{max_rounds} · {len(agents)} agent(s)"
                   + (": " + ", ".join(f"{n} {s}" for s, n in sorted(states.items())) if agents else ""))
        for a in agents[:12]:
            role = str(a.get("role") or "?").replace("cecilia-", "")
            extra = "/".join(str(a[k]) for k in ("lens", "unit") if a.get(k) and a.get(k) != "-")
            out.append(f"  {str(a.get('id') or ''):<8} {role + (' ' + extra if extra else ''):<28} "
                       f"{str(a.get('state') or '?'):<9} {str(a.get('sha') or '')[:8]}")
        if len(agents) > 12:
            out.append(f"  … {len(agents) - 12} more in run.json")
    return out


def guard_events(ws: Path, limit: int | None = None) -> list[dict]:
    f = ws / ".cecilia" / "guard.log"
    if not f.is_file():
        return []
    rows = []
    for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows[-limit:] if limit else rows


def cmd_status(ws: Path, project: Path) -> int:
    print(f"Workspace {ws}\nProject   {project}")
    br = git(project, "rev-parse", "--abbrev-ref", "HEAD") or "?"
    dirty = len([x for x in git(project, "status", "--porcelain").splitlines() if x.strip()])
    print(f"Branch    {br}  ·  {dirty} uncommitted file(s)")
    wts = [l[9:] for l in git(project, "worktree", "list", "--porcelain").splitlines() if l.startswith("worktree ")]
    if len(wts) > 1:
        print("Worktrees " + " · ".join(Path(w).name for w in wts[1:]))
    cfg = load_cfg(ws)
    print(f"Flow      {cfg.get('flow') or 'personal'}")
    ts = tasks(ws)
    print(f"\nTasks ({len(ts)})")
    for t in ts:
        print(f"  {t['task']:<14} {t['mode'][:10]:<10} {t['updated']}  {t['goal'][:60]}")
        for line in task_run_lines(ws, t["task"], cfg):
            print(f"  {'':<14} {line}")
        if t["next"]:
            print(f"  {'':<14} next: {t['next'][:80]}")
        if t["pending"] and t["pending"].lower() not in {"none", "-", "không"}:
            print(f"  {'':<14} WAITING FOR YOU: {t['pending'][:80]}")
    ev = [e for e in guard_events(ws, 200) if e.get("decision") in {"deny", "ask"}][-5:]
    if ev:
        print("\nRecent guard refusals / questions")
        for e in ev:
            print(f"  {e.get('at', '')[:16]} {e.get('decision'):4} {str(e.get('payload'))[:60]} — {e.get('reason', '')[:60]}")
    return 0


def lesson_lines(ws: Path) -> list[str]:
    f = ws / "tensura" / "lessons.md"
    if not f.is_file():
        return []
    return [l.strip() for l in f.read_text(encoding="utf-8", errors="replace").splitlines()
            if "[generic?]" in l.lower() or "[generic]" in l.lower()]


def cmd_lessons(ws: Path | None, scan: Path | None) -> int:
    spaces = sorted(p for p in scan.iterdir() if p.is_dir() and (p / ".cecilia").is_dir()) if scan else [ws]
    total = 0
    for s in spaces:
        lines = lesson_lines(s)
        if lines:
            print(f"\n{s.name}")
            for l in lines:
                print("  " + l)
            total += len(lines)
    print(f"\n{total} lesson(s) marked [generic?]. Promote one by adding it to the matching skill in your Cecilia repo "
          "(e.g. shared/code-quality.md or a role's references/workflow.md), then release and `cecilia upgrade`.")
    return 0


ROLE_FILES = {"dev-be": "cecilia-dev-be", "dev-fe": "cecilia-dev-fe", "db": "cecilia-db", "test": "cecilia-test",
              "review": "cecilia-review", "devops": "cecilia-devops", "design": "cecilia-design", "ui": "cecilia-ui",
              "plan": "cecilia-plan", "discovery": "cecilia-discovery", "api-ux": "cecilia-api-ux",
              "extend": "cecilia-extend", "orchestrator": "cecilia-orchestrator"}


def report_role(stem: str, reg: dict | None = None) -> tuple[str | None, str | None]:
    """Report file stem -> (cecilia role, lens): `dev-be`, `dev-be-2`, `test-security`, `review-data-1`."""
    shorts = dict(ROLE_FILES)
    for name in (reg or {}).get("roles", {}):
        shorts[short(name)] = name
    lenses = {n for k in ("test", "review") for n in ((reg or {}).get("lenses", {}).get(k) or {})}
    base = re.sub(r"-\d+$", "", stem)
    for key in sorted(shorts, key=len, reverse=True):
        if base == key:
            return shorts[key], None
        if base.startswith(key + "-"):
            rest = base[len(key) + 1:]
            return shorts[key], (rest if rest in lenses else None)
    return None, None


def cmd_scorecard(ws: Path) -> int:
    reports: Counter = Counter()
    deviations: Counter = Counter()
    reg = load_reg(ws)
    for f in (ws / "tensura" / "reports").glob("*/*.md"):
        role = report_role(f.stem, reg)[0]
        if not role:
            continue
        reports[role] += 1
        dev = field(f.read_text(encoding="utf-8", errors="replace"), "Deviations")
        if dev and dev.lower().strip(" .`") not in {"none", "không", "-"}:
            deviations[role] += 1
    checks = Counter()
    for f in (ws / "tensura" / "reports").glob("*/evidence.json"):
        try:
            checks[json.loads(f.read_text(encoding="utf-8")).get("result", "?")] += 1
        except ValueError:
            continue
    refusals: dict = defaultdict(Counter)
    for e in guard_events(ws):
        if e.get("decision") in {"deny", "ask"} and str(e.get("payload")) != "gh pr merge 1":   # doctor's probe
            refusals[e.get("agent") or "main session"][e["decision"]] += 1
    panel = Counter()
    for f in (ws / "tensura" / "reports").glob("*/panel/verdict.md"):
        text = f.read_text(encoding="utf-8", errors="replace")
        for k in ("ACCEPTED", "REJECTED", "DISPUTED"):
            panel[k] += len(re.findall(rf"\b{k}\b", text))
    names = sorted(set(reports) | set(refusals))
    print(f"{'role':<22} {'reports':>7} {'deviations':>10} {'guard deny':>10} {'guard ask':>9}")
    for n in names:
        print(f"{n:<22} {reports[n]:>7} {deviations[n]:>10} {refusals[n]['deny']:>10} {refusals[n]['ask']:>9}")
    print(f"\nSelf-checks (evidence.json): {dict(checks) or 'none yet'}")
    if panel:
        print(f"Review panel findings: {dict(panel)}")
    print("\nRead it as: many deviations → the role's instructions or the plans are unclear; many guard denials → the role "
          "keeps trying something it may not do; failed self-checks → fix before review.")
    return 0


def cmd_clean(ws: Path, project: Path, apply: bool, days: int) -> int:
    base = ws / ".worktrees"
    cands = []
    listing = git(project, "worktree", "list", "--porcelain").split("\n\n")
    for block in listing:
        m = re.search(r"^worktree (.+)$", block, re.M)
        if not m:
            continue
        path = Path(m.group(1))
        if base not in path.parents:
            continue
        dirty = bool(git(path, "status", "--porcelain"))
        cands.append(("worktree", path, "has uncommitted changes — kept" if dirty else "clean", dirty))
    cutoff = dt.datetime.now().timestamp() - days * 86400
    for root in (ws / "tensura" / "backups", ws / ".cecilia" / "backup"):
        for d in sorted(root.glob("*")) if root.is_dir() else []:
            if d.is_dir() and d.stat().st_mtime < cutoff:
                cands.append(("backup", d, f"older than {days} days", False))
    if not cands:
        print("Nothing to clean.")
        git(project, "worktree", "prune")
        return 0
    for kind, path, note, _ in cands:
        print(f"  {kind:8} {path}  ({note})")
    if not apply:
        print("\nList only. Re-run with --apply to remove the clean worktrees and old backups (you confirm first). "
              "Branches stay; nothing is pushed or deleted remotely.")
        return 0
    if not (sys.stdin.isatty() and input("Type CLEAN to remove the items above (dirty worktrees are kept): ").strip() == "CLEAN"):
        print("Cancelled.")
        return 1
    for kind, path, _, dirty in cands:
        if kind == "worktree" and not dirty:
            subprocess.call(["git", "-C", str(project), "worktree", "remove", str(path)])
        elif kind == "backup":
            shutil.rmtree(path, ignore_errors=True)
    git(project, "worktree", "prune")
    print("Done.")
    return 0


# --------------------------------------------------------------------------- rules (v20, DESIGN-V20 §3)

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates" / "rules"
RULE_LINE = re.compile(r"^\s*[-*]\s+(PR-[^\s:]*)\s*:\s*(.*)$")
RULE_ID = re.compile(r"^PR-\d{2,}$")
CHECK_BLOCK = re.compile(r"^```[ \t]*cecilia-check[ \t]*\r?\n(.*?)^```", re.M | re.S)
COMMENT = re.compile(r"<!--.*?-->", re.S)
CHECK_KEYS = {"id", "forbid_regex", "paths", "require_command", "why"}
# A rule may only tighten (A4): wording that grants push / PR / merge / deploy / production / secrets is refused.
PERMIT = re.compile(r"\b(may|can|could|allow(?:s|ed)?(?: to)?|permit(?:s|ted)?(?: to)?|free to|ok(?:ay)? to|fine to|"
                    r"is fine|are fine|without (?:asking|approval|confirmation|cecilia)|no need to ask|"
                    r"skip(?:ping)? (?:the )?(?:guard|approval|review|push lock)|bypass(?:es|ing)?|"
                    r"disable|turn off|switch off|ignore)\b", re.I)
TARGET = re.compile(r"(\bpush(?:es|ed|ing)?\b|\bforce-push|\bpull requests?\b|\bmerge requests?\b|\bPRs?\b|\bMRs?\b|"
                    r"\bmerg(?:e|es|ed|ing)\b|\bdeploy(?:s|ed|ing|ment)?\b|\bproduction\b|\bprod\b|\bsecrets?\b|"
                    r"\bcredentials?\b|\bapi[ _-]?keys?\b|\.env\b|\bguard\b|\bpush lock\b|\blocal-only\b)", re.I)
NEGATION = re.compile(r"\b(not|never|no|cannot|can't|mustn't|don't|do not|must not|forbidden|nor)\b", re.I)


def short(name: str) -> str:
    return name[len("cecilia-"):] if name.startswith("cecilia-") else name


def rules_hash(ws: Path, role: str | None, flow: str, lens: str | None) -> str:
    """DESIGN-V20 §3 — same algorithm in workflow.py, the guard and cecilia_check.py (copied, not imported)."""
    files = ["rules/_project.md"] + ([f"rules/roles/{short(role)}.md"] if role else []) + \
            [f"rules/flows/{flow}.md"] + ([f"rules/lenses/{lens}.md"] if lens else [])
    h = hashlib.sha256()
    for rel in files:
        p = ws / rel
        if p.is_file():
            h.update(rel.encode() + b"\n" + p.read_bytes() + b"\n")
    return h.hexdigest()[:12]


def rules_template(kind: str, name: str = "") -> str:
    """kind: project | role | flow | lens. Text of a new rules file (header only, no rules)."""
    f = TEMPLATES / ("_project.md" if kind == "project" else f"{kind}.md")
    text = f.read_text(encoding="utf-8")
    return text.replace("__NAME__", name).replace("__SHORT__", short(name))


def rules_rel(kind: str, name: str = "") -> str:
    return {"project": "rules/_project.md", "role": f"rules/roles/{short(name)}.md",
            "flow": f"rules/flows/{name}.md", "lens": f"rules/lenses/{name}.md"}[kind]


def _strip_comments(text: str) -> str:
    return COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def parse_rules(text: str) -> tuple[list, list, list]:
    """-> (rules [(id, text, line)], checks [dict], errors). HTML comments (the header) are ignored."""
    body = _strip_comments(text)
    rules, checks, errors = [], [], []
    in_block = False
    for i, line in enumerate(body.splitlines(), 1):
        if line.strip().startswith("```"):
            in_block = not in_block
            continue
        m = None if in_block else RULE_LINE.match(line)
        if m:
            rules.append((m.group(1), m.group(2).strip(), i))
    for m in CHECK_BLOCK.finditer(body):
        try:
            data = json.loads(m.group(1))
        except ValueError as e:
            errors.append(f"cecilia-check block is not valid JSON ({e})")
            continue
        if not isinstance(data, list) or not all(isinstance(x, dict) for x in data):
            errors.append("cecilia-check block must be a JSON list of objects")
            continue
        checks.extend(data)
    return rules, checks, errors


def loosening(text: str) -> str:
    """The phrase that would loosen A3/A4 (push/PR/merge/deploy/production/secrets/guard), or ''."""
    for sentence in re.split(r"[.;!?]\s|[.;!?]$|\n", text):
        target = TARGET.search(sentence)
        if not target:
            continue
        for m in PERMIT.finditer(sentence):
            own = "" if m.group(0).lower().startswith("no ") else m.group(0)    # "no need to ask" grants
            window = sentence[max(0, m.start() - 24): m.start()] + own + sentence[m.end(): m.end() + 8]
            if not NEGATION.search(window):
                return f"'{m.group(0)}' … '{target.group(0)}'"
    return ""


def lint_text(rel: str, text: str, max_bytes: int = 2048) -> list[str]:
    errs = []
    size = len(text.encode("utf-8"))
    if max_bytes and size > max_bytes:
        errs.append(f"{rel}: {size} bytes > rules.max_bytes_per_file {max_bytes} — shorten or split")
    rules, checks, perrs = parse_rules(text)
    errs += [f"{rel}: {e}" for e in perrs]
    seen: dict = {}
    for rid, body, line in rules:
        if not RULE_ID.match(rid):
            errs.append(f"{rel}:{line}: bad rule id '{rid}' (use PR-nn)")
        if rid in seen:
            errs.append(f"{rel}:{line}: duplicate id {rid} (first on line {seen[rid]})")
        seen.setdefault(rid, line)
        if not body:
            errs.append(f"{rel}:{line}: {rid} has no text")
        why = loosening(body)
        if why:
            errs.append(f"{rel}:{line}: {rid} loosens a safety rule ({why}) — rules may only tighten (A4)")
    for c in checks:
        cid = c.get("id")
        where = f"{rel}: cecilia-check {cid or '?'}"
        if not isinstance(cid, str) or cid not in seen:
            errs.append(f"{where}: 'id' must name a rule of this file")
        extra = set(c) - CHECK_KEYS
        if extra:
            errs.append(f"{where}: unknown key(s) {sorted(extra)}")
        kinds = [k for k in ("forbid_regex", "require_command") if k in c]
        if len(kinds) != 1:
            errs.append(f"{where}: needs exactly one of forbid_regex / require_command")
        if "forbid_regex" in c:
            try:
                re.compile(str(c["forbid_regex"]))
            except re.error as e:
                errs.append(f"{where}: forbid_regex does not compile ({e})")
            if not isinstance(c["forbid_regex"], str):
                errs.append(f"{where}: forbid_regex must be a string")
        if "paths" in c and not (isinstance(c["paths"], list) and all(isinstance(p, str) for p in c["paths"])):
            errs.append(f"{where}: paths must be a list of globs")
        if "require_command" in c and not (isinstance(c["require_command"], str) and c["require_command"].strip()):
            errs.append(f"{where}: require_command must be a non-empty string")
    return errs


def rules_files(ws: Path) -> list[Path]:
    d = ws / "rules"
    return sorted(p for p in d.rglob("*.md") if p.is_file()) if d.is_dir() else []


def max_bytes(cfg: dict) -> int:
    r = cfg.get("rules") if isinstance(cfg.get("rules"), dict) else {}
    try:
        return int(r.get("max_bytes_per_file", 2048))
    except (TypeError, ValueError):
        return 2048


def lint_workspace(ws: Path, cfg: dict | None = None) -> list[str]:
    cfg = load_cfg(ws) if cfg is None else cfg
    errs = []
    for f in rules_files(ws):
        errs += lint_text(f.relative_to(ws).as_posix(), f.read_text(encoding="utf-8", errors="replace"), max_bytes(cfg))
    return errs


def role_names(ws: Path) -> list[str]:
    reg = load_reg(ws)
    names = list(reg.get("roles", {})) or ["cecilia-" + k for k in ROLE_FILES]
    return sorted(set(names))


def resolve_role(ws: Path, role: str) -> str | None:
    for name in role_names(ws):
        if role in (name, short(name)):
            return name
    return None


def cmd_rules_list(ws: Path) -> int:
    cfg = load_cfg(ws)
    flow = cfg.get("flow") or "personal"
    files = rules_files(ws)
    if not files:
        print("No rules/ folder in this workspace — `cecilia upgrade` creates it.")
        return 0
    print(f"Rules in {ws / 'rules'} (flow {flow}):")
    for f in files:
        rules, checks, _ = parse_rules(f.read_text(encoding="utf-8", errors="replace"))
        print(f"  {f.relative_to(ws).as_posix():<34} {len(rules):3} rule(s) {len(checks):2} check(s)  {f.stat().st_size} B")
    print(f"\nhash (project + flow {flow}): {rules_hash(ws, None, flow, None)}")
    return 0


def cmd_rules_show(ws: Path, role: str | None) -> int:
    cfg = load_cfg(ws)
    flow = cfg.get("flow") or "personal"
    name = None
    if role:
        name = resolve_role(ws, role)
        if not name:
            print(f"unknown role '{role}' — one of: {', '.join(short(n) for n in role_names(ws))}")
            return 2
    rels = [rules_rel("project")] + ([rules_rel("role", name)] if name else []) + [rules_rel("flow", flow)]
    for rel in rels:
        f = ws / rel
        print(f"==> {rel}" + ("" if f.is_file() else "  (missing)"))
        if f.is_file():
            rules, _, _ = parse_rules(f.read_text(encoding="utf-8", errors="replace"))
            for rid, body, _ in rules:
                print(f"  - {rid}: {body}")
            if not rules:
                print("  (no rules)")
    print(f"\nRules: {rules_hash(ws, name, flow, None)}  (role {short(name) if name else '-'}, flow {flow}, lens -)")
    return 0


def next_rule_id(ws: Path) -> str:
    n = 0
    for f in rules_files(ws):
        for rid, _, _ in parse_rules(f.read_text(encoding="utf-8", errors="replace"))[0]:
            m = re.match(r"^PR-(\d+)$", rid)
            if m:
                n = max(n, int(m.group(1)))
    return f"PR-{n + 1:02d}"


def add_rule(ws: Path, kind: str, name: str, text: str) -> tuple[bool, str]:
    """Add `- PR-nn: text` to one rules file (created from its template when missing). Never writes a file that
    fails lint. Returns (ok, message)."""
    text = " ".join(text.split())
    if not text:
        return False, "empty rule text"
    why = loosening(text)
    if why:
        return False, f"refused: the rule loosens a safety rule ({why}) — rules may only tighten (A4)"
    if kind == "role":
        full = resolve_role(ws, name)
        if not full:
            return False, f"unknown role '{name}'"
        name = full
    if kind in {"flow", "lens"} and not re.match(r"^[a-z][a-z0-9-]*$", name or ""):
        return False, f"bad {kind} name '{name}'"
    rel = rules_rel(kind, name)
    f = ws / rel
    cur = f.read_text(encoding="utf-8") if f.is_file() else rules_template(kind, name)
    rid = next_rule_id(ws)
    line = f"- {rid}: {text}"
    lines = cur.splitlines()
    body = _strip_comments(cur).splitlines()
    last = max((i for i, l in enumerate(body) if RULE_LINE.match(l)), default=None)
    block = next((i for i, l in enumerate(body) if re.match(r"^```[ \t]*cecilia-check", l)), None)
    if last is not None:
        lines.insert(last + 1, line)
    elif block is not None:
        lines[block:block] = [line, ""]
    else:
        while lines and not lines[-1].strip():
            lines.pop()
        lines += ["", line]
    new = "\n".join(lines) + "\n"
    errs = lint_text(rel, new, max_bytes(load_cfg(ws)))
    if errs:
        return False, "refused:\n  " + "\n  ".join(errs)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(new, encoding="utf-8")
    return True, f"{rel}: added {rid}"


def human_terminal(what: str) -> bool:
    if sys.stdin.isatty() and sys.stdout.isatty():
        return True
    print(f"ERROR: {what} needs your interactive terminal (Cecilia only; agents are refused).", file=sys.stderr)
    return False


def cmd_rules(ws: Path, args: list[str], role: str | None, project_rule: bool, flow: str | None,
              lens: str | None) -> int:
    sub = args[0] if args else "list"
    if sub == "list":
        return cmd_rules_list(ws)
    if sub == "show":
        return cmd_rules_show(ws, args[1] if len(args) > 1 else role)
    if sub == "lint":
        errs = lint_workspace(ws)
        for e in errs:
            print(e)
        print(("FAIL" if errs else "PASS") + f" — {len(rules_files(ws))} rules file(s), {len(errs)} error(s)")
        return 1 if errs else 0
    if sub == "add":
        targets = [t for t in (("role", role) if role else None, ("project", "") if project_rule else None,
                               ("flow", flow) if flow else None, ("lens", lens) if lens else None) if t]
        text = " ".join(args[1:])
        if len(targets) != 1 or not text:
            print('usage: cecilia rules add (--project | --role R | --flow F | --lens L) "rule text"')
            return 2
        if not human_terminal("cecilia rules add"):
            return 2
        ok, msg = add_rule(ws, targets[0][0], targets[0][1], text)
        print(msg)
        return 0 if ok else 1
    print("usage: cecilia rules list | show [role] | lint | add (--project | --role R | --flow F | --lens L) \"text\"")
    return 2


# --------------------------------------------------------------------------- flow (v20)

def flow_names(ws: Path) -> list[str]:
    return sorted(load_reg(ws).get("flows") or {"personal": {}, "team": {}})


FLOW_LINE = re.compile(r"^(- \*\*Current flow:\*\* )`[^`]*`", re.M)


def write_json_atomic(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def cmd_flow(ws: Path, name: str | None) -> int:
    cfg = load_cfg(ws)
    cur = cfg.get("flow") or "personal"
    names = flow_names(ws)
    if not name:
        print(f"flow: {cur}   (available: {', '.join(names)})")
        reg_flow = (load_reg(ws).get("flows") or {}).get(cur) or {}
        settings = dict(reg_flow.get("settings") or {})
        settings.update(((cfg.get("flows") or {}).get(cur) or {}) if isinstance(cfg.get("flows"), dict) else {})
        for k, v in settings.items():
            print(f"  {k:15} {json.dumps(v, ensure_ascii=False)}")
        if reg_flow.get("summary"):
            print(f"  {reg_flow['summary']}")
        print("Switch with `cecilia flow <name>` (asks you to type the name).")
        return 0
    if name not in names:
        print(f"unknown flow '{name}' — one of: {', '.join(names)}")
        return 2
    if not human_terminal("changing the flow"):
        return 2
    print(f"Workspace: {ws}\nCurrent:   {cur}\nNew:       {name}")
    if input(f"Type {name} to confirm: ").strip() != name:
        print("Cancelled.")
        return 1
    return set_flow(ws, name)


def set_flow(ws: Path, name: str) -> int:
    f = ws / ".cecilia" / "config.json"
    cfg = load_cfg(ws)
    if not f.is_file() or not cfg:
        print("ERROR: .cecilia/config.json missing or unreadable — run `cecilia upgrade` first", file=sys.stderr)
        return 2
    cfg["flow"] = name
    write_json_atomic(f, cfg)
    rf = ws / rules_rel("flow", name)
    if (ws / "rules").is_dir() and not rf.exists():
        rf.parent.mkdir(parents=True, exist_ok=True)
        rf.write_text(rules_template("flow", name), encoding="utf-8")
    for guide in ("CLAUDE.md", "AGENTS.md"):
        g = ws / guide
        if g.is_file():
            text = g.read_text(encoding="utf-8")
            new = FLOW_LINE.sub(lambda m: f"{m.group(1)}`{name}`", text)
            if new != text:
                g.write_text(new, encoding="utf-8")
    print(f"Flow set to {name}.")
    return 0


# --------------------------------------------------------------------------- extensions (v20)

def ext_dir(ws: Path, cfg: dict | None = None) -> Path:
    cfg = load_cfg(ws) if cfg is None else cfg
    e = cfg.get("extensions") if isinstance(cfg.get("extensions"), dict) else {}
    rel = e.get("dir") or ".cecilia/extensions"
    p = Path(rel)
    return p if p.is_absolute() else ws / p


def proposal_dir(ws: Path, arg: str) -> Path:
    p = Path(arg).expanduser()
    for cand in ([p] if p.is_absolute() else [Path.cwd() / p, ws / p, ws / "tensura" / "extensions" / arg]):
        if cand.is_dir():
            return cand.resolve()
    raise SystemExit(f"cecilia: no proposal folder '{arg}' (look in {ws / 'tensura' / 'extensions'})")


def proposal_files(prop: Path) -> list[Path]:
    """Files copied by `extension apply`: everything in the proposal's sub-folders (registry/, skills/, guides);
    loose files at the top (README, proposal notes) stay in tensura/. `rules/**` goes to the workspace rules/."""
    return sorted(f for f in prop.rglob("*") if f.is_file() and f.parent != prop and "__pycache__" not in f.parts)


def apply_target(ws: Path, prop: Path, f: Path) -> Path:
    rel = f.relative_to(prop)
    return ws / rel if rel.parts[0] == "rules" else ext_dir(ws) / rel


def _registry_module():
    sys.path.insert(0, str(ROOT / "tools"))
    import registry  # noqa: E402  (A1, tools/registry.py)
    return registry


def copy_extension(ws: Path, prop: Path) -> list[Path]:
    """Copy a checked proposal: registry/skills/guides into .cecilia/extensions (old copies backed up), rules/**
    into the workspace rules/ only where Cecilia has no file yet. Returns the written paths."""
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    written = []
    for f in proposal_files(prop):
        dest = apply_target(ws, prop, f)
        if dest.parts[len(ws.parts)] == "rules" and dest.exists():
            continue                                    # never overwrite Cecilia's rules
        if dest.is_file():
            bak = ws / ".cecilia" / "backup" / f"{stamp}-extension-{prop.name}" / dest.relative_to(ws)
            bak.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dest, bak)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, dest)
        written.append(dest)
    return written


def check_extension(ws: Path, prop: Path) -> list[str]:
    """registry.validate on a temporary overlay: current extensions + the proposal."""
    if not proposal_files(prop):
        return [f"{prop}: nothing to apply (expected registry/… and skills/<name>/ sub-folders)"]
    reg_mod = _registry_module()
    with tempfile.TemporaryDirectory() as tmp:
        overlay = Path(tmp) / "extensions"
        cur = ext_dir(ws)
        if cur.is_dir():
            shutil.copytree(cur, overlay)
        errs = []
        for f in proposal_files(prop):
            rel = f.relative_to(prop)
            if rel.parts[0] == "rules":
                errs += lint_text(rel.as_posix(), f.read_text(encoding="utf-8", errors="replace"),
                                  max_bytes(load_cfg(ws)))
                continue
            dest = overlay / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, dest)
        known = set(reg_mod.validate(reg_mod.load(ROOT), ROOT))       # core problems are not the proposal's
        reg = reg_mod.load(ROOT, extensions=overlay)
        return errs + [str(e).replace(str(overlay), "<extensions>") for e in reg_mod.validate(reg, ROOT)
                       if e not in known]


def cmd_extension(ws: Path, project: Path, args: list[str]) -> int:
    sub = args[0] if args else "list"
    if sub == "list":
        applied = ext_dir(ws)
        names = sorted(f"{f.parent.relative_to(applied / 'registry').as_posix()}/{f.stem}"
                       for f in (applied / "registry").rglob("*.json")) if (applied / "registry").is_dir() else []
        print("Applied extensions: " + (", ".join(names) or "none"))
        props = ws / "tensura" / "extensions"
        found = sorted(p.name for p in props.iterdir() if p.is_dir()) if props.is_dir() else []
        print("Proposals (tensura/extensions): " + (", ".join(found) or "none"))
        return 0
    if sub not in {"check", "apply"} or len(args) < 2:
        print("usage: cecilia extension list | check <dir> | apply <dir>")
        return 2
    prop = proposal_dir(ws, args[1])
    errs = check_extension(ws, prop)
    for e in errs:
        print(e)
    print(("FAIL" if errs else "PASS") + f" — proposal {prop.name}: {len(proposal_files(prop))} file(s), "
          f"{len(errs)} error(s)")
    if sub == "check" or errs:
        return 1 if errs else 0
    if not human_terminal("cecilia extension apply"):
        return 2
    dest_root = ext_dir(ws)
    files = proposal_files(prop)
    for f in files:
        dest = apply_target(ws, prop, f)
        keep = dest.parts[len(ws.parts)] == "rules" and dest.exists()
        print(f"  {'=' if keep else '+'} {dest.relative_to(ws).as_posix()}" + ("  (your rules file is kept)" if keep else ""))
    if input(f"Type {prop.name} to copy these into {dest_root.relative_to(ws).as_posix()} and upgrade: ").strip() \
            != prop.name:
        print("Cancelled.")
        return 1
    copy_extension(ws, prop)
    hosts = [x for h, d in (("claude", ".claude"), ("antigravity", ".agents")) if (ws / d).is_dir()
             for x in ("--host", h)] or ["--host", "claude", "--host", "antigravity"]
    where = [] if ws == project else ["--workspace", str(ws)]
    return subprocess.call([sys.executable, str(ROOT / "tools" / "install.py"), "--project", str(project), *where,
                            *hosts, "--upgrade", "--apply"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["status", "lessons", "scorecard", "clean", "flow", "rules", "extension"])
    ap.add_argument("args", nargs="*", help="flow: [name] · rules: list|show [role]|lint|add TEXT · "
                                            "extension: list|check DIR|apply DIR")
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--all", dest="scan", help="lessons: scan every workspace under this folder")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--rule-role", help="rules add: the role file")
    ap.add_argument("--rule-project", action="store_true", help="rules add: rules/_project.md")
    ap.add_argument("--rule-flow", help="rules add: the flow file")
    ap.add_argument("--rule-lens", help="rules add: the lens file")
    argv = list(sys.argv[1:] if argv is None else argv)
    tail: list[str] = []
    if "--" in argv:                      # `… -- show dev-be`: everything after -- is positional (rule text too)
        i = argv.index("--")
        argv, tail = argv[:i], argv[i + 1:]
    a = ap.parse_args(argv)
    a.args = list(a.args) + tail
    ws, project = Path(a.workspace).resolve(), Path(a.project).resolve()
    if a.command == "status":
        return cmd_status(ws, project)
    if a.command == "lessons":
        return cmd_lessons(ws, Path(a.scan) if a.scan else None)
    if a.command == "scorecard":
        return cmd_scorecard(ws)
    if a.command == "flow":
        return cmd_flow(ws, a.args[0] if a.args else None)
    if a.command == "rules":
        return cmd_rules(ws, a.args, a.rule_role, a.rule_project, a.rule_flow, a.rule_lens)
    if a.command == "extension":
        return cmd_extension(ws, project, a.args)
    return cmd_clean(ws, project, a.apply, a.days)


if __name__ == "__main__":
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    sys.exit(main())
