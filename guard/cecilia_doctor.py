#!/usr/bin/env python3
"""Cecilia doctor — checks that the installation actually protects this project. Read-only by default.

    python .cecilia/bin/cecilia_doctor.py            # table of OK / WARN / FAIL with the fix for each
    python .cecilia/bin/cecilia_doctor.py --json
    python .cecilia/bin/cecilia_doctor.py --fix      # only safe fixes: missing .git/info/exclude lines

Checks: the guard and policy.json load; the hook interpreter (`guard.python`, default `python` on Windows /
`python3` elsewhere) resolves on PATH, runs, is Python 3.9+ and is not the Microsoft Store stub; the Claude Code /
Antigravity hooks point at an interpreter and a guard that exist and really deny `gh pr merge`; the Antigravity hook
covers MCP calls, subagent dispatches and PreInvocation (20.2); `agy --version` >= 1.2.7; no old global Cecilia install
shadows this one (~/.gemini, ~/.claude); the MCP servers agy offers (names only); Cecilia's paths are excluded from git and none is tracked or staged; the push lock; the config
(unknown keys, profile levels, tool rules whose tools no MCP config provides); API keys or tokens written
as plain text in MCP config files (reported by file and key — the value is never printed). Best effort, never
failing: when this Cecilia was installed with `uv tool install git+<url>`, a newer vX.Y.Z tag is reported as INFO
(set CECILIA_NO_UPDATE_CHECK=1 to skip).

Agents may run it without --fix (the guard allows that); --fix and every change is Cecilia's.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

RESULTS: list[dict] = []
TOKEN_PATTERNS = [
    ("bearer token", re.compile(r"bearer\s+[a-z0-9._~+/=-]{16,}", re.I)),
    ("sk- API key", re.compile(r"\bsk-[a-z0-9_-]{16,}", re.I)),
    ("GitHub token", re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[a-z0-9]{20,}|github_pat_[a-z0-9_]{20,}", re.I)),
    ("Slack token", re.compile(r"\bxox[abpr]-[a-z0-9-]{10,}", re.I)),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("token in URL", re.compile(r"[?&](token|usertoken|access_token|api_key|apikey|key)=[a-z0-9._~%-]{16,}", re.I)),
    ("JWT", re.compile(r"\beyJ[a-z0-9_-]{10,}\.[a-z0-9_-]{10,}", re.I)),
]
SECRET_KEY = re.compile(r"(token|secret|password|passwd|api[_-]?key|authorization|auth)", re.I)
NOT_SECRET_KEY = re.compile(r"(Date|At|Time|Count|Expires|Enabled|DATE|AT|TIME|COUNT|EXPIRES|ENABLED)$"
                            r"|(?i:(^|[_.-])(date|at|time|count|expires|expires_at|enabled)$)")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?$")
NUMBER = re.compile(r"^[+-]?\d+(\.\d+)?([eE][+-]?\d+)?$")
UPDATE_TIMEOUT = 5.0


def secret_kind(key: str, val: str) -> str | None:
    """The kind of credential a plain-text MCP config value looks like, or None. Known token shapes always count;
    the key-name heuristic (…Token, …Secret, password, apiKey …) skips values that are ISO dates/timestamps,
    booleans, numbers, shorter than 16 characters or contain a space, and keys ending in
    Date/At/Time/Count/Expires(At)/Enabled (e.g. `claudeCodeFirstTokenDate`)."""
    if not isinstance(val, str) or "${" in val or val.startswith("$") or val.startswith("env:"):
        return None                                  # a reference to an environment variable: fine
    kinds = [name for name, rx in TOKEN_PATTERNS if rx.search(val)]
    if kinds:
        return kinds[0]
    v = val.strip()
    k = str(key or "")
    if not SECRET_KEY.search(k) or NOT_SECRET_KEY.search(k):
        return None
    if len(v) < 16 or " " in v or v.lower() in {"true", "false", "null", "none"} or NUMBER.match(v) \
            or ISO_DATE.match(v):
        return None
    return "secret-like value"


def add(status: str, check: str, detail: str, fix: str = ""):
    RESULTS.append({"status": status, "check": check, "detail": detail, "fix": fix})


def find_root(start: Path) -> Path:
    for d in [start, *start.parents]:
        if (d / ".cecilia").is_dir():
            return d
    return start


def home() -> Path:
    return Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or Path.home())


def check_guard(root: Path):
    try:
        import cecilia_guard as G  # noqa: WPS433
    except Exception as e:  # pragma: no cover - broken install
        add("FAIL", "guard", f"cecilia_guard.py does not load: {e}", "re-run the installer with --upgrade")
        return None
    if G.POLICY_ERROR:
        add("FAIL", "policy", G.POLICY_ERROR, "re-run the installer with --upgrade")
        return G
    if G.POLICY.get("version") != G.VERSION:
        add("WARN", "policy", f"policy.json {G.POLICY.get('version')} vs guard {G.VERSION}", "re-run the installer with --upgrade")
    d, _ = G.decide_command("gh pr merge 1", root, root)
    add("OK" if d == "deny" else "FAIL", "guard decision", f"`gh pr merge 1` -> {d or 'allow'}")
    return G


def default_python(windows: bool | None = None) -> str:
    windows = (os.name == "nt") if windows is None else windows
    return "python" if windows else "python3"


def configured_python(cfg: dict | None) -> str:
    guard = (cfg or {}).get("guard")
    py = guard.get("python") if isinstance(guard, dict) else None
    return py.strip() if isinstance(py, str) and py.strip() else default_python()


def resolve_python(py: str) -> str | None:
    """Absolute path of an interpreter token (`python3`, `C:\\Python312\\python.exe`), or None."""
    if not py:
        return None
    p = Path(py).expanduser()
    if p.is_absolute() or os.sep in py or "/" in py:
        return str(p) if p.exists() else None
    import shutil  # noqa: WPS433
    return shutil.which(py)


def python_version_of(exe: str, timeout: float = 5.0) -> tuple[tuple[int, ...] | None, str]:
    """((major, minor, micro) or None, raw output) of `<exe> --version` within `timeout` seconds."""
    try:
        r = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, f"`{exe} --version` did not answer within {timeout:g}s"
    except (OSError, subprocess.SubprocessError) as e:
        return None, f"`{exe} --version` failed: {e}"
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    m = re.search(r"Python\s+(\d+)\.(\d+)(?:\.(\d+))?", out)
    if r.returncode != 0 or not m:
        return None, out[:120]
    return tuple(int(x or 0) for x in m.groups()), out[:120]


PY_FIX = ("install Python from python.org (tick \"Add python.exe to PATH\") or set guard.python in "
          ".cecilia/config.json to an absolute path, then `cecilia upgrade`")


def check_interpreter(py: str, label: str = "hook python") -> bool:
    """FAIL when the hook interpreter does not resolve, does not run within 5s, is older than 3.9, or is the
    Microsoft Store stub (…\\WindowsApps\\python.exe that opens the Store instead of running)."""
    exe = resolve_python(py)
    if not exe:
        add("FAIL", label, f"`{py}` is not found" + (" on PATH" if not Path(py).is_absolute() else ""), PY_FIX)
        return False
    ver, raw = python_version_of(exe)
    store = "\\windowsapps\\" in exe.lower().replace("/", "\\")
    if ver is None:
        why = ("the Microsoft Store stub (it opens the Store instead of running Python)" if store
               else f"it does not run ({raw or 'no output'})")
        add("FAIL", label, f"`{py}` → {exe}: {why}", PY_FIX)
        return False
    if ver < (3, 9):
        add("FAIL", label, f"`{py}` → {exe} is Python {'.'.join(map(str, ver))} (< 3.9)", PY_FIX)
        return False
    add("OK", label, f"`{py}` → {exe} (Python {'.'.join(map(str, ver))})")
    return True


def _run_hook(argv: list[str], payload: dict) -> str | None:
    try:
        r = subprocess.run(argv, input=json.dumps(payload), capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        return f"error: {e}"
    return (r.stdout or "") + (r.stderr or "")


def check_claude_hook(root: Path, project: Path | None = None):
    project = project or root
    f = root / ".claude" / "settings.json"
    if not f.is_file():
        if (root / ".claude" / "skills").is_dir():
            add("WARN", "claude hook", ".claude/settings.json missing — the guard does not run in Claude Code",
                "merge .claude/settings.json.cecilia-suggested or re-run the installer")
        return
    try:
        data = json.loads(f.read_text(encoding="utf-8-sig"))
    except ValueError as e:
        add("FAIL", "claude hook", f".claude/settings.json is not valid JSON ({e})")
        return
    hooks = [h for e in (data.get("hooks", {}).get("PreToolUse") or []) if isinstance(e, dict)
             for h in e.get("hooks", []) if isinstance(h, dict) and "cecilia_guard" in json.dumps(h)]
    if not hooks:
        add("FAIL", "claude hook", "no cecilia_guard PreToolUse hook in .claude/settings.json",
            "merge .claude/settings.json.cecilia-suggested")
        return
    h = hooks[0]
    argv = [h["command"], *h.get("args", [])] if h.get("args") else None
    if argv is None:
        parts = re.findall(r'"([^"]+)"|(\S+)', h["command"])
        argv = [a or b for a, b in parts]
    exe = resolve_python(argv[0]) if argv else None
    if not exe:
        add("FAIL", "claude hook", f"interpreter not found: {argv[0] if argv else '?'}", PY_FIX)
        return
    argv = [exe, *argv[1:]]
    out = _run_hook(argv, {"tool_name": "Bash", "tool_input": {"command": "gh pr merge 1"}, "cwd": str(project)})
    add("OK" if out and '"deny"' in out else "FAIL", "claude hook live",
        "hook denies `gh pr merge 1`" if out and '"deny"' in out else f"hook output: {(out or '')[:120]}")
    if "UserPromptSubmit" not in json.dumps(data.get("hooks", {})):
        add("WARN", "claude reminder", "no UserPromptSubmit hook — tool rules are not reminded each turn",
            "merge .claude/settings.json.cecilia-suggested")


def check_antigravity_hook(root: Path, project: Path | None = None):
    project = project or root
    f = root / ".agents" / "hooks.json"
    if not f.is_file():
        if (root / ".agents" / "skills").is_dir():
            add("WARN", "antigravity hook", ".agents/hooks.json missing — the guard does not run in Antigravity",
                "merge .agents/hooks.json.cecilia-suggested or re-run the installer")
        return
    try:
        data = json.loads(f.read_text(encoding="utf-8-sig"))
    except ValueError as e:
        add("FAIL", "antigravity hook", f".agents/hooks.json is not valid JSON ({e})")
        return
    cmds = []
    stack = [data]
    while stack:
        o = stack.pop()
        if isinstance(o, dict):
            if isinstance(o.get("command"), str) and "cecilia_guard" in o["command"]:
                cmds.append(o["command"])
            stack.extend(o.values())
        elif isinstance(o, list):
            stack.extend(o)
    if not cmds:
        add("FAIL", "antigravity hook", "no cecilia-guard entry in .agents/hooks.json")
        return
    check_antigravity_coverage(data)
    cmd = cmds[0]
    problem = antigravity_quote_problem(cmd, os.name == "nt")
    if problem:
        add("FAIL", "antigravity hook", problem,
            "run `cecilia upgrade <project>` (writes the unquoted command, or .cecilia/bin/cecilia_guard_antigravity.cmd "
            "when a path has a space); if .agents/hooks.json was customised, merge .agents/hooks.json.cecilia-suggested")
        return
    parts = [a or b for a, b in re.findall(r'"([^"]+)"|(\S+)', cmd)]
    if parts and parts[0].lower().endswith((".cmd", ".bat")):
        launcher = Path(parts[0])
        if not launcher.is_file():
            add("FAIL", "antigravity hook", f"launcher not found: {parts[0]}", "run `cecilia upgrade <project>`")
            return
        inner = launcher_command(launcher)
        inner_parts = [a or b for a, b in re.findall(r'"([^"]+)"|(\S+)', inner or "")]
        if inner_parts and not resolve_python(inner_parts[0]):
            add("FAIL", "antigravity hook", f"the launcher's interpreter is not found: {inner_parts[0]}", PY_FIX)
            return
    elif parts:
        exe = resolve_python(parts[0])
        if not exe:
            add("FAIL", "antigravity hook", f"interpreter not found: {parts[0]}", PY_FIX)
            return
        parts = [exe, *parts[1:]]
    if len(parts) > 1 and not Path(parts[1]).is_absolute():
        add("WARN", "antigravity hook", "relative guard path (older Cecilia) — breaks when the workspace root differs",
            "re-run the installer with --upgrade")
    out = _run_hook(parts, {"toolCall": {"name": "run_command", "args": {"CommandLine": "gh pr merge 1"}},
                            "workspacePaths": [str(root), str(project)]})
    add("OK" if out and '"deny"' in out else "FAIL", "antigravity hook live",
        "hook denies `gh pr merge 1`" if out and '"deny"' in out else f"hook output: {(out or '')[:120]}")


# 20.2: tools the guard must see on Antigravity (MCP calls and dispatches bypassed the 20.1 matcher).
AG_MUST_MATCH = ("run_command", "write_to_file", "call_mcp_tool", "invoke_subagent")
AGY_MIN_VERSION = (1, 2, 7)


def _matcher_covers(matcher, tool: str) -> bool:
    if matcher in (None, "", "*"):
        return True
    try:
        return re.fullmatch(f"(?:{matcher})", tool) is not None
    except (re.error, TypeError):
        return False


def antigravity_coverage_problems(data) -> list[str]:
    """What a hooks.json misses for 20.2: guard PreToolUse matchers covering AG_MUST_MATCH, a guard PreInvocation."""
    groups = [g for g in (data.values() if isinstance(data, dict) else []) if isinstance(g, dict)]

    def guard_entries(event):
        out = []
        for g in groups:
            entries = g.get(event)
            for e in entries if isinstance(entries, list) else []:
                if isinstance(e, dict) and "cecilia_guard" in json.dumps(e.get("hooks", [])):
                    out.append(e)
        return out
    pre = guard_entries("PreToolUse")
    problems = [f"PreToolUse matcher misses {t}" for t in AG_MUST_MATCH
                if not any(_matcher_covers(e.get("matcher"), t) for e in pre)]
    if not guard_entries("PreInvocation"):
        problems.append("no PreInvocation hook")
    return problems


def check_antigravity_coverage(data) -> None:
    try:
        problems = antigravity_coverage_problems(data)
    except Exception as e:  # noqa: BLE001 — never fail the doctor on an odd file
        add("WARN", "antigravity coverage", f"could not read the hook matchers ({e})")
        return
    if problems:
        add("FAIL", "antigravity coverage", "; ".join(problems) + " — MCP calls and subagent dispatches bypass the "
            "guard (hooks.json from Cecilia 20.1 or older)",
            "run `cecilia upgrade <project>` (if .agents/hooks.json was customised, merge "
            ".agents/hooks.json.cecilia-suggested)")
    else:
        add("OK", "antigravity coverage", "guard sees commands, edits, MCP calls, dispatches and each invocation")


def parse_agy_version(text: str) -> tuple[int, int, int] | None:
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", text or "")
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def version_at_least(version, minimum=AGY_MIN_VERSION) -> bool:
    return version is not None and tuple(version) >= tuple(minimum)


def find_agy() -> str | None:
    import shutil  # noqa: WPS433
    for name in ("agy", "agy.cmd", "agy.exe"):
        exe = shutil.which(name)
        if exe:
            return exe
    return None


def check_agy_version(timeout: float = 5.0) -> None:
    exe = find_agy()
    if not exe:
        add("INFO", "agy version", "agy not on PATH — skipped")
        return
    try:
        r = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=timeout,
                           stdin=subprocess.DEVNULL)
        out = ((r.stdout or "") + (r.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        add("WARN", "agy version", f"`agy --version` did not answer within {timeout:g}s")
        return
    except (OSError, subprocess.SubprocessError) as e:
        add("WARN", "agy version", f"`agy --version` failed: {e}")
        return
    ver = parse_agy_version(out)
    need = ".".join(map(str, AGY_MIN_VERSION))
    if ver is None:
        add("WARN", "agy version", f"unknown agy version ({out[:60] or 'no output'})")
    elif not version_at_least(ver):
        add("WARN", "agy version", f"agy {'.'.join(map(str, ver))} < {need}: a custom main agent (cecilia-orchestrator) "
            "cannot invoke subagents before 1.2.7", "update the Antigravity CLI")
    else:
        add("OK", "agy version", f"agy {'.'.join(map(str, ver))}")


def _command_target_missing(cmd: str) -> str | None:
    """The cecilia_guard file (script or .cmd launcher) a hook command names, when it does not exist."""
    for a, b in re.findall(r'"([^"]+)"|(\S+)', cmd or ""):
        tok = a or b
        if "cecilia_guard" in tok:
            return None if Path(tok).expanduser().exists() else tok
    return None


def check_antigravity_global() -> None:
    """Global Antigravity leftovers that act in every folder: ~/.gemini/config/agents/cecilia-* (a global main agent
    without the workspace's hooks) and a global hooks.json whose cecilia_guard file is gone."""
    h = home()
    found = []
    try:
        agents = h / ".gemini" / "config" / "agents"
        if agents.is_dir():
            found += [str(p) for p in sorted(agents.iterdir()) if p.name.startswith("cecilia-")]
        hf = h / ".gemini" / "config" / "hooks.json"
        if hf.is_file():
            data = json.loads(hf.read_text(encoding="utf-8-sig"))
            stack = [data]
            while stack:
                o = stack.pop()
                if isinstance(o, dict):
                    c = o.get("command")
                    if isinstance(c, str) and "cecilia_guard" in c:
                        miss = _command_target_missing(c)
                        if miss:
                            found.append(f"{hf} (runs {miss}, which does not exist)")
                            break
                    stack.extend(o.values())
                elif isinstance(o, list):
                    stack.extend(o)
    except (OSError, ValueError) as e:
        add("WARN", "agy global", f"could not read ~/.gemini/config ({e})")
        return
    if found:
        add("WARN", "agy global", f"{len(found)} global Antigravity Cecilia leftover(s): " + "; ".join(found[:6])
            + (" …" if len(found) > 6 else ""),
            "remove them (docs/INSTALL.md §Uninstall global) and start agy from the workspace: "
            "`cecilia open <project> --agy`")
    else:
        add("OK", "agy global", "no global Antigravity Cecilia leftovers")


def _mcp_server_names(data) -> list[str]:
    if not isinstance(data, dict):
        return []
    for key in ("mcpServers", "servers", "mcp_servers"):
        if isinstance(data.get(key), dict):
            return sorted(str(k) for k in data[key])
    return []


def check_antigravity_mcp(root: Path) -> None:
    """INFO: the MCP servers agy offers (names only — values and env are never printed) and who may use them."""
    f = home() / ".gemini" / "config" / "mcp_config.json"
    if not f.is_file():
        return
    try:
        names = _mcp_server_names(json.loads(f.read_text(encoding="utf-8-sig")))
    except (OSError, ValueError):
        add("INFO", "agy MCP", f"{f} is not readable JSON — skipped")
        return
    roles = []
    try:
        for a in sorted((root / ".agents" / "agents").glob("cecilia-*/agent.md")):
            if re.search(r"^\s*-\s*call_mcp_tool\s*$", a.read_text(encoding="utf-8", errors="ignore"), re.M):
                roles.append(a.parent.name[len("cecilia-"):])
    except OSError:
        pass
    add("INFO", "agy MCP", f"servers in ~/.gemini/config/mcp_config.json: {', '.join(names) or 'none'} — the guard "
        "denies MCP to the orchestrator (main agent); "
        + (f"roles with call_mcp_tool may use them ({', '.join(roles)}), A3 rules apply" if roles
           else "roles with call_mcp_tool may use them, A3 rules apply"))


def antigravity_quote_problem(cmd: str, windows: bool) -> str | None:
    """20.1: on Windows the Antigravity hook command must carry no double quotes at all — Antigravity escapes them
    and cmd.exe cannot start the command. Quoting is fine only inside the .cmd launcher."""
    if windows and '"' in cmd:
        return ("the hook command is quoted - Antigravity on Windows escapes the quotes and cmd.exe cannot start it, "
                "so every Antigravity tool call fails (quotes belong only inside the .cmd launcher)")
    return None


def launcher_command(launcher: Path) -> str | None:
    """The command line inside a cecilia_guard_antigravity.cmd launcher."""
    try:
        lines = launcher.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return None
    for ln in lines:
        t = ln.strip()
        if t and not t.lower().startswith(("@echo", "rem ", "rem\t", "::", "exit ", "setlocal", "endlocal")):
            return t
    return None


def check_global_leftovers(root: Path):
    h = home()
    spots = [h / ".gemini/config/skills", h / ".gemini/antigravity-cli/skills", h / ".gemini/config/agents",
             h / ".claude/skills", h / ".claude/agents"]
    found = []
    for s in spots:
        if s.is_dir():
            found += [str(p) for p in s.iterdir() if p.name.startswith("cecilia-")]
    for hf in (h / ".gemini/config/hooks.json",):
        if hf.is_file() and "cecilia_guard" in hf.read_text(encoding="utf-8", errors="ignore"):
            found.append(str(hf))
    local = (root / ".claude/skills").is_dir() or (root / ".agents/skills").is_dir()
    if found and local:
        add("WARN", "global install", f"{len(found)} global Cecilia item(s) also installed (e.g. {found[0]}) — "
            "two copies of every skill; the global guard also runs in every other project",
            "remove the global copies if you install per project (docs/INSTALL.md §Uninstall global)")
    elif found:
        add("OK", "global install", f"global install present ({len(found)} item(s))")
    else:
        add("OK", "global install", "no global Cecilia copies")


def check_workspace(home: Path, project: Path, G):
    """Workspace mode: the project folder must hold no Cecilia file at all."""
    if not project.is_dir():
        add("FAIL", "workspace", f"project folder not found: {project}", "fix workspace.project in .cecilia/config.json")
        return
    add("OK", "workspace", f"workspace {home.name} serves {project}")
    pats = G.POLICY.get("local_only_paths", []) if G else []
    found = []
    for pat in pats:
        base = pat.rstrip("/").split("*")[0].rstrip("/")
        if base and (project / base).exists():
            found.append(base)
    for extra in (".claude/settings.json", ".agents/hooks.json", ".mcp.json.cecilia-suggested"):
        if (project / extra).exists() and "cecilia" in (project / extra).read_text(encoding="utf-8", errors="ignore").lower():
            found.append(extra)
    if found:
        add("WARN", "project untouched", f"Cecilia file(s) inside the project: {', '.join(sorted(set(found))[:5])}",
            "move them to the workspace (older in-project install?) — see docs/MIGRATION.md")
    else:
        add("OK", "project untouched", "no Cecilia file inside the project")


def check_git(root: Path, G, fix: bool, workspace: bool = False):
    if not (root / ".git").exists():
        add("WARN", "git", "not a git repository — Cecilia edits only on a task branch", "git init; first commit")
        return
    pats = G.POLICY.get("local_only_paths", []) if G else []
    f = root / ".git" / "info" / "exclude"
    have = [x.strip() for x in f.read_text(encoding="utf-8").splitlines()] if f.is_file() else []
    missing = [] if workspace else [p for p in pats if p not in have]
    if workspace:
        pass                                       # nothing of Cecilia lives in the project: no exclude needed
    elif missing and fix:
        text = (f.read_text(encoding="utf-8") if f.is_file() else "")
        text += ("" if not text or text.endswith("\n") else "\n") + "# Cecilia (local-only)\n" + "\n".join(missing) + "\n"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
        add("OK", "exclude", f"added {len(missing)} line(s) to .git/info/exclude")
    elif missing:
        add("WARN", "exclude", f"{len(missing)} Cecilia path(s) not in .git/info/exclude: {', '.join(missing[:4])}",
            "python .cecilia/bin/cecilia_doctor.py --fix")
    else:
        add("OK", "exclude", "Cecilia paths are excluded from git")
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    try:
        tracked = subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True, text=True, timeout=20,
                                 env=env).stdout.splitlines()
        staged = subprocess.run(["git", "-C", str(root), "--no-optional-locks", "diff", "--cached", "--name-only"],
                                capture_output=True, text=True, timeout=20, env=env).stdout.splitlines()
    except (OSError, subprocess.SubprocessError):
        tracked, staged = [], []
    if G:
        bad_t = [p for p in tracked if G.local_only_match(p)]
        bad_s = [p for p in staged if G.local_only_match(p)]
        if bad_t:
            add("WARN", "tracked", f"{len(bad_t)} Cecilia file(s) are tracked by git (e.g. {bad_t[0]}) — they reach the "
                "remote with your next push", "git rm -r --cached <path> (keeps the files), then commit that")
        if bad_s:
            add("FAIL", "staged", f"Cecilia file(s) staged: {', '.join(bad_s[:3])}", "git restore --staged -- <path>")
    try:
        import cecilia_mode as M  # noqa: WPS433
        on = M.push_lock_status(root)
        if workspace:
            add("OK", "push lock", "ON (project .git/config)" if on else
                "off — the guard still denies every agent push; `cecilia push-lock on` adds a git-level lock "
                "(writes the project's .git/config)")
        else:
            add("OK" if on else "WARN", "push lock", "ON" if on else "off — an allowed push would reach the remote",
                "" if on else "python .cecilia/bin/cecilia_mode.py --push-lock on")
    except Exception as e:  # pragma: no cover
        add("WARN", "push lock", f"unknown ({e})")


def _mcp_files(root: Path) -> list[Path]:
    h = home()
    cands = [root / ".mcp.json", root / ".cursor/mcp.json", root / ".vscode/mcp.json", h / ".claude.json",
             h / ".gemini/config/mcp_config.json", h / ".gemini/antigravity/mcp_config.json", h / ".gemini/settings.json",
             h / ".codeium/windsurf/mcp_config.json"]
    return [c for c in cands if c.is_file()]


def _walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


def check_mcp(root: Path, cfg: dict):
    files = _mcp_files(root)
    servers_text = ""
    leaks = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        servers_text += json.dumps(data).lower()
        for path, val in _walk(data):
            kind = secret_kind(re.sub(r"\[\d+\]$", "", path.split(".")[-1]), val)
            if kind:
                leaks.append(f"{f} → {path} ({kind})")
    if leaks:
        add("WARN", "MCP secrets", f"{len(leaks)} plain-text credential(s) in MCP config: " + "; ".join(leaks[:4]),
            "rotate them, then reference environment variables (e.g. \"Authorization\": \"Bearer ${MY_TOKEN}\") "
            "and never paste these files into chats")
    else:
        add("OK", "MCP secrets", f"no plain-text credentials found in {len(files)} MCP config file(s)")
    for rule in cfg.get("tool_rules") or []:
        pats = [p.strip("*").lower() for p in rule.get("tools", []) if p.strip("*")]
        if pats and not any(p.split("*")[0] in servers_text for p in pats):
            add("WARN", "tool rule", f"rule '{rule.get('id')}' needs {rule.get('tools')} but no MCP config mentions it "
                "— agents could never satisfy it", "install that MCP server, or set the rule's enforce to \"report\"")


def parse_version(text: str) -> tuple[int, int, int] | None:
    """`v20.1.0` / `20.1` / `refs/tags/v20.0.1` -> (20, 1, 0); None for anything else (pre-releases included)."""
    m = re.search(r"(?:^|/)v?(\d+)\.(\d+)(?:\.(\d+))?$", (text or "").strip())
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)) if m else None


def newest_tag(tags: list[str], current: str) -> str | None:
    """The highest vX.Y.Z tag strictly above `current`, or None."""
    cur = parse_version(current)
    best, best_v = None, cur
    for t in tags:
        t = t.strip()
        if t.endswith("^{}"):
            t = t[:-3]
        name = t.rsplit("refs/tags/", 1)[-1]
        v = parse_version(name)
        if v and name.startswith("v") and (best_v is None or v > best_v):
            best, best_v = name, v
    return best if best and (cur is None or best_v > cur) else None


def uv_receipt_url(prefixes: list[Path] | None = None) -> str | None:
    """The git URL from the uv tool receipt (uv-receipt.toml) of the environment running this doctor, or None
    when Cecilia was not installed with `uv tool install git+<url>`."""
    cands: list[Path] = []
    for base in prefixes if prefixes is not None else [Path(sys.prefix), Path(sys.executable).resolve().parent.parent,
                                                       Path(sys.executable).parent.parent]:
        cands += [base / "uv-receipt.toml", base.parent / "uv-receipt.toml"]
    for f in cands:
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            continue
        m = re.search(r'git\s*=\s*"([^"]+)"', text)
        if not m:
            continue
        url = re.split(r"[?#]", m.group(1), 1)[0]
        scheme, sep, rest = url.partition("://")
        if sep and "@" in rest.rsplit("/", 1)[-1]:          # .../repo@v20.0.1 -> .../repo
            head, _, last = rest.rpartition("/")
            rest = (head + "/" if head else "") + last.split("@", 1)[0]
        return (scheme + sep + rest) if sep else url
    return None


def installed_version() -> str:
    try:
        from cecilia import __version__ as v  # noqa: WPS433 — the uv tool package, when it runs this doctor
        return v
    except Exception:  # noqa: BLE001
        pass
    try:
        import cecilia_guard as G  # noqa: WPS433
        return G.VERSION
    except Exception:  # noqa: BLE001
        return ""


def check_update(timeout: float = UPDATE_TIMEOUT) -> None:
    """Best effort, never fails, at most ~`timeout` seconds: INFO when a newer vX.Y.Z tag exists upstream."""
    if os.environ.get("CECILIA_NO_UPDATE_CHECK"):
        return
    try:
        url = uv_receipt_url()
        current = installed_version()
        if not url or not current:
            return
        r = subprocess.run(["git", "ls-remote", "--tags", url], capture_output=True, text=True, timeout=timeout,
                           env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))
        if r.returncode != 0:
            return
        tag = newest_tag([ln.split("\t", 1)[-1] for ln in r.stdout.splitlines() if "\t" in ln], current)
        if tag:
            add("INFO", "new version", f"Cecilia {tag} is available (installed {current}): "
                f"uv tool install --force git+{url}@{tag}, then cecilia upgrade --all")
    except Exception:  # noqa: BLE001 — offline, no git, odd receipt: skip silently
        return


def check_config(root: Path) -> dict:
    f = root / ".cecilia" / "config.json"
    if not f.is_file():
        add("WARN", "config", ".cecilia/config.json missing — defaults apply")
        return {}
    try:
        cfg = json.loads(f.read_text(encoding="utf-8-sig"))
    except ValueError as e:
        add("FAIL", "config", f"invalid JSON: {e}")
        return {}
    known = {"roles", "plan_first", "docs_layout", "docs_root", "ui", "git", "parallel", "models", "profiles",
             "tool_rules", "guard", "workspace", "review", "scale", "flow", "flows", "orchestration", "lanes", "test",
             "fix_loop", "rules", "extensions", "consensus", "automation", "mcp", "antigravity"}
    unknown = [k for k in cfg if k not in known]
    missing = [k for k in ("profiles", "tool_rules", "docs_root", "review", "scale") if k not in cfg]
    if missing:
        add("WARN", "config", f"older config (missing {', '.join(missing)}) — defaults apply",
            "re-run the installer with --upgrade (migrates, backs up first)")
    if unknown:
        add("WARN", "config", f"unknown key(s): {', '.join(unknown)} — ignored")
    for p in cfg.get("profiles") or []:
        if isinstance(p, dict) and p.get("level") not in {"fast", "standard", "ask", "controlled", "deny"}:
            add("WARN", "config", f"profile '{p.get('name')}' level '{p.get('level')}' unknown — ignored by the guard")
    if not missing and not unknown:
        add("OK", "config", "v20 config")
    return cfg


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--project", help="project root (default: nearest folder with .cecilia/)")
    ap.add_argument("--no-update-check", action="store_true", help="skip the new-version notice (git ls-remote)")
    a = ap.parse_args()
    home_dir = Path(a.project).resolve() if a.project else find_root(Path.cwd().resolve())
    if sys.version_info < (3, 9):
        add("FAIL", "python", f"Python {sys.version.split()[0]} < 3.9")
    try:
        import cecilia_guard as G0  # noqa: WPS433
        project = G0.resolve_roots(home_dir)
        workspace = G0.WORKSPACE is not None
    except Exception:  # check_guard reports the failure
        project, workspace = home_dir, False
    root = home_dir
    G = check_guard(project)
    cfg = check_config(home_dir)
    check_interpreter(configured_python(cfg))
    check_claude_hook(home_dir, project)
    check_antigravity_hook(home_dir, project)
    check_global_leftovers(home_dir)
    check_antigravity_global()
    if (home_dir / ".agents").is_dir():
        check_agy_version()
        check_antigravity_mcp(home_dir)
        add("INFO", "agy start", f"start agy from the workspace: cecilia open {project.name} --agy")
    if workspace:
        check_workspace(home_dir, project, G)
    check_git(project if workspace else root, G, a.fix, workspace)
    check_mcp(project if workspace else root, cfg)
    if not a.no_update_check:
        check_update()
    if a.json:
        print(json.dumps({"project": str(root), "results": RESULTS}, indent=2, ensure_ascii=False))
    else:
        print(f"Cecilia doctor — {root}")
        for r in RESULTS:
            print(f"  {r['status']:4}  {r['check']:18} {r['detail']}")
            if r["fix"] and r["status"] not in ("OK", "INFO"):
                print(f"        fix: {r['fix']}")
    return 1 if any(r["status"] == "FAIL" for r in RESULTS) else 0


if __name__ == "__main__":
    sys.exit(main())
