#!/usr/bin/env python3
"""Cecilia's G2 approval tool — run it yourself, in your own terminal. Agents never run it.

    cecilia_approve.py tensura/plans/SHOP-42-cancel.md [--task SHOP-42-B01] [--hours 72]
    cecilia_approve.py tensura/plans/SHOP-42-cancel.md --all      # every block, one confirmation
    cecilia_approve.py lint tensura/plans/SHOP-42-cancel.md       # findings only, approves nothing
    cecilia_approve.py --list
    cecilia_approve.py --show SHOP-42-B01
    cecilia_approve.py --revoke SHOP-42-B01

It reads a ```cecilia-scope``` block from the plan, shows exactly what it would allow, asks you to
type the task id, and writes .cecilia/approvals/<task>.json — a snapshot the guard enforces until it
expires or you revoke it. It refuses to run without an interactive terminal, so an agent's shell
cannot approve on your behalf. Every block is linted first (unset variables, placeholders, swallowed
failures, delete-before-verify, secret dumps, paths doubling the project folder); an ERROR approves nothing.

`--yes --by NAME` (20.2) skips the terminal check and the typed confirmation; it is honoured only when env
CECILIA_MCP=1 (the `cecilia mcp` server's control tools) and refused everywhere else. Lint still blocks.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import getpass
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

TASK_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
BLOCK_RE = re.compile(r"```cecilia-scope[ \t]*\n(.*?)\n```", re.S)
FORBIDDEN_PREFIXES = (".cecilia", ".git/", ".claude", ".agents", ".github/CODEOWNERS", ".worktrees")
TOO_BROAD = {"*", "**", "**/*", "./**", "./*", "/", "."}
MAX_HOURS = 24 * 14


class ScopeError(ValueError):
    pass


def find_root(start: Path) -> Path:
    for d in [start, *start.parents]:
        if (d / ".cecilia").is_dir():
            return d
    raise ScopeError("no .cecilia/ folder found here or above — install the guard first (tools/install.py)")


def parse_blocks(text: str):
    blocks = []
    for raw in BLOCK_RE.findall(text):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ScopeError(f"a cecilia-scope block is not valid JSON: {e}") from e
        blocks.append((raw, data))
    return blocks


def validate(scope: dict) -> dict:
    task = scope.get("task", "")
    if not isinstance(task, str) or not TASK_RE.match(task):
        raise ScopeError(f"task id {task!r} is invalid (letters, digits, . _ -)")
    write = scope.get("write")
    if not isinstance(write, list) or not write or not all(isinstance(w, str) and w.strip() for w in write):
        raise ScopeError("'write' must be a non-empty list of paths")
    for w in write:
        w2 = w.strip()
        if w2.startswith("/") or ".." in w2.split("/") or "\\" in w2:
            raise ScopeError(f"write path {w!r} must be relative to the project, without '..'")
        if w2 in TOO_BROAD:
            raise ScopeError(f"write path {w!r} would allow the whole project — list real paths")
        bare = w2[2:] if w2.startswith("./") else w2
        if bare.startswith(FORBIDDEN_PREFIXES) or bare.startswith("**/."):
            raise ScopeError(f"write path {w!r} touches guard/host/git files — never approvable")
    commands = scope.get("commands", [])
    if not isinstance(commands, list) or not all(isinstance(c, str) for c in commands):
        raise ScopeError("'commands' must be a list of strings")
    envs = scope.get("environments", ["local"])
    if not isinstance(envs, list) or any(re.search(r"prod", e, re.I) for e in envs):
        raise ScopeError("'environments' must be a list and can never include production")
    worktree = scope.get("worktree")
    if worktree is not None and (not isinstance(worktree, str) or not re.match(r"^[A-Za-z0-9._-]+$", worktree)):
        raise ScopeError("'worktree' must be the name of one .worktrees/<name>/ folder (letters, digits, . _ -)")
    hours = scope.get("expires_hours", 72)
    if not isinstance(hours, (int, float)) or not 0 < hours <= MAX_HOURS:
        raise ScopeError(f"'expires_hours' must be between 1 and {MAX_HOURS}")
    out = {"task": task, "write": [w.strip() for w in write], "commands": commands,
           "environments": envs, "expires_hours": hours}
    if worktree:
        out["worktree"] = worktree
    return out


# ---------------------------------------------------------------------------------------------------------------
# Plan linter (v20.1). Runs before any approval is written; an ERROR blocks the whole approval. It catches plans
# that *look* safe but are not: safety gates over variables nobody set, placeholders, paths that double the
# project folder, swallowed failures, deletes before the copy is verified, secret dumps.
# ---------------------------------------------------------------------------------------------------------------
ERROR, WARN = "ERROR", "WARN"
SEND_BACK = "send the plan back to cecilia-plan; do not edit it yourself"

_BASH_KNOWN = {"HOME", "PWD", "OLDPWD", "USER", "LOGNAME", "PATH", "SHELL", "HOSTNAME", "TMPDIR", "UID", "EUID",
               "PPID", "RANDOM", "LINENO", "SECONDS", "IFS", "BASHPID", "BASH_SOURCE", "FUNCNAME", "OSTYPE",
               "HOSTTYPE", "LANG", "TERM",
               # awk builtins ('{print $NF}')
               "NF", "NR", "FNR", "FS", "OFS", "RS", "ORS", "FILENAME"}
_PS_KNOWN = {"_", "psitem", "true", "false", "null", "args", "input", "lastexitcode", "error", "home", "pwd",
             "host", "pshome", "psscriptroot", "pscommandpath", "myinvocation", "matches", "this", "profile",
             "iswindows", "islinux", "ismacos", "psversiontable"}
_ENV_KNOWN = {"userprofile", "home", "homedrive", "homepath", "username", "userdomain", "computername", "appdata",
              "localappdata", "temp", "tmp", "programfiles", "programfiles(x86)", "programdata", "systemroot",
              "systemdrive", "windir", "path", "pathext", "pwd", "user", "os", "processor_architecture", "public",
              "comspec", "number_of_processors"}

_VAR_USE = re.compile(r"(?<!\\)\$(?:\{(?P<bang>[#!]?)(?P<benv>[Ee][Nn][Vv]:)?(?P<bname>[A-Za-z_][A-Za-z0-9_]*)"
                      r"(?P<mod>[^}]*)\}|(?P<env>[Ee][Nn][Vv]):(?P<ename>[A-Za-z_][A-Za-z0-9_()]*)"
                      r"|(?P<name>[A-Za-z_][A-Za-z0-9_]*))")
_DEFAULTED = re.compile(r"^:?[-=?+]")          # ${X:-d} ${X-d} ${X:=d} ${X:?msg} ${X:+alt}

_PLACEHOLDERS = [
    (re.compile(r"(?<![A-Za-z])(?:x{3,}|X{3,})(?![A-Za-z])"), "placeholder 'xxx'"),
    (re.compile(r"(?<![<\w])<[A-Za-z_][\w.:/-]*>"), "placeholder '<...>'"),
    (re.compile(r"\b(?:TODO|TBD|CHANGEME|CHANGE_ME|FIXME|REPLACEME|REPLACE_ME)\b"), "placeholder word"),
    (re.compile(r"(?:^|\s)(['\"]?)(?:\.\.\.|…)\1(?=\s|$)"), "'...' used as an argument"),
]
_SWALLOW = [
    re.compile(r"\|\|\s*(?:true|:)(?=\s*(?:$|[;&|)'\"]))"),
    re.compile(r"\|\|\s*exit\s+0\b"),
    re.compile(r";\s*(?:true|:)\s*['\"]?\s*\)?\s*$"),
    re.compile(r"\bset\s+\+e\b"),
    re.compile(r"(?i)-ErrorAction\s*:?\s*['\"]?(?:SilentlyContinue|Ignore)\b"),
    re.compile(r"(?i)(?<![\w-])-ea\s*:?\s*['\"]?(?:0|SilentlyContinue|Ignore)\b"),
    re.compile(r"(?i)\$ErrorActionPreference\s*=\s*['\"]?(?:SilentlyContinue|Ignore)"),
]
_VERIFY = re.compile(r"(?i)\b(?:sha\d*sum|shasum|md5sum|b2sum)\b[^;&|]*?\s(?:-c|--check)\b|\bcmp\s|\bdiff\s"
                     r"|\b(?:etcdctl|etcdutl)\b[^;&|]*?\bsnapshot\s+status\b|\btest\s+-s\s|\[\[?\s+-s\s"
                     r"|\bGet-FileHash\b")
_TOKEN = re.compile(r"[^\s;&|()'\"`]+")
_DELETERS = {"rm", "rmdir", "del", "erase", "remove-item"}
# `docker rm`, `git rm`, `crictl rm` … are subcommands of another tool, not a file delete
_SUBCMD_TOOLS = {"docker", "podman", "nerdctl", "crictl", "ctr", "git", "npm", "pnpm", "yarn", "helm", "kubectl",
                 "oc", "gh", "pip", "pip3", "cargo", "go", "conda", "brew", "apt", "apt-get", "dnf", "yum",
                 "snap", "flatpak", "virsh", "lxc", "incus", "multipass", "vagrant", "terraform", "pulumi", "minikube",
                 "kind", "k3d", "calicoctl", "cilium", "istioctl", "argocd", "flux", "az", "aws", "gcloud", "bun"}
_SECRET_RES = re.compile(r"(?i)^secrets?(?:\.v1)?(?:/.*)?$")


def project_root(root: Path) -> Path:
    """The project folder a workspace serves (config `workspace.project`), else `root` itself."""
    try:
        cfg = json.loads((root / ".cecilia" / "config.json").read_text(encoding="utf-8-sig"))
        proj = (cfg.get("workspace") or {}).get("project") if isinstance(cfg, dict) else None
    except (OSError, ValueError, AttributeError):
        proj = None
    if isinstance(proj, str) and proj.strip():
        p = Path(proj)
        return Path(os.path.normpath(str(p if p.is_absolute() else root / p)))
    return root


def _assigned_before(name: str, cmd: str, pos: int, env: bool) -> bool:
    n = re.escape(name)
    if env:
        pats = [rf"(?i)\$env:{n}\s*=(?!=)"]
    else:
        pats = [rf"(?<![\w$./\\-]){n}\+?=(?!=)",                          # NAME=…  export NAME=…  local NAME=…
                rf"\bfor\s+{n}\s+in\b",
                rf"\b(?:read|mapfile|readarray)\b[^;&|\n]*?(?<![\w$-]){n}\b",
                rf"(?i)\${n}\s*[-+*/]?=(?!=)",                             # PowerShell $NAME = …
                rf"(?i)\bforeach\s*\(\s*\${n}\s+in\b",
                rf"(?i)-(?:OutVariable|ov)\s+['\"]?{n}\b",
                rf"\${n}\s*:=",                                            # go template {{ $x := … }}
                ]
    for p in pats:
        m = re.search(p, cmd)
        if m and m.start() <= pos:            # == pos: this `$NAME = …` is the assignment itself
            return True
    return bool(not env and re.search(rf"--arg(?:json)?\s+{n}\b", cmd))    # jq --arg NAME v, anywhere


def _unresolved_vars(cmd: str, declared: set) -> list:
    out = []
    for m in _VAR_USE.finditer(cmd):
        if m.group("bname"):
            if m.group("bang") == "!" or _DEFAULTED.match(m.group("mod") or ""):
                continue
            name, env = m.group("bname"), bool(m.group("benv"))
        elif m.group("ename"):
            name, env = m.group("ename"), True
        else:
            name, env = m.group("name"), False
        if env:
            if name.casefold() in _ENV_KNOWN or name.casefold() in declared:
                continue
        elif name in _BASH_KNOWN or name.casefold() in _PS_KNOWN or name.casefold() in declared:
            continue
        if _assigned_before(name, cmd, m.start(), env):
            continue
        label = f"$env:{name}" if env else f"${name}"
        if label not in out:
            out.append(label)
    return out


def _placeholders(text: str) -> list:
    found = []
    for rx, what in _PLACEHOLDERS:
        m = rx.search(text)
        if m:
            hit = m.group(0).strip()
            found.append(what if f"'{hit}'" in what else f"{what} {hit!r}")
    return found


def _is_delete(cmd: str):
    """Start offset of the first file-delete command word in `cmd`, or None."""
    prev = None
    for m in _TOKEN.finditer(cmd):
        tok = m.group(0)
        if tok.casefold() in _DELETERS and (prev is None or prev.casefold() not in _SUBCMD_TOOLS):
            return m.start()
        prev = tok
    return None


def _secret_dump(cmd: str) -> bool:
    for seg in re.split(r"\|\||&&|[|;]", cmd):
        toks = [t.strip("'\"") for t in seg.split()]
        low = [t.casefold() for t in toks]
        for i, t in enumerate(low):
            if t in ("kubectl", "oc") and "get" in low[i + 1:]:
                rest = toks[low.index("get", i + 1) + 1:]
                has_secret = any(_SECRET_RES.match(e) for r in rest if not r.startswith("-") for e in r.split(","))
                output = None
                for j, r in enumerate(rest):
                    if r in ("-o", "--output"):
                        output = rest[j + 1] if j + 1 < len(rest) else ""
                    elif r.startswith("--output="):
                        output = r[9:]
                    elif r.startswith("-o") and not r.startswith("--"):
                        output = r[2:].lstrip("=")
                if has_secret and output is not None and output.casefold() not in ("name", "wide"):
                    return True
            if t in ("etcdctl", "etcdutl") and "get" in low[i + 1:]:
                if re.search(r"/registry/secrets", seg) or (
                        re.search(r"/registry/?(?=[\s'\"]|$)", seg) and "--prefix" in seg):
                    return True
    return False


def _root_cause_warnings(plan_text: str) -> list:
    out = []
    heads = [(m.start(), m.end(), len(m.group(1)), m.group(2)) for m in
             re.finditer(r"(?m)^(#{1,6})[ \t]+(.+?)[ \t]*$", plan_text or "")]
    for i, (s, e, lvl, title) in enumerate(heads):
        if not re.search(r"(?i)root[\s_-]*cause|nguy[eê]n\s+nh[aâ]n", title):
            continue
        end = next((h[0] for h in heads[i + 1:] if h[2] <= lvl), len(plan_text))
        if "[verified]" not in plan_text[e:end].lower():
            out.append((WARN, f"section '{title.strip()}' has no [verified] marker — the root cause is a guess "
                              f"until evidence is attached"))
    return out


def lint_scope(scope: dict, project_root: Path, plan_text: str = "") -> list:
    """Lint one cecilia-scope block. Returns [(level, message)], level ERROR (blocks approval) or WARN."""
    out: list = []
    commands = [c for c in (scope.get("commands") or []) if isinstance(c, str)]
    write = [w for w in (scope.get("write") or []) if isinstance(w, str)]
    vars_ = scope.get("vars") or {}
    if not isinstance(vars_, dict) or not all(isinstance(k, str) and isinstance(v, str) and v.strip()
                                              for k, v in vars_.items()):
        out.append((ERROR, "'vars' must be an object of NAME: non-empty value"))
        vars_ = {}
    declared = {k.casefold() for k in vars_}
    for k, v in vars_.items():
        for p in _placeholders(v):
            out.append((ERROR, f"vars.{k} is a {p}: {v}"))

    root_name = project_root.name if project_root else ""
    if root_name:
        try:
            entries = {e.name for e in project_root.iterdir()}
        except OSError:
            entries = set()
        exists = (lambda s: s.casefold() in {e.casefold() for e in entries}) if os.name == "nt" else \
            (lambda s: s in entries)
    for w in write:
        bare = w.strip()
        bare = bare[2:] if bare.startswith("./") else bare
        first = re.split(r"[/\\]", bare, 1)[0]
        if root_name and first.casefold() == root_name.casefold() and not exists(first):
            out.append((ERROR, f"write path {w!r} starts with the project folder name '{root_name}'; paths are "
                               f"relative to the project root (it would land in {root_name}/{bare})"))
        for p in _placeholders(w):
            out.append((ERROR, f"write path has a {p}: {w}"))
        if "$" in w:
            out.append((ERROR, f"write path uses a shell variable; list the real path: {w}"))

    verified_at = None                      # index of the first command holding a verification step
    for idx, cmd in enumerate(commands):
        for v in _unresolved_vars(cmd, declared):
            out.append((ERROR, f"unresolved variable {v} — never assigned in this command nor listed in \"vars\" "
                               f"(a check over it passes vacuously): {cmd}"))
        for p in _placeholders(cmd):
            out.append((ERROR, f"{p} — put the real value: {cmd}"))
        if any(rx.search(cmd) for rx in _SWALLOW):
            out.append((ERROR, f"failure is swallowed (|| true, ; true, -ErrorAction SilentlyContinue …) — a "
                               f"failing step must stop the task: {cmd}"))
        dpos = _is_delete(cmd)
        vm = _VERIFY.search(cmd)
        if dpos is not None and verified_at is None and not (vm and vm.start() < dpos):
            out.append((ERROR, f"deletes before any verification (sha256sum -c, cmp, diff, snapshot status, "
                               f"test -s, Get-FileHash) earlier in the block: {cmd}"))
        if vm and verified_at is None:
            verified_at = idx
        if _secret_dump(cmd):
            out.append((ERROR, f"dumps Secret values (kubectl/oc get secret -o …, etcdctl get /registry/secrets) "
                               f"— list secret NAMES only: {cmd}"))
    out.extend(_root_cause_warnings(plan_text))
    return out


def lint_plan(text: str, project_root: Path, blocks=None) -> list:
    """[(task, level, message)] for every block; plan-level WARNs are reported once (task '-')."""
    blocks = parse_blocks(text) if blocks is None else blocks
    rows, seen = [], set()
    for _, data in blocks:
        task = data.get("task", "?") if isinstance(data, dict) else "?"
        for level, msg in lint_scope(data if isinstance(data, dict) else {}, project_root, text):
            key = (level, msg)
            if level == WARN and key in seen:
                continue
            seen.add(key)
            rows.append((task, level, msg))
    return rows


def print_findings(rows: list) -> bool:
    """Print lint rows; True when any ERROR."""
    bad = False
    for task, level, msg in rows:
        print(f"{level:<5} [{task}] {msg}")
        bad = bad or level == ERROR
    if bad:
        print(f"\nApproval blocked: {sum(1 for r in rows if r[1] == ERROR)} error(s). {SEND_BACK[0].upper()}"
              f"{SEND_BACK[1:]}.")
    return bad


def approver_name(root: Path) -> str:
    try:
        name = subprocess.run(["git", "config", "user.name"], cwd=root, capture_output=True, text=True,
                              timeout=5).stdout.strip()
    except Exception:
        name = ""
    return name or getpass.getuser()


YES_ONLY = "--yes is only for the Cecilia MCP server"


def yes_allowed() -> bool:
    """20.2: `--yes --by NAME` approves without the typed confirmation — only when `cecilia mcp` runs this tool
    (it sets CECILIA_MCP=1 for its control tools). Lint still runs and an ERROR still blocks."""
    return os.environ.get("CECILIA_MCP") == "1"


def build_record(scope: dict, plan: Path, root: Path, raw_block: str, approver: str, hours=None, now=None,
                 non_interactive: bool = False) -> dict:
    now = now or _dt.datetime.now(_dt.timezone.utc)
    hours = hours or scope["expires_hours"]
    extra = {"non_interactive": True} if non_interactive else {}
    return {
        "task": scope["task"], "write": scope["write"], "commands": scope["commands"],
        "environments": scope["environments"],
        **({"worktree": scope["worktree"]} if scope.get("worktree") else {}),
        "approved_by": approver, "approved_at": now.isoformat(timespec="seconds"),
        "expires_at": (now + _dt.timedelta(hours=hours)).isoformat(timespec="seconds"),
        "plan": plan.resolve().relative_to(root).as_posix() if plan.resolve().is_relative_to(root) else str(plan),
        "plan_sha256": hashlib.sha256(plan.read_bytes()).hexdigest(),
        "block_sha256": hashlib.sha256(raw_block.encode()).hexdigest(),
        "revoked": False,
        "tool": "cecilia_approve v20",
        **extra,
    }


def write_record(root: Path, rec: dict) -> Path:
    d = root / ".cecilia" / "approvals"
    d.mkdir(parents=True, exist_ok=True)
    target = d / f"{rec['task']}.json"
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, target)
    return target


def require_tty():
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise ScopeError("refusing to run without an interactive terminal — Cecilia runs this herself")


def cmd_approve(args, root: Path, ask=input, tty_check=None) -> int:
    """Approve one block (--task, or the only one) or every block (--all). `ask`/`tty_check` exist for tests;
    the command line always uses input() and require_tty(). `args.yes` (+ `args.by`) is the MCP server's
    non-interactive path: no terminal, no typed confirmation — honoured only with env CECILIA_MCP=1."""
    tty_check = tty_check or require_tty
    yes = bool(getattr(args, "yes", False))
    by = (getattr(args, "by", None) or "mcp").strip() or "mcp"
    if yes and not yes_allowed():
        raise ScopeError(YES_ONLY)
    if yes:
        tty_check = lambda: None                                          # noqa: E731
    plan = Path(args.plan)
    if not plan.is_file():
        raise ScopeError(f"plan not found: {plan}")
    text = plan.read_text(encoding="utf-8-sig")
    blocks = parse_blocks(text)
    if not blocks:
        raise ScopeError("no ```cecilia-scope``` block in that file")
    every = bool(getattr(args, "all", False))
    if every and args.task:
        raise ScopeError("use --all or --task, not both")
    if args.task:
        blocks = [b for b in blocks if b[1].get("task") == args.task]
        if not blocks:
            raise ScopeError(f"no block with task {args.task!r}")
    if len(blocks) > 1 and not every:
        print("Several scope blocks — choose one with --task, or approve them all with --all:")
        for _, b in blocks:
            print("  ", b.get("task"))
        return 1
    scopes = [validate(data) for _, data in blocks]
    tasks = [s["task"] for s in scopes]
    if len(set(tasks)) != len(tasks):
        raise ScopeError("two scope blocks share one task id — " + ", ".join(sorted({t for t in tasks
                                                                                      if tasks.count(t) > 1})))
    rows = lint_plan(text, project_root(root), blocks)
    if print_findings(rows):
        print("Nothing approved.")
        return 1
    if rows:
        print()
    tty_check()
    hours = args.hours or None
    if hours is not None and not 0 < hours <= MAX_HOURS:
        print(f"ERROR: --hours must be between 1 and {MAX_HOURS}", file=sys.stderr)
        return 2
    if every:
        return _approve_all(plan, root, blocks, scopes, hours, ask, by if yes else None)
    raw = blocks[0][0]
    scope = scopes[0]
    hours = hours or scope["expires_hours"]
    print(f"\nPlan: {plan}\nTask: {scope['task']}\nExpires after: {hours} h\n")
    print("Agents will be allowed to EDIT only these paths (plus tensura/ drafts):")
    for w in scope["write"]:
        print("   ", w)
    print("\nLocal commands the plan says it will run (anything else still asks you):")
    for c in scope["commands"] or ["(none listed)"]:
        print("   ", c)
    print("\nEnvironments:", ", ".join(scope["environments"]))
    print("Still never allowed: push/PR without your yes, merge, production, secrets, releases.\n")
    if yes:
        print(f"Confirmed non-interactively by {by} (--yes, Cecilia MCP server).")
    else:
        typed = ask(f"Type the task id to approve ({scope['task']}), anything else cancels: ").strip()
        if typed != scope["task"]:
            print("Cancelled — nothing written.")
            return 1
    rec = build_record(scope, plan, root, raw, by if yes else approver_name(root), hours, non_interactive=yes)
    path = write_record(root, rec)
    print(f"Approved. Written {path.relative_to(root)} (expires {rec['expires_at']}).")
    return 0


def _approve_all(plan: Path, root: Path, blocks, scopes, hours, ask, yes_by=None) -> int:
    print(f"\nPlan: {plan}\nApproving {len(scopes)} scope block(s) in one go:\n")
    for s in scopes:
        h = hours or s["expires_hours"]
        print(f"== {s['task']}  (expires after {h} h, environments: {', '.join(s['environments'])}"
              f"{', worktree ' + s['worktree'] if s.get('worktree') else ''})")
        print("   EDIT only:")
        for w in s["write"]:
            print("     ", w)
        print("   Commands:")
        for c in s["commands"] or ["(none listed)"]:
            print("     ", c)
    print("\nStill never allowed: push/PR without your yes, merge, production, secrets, releases.")
    print("Tasks: " + ", ".join(s["task"] for s in scopes))
    want = f"approve {len(scopes)}"
    if yes_by:
        print(f"Confirmed non-interactively by {yes_by} (--yes, Cecilia MCP server).")
    else:
        typed = ask(f"Type '{want}' to approve all {len(scopes)} tasks above, anything else cancels: ").strip()
        if " ".join(typed.split()).lower() != want:
            print("Cancelled — nothing written.")
            return 1
    who = yes_by or approver_name(root)
    recs = [build_record(s, plan, root, raw, who, hours, non_interactive=bool(yes_by))
            for (raw, _), s in zip(blocks, scopes)]
    paths = [write_record(root, r) for r in recs]
    w1 = max(4, *(len(r["task"]) for r in recs))
    print(f"\n{'TASK':<{w1}}  {'PATHS':>5}  {'CMDS':>4}  {'EXPIRES':<25}  FILE")
    for r, p in zip(recs, paths):
        print(f"{r['task']:<{w1}}  {len(r['write']):>5}  {len(r['commands']):>4}  {r['expires_at']:<25}  "
              f"{p.relative_to(root).as_posix()}")
    print(f"Approved {len(recs)} task(s).")
    return 0


def cmd_lint(plan_arg: str, project_arg=None) -> int:
    """`cecilia_approve.py lint <plan.md>` — findings only, approves nothing; exit 1 on any ERROR."""
    plan = Path(plan_arg)
    if not plan.is_file():
        raise ScopeError(f"plan not found: {plan}")
    text = plan.read_text(encoding="utf-8-sig")
    blocks = parse_blocks(text)
    if not blocks:
        raise ScopeError("no ```cecilia-scope``` block in that file")
    if project_arg:
        proj = Path(project_arg).resolve()
    else:
        proj = None
        for start in (plan.resolve().parent, Path.cwd()):
            try:
                proj = project_root(find_root(start))
                break
            except ScopeError:
                continue
    for _, data in blocks:
        try:
            validate(data)
        except ScopeError as e:
            print(f"ERROR [{data.get('task', '?') if isinstance(data, dict) else '?'}] {e}")
            print(f"\nApproval blocked. {SEND_BACK[0].upper()}{SEND_BACK[1:]}.")
            return 1
    if proj is None:
        print("WARN  [-] no workspace found — project-folder path check skipped (pass --project DIR)")
    rows = lint_plan(text, proj, blocks)
    if print_findings(rows):
        return 1
    print(f"OK — {len(blocks)} scope block(s) lint clean" + (f", {len(rows)} warning(s)." if rows else "."))
    return 0


def cmd_list(root: Path) -> int:
    now = _dt.datetime.now(_dt.timezone.utc)
    rows = []
    for f in sorted((root / ".cecilia" / "approvals").glob("*.json")):
        try:
            a = json.loads(f.read_text(encoding="utf-8-sig"))
            exp = _dt.datetime.fromisoformat(a["expires_at"])
            state = "REVOKED" if a.get("revoked") else ("ACTIVE" if exp > now else "EXPIRED")
            rows.append((a["task"], state, a["expires_at"], a.get("approved_by", "?"), len(a.get("write", []))))
        except Exception as e:
            rows.append((f.stem, f"UNREADABLE ({type(e).__name__})", "", "", 0))
    if not rows:
        print("No approvals.")
    for r in rows:
        print(f"{r[0]:<24} {r[1]:<10} expires {r[2]:<26} by {r[3]:<16} {r[4]} path(s)")
    return 0


def cmd_show(root: Path, task: str) -> int:
    f = root / ".cecilia" / "approvals" / f"{task}.json"
    if not f.is_file():
        raise ScopeError(f"no approval {task}")
    print(f.read_text(encoding="utf-8-sig"))
    return 0


def cmd_revoke(root: Path, task: str) -> int:
    f = root / ".cecilia" / "approvals" / f"{task}.json"
    if not f.is_file():
        raise ScopeError(f"no approval {task}")
    require_tty()
    a = json.loads(f.read_text(encoding="utf-8-sig"))
    a["revoked"] = True
    a["revoked_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    write_record(root, a)
    print(f"Revoked {task}. Agents can no longer edit its paths.")
    return 0



def _utf8_console() -> None:
    """Windows consoles default to a legacy code page; keep output readable and crash-free."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

def main(argv=None) -> int:
    _utf8_console()
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) >= 2 and argv[0] == "lint":
        lp = argparse.ArgumentParser(prog="cecilia_approve.py lint", description="lint a plan; approves nothing")
        lp.add_argument("plan")
        lp.add_argument("--project", help="project folder (default: from the workspace config)")
        largs = lp.parse_args(argv[1:])
        try:
            return cmd_lint(largs.plan, largs.project)
        except ScopeError as e:
            print("ERROR:", e, file=sys.stderr)
            return 2
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", nargs="?", help="plan or brief containing a cecilia-scope block")
    ap.add_argument("--task")
    ap.add_argument("--all", action="store_true", help="approve every cecilia-scope block in the plan at once")
    ap.add_argument("--hours", type=float)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--show")
    ap.add_argument("--revoke")
    ap.add_argument("--yes", action="store_true", help="no typed confirmation — only for the Cecilia MCP server")
    ap.add_argument("--by", help="with --yes: who confirmed (recorded as approved_by)")
    args = ap.parse_args(argv)
    if args.by is not None and not args.yes:
        print("ERROR: --by needs --yes", file=sys.stderr)
        return 2
    if args.yes and not yes_allowed():
        print(f"ERROR: {YES_ONLY}", file=sys.stderr)
        return 2
    if args.yes and (args.list or args.show or args.revoke):
        print("ERROR: --yes applies to approving a plan only", file=sys.stderr)
        return 2
    try:
        root = find_root(Path.cwd())
        if args.list:
            return cmd_list(root)
        if args.show:
            return cmd_show(root, args.show)
        if args.revoke:
            return cmd_revoke(root, args.revoke)
        if not args.plan:
            ap.error("give a plan path, or --list / --show / --revoke")
        return cmd_approve(args, root)
    except ScopeError as e:
        print("ERROR:", e, file=sys.stderr)
        return 2
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled — nothing written.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
