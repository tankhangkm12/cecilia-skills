#!/usr/bin/env python3
"""Install Cecilia v20 for Claude Code and/or Antigravity — project-local or user-global.

Workspace mode (recommended — the project folder gets nothing; everything goes to <project>.cecilia/):
  python tools/install.py --project /abs/project --workspace --host claude --host antigravity --apply
  (usually through the `cecilia init` command of the uv tool)
  v20 workspace extras: .cecilia/registry.json (compiled roles/flows/lenses, incl. applied extensions from
  .cecilia/extensions/), rules/ (_project.md, roles/<role>.md, flows/<flow>.md — created once, never
  overwritten), CLAUDE.md/AGENTS.md telling the main session it is the cecilia-orchestrator.

In-project (older layout — files inside the repository, hidden by .git/info/exclude):
  python tools/install.py --project /abs/project --host claude --host antigravity
  python tools/install.py --project /abs/project --host claude --host antigravity --apply

User-global:
  python tools/install.py --global --host claude --host antigravity
  python tools/install.py --global --host claude --host antigravity --apply

Default is a dry run. With --apply, files are created.

Local-only (v19 default, project installs in a git repository): Cecilia's own paths are added to
.git/info/exclude (never to .gitignore — nothing about Cecilia reaches the shared repository), and the
push lock is switched on (`url.<prefix>.pushInsteadOf` in the repository's .git/config makes every push
fail until you run `.cecilia/bin/cecilia_mode.py --push-lock off` or `... push`). --no-push-lock skips the
lock. --home <dir> installs "global" into another directory (tests, portable setups).

Existing files with different content are never overwritten; host config conflicts are written as
*.cecilia-suggested for manual merge.

Upgrading (e.g. 19.2 -> 20): add --upgrade. Cecilia's OWN files (skills/cecilia-*, the Cecilia agent
files, .cecilia/bin/*) that differ are replaced, and files a new version no longer ships are retired —
every old copy is first backed up to .cecilia/backup/<timestamp>/ (global: ~/.cecilia-backup/<timestamp>/).
Your files are never replaced: mode, approvals, settings.json, hooks.json, .playwright/cli.config.json.
.cecilia/config.json is migrated (-> v20: new keys added with their defaults, nothing you set is
changed) only with --upgrade, after a backup, and the before -> after table is printed.

Hook interpreter (20.1): hook commands call a plain `python` (Windows) / `python3` (elsewhere) found on PATH,
or `guard.python` in .cecilia/config.json (`--python` sets it; an absolute path works too). Antigravity gets an
inline command without any quotes when no path has a space; on Windows with a space it falls back to the
.cecilia/bin/cecilia_guard_antigravity.cmd launcher. --upgrade replaces hook files an older Cecilia wrote
(absolute-path, quoted or launcher forms). `~/.cecilia/workspaces.json` lists every workspace installed or
upgraded here (`cecilia workspaces`, `cecilia upgrade --all`).

Project layout:
  .claude/skills/<skill>/  .claude/agents/<agent>.md  .claude/settings.json   (Claude Code)
  .agents/skills/<skill>/  .agents/agents/<agent>/agent.md  .agents/hooks.json (Antigravity)
  .cecilia/bin/  .cecilia/mode.json  .cecilia/config.json  .cecilia/approvals/

Global layout:
  ~/.claude/skills/  ~/.claude/agents/  ~/.claude/settings.json  ~/.claude/cecilia/bin/     (Claude Code)
  ~/.gemini/config/skills/ (2.0/IDE)  ~/.gemini/antigravity-cli/skills/ (CLI)
  ~/.gemini/config/agents/<agent>/agent.md  ~/.gemini/config/hooks.json  ~/.gemini/config/cecilia/bin/

Global install does not create per-project .cecilia state. Projects without it run in STANDARD mode
with the default config (every role on except cecilia-ui; git flow required).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import filecmp
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from roster import VERSION, default_config, migrate_config, policy  # noqa: E402

SKILLS = sorted(p.name for p in (ROOT / "skills").iterdir() if p.is_dir())
OLD_NAMES = {
    "cecilia-ba", "cecilia-onboard", "cecilia-design-be", "cecilia-design-fe",
    "cecilia-security", "cecilia-lead", "cecilia-verify",
}


class Plan:
    def __init__(self, base: Path, label: str, upgrade: bool = False, backup_dir: str = ".cecilia/backup"):
        self.base = base
        self.label = label
        self.upgrade = upgrade
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.backup = base / backup_dir / f"{stamp}-before-v{VERSION}"
        self.create: list[tuple[Path, Path | str]] = []
        self.replace: list[tuple[Path, Path | str]] = []
        self.retire: list[Path] = []
        self.same: list[Path] = []
        self.conflicts: list[tuple[Path, str]] = []
        self.notes: list[str] = []
        self.exclude: list[str] = []            # lines to add to .git/info/exclude (local-only)
        self.push_lock = False                  # switch the push lock on after writing
        self.config_migration: tuple[Path, dict, list] | None = None
        self.set_python: str | None = None      # --python: stored as guard.python in .cecilia/config.json
        self.register: tuple[Path, Path] | None = None   # (workspace, project) for ~/.cecilia/workspaces.json

    def file(self, dest_rel: str, src: Path | str, owned: bool = False):
        """owned=True: a file Cecilia ships and nobody edits (skills, agents, bin) — replaceable on --upgrade."""
        dest = self.base / dest_rel
        if dest.exists():
            try:
                equal = (dest.read_text(encoding="utf-8") == src) if isinstance(src, str) else \
                    filecmp.cmp(dest, src, shallow=False)
            except (OSError, UnicodeDecodeError):
                equal = False
            if equal:
                self.same.append(dest)
            elif owned and self.upgrade:
                self.replace.append((dest, src))
            else:
                hint = " - re-run with --upgrade to replace it (old copy backed up)" if owned else ""
                self.conflicts.append((dest, "exists with different content - not overwritten" + hint))
            return
        self.create.append((dest, src))

    def tree(self, dest_rel: str, src_dir: Path):
        shipped = set()
        for f in sorted(src_dir.rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts:
                rel = f.relative_to(src_dir).as_posix()
                shipped.add(rel)
                self.file(f"{dest_rel}/{rel}", f, owned=True)
        existing = self.base / dest_rel
        if self.upgrade and existing.is_dir():
            for f in sorted(existing.rglob("*")):
                if f.is_file() and "__pycache__" not in f.parts and f.relative_to(existing).as_posix() not in shipped:
                    self.retire.append(f)

    def host_config(self, dest_rel: str, content: str, merge_hint: str):
        dest = self.base / dest_rel
        side = self.base / (dest_rel + ".cecilia-suggested")
        if self.upgrade and dest.exists() and only_cecilia_settings(dest, content):
            self.file(dest_rel, content, owned=True)       # a file an older Cecilia wrote, never customised
            if side.exists():
                self.retire.append(side)                    # nothing left to merge
            return
        if dest.exists() and dest.read_text(encoding="utf-8-sig") != content:
            side = dest_rel + ".cecilia-suggested"
            if (self.base / side).exists() and (self.base / side).read_text(encoding="utf-8-sig") != content:
                self.replace.append((self.base / side, content))    # generated file: always refreshed
            else:
                self.file(side, content)
            self.notes.append(
                f"{dest_rel} already exists - NOT changed. Merge {side} into it yourself ({merge_hint})."
            )
        else:
            self.file(dest_rel, content)

    def display(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.base))
        except ValueError:
            return str(path)


# Permission rules earlier Cecilia versions wrote and this one no longer does (still "ours" on --upgrade).
LEGACY_RULES = {"Read(./.env)", "Read(./.env.*)", "Read(!.env.example)"}


def only_cecilia_settings(dest: Path, new_content: str) -> bool:
    """True when an existing Claude settings.json holds nothing but what Cecilia would write: the same
    top-level keys, every permission rule also present in the new file, and only the Cecilia hook."""
    try:
        old, new = json.loads(dest.read_text(encoding="utf-8-sig")), json.loads(new_content)
    except (OSError, ValueError):
        return False
    if not isinstance(old, dict) or set(old) - set(new):
        return False
    if set(new) == {"cecilia-guard"}:                   # Antigravity hooks.json: only Cecilia's hook group
        return only_cecilia_antigravity_hooks(old.get("cecilia-guard"), new.get("cecilia-guard"))
    perms_old, perms_new = old.get("permissions", {}), new.get("permissions", {})
    if not isinstance(perms_old, dict) or set(perms_old) - set(perms_new):
        return False
    for key, rules in perms_old.items():
        if key == "defaultMode":
            if rules != perms_new.get(key):
                return False
        elif not isinstance(rules, list) or set(rules) - set(perms_new.get(key, [])) - LEGACY_RULES:
            return False
    hooks = old.get("hooks", {})
    if not isinstance(hooks, dict) or set(hooks) - {"PreToolUse", "UserPromptSubmit"}:
        return False
    for event, entries in hooks.items():
        commands = [" ".join([str(h.get("command", ""))] + [str(a) for a in h.get("args", []) or []])
                    for e in entries if isinstance(e, dict) for h in e.get("hooks", []) if isinstance(h, dict)]
        if len(commands) != 1 or "cecilia_guard" not in commands[0]:
            return False
    return "PreToolUse" in hooks


# PreToolUse matchers earlier Cecilia versions wrote (19.x-20.1: files and commands only; 20.2 adds MCP + dispatch).
AG_OLD_MATCHERS = {"run_command|write_to_file|replace_file_content|multi_replace_file_content"}


def only_cecilia_antigravity_hooks(old, new) -> bool:
    """True when an Antigravity `cecilia-guard` hook group is one Cecilia wrote (19.x-20.1: one PreToolUse entry;
    20.2: PreToolUse + PreInvocation) and was not customised: only those events, one handler per event, every
    handler runs cecilia_guard (inline or via the .cmd launcher), and the matcher is a known Cecilia matcher."""
    if not isinstance(old, dict) or not old or set(old) - {"PreToolUse", "PreInvocation"} or "PreToolUse" not in old:
        return False
    known = set(AG_OLD_MATCHERS)
    for e in ((new or {}).get("PreToolUse") or []) if isinstance(new, dict) else []:
        if isinstance(e, dict) and isinstance(e.get("matcher"), str):
            known.add(e["matcher"])
    for event, entries in old.items():
        if not isinstance(entries, list) or len(entries) != 1 or not isinstance(entries[0], dict):
            return False
        entry = entries[0]
        if event == "PreToolUse" and entry.get("matcher") not in known:
            return False
        if event == "PreInvocation" and entry.get("matcher") not in (None, "", "*"):
            return False
        handlers = entry.get("hooks")
        if not isinstance(handlers, list) or len(handlers) != 1 or not isinstance(handlers[0], dict):
            return False
        if "cecilia_guard" not in str(handlers[0].get("command", "")):
            return False
    return True


def quote_cmd_arg(value: str) -> str:
    """Quote one executable/path for the host shell; double quotes work for our Windows/POSIX paths."""
    return '"' + value.replace('"', '\\"') + '"'


def needs_quote(value: str) -> bool:
    """A token that a shell would split or reinterpret (spaces, quotes, shell metacharacters)."""
    return not value or any(c in value for c in ' \t"\'&|<>^();`$%!')


def quote_if_needed(value: str) -> str:
    return quote_cmd_arg(value) if needs_quote(value) else value


def default_python(windows: bool | None = None) -> str:
    """20.1: the hook interpreter found on PATH — `python` on Windows (where `python3` often is the Store stub or
    missing), `python3` elsewhere."""
    windows = (os.name == "nt") if windows is None else windows
    return "python" if windows else "python3"


HOOK_PYTHON: dict = {"override": None}      # --python for this run (main() sets it)


def configured_python(base: Path | None = None, override: str | None = None, windows: bool | None = None) -> str:
    """--python, else `guard.python` in <base>/.cecilia/config.json, else the platform default."""
    override = override or HOOK_PYTHON.get("override")
    if override:
        return str(override).strip()
    if base is not None:
        guard = project_config(base).get("guard")
        py = guard.get("python") if isinstance(guard, dict) else None
        if isinstance(py, str) and py.strip():
            return py.strip()
    return default_python(windows)


def python_cmd(python: str | None = None) -> str:
    """The hook interpreter as a shell token: bare (`python3`) unless it contains a space or a quote."""
    return quote_if_needed(python or configured_python())


EXEC_FORM_MIN = (2, 1, 142)     # Claude Code release that added `args` (exec form) to command hooks
HOOK_FORM = {"form": "auto", "detected": None, "why": ""}


def claude_code_version():
    """(major, minor, patch) of the `claude` on PATH, or None when it cannot be found or read."""
    exe = shutil.which("claude")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", out or "")
    return tuple(int(x) for x in m.groups()) if m else None


def choose_hook_form(requested: str) -> str:
    """exec (no shell, safe with spaces and PowerShell) when Claude Code supports it; otherwise the quoted
    shell form, which Claude Code runs through Git Bash / sh."""
    if requested in {"exec", "shell"}:
        HOOK_FORM.update(form=requested, why=f"--hook-form {requested}")
        return requested
    ver = claude_code_version()
    HOOK_FORM["detected"] = ver
    if ver is None and os.name != "nt":
        HOOK_FORM.update(form="shell", why="Claude Code version not detected - shell form, which every version runs")
    elif ver is None:
        HOOK_FORM.update(form="exec", why="WARNING: Claude Code version not detected (`claude` not on PATH) - exec "
                         "form assumed; if your Claude Code is older than 2.1.142 re-run with --hook-form shell")
    elif ver >= EXEC_FORM_MIN:
        HOOK_FORM.update(form="exec", why=f"Claude Code {'.'.join(map(str, ver))} supports the exec form")
    else:
        HOOK_FORM.update(form="shell", why=f"Claude Code {'.'.join(map(str, ver))} is older than 2.1.142 - shell "
                         "form (needs Git Bash on Windows); update Claude Code and re-run for the exec form")
    return HOOK_FORM["form"]


def claude_abs(path: Path) -> str:
    """A path in Claude Code's absolute rule form: `//abs/posix/path` (`D:\\x` -> `//d/x`)."""
    posix = path.as_posix()
    if re.match(r"^[A-Za-z]:/", posix):
        posix = "/" + posix[0].lower() + posix[2:]
    return "/" + posix


def render_claude_settings(guard: Path, workspace: Path | None = None, project: Path | None = None,
                           main_agent: bool = True, python: str | None = None) -> str:
    """The Cecilia hook with absolute paths. Exec form: command + args, no shell. Shell form: one quoted
    command line for older Claude Code. Workspace mode: the hook names the workspace, the project is an
    additional directory, and the secret-file read denies are repeated for the project's absolute path.
    v20: `"agent": "cecilia-orchestrator"` makes the orchestrator the session's main thread (workspace and
    in-project installs); a global install never sets it (it would turn every Claude Code session into it)."""
    text = (ROOT / "adapters/claude-code/settings.cecilia.json").read_text(encoding="utf-8")
    data = json.loads(text)
    if not main_agent:
        data.pop("agent", None)
    elif workspace is not None:
        data.setdefault("agent", "cecilia-orchestrator")
    extra = ["--workspace", str(workspace)] if workspace else []
    py = python or configured_python(workspace or project)
    for event in ("PreToolUse", "UserPromptSubmit"):
        for entry in data["hooks"].get(event, []):
            for hook in entry["hooks"]:
                if HOOK_FORM["form"] == "shell":
                    ws = f" --workspace {quote_cmd_arg(workspace.as_posix())}" if workspace else ""
                    hook["command"] = f"{python_cmd(py)} {quote_cmd_arg(guard.as_posix())} --host claude{ws}"
                    hook.pop("args", None)
                else:
                    hook["command"] = py            # exec form: no shell, so no quoting at all
                    hook["args"] = [str(guard) if a == "__CECILIA_GUARD__" else a for a in hook["args"]] + extra
    if project is not None:
        perms = data["permissions"]
        perms["additionalDirectories"] = [str(project)]
        base = claude_abs(project)
        perms["deny"] += [f"Read({base}/{r[len('Read('):]}" for r in list(perms["deny"])
                          if r.startswith("Read(**/")]
    return json.dumps(data, indent=2) + "\n"


AG_LAUNCHER = "cecilia_guard_antigravity.cmd"


def antigravity_hook_command(guard_path: Path, workspace: Path | None = None, windows: bool | None = None,
                             python: str | None = None) -> tuple[str, str | None]:
    """(hook command, launcher .cmd text or None).

    20.1: the interpreter is a plain `python`/`python3` from PATH (or `guard.python`). When neither the interpreter
    nor the guard/workspace paths contain a space or a quote, the command is inline with NO quotes at all (Windows:
    backslash paths) — e.g. `python D:\\w\\k8s.cecilia\\.cecilia\\bin\\cecilia_guard.py --host antigravity --workspace
    D:\\w\\k8s.cecilia`. Antigravity on Windows hands the command to cmd.exe with its double quotes backslash-escaped
    (`\\"C:/Users/Thanh Tan/...\\"` is not recognized), so when a path has a space the hook command is the bare
    backslash path of a small launcher next to the guard, and the launcher holds the quoted command line.
    POSIX shells handle quotes: only the tokens that need them are quoted."""
    windows = (os.name == "nt") if windows is None else windows
    py = python or default_python(windows)
    ws_path = workspace.as_posix() if workspace is not None else None
    if not windows:
        ws = f" --workspace {quote_if_needed(ws_path)}" if ws_path else ""
        return f"{quote_if_needed(py)} {quote_if_needed(guard_path.as_posix())} --host antigravity{ws}", None

    def win(p) -> str:
        return str(p).replace("/", "\\")
    py_w = win(py) if ("/" in py or "\\" in py) else py
    tokens = [py_w, win(guard_path.as_posix())] + ([win(ws_path)] if ws_path else [])
    if not any(needs_quote(t) for t in tokens):
        ws = f" --workspace {win(ws_path)}" if ws_path else ""
        return f"{py_w} {win(guard_path.as_posix())} --host antigravity{ws}", None
    ws = f' --workspace "{win(ws_path)}"' if ws_path else ""
    body = ("@echo off\n"
            "rem Cecilia guard for Antigravity (generated by the installer; re-run `cecilia upgrade` to refresh)\n"
            f'{quote_if_needed(py_w)} "{win(guard_path.as_posix())}" --host antigravity{ws}\n'
            "exit /b %ERRORLEVEL%\n")
    return win((guard_path.parent / AG_LAUNCHER).as_posix()), body


def render_antigravity_hooks(guard_path: Path, workspace: Path | None = None, plan: "Plan | None" = None,
                             windows: bool | None = None, python: str | None = None) -> str:
    data = json.loads((ROOT / "adapters/antigravity/hooks.json").read_text(encoding="utf-8"))
    py = python or configured_python(workspace, windows=windows)
    command, launcher = antigravity_hook_command(guard_path, workspace, windows, py)
    launcher_file = guard_path.parent / AG_LAUNCHER
    if launcher is not None:
        if " " in command:
            if plan is not None:
                plan.notes.append(f"The Antigravity hook launcher path contains a space ({command}); Antigravity on "
                                  "Windows may not run it. Move the workspace to a path without spaces.")
        if plan is not None:
            rel = launcher_file.relative_to(plan.base).as_posix()
            plan.file(rel, launcher, owned=True)
    elif plan is not None and plan.upgrade and launcher_file.is_file():
        plan.retire.append(launcher_file)           # 20.0.1 launcher, replaced by the inline command
    for entries in data["cecilia-guard"].values():     # 20.2: PreToolUse and PreInvocation run the same guard
        for entry in entries:
            for h in entry.get("hooks", []):
                if h.get("command") == "__CECILIA_GUARD_COMMAND__":
                    h["command"] = command
    return json.dumps(data, indent=2) + "\n"


def add_runtime(plan: Plan, prefix: str = ".cecilia"):
    plan.file(f"{prefix}/bin/cecilia_guard.py", ROOT / "guard" / "cecilia_guard.py", owned=True)
    plan.file(f"{prefix}/bin/policy.json", ROOT / "guard" / "policy.json", owned=True)
    plan.file(f"{prefix}/bin/cecilia_doctor.py", ROOT / "guard" / "cecilia_doctor.py", owned=True)
    plan.file(f"{prefix}/bin/cecilia_approve.py", ROOT / "guard" / "cecilia_approve.py", owned=True)
    plan.file(f"{prefix}/bin/cecilia_mode.py", ROOT / "guard" / "cecilia_mode.py", owned=True)
    plan.file(f"{prefix}/README.md", (ROOT / "guard" / "README.md").read_text(encoding="utf-8"), owned=True)


def add_project_runtime(plan: Plan):
    add_runtime(plan)
    if not (plan.base / ".cecilia" / "mode.json").exists():       # Cecilia's current mode is never touched
        plan.file(".cecilia/mode.json", '{\n  "mode": "standard",\n  "set_by": "installer"\n}\n')
    plan.file(".cecilia/approvals/.keep", "")
    cfg_file = plan.base / ".cecilia" / "config.json"
    if not cfg_file.exists():
        plan.file(".cecilia/config.json", json.dumps(default_config(), indent=2) + "\n")
    elif plan.upgrade:
        try:
            old = json.loads(cfg_file.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            old = None
        if isinstance(old, dict):
            new, changes = migrate_config(old)
            if changes:
                plan.config_migration = (cfg_file, new, changes)


AG_MODEL_RX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def antigravity_model_overrides(cfg: dict | None, plan: "Plan | None" = None) -> dict:
    """{agent name: model} from `.cecilia/config.json` → `antigravity.models` ({"plan": "flash", "cecilia-dev-be":
    "pro", …}; short or full role names). Values are `inherit`, `flash`, `pro` or a model id; anything else is
    ignored with a note."""
    ag = (cfg or {}).get("antigravity") if isinstance(cfg, dict) else None
    models = ag.get("models") if isinstance(ag, dict) else None
    if not isinstance(models, dict):
        return {}
    out = {}
    for role, model in models.items():
        if not isinstance(role, str) or not role.strip():
            continue
        name = role.strip() if role.strip().startswith("cecilia-") else f"cecilia-{role.strip()}"
        if isinstance(model, str) and AG_MODEL_RX.match(model.strip()):
            out[name] = model.strip()
        elif plan is not None:
            plan.notes.append(f"antigravity.models.{role} = {model!r} ignored (use inherit, flash, pro or a model id).")
    return out


def with_agent_model(text: str, model: str) -> str:
    """agent.md text with its frontmatter `model:` line set to `model` (added before the closing --- if missing)."""
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end < 0:
        return text
    head, rest = text[:end], text[end:]
    if re.search(r"^model:.*$", head, re.M):
        head = re.sub(r"^model:.*$", f"model: {model}", head, count=1, flags=re.M)
    else:
        head += f"\nmodel: {model}"
    return head + rest


def antigravity_agents(plan: Plan, dest_root: str, sources: dict | None = None, models: dict | None = None):
    """sources: {agent name: Path | rendered text}; default = the shipped adapters. models: {agent name: model}
    from the workspace config (`antigravity.models`) — rewrites that agent's frontmatter `model:` line."""
    if sources is None:
        sources = agent_sources(None)[1]
    for name, src in sorted(sources.items()):
        if models and name in models:
            text = src.read_text(encoding="utf-8") if isinstance(src, Path) else str(src)
            src = with_agent_model(text, models[name])
        plan.file(f"{dest_root}/{name}/agent.md", src, owned=True)


def agent_sources(reg: dict | None) -> tuple[dict, dict]:
    """({file name: src} for .claude/agents, {agent name: src} for Antigravity agents). With a registry that holds
    extensions, every agent file is rendered from it (tools/build_adapters.py), so new roles get host agents and the
    orchestrator may dispatch them; otherwise the shipped adapters are copied."""
    if reg is not None and any(v.get("_source") == "extension" for v in reg.get("roles", {}).values()):
        try:
            import build_adapters as B  # noqa: E402  (A1 — renders from a registry dict)
            claude = {Path(k).name: v for k, v in B.claude_files(reg).items() if k.startswith("adapters/claude-code/agents/")}
            ag = {Path(k).parent.name: v for k, v in B.antigravity_files(reg).items()
                  if k.startswith("adapters/antigravity/agents/")}
            return claude, ag
        except Exception as e:      # noqa: BLE001 — fall back to the shipped adapters, never half an install
            print(f"WARNING: extension agent files not rendered ({e}); shipped agents installed", file=sys.stderr)
    claude = {f.name: f for f in sorted((ROOT / "adapters/claude-code/agents").glob("*.md"))}
    ag_root = ROOT / "adapters" / "antigravity" / "agents"
    ag = {d.name: d / "agent.md" for d in sorted(ag_root.iterdir()) if (d / "agent.md").is_file()}
    return claude, ag


def workspace_registry(workspace: Path, plan: Plan | None = None):
    """(registry module, merged registry with the workspace's applied extensions, extensions dir or None).
    Invalid extensions are left out (core registry only) with a note. (None, None, None) when tools/registry.py
    is not available."""
    try:
        import registry as REG  # noqa: E402  (A1)
    except ImportError:
        return None, None, None
    cfg = project_config(workspace)
    rel = (cfg.get("extensions") or {}).get("dir") if isinstance(cfg.get("extensions"), dict) else None
    ext = Path(rel or ".cecilia/extensions")
    ext = ext if ext.is_absolute() else workspace / ext
    core = REG.load(ROOT)
    if not ext.is_dir():
        return REG, core, None
    merged = REG.load(ROOT, extensions=ext)
    known = set(REG.validate(core, ROOT))
    errs = [e for e in REG.validate(merged, ROOT) if e not in known]
    if errs:
        if plan is not None:
            plan.notes.append(f"Extensions in {ext} are INVALID and were not installed ({len(errs)} error(s)): "
                              + "; ".join(errs[:3]) + " — fix them (`cecilia extension check`) and upgrade again.")
        return REG, core, None
    return REG, merged, ext


def add_rules(plan: Plan, workspace: Path, reg: dict | None):
    """rules/_project.md, rules/roles/<short>.md per role, rules/flows/<flow>.md per flow — only the missing ones;
    Cecilia's rules files are never overwritten (also not on --upgrade)."""
    from workspace_tools import rules_rel, rules_template  # noqa: E402
    if reg:
        roles, flows = sorted(reg.get("roles", {})), sorted(reg.get("flows", {}))
    else:
        from roster import all_names  # noqa: E402
        roles, flows = all_names(), ["personal", "team"]
    wanted = [("project", "")] + [("role", r) for r in roles] + [("flow", f) for f in flows]
    added = 0
    for kind, name in wanted:
        rel = rules_rel(kind, name)
        if not (workspace / rel).exists():
            plan.file(rel, rules_template(kind, name))
            added += 1
    if added and (workspace / "rules").is_dir():
        plan.notes.append(f"rules/: {added} missing rules file(s) added (header only); your existing rules are kept.")


def add_skills(plan: Plan, roots: set[str], existing_base: Path | None = None):
    for sr in sorted(roots):
        for skill in SKILLS:
            plan.tree(f"{sr}/{skill}", ROOT / "skills" / skill)
        existing = (existing_base or plan.base) / sr
        if existing.is_dir():
            old = sorted(p.name for p in existing.iterdir() if p.name in OLD_NAMES)
            if old:
                plan.notes.append(
                    f"{sr} still contains older Cecilia skills {old} - move them out before using v20."
                )


def project_config(project: Path) -> dict:
    f = project / ".cecilia" / "config.json"
    try:
        cfg = json.loads(f.read_text(encoding="utf-8-sig")) if f.is_file() else default_config()
        return cfg if isinstance(cfg, dict) else {}
    except (OSError, ValueError):
        return {}


def exclude_lines(project: Path) -> list[str]:
    f = project / ".git" / "info" / "exclude"
    try:
        return [x.strip() for x in f.read_text(encoding="utf-8").splitlines()]
    except OSError:
        return []


def hook_python_note(py: str) -> str:
    where = shutil.which(py) if not Path(py).is_absolute() else (py if Path(py).exists() else None)
    return (f"Guard hooks run `{py}`" + (f" ({where})" if where and where != py else "") +
            (" — NOT found on PATH here: install Python 3.9+ from python.org (tick \"Add to PATH\") or set "
             "guard.python to an absolute path (`cecilia upgrade --python <path>`)" if not where else "") +
            ". Change it with `--python` (stored as guard.python in .cecilia/config.json).")


def set_config_python(cfg_file: Path, python: str) -> bool:
    """guard.python = python in an existing config.json; True when the file changed."""
    try:
        cfg = json.loads(cfg_file.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return False
    if not isinstance(cfg, dict):
        return False
    guard = cfg.get("guard") if isinstance(cfg.get("guard"), dict) else {}
    if guard.get("python") == python:
        return False
    guard["python"] = python
    cfg["guard"] = guard
    cfg_file.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True


def workspaces_file() -> Path:
    """~/.cecilia/workspaces.json (CECILIA_WORKSPACES overrides the path — tests, portable setups)."""
    env = os.environ.get("CECILIA_WORKSPACES")
    return Path(env) if env else Path.home() / ".cecilia" / "workspaces.json"


def read_workspaces(path: Path | None = None) -> list[dict]:
    f = path or workspaces_file()
    try:
        data = json.loads(f.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    items = data.get("workspaces") if isinstance(data, dict) else None
    return [w for w in items or [] if isinstance(w, dict) and w.get("workspace")]


def _same_path(a: str, b: str) -> bool:
    na, nb = os.path.normpath(str(a)), os.path.normpath(str(b))
    return (na.lower() == nb.lower()) if os.name == "nt" else na == nb


def register_workspace(workspace: Path, project: Path, name: str | None = None, path: Path | None = None) -> Path:
    """Add or refresh {"workspace","project","name","updated"} in ~/.cecilia/workspaces.json (deduplicated by the
    workspace path). The MCP server and `cecilia upgrade --all` read this file."""
    f = path or workspaces_file()
    items = [w for w in read_workspaces(f) if not _same_path(w["workspace"], str(workspace))]
    items.append({"workspace": str(workspace), "project": str(project), "name": name or Path(project).name,
                  "updated": _dt.datetime.now().astimezone().isoformat(timespec="seconds")})
    items.sort(key=lambda w: str(w.get("name", "")).lower())
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"workspaces": items}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, f)
    return f


def build_project(project: Path, hosts: set[str], upgrade: bool = False, push_lock: bool = True,
                  python: str | None = None) -> Plan:
    plan = Plan(project, f"Project: {project}", upgrade)
    add_project_runtime(plan)
    py = configured_python(project, python)
    plan.set_python = python or HOOK_PYTHON.get("override") or None
    plan.register = (project, project)
    ui = project_config(project).get("ui")
    browser = ui.get("browser", "playwright-cli") if isinstance(ui, dict) else "playwright-cli"
    if browser == "playwright-cli":
        # Limits the agent's browser to local pages; Cecilia's file (the guard blocks agent edits).
        plan.file(".playwright/cli.config.json", ROOT / "shared" / "scoped" / "frontend" / "playwright-cli.config.json")

    skill_roots: set[str] = set()
    if "claude" in hosts:
        skill_roots.add(".claude/skills")
        for f in sorted((ROOT / "adapters/claude-code/agents").glob("*.md")):
            plan.file(f".claude/agents/{f.name}", f, owned=True)
        plan.host_config(
            ".claude/settings.json",
            render_claude_settings(project / ".cecilia" / "bin" / "cecilia_guard.py", python=py),
            "add the hooks.PreToolUse entry and permission rules",
        )

    if "antigravity" in hosts:
        skill_roots.add(".agents/skills")
        antigravity_agents(plan, ".agents/agents", models=antigravity_model_overrides(project_config(project), plan))
        hooks = render_antigravity_hooks(project / ".cecilia/bin/cecilia_guard.py", plan=plan, python=py)
        plan.host_config(".agents/hooks.json", hooks, "add the cecilia-guard hook")

    add_skills(plan, skill_roots, project)

    for agents_dir in (".claude/agents", ".agents/agents"):
        directory = project / agents_dir
        if directory.is_dir():
            old = sorted(p.name for p in directory.iterdir() if p.stem in OLD_NAMES or p.name in OLD_NAMES)
            if old:
                plan.notes.append(f"{agents_dir} still contains older Cecilia agents {old} - archive them.")

    if (project / ".git").exists():
        wanted = list(policy()["local_only_paths"])
        for created, host_file in ((".claude/settings.json", "claude"), (".agents/hooks.json", "antigravity")):
            if host_file in hosts and any(d == project / created for d, _ in plan.create):
                wanted.append(created)            # a host file Cecilia created alone: Cecilia's, stays local
        have = exclude_lines(project)
        plan.exclude = [w for w in wanted if w not in have]
        plan.push_lock = push_lock
        if plan.exclude:
            plan.notes.append("Local-only: " + str(len(plan.exclude)) + " Cecilia path(s) go to .git/info/exclude "
                              "(this clone only — nothing is added to .gitignore or committed).")
        if push_lock:
            plan.notes.append("Push lock ON after install: every `git push` here fails until you run "
                              "`python .cecilia/bin/cecilia_mode.py push …` (unlock, push, relock) or "
                              "`--push-lock off`. Install with --no-push-lock to skip.")
    plan.notes.append(
        "Default work mode is STANDARD. Switch to CONTROLLED with `.cecilia/bin/cecilia_mode.py controlled` "
        "when you want strict G2 scope enforcement."
    )
    plan.notes.append(
        "Roles, plan_first, git, parallel, docs_layout and ui (browser, style) live in .cecilia/config.json — edit "
        "it by hand; every role is on except cecilia-ui. Check it with `.cecilia/bin/cecilia_mode.py --show` and `.cecilia/bin/cecilia_doctor.py`."
    )
    plan.notes.append(hook_python_note(py))
    if "claude" in hosts:
        plan.notes.append(f"Claude Code hook: {HOOK_FORM['form']} form ({HOOK_FORM['why']}). Check with /hooks, "
                          "then HOST-SMOKE H00 (a push must be denied).")
    if not (project / ".git").exists():
        plan.notes.append("This folder is not a git repository yet: Cecilia edits only on a task branch — run "
                          "`git init`, make a first commit, re-run this installer (local-only exclude + push lock), "
                          "then let the agent create task branches.")
    plan.notes.append("Run docs/HOST-SMOKE.md on this project after install.")
    return plan


def default_workspace(project: Path) -> Path:
    """`D:\\projects\\shop` -> `D:\\projects\\shop.cecilia` (next to the project, never inside it)."""
    return project.parent / f"{project.name}.cecilia"


WORKSPACE_GUIDE = """# Cecilia workspace — {name}

This folder is the Cecilia workspace for the project at:

    {project}

## This session is the cecilia-orchestrator

The main session here is **cecilia-orchestrator** (Claude Code: `"agent"` in `.claude/settings.json`; Antigravity:
its `mainAgent`). Load the `cecilia-orchestrator` skill and its `references/common/core-min.md` first.

- **Never do specialist work yourself** — no code, tests, reviews, designs or migrations, not even in FAST. You
  write only under `tensura/`; everything else is dispatched to the matching cecilia role agent.
- **FAST:** dispatch one role with a 3-line brief (no workflow file).
- **STANDARD and CONTROLLED:** `workflow.py options` writes 2–3 workflow options (agents per kind, split, test and
  review lenses, time + token estimate) → show them → **Cecilia chooses** (`workflow.py choose`) → dispatch every
  agent with the brief from `workflow.py brief` (first line `[cecilia-brief …]`). No writer before her choice.
- Run the chosen agents in parallel; review panel from STANDARD; fix loop up to `fix_loop.max_rounds`, then give
  Cecilia options. Only Cecilia approves, pushes, opens PRs, merges or deploys.
- **Rules:** read `rules/_project.md` and `rules/flows/<flow>.md` before planning; each brief embeds the role's
  `rules/roles/<role>.md`. Only Cecilia edits `rules/` (`cecilia rules add …`).
- **Current flow:** `{flow}` — the source of truth is `flow` in `.cecilia/config.json` (`cecilia flow` switches it);
  follow that flow's guide (`.cecilia/registry.json` → `flows`).

## Where things live

- **Code** lives in the project folder above. Run git, builds and tests there (`cd "{project}"` or `git -C`).
- **Docs, plans, reports, task state** live here, in `tensura/` (`tensura/docs`, `tensura/plans`,
  `tensura/reports/<TASK>/`, `tensura/tasks/<TASK>/` with `state.md`, `workflow.json`, `run.json`). Worktrees:
  `.worktrees/`.
- Before the first plan read `tensura/conventions.md` and `tensura/lessons.md` when they exist.
- Every finish: task branch, full reports in `tensura/reports/<TASK>/`, and a reply of at most 15 lines that
  includes **Rollback** (start SHA + commands) and **Deviations:** (`none` or what differs).
- **Never** create Cecilia files (skills, agents, hooks, `.cecilia/`, `tensura/`, `rules/`) inside the project, and
  never copy anything from here into it. Nothing here is committed or pushed anywhere: local-only.
- Skills, agents, hooks, `rules/` and `.cecilia/` here are Cecilia's own — only she changes them.
"""


def build_workspace(project: Path, workspace: Path, hosts: set[str], upgrade: bool = False,
                    push_lock: bool = False, python: str | None = None) -> Plan:
    """Workspace mode (v19, v20 extras): everything Cecilia installs goes to a sidecar folder; the project gets nothing."""
    if workspace == project or project in workspace.parents or workspace in project.parents:
        raise ValueError("the workspace must be a separate folder next to the project, not inside it (or around it)")
    plan = Plan(workspace, f"Workspace: {workspace}\nProject:   {project} (nothing is written there)", upgrade)
    add_project_runtime(plan)
    cfg_file = workspace / ".cecilia" / "config.json"
    if not cfg_file.exists():
        cfg = default_config()
        cfg["workspace"] = {"project": str(project)}
        plan.create = [(d, s) for d, s in plan.create if d != cfg_file]
        plan.file(".cecilia/config.json", json.dumps(cfg, indent=2) + "\n")
    else:
        try:
            cur = json.loads(cfg_file.read_text(encoding="utf-8-sig"))
            cur_proj = (cur.get("workspace") or {}).get("project")
        except (OSError, ValueError, AttributeError):
            cur_proj = None
        if cur_proj and Path(cur_proj) != project:
            plan.conflicts.append((cfg_file, f"serves {cur_proj}, not {project} — pick another --workspace"))
    ui = project_config(workspace).get("ui")
    browser = ui.get("browser", "playwright-cli") if isinstance(ui, dict) else "playwright-cli"
    if browser == "playwright-cli":
        plan.file(".playwright/cli.config.json", ROOT / "shared" / "scoped" / "frontend" / "playwright-cli.config.json")
    guard = workspace / ".cecilia" / "bin" / "cecilia_guard.py"
    py = configured_python(workspace, python)
    plan.set_python = python or HOOK_PYTHON.get("override") or None
    plan.register = (workspace, project)
    cfg_now = plan.config_migration[1] if plan.config_migration else project_config(workspace)
    flow = cfg_now.get("flow") if isinstance(cfg_now.get("flow"), str) and cfg_now.get("flow") else "personal"
    guide = WORKSPACE_GUIDE.format(name=project.name, project=project, flow=flow)
    own = [f for f in ("CLAUDE.md", "AGENTS.md", ".claude/CLAUDE.md") if (project / f).is_file()]
    claude_guide, agents_guide = guide, guide
    if own:
        # Claude Code expands `@path` imports at launch (asks once to approve an import outside the workspace).
        claude_guide += ("\n## The project's own instructions\n\n" + "\n".join(f"@{(project / f).as_posix()}" for f in own)
                         + "\n\nThey win over Cecilia's defaults where they conflict (repository conventions), never over "
                         "the guard, local-only, `rules/` or Cecilia's decisions.\n")
        agents_guide += ("\n## The project's own instructions\n\nRead these before the first edit: "
                         + ", ".join(f"`{(project / f).as_posix()}`" for f in own) + ".\n")
    # v20: compiled registry (core + applied extensions), extension skills/agents, rules/ folder.
    reg_mod, reg, ext = workspace_registry(workspace, plan)
    if reg_mod is not None:
        plan.file(".cecilia/registry.json", json.dumps(reg_mod.compile(reg), indent=2, ensure_ascii=False) + "\n",
                  owned=True)
    else:
        plan.notes.append("tools/registry.py not found — .cecilia/registry.json not written (the v20 guard gates stay off).")
    claude_agents, ag_agents = agent_sources(reg if ext else None)
    ext_skills = sorted(d for d in (ext / "skills").iterdir() if d.is_dir()) if ext and (ext / "skills").is_dir() else []
    skill_roots: set[str] = set()
    if "claude" in hosts:
        skill_roots.add(".claude/skills")
        for fname, src in sorted(claude_agents.items()):
            plan.file(f".claude/agents/{fname}", src, owned=True)
        plan.host_config(".claude/settings.json", render_claude_settings(guard, workspace, project, python=py),
                         "add the hooks, agent, additionalDirectories and permission rules")
        plan.file("CLAUDE.md", claude_guide, owned=True)
    if "antigravity" in hosts:
        skill_roots.add(".agents/skills")
        antigravity_agents(plan, ".agents/agents", ag_agents, models=antigravity_model_overrides(cfg_now, plan))
        plan.host_config(".agents/hooks.json", render_antigravity_hooks(guard, workspace, plan=plan, python=py),
                         "add the cecilia-guard hook")
        plan.file("AGENTS.md", agents_guide, owned=True)
    add_skills(plan, skill_roots, workspace)
    for d in [d for d in ext_skills if d.name in SKILLS]:
        plan.conflicts.append((d, f"extension skill {d.name} has the name of a core skill — not installed"))
    ext_skills = [d for d in ext_skills if d.name not in SKILLS]
    for sr in sorted(skill_roots):
        for d in ext_skills:       # extension skills install like core skills (replaced on --upgrade)
            plan.tree(f"{sr}/{d.name}", d)
    if ext_skills:
        plan.notes.append("Extensions installed: " + ", ".join(d.name for d in ext_skills) + f" (from {ext}).")
    add_rules(plan, workspace, reg)
    plan.file("tensura/README.md", f"# tensura — docs, plans and reports for {project.name}\n\nLocal-only. "
              "Index of documents and reports goes here.\n")
    plan.file(f"{project.name}.code-workspace", json.dumps(
        {"folders": [{"path": ".", "name": f"{project.name} (Cecilia)"}, {"path": str(project), "name": project.name}],
         "settings": {"files.exclude": {"**/__pycache__": True}}}, indent=2) + "\n", owned=True)
    plan.push_lock = push_lock and (project / ".git").exists()
    plan.notes.append(f"Open the workspace, not the project: Claude Code — `cd \"{workspace}\"` then `claude` "
                      f"(the project is an additional directory); Antigravity — open {project.name}.code-workspace, "
                      f"or for the agy CLI `cecilia open {project.name} --agy` (starts agy in the workspace; agy "
                      "started from any other folder loads none of Cecilia's hooks, agents or main agent).")
    plan.notes.append("The project folder is not touched: no skills, hooks, .cecilia/, tensura/ or exclude lines in it. "
                      "The guard still denies every agent push/PR; `cecilia push-lock on` adds a git-level lock "
                      "(it writes the project's .git/config — off by default for that reason).")
    plan.notes.append(hook_python_note(py))
    if "claude" in hosts:
        plan.notes.append(f"Claude Code hook: {HOOK_FORM['form']} form ({HOOK_FORM['why']}). Check with /hooks, "
                          "then HOST-SMOKE H00 (a push must be denied).")
    if not (project / ".git").exists():
        plan.notes.append("The project is not a git repository yet: Cecilia edits only on a task branch — "
                          "`git init` and a first commit there first.")
    return plan


def build_global(home: Path, hosts: set[str], upgrade: bool = False, python: str | None = None) -> Plan:
    plan = Plan(home, f"Global home: {home}", upgrade, ".cecilia-backup")
    py = configured_python(None, python)
    if "claude" in hosts:
        add_runtime(plan, ".claude/cecilia")
        add_skills(plan, {".claude/skills"}, home)
        for f in sorted((ROOT / "adapters/claude-code/agents").glob("*.md")):
            plan.file(f".claude/agents/{f.name}", f, owned=True)
        guard = home / ".claude/cecilia/bin/cecilia_guard.py"
        plan.host_config(".claude/settings.json", render_claude_settings(guard, main_agent=False, python=py),
                         "add the hooks.PreToolUse entry and permission rules")
        plan.notes.append("Claude Code global: skills/agents in ~/.claude, guard in ~/.claude/cecilia/bin. "
                          f"Hook: {HOOK_FORM['form']} form ({HOOK_FORM['why']}). Run /agents and /hooks to verify.")
    plan.notes.append(hook_python_note(py))
    if "antigravity" not in hosts:
        return plan
    cfg = ".gemini/config"
    cli = ".gemini/antigravity-cli"

    # The guard is global, but mode/approval state stays repository-local.
    add_runtime(plan, f"{cfg}/cecilia")

    skill_roots = {f"{cfg}/skills", f"{cli}/skills"}
    add_skills(plan, skill_roots, home)
    antigravity_agents(plan, f"{cfg}/agents")

    guard = home / cfg / "cecilia/bin/cecilia_guard.py"
    hooks = render_antigravity_hooks(guard, plan=plan, python=py)
    plan.host_config(f"{cfg}/hooks.json", hooks, "add the cecilia-guard hook")

    plan.notes.append(
        "Global Antigravity skills are installed to both ~/.gemini/config/skills (2.0/IDE) and "
        "~/.gemini/antigravity-cli/skills (CLI). Agents and hooks use ~/.gemini/config."
    )
    plan.notes.append(
        "Global install does not create .cecilia inside every repository. Without project state, the guard "
        "uses STANDARD behavior. Use the project-local installer for repositories where you want persistent "
        "FAST/CONTROLLED mode and G2 approvals."
    )
    plan.notes.append("Reload with `/skills reload`, then open `/agents` and verify the Cecilia roster.")
    return plan


def _backup(plan: Plan, dest: Path):
    target = plan.backup / dest.relative_to(plan.base)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(dest, target)


def apply(plan: Plan):
    for dest, _ in plan.replace:
        _backup(plan, dest)
    for dest in plan.retire:
        _backup(plan, dest)
        dest.unlink()
    for dest, src in plan.create + plan.replace:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(src, str):
            dest.write_text(src, encoding="utf-8")
        else:
            shutil.copyfile(src, dest)
        if dest.suffix == ".py" and "cecilia/bin" in dest.as_posix():
            dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    if plan.config_migration:
        cfg_file, new, _ = plan.config_migration
        _backup(plan, cfg_file)
        cfg_file.write_text(json.dumps(new, indent=2) + "\n", encoding="utf-8")
    if plan.set_python:
        set_config_python(plan.base / ".cecilia" / "config.json", plan.set_python)
    if plan.exclude:
        f = plan.base / ".git" / "info" / "exclude"
        f.parent.mkdir(parents=True, exist_ok=True)
        text = f.read_text(encoding="utf-8") if f.is_file() else ""
        if text and not text.endswith("\n"):
            text += "\n"
        text += "# Cecilia (local-only: never committed)\n" + "\n".join(plan.exclude) + "\n"
        f.write_text(text, encoding="utf-8")
    if plan.push_lock:
        sys.path.insert(0, str(ROOT / "guard"))
        import cecilia_mode  # noqa: E402
        try:
            print(cecilia_mode.set_push_lock(plan.base, True))
        except (RuntimeError, OSError, subprocess.SubprocessError) as e:
            print(f"WARNING: push lock not set ({e}) — run `.cecilia/bin/cecilia_mode.py --push-lock on` yourself.")



def _utf8_console() -> None:
    """Windows consoles default to a legacy code page; keep output readable and crash-free."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

def main() -> int:
    _utf8_console()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    target = ap.add_mutually_exclusive_group(required=True)
    target.add_argument("--project", help="absolute path of the project to install into")
    target.add_argument("--global", dest="global_install", action="store_true", help="install user-global customization")
    ap.add_argument("--host", action="append", choices=["claude", "antigravity"], required=True)
    ap.add_argument("--apply", action="store_true", help="create the files (default: dry run)")
    ap.add_argument("--hook-form", choices=["auto", "exec", "shell"], default="auto",
                    help="Claude Code hook form: exec (2.1.142+, no shell) or shell; auto detects `claude --version`")
    ap.add_argument("--upgrade", action="store_true",
                    help="replace Cecilia's own files that differ (skills, agents, bin) after backing them up")
    ap.add_argument("--home", help="with --global: install into this directory instead of your home (tests, portable)")
    ap.add_argument("--no-push-lock", action="store_true", help="in-project install: do not switch the push lock on")
    ap.add_argument("--workspace", nargs="?", const="auto",
                    help="workspace mode (recommended): install into a sidecar folder, nothing into the project; "
                         "default folder <project>.cecilia next to it")
    ap.add_argument("--push-lock", action="store_true",
                    help="workspace mode: also switch the git-level push lock on (writes the project's .git/config)")
    ap.add_argument("--python", help="interpreter the guard hooks run (default: guard.python in the config, else "
                    "`python` on Windows / `python3` elsewhere, found on PATH); stored as guard.python")
    args = ap.parse_args()
    hosts = set(args.host)
    HOOK_PYTHON["override"] = (args.python or "").strip() or None
    if "claude" in hosts:
        choose_hook_form(args.hook_form)

    try:
        if args.home and not args.global_install:
            print("ERROR: --home only goes with --global", file=sys.stderr)
            return 2
        if args.global_install:
            home = Path(args.home).resolve() if args.home else Path.home().resolve()
            plan = build_global(home, hosts, args.upgrade)
        else:
            project = Path(args.project)
            if not project.is_absolute() or not project.is_dir():
                print("ERROR: --project must be an existing absolute path", file=sys.stderr)
                return 2
            if project.resolve() == Path.home().resolve():
                print("ERROR: use --global for your home-level install; --project must point to a repository", file=sys.stderr)
                return 2
            if args.workspace:
                ws = default_workspace(project.resolve()) if args.workspace == "auto" else Path(args.workspace)
                if not ws.is_absolute():
                    print("ERROR: --workspace must be an absolute path (or omit the value for <project>.cecilia)",
                          file=sys.stderr)
                    return 2
                plan = build_workspace(project.resolve(), ws.resolve(), hosts, args.upgrade, push_lock=args.push_lock)
            else:
                plan = build_project(project.resolve(), hosts, args.upgrade, push_lock=not args.no_push_lock)
    except ValueError as e:
        print("ERROR:", e, file=sys.stderr)
        return 2

    print(plan.label)
    if "claude" in hosts:
        print(f"Claude Code hook form: {HOOK_FORM['form']} ({HOOK_FORM['why']})")
    print("Hosts:      " + ", ".join(sorted(hosts)) + "\n")
    print(f"Create:     {len(plan.create)} file(s)")
    for dest, _ in plan.create[:500]:
        print("   +", plan.display(dest))
    if plan.replace or plan.retire:
        print(f"Replace:    {len(plan.replace)} file(s) (old copy backed up first)")
        for dest, _ in plan.replace[:500]:
            print("   ~", plan.display(dest))
        print(f"Retire:     {len(plan.retire)} file(s) no longer shipped (moved to the backup)")
        for dest in plan.retire[:500]:
            print("   -", plan.display(dest))
        print(f"Backup to:  {plan.display(plan.backup)}")
    print(f"Unchanged:  {len(plan.same)} file(s) already identical")
    if plan.config_migration:
        print(f"Config:     .cecilia/config.json v18 -> v19 -> v{VERSION} (missing keys added, backed up first; nothing you set is changed)")
        for key, before, after in plan.config_migration[2]:
            print(f"   {key:28} {before:10} -> {after}")
    if plan.exclude:
        print(f"Exclude:    {len(plan.exclude)} line(s) -> .git/info/exclude")
    if plan.set_python:
        print(f"Config:     guard.python = {plan.set_python}")
    if plan.conflicts:
        print(f"Conflicts:  {len(plan.conflicts)} (left as they are)")
        for dest, why in plan.conflicts:
            print("   !", plan.display(dest), "-", why)
    if plan.notes:
        print("\nYou need to:")
        for note in plan.notes:
            print("  *", note)
    if not args.apply:
        print("\nDry run - nothing written. Re-run with --apply.")
        return 0
    apply(plan)
    print(f"\nWrote {len(plan.create) + len(plan.replace)} file(s)"
          + (f", retired {len(plan.retire)}; old copies in {plan.display(plan.backup)}." if plan.replace or plan.retire
             else "."))
    if plan.register:
        try:
            register_workspace(*plan.register)
        except OSError as e:                  # best effort: the install itself succeeded
            print(f"WARNING: {workspaces_file()} not updated ({e})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
