#!/usr/bin/env python3
"""Cecilia v20 host guard — a PreToolUse (and UserPromptSubmit) hook for Claude Code and Antigravity.

It enforces the parts of `core.md` a host can check before a tool runs. The *data* it judges with
(protected paths, secret files, live systems, migrations, git-host tools, MCP verbs…) lives in
`policy.json` next to this file; Cecilia can add entries per project in `.cecilia/config.json` → `guard`.

* local-only (default, `git.local_only`): nothing the agent does leaves the machine — push, PR/MR, remote
  branches, git-host API writes and git-host MCP writes are A4 (denied; the agent prepares the command);
  Cecilia's own files (`.cecilia/`, `tensura/`, Cecilia skills/agents…) can never be staged or committed;
* git flow: edits (edit tools AND shell writes) only on a task branch — never on a protected branch, a
  detached HEAD or outside a git repository; commit/merge/rebase/… on a protected branch are denied, also
  when the same command switched to it first (`git switch develop && git merge x`);
* path profiles (`profiles` in config): per path group the level is fast | standard | ask | controlled |
  deny, combined with the project mode (`.cecilia/mode.json`) — the stricter wins. CONTROLLED needs an
  approved scope (`.cecilia/approvals/*.json`), for edit tools and for shell write targets alike;
* never edits to the guard, config, approvals, host permission/hook/MCP files, the Playwright CLI config,
  `.git/`, or secret files; never reads/copies secret files (any command) or dumps the environment unasked;
* A4 commands (merge to protected, publish/release, production, IAM, secrets, force-push, --no-verify…)
  denied; A3 commands (installs, live systems, deletes, discards, migrations that drop or deploy, running
  packages downloaded from a registry, network writes…) sent to Cecilia to approve;
* tool rules (`tool_rules` in config, Claude Code): e.g. "call context7 before writing code that imports a
  library you have not looked up" — checked against the agent's own transcript; a UserPromptSubmit reminder
  lists the active rules;
* Playwright CLI/MCP: local pages only; installs, other origins, real profiles, `run-code` ask.
* v20 (Claude Code; identity = the hook's `agent_type`; on only when `.cecilia/registry.json` or the v20
  config keys exist): the orchestrator writes only under `<workspace>/tensura/`; a Cecilia role writes only in
  its `lanes` (+ tensura/reports|tasks|backups); an `Agent`/`Task` dispatch of a writer/tester role from
  STANDARD needs a brief header whose WORKFLOW matches the chosen `workflow.json` (ROUND <= fix_loop.max_rounds);
  a role's first write needs its project rules read (brief header RULES=<hash> or a Read of the files);
  `rules/` and `.cecilia/extensions/` are Cecilia's; `cecilia flow|rules add|rm|edit|extension apply` are hers.
* v20.1: the orchestrator writes only its tensura/ files (tasks, decisions, inbox, runs, state, lessons — not
  plans, docs, extensions, reports, votes or review/verdict files); it runs only `cecilia`, Cecilia's scripts,
  read-only tools and integration git (+ `orchestration.orchestrator_commands`) and no MCP tool unless listed in
  `orchestration.orchestrator_mcp`. Any agent: `kubectl get <secrets> -o yaml|json…` asks, written to a file is
  denied; `etcdctl get /registry/secrets…` is denied.
* v20.2 (Antigravity): `call_mcp_tool` is judged as `mcp__<ServerName>__<ToolName>`, `invoke_subagent` /
  `define_subagent` as a dispatch (the orchestrator dispatches only enabled Cecilia roles, never defines ad-hoc
  agents); identity = the ROLE of the brief in the conversation's transcript, else the main agent
  (`antigravity.main_agent`, default the orchestrator; `antigravity.identity: "off"` = 20.1); PreInvocation
  injects a short reminder; A3 = force_ask (`antigravity.ask: "ask"` = plain ask). Both hosts: allowed writes
  under tensura/ are appended to `.cecilia/provenance.jsonl`; `guard.agent_may_run` opens listed human-only
  `cecilia` subcommands (mode, approve, flow, rules add, extension apply, push) to agents.

It is a strong seat belt, not a sandbox: a shell can always find a form a pattern did not foresee (code run
by an interpreter, string-built paths). The real boundary for A4 is that production credentials are never in
the agent session; the push lock (`cecilia_mode.py --push-lock`) blocks pushes whatever form they take.

Usage (the host runs this; stdin = the host's hook JSON, UTF-8):
    cecilia_guard.py --host claude|antigravity
    cecilia_guard.py --explain "<shell command>" [--cwd DIR]    # the decision and the effects, for humans

Fails closed: any internal error (or a missing/invalid policy.json) blocks the tool call. Python 3.9+;
standard library only.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import datetime as _dt
import fnmatch
import json
import os
import posixpath
import re
import shlex
import subprocess
import sys
from pathlib import Path, PurePosixPath

ALLOW, ASK, DENY = None, "ask", "deny"
RANK = {ALLOW: 0, ASK: 1, DENY: 2}
VERSION = "20.2.0"


# --------------------------------------------------------------------------- policy

class PolicyError(Exception):
    pass


def _load_policy() -> dict:
    f = Path(__file__).resolve().with_name("policy.json")
    try:
        p = json.loads(f.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        raise PolicyError(f"policy.json missing or invalid next to the guard ({e}) — re-run the installer") from e
    for key in ("protected_write", "secret_file_regex", "live_tools", "local_only_paths"):
        if key not in p:
            raise PolicyError(f"policy.json lacks '{key}' — re-run the installer")
    return p


try:
    POLICY = _load_policy()
    POLICY_ERROR = ""
except PolicyError as _e:     # judged per call: every hook call is denied with this message
    POLICY, POLICY_ERROR = {}, str(_e)

MERGEABLE = {"live_tools", "deploy_words", "migration_ask", "migration_apply", "protected_write", "local_only_paths",
             "git_host_clis", "mcp_git_host_servers", "env_dumpers", "task_runners", "db_url_vars",
             "git_exec_config_keys", "git_host_api_hosts", "default_code_globs", "secret_dump_clis",
             "secret_resources", "secret_dump_formats"}


def policy(cfg: dict | None = None) -> dict:
    """policy.json plus the project's additions from .cecilia/config.json → guard (lists merged, never removed)."""
    extra = (cfg or {}).get("guard_extra") or {}
    if not extra:
        return POLICY
    p = dict(POLICY)
    for k, v in extra.items():
        if k in MERGEABLE and isinstance(v, list):
            p[k] = list(POLICY.get(k, [])) + [x for x in v if x not in POLICY.get(k, [])]
        elif k == "live_tool_safe" and isinstance(v, dict):
            p[k] = {**POLICY.get(k, {}), **v}
    return p


def _re(key: str, flags=re.I):
    return re.compile(POLICY.get(key, "(?!)"), flags)


SECRET_FILES = _re("secret_file_regex")
SECRET_INLINE = _re("secret_inline_regex")
PROD = _re("prod_regex")
STAGING = _re("staging_regex")
PROTECTED_WRITE = POLICY.get("protected_write", [])
ALWAYS_WRITABLE = POLICY.get("always_writable", ["tensura/**"])
GIT_EXEMPT = POLICY.get("git_exempt", [])
DEFAULT_PROTECTED = POLICY.get("default_protected_branches", ["main", "master", "develop"])
CASE_FOLD = os.name == "nt"   # Windows paths are case-insensitive
VALID_MODES = {"fast", "standard", "controlled"}
LEVELS = {"fast": 0, "standard": 0, "ask": 1, "controlled": 2, "deny": 3}


# --------------------------------------------------------------------------- paths

def glob_to_regex(pattern: str, fold: bool = False) -> re.Pattern:
    """`dir/**` = everything below dir; `*` = within one segment; `?` = one char; `{a,b}` = either."""
    p = pattern.strip()
    p = p[2:] if p.startswith("./") else p
    out, i = "", 0
    while i < len(p):
        if p.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif p.startswith("**", i):
            out += ".*"
            i += 2
        elif p[i] == "*":
            out += "[^/]*"
            i += 1
        elif p[i] == "?":
            out += "[^/]"
            i += 1
        elif p[i] == "{" and "}" in p[i:]:
            j = p.index("}", i)
            out += "(?:" + "|".join(re.escape(x) for x in p[i + 1:j].split(",")) + ")"
            i = j + 1
        else:
            out += re.escape(p[i])
            i += 1
    return re.compile("^" + out + "$", re.I if fold else 0)


def matches(rel: str, patterns) -> bool:
    return any(glob_to_regex(p, CASE_FOLD).match(rel) for p in patterns)


def local_only_match(rel: str, patterns=None) -> bool:
    """gitignore-like: `dir/` = the directory and everything below; `*` within one segment; no `/` = any level."""
    rel = rel.replace("\\", "/").lstrip("/")
    for pat in patterns if patterns is not None else POLICY.get("local_only_paths", []):
        if pat.endswith("/"):
            base = pat.rstrip("/")
            rx = glob_to_regex(base + "/**", CASE_FOLD)
            if rx.match(rel) or glob_to_regex(base, CASE_FOLD).match(rel):
                return True
        elif "/" not in pat:
            if fnmatch.fnmatch(rel.split("/")[-1], pat):
                return True
        elif glob_to_regex(pat, CASE_FOLD).match(rel):
            return True
    return False


def find_root(start: Path) -> Path:
    for d in [start, *start.parents]:
        if (d / ".cecilia").is_dir():
            return d
    return start


# Workspace mode (v19): Cecilia lives in a sidecar folder (`<project>.cecilia/`) and the project folder holds no
# Cecilia file. WORKSPACE is that folder; `root` everywhere below stays the project the code lives in.
WORKSPACE = None


def cdir(root: Path) -> Path:
    """Where `.cecilia/` (config, mode, approvals, log) is: the workspace in workspace mode, else the project."""
    return (WORKSPACE or root) / ".cecilia"


def wt_base(root: Path) -> Path:
    return (WORKSPACE or root) / ".worktrees"


def workspace_project(home: Path):
    """The project a workspace serves (config `workspace.project`), or None for an in-project install."""
    try:
        cfg = json.loads((home / ".cecilia" / "config.json").read_text(encoding="utf-8-sig"))
        proj = (cfg.get("workspace") or {}).get("project") if isinstance(cfg, dict) else None
    except (OSError, ValueError, AttributeError):
        return None
    if not isinstance(proj, str) or not proj.strip():
        return None
    pp = Path(proj)
    if not pp.is_absolute():
        pp = home / pp
    return Path(os.path.normpath(str(pp)))


def resolve_roots(start: Path, workspace=None) -> Path:
    """Set WORKSPACE (or clear it) and return the project root the guard judges code against."""
    global WORKSPACE
    home = Path(os.path.normpath(str(workspace))) if workspace else find_root(start)
    proj = workspace_project(home) if (home / ".cecilia").is_dir() else None
    WORKSPACE = home if proj else None
    return proj or home


def to_rel(path_str: str, cwd: Path, root: Path):
    p = Path(os.path.expanduser(path_str)) if path_str.startswith("~") else Path(path_str)
    if not p.is_absolute():
        p = cwd / p
    p = Path(os.path.normpath(str(p)))
    try:
        rel = p.relative_to(root)
    except ValueError:
        if CASE_FOLD:
            try:
                rel = Path(str(p).lower()).relative_to(Path(str(root).lower()))
            except ValueError:
                return None
        else:
            return None
    return PurePosixPath(rel.as_posix()).as_posix()


def worktree_name(rel: str):
    parts = rel.split("/")
    if len(parts) > 2 and (parts[0].lower() if CASE_FOLD else parts[0]) == ".worktrees":
        return parts[1]
    return None


def strip_worktree(rel: str) -> str:
    parts = rel.split("/")
    if len(parts) > 2 and (parts[0].lower() if CASE_FOLD else parts[0]) == ".worktrees":
        return "/".join(parts[2:])
    return rel


def load_mode(root: Path) -> str:
    """Return persistent project mode. Missing means STANDARD; malformed fails safer as CONTROLLED."""
    f = cdir(root) / "mode.json"
    if not f.is_file():
        return "standard"
    try:
        mode = json.loads(f.read_text(encoding="utf-8-sig")).get("mode", "standard")
    except Exception:
        return "controlled"
    return mode if mode in VALID_MODES else "controlled"


DEFAULT_PROFILES = POLICY.get("default_profiles", [])


V20_KEYS = ("lanes", "orchestration", "rules", "flow", "fix_loop")
ORCHESTRATOR = "cecilia-orchestrator"
SAFE_REL = re.compile(r"^[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*$")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")


def _v20_view(cfg: dict) -> dict:
    """The v20 keys the guard reads (lanes, orchestration, fix_loop, rules, flow), with safe defaults."""
    lanes = cfg.get("lanes") if isinstance(cfg.get("lanes"), dict) else {}
    lanes = {k: [g for g in v if isinstance(g, str) and g.strip()] for k, v in lanes.items() if isinstance(v, list)}
    orch = cfg.get("orchestration") if isinstance(cfg.get("orchestration"), dict) else {}
    fix = cfg.get("fix_loop") if isinstance(cfg.get("fix_loop"), dict) else {}
    rules = cfg.get("rules") if isinstance(cfg.get("rules"), dict) else {}
    rmax = fix.get("max_rounds", 3)
    rdir = rules.get("dir", "rules")
    flow = cfg.get("flow", "personal")
    team = ((cfg.get("flows") or {}).get("team") or {}) if isinstance(cfg.get("flows"), dict) else {}
    dexp = team.get("docs_export") if isinstance(team, dict) else ""
    docs_export = dexp.strip("/") if isinstance(dexp, str) and dexp.strip("/") and SAFE_REL.match(dexp.strip("/")) \
        and ".." not in dexp.split("/") else ""
    strs = lambda v: [x.strip() for x in v if isinstance(x, str) and x.strip()] if isinstance(v, list) else []  # noqa: E731
    agy = cfg.get("antigravity") if isinstance(cfg.get("antigravity"), dict) else {}
    main_agent = agy.get("main_agent", ORCHESTRATOR)
    return {"lanes": lanes, "docs_export": docs_export,
            # 20.2: who the Antigravity main agent / subagents are (read from the transcript), and how A3 asks.
            "antigravity": {"identity": "off" if agy.get("identity") == "off" else "transcript",
                            "main_agent": main_agent.strip() if isinstance(main_agent, str) else ORCHESTRATOR,
                            "ask": "ask" if agy.get("ask") == "ask" else "force_ask"},
            "orchestration": {"orchestrator_writes": str(orch.get("orchestrator_writes") or "tensura-only"),
                              "workflow_required_from": str(orch.get("workflow_required_from") or "standard").lower(),
                              "orchestrator_commands": strs(orch.get("orchestrator_commands")),
                              "orchestrator_mcp": strs(orch.get("orchestrator_mcp"))},
            "fix_loop": {"max_rounds": rmax if isinstance(rmax, int) and not isinstance(rmax, bool) and rmax >= 0
                         else 3},
            "rules": {"enforce": str(rules.get("enforce") or "gate"),
                      "dir": rdir if isinstance(rdir, str) and SAFE_REL.match(rdir) and ".." not in rdir.split("/")
                      else "rules"},
            "flow": flow if isinstance(flow, str) and SAFE_ID.match(flow) else "personal",
            "v20": any(k in cfg for k in V20_KEYS)}


def default_config_view() -> dict:
    return {"roles": {"cecilia-ui": False}, "ui": {"design_writes": "ask"},
            "git": {"require_task_branch": True, "protected": list(DEFAULT_PROTECTED), "local_only": True},
            "profiles": DEFAULT_PROFILES, "tool_rules": [], "guard_extra": {}, **_v20_view({})}


def load_config(root: Path | None) -> dict:
    """`.cecilia/config.json` as the guard sees it. Missing file = defaults. A present file is taken literally
    for roles (missing or not `true` = off). Malformed = the defaults (cecilia-ui off, writes ask)."""
    default = default_config_view()
    if root is None:
        return default
    f = cdir(root) / "config.json"
    if not f.is_file():
        return default
    try:
        cfg = json.loads(f.read_text(encoding="utf-8-sig"))
        if not isinstance(cfg, dict):
            raise ValueError("not an object")
    except Exception:
        return default
    roles = cfg.get("roles") if isinstance(cfg.get("roles"), dict) else {}
    ui = cfg.get("ui") if isinstance(cfg.get("ui"), dict) else {}
    git = cfg.get("git") if isinstance(cfg.get("git"), dict) else {}
    protected = git.get("protected")
    if not (isinstance(protected, list) and all(isinstance(b, str) and b.strip() for b in protected)):
        protected = list(DEFAULT_PROTECTED)
    profiles = cfg.get("profiles", DEFAULT_PROFILES)
    if not isinstance(profiles, list):
        profiles = DEFAULT_PROFILES
    profiles = [p for p in profiles if isinstance(p, dict) and isinstance(p.get("paths"), list)
                and p.get("level") in LEVELS]
    rules = cfg.get("tool_rules") if isinstance(cfg.get("tool_rules"), list) else []
    extra = cfg.get("guard") if isinstance(cfg.get("guard"), dict) else {}
    return {"roles": {k: v is True for k, v in roles.items()},
            "ui": {"design_writes": "allow" if ui.get("design_writes") == "allow" else "ask"},
            "git": {"require_task_branch": git.get("require_task_branch") is not False, "protected": protected,
                    "local_only": git.get("local_only") is not False},
            "profiles": profiles, "tool_rules": [r for r in rules if isinstance(r, dict)], "guard_extra": extra,
            **_v20_view(cfg)}


# --------------------------------------------------------------------------- git

def git_dir_for(start: Path):
    """The .git directory for `start` (walking up); follows the `gitdir:` file of a worktree."""
    for d in [start, *start.parents]:
        g = d / ".git"
        if g.is_dir():
            return g
        if g.is_file():
            try:
                text = g.read_text(encoding="utf-8-sig").strip()
            except OSError:
                return None
            if text.startswith("gitdir:"):
                target = Path(text[len("gitdir:"):].strip())
                return target if target.is_absolute() else (d / target)
            return None
    return None


def current_branch(start: Path):
    """Branch name, "(detached)", or None when `start` is not inside a git repository."""
    g = git_dir_for(start)
    if g is None:
        return None
    try:
        head = (g / "HEAD").read_text(encoding="utf-8-sig").strip()
    except OSError:
        return None
    if head.startswith("ref:"):
        ref = head[4:].strip()
        return ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ref
    return "(detached)"


def branch_protected(branch: str, patterns) -> bool:
    return any(glob_to_regex(p).match(branch) for p in patterns)


def git_block_reason(start: Path, cfg: dict, branch=None):
    """Why an edit under `start` is not allowed by git flow, or None."""
    if not cfg["git"]["require_task_branch"]:
        return None
    branch = branch or current_branch(start)
    if branch is None:
        return ("git flow: this project is not a git repository. Initialise it (`git init`, first commit) "
                "and create a task branch before editing — or Cecilia sets git.require_task_branch false.")
    if branch == "(detached)":
        return "git flow: HEAD is detached. Create a task branch (`git switch -c feature/<TASK>-<desc>`) first."
    if branch_protected(branch, cfg["git"]["protected"]):
        return (f"git flow: '{branch}' is a protected branch. Create a task branch from it first — "
                f"`git switch -c feature/<TASK>-<desc>` (git.md §2) — then edit there.")
    return None


def role_enabled(cfg: dict, name: str) -> bool:
    return cfg.get("roles", {}).get(name) is True


def load_scopes(root: Path, now=None):
    now = now or _dt.datetime.now(_dt.timezone.utc)
    active, inactive = [], []
    for f in sorted((cdir(root) / "approvals").glob("*.json")):
        try:
            a = json.loads(f.read_text(encoding="utf-8-sig"))
            exp = _dt.datetime.fromisoformat(a["expires_at"].replace("Z", "+00:00"))
            ok = (not a.get("revoked")) and exp > now and isinstance(a.get("write"), list)
        except Exception:  # an unreadable approval is simply not an approval
            inactive.append(f.stem)
            continue
        (active if ok else inactive).append(a if ok else f.stem)
    return active, inactive


def profile_for(rel: str, cfg: dict):
    for p in cfg.get("profiles", []):
        if matches(rel, p["paths"]):
            return p
    return None


# --------------------------------------------------------------------------- v20: lanes, workflow gate, rules

AGENT = ""              # Claude Code: the hook's `agent_type`; Antigravity: agy_identity() (transcript brief ROLE,
                        # else antigravity.main_agent); "" = main thread without an agent / identity off
WRITES_SEEN: list = []  # (path, cwd) inside the project/workspace this hook call writes (rules gate, provenance)
BRIEF_KEYS = ("TASK", "ROLE", "LENS", "UNIT", "WORKFLOW", "ROUND", "RULES")
BRIEF_RX = re.compile(r"\[cecilia-brief ([^\]\r\n\"\\]*)\]")
MODE_ORDER = {"fast": 0, "standard": 1, "controlled": 2}


def ws_home(root: Path) -> Path:
    """The workspace: the sidecar folder in workspace mode, else the project itself."""
    return WORKSPACE or root


def short(name: str) -> str:
    return name[len("cecilia-"):] if name.startswith("cecilia-") else name


def rules_hash(ws: Path, role, flow: str, lens) -> str:
    """DESIGN-V20 section 3 — same algorithm in workflow.py, the guard and cecilia_check (copied, not imported)."""
    import hashlib
    files = ["rules/_project.md"] + ([f"rules/roles/{short(role)}.md"] if role else []) + \
            [f"rules/flows/{flow}.md"] + ([f"rules/lenses/{lens}.md"] if lens else [])
    h = hashlib.sha256()
    for rel in files:
        p = ws / rel
        if p.is_file():
            h.update(rel.encode() + b"\n" + p.read_bytes() + b"\n")
    return h.hexdigest()[:12]


def parse_brief(text: str):
    """`[cecilia-brief TASK=.. ROLE=.. LENS=.. UNIT=.. WORKFLOW=.. ROUND=.. RULES=..]` -> dict, or None."""
    m = BRIEF_RX.fullmatch(text.strip()) if text else None
    if not m:
        return None
    fields = {}
    for part in m.group(1).split():
        k, eq, v = part.partition("=")
        if not eq or k not in BRIEF_KEYS or k in fields or not v:
            return None
        fields[k] = v
    if set(fields) != set(BRIEF_KEYS) or not re.fullmatch(r"\d{1,3}", fields["ROUND"]):
        return None
    return fields


def load_registry(root: Path):
    """`<workspace>/.cecilia/registry.json` (tools/registry.py compile()), or None when absent/unreadable."""
    f = cdir(root) / "registry.json"
    try:
        reg = json.loads(f.read_text(encoding="utf-8-sig")) if f.is_file() else None
    except (OSError, ValueError):
        return None
    return reg if isinstance(reg, dict) else None


def _reg_roles(reg) -> dict:
    roles = (reg or {}).get("roles")
    if isinstance(roles, list):
        roles = {r.get("name"): r for r in roles if isinstance(r, dict) and r.get("name")}
    return {k: v for k, v in roles.items() if isinstance(v, dict)} if isinstance(roles, dict) else {}


def role_view(root: Path, cfg: dict, agent: str):
    """What v20 knows about `agent`: {"name","agent_type","lane","orchestrator"}; None = not a Cecilia role or the
    v20 gates are off (no registry snapshot and no v20 config) — v19.2 behaviour."""
    if not agent:
        return None
    reg = load_registry(root)
    roles = _reg_roles(reg)
    info = roles.get(agent)
    at = str((info or {}).get("agent_type") or "")
    if agent == ORCHESTRATOR or at == "orchestrator":
        if reg is None and not cfg.get("v20"):
            return None
        return {"name": agent, "agent_type": "orchestrator", "lane": None, "orchestrator": True}
    lanes = cfg.get("lanes") or {}
    if info is None and agent not in lanes:
        return None
    lane = lanes.get(agent) if agent in lanes else (info or {}).get("lane")
    if not isinstance(lane, list):
        writes = ((reg or {}).get("agent_types") or {}).get(at, {}) if at else {}
        lane = [] if isinstance(writes, dict) and writes.get("writes") == "none" else None
    return {"name": agent, "agent_type": at, "lane": lane, "orchestrator": False}


def _lane_targets(path_str: str, cwd: Path, root: Path):
    """(workspace-relative path when it is under tensura/, project-relative code path) — either may be None."""
    ws = ws_home(root)
    wrel = to_rel(path_str, cwd, ws)
    tens = wrel if wrel and (wrel.split("/")[0].lower() if CASE_FOLD else wrel.split("/")[0]) == "tensura" else None
    if WORKSPACE is not None and wrel and wrel.split("/")[0] == ".worktrees" and len(wrel.split("/")) > 2:
        code = strip_worktree(wrel)
    else:
        prel = to_rel(path_str, cwd, root)
        code = strip_worktree(prel) if prel not in {None, "", "."} else None
    return tens, code


def _lane_hit(glob: str, tens, code) -> bool:
    g = re.sub(r"<[A-Za-z_]+>|\{[A-Z_]+\}", "*", glob.strip())
    target = tens if g.startswith("tensura/") else code
    return target is not None and matches(target, [g])


def in_lane(lane: list, tens, code, implicit_extra=()) -> bool:
    """Implicit lanes (policy lane_implicit + the registry's implicit_lane) always; then includes minus `!` excludes."""
    implicit = list(POLICY.get("lane_implicit", ["tensura/reports/**", "tensura/tasks/**", "tensura/backups/**"]))
    implicit += [g for g in implicit_extra if isinstance(g, str) and not g.startswith("!")]
    if any(_lane_hit(g, tens, code) for g in implicit):
        return True
    inc = [g for g in lane if not g.startswith("!")]
    exc = [g[1:] for g in lane if g.startswith("!")]
    return any(_lane_hit(g, tens, code) for g in inc) and not any(_lane_hit(g, tens, code) for g in exc)


# v20.1: the orchestrator's own tensura/ files. Used when no registry snapshot says otherwise; the registry lane
# (registry/roles/cecilia-orchestrator.json) and a config `lanes` entry can only narrow it (all must admit).
ORCH_LANE = [
    "tensura/tasks/**", "tensura/decisions/**", "tensura/inbox/**", "tensura/runs/**", "tensura/state.md",
    "tensura/lessons*.md",
    "tensura/reports/*/orchestration-*.md",                   # its run log (registry `report`)
    "tensura/reports/*/panel/**/inputs.md", "tensura/reports/*/panel/**/r?-all.md",
    "tensura/reports/*/panel/**/map.md",                      # panel inputs + anonymized merges (panel-run.md)
    "!tensura/tasks/**/votes/**", "!tensura/tasks/**/review*", "!tensura/tasks/**/judge*",
    "!tensura/tasks/**/verdict*",
]
ORCH_OWNERS = [       # (glob, who owns it) — for the deny message
    ("tensura/plans/**", "cecilia-plan"), ("tensura/docs/**", "cecilia-discovery / cecilia-design"),
    ("tensura/extensions/**", "cecilia-extend"), ("tensura/tasks/**/votes/**", "cecilia-review (the voters)"),
    ("tensura/tasks/**/review*", "cecilia-review"), ("tensura/tasks/**/judge*", "cecilia-review (the judge)"),
    ("tensura/tasks/**/verdict*", "cecilia-review (the judge)"),
    ("tensura/reports/*/panel/**", "cecilia-review (panel reviewers / judge)"),
    ("tensura/reports/**", "the role whose report it is"),
]


def _orch_admits(lane: list, tens: str) -> bool:
    """Includes minus `!` excludes, without the implicit role lanes (reports/, backups/)."""
    inc = [g for g in lane if not g.startswith("!")]
    exc = [g[1:] for g in lane if g.startswith("!")]
    return any(_lane_hit(g, tens, None) for g in inc) and not any(_lane_hit(g, tens, None) for g in exc)


def _orch_lanes(root: Path, cfg: dict) -> list:
    """The built-in orchestrator lane, plus the registry's and the config's lane when they are lists."""
    lanes = [ORCH_LANE]
    info = _reg_roles(load_registry(root)).get(AGENT) or _reg_roles(load_registry(root)).get(ORCHESTRATOR) or {}
    if isinstance(info.get("lane"), list) and info["lane"]:
        lanes.append([g for g in info["lane"] if isinstance(g, str)])
    conf = (cfg.get("lanes") or {}).get(AGENT)
    if isinstance(conf, list) and conf:
        lanes.append(conf)
    return lanes


def _orch_owner(tens: str) -> str:
    for glob, who in ORCH_OWNERS:
        if _lane_hit(glob, tens, None):
            return who
    return "another role"


def lane_check(path_str: str, cwd: Path, root: Path, via: str = "edit"):
    """v20 decisions 1 and 2: the orchestrator writes only under <ws>/tensura/; a role only in its lane."""
    if not AGENT:
        return ALLOW, ""
    cfg = load_config(root)
    rv = role_view(root, cfg, AGENT)
    if rv is None:
        return ALLOW, ""
    tens, code = _lane_targets(path_str, cwd, root)
    if tens is None and code is None:
        return ALLOW, ""          # outside project and workspace: judged by decide_write (edit) or not ours (shell)
    shown = tens or code
    if rv["orchestrator"]:
        if cfg["orchestration"]["orchestrator_writes"] != "tensura-only":
            return ALLOW, ""
        if tens is None:
            return DENY, (f"orchestrator lane: '{shown}' is outside tensura/. The orchestrator only orchestrates - "
                          "dispatch it to the right role with a brief (workflow.py brief), do not do the work "
                          "yourself.")
        if all(_orch_admits(lane, tens) for lane in _orch_lanes(root, cfg)):
            return ALLOW, ""
        return DENY, (f"orchestrator lane: '{tens}' belongs to {_orch_owner(tens)} - dispatch it with a brief "
                      "(workflow.py brief), do not write it yourself. The orchestrator writes only "
                      "tensura/tasks/** (not votes/ or review/verdict files), tensura/decisions/**, "
                      "tensura/inbox/**, tensura/runs/**, tensura/state.md, tensura/lessons*.md and its run log.")
    lane = rv["lane"]
    reg = load_registry(root)
    extra = list((reg or {}).get("implicit_lane") if isinstance((reg or {}).get("implicit_lane"), list) else [])
    kind = str((_reg_roles(reg).get(AGENT) or {}).get("kind") or "")
    if cfg.get("flow") == "team" and cfg.get("docs_export") and kind in {"docs", "design"}:
        extra.append(cfg["docs_export"] + "/**")     # team flow: docs/ADR exported into the project's docs folder
    if lane is None or in_lane(lane, tens, code, extra):
        return ALLOW, ""
    owner = ""
    reg_roles = _reg_roles(reg)
    for name in sorted(set(cfg.get("lanes") or {}) | set(reg_roles)):
        other = (cfg.get("lanes") or {}).get(name, reg_roles.get(name, {}).get("lane"))
        if name != AGENT and isinstance(other, list) and other and in_lane(other, tens, code) and \
                name != ORCHESTRATOR:
            owner = name
            break
    lane_txt = ", ".join(lane[:5]) + (" ..." if len(lane) > 5 else "") if lane else "reports only"
    return DENY, (f"lane: '{shown}' is outside {AGENT}'s lane ({lane_txt}). Do not write it: stop and end your "
                  f"report with 'HANDOFF: needs {owner or '<role>'} - <what>'; the orchestrator dispatches it.")


AGY_DISPATCH_MSG = ("dispatch only Cecilia roles: invoke_subagent TypeName=cecilia-<role> with the brief from "
                    "workflow.py brief; if the role cannot be invoked, STOP and report — never do the work yourself")


def _dispatchable(sub: str, reg, cfg: dict) -> bool:
    """Antigravity: an enabled cecilia-* role (config `roles`, else the registry's default_on) or an extension role
    in the registry snapshot — never the orchestrator itself, never an unknown/built-in agent."""
    if not sub or sub == ORCHESTRATOR:
        return False
    roles = _reg_roles(reg)
    info = roles.get(sub)
    if info is not None and str(info.get("agent_type") or "") == "orchestrator":
        return False
    if sub in (cfg.get("roles") or {}):
        return cfg["roles"][sub] is True
    if info is not None:
        return info.get("default_on", True) is not False
    return reg is None and sub.startswith("cecilia-") and bool(SAFE_ID.match(sub))


def decide_dispatch(ti: dict, root: Path):
    """v20 decision 3: the workflow gate on Agent/Task calls (Claude Code) and invoke_subagent / define_subagent
    (Antigravity, normalised by extract() to {"subagent_type","prompt","_host","_tool"})."""
    if POLICY_ERROR:
        return DENY, POLICY_ERROR
    sub = str(ti.get("subagent_type") or "")
    reg = load_registry(root)
    if ti.get("_host") == "antigravity":
        cfg = load_config(root)
        if _is_orchestrator(root, cfg) and (ti.get("_tool") == "define_subagent"
                                            or not _dispatchable(sub, reg, cfg)):
            what = "define_subagent (an ad-hoc agent)" if ti.get("_tool") == "define_subagent" else \
                f"'{sub or '?'}' is not an enabled Cecilia role"
            return DENY, f"orchestrator: {what} - {AGY_DISPATCH_MSG}"
    info = _reg_roles(reg).get(sub)
    gated = POLICY.get("workflow_gated_agent_types", ["writer", "tester"])
    if reg is None or info is None or info.get("agent_type") not in gated:
        return ALLOW, ""
    cfg = load_config(root)
    lane = (cfg.get("lanes") or {}).get(sub, info.get("lane"))
    if isinstance(lane, list) and lane and all(isinstance(g, str) and g.lstrip("!").startswith("tensura/")
                                               for g in lane):
        return ALLOW, ""      # plan/discovery/design write only tensura/: they prepare the options, not gated
    mode = load_mode(root)
    req = cfg["orchestration"]["workflow_required_from"]
    if req not in MODE_ORDER or MODE_ORDER.get(mode, 2) < MODE_ORDER[req]:
        return ALLOW, ""
    prompt = str(ti.get("prompt") or "").lstrip("\ufeff")
    first = prompt.lstrip().splitlines()[0] if prompt.strip() else ""
    hdr = parse_brief(first)
    fix = "run `workflow.py options`, let Cecilia choose, `workflow.py choose`, then build the brief with `workflow.py brief`"
    if hdr is None:
        return DENY, (f"workflow gate ({mode.upper()}): dispatching {sub} needs a brief whose first line is "
                      "[cecilia-brief TASK=.. ROLE=.. LENS=.. UNIT=.. WORKFLOW=.. ROUND=.. RULES=..] - " + fix + ".")
    if hdr["ROLE"] != sub:
        return DENY, f"workflow gate: the brief is for ROLE={hdr['ROLE']} but it is sent to {sub} - rebuild the brief."
    rmax = cfg["fix_loop"]["max_rounds"]
    if int(hdr["ROUND"]) > rmax:
        return DENY, (f"fix loop: ROUND={hdr['ROUND']} is past fix_loop.max_rounds ({rmax}). Stop fixing and give "
                      "Cecilia options (accept, change scope, take over).")
    if not SAFE_ID.match(hdr["TASK"]):
        return DENY, f"workflow gate: TASK={hdr['TASK']!r} is not a valid task id."
    wf_file = ws_home(root) / "tensura" / "tasks" / hdr["TASK"] / "workflow.json"
    try:
        wf = json.loads(wf_file.read_text(encoding="utf-8-sig")) if wf_file.is_file() else None
    except (OSError, ValueError):
        wf = None
    if not isinstance(wf, dict) or not wf.get("chosen") or not wf.get("hash"):
        return DENY, (f"workflow gate ({mode.upper()}): no chosen workflow for task {hdr['TASK']} "
                      f"(tensura/tasks/{hdr['TASK']}/workflow.json) - {fix}.")
    if isinstance(wf.get("option"), dict):
        import hashlib
        opts = {hashlib.sha256(json.dumps(wf["option"], sort_keys=True, separators=(",", ":"), ensure_ascii=a)
                               .encode("utf-8")).hexdigest()[:12] for a in (True, False)}
        if str(wf["hash"]) not in opts:
            return DENY, (f"workflow gate: tensura/tasks/{hdr['TASK']}/workflow.json was changed after it was "
                          "chosen (hash mismatch) - Cecilia chooses again with `workflow.py choose`.")
    if hdr["WORKFLOW"] != str(wf["hash"]):
        return DENY, (f"workflow gate: brief WORKFLOW={hdr['WORKFLOW']} does not match the chosen workflow "
                      f"({wf['hash']}) of task {hdr['TASK']} - rebuild the brief with `workflow.py brief`.")
    return ALLOW, ""


def check_rules_gate(data: dict, root: Path):
    """v20 decision 4: a role's first write needs its project rules read — its brief header with RULES=<current
    hash> in the transcript, or a Read of each rules file that exists. Unreadable transcript -> allow."""
    if not AGENT:
        return ALLOW, ""
    cfg = load_config(root)
    rv = role_view(root, cfg, AGENT)
    if rv is None or rv["orchestrator"] or cfg["rules"]["enforce"] != "gate":
        return ALLOW, ""
    ws, flow = ws_home(root), cfg["flow"]
    files = [f"rules/_project.md", f"rules/roles/{short(AGENT)}.md", f"rules/flows/{flow}.md"]
    existing = [f for f in files if (ws / f).is_file()]
    if not existing:
        return ALLOW, ""
    blobs = _transcript_blobs(data)
    if not blobs:
        return ALLOW, ""
    for blob in blobs:
        for m in BRIEF_RX.finditer(blob):
            hdr = parse_brief(m.group(0))
            if hdr and hdr["ROLE"] == AGENT:
                lens = hdr["LENS"] if hdr["LENS"] not in {"-", "none"} and SAFE_ID.match(hdr["LENS"]) else None
                if hdr["RULES"] == rules_hash(ws, AGENT, flow, lens):
                    return ALLOW, ""
    reads = [c.replace("\\\\", "/") for c in _tool_calls(blobs, ["Read", "view_file"])]
    if all(any(f.lower() in c for c in reads) for f in existing):
        return ALLOW, ""
    return DENY, (f"rules gate: read your project rules before your first write - {', '.join(existing)} "
                  f"(or work from a brief whose header has RULES={rules_hash(ws, AGENT, flow, None)}); "
                  "follow them, then retry.")


WIN_ALIAS = re.compile(r"(:|[. ]$|^[^.~]{1,6}~\d+(\.[^.]{0,3})?$)")   # stream, trailing dot/space, 8.3 name


def decide_write(path_str: str, cwd: Path, root: Path, now=None, via: str = "edit", branch=None):
    """Judge one written path (see _decide_write_sym), then the v20 lane of the agent that writes it."""
    d, r = _decide_write_sym(path_str, cwd, root, now, via, branch)
    if AGENT and d != DENY:
        ld, lr = lane_check(path_str, cwd, root, via)
        if RANK[ld] > RANK[d]:
            d, r = ld, lr
    if d != DENY:
        tens, code = _lane_targets(path_str, cwd, root)
        if tens is not None or code is not None:
            WRITES_SEEN.append((path_str, cwd))      # (path, the cwd it is relative to): rules gate + provenance
    return d, r


def _decide_write_sym(path_str: str, cwd: Path, root: Path, now=None, via: str = "edit", branch=None, _real=False):
    """Judge one written path. via="edit": the host's edit tools. via="shell": a write target a shell command
    names — a path outside the project is not this guard's business there (/dev/null, /tmp…).
    A path that goes through a symlink is judged twice — as written and as resolved — and the stricter wins."""
    global WORKSPACE
    d, r = _decide_write(path_str, cwd, root, now, via, branch)
    if _real or d == DENY:
        return d, r
    try:
        p = Path(os.path.expanduser(path_str)) if path_str.startswith("~") else Path(path_str)
        p = p if p.is_absolute() else cwd / p
        real = os.path.realpath(str(p))
        same = os.path.normcase(os.path.normpath(str(p))) == os.path.normcase(real)
    except (OSError, ValueError):
        return d, r
    if same:
        return d, r
    saved = WORKSPACE
    try:
        WORKSPACE = Path(os.path.realpath(str(saved))) if saved is not None else None
        d2, r2 = _decide_write(real, Path(os.path.realpath(str(cwd))), Path(os.path.realpath(str(root))), now, via,
                               branch)
    finally:
        WORKSPACE = saved
    if RANK[d2] > RANK[d]:
        return d2, f"(through a symlink to {real}) {r2}"
    return d, r


def _is_rules_path(rel: str, cfg: dict) -> bool:
    """Is `rel` (workspace-relative) inside the project rules folder (`rules/`, or config rules.dir)?"""
    low = rel.lower() if CASE_FOLD else rel
    for d in {"rules", cfg.get("rules", {}).get("dir", "rules")}:
        d = d.lower() if CASE_FOLD else d
        if low == d or low.startswith(d + "/"):
            return True
    return False


def _rules_msg(rel: str) -> str:
    what = "extension" if ".cecilia/extensions" in rel.lower() else "project rules"
    return (f"'{rel}' is a Cecilia {what} file - only Cecilia changes it ({'cecilia extension apply' if what == 'extension' else 'cecilia rules add|rm|edit'}"
            " in her own terminal). Propose the change in your report instead.")


def _decide_write(path_str: str, cwd: Path, root: Path, now=None, via: str = "edit", branch=None):
    rel = None
    if WORKSPACE is not None:
        wrel = to_rel(path_str, cwd, WORKSPACE)
        if wrel is not None and wrel not in {"", "."}:
            first = wrel.split("/")[0].lower() if CASE_FOLD else wrel.split("/")[0]
            if first == "tensura":
                if SECRET_FILES.search(wrel):
                    return DENY, f"'{wrel}' looks like a secret file. Agents never write secrets (A4)."
                return ALLOW, ""                       # A1: the role's own docs and reports
            if first == ".worktrees" and len(wrel.split("/")) > 2:
                rel = wrel                             # a worktree of the project, kept in the workspace
            elif _is_rules_path(wrel, load_config(root)) or wrel.lower().startswith(".cecilia/extensions"):
                return DENY, _rules_msg(wrel)
            else:
                return DENY, (f"'{wrel}' is a Cecilia workspace file (skills, agents, hooks, config, approvals). "
                              "Only Cecilia changes these — propose the change instead.")
    if rel is None:
        rel = to_rel(path_str, cwd, root)
        if rel is not None and WORKSPACE is not None and rel not in {"", "."} and local_only_match(rel):
            return DENY, (f"'{rel}' is a Cecilia path, and in workspace mode the project holds none — write docs and "
                          f"reports to {WORKSPACE / 'tensura'} instead.")
    if rel is None:
        if via == "shell":
            return ALLOW, ""
        where = " or its workspace's tensura/" if WORKSPACE is not None else ""
        return DENY, f"'{path_str}' is outside the project{where} — agents write only inside it."
    if rel in {"", "."}:
        return ALLOW, ""
    if CASE_FOLD and any(WIN_ALIAS.search(part) for part in rel.split("/") if part not in {"", ".", ".."}):
        return DENY, (f"'{path_str}' uses a Windows path alias (stream ':', trailing dot/space or 8.3 short "
                      "name) — write to the plain path instead.")
    inner = strip_worktree(rel)
    cfg = load_config(root)
    if WORKSPACE is None and rel == inner and (
            rel.lower().startswith(".cecilia/extensions") or (_is_rules_path(rel, cfg) and (
                cfg.get("v20") or (root / cfg["rules"]["dir"] / "_project.md").is_file()))):
        return DENY, _rules_msg(rel)
    for candidate in {rel, inner}:
        if matches(candidate, PROTECTED_WRITE):
            return DENY, (f"'{rel}' is a protected file (guard, approvals, host permissions, git internals). "
                          "Only Cecilia changes these — propose the change instead.")
        if SECRET_FILES.search(candidate):
            return DENY, f"'{rel}' looks like a secret file. Agents never write secrets (A4)."
    if not matches(inner, GIT_EXEMPT):
        wt = worktree_name(rel)
        start = wt_base(root) / wt if wt and (wt_base(root) / wt).exists() else root
        why = git_block_reason(start, cfg, branch if not wt else None)
        if why:
            return DENY, why
    if matches(inner, ALWAYS_WRITABLE):
        return ALLOW, ""
    mode = load_mode(root)
    prof = profile_for(inner, cfg)
    level = max(LEVELS[mode], LEVELS[prof["level"]] if prof else 0)
    if level == LEVELS["deny"]:
        return DENY, f"'{inner}' is in profile '{prof['name']}' set to deny — only Cecilia changes it."
    if level == 0:
        return ALLOW, ""
    scopes, _ = load_scopes(root, now)
    wt = worktree_name(rel)
    for scope in scopes:
        bound = scope.get("worktree")
        if bound and bound != wt:
            continue          # a worktree-bound scope only allows writes inside that worktree
        if matches(inner, scope["write"]):
            return ALLOW, ""
    if level == LEVELS["ask"]:
        return ASK, (f"'{inner}' is in profile '{prof['name']}' (strict paths: CI, containers, IaC, migrations) — "
                     "Cecilia approves this edit (A3), or approves a cecilia-scope that covers it.")
    names = ", ".join(scope["task"] for scope in scopes) or "none"
    where = f"profile '{prof['name']}' is CONTROLLED" if prof and LEVELS[prof["level"]] == level else "CONTROLLED mode"
    return DENY, (f"{where}: '{inner}' is not inside any approved scope (active: {names}). "
                  "Stop and ask Cecilia for a scope change (G2) — do not try another way to write it.")


# --------------------------------------------------------------------------- commands: parsing

WRAPPERS = {"sudo", "doas", "env", "timeout", "time", "nice", "nohup", "stdbuf", "command", "builtin", "noglob", "xargs",
            "exec", "if", "then", "do", "else", "elif", "while", "until", "!", "foreach-object", "%",
            "invoke-command", "icm", "start-job", "start-threadjob", "try", "finally"}
WRAPPER_VALUE_OPTS = {
    "sudo": {"-u", "-g", "-h", "-p", "-U", "-C", "-D", "-r", "-t", "--user", "--group", "--host", "--prompt", "--chdir"},
    "doas": {"-u", "-C"}, "env": {"-u", "--unset", "-C", "--chdir"}, "nice": {"-n", "--adjustment"},
    "timeout": {"-s", "--signal", "-k", "--kill-after"}, "exec": {"-a"}, "stdbuf": {"-i", "-o", "-e"},
    "time": {"-f", "-o", "--format", "--output"},
    "xargs": {"-n", "-I", "-i", "-P", "-L", "-l", "-d", "-E", "-e", "-s", "-a", "--max-args", "--replace",
              "--max-procs", "--delimiter", "--arg-file", "--max-lines"},
}
EXE_SUFFIXES = (".exe", ".cmd", ".bat", ".ps1", ".com")
ALIASES = {"remove-item": "rm", "ri": "rm", "del": "rm", "erase": "rm", "rd": "rmdir",
           "get-content": "cat", "gc": "cat", "type": "cat", "select-string": "grep", "sls": "grep",
           "invoke-expression": "eval", "iex": "eval",
           "invoke-webrequest": "curl", "iwr": "curl", "invoke-restmethod": "curl", "irm": "curl",
           "copy-item": "cp", "cpi": "cp", "copy": "cp", "xcopy": "cp", "robocopy": "cp",
           "move-item": "mv", "mi": "mv", "move": "mv", "rename-item": "mv", "rni": "mv", "ren": "mv",
           "out-file": "tee", "add-content": "tee", "ac": "tee", "set-content": "tee", "tee-object": "tee",
           "new-item": "touch", "ni": "touch", "set-location": "cd", "sl": "cd", "push-location": "pushd",
           "get-childitem": "ls", "gci": "ls", "dir": "ls"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh", "fish", "tcsh", "csh", "ash", "mksh"}
MAX_COMMAND = 100_000


def cmd_name(tok: str) -> str:
    """`C:\\Git\\bin\\git.exe` -> `git`, `NPM.cmd` -> `npm`, `Remove-Item` -> `rm`."""
    name = re.split(r"[\\/]", tok)[-1].lower().replace("`", "").replace("^", "")
    for suf in EXE_SUFFIXES:
        if name.endswith(suf):
            name = name[: -len(suf)]
            break
    return ALIASES.get(name, name)


def normalize_command(cmd: str) -> str:
    """Join line continuations (`\\` or PowerShell backtick at the end of a line)."""
    return re.sub(r"[\\`]\r?\n", " ", cmd)


def split_top(cmd: str):
    """Split on ; && || | & newline { } OUTSIDE quotes (`${VAR}`, `2>&1`, `&>`, `>|` stay intact)."""
    parts, buf, q, i, n = [], [], None, 0, len(cmd)

    def cut():
        parts.append("".join(buf))
        buf.clear()

    while i < n:
        ch = cmd[i]
        if q:
            buf.append(ch)
            if ch == q:
                q = None
            elif ch == "\\" and q == '"' and i + 1 < n:
                buf.append(cmd[i + 1])
                i += 1
            i += 1
            continue
        if ch in "'\"":
            q = ch
            buf.append(ch)
        elif ch == "\\" and i + 1 < n:
            buf.append(ch + cmd[i + 1])
            i += 1
        elif ch == "$" and cmd.startswith("${", i) and "}" in cmd[i:]:
            j = cmd.index("}", i)
            buf.append(cmd[i:j + 1])
            i = j
        elif cmd.startswith("&&", i) or cmd.startswith("||", i):
            cut()
            i += 1
        elif ch == "|" and buf and buf[-1] == ">":
            buf.append(ch)                       # >| redirect
        elif ch in ";\n|{}":
            cut()
        elif ch == "&" and (cmd.startswith("&>", i) or (buf and buf[-1] in "<>")):
            buf.append(ch)                       # &> file, 2>&1
        elif ch == "&":
            cut()
        else:
            buf.append(ch)
        i += 1
    cut()
    return parts


def _shell_inner(toks):
    """The command string a shell wrapper runs, None if none, or '' when it cannot be read (encoded)."""
    c, args = toks[0], toks[1:]
    low = [a.lower() for a in args]
    if c == "busybox" and args:
        return _shell_inner([cmd_name(args[0])] + args[1:])
    if c in SHELLS:
        for i, a in enumerate(args):
            if re.match(r"^-[a-zA-Z]*c[a-zA-Z]*$", a):
                rest = args[i + 1:]
                if rest[:1] == ["--"]:
                    rest = rest[1:]
                return rest[0] if rest else None
        return None
    if c == "cmd":
        for i, a in enumerate(low):
            if a[:2] in {"/c", "/k", "/r"}:
                return " ".join(([args[i][2:]] if len(a) > 2 else []) + args[i + 1:])
        return None
    if c in {"powershell", "pwsh"}:
        value_opts = {"-executionpolicy", "-exec", "-ex", "-ep", "-windowstyle", "-w", "-workingdirectory", "-wd",
                      "-configurationname", "-inputformat", "-if", "-outputformat", "-of", "-version", "-v",
                      "-psconsolefile", "-settingsfile"}
        i = 0
        while i < len(low):
            a = low[i].split(":")[0]
            if a.startswith("-"):
                if a in {"-e", "-ec"} or (len(a) >= 3 and "-encodedcommand".startswith(a)):
                    return ""
                if a.startswith("-c") and "-command".startswith(a):
                    return " ".join(args[i + 1:])
                if a in {"-f", "-fi", "-fil", "-file"}:
                    return None
                i += 2 if (a in value_opts or a.startswith("-exe")) else 1
                continue
            return " ".join(args[i:]) if c == "powershell" else None
        return None
    if c == "wsl":
        i = 0
        while i < len(args):
            a = args[i]
            if a in {"-e", "--exec", "--"}:
                return " ".join(args[i + 1:])
            if a in {"-d", "--distribution", "-u", "--user", "--cd", "--shell-type"}:
                i += 2
                continue
            if a.startswith("-"):
                i += 1
                continue
            return " ".join(args[i:])
        return None
    return None


REDIR_TOKEN = re.compile(r"^(\d*|&)>>?\|?$")
REDIR_JOINED = re.compile(r"^(\d*|&)>>?\|?(?!&)(.+)$")


def split_segments(cmd: str, _depth: int = 0, windows_paths: bool = True, with_env: bool = False):
    """Token lists for every simple command in `cmd`, including $(...), `...`, bash -c, cmd /c, pwsh -c.
    windows_paths=True reads `a\\b` as the path `a/b`; False reads it as POSIX (`g\\it` = `git`). The caller
    judges both readings and keeps the stricter one. with_env=True returns (tokens, env assignments)."""
    if _depth > 5:
        return [(["eval"], {})] if with_env else [["eval"]]
    cmd = normalize_command(cmd)
    inner = re.findall(r"\$\(([^()]*)\)", cmd) + re.findall(r"`([^`\n]*)`", cmd)
    segs = []
    for piece in split_top(cmd):
        piece = (piece or "").strip().lstrip("(").rstrip(")").strip()
        if not piece:
            continue
        if windows_paths:
            piece = re.sub(r"\\(?=[A-Za-z0-9._$%~-])", "/", piece)
        try:
            toks = shlex.split(piece, posix=True)
        except ValueError:
            toks = piece.split()
        toks = [t.replace("`", "") for t in toks]
        env: dict = {}
        elevated = False
        while toks:
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", toks[0])
            if m:
                env[m.group(1)] = m.group(2)
                toks = toks[1:]
                continue
            w = cmd_name(toks[0])
            if w not in WRAPPERS:
                break
            elevated = elevated or w in {"sudo", "doas"}
            toks = toks[1:]
            vals = WRAPPER_VALUE_OPTS.get(w, set())
            while toks and toks[0].startswith("-") and toks[0] != "-":
                opt = toks[0].split("=", 1)[0]
                if w == "env" and opt in {"-S", "--split-string"}:
                    if "=" in toks[0]:
                        inner.append(toks[0].split("=", 1)[1])
                        toks = toks[1:]
                    elif len(toks) > 1:
                        inner.append(toks[1])
                        toks = toks[2:]
                    else:
                        toks = toks[1:]
                    continue
                toks = toks[2:] if (opt in vals and "=" not in toks[0]) else toks[1:]
            if w == "env":
                while toks and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", toks[0]):
                    k, _, v = toks[0].partition("=")
                    env[k] = v
                    toks = toks[1:]
                if not toks:
                    toks = ["printenv"]           # bare `env` prints the environment
            if w == "timeout" and toks and re.match(r"^[0-9.]+[smhd]?$", toks[0]):
                toks = toks[1:]
        if elevated:
            segs.append((["sudo"], env))
        if toks:
            toks[0] = cmd_name(toks[0])
            sub = _shell_inner(toks)
            if sub == "":
                segs.append((["eval"], env))          # -EncodedCommand: unreadable, asks
                continue
            if sub is not None:
                inner.append(sub)
                continue
            segs.append((toks, env))
    for x in inner:
        segs.extend(split_segments(x, _depth + 1, windows_paths, with_env=True))
    return segs if with_env else [t for t, _ in segs]


def split_redirects(toks):
    """(tokens without redirections, redirect targets). `2>&1` and `>&2` are not targets."""
    out, targets, i = [], [], 0
    while i < len(toks):
        t = toks[i]
        if REDIR_TOKEN.match(t) and i + 1 < len(toks):
            if not toks[i + 1].startswith("&"):
                targets.append(toks[i + 1])
            i += 2
            continue
        m = REDIR_JOINED.match(t)
        if m and not t.startswith(("-", "=")) and m.group(2) and not m.group(2).startswith("&"):
            targets.append(m.group(2))
            i += 1
            continue
        if t in {"<", "<<", "<<<"} and i + 1 < len(toks):
            i += 2
            continue
        out.append(t)
        i += 1
    return out, targets


def _positionals(args, value_flags=()):
    """Arguments that are not options, skipping the value of options that take one (`-R owner/repo`)."""
    out, i = [], 0
    while i < len(args):
        a = args[i]
        if a.startswith("-") and a != "-":
            i += 2 if a in value_flags else 1
            continue
        out.append(a)
        i += 1
    return out


def _has(toks, *flags):
    return any(t == f or t.startswith(f + "=") for t in toks for f in flags)


def _flag_value(toks, *flags):
    for i, t in enumerate(toks):
        for f in flags:
            if t == f and i + 1 < len(toks):
                return toks[i + 1]
            if t.startswith(f + "="):
                return t.split("=", 1)[1]
    return None


def _flag_value_prod(toks, *flags):
    for i, t in enumerate(toks):
        for f in flags:
            if t == f and i + 1 < len(toks) and PROD.search(toks[i + 1]):
                return True
            if t.startswith(f + "=") and PROD.search(t.split("=", 1)[1]):
                return True
    return False


def _git_sub(args):
    """(index of the git subcommand, subcommand, rest). Skips global options that take a value."""
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in {"-C", "-c", "--git-dir", "--work-tree", "--namespace"} else 1
    sub = args[i] if i < len(args) else ""
    return i, sub, args[i + 1:]


# --------------------------------------------------------------------------- commands: judging

PROTECTED_BRANCH = re.compile(r"(^|:|/)(main|master|develop|trunk|release/.+|production|prod|hotfix/.+)$")
WRITE_CMDS = {"cp", "mv", "rm", "rmdir", "tee", "touch", "ln", "chmod", "chown", "truncate", "dd", "install", "rsync",
              "mkdir", "unlink", "shred"}
INTERPRETERS = {"python", "python3", "py", "node", "perl", "ruby", "deno", "bun", "php", "cscript", "wscript", "osascript"}
GIT_FILE_WRITES = {"checkout", "restore", "reset", "stash", "apply", "am", "mv", "rm", "clean"}
DOTNET_WRITE = re.compile(r"\[(system\.)?io\.(file|directory)\]::", re.I)
OUTPUT_FLAGS = {"curl": {"-o", "--output", "--output-dir", "-outfile"},
                "wget": {"-o", "--output-document", "-p", "--directory-prefix"},
                "tar": {"-c", "--directory"}, "bsdtar": {"-c", "--directory"},
                "unzip": {"-d"}, "expand-archive": {"-destinationpath"}}
REDIRECT = re.compile(r"(?:\d*|&)>>?\|?\s*(?!&)([^\s;&|<>]+)")
WIPE_TARGET = re.compile(r"^(/|/\*|~|~/|~/\*|\*|\.|\.\.|\./\*|[a-z]:/?|[a-z]:/\*|\$home/?|\$\{home\}?/?|\$env:userprofile/?|"
                         r"%userprofile%/?|\$env:systemroot/?|%systemroot%/?|c:/windows/?|/home/?|/users/?)$", re.I)
PW_LOCAL = re.compile(r"^(https?://)?(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]|[a-z0-9-]+\.localhost|"
                      r"host\.docker\.internal)(:\d+)?([/?#]|$)", re.I)
PW_CONFIG = ".playwright/cli.config.json"
PW_VALUE_FLAGS = {"-s", "--session", "--config", "--browser", "--profile", "--device", "--filename", "--cdp"}
GIT_HISTORY_WRITES = {"commit", "merge", "rebase", "cherry-pick", "revert", "am", "pull"}
LOCAL_ONLY_MSG = ("local-only: nothing leaves this machine from an agent (A4). Put the exact command in your report "
                  "for Cecilia to run herself.")


def _pw_parse(args):
    """playwright-cli [global flags] <sub> [args] -> (sub, positional args after sub, --config value)."""
    sub, rest, config, i = "", [], None, 0
    while i < len(args):
        x = args[i]
        if x.startswith("-"):
            name, eq, val = x.partition("=")
            if name in PW_VALUE_FLAGS and not eq and i + 1 < len(args):
                val = args[i + 1]
                i += 1
            if name == "--config":
                config = val
        elif not sub:
            sub = x
        else:
            rest.append(x)
        i += 1
    return sub, rest, config


def _local_bin(name: str, ctx: dict) -> bool:
    """Is `name` already installed in the project (node_modules/.bin) — npx then runs local code, no download."""
    starts = [p for p in (ctx.get("cwd"), ctx.get("root")) if p is not None]
    for start in starts:
        for d in [start, *start.parents]:
            b = d / "node_modules" / ".bin"
            if (b / name).exists() or (b / f"{name}.cmd").exists():
                return True
            if ctx.get("root") is not None and d == ctx["root"]:
                break
    return False


def _seq_in(seq, args) -> bool:
    """Does the token sequence `seq` (after its first element = the command) appear at the start of args?"""
    return [a.lower() for a in args[:len(seq) - 1]] == [s.lower() for s in seq[1:]]


def _env_target(env: dict, args, pol) -> str:
    """'prod', 'staging' or '' — where a DB/deploy command points, from inline env vars and flags."""
    envish = lambda k: k.upper() in set(pol.get("db_url_vars", [])) or k.upper().endswith("_ENV") or \
        k.upper() in {"ENV", "ENVIRONMENT", "STAGE", "APP_ENV"}
    vals = [v for k, v in env.items() if envish(k)]
    vals += [a for a in args if "=" in a and a.startswith("-")]
    vals += [a.split("=", 1)[1] for a in args if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", a) and envish(a.split("=", 1)[0])]
    for f in ("--env", "-e", "--environment", "--url", "--database-url", "--settings", "--stage", "--profile"):
        v = _flag_value(args, f)
        if v:
            vals.append(v)
    blob = " ".join(vals)
    if PROD.search(blob):
        return "prod"
    if STAGING.search(blob):
        return "staging"
    return ""


def decide_segment(t, ctx=None):
    ctx = ctx or {}
    pol = ctx.get("policy") or POLICY
    cfg = ctx.get("cfg") or default_config_view()
    local_only = cfg["git"].get("local_only", True)
    env = ctx.get("env") or {}
    c = t[0]
    args = t[1:]
    a0 = args[0] if args else ""
    a1 = args[1] if len(args) > 1 else ""
    joined = " ".join(t)

    if c == "sudo":
        return ASK, "sudo runs with elevated privileges (A3)."
    # ---- guard self-protection ------------------------------------------------------------
    runs = [c] + (args[:2] if c in {"python", "python3", "py", "uv", "pipx"} or re.match(r"^python[0-9.]+$", c) else [])
    may_run = agent_may_run(cfg)
    ctl = next((m.group(1) for x in runs for m in [re.search(r"cecilia_(approve|mode)(\.py)?$", x.replace("\\", "/"))]
                if m), None)
    if ctl:
        opened = ctl in may_run and not (ctl == "mode" and any(a.startswith("--push-lock") for a in args)
                                         and "push-lock" not in may_run)
        if not opened:
            return DENY, "Only Cecilia runs the approval/mode control tools, in her own terminal."
        return ALLOW, ""          # guard.agent_may_run: Cecilia opened it to agents
    if len(runs) > 1 and runs[1].replace("\\", "/").split("/")[-1].lower() == "workspace_tools.py":
        wt = _cecilia_v20_control(args[1] if len(args) > 1 else "", list(args[2:]), may_run)
        if wt:
            return wt
    cli = None
    if c == "cecilia":
        cli = list(args)
    elif (c in {"python", "python3", "py"} or re.match(r"^python[0-9.]+$", c)) and args[:2] == ["-m", "cecilia"]:
        cli = list(args[2:])
    elif c in {"uv", "uvx"} and any(re.search(r"(^|[/@:])cecilia(-skills)?([@.#]|$)", x) for x in args):
        if "tool" in args[:2]:
            return DENY, "Installing, upgrading or removing the Cecilia tool is Cecilia's (it changes the guard)."
        cli = list(args[args.index("cecilia") + 1:]) if "cecilia" in args else ["init"]
    if cli is not None:
        sub, rest = (cli[0] if cli else "help"), cli[1:]
        v20 = _cecilia_v20_control(sub, rest, may_run)
        if v20:
            return v20
        if sub in {"mode", "approve", "push", "push-lock"} and sub in may_run:
            return ALLOW, ""      # guard.agent_may_run: Cecilia opened it to agents
        if sub in {"doctor", "where", "version", "--version", "-V", "help", "--help", "-h", "validate", "tokens",
                   "corpus", "status", "lessons", "scorecard"} and "--fix" not in rest:
            return ALLOW, ""
        if sub == "open" and "--claude" not in rest:
            return ALLOW, ""
        if (sub == "mode" and rest in ([], ["--show"])) or (sub == "push-lock" and rest in ([], ["status"])) or \
                (sub == "clean" and "--apply" not in rest):
            return ALLOW, ""
        if sub in {"evals", "package"}:
            return ASK, f"`cecilia {sub}` costs tokens or writes release files (A3) — Cecilia approves it."
        return DENY, (f"`cecilia {sub}` changes Cecilia's controls or leaves the machine (mode, approve, push, "
                      "push-lock, init, upgrade) — only Cecilia runs it, in her own terminal. Put the command in "
                      "your report.")

    # ---- package runners: a package downloaded from a registry is A3; a local bin is judged as itself --------
    if c in {"npx", "bunx"} or (c in {"pnpm", "yarn"} and a0 == "dlx") or (c == "npm" and a0 in {"exec", "x"}):
        rest = list(args if c in {"npx", "bunx"} else args[1:])
        dlx = c in {"pnpm", "yarn", "bunx"} and (a0 == "dlx" or c == "bunx")
        no_install, pinned_pkg, i = False, None, 0
        while i < len(rest) and rest[i].startswith("-"):
            if rest[i] in {"-c", "--call"} and i + 1 < len(rest):
                return decide_command_segments(rest[i + 1], ctx)
            if rest[i] in {"--no-install", "--no", "--offline", "--prefer-offline"}:
                no_install = True
            if rest[i] in {"-p", "--package"} and i + 1 < len(rest):
                pinned_pkg = rest[i + 1]
                i += 2
                continue
            i += 1
        if rest[i:i + 1] == ["--"]:
            i += 1
        if i < len(rest):
            pkg = re.sub(r"(?<=.)@[^/@]*$", "", rest[i])
            name = pol.get("pkg_bin", {}).get(pkg, cmd_name(pkg))
            inner = decide_segment([name] + rest[i + 1:], {**ctx, "via_runner": True})
            if inner[0] == DENY:
                return inner
            local = (not dlx) and (no_install or _local_bin(name, ctx)) and pinned_pkg is None
            if not local and name not in {"playwright-cli", "skills"}:
                why = (f"`{' '.join(t[:3])}…` downloads '{pinned_pkg or pkg}' from the registry and runs it (A3) — "
                       "not installed in this project. Install it as a dependency (A3) or Cecilia approves this run.")
                return (ASK, why) if RANK[inner[0]] <= RANK[ASK] else inner
            return inner
        return ALLOW, ""
    if (c == "pipx" and a0 == "run") or c == "uvx" or (c == "uv" and a0 == "tool" and a1 == "run"):
        return ASK, f"`{' '.join(t[:3])}` downloads a Python tool and runs it (A3)."

    # ---- agent skills and browser automation -----------------------------------------------
    if c == "skills" and a0 in {"add", "install", "i", "remove", "rm", "update", "upgrade", "init", "sync"}:
        return ASK, ("skills " + a0 + " installs third-party agent instructions that run with the agent's "
                     "permissions (A3). Prefer the vendored style guides (ui.style in .cecilia/config.json).")
    if c == "playwright":
        if a0 in {"install", "install-deps", "uninstall"}:
            return ASK, f"playwright {a0} downloads or removes browsers/system packages (A3)."
        if a0 == "cli":
            return decide_segment(["playwright-cli"] + args[1:], ctx)
        return ALLOW, ""
    if c == "playwright-cli":
        sub, rest, config = _pw_parse(args)
        if sub.startswith("install") or sub == "uninstall":
            return ASK, f"playwright-cli {sub} downloads browsers or installs skills (A3)."
        if sub in {"attach"} or _has(args, "--cdp", "--extension", "--profile"):
            return ASK, "Driving a real browser profile (your sign-ins) is A3 — agents use an isolated session."
        if sub in {"close-all", "kill-all"}:
            return ASK, f"playwright-cli {sub} also stops other members' browsers (A3) — close your own session."
        if sub == "run-code":
            return ASK, "playwright-cli run-code runs code outside the page (A3) — use eval, route or the commands."
        if config is not None and not config.replace("\\", "/").endswith(PW_CONFIG):
            return ASK, f"playwright-cli with another config than {PW_CONFIG} (A3) — that file limits it to local pages."
        if sub in {"open", "goto", "tab-new"}:
            for u in rest:
                if not PW_LOCAL.match(u):
                    return ASK, f"Opening '{u}' leaves localhost (A3) — Cecilia approves the site."
        return ALLOW, ""
    if c == "start-process" and any(x.lower() == "runas" for x in args):
        return ASK, "Start-Process -Verb RunAs runs elevated (A3)."

    # ---- environment dumps and secret files, whatever the command ----------------------------
    if c in set(pol.get("env_dumpers", [])) or (c == "set" and not args) or \
            (c == "ls" and any(x.lower().rstrip("\\/") in {"env:", "env:*"} for x in args)):
        return ASK, "Printing the whole environment exposes secrets (tokens, DB URLs) — Cecilia approves (A3)."
    git_sub = _git_sub(args)[1] if c == "git" else ""
    safe = c in set(pol.get("secret_safe_commands", [])) or (c == "git" and git_sub in set(pol.get("secret_safe_git", [])))
    passed = set()     # `--env-file .env` hands the file to a program without printing it: allowed
    for i, x in enumerate(args):
        if x in {"--env-file", "--env_file"} or (c == "dotenv" and x in {"-e", "--env"}):
            passed.add(i + 1)
    if c in {"grep", "rg", "egrep", "fgrep", "awk", "sed", "findstr"} and not _has(args, "-e", "-f", "--regexp", "--file"):
        first = next((i for i, x in enumerate(args) if not x.startswith("-")), None)
        if first is not None:
            passed.add(first)        # the search pattern / script is text, not a file that is read
    hits = [x for i, x in enumerate(args) if i not in passed and not x.startswith("-")
            and SECRET_FILES.search(x.replace("\\", "/"))]
    inline = [x for x in args if " " in x or "(" in x or "'" in x or '"' in x]
    inline_hit = (c in INTERPRETERS or re.match(r"^python[0-9.]+$", c)) and any(SECRET_INLINE.search(x) for x in inline)
    if c == "git" and git_sub == "add" and hits:
        return DENY, f"`git add {hits[0]}` would commit a secret file — never (A4)."
    if (hits or inline_hit) and not safe:
        what = hits[0] if hits else "a secret file"
        return DENY, (f"'{what}' looks like a secret file — agents never read, copy or print secret values (A4). "
                      "Use the variable names from .env.example; Cecilia provides values.")

    # ---- git ------------------------------------------------------------------------------
    if c == "git":
        genv = {k.upper(): str(v).lower() for k, v in (ctx.get("env") or {}).items()}
        if any(k.startswith("GIT_CONFIG_KEY_") or k == "GIT_CONFIG_PARAMETERS" for k in genv):
            blob = " ".join(genv.values())
            if "alias" in blob or "push" in blob or "insteadof" in blob or "url." in blob:
                return DENY, "git config injected through the environment (alias/url rewrite) — never (A4)."
            return ASK, "git config injected through the environment (A3) — Cecilia approves it."
        return _decide_git(args, ctx, cfg, pol, local_only)

    # ---- git hosts --------------------------------------------------------------------------
    if c in set(pol.get("git_host_clis", ["gh", "glab"])):
        return _decide_git_host(c, args, local_only, pol)

    # ---- publishing / release -------------------------------------------------------------
    if (c in {"npm", "pnpm", "yarn", "bun"} and "publish" in args) or (c == "twine" and a0 == "upload") \
            or (c in {"cargo", "gem"} and a0 in {"publish", "push"}) or (c == "mvn" and "deploy" in args) \
            or (c in {"gradle", "./gradlew", "gradlew"} and any(x.startswith("publish") for x in args)) \
            or (c == "poetry" and a0 == "publish") or (c == "uv" and a0 == "publish") \
            or (c == "dotnet" and a0 == "nuget" and a1 == "push"):
        return DENY, "Publishing a package is a release (A4) — Cecilia only."

    # ---- secrets and IAM ------------------------------------------------------------------
    if c == "vault" or (c == "aws" and a0 in {"iam", "secretsmanager", "kms", "sso"}) \
            or (c == "aws" and a0 == "ssm" and "get-parameter" in joined and "--with-decryption" in args) \
            or (c == "gcloud" and (a0 in {"iam", "secrets", "kms"} or "add-iam-policy-binding" in args
                                   or "set-iam-policy" in args)) \
            or (c == "az" and a0 in {"role", "keyvault", "ad"}) \
            or (c in {"kubectl", "oc"} and ("secret" in args or "secrets" in args) and a0 in {"create", "get", "describe",
                                                                                          "edit", "delete", "apply"}) \
            or (c in {"kubectl", "oc"} and a0 == "create" and a1 in {"role", "clusterrole", "rolebinding",
                                                                  "clusterrolebinding", "serviceaccount", "token"}) \
            or (c in {"wrangler"} and a0 == "secret") or (c == "supabase" and a0 == "secrets") \
            or (c in {"vercel"} and a0 == "env" and a1 in {"pull", "add", "rm"}) \
            or (c in {"railway"} and a0 == "variables"):
        return DENY, "Secrets and IAM are A4 — never handled by an agent. Prepare the command for Cecilia."
    if secret_dump(t, pol) == "etcd":
        return DENY, ("etcdctl get on /registry/secrets prints every cluster secret — never (A4). Prepare the "
                      "command for Cecilia.")
    if c in {"cat", "less", "more", "head", "tail", "bat", "source", ".", "strings", "xxd", "base64",
             "grep", "rg", "awk", "sed"}:
        files = list(args)
        if c in {"grep", "rg", "awk", "sed"} and not _has(args, "-e", "-f", "--regexp", "--file"):
            first = next((i for i, x in enumerate(args) if not x.startswith("-")), None)
            if first is not None:
                files = args[:first] + args[first + 1:]      # the pattern/script is not a file
        for x in files:
            if not x.startswith("-") and SECRET_FILES.search(x):
                return DENY, f"'{x}' looks like a secret file — agents never read secret values (A4)."

    # ---- production anywhere --------------------------------------------------------------
    live = set(pol.get("live_tools", []))
    if c in live and (_flag_value_prod(args, "--context", "--kube-context", "-n", "--namespace", "--profile",
                                       "-f", "--values", "-var-file", "--var-file", "--kubeconfig",
                                       "--project", "--subscription", "--env", "--environment", "--stage",
                                       "-e", "--app", "-a", "--cluster", "--workspace", "-h", "--host", "--project-ref",
                                       "--service")
                      or any(PROD.search(x) for x in args if "=" in x and x.startswith("-"))
                      or (c in {"kubectx", "kubens"} and any(PROD.search(x) for x in args))
                      or (c == "kubectl" and a0 == "config" and a1 in {"use-context", "set-context"}
                          and any(PROD.search(x) for x in args))
                      or (c in {"terraform", "tofu"} and a0 == "workspace" and any(PROD.search(x) for x in args))
                      or (c in {"vercel", "netlify", "firebase"} and _has(args, "--prod"))
                      or _env_target(env, [], pol) == "prod"):
        return DENY, "This targets production — A4. Prepare the exact command, its check and rollback for Cecilia."

    # ---- infrastructure / live systems ----------------------------------------------------
    if c in {"terraform", "tofu", "terragrunt"}:
        if a0 in {"destroy"} or _has(args, "-auto-approve", "--auto-approve") or \
                (a0 == "state" and a1 in {"push"}) or a0 == "force-unlock":
            return DENY, f"terraform {a0} with this form is A4 (destroy / auto-approve / state surgery)."
        if a0 in {"fmt", "validate", "version", "providers", "graph", "console", "-help", "--help"} or \
                (a0 == "init" and _has(args, "-backend=false")):
            return ALLOW, ""
        return ASK, f"terraform {a0} reads or changes live state (A3) — quote it with the context."
    if c == "pulumi" and a0 in {"destroy"}:
        return DENY, "pulumi destroy is A4."
    if secret_dump(t, pol) == "kube":
        return ASK, (f"`{c} get … secret … -o …` prints secret values into the transcript (A3) — Cecilia approves "
                     "it, or leave out -o (names only) / use describe.")
    if c == "helm":
        if a0 in {"lint", "template", "version", "show", "dependency", "create", "package", "search", "repo"}:
            return ALLOW, ""
        return ASK, f"helm {a0} touches a cluster (A3)."
    if c in {"kubectl", "oc"}:
        if a0 in {"version", "kustomize", "explain", "completion"} or _has(args, "--dry-run=client") or \
                (a0 == "config" and a1 in {"view", "get-contexts", "current-context"}):
            return ALLOW, ""
        return ASK, f"kubectl {a0} reads or changes a live cluster (A3) — quote it with --context."
    if c in live:
        safe = pol.get("live_tool_safe", {}).get(c, [])
        pos = _positionals(args, {"--env", "-e", "--config", "-c", "--project-ref", "--profile"})
        if any(pos[:len(s)] == s or args[:len(s)] == s for s in safe):
            return ALLOW, ""
        for seq in pol.get("migration_ask", []):
            if seq[0] == c and _seq_in(seq, pos):
                return ASK, f"`{' '.join(seq)}` changes or wipes a database (A3) — say which database and back it up first."
        return ASK, f"{c} reaches a live system or cloud account (A3)."
    if c == "docker":
        if a0 in {"push", "login", "logout"} or (a0 == "image" and a1 == "push"):
            return ASK, f"docker {a0} reaches a registry (A3)."
        if a0 in {"system", "volume", "image", "container", "network", "builder", "buildx"} and a1 in {"prune", "rm"}:
            return ASK, "Pruning/removing docker resources (A3)."
        if (a0 == "compose" or c == "docker-compose") and "down" in args and _has(args, "-v", "--volumes"):
            return ASK, "docker compose down -v deletes the volumes — local databases included (A3). Dump first."
        return ALLOW, ""
    if c == "docker-compose" and "down" in args and _has(args, "-v", "--volumes"):
        return ASK, "docker compose down -v deletes the volumes — local databases included (A3). Dump first."

    # ---- migrations -----------------------------------------------------------------------
    mig = _decide_migration(c, args, env, pol)
    if mig:
        return mig

    # ---- project scripts and task runners that deploy or release --------------------------
    scr = _decide_scripts(c, args, env, pol)
    if scr:
        return scr

    # ---- dependencies ---------------------------------------------------------------------
    installs = {
        "npm": {"install", "i", "add", "ci", "uninstall", "remove", "rm", "update", "upgrade", "link"},
        "pnpm": {"install", "i", "add", "remove", "rm", "update", "up", "upgrade", "link"},
        "yarn": {"install", "add", "remove", "upgrade", "up", "link"},
        "bun": {"install", "i", "add", "remove", "rm", "update", "link"},
        "pip": {"install", "uninstall", "download"}, "pip3": {"install", "uninstall", "download"},
        "poetry": {"add", "remove", "update", "install", "lock"}, "uv": {"add", "remove", "pip", "sync", "lock"},
        "pipenv": {"install", "uninstall", "update"}, "conda": {"install", "remove", "update", "create"},
        "go": {"get", "install"}, "cargo": {"add", "remove", "install", "update"},
        "bundle": {"add", "install", "update"}, "gem": {"install", "uninstall", "update"},
        "composer": {"require", "remove", "update", "install"}, "dotnet": {"add"},
        "brew": {"install", "uninstall", "upgrade", "tap"}, "apt": {"install", "remove", "upgrade"},
        "apt-get": {"install", "remove", "upgrade"}, "yum": {"install", "remove"}, "dnf": {"install", "remove"},
        "apk": {"add", "del"}, "choco": {"install", "uninstall", "upgrade"}, "winget": {"install", "uninstall", "upgrade"},
        "scoop": {"install", "uninstall", "update"},
    }
    pos = _positionals(args, {"--prefix", "-C", "--dir", "--filter", "-F", "--registry", "--workspace", "-w", "--cwd",
                              "--userconfig", "--cache", "-p", "--python"}) if c in installs else []
    if c == "uv" and len(pos) > 1 and (pos[0], pos[1]) in {("tool", "install"), ("tool", "upgrade"), ("tool", "uninstall"),
                                                            ("tool", "run"), ("python", "install"),
                                                            ("python", "uninstall"), ("self", "update")}:
        return ASK, f"uv {pos[0]} {pos[1]} downloads or removes code (A3)."
    if c in installs and pos and pos[0] in installs[c]:
        return ASK, f"{c} {pos[0]} changes dependencies or downloads code (A3)."
    if c in {"python", "python3", "py"} and a0 == "-m" and a1 in {"pip", "ensurepip"}:
        return ASK, "pip changes dependencies or downloads code (A3)."

    # ---- deleting files -------------------------------------------------------------------
    if c in {"rm", "rmdir", "unlink", "shred", "srm"}:
        targets = [x for x in args if not x.startswith("-")]
        if any(WIPE_TARGET.match(x.replace("\\", "/").rstrip("}")) for x in targets) or "--no-preserve-root" in args:
            return DENY, "That delete could wipe the project or the machine — never."
        return ASK, "Deleting files is A3 — Cecilia approves the exact paths."
    if c == "find" and ("-delete" in args or "-exec" in args and "rm" in args):
        return ASK, "find -delete removes files (A3)."

    # ---- network writes, remote shells, messages ------------------------------------------
    if c in set(pol.get("network_write_tools", [])):
        write_methods = {"POST", "PUT", "PATCH", "DELETE"}
        method_flag = any(x.upper() in write_methods for x in args) or \
            any(x.upper() in {"-X" + m for m in write_methods} for x in args) or \
            any(x.startswith("--request=") and x.split("=", 1)[1].upper() in write_methods for x in args)
        body_flag = _has(args, "-d", "--data", "--data-raw", "--data-binary", "--data-urlencode", "-F", "--form",
                         "-T", "--upload-file", "--post-data", "--post-file", "--json")
        ps_body = any(x.lower() in {"-body", "-infile", "-form"} for x in args) or \
            any(x.lower().startswith("-method:") and x.split(":", 1)[1].upper() in write_methods for x in args)
        if method_flag or body_flag or ps_body:
            if local_only and any(h in x for x in args for h in pol.get("git_host_api_hosts", [])):
                return DENY, "A write to a git host's API. " + LOCAL_ONLY_MSG
            return ASK, "This sends data to a remote system (A3)."
        return ALLOW, ""
    if c in set(pol.get("remote_shell_tools", [])) or c == "rsync":
        if c == "rsync" and not any(":" in x for x in args if not x.startswith("-")):
            return ALLOW, ""
        return ASK, f"{c} reaches a remote machine (A3)."
    if c in set(pol.get("messaging_tools", [])):
        return ASK, "Sending a message is A3 — destination and content need Cecilia's yes."

    # ---- running a script fetched from the internet ----------------------------------------
    if c in {"eval"}:
        return ASK, "eval runs an unseen command (A3)."

    return ALLOW, ""


def agent_may_run(cfg) -> set:
    """20.2 `guard.agent_may_run`: human-only `cecilia` subcommands Cecilia opened to agents (default none).
    Names: mode, approve, flow, rules add (or `rules` = every rules change), extension apply (or `extension`), push."""
    v = ((cfg or {}).get("guard_extra") or {}).get("agent_may_run")
    return {" ".join(x.lower().split()) for x in v if isinstance(x, str) and x.strip()} if isinstance(v, list) else set()


def _cecilia_v20_control(sub: str, rest: list, may_run=()):
    """`cecilia flow|rules|extension ...`: the read-only forms pass; changes are Cecilia's own (human-only),
    unless Cecilia listed the subcommand in `guard.agent_may_run`."""
    if sub not in {"flow", "rules", "extension", "extensions"}:
        return None
    verb = next((x for x in rest if not x.startswith("-")), "")
    if "--fix" not in rest and "--apply" not in rest and (
            (sub == "flow" and not verb and set(rest) <= {"--show", "--json"}) or (sub == "flow" and verb in {"show", "list"})
            or (sub == "rules" and verb in {"", "list", "show", "lint", "hash"})
            or (sub.startswith("extension") and verb in {"", "check", "list", "show"})):
        return ALLOW, ""
    base = "extension" if sub.startswith("extension") else sub
    if base in may_run or (base != "flow" and f"{base} {verb or ('apply' if '--apply' in rest else '')}".strip()
                           in may_run):
        return ALLOW, ""
    what = {"flow": "the project flow", "rules": "the project rules"}.get(sub, "the installed extensions")
    shown = f"cecilia {sub} {verb}".strip()
    return DENY, (f"`{shown}` changes {what} - only Cecilia runs it, in her own terminal. "
                  "Put the exact command in your report.")


def _decide_git(args, ctx, cfg, pol, local_only):
    if any(x.startswith("--no-v") for x in args) or \
            (_positionals(args, {"-C", "-c"})[:1] == ["commit"]
             and any(re.match(r"^-[a-zA-Z]*n[a-zA-Z]*$", x) for x in args)):
        return DENY, "--no-verify skips the repo's hooks — never (A4). Fix or report the failing hook."
    if any(x.lower().startswith("core.hookspath") for x in args):
        return DENY, "Changing core.hooksPath switches the repo's hooks off — never (A4)."
    sub_i, sub, rest = _git_sub(args)
    cvals = [args[i + 1].lower() for i in range(sub_i - 1) if args[i] == "-c" and i + 1 < len(args)]
    if any(v.startswith("alias.") and ("push" in v or "=!" in v or "send-pack" in v) for v in cvals):
        return DENY, "A git alias that pushes or runs a shell is a way around local-only — never (A4)."
    if "-c" in args[:sub_i]:
        return ASK, "git -c can run arbitrary programs — needs Cecilia's yes."
    if sub in {"show", "cat-file", "archive", "diff", "log", "grep"} and any(
            ":" in r and SECRET_FILES.search(r.split(":", 1)[1].replace("\\", "/")) for r in rest if not r.startswith("-")):
        return DENY, "Reading a secret file from git history prints secret values — never (A4)."
    # ---- leaving the machine -----------------------------------------------------------------
    pushlike = sub in set(pol.get("git_push_like", ["push"])) or \
        any([sub, *rest[:1]] == seq for seq in pol.get("git_push_subcommands", []))
    if pushlike:
        if _has(rest, "--force", "-f", "--mirror", "--all", "--delete", "-d") or any(r.startswith("+") or r.startswith(":")
                                                                                     for r in rest):
            return DENY, "Force/mirror push or deleting a remote branch is A4 — Cecilia only."
        if any(PROTECTED_BRANCH.search(r) for r in rest if not r.startswith("-")):
            return DENY, "Pushing to a protected/shared branch is A4 — Cecilia only."
        if local_only:
            return DENY, "git " + sub + ": " + LOCAL_ONLY_MSG
        return ASK, "git push leaves this machine (A3) — Cecilia approves this exact push."
    if sub == "remote" and rest and rest[0] in {"add", "set-url", "remove", "rm", "rename"}:
        return (DENY, "Changing git remotes. " + LOCAL_ONLY_MSG) if local_only else (ASK, "Changing git remotes is A3.")
    if sub == "config":
        keys = [r.lower() for r in rest if not r.startswith("-")]
        key = keys[0] if keys else ""
        writing = len(keys) > 1 or _has(rest, "--unset", "--unset-all", "--add", "--replace-all", "--remove-section",
                                        "--rename-section", "--edit", "-e")
        if any(r in {"--global", "--system"} for r in rest) and writing:
            return DENY, "Changing global git config is not the agent's (A4)."
        remote_key = key.startswith(("url.", "remote.")) or "insteadof" in key or \
            key.endswith((".pushremote", ".remote", ".pushurl")) or key == "remote.pushdefault"
        if (remote_key and writing) or _has(rest, "--remove-section", "--rename-section", "--edit", "-e"):
            return (DENY, "Changing where git pushes/fetches (url.*, remote.*) is how the push lock works — "
                    + LOCAL_ONLY_MSG) if local_only else (ASK, "Changing git remote settings is A3.")
        if key.startswith("alias.") and writing:
            val = " ".join(r for r in rest if not r.startswith("-")).lower()
            if "push" in val or "send-pack" in val or "!" in val:
                return DENY, "A git alias that pushes or runs a shell is a way around local-only — never (A4)."
            return ASK, f"git config {key} adds a persistent alias (A3) — Cecilia approves it."
        if key and writing and any(k in key for k in pol.get("git_exec_config_keys", [])):
            return ASK, f"git config {key} makes git run a program later (A3) — Cecilia approves the exact value."
    # ---- history writes on a protected branch (also after a switch in the same command) ---------
    if sub in GIT_HISTORY_WRITES and ctx.get("cwd") is not None:
        here = ctx["cwd"]
        if "-C" in args[:sub_i]:
            j = args.index("-C")
            if j + 1 < len(args):
                here = Path(args[j + 1]) if Path(args[j + 1]).is_absolute() else here / args[j + 1]
        branch = ctx.get("branch_override") if "-C" not in args[:sub_i] else None
        branch = branch or current_branch(here)
        if cfg["git"]["require_task_branch"] and branch is None and not Path(here).exists():
            return ASK, f"git {sub} in a directory that does not exist yet — cannot tell the branch (A3)."
        if cfg["git"]["require_task_branch"] and branch and branch_protected(branch, cfg["git"]["protected"]):
            return DENY, (f"git flow: `git {sub}` on protected branch '{branch}' is A4 — work on a task branch "
                          "(git.md §2); Cecilia merges into protected branches.")
    if sub == "commit" and local_only and ctx.get("cwd") is not None:
        staged = _staged_local_only(ctx["cwd"], "-a" in rest or "--all" in rest or any(
            re.match(r"^-[a-zA-Z]*a[a-zA-Z]*$", r) for r in rest), pol)
        if staged is None:
            return ASK, "Could not list the staged files to check for Cecilia's local files (A3)."
        if staged:
            shown = ", ".join(staged[:5]) + ("…" if len(staged) > 5 else "")
            return DENY, (f"local-only: Cecilia's own files are staged ({shown}) — they never enter a commit. "
                          f"Unstage them: `git restore --staged -- {' '.join(staged[:5])}`.")
    if sub == "add" and _has(rest, "-f", "--force"):
        paths = [r for r in rest if not r.startswith("-")]
        here = ctx.get("cwd") or Path.cwd()
        root = ctx.get("root") or here
        for pth in paths:
            rel = to_rel(pth, Path(here), Path(root)) or pth
            if local_only_match(rel, pol.get("local_only_paths")) or pth in {".", "-A", ":/"}:
                return DENY, f"local-only: `git add -f {pth}` would stage Cecilia's local files — never."
    # ---- discarding work -----------------------------------------------------------------------
    if sub == "reset" and ("--hard" in rest or "--merge" in rest or "--keep" in rest):
        return ASK, f"git reset {'--hard' if '--hard' in rest else rest[0]} can discard work (A3)."
    if sub == "clean" and any(r.startswith("-") and "f" in r for r in rest):
        return ASK, "git clean deletes untracked files (A3)."
    if sub == "checkout":
        if "." in rest or ("--" in rest and rest.index("--") < len(rest) - 1) or _has(rest, "-f", "--force", "--ours",
                                                                                         "--theirs", "-p", "--patch"):
            return ASK, "git checkout of paths (or -f) overwrites local changes (A3)."
        pos = [r for r in rest if not r.startswith("-")]
        here = Path(ctx.get("cwd") or Path.cwd())
        if len(pos) >= 1 and not _has(rest, "-b", "-B", "--orphan", "--detach") and \
                any((here / p).exists() for p in pos if p not in {"HEAD"}) and "--" not in rest:
            return ASK, "git checkout <path> overwrites local changes to that path (A3)."
    if sub == "restore":
        staged_only = _has(rest, "--staged", "-S") and not _has(rest, "--worktree", "-W")
        if not staged_only:
            return ASK, "git restore discards local changes to those paths (A3)."
    if sub == "switch" and _has(rest, "-f", "--force", "--discard-changes"):
        return ASK, "git switch --discard-changes throws local changes away (A3)."
    if sub == "stash" and rest and rest[0] in {"drop", "clear"}:
        return ASK, "Dropping stashes loses work (A3)."
    prot = cfg.get("git", {}).get("protected") or DEFAULT_PROTECTED
    names = [r for r in rest if not r.startswith("-")]
    is_prot = lambda n: branch_protected(n, prot)  # noqa: E731
    if sub == "branch" and names:
        moved = (_has(rest, "-f", "--force") and is_prot(names[0])) or \
            (_has(rest, "-D", "-d", "--delete") and any(is_prot(n) for n in names)) or \
            (_has(rest, "-m", "-M", "--move") and len(names) == 2 and is_prot(names[0]))
        if moved:
            return DENY, "Moving, renaming or deleting a protected branch is A4 — Cecilia only."
        if _has(rest, "-M", "-C") and is_prot(names[-1]):
            return ASK, "Force-renaming or copying onto a protected branch name (A3)."
        if "-D" in rest:
            return ASK, "Force-deleting a branch (A3)."
    if sub == "pull":
        return ASK, "git pull changes your working tree from the remote (A3)."
    if sub == "tag" and rest and not rest[0].startswith("-l") and rest[0] not in {"-l", "--list"}:
        return ASK, "Creating tags prepares a release (A3); pushing tags is A4."
    if sub == "worktree" and rest and rest[0] == "remove":
        return ASK, "Removing a worktree can lose unpushed work (A3)."
    if sub == "config" and any(r.lower().startswith("alias.") for r in rest) and len(names) > 1:
        return ASK, "A git alias can hide any command (A3)."
    if sub == "update-ref" and any(is_prot(n.replace("refs/heads/", "")) for n in names):
        return DENY, "Moving a protected branch is A4 — Cecilia only."
    return ALLOW, ""


def _staged_local_only(cwd: Path, include_modified: bool, pol) -> list | None:
    """Staged paths (and, for `commit -a`, modified tracked paths) that are Cecilia's local files. None = unknown."""
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    try:
        top = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                             timeout=5, env=env)
        if top.returncode != 0:
            return []                       # not a repository: git commit will fail by itself
        out = subprocess.run(["git", "-C", str(cwd), "--no-optional-locks", "diff", "--cached", "--name-only", "-z"],
                             capture_output=True, text=True, timeout=5, env=env)
        files = [f for f in out.stdout.split("\0") if f]
        if include_modified:
            mod = subprocess.run(["git", "-C", str(cwd), "--no-optional-locks", "diff", "--name-only", "-z"],
                                 capture_output=True, text=True, timeout=5, env=env)
            files += [f for f in mod.stdout.split("\0") if f]
    except (OSError, subprocess.SubprocessError):
        return None
    return [f for f in files if local_only_match(f, pol.get("local_only_paths"))]


def _decide_git_host(c, args, local_only, pol):
    pos = _positionals(args, {"-R", "--repo", "--hostname", "-H", "--jq", "-q", "--template", "-t"})
    a0 = pos[0] if pos else ""
    a1 = pos[1] if len(pos) > 1 else ""
    if a0 in {"pr", "mr"} and (a1 == "merge" or a1 == "approve" or (a1 == "review" and _has(args, "--approve", "-a"))):
        return DENY, "Merging or approving a PR is A4 — Cecilia only."
    if a0 in {"release", "secret", "ssh-key", "gpg-key", "auth"}:
        return DENY, f"{c} {a0} is A4 (release, secrets, credentials) — Cecilia only."
    if a0 == "repo" and a1 in {"delete", "edit", "archive", "rename"}:
        return DENY, f"{c} repo {a1} is A4."
    if a0 == "api":
        if any("protection" in x for x in args):
            return DENY, "Branch protection is A4."
        write = (_has(args, "-X", "--method") and not any(x.upper() in {"GET", "-XGET", "--METHOD=GET"} for x in args)) \
            or any(re.match(r"^-X(POST|PUT|PATCH|DELETE)$", x, re.I) for x in args) \
            or _has(args, "-f", "-F", "--field", "--raw-field", "--input")
        if write:
            return (DENY, f"{c} api write. " + LOCAL_ONLY_MSG) if local_only else (ASK, f"{c} api write call (A3).")
        return ALLOW, ""
    reads = set(pol.get("git_host_read_verbs", []))
    if a0 in set(pol.get("git_host_write_verbs", [])):
        if local_only:
            return DENY, f"{c} {a0} writes to the git host. " + LOCAL_ONLY_MSG
        return ASK, f"{c} {a0} writes to the git host (A3)."
    if a0 in {"repo"} and a1 in {"clone", "view", "list"}:
        return ALLOW, ""
    if a0 in {"pr", "mr", "issue", "workflow", "run", "label", "variable", "repo", "gist", "project", "cache",
              "ruleset", "codespace", "discussion", "note", "snippet", "ci", "pipeline", "job", "milestone"} and a1:
        if a1 in reads:
            return ALLOW, ""
        if a0 in {"pr", "mr"} and a1 in {"checkout"}:
            return ALLOW, ""
        if local_only:
            return DENY, f"{c} {a0} {a1} is visible to others. " + LOCAL_ONLY_MSG
        return ASK, f"{c} {a0} {a1} is visible to others (A3) — Cecilia approves this exact action."
    return ALLOW, ""


def _decide_migration(c, args, env, pol):
    """Migrations: drop/reset/deploy/remote → ask; applying to a DB that looks like production → deny; staging → ask;
    applying to the local development DB → allowed (dump it first, git.md §4)."""
    name = c
    rest = list(args)
    if c in INTERPRETERS or re.match(r"^python[0-9.]+$", c):
        if rest and rest[0] == "-m":
            name, rest = rest[1] if len(rest) > 1 else "", rest[2:]
        elif rest and rest[0].endswith(("manage.py",)):
            name, rest = "manage.py", rest[1:]
    if c in {"bundle", "bin/rails", "./bin/rails"} and rest[:1] == ["exec"]:
        name, rest = cmd_name(rest[1]) if len(rest) > 1 else "", rest[2:]
    if c.endswith("manage.py"):
        name = "manage.py"
    pos = [a for a in rest if not a.startswith("-")]
    target = _env_target(env, rest, pol)
    for seq in pol.get("migration_ask", []):
        if seq[0] == name and _seq_in(seq, pos):
            if target == "prod":
                return DENY, f"`{' '.join(seq)}` against production — A4. Cecilia runs it with a backup and a rollback."
            return ASK, f"`{' '.join(seq)}` changes, deploys or wipes a database (A3) — say which database; dump it first."
    for seq in pol.get("migration_apply", []):
        if seq[0] == name and _seq_in(seq, pos):
            if target == "prod":
                return DENY, f"`{' '.join(seq)}` against production — A4. Cecilia runs it."
            if target == "staging":
                return ASK, f"`{' '.join(seq)}` against a shared (staging) database — A3."
            return None       # local development DB: allowed; the dump-first rule is in git.md §4
    return None


def _decide_scripts(c, args, env, pol):
    """npm/pnpm/yarn/bun scripts, task runners and deploy-named scripts: deploy/release words → ask; with prod → deny."""
    words = [w.lower() for w in pol.get("deploy_words", [])]
    destructive = [w.lower() for w in pol.get("migration_script_destructive_words", [])]
    names = []
    if c in {"npm", "pnpm", "yarn", "bun"}:
        pos = _positionals(args, {"--prefix", "-C", "--dir", "--filter", "-F", "-w", "--workspace", "--cwd"})
        if pos and pos[0] in {"run", "run-script", "rum", "urn"}:
            names = pos[1:2]
        elif c in {"pnpm", "yarn", "bun"} and pos and pos[0] not in {"install", "i", "add", "remove", "rm", "up",
                                                                        "update", "upgrade", "link", "dlx", "exec",
                                                                        "create", "init", "why", "list", "ls", "test",
                                                                        "info", "outdated", "audit", "config"}:
            names = pos[:1]
    elif c in set(pol.get("task_runners", [])):
        names = [a for a in args if not a.startswith("-") and "=" not in a][:3]
    elif re.search(r"(^|/)[^/]*\.(sh|ps1|bat|cmd|py|js|ts)$", c) or (c in SHELLS | {"pwsh", "powershell"} | INTERPRETERS
                                                                     and args and not args[0].startswith("-")):
        script = c if re.search(r"\.(sh|ps1|bat|cmd|py|js|ts)$", c) else args[0]
        names = [re.split(r"[\\/]", script)[-1]]
    if not names:
        return None
    blob = " ".join(names).lower()
    if any(re.search(rf"(^|[^a-z]){re.escape(w)}([^a-z]|$)", blob) for w in pol.get("deploy_safe_words", [])):
        return None           # deploy:check, release-notes, publish:dry-run — reads, not releases
    if any(re.search(rf"(^|[^a-z]){re.escape(w)}", blob) for w in words):
        if PROD.search(blob) or PROD.search(" ".join(args)) or _env_target(env, args, pol) == "prod":
            return DENY, f"`{c} … {names[0]}` deploys/releases to production — A4. Prepare the command for Cecilia."
        return ASK, f"`{c} … {names[0]}` deploys, releases or uploads (A3) — Cecilia approves the target."
    if any(re.search(rf"(^|[^a-z]){re.escape(w)}", blob) for w in destructive) and re.search(r"db|data|schema|migrat", blob):
        return ASK, f"`{c} … {names[0]}` resets or drops data (A3) — dump the database first."
    return None


CONTROL_PATHS = [".cecilia", ".claude/settings", ".claude/hooks", ".claude/agents", ".agents/hooks",
                 ".agents/agents", ".mcp.json"]
SOFT_CONTROL_PATHS = [".claude/skills", ".agents/skills", PW_CONFIG]
HARMLESS_CONTROL = {".cecilia/run.sqlite", ".cecilia/guard.log"}   # the ledger and log roles may use


def _norm_arg(x: str) -> str:
    """Lower-case, forward slashes, `a/b/../c` collapsed, the ledger/log paths blanked out."""
    x = x.lower().replace("\\", "/").strip("'\"")
    if ".." in x:
        x = posixpath.normpath(x)
    for ok in HARMLESS_CONTROL:
        if x == ok or x.endswith("/" + ok):
            return ""
    return x


def _outputs(t):
    """Paths a download or extraction command writes to (`curl -o F`, `tar -C D`, `-OutFile F`)."""
    flags = OUTPUT_FLAGS.get(t[0], set())
    out = []
    for i, x in enumerate(t[1:], start=1):
        name, eq, val = x.partition("=")
        if name.lower() in flags:
            out.append(val if eq else (t[i + 1] if i + 1 < len(t) else ""))
    if t[0] in {"curl"} and _has(t, "-O", "--remote-name"):
        urls = [x for x in t[1:] if re.match(r"^https?://", x)]
        out += [u.rstrip("/").split("/")[-1].split("?")[0] for u in urls]
    return out


CONTROL_PARENTS = {".claude", ".agents", ".playwright"}   # a write INTO these folders can create control files
COPY_CMDS = {"cp", "rsync", "install", "ln"}   # mv also removes its source: all arguments count
CD_CMDS = {"cd", "pushd", "set-location", "sl", "chdir", "push-location"}


def _hits(prot: str, text: str) -> bool:
    """`prot` appears as a path (segment boundaries): `.cecilia/x` yes, `settings.json.cecilia-suggested` no."""
    return re.search(r"(^|[/\s'\"(=,])" + re.escape(prot) + r"([/.'\"),\s]|$)", text) is not None


def _is_writer(t) -> bool:
    return t[0] in WRITE_CMDS or (t[0] == "sed" and any(x.startswith("-i") for x in t[1:])) or bool(_outputs(t)) \
        or (t[0] == "git" and (_positionals(t[1:], {"-C", "-c"})[:1] or [""])[0] in GIT_FILE_WRITES)


def _readonly_tool(t) -> bool:
    """`python .cecilia/bin/cecilia_guard.py --explain …` (and the doctor without --fix) only read."""
    if not (t[0] in INTERPRETERS or re.match(r"^python[0-9.]+$", t[0])) or len(t) < 2:
        return False
    script = t[1].replace("\\", "/").split("/")[-1].lower()
    return script in {x.lower() for x in POLICY.get("guard_readonly_tools", [])} and "--fix" not in t


def _writes_control(t, prot, hard):
    """Does this simple command write `prot`? Soft paths (skills, browser config) only count file writers;
    hard paths (.cecilia, host settings) also count interpreters, .NET writes and git file operations."""
    if _readonly_tool(t):
        t = [t[0]] + t[2:]
    args = [_norm_arg(x) for x in t[1:]]
    if t[0] in COPY_CMDS and t[0] != "ln":    # a copy only writes its destination; a link to a control path counts
        tgt = [t[i + 1] for i, x in enumerate(t[:-1]) if x in {"-t", "--target-directory", "-destination"}]
        pos = _positionals(t[1:], {"-t", "--target-directory", "-destination", "-path", "-literalpath"})
        args = [_norm_arg(x) for x in (tgt or pos[-1:])]
    parent = prot.split("/")[0] if "/" in prot else None
    into_parent = parent in CONTROL_PARENTS and any(x.rstrip("/.") == parent for x in args + [_norm_arg(o) for o in _outputs(t)])
    if not into_parent and not any(_hits(prot, x) for x in args) and \
            not (hard and DOTNET_WRITE.search(t[0]) and _hits(prot, t[0].lower())):
        return False
    c = t[0]
    if c in WRITE_CMDS or (c == "sed" and any(x.startswith("-i") for x in t[1:])) or \
            _has(t, "--dir", "--target", "--output-dir") or any(_hits(prot, _norm_arg(o)) for o in _outputs(t)) or \
            (into_parent and _is_writer(t)):
        return True
    if c == "git" and _positionals(t[1:], {"-C", "-c"})[:1] and _positionals(t[1:], {"-C", "-c"})[0] in GIT_FILE_WRITES:
        return True
    return hard and (c in INTERPRETERS or bool(re.match(r"^python[0-9.]+$", c)) or bool(DOTNET_WRITE.search(c)))


def shell_write_targets(toks, redirects):
    """Files a simple command writes (by its arguments) plus its redirect targets."""
    c, args = toks[0], toks[1:]
    out = list(redirects)
    if c in {"cp", "install", "ln", "rsync"}:
        tgt = [args[i + 1] for i, x in enumerate(args[:-1]) if x in {"-t", "--target-directory"}]
        pos = _positionals(args, {"-t", "--target-directory", "-m", "--mode", "-o", "-g", "-S"})
        out += tgt or pos[-1:]
    elif c == "mv":
        out += _positionals(args, {"-t", "--target-directory", "-S"})
    elif c in {"rm", "rmdir", "unlink", "shred", "touch", "mkdir", "chmod", "chown", "truncate"}:
        pos = _positionals(args, {"-m", "--mode", "-s", "--size", "-r", "--reference"})
        out += pos[1:] if c in {"chmod", "chown"} else pos
    elif c == "tee":
        out += _positionals(args)
    elif c == "sed" and any(x.startswith("-i") for x in args):
        pos = _positionals(args, {"-e", "-f", "--expression", "--file"})
        explicit_e = _has(args, "-e", "--expression", "-f", "--file")
        out += pos if explicit_e else pos[1:]
    elif c == "dd":
        out += [x[3:] for x in args if x.startswith("of=")]
    elif c in OUTPUT_FLAGS:
        out += _outputs(toks)
    return [p for p in out if p and p not in {"-", "/dev/null", "nul", "NUL", "$null"} and "$" not in p
            and not p.startswith(("&", "/dev/", "/proc/"))]


PERSIST_FILES = re.compile(r"(\.bashrc|\.zshrc|\.bash_profile|\.zprofile|\.zshenv|(^|[/\\~\s])\.profile\b|\.bash_aliases|"
                           r"config\.fish|\.gitconfig|\$profile\b|_profile\.ps1|\.bash_logout)", re.I)
BYPASS_FLAGS = re.compile(r"--dangerously-skip-permissions|--permission-mode[= ]+bypasspermissions|"
                          r"--dangerously-bypass-approvals|--yolo\b|--allow-dangerously", re.I)
B64_TOKEN = re.compile(r"[A-Za-z0-9+/]{8,}={0,2}")
CODE_EXEC = re.compile(r"system|subprocess|popen|exec|spawn|child_process|shell|runtime\.getruntime", re.I)
EXE_DOWNLOAD = re.compile(r"\.(msi|exe|sh|ps1|bat|cmd|deb|rpm|pkg|dmg|appimage|jar|run|bin|vbs|scr)$", re.I)


def _decoded_commands(cmd: str, segs) -> list:
    """Commands hidden in base64 (`echo … | base64 -d`, PowerShell -EncodedCommand) or in interpreter code
    (`python -c "os.system('…')"`), decoded so they can be judged like any other command."""
    out = []
    low = cmd.lower()
    if re.search(r"base64\s+(-d|--decode|-D)\b|frombase64string|b64decode|atob\(|-e(nc(odedcommand)?)?\s", low):
        for tok in B64_TOKEN.findall(cmd):
            if len(tok) % 4:
                continue
            try:
                raw = base64.b64decode(tok, validate=True)
            except (ValueError, binascii.Error):
                continue
            for enc in ("utf-8", "utf-16-le"):
                try:
                    text = raw.decode(enc)
                except UnicodeDecodeError:
                    continue
                if len(text) >= 4 and all(ch.isprintable() or ch in "\n\t" for ch in text):
                    out.append(text)
                    break
    for t in segs:
        if t and (t[0] in INTERPRETERS or re.match(r"^python[0-9.]+$", t[0])):
            for i, a in enumerate(t[1:-1], start=1):
                if a in {"-c", "-e", "-r", "--eval", "-E"} and CODE_EXEC.search(t[i + 1]):
                    out += [x or y for x, y in re.findall(r"'([^']{3,})'|\"([^\"]{3,})\"", t[i + 1])]
    return out


# --------------------------------------------------------------------------- v20.1: orchestrator commands

ORCH_READ_CMDS = {"ls", "cat", "head", "tail", "grep", "rg", "findstr", "find", "wc", "pwd", "echo", "test", "[",
                  "test-path", "get-location", "write-output", "write-host", "cd", "pushd", "popd", "true", "false"}
ORCH_SCRIPTS = ("workflow.py", "cecilia_check.py", "capacity.py")
ORCH_GIT = {"status", "log", "diff", "show", "rev-parse", "ls-files", "branch", "worktree", "switch", "checkout",
            "merge"}
FIND_RUNS = {"-exec", "-execdir", "-delete", "-ok", "-okdir", "-fprint", "-fprint0", "-fprintf", "-fls"}
PY_SAFE_OPTS = {"-u", "-B", "-E", "-s", "-S", "-I", "-O", "-OO", "-q"}


def _orch_msg(shown: str) -> str:
    return (f"orchestrator: '{shown}' is specialist work - dispatch it to the right role (discovery reads the "
            "cluster/repo, devops runs infra commands) with workflow.py brief.")


def _orch_python(c: str, args: list, cwd):
    """`python|python3|py [-3] <path>/scripts/{workflow,cecilia_check,capacity}.py ...` (not from tensura/)."""
    i = 0
    while i < len(args) and args[i].startswith("-"):
        a = args[i]
        if a == "-m" and args[i + 1:i + 2] == ["cecilia"]:
            return ALLOW, ""                       # `python -m cecilia …` = the cecilia CLI (judged as such)
        if c == "py" and re.fullmatch(r"-[23](\.\d+)?(-(32|64))?", a):
            i += 1
        elif a in PY_SAFE_OPTS:
            i += 1
        elif a in {"-X", "-W"}:
            i += 2
        else:
            return DENY, _orch_msg(f"{c} {a}") + " The orchestrator runs only Cecilia's scripts " \
                "(workflow.py, cecilia_check.py, capacity.py)."
    if i >= len(args):
        return DENY, _orch_msg(c)
    script = args[i]
    low = script.lower().replace("\\", "/")
    here = str(cwd or "").lower().replace("\\", "/")
    named = any(low.endswith(("scripts/" + s, "scripts" + s)) or (low == s and here.endswith("/scripts"))
                for s in ORCH_SCRIPTS)
    if not named or "tensura" in low or "/tensura/" in here + "/":
        return DENY, _orch_msg(f"{c} {script}") + " The orchestrator runs only Cecilia's own scripts " \
            "(<skill>/scripts/workflow.py, cecilia_check.py, capacity.py), never a script under tensura/."
    return ALLOW, ""


def _orch_git(args: list, cwd):
    _, sub, rest = _git_sub(args)
    shown = f"git {sub}".strip()
    if sub not in ORCH_GIT:
        return DENY, _orch_msg(shown) + " The orchestrator's git: status, log, diff, show, rev-parse, ls-files, " \
            "branch, worktree list|add|remove|prune, switch/checkout of task branches, merge into int/<TASK>."
    if sub in {"diff", "log", "show"} and _has(rest, "--output"):
        return DENY, _orch_msg(f"{shown} --output")
    if sub == "branch":
        bad_long = {"--delete", "--move", "--copy", "--force", "--set-upstream-to", "--unset-upstream",
                     "--edit-description"}
        if _has(rest, *bad_long) or any(re.match(r"^-[a-zA-Z]*[dDmMcCfu]", r) for r in rest if not r.startswith("--")):
            return DENY, _orch_msg(f"{shown} {' '.join(rest)}") + " (list or create branches only)"
    if sub == "worktree":
        verb = next((r for r in rest if not r.startswith("-")), "")
        if verb not in {"list", "add", "remove", "prune"}:
            return DENY, _orch_msg(f"{shown} {verb}".strip())
    if sub == "checkout":
        pos = _positionals(rest, {"-b", "-B", "--orphan"})
        here = Path(cwd) if cwd is not None else None
        if "--" in rest or "." in pos or len(pos) > 1 or \
                _has(rest, "-p", "--patch", "-f", "--force", "--ours", "--theirs", "-m", "--merge") or \
                (here is not None and pos and not _has(rest, "-b", "-B", "--orphan") and (here / pos[0]).exists()):
            return DENY, _orch_msg(f"{shown} {' '.join(rest)}") + " (the orchestrator switches branches; it " \
                "never checks out files)"
    return ALLOW, ""


def orch_segment(toks: list, ctx: dict):
    """v20.1: what the orchestrator may run (a simple command); everything else is dispatched."""
    c, args = toks[0], toks[1:]
    extra = {cmd_name(x) for x in (ctx.get("cfg") or {}).get("orchestration", {}).get("orchestrator_commands", [])}
    if c in extra or c == "cecilia":
        return ALLOW, ""
    if c in {"python", "python3", "py"} or re.match(r"^python[0-9.]+$", c):
        return _orch_python(c, args, ctx.get("cwd"))
    if c == "git":
        return _orch_git(args, ctx.get("cwd"))
    if c in ORCH_READ_CMDS:
        if c == "find" and any(a.lower() in FIND_RUNS for a in args):
            return DENY, _orch_msg("find " + next(a for a in args if a.lower() in FIND_RUNS))
        if c == "rg" and _has(args, "--pre"):
            return DENY, _orch_msg("rg --pre")
        return ALLOW, ""
    return DENY, _orch_msg(" ".join(toks)[:80])


def _is_orchestrator(root, cfg) -> bool:
    if not AGENT or root is None:
        return False
    rv = role_view(root, cfg, AGENT)
    return bool(rv and rv["orchestrator"])


# --------------------------------------------------------------------------- secret dumps (all agents)

KUBE_VALUE_FLAGS = {"-n", "--namespace", "--context", "--kubeconfig", "--cluster", "--user", "-l", "--selector",
                    "-o", "--output", "-f", "--filename", "--field-selector", "-L", "--label-columns", "--sort-by",
                    "--template", "-c", "--container", "--server", "-s", "--token", "--as", "--as-group",
                    "--request-timeout", "-v", "--chunk-size", "--show-kind"}
ETCD_VALUE_FLAGS = {"--endpoints", "--cacert", "--cert", "--key", "--user", "--password", "-w", "--write-out",
                    "--dial-timeout", "--command-timeout", "--rev", "--limit", "--order", "--sort-by",
                    "--consistency"}


def _kube_output(args: list):
    for i, a in enumerate(args):
        if a in {"-o", "--output"}:
            return args[i + 1] if i + 1 < len(args) else ""
        if a.startswith("--output="):
            return a.split("=", 1)[1]
        if a.startswith("-o") and not a.startswith("--") and len(a) > 2:
            return a[2:].lstrip("=")
    return "go-template" if _has(args, "--template") else None


def secret_dump(toks: list, pol: dict):
    """'kube' = `kubectl|oc get <…secret…> -o yaml|json|jsonpath|go-template…` (prints secret values);
    'etcd' = `etcdctl get` of the secrets keyspace; None otherwise."""
    c, args = toks[0], list(toks[1:])
    if c in {"k3s", "microk8s"} and args[:1] == ["kubectl"]:
        c, args = "kubectl", args[1:]
    if c in set(pol.get("secret_dump_clis", ["kubectl", "oc"])):
        pos = _positionals(args, KUBE_VALUE_FLAGS)
        if not pos or pos[0] != "get":
            return None
        names = {n.lower() for n in pol.get("secret_resources", ["secret", "secrets"])}
        if not any(item.split("/")[0].split(".")[0].lower() in names for p in pos[1:] for item in p.split(",")):
            return None
        fmt = _kube_output(args)
        formats = {f.lower() for f in pol.get("secret_dump_formats", [])}
        return "kube" if fmt is not None and re.split(r"[=:]", fmt, 1)[0].lower() in formats else None
    if c == "etcdctl":
        pos = _positionals(args, ETCD_VALUE_FLAGS)
        if not pos or pos[0] != "get" or _has(args, "--keys-only"):
            return None
        prefix = str(pol.get("etcd_secret_prefix") or "/registry/secrets")
        keys = pos[1:3]
        ranged = _has(args, "--prefix", "--from-key")
        if any(k.startswith(prefix) or (ranged and prefix.startswith(k)) for k in keys) or \
                (not keys and ranged) or (len(keys) == 2 and keys[0] <= prefix < keys[1]):
            return "etcd"
    return None


def decide_command(cmd: str, root: Path | None = None, cwd: Path | None = None, detail: list | None = None,
                   _depth: int = 0):
    if POLICY_ERROR:
        return DENY, POLICY_ERROR
    cmd = normalize_command(cmd)
    if len(cmd) > MAX_COMMAND:
        return ASK, "Command too long for the guard to check (A3) — split it or ask Cecilia."
    if BYPASS_FLAGS.search(cmd):
        return DENY, "Starting an agent with its permission checks switched off is never allowed (A4)."
    if re.search(r"((ba|z|da|k)?sh|source|\.)\s+<\(\s*(curl|wget|iwr|irm|invoke-webrequest|invoke-restmethod)\b", cmd, re.I) or \
            re.search(r"(ba|z|da|k)?sh\s+-c\s+[\"']?\$\(\s*(curl|wget)\b", cmd, re.I):
        return DENY, "Running a script straight from the network is never allowed."
    if PERSIST_FILES.search(cmd) and (re.search(r">|\b(add-content|set-content|out-file|tee|tee-object|sed|cp|mv|ln|"
                                                r"install|truncate|perl|python3?|node)\b|\bac\b|\bsc\b", cmd, re.I)):
        return DENY, ("Changing a shell or git profile (.bashrc, $PROFILE, .gitconfig…) persists beyond this task — "
                      "never (A4). Tell Cecilia what you need.")
    if _depth < 2:
        hidden = _decoded_commands(cmd, split_segments(cmd) + split_segments(cmd, windows_paths=False))
        for h in hidden:
            hd, hr = decide_command(h, root, cwd, None, _depth + 1)
            if hd == DENY:
                return DENY, f"Hidden (encoded/embedded) command: {hr}"
    if re.search(r"(curl|wget|iwr|irm|invoke-webrequest|invoke-restmethod)[^|]*\|\s*(sudo\s+)?"
                 r"((ba|z|da|k)?sh|iex|invoke-expression|pwsh|powershell|cmd|python3?|node|perl|ruby)\b", cmd, re.I) or \
            re.search(r"base64\s+(-d|--decode)[^|]*\|\s*(ba|z|da)?sh\b", cmd):
        return DENY, "Piping downloaded or decoded content into a shell or interpreter is never allowed."
    segs = split_segments(cmd) + split_segments(cmd, windows_paths=False)
    targets = [_norm_arg(t) for t in REDIRECT.findall(cmd)]
    # Where relative writes land: the hook's cwd and any `cd` in the command itself.
    here = []
    if root is not None and cwd is not None:
        rel = to_rel(str(cwd), root, root)
        if rel and rel != ".":
            here.append(strip_worktree(rel).lower())
    here += [_norm_arg(t[1]) for t in segs if t[0] in CD_CMDS and len(t) > 1]
    writes_here = bool(targets) or any(_is_writer(t) or (t[0] in INTERPRETERS and not _readonly_tool(t)) for t in segs)
    for prot in CONTROL_PATHS + SOFT_CONTROL_PATHS:
        hard = prot in CONTROL_PATHS
        base = prot.split("/")[0]
        in_control_dir = writes_here and any(h == base or h.startswith(base + "/") or _hits(prot, h) for h in here)
        if in_control_dir or any(_hits(prot, t) for t in targets) or any(_writes_control(t, prot, hard) for t in segs):
            if hard:
                return DENY, (f"This command could modify {prot} — the guard, approvals, host settings, agents and "
                              "MCP config are Cecilia's to change.")
            return DENY, (f"This command could modify {prot} — installed skills and the browser config are "
                          "Cecilia's to change (re-run the installer).")
    low = cmd.lower()
    if re.search(r"playwright_mcp_(config|allow_unrestricted|cdp|extension)", low):
        return ASK, "Overriding the Playwright configuration from the environment (A3)."
    if re.search(r"\|\s*(sudo\s+)?((ba|z|da|k|tc|c|a)?sh|fish|pwsh|powershell|cmd|iex|invoke-expression)(\.exe)?"
                 r"(\s+-{1,2}[\w-]*)*\s*($|[;&|)])", cmd, re.I):
        return ASK, "Piping text into a shell runs commands nobody has read (A3)."
    cfg = load_config(root) if root is not None else default_config_view()
    ctx = {"cwd": cwd, "root": root, "cfg": cfg, "policy": policy(cfg), "orch": _is_orchestrator(root, cfg)}
    return _both_readings(cmd, ctx, detail)


def _both_readings(cmd: str, ctx: dict, detail=None):
    """Judge the Windows reading (`a\\b` = path) and the POSIX reading separately; keep the stricter."""
    first = _decide_segs(split_segments(cmd, with_env=True), ctx, detail)
    second = _decide_segs(split_segments(cmd, windows_paths=False, with_env=True), ctx)
    return first if RANK[first[0]] >= RANK[second[0]] else second


def decide_command_segments(cmd: str, ctx: dict):
    return _both_readings(cmd, ctx)


def _decide_segs(segs_env, ctx, detail=None):
    """Judge each simple command in order, carrying the state a compound command creates: the directory after
    `cd`, the branch after `git switch/checkout`, files a download wrote (and whether they are then run)."""
    worst, why = ALLOW, ""
    state_cwd = ctx.get("cwd")
    branch = None
    downloaded: set = set()
    root = ctx.get("root")
    seen = set()
    aliases: dict = {}
    dumping = False
    for toks, env in segs_env:
        key = (tuple(toks), tuple(sorted(env.items())))
        if key in seen:
            continue
        seen.add(key)
        toks, redirects = split_redirects(toks)
        dumping = dumping or (bool(toks) and secret_dump(toks, ctx.get("policy") or POLICY) is not None)
        if dumping and ([x for x in redirects if x not in {"-", "/dev/null", "nul", "NUL", "$null"}
                         and not x.startswith("&")] or (toks[:1] == ["tee"] and _positionals(toks[1:]))):
            why = ("This writes cluster secrets to disk in plain text — never (A4). Read names only (no -o), "
                   "or ask Cecilia.")
            if detail is not None:
                detail.append({"cmd": " ".join(toks)[:120], "decision": DENY, "reason": why})
            return DENY, why
        if not toks:
            continue
        c = toks[0]
        if c == "alias" and len(toks) > 1 and "=" in toks[1]:
            name, _, val = toks[1].partition("=")
            aliases[name] = val
            continue
        if c in aliases:
            ad, ar = decide_command_segments(aliases[c] + " " + " ".join(shlex.quote(x) for x in toks[1:]), ctx)
            if ad == DENY:
                return ad, f"(alias {c}) {ar}"
            if ad == ASK and worst is ALLOW:
                worst, why = ad, f"(alias {c}) {ar}"
        # ---- state carried along the command ----
        if c in CD_CMDS | {"cd"}:
            if len(toks) > 1 and state_cwd is not None and not toks[1].startswith("-"):
                p = Path(os.path.expanduser(toks[1]))
                state_cwd = p if p.is_absolute() else Path(os.path.normpath(str(Path(state_cwd) / p)))
            continue
        if c == "git":
            _, sub, rest = _git_sub(toks[1:])
            if sub in {"switch", "checkout"}:
                new = None
                for flag in ("-c", "-C", "-b", "-B", "--create", "--force-create", "--orphan"):
                    v = _flag_value(rest, flag)
                    if v:
                        new = v
                if new is None and _has(rest, "--detach", "-d"):
                    new = "(detached)"
                if new is None:
                    pos = [r for r in rest if not r.startswith("-")]
                    if pos and "--" not in rest and (sub == "switch" or state_cwd is None
                                                     or not (Path(state_cwd) / pos[0]).exists()):
                        new = pos[0] if not re.match(r"^[0-9a-f]{7,40}$|~|\^", pos[0]) else "(detached)"
                if new:
                    branch = new
        sub_ctx = {**ctx, "cwd": state_cwd, "branch_override": branch, "env": env}
        d, r = decide_segment(toks, sub_ctx)
        if ctx.get("orch") and d != DENY:
            od, orr = orch_segment(toks, sub_ctx)
            if RANK[od] > RANK[d]:
                d, r = od, orr
        # ---- files this command writes: profiles, CONTROLLED scope, git flow ----
        if root is not None and state_cwd is not None and d != DENY:
            for target in shell_write_targets(toks, redirects):
                if target in downloaded:
                    continue
                wd, wr = decide_write(target, Path(state_cwd), Path(root), via="shell",
                                      branch=branch if branch and branch != "(detached)" else None)
                if RANK[wd] > RANK[d]:
                    d, r = wd, wr
        # ---- download, then run it ----
        outs = _outputs(toks)
        if outs:
            downloaded.update(o.lstrip("./") for o in outs)
            if c in {"curl", "wget"} and any(EXE_DOWNLOAD.search(o) for o in outs) and RANK[d] < RANK[ASK]:
                d, r = ASK, "Downloading an installer or executable (A3) — Cecilia approves the source first."
        runner = c in SHELLS | {"pwsh", "powershell"} | INTERPRETERS or c.startswith("./")
        target = (toks[0][2:] if c.startswith("./") else (toks[1] if len(toks) > 1 else "")).lstrip("./")
        if runner and target and target in downloaded:
            d2, r2 = ASK, f"Running '{target}', which this command just downloaded (A3) — Cecilia reads it first."
            if RANK[d2] > RANK[d]:
                d, r = d2, r2
        if detail is not None:
            detail.append({"cmd": " ".join(toks)[:120], "decision": d or "allow", "reason": r,
                           **({"branch": branch} if branch else {})})
        if d == DENY:
            return d, r
        if d == ASK and worst is ALLOW:
            worst, why = d, r
    return worst, why


# --------------------------------------------------------------------------- connector (MCP) tools

def _mcp_words(action: str):
    return [w for w in re.split(r"[_\-\s.]+|(?<=[a-z])(?=[A-Z])", action) if w]


def decide_mcp(name: str, root: Path | None = None, tool_input: dict | None = None):
    if POLICY_ERROR:
        return DENY, POLICY_ERROR
    cfg = load_config(root)
    pol = policy(cfg)
    if _is_orchestrator(root, cfg):
        allowed = cfg["orchestration"]["orchestrator_mcp"]
        if not any(fnmatch.fnmatchcase(name, g) or fnmatch.fnmatchcase(name.lower(), g.lower()) for g in allowed):
            return DENY, (f"orchestrator: MCP tool '{name}' is specialist work - dispatch it to the right role "
                          "(discovery reads the cluster/repo/docs, devops runs infra tools) with workflow.py brief. "
                          "Only tools Cecilia lists in orchestration.orchestrator_mcp are the orchestrator's.")
    parts = name.split("__")
    action = parts[-1] if len(parts) > 1 else name
    server = parts[1] if len(parts) > 2 else ""
    if "playwright" in server.lower():
        url = str((tool_input or {}).get("url") or "")
        if action in {"browser_install"}:
            return ASK, "Installing a browser downloads code (A3)."
        if url and not PW_LOCAL.match(url):
            return ASK, f"Opening '{url}' leaves localhost (A3) — Cecilia approves the site."
        if action in {"browser_run_code"}:
            return ASK, "browser_run_code runs code outside the page (A3)."
        if action in {"browser_file_upload"}:
            return ASK, "Uploading a file from this machine into a page (A3)."
        return ALLOW, ""
    words = [w.lower() for w in _mcp_words(action)]
    read_v, ask_w = set(pol["mcp_read_verbs"]), set(pol["mcp_ask_words"])
    deny_v, deny_w = set(pol["mcp_deny_verbs"]), set(pol["mcp_deny_words"])
    reading = bool(words) and (words[0] in read_v or words[-1] in read_v) and \
        not ((set(words) - {"request", words[0], words[-1]}) & (ask_w | deny_v)) and \
        not ({words[0], words[-1]} & (ask_w | deny_v) - read_v)
    if not reading and (set(words) & deny_w or ("delete" in words and ({"repo", "repository"} & set(words)))
                        or ("deploy" in words and ({"prod", "production"} & set(words)))):
        return DENY, f"Connector action '{action}' is A4 (merge, approve, release, secrets, permissions) — Cecilia only."
    writes = not reading and bool(set(words) & ask_w)
    host = any(s in server.lower() for s in pol.get("mcp_git_host_servers", [])) or \
        any(w in {"github", "gitlab", "bitbucket"} for w in words)
    if writes and host and cfg["git"].get("local_only", True):
        return DENY, f"Git-host connector write '{action}'. " + LOCAL_ONLY_MSG
    if re.search(pol.get("mcp_design_servers_regex", "(penpot|figma)"), server, re.I) and writes:
        if not role_enabled(cfg, "cecilia-ui"):
            return DENY, (f"Design-tool write '{action}' blocked: cecilia-ui is off in .cecilia/config.json. "
                          "Cecilia turns it on herself; reading the design is still allowed.")
        if cfg["ui"]["design_writes"] == "allow":
            return ALLOW, ""
        return ASK, (f"Design-tool write '{action}' changes a shared design file (A3) — Cecilia approves it "
                     "(or sets ui.design_writes to \"allow\" in .cecilia/config.json).")
    if writes:
        return ASK, f"Connector action '{action}' changes something outside this machine (A3)."
    return ALLOW, ""


# --------------------------------------------------------------------------- tool rules (Claude Code)

JS_IMPORT = re.compile(r"""(?:^|[\s;])(?:import\s+(?:[^'"]*?\s+from\s+)?|export\s+[^'"]*?\s+from\s+|require\(\s*|import\(\s*)['"]([^'"]+)['"]""", re.M)
PY_IMPORT = re.compile(r"^\s*(?:from\s+([A-Za-z_][\w.]*)\s+import|import\s+([A-Za-z_][\w.]*(?:\s*,\s*[A-Za-z_][\w.]*)*))", re.M)
JAVA_IMPORT = re.compile(r"^\s*import\s+(?:static\s+)?([a-z][\w]*\.[\w.]+)", re.M)
GO_IMPORT = re.compile(r'"([a-z0-9.-]+\.[a-z]+/[^"]+)"')
NODE_BUILTINS = {"fs", "path", "os", "url", "util", "http", "https", "crypto", "stream", "events", "child_process",
                 "assert", "buffer", "zlib", "net", "tls", "dns", "readline", "process", "timers", "worker_threads",
                 "querystring", "cluster", "module", "vm", "perf_hooks", "string_decoder", "async_hooks", "v8", "test"}


# Python < 3.10 has no sys.stdlib_module_names: the top-level standard modules (3.11 list), for tool_rules.
PY39_STDLIB = frozenset("""
abc aifc antigravity argparse array ast asynchat asyncio asyncore atexit audioop base64 bdb binascii bisect
builtins bz2 cProfile calendar cgi cgitb chunk cmath cmd code codecs codeop collections colorsys compileall
concurrent configparser contextlib contextvars copy copyreg crypt csv ctypes curses dataclasses datetime dbm
decimal difflib dis distutils doctest email encodings ensurepip enum errno faulthandler fcntl filecmp
fileinput fnmatch fractions ftplib functools gc genericpath getopt getpass gettext glob graphlib grp gzip
hashlib heapq hmac html http idlelib imaplib imghdr imp importlib inspect io ipaddress itertools json keyword
lib2to3 linecache locale logging lzma mailbox mailcap marshal math mimetypes mmap modulefinder msilib msvcrt
multiprocessing netrc nis nntplib nt ntpath nturl2path numbers opcode operator optparse os ossaudiodev
pathlib pdb pickle pickletools pipes pkgutil platform plistlib poplib posix posixpath pprint profile pstats
pty pwd py_compile pyclbr pydoc pydoc_data pyexpat queue quopri random re readline reprlib resource
rlcompleter runpy sched secrets select selectors shelve shlex shutil signal site smtpd smtplib sndhdr socket
socketserver spwd sqlite3 sre_compile sre_constants sre_parse ssl stat statistics string stringprep struct
subprocess sunau symtable sys sysconfig syslog tabnanny tarfile telnetlib tempfile termios textwrap this
threading time timeit tkinter token tokenize tomllib trace traceback tracemalloc tty turtle turtledemo types
typing unicodedata unittest urllib uu uuid venv warnings wave weakref webbrowser winreg winsound wsgiref
xdrlib xml xmlrpc zipapp zipfile zipimport zlib zoneinfo
""".split())


def _packages(text: str, suffix: str, root: Path | None) -> set:
    """Third-party package names a piece of code imports (relative, alias and standard-library imports skipped)."""
    pk = set()
    if suffix in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte"}:
        for m in JS_IMPORT.finditer(text):
            s = m.group(1)
            if s.startswith((".", "/", "@/", "~/", "#", "node:", "virtual:", "$")) or s.split("/")[0] in NODE_BUILTINS:
                continue
            pk.add("/".join(s.split("/")[:2]) if s.startswith("@") else s.split("/")[0])
    elif suffix == ".py":
        std = set(getattr(sys, "stdlib_module_names", ())) or PY39_STDLIB
        for m in PY_IMPORT.finditer(text):
            for name in filter(None, [m.group(1)] + (m.group(2) or "").split(",")):
                top = name.strip().split(".")[0]
                if not top or top in std or top == "__future__":
                    continue
                if root is not None and ((root / top).is_dir() or (root / f"{top}.py").is_file()
                                         or (root / "src" / top).is_dir()):
                    continue
                pk.add(top)
    elif suffix in {".java", ".kt", ".scala"}:
        for m in JAVA_IMPORT.finditer(text):
            name = m.group(1)
            if not name.startswith(("java.", "javax.", "kotlin.", "scala.", "jdk.", "sun.")):
                pk.add(".".join(name.split(".")[:3]))
    elif suffix == ".go":
        pk.update(m.group(1) for m in GO_IMPORT.finditer(text))
    return pk


def _transcript_blobs(data: dict) -> list:
    """The agent's own transcript(s): the session transcript and, inside a subagent, its sibling files."""
    out = []
    tp = data.get("transcript_path") or data.get("transcriptPath")    # Claude Code | Antigravity
    paths = []
    if tp:
        p = Path(tp)
        paths.append(p)
        aid = data.get("agent_id")
        if aid and p.parent.is_dir():
            paths += [q for q in p.parent.rglob(f"*{aid}*.jsonl")][:5]
    for p in paths:
        try:
            if p.is_file():
                with open(p, "rb") as fh:
                    size = p.stat().st_size
                    if size > 30_000_000:
                        fh.seek(size - 30_000_000)
                    out.append(fh.read().decode("utf-8", errors="replace"))
        except OSError:
            continue
    return out


def _tool_calls(blobs: list, patterns: list) -> list:
    """Inputs of tool calls whose name matches one of `patterns` (fnmatch), as lowercase JSON strings."""
    found = []
    for blob in blobs:
        for line in blob.splitlines():
            claude = '"tool_use"' in line
            if not claude and not any(k in line for k in ('"args"', '"Args"', '"arguments"', '"toolCall')):
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict):
                continue
            if claude:
                msg = rec.get("message")
                content = msg.get("content") if isinstance(msg, dict) else None
                for item in content if isinstance(content, list) else []:
                    if isinstance(item, dict) and item.get("type") == "tool_use":
                        name = str(item.get("name", ""))
                        if any(fnmatch.fnmatch(name.lower(), pat.lower()) for pat in patterns):
                            found.append(json.dumps(item.get("input", {}), ensure_ascii=False).lower())
                continue
            for item in _agy_calls(rec):          # Antigravity (format undocumented): {name, args|arguments}
                name = str(item.get("name") or item.get("Name") or "")
                if any(fnmatch.fnmatch(name.lower(), pat.lower()) for pat in patterns):
                    args = next((item[k] for k in ("args", "Args", "arguments", "input") if k in item), {})
                    found.append(json.dumps(args, ensure_ascii=False).lower())
    return found


def _agy_calls(node, depth=0) -> list:
    """Dicts that look like a tool call ({name, args|arguments|input}) anywhere inside a transcript entry."""
    if depth > 6:
        return []
    out = []
    if isinstance(node, dict):
        if (node.get("name") or node.get("Name")) and any(k in node for k in ("args", "Args", "arguments", "input")):
            out.append(node)
        for v in node.values():
            if isinstance(v, (dict, list)):
                out += _agy_calls(v, depth + 1)
    elif isinstance(node, list):
        for v in node[:200]:
            out += _agy_calls(v, depth + 1)
    return out


def check_tool_rules(data: dict, paths: list, cwd: Path, root: Path):
    """Claude Code only: the edit may need an earlier call to a required tool (e.g. context7 before new imports)."""
    cfg = load_config(root)
    rules = cfg.get("tool_rules") or []
    if not rules:
        return ALLOW, ""
    agent = data.get("agent_type") or "main"
    ti = data.get("tool_input") or {}
    new_text = str(ti.get("content") or ti.get("new_string") or "")
    old_text = str(ti.get("old_string") or "")
    for e in ti.get("edits") or []:
        if isinstance(e, dict):
            new_text += "\n" + str(e.get("new_string", ""))
            old_text += "\n" + str(e.get("old_string", ""))
    pol = policy(cfg)
    for rule in rules:
        if rule.get("enforce", "report") != "gate":
            continue
        roles = rule.get("roles")
        if roles and agent not in roles and not (agent == "main" and "main" in roles):
            continue
        globs = rule.get("paths") or pol.get("default_code_globs", [])
        for p in paths:
            rel = to_rel(p, cwd, root)
            if rel is None or not matches(strip_worktree(rel), globs):
                continue
            suffix = Path(rel).suffix.lower()
            before = old_text
            if not before and ti.get("content") is not None:
                try:
                    before = (Path(p) if Path(p).is_absolute() else cwd / p).read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    before = ""
            new_pk = _packages(new_text, suffix, root) - _packages(before, suffix, root)
            if not new_pk:
                continue
            calls = _tool_calls(_transcript_blobs(data), rule.get("tools", []))
            missing = sorted(pk for pk in new_pk if not any(pk.lower() in c or pk.split("/")[-1].lower() in c
                                                             for c in calls))
            if missing:
                return DENY, (f"tool rule '{rule.get('id', 'docs-first')}': before writing code that uses "
                              f"{', '.join(missing[:4])}, look it up with {' / '.join(rule.get('tools', []))} "
                              f"(resolve the library, then query the docs for what you use), then retry. "
                              f"{rule.get('why', '')}".strip())
    return ALLOW, ""


def prompt_reminder(root: Path) -> str:
    cfg = load_config(root)
    lines = []
    for r in cfg.get("tool_rules") or []:
        lines.append(f"- {r.get('id', 'rule')}: {r.get('when', 'when it applies')} → use {', '.join(r.get('tools', []))}"
                     f"{' (gate: edits are blocked until you do)' if r.get('enforce') == 'gate' else ''}.")
    if not lines:
        return ""
    return "Cecilia tool rules for this project:\n" + "\n".join(lines)


# --------------------------------------------------------------------------- host adapters

def extract(host: str, data: dict):
    """Return (kind, payload, cwd) with kind in {'command','write','mcp','dispatch','prompt','other'};
    payload = str, [paths], (tool, input) or the Agent/Task input."""
    if host == "claude":
        if data.get("hook_event_name") == "UserPromptSubmit":
            return "prompt", None, Path(data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
        tool = data.get("tool_name", "")
        ti = data.get("tool_input") or {}
        cwd = Path(data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
        if tool in {"Bash", "PowerShell"}:
            return "command", ti.get("command", ""), cwd
        if tool in {"Edit", "Write", "MultiEdit", "NotebookEdit"}:
            paths = [ti[k] for k in ("file_path", "notebook_path") if ti.get(k)]
            for e in ti.get("edits") or []:
                if isinstance(e, dict) and e.get("file_path"):
                    paths.append(e["file_path"])
            return "write", paths, cwd
        if tool.startswith("mcp__"):
            return "mcp", (tool, ti if isinstance(ti, dict) else {}), cwd
        if tool in {"Agent", "Task"}:
            return "dispatch", ti if isinstance(ti, dict) else {}, cwd
        return "other", None, cwd
    if host == "antigravity":
        call = data.get("toolCall") if isinstance(data.get("toolCall"), dict) else {}
        tool = str(call.get("name") or "")
        args = call.get("args") if isinstance(call.get("args"), dict) else {}
        ws = data.get("workspacePaths") if isinstance(data.get("workspacePaths"), list) else []
        cwd = Path(str(args.get("Cwd") or (ws[0] if ws else "") or os.getcwd()))
        if not call and "invocationNum" in data:
            return "prompt", None, cwd                  # PreInvocation: before each model call
        if tool == "run_command":
            return "command", args.get("CommandLine", ""), cwd
        if tool in {"write_to_file", "replace_file_content", "multi_replace_file_content"}:
            return "write", [args.get("TargetFile", "")], cwd
        if tool == "call_mcp_tool":
            return "mcp", _agy_mcp(args), cwd
        if tool.startswith("mcp__"):
            return "mcp", (tool, args), cwd
        if tool in {"invoke_subagent", "define_subagent"}:
            return "dispatch", _agy_dispatch(tool, args), cwd
        return "other", None, cwd                       # send_message, view_file, ask_question, manage_task...
    raise ValueError(f"unknown host {host}")


def _first_str(args: dict, keys) -> str:
    for k in keys:
        v = args.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _agy_mcp(args: dict):
    """call_mcp_tool {ServerName, ToolName, Arguments(dict | JSON string)} -> ("mcp__<server>__<tool>", arguments);
    ("", {}) when the server or tool name cannot be read (run_hook denies it)."""
    server = _first_str(args, ("ServerName", "server_name", "serverName", "Server", "server"))
    tool = _first_str(args, ("ToolName", "tool_name", "toolName", "Tool", "tool", "Name", "name"))
    raw = next((args[k] for k in ("Arguments", "arguments", "Args", "args", "Input", "input") if k in args), {})
    if isinstance(raw, str):
        try:
            raw = json.loads(raw) if raw.strip() else {}
        except ValueError:
            raw = {"_raw": raw}
    if not isinstance(raw, dict):
        raw = {"_raw": raw}
    if not server or not tool:
        return "", {}
    return f"mcp__{server}__{tool}", raw


AGY_PROMPT_KEYS = ("Prompt", "prompt", "Task", "task", "Message", "message", "InitialPrompt", "Instructions")
AGY_NAME_KEYS = ("TypeName", "typeName", "type_name", "SubagentType", "subagent_type", "AgentName", "agent_name")


def _agy_dispatch(tool: str, args: dict) -> dict:
    """invoke_subagent / define_subagent -> the Agent/Task shape decide_dispatch judges."""
    keys = AGY_NAME_KEYS if tool == "invoke_subagent" else ("Name", "name") + AGY_NAME_KEYS
    name = _first_str(args, keys)
    prompt = _first_str(args, AGY_PROMPT_KEYS)
    if not prompt:
        rest = [v for k, v in args.items() if isinstance(v, str) and k not in keys]
        prompt = max(rest, key=len) if rest else ""
    return {"subagent_type": name, "prompt": prompt, "_host": "antigravity", "_tool": tool}


# --------------------------------------------------------------------------- Antigravity identity (20.2)

AGY_TRANSCRIPT_CAP = 256 * 1024
AGY_CACHE_MAX = 500


def _entry_text(node, depth=0) -> str:
    """Every string inside a transcript entry's content (str, list or dict), joined."""
    if depth > 6:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        return "\n".join(_entry_text(v, depth + 1) for v in node.values())
    if isinstance(node, list):
        return "\n".join(_entry_text(v, depth + 1) for v in node[:200])
    return ""


def _brief_role(text: str) -> str:
    """ROLE of the first brief header in `text` (tolerant: a header with other fields malformed still names the
    role); the short name is normalised to cecilia-<short>. "" = none."""
    for m in BRIEF_RX.finditer(text or ""):
        hdr = parse_brief(m.group(0))
        role = hdr["ROLE"] if hdr else next((p[5:] for p in m.group(1).split() if p.startswith("ROLE=")), "")
        if role and SAFE_ID.match(role):
            return role if role.startswith("cecilia-") else "cecilia-" + role
    return ""


def agy_transcript_role(path):
    """(role, final): the brief ROLE found in the entries before the first PLANNER_RESPONSE ("" = no brief = the
    main agent) and whether that answer is final (a brief was found, or the planner already answered). Missing or
    unreadable transcript -> ("", False)."""
    if not path:
        return "", False
    try:
        with open(str(path), "rb") as fh:
            head = fh.read(AGY_TRANSCRIPT_CAP).decode("utf-8", errors="replace")
    except (OSError, ValueError):
        return "", False
    for line in head.splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue                                    # a bad or truncated line: skip it
        if not isinstance(rec, dict):
            continue
        if "PLANNER_RESPONSE" in str(rec.get("type") or "").upper():
            return "", True
        content = rec.get("content")
        if content is None and isinstance(rec.get("message"), (dict, str)):
            content = rec["message"]
        role = _brief_role(_entry_text(content))
        if role:
            return role, True
    return "", False


def _agy_cache_file(root: Path) -> Path:
    return cdir(root) / "agy-identity.json"


def agy_identity(data: dict, root: Path, cfg: dict) -> str:
    """AGENT for an Antigravity hook call (spec "Identity on Antigravity"): the role of the subagent's brief,
    else the main agent (antigravity.main_agent, default the orchestrator; "" = none). Cached per conversationId
    once the answer is final, in .cecilia/agy-identity.json (a control file agents cannot write)."""
    agy = cfg.get("antigravity") or {}
    if agy.get("identity") == "off":
        return ""
    main = agy.get("main_agent", ORCHESTRATOR)
    conv = str(data.get("conversationId") or "")
    cache_f = _agy_cache_file(root)
    cache = {}
    if conv:
        try:
            cache = json.loads(cache_f.read_text(encoding="utf-8-sig")) if cache_f.is_file() else {}
        except (OSError, ValueError):
            cache = {}
        if not isinstance(cache, dict):
            cache = {}
        hit = cache.get(conv)
        if isinstance(hit, dict) and isinstance(hit.get("role"), str):
            return hit["role"] or main
    role, final = agy_transcript_role(data.get("transcriptPath"))
    if conv and final and cdir(root).is_dir():
        cache[conv] = {"role": role, "at": _dt.datetime.now(_dt.timezone.utc).isoformat()}
        if len(cache) > AGY_CACHE_MAX:
            keep = sorted(cache.items(), key=lambda kv: str((kv[1] or {}).get("at", "") if isinstance(kv[1], dict)
                                                            else ""))[-AGY_CACHE_MAX:]
            cache = dict(keep)
        try:
            tmp = cache_f.with_name(cache_f.name + f".{os.getpid()}.tmp")
            tmp.write_text(json.dumps(cache, ensure_ascii=True), encoding="utf-8")
            os.replace(str(tmp), str(cache_f))
        except OSError:
            pass
    return role or main


# --------------------------------------------------------------------------- provenance (20.2)

def provenance(host: str, data: dict, root: Path, targets) -> None:
    """Append one line per allowed write under <ws>/tensura/ to <ws>/.cecilia/provenance.jsonl (best effort)."""
    ws = ws_home(root)
    seen = []
    for p, cwd in targets:
        try:
            rel = to_rel(str(p), Path(cwd), ws)
        except (OSError, ValueError):
            continue
        if rel and (rel.split("/")[0].lower() if CASE_FOLD else rel.split("/")[0]) == "tensura" and rel not in seen:
            seen.append(rel)
    if not seen or not cdir(root).is_dir():
        return
    if host == "antigravity":
        actor, model = str(data.get("conversationId") or ""), str(data.get("modelName") or "")
    else:
        actor = str(data.get("agent_id") or "") or f"{data.get('session_id') or ''}:{data.get('agent_type') or ''}"
        model = str(data.get("model") or "")
    now = _dt.datetime.now(_dt.timezone.utc).isoformat()
    try:
        with open(cdir(root) / "provenance.jsonl", "a", encoding="utf-8") as f:
            for rel in seen:
                f.write(json.dumps({"ts": now, "host": host, "path": rel, "agent": AGENT, "actor": actor,
                                    "model": model}, ensure_ascii=False) + "\n")
    except OSError:
        pass


# --------------------------------------------------------------------------- PreInvocation reminder (20.2)

AGY_REMIND_EVERY = 25


def _open_counts(ws: Path) -> tuple:
    """(open decision cards, new inbox items) under <ws>/tensura/."""
    counts = []
    for sub, open_ in (("decisions", lambda d: d.get("status") != "answered"),
                       ("inbox", lambda d: d.get("status", "new") == "new")):
        n = 0
        d = ws / "tensura" / sub
        for f in sorted(d.glob("*.json"))[:500] if d.is_dir() else []:
            try:
                rec = json.loads(f.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                continue
            n += isinstance(rec, dict) and open_(rec)
        counts.append(n)
    return tuple(counts)


def agy_invocation_context(data: dict, root: Path) -> str:
    """The ephemeral message injected before a model call on Antigravity ("" = nothing)."""
    try:
        num = int(data.get("invocationNum") or 0)
    except (TypeError, ValueError):
        num = 0
    rules = prompt_reminder(root)
    cfg = load_config(root)
    rv = role_view(root, cfg, AGENT) if AGENT else None
    if rv and rv["orchestrator"]:
        if num % AGY_REMIND_EVERY:
            return ""
        dec, inbox = _open_counts(ws_home(root))
        msg = (f"[Cecilia] You are {AGENT}: coordinator only. Dispatch Cecilia roles with invoke_subagent "
               "(TypeName=cecilia-<role>, the prompt = the brief from workflow.py brief). Never call MCP tools or run "
               "cluster/infra commands yourself (kubectl, helm, ssh, pods_*, resources_*...). If a dispatch fails, "
               "STOP and report - never do the work yourself. "
               f"Open decision cards: {dec}; new inbox items: {inbox}.")
        return msg + ("\n" + rules if rules else "")
    if num != 0:
        return ""
    if rv:
        lane = rv.get("lane")
        lane_txt = ", ".join(lane[:6]) + (" ..." if len(lane) > 6 else "") if isinstance(lane, list) and lane else \
            ("reports only (tensura/reports/**)" if isinstance(lane, list) else "your registry lane")
        msg = (f"[Cecilia] You are {AGENT}. Write only in your lane: {lane_txt} (+ tensura/reports|tasks). "
               "Anything outside it: stop and end your report with 'HANDOFF: needs <role> - <what>'.")
        return msg + ("\n" + rules if rules else "")
    return rules


def emit(host: str, decision, reason: str, kind: str = "other", context: str = "", ask: str = "force_ask"):
    tag = "[cecilia-guard] "
    if host == "claude":
        if kind == "prompt":
            if not context:
                return 0, ""
            return 0, json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                                         "additionalContext": context}}, ensure_ascii=True)
        if decision is ALLOW:
            return 0, ""
        out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": decision,
                                      "permissionDecisionReason": tag + reason}}
        return 0, json.dumps(out, ensure_ascii=True)
    if host == "antigravity":
        if kind == "prompt":        # PreInvocation: {"injectSteps": [...]} or {} (valid JSON either way)
            out = {"injectSteps": [{"ephemeralMessage": context}]} if context else {}
            return 0, json.dumps(out, ensure_ascii=True)
        # Antigravity wants an explicit decision. Allowed local file edits return "allow";
        # a command with no concern goes through the host's own cached permissions ("ask").
        # A3 (our ASK): "force_ask" (default) always stops for the user, even under
        # `agy --dangerously-skip-permissions`; config antigravity.ask = "ask" sends a plain "ask", which
        # skip-permissions (and the host's cached approvals) answer automatically - A3 then runs unasked.
        if decision is ALLOW:
            out = {"decision": "allow" if kind == "write" else "ask"}
        else:
            out = {"decision": ("ask" if ask == "ask" else "force_ask") if decision == ASK else "deny",
                   "reason": tag + reason}
        return 0, json.dumps(out, ensure_ascii=True)
    raise ValueError(host)


def log(root: Path, host: str, kind: str, payload, decision, reason: str, agent: str = ""):
    if decision is ALLOW:
        return
    try:
        rec = {"at": _dt.datetime.now(_dt.timezone.utc).isoformat(), "host": host, "kind": kind,
               "payload": payload if isinstance(payload, list) else str(payload)[:500],
               "decision": decision, "reason": reason, **({"agent": agent} if agent else {})}
        with open(cdir(root) / "guard.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


# High-confidence credential shapes (same family as cecilia_check.py). Placeholders and local examples pass.
SECRET_CONTENT = [
    ("private key", re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}")),
    ("Slack token", re.compile(r"\bxox[abpr]-[0-9]{6,}-[A-Za-z0-9-]{10,}")),
    ("Stripe live key", re.compile(r"\b(sk|rk)_live_[A-Za-z0-9]{20,}")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("OpenAI/Anthropic key", re.compile(r"\bsk-(proj-|ant-(api\d+-)?)?[A-Za-z0-9_-]{32,}")),
    ("URL with password", re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s:/@'\"]+:([^\s@/'\"$\{<]{8,})@([^\s/'\":]+)", re.I)),
]
PLACEHOLDER = re.compile(r"example|localhost|127\.0\.0\.1|changeme|password|secret|xxxx|your[_-]|<|\*\*\*|dummy|test|fake|"
                         r"placeholder|redacted", re.I)


def secret_in_content(text: str):
    """Kind of credential in text an agent is about to write, or None."""
    for kind, rx in SECRET_CONTENT:
        for m in rx.finditer(text or ""):
            chunk = m.group(0)
            if kind == "URL with password" and PLACEHOLDER.search(chunk):
                continue
            if kind != "private key" and re.search(r"(EXAMPLE|example|xxxx|XXXX|0000000000)", chunk):
                continue
            return kind
    return None


def _written_text(host: str, data: dict) -> str:
    if host == "claude":
        ti = data.get("tool_input") or {}
        parts = [str(ti.get(k) or "") for k in ("content", "new_string", "new_source")]
        parts += [str(e.get("new_string", "")) for e in ti.get("edits") or [] if isinstance(e, dict)]
        return "\n".join(parts)
    call = data.get("toolCall") or {}
    return json.dumps(call.get("args") or {}, ensure_ascii=False)


def run_hook(host: str, raw: str, workspace=None):
    global AGENT
    data = json.loads(raw or "{}")
    if not isinstance(data, dict):
        raise ValueError("hook input is not a JSON object")
    kind, payload, cwd = extract(host, data)
    AGENT = str(data.get("agent_type") or "") if host == "claude" else ""
    del WRITES_SEEN[:]
    start = Path(os.environ.get("CLAUDE_PROJECT_DIR") or cwd) if host == "claude" else cwd
    root = resolve_roots(Path(os.path.normpath(str(start))), workspace)
    ask = "force_ask"
    if host == "antigravity":
        cfg = load_config(root)
        ask = cfg["antigravity"]["ask"]
        AGENT = agy_identity(data, root, cfg) if cdir(root).is_dir() else ""
    if kind == "prompt":
        if host == "antigravity":
            return emit(host, ALLOW, "", kind, "" if POLICY_ERROR else agy_invocation_context(data, root))
        return emit(host, ALLOW, "", kind, "" if POLICY_ERROR else prompt_reminder(root))
    decision, reason = ALLOW, ""
    if POLICY_ERROR and kind in {"command", "write", "mcp", "dispatch"}:
        decision, reason = DENY, POLICY_ERROR
    elif kind == "mcp" and not (payload or ("",))[0]:
        decision, reason = DENY, ("Could not read which MCP server/tool this call_mcp_tool targets "
                                  "(ServerName / ToolName) — blocked for safety.")
    elif kind == "command":
        decision, reason = decide_command(payload or "", root, Path(os.path.normpath(str(cwd))))
        if decision is not DENY and WRITES_SEEN:
            d, r = check_rules_gate(data, root)
            if RANK[d] > RANK[decision]:
                decision, reason = d, r
    elif kind == "dispatch":
        decision, reason = decide_dispatch(payload or {}, root)
    elif kind == "mcp":
        tool, ti = payload if isinstance(payload, tuple) else (payload or "", {})
        decision, reason = decide_mcp(tool, root, ti)
    elif kind == "write":
        if not payload:
            decision, reason = DENY, "Could not read which file this edit targets — blocked for safety."
        for p in payload or []:
            d, r = decide_write(p, cwd, root)
            if RANK[d] > RANK[decision]:
                decision, reason = d, r
            if d == DENY:
                break
        if decision is not DENY:
            kind_found = secret_in_content(_written_text(host, data))
            if kind_found:
                decision, reason = DENY, (f"The text being written contains what looks like a real {kind_found}. "
                                          "Never put credentials in files — read them from an environment variable "
                                          "and put a placeholder in .env.example.")
        if decision is not DENY:        # Antigravity too (20.2): AGENT comes from the transcript there
            d, r = check_rules_gate(data, root)
            if RANK[d] > RANK[decision]:
                decision, reason = d, r
        if decision is ALLOW and host == "claude":
            decision, reason = check_tool_rules(data, payload or [], cwd, root)
    if decision is ALLOW and kind in {"write", "command"}:
        targets = [(p, cwd) for p in payload or []] if kind == "write" else list(WRITES_SEEN)
        provenance(host, data, root, targets)
    log(root, host, kind, payload, decision, reason, AGENT)
    return emit(host, decision, reason, kind, ask=ask)


def utf8_stdio() -> None:
    """Hosts exchange UTF-8 JSON. On Windows, Python's pipes default to the legacy code page (cp1252,
    cp1258…), which turns an em dash into byte 0x97 (invalid UTF-8 for the host) and fails to decode
    Vietnamese input. Force UTF-8 both ways; our own JSON output is ASCII-only anyway."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def read_stdin() -> str:
    buf = getattr(sys.stdin, "buffer", None)
    if buf is not None:
        return buf.read().decode("utf-8", errors="replace")
    return sys.stdin.read()


def main() -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", choices=["claude", "antigravity"])
    ap.add_argument("--explain", metavar="COMMAND", help="show the decision for a shell command")
    ap.add_argument("--cwd", help="with --explain: judge as if run in this directory (default: here)")
    ap.add_argument("--workspace", help="workspace mode: the sidecar folder that holds .cecilia/ (set by the installer)")
    ap.add_argument("--agent", help="with --explain: judge as this agent type (v20 lanes), e.g. cecilia-dev-be")
    a = ap.parse_args()
    if a.explain is not None:
        global AGENT
        AGENT = a.agent or ""
        cwd = Path(a.cwd or os.getcwd()).resolve()
        root = resolve_roots(cwd, a.workspace)
        detail: list = []
        d, r = decide_command(a.explain, root if cdir(root).is_dir() else None, cwd, detail)
        print(json.dumps({"decision": d or "allow", "reason": r, "segments": detail}, ensure_ascii=True))
        return 0
    if not a.host:
        ap.error("--host is required when running as a hook")
    try:
        code, out = run_hook(a.host, read_stdin(), a.workspace)
        if out:
            print(out)
        return code
    except Exception as e:  # fail closed
        msg = f"[cecilia-guard] internal error, blocked for safety: {type(e).__name__}: {e}"
        if a.host == "antigravity":
            print(json.dumps({"decision": "deny", "reason": msg}, ensure_ascii=True))
            return 0
        print(msg, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
