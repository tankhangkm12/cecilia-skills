#!/usr/bin/env python3
"""Set Cecilia's persistent project work mode and the push lock. This tool is for the human, not the agent.

Usage:
  python3 .cecilia/bin/cecilia_mode.py fast | standard | controlled
  python3 .cecilia/bin/cecilia_mode.py --show            # mode, flow, roles, lanes, rules, panel, push lock
  python3 .cecilia/bin/cecilia_mode.py --push-lock on    # every `git push` in this repository fails
  python3 .cecilia/bin/cecilia_mode.py --push-lock off   # pushes work again (asks you to confirm)
  python3 .cecilia/bin/cecilia_mode.py --push-lock status
  python3 .cecilia/bin/cecilia_mode.py push [git push arguments]   # unlock, push, lock again

The push lock is local git config (`url.cecilia-push-locked://.pushInsteadOf` for every URL form, plus any
explicit `remote.<name>.pushurl` swapped out and saved in .cecilia/pushlock.json): git rewrites the push
URL to a scheme nothing can reach, so a push fails whatever command, alias or tool issued it. Fetch is
not affected. Turning the lock off or pushing requires your interactive terminal; the host guard denies
agent attempts to run this script or to touch url.*/remote.* git config.

`--yes --by NAME` (mode switch and push only) skips the typed confirmation; it is honoured only when env
CECILIA_MCP=1, i.e. when `cecilia mcp` runs it for its control tools. Anywhere else it is refused (exit 2).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

VALID = {"fast", "standard", "controlled"}


def find_root(start: Path) -> Path:
    for d in [start, *start.parents]:
        if (d / ".cecilia").is_dir():
            return d
    raise SystemExit("ERROR: run this inside a project containing .cecilia/")


def git_root(root: Path) -> Path:
    """Workspace mode: the project the workspace serves (config `workspace.project`); else the folder itself."""
    try:
        cfg = json.loads((root / ".cecilia" / "config.json").read_text(encoding="utf-8-sig"))
        proj = (cfg.get("workspace") or {}).get("project")
    except (OSError, ValueError, AttributeError):
        proj = None
    if isinstance(proj, str) and proj.strip():
        pp = Path(proj)
        return pp if pp.is_absolute() else (root / pp).resolve()
    return root


def read_mode(root: Path) -> str:
    f = root / ".cecilia" / "mode.json"
    if not f.is_file():
        return "standard"
    try:
        value = json.loads(f.read_text(encoding="utf-8-sig")).get("mode", "standard")
    except Exception:
        return "controlled"
    return value if value in VALID else "controlled"


UI_BROWSERS = ("playwright-cli", "playwright-mcp", "none")                      # same as tools/roster.py
UI_STYLES = ("none", "taste", "minimalist", "soft", "brutalist", "redesign")
KNOWN_KEYS = {"roles", "plan_first", "docs_layout", "docs_root", "ui", "git", "parallel", "models", "profiles",
              "tool_rules", "guard", "workspace", "review", "scale",
              # v20
              "flow", "flows", "orchestration", "lanes", "test", "fix_loop", "rules", "extensions"}


def show_config(root: Path) -> None:
    """Print the effective .cecilia/config.json and flag likely typos. Edit the file by hand."""
    f = root / ".cecilia" / "config.json"
    if not f.is_file():
        print("config: .cecilia/config.json missing — defaults apply (every role on except cecilia-ui)")
        return
    try:
        cfg = json.loads(f.read_text(encoding="utf-8-sig"))
    except Exception as e:
        print(f"config: INVALID JSON ({e}) — the guard treats cecilia-ui as off; fix the file")
        return
    roles = cfg.get("roles", {}) if isinstance(cfg.get("roles"), dict) else {}
    on = sorted(k for k, v in roles.items() if v is True)
    off = sorted(k for k, v in roles.items() if v is not True)
    print("roles on:  " + (", ".join(on) or "none"))
    print("roles off: " + (", ".join(off) or "none"))
    git = cfg.get("git") if isinstance(cfg.get("git"), dict) else {}
    par = cfg.get("parallel") if isinstance(cfg.get("parallel"), dict) else {}
    print(f"plan_first: {cfg.get('plan_first', {'fast': False, 'standard': True, 'controlled': True})}")
    ui = cfg.get("ui") if isinstance(cfg.get("ui"), dict) else {}
    print(f"docs_layout: {cfg.get('docs_layout', 'monolith')} · ui.design_writes: {ui.get('design_writes', 'ask')} · "
          f"ui.browser: {ui.get('browser', 'playwright-cli')} · ui.style: {ui.get('style', 'none')}")
    print(f"git: model={git.get('model', 'auto')} · require_task_branch={git.get('require_task_branch', True)} · "
          f"protected={git.get('protected', ['main', 'master', 'develop', 'trunk', 'production', 'prod', 'release/*'])}")
    limits = par.get("limits") if isinstance(par.get("limits"), dict) else {}
    lim = ", ".join(f"{k}={'none' if v is None else v}" for k, v in limits.items()) or "none"
    print(f"parallel: limits {lim}" + (f" · max_writers={par['max_writers']} (v19 key, read as the dev cap)"
                                         if "max_writers" in par else "")
          + f" · wave_checkin={par.get('wave_checkin', 'auto')}")
    show_v20(root, cfg)
    if cfg.get("models"):
        print(f"models: {cfg['models']}")
    print(f"local_only: {git.get('local_only', True)} · push lock: {'ON' if push_lock_status(root) else 'off'}"
          f" · docs_root: {cfg.get('docs_root') or 'tensura/docs'}")
    profiles = cfg.get("profiles")
    if isinstance(profiles, list):
        print("profiles (path group -> level; the stricter of this and the mode wins):")
        for p in profiles:
            if isinstance(p, dict):
                paths = p.get("paths", [])
                print(f"  {p.get('name', '?'):8} {p.get('level', '?'):10} {', '.join(paths[:6])}{' …' if len(paths) > 6 else ''}")
                if p.get("level") not in {"fast", "standard", "ask", "controlled", "deny"}:
                    print(f"WARNING: profile '{p.get('name')}' has an unknown level — the guard ignores it")
    for r in cfg.get("tool_rules") or []:
        if isinstance(r, dict):
            print(f"tool rule {r.get('id', '?')}: {', '.join(r.get('tools', []))} · enforce={r.get('enforce', 'report')}"
                  f" · roles={r.get('roles') or 'all'}")
    known = {p.name for d in (root / ".claude" / "skills", root / ".agents" / "skills") if d.is_dir()
             for p in d.iterdir() if p.name.startswith("cecilia-")}
    for k in roles:
        if known and k not in known:
            print(f"WARNING: role '{k}' is not an installed skill — typo? (installed: {', '.join(sorted(known))})")
    for k in cfg:
        if k not in KNOWN_KEYS:
            print(f"WARNING: unknown key '{k}' — ignored")
    if ui.get("browser", "playwright-cli") not in UI_BROWSERS:
        print(f"WARNING: ui.browser must be one of {', '.join(UI_BROWSERS)}")
    if ui.get("style", "none") not in UI_STYLES:
        print(f"WARNING: ui.style must be one of {', '.join(UI_STYLES)}")
    if ui.get("design_writes", "ask") not in {"ask", "allow"}:
        print("WARNING: ui.design_writes must be \"ask\" or \"allow\"")
    if cfg.get("docs_layout", "monolith") not in {"monolith", "microservices"}:
        print("WARNING: docs_layout must be \"monolith\" or \"microservices\"")



def _d(cfg: dict, key: str) -> dict:
    return cfg.get(key) if isinstance(cfg.get(key), dict) else {}


def show_v20(root: Path, cfg: dict) -> None:
    """v20 keys: flow, orchestration, lanes, test lenses, review panel, fix loop, rules, extensions."""
    try:
        reg = json.loads((root / ".cecilia" / "registry.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        reg = {}
    flows = sorted((reg.get("flows") or {}) if isinstance(reg, dict) else {}) or ["personal", "team"]
    flow = cfg.get("flow", "personal")
    settings = _d(_d(cfg, "flows"), flow) if isinstance(flow, str) else {}
    print(f"flow: {flow}" + (f" · {', '.join(f'{k}={v}' for k, v in settings.items())}" if settings else "")
          + f"   (flows: {', '.join(flows)}; switch with `cecilia flow`)")
    if flow not in flows:
        print(f"WARNING: flow '{flow}' is not a known flow ({', '.join(flows)}) — the orchestrator falls back to personal")
    orch = _d(cfg, "orchestration")
    if orch:
        print(f"orchestration: writes={orch.get('orchestrator_writes', 'tensura-only')} · workflow from "
              f"{orch.get('workflow_required_from', 'standard')} · {orch.get('options', 3)} options")
    lanes = _d(cfg, "lanes")
    if lanes:
        print("lanes (role -> where it may write; plus tensura/reports|tasks|backups/<TASK>):")
        for role, globs in sorted(lanes.items()):
            g = globs if isinstance(globs, list) else []
            print(f"  {role.replace('cecilia-', ''):13} {', '.join(map(str, g[:6])) or '(read-only)'}{' …' if len(g) > 6 else ''}")
    test = _d(cfg, "test")
    if test:
        print(f"test lenses: {', '.join(map(str, test.get('lenses') or [])) or 'none'}")
    panel = _d(_d(cfg, "review"), "panel")
    if panel:
        print(f"review panel: from {panel.get('from', panel.get('auto_in', 'standard'))} · reviewers "
              f"{panel.get('reviewers')} · redteam in {panel.get('redteam_in', ['controlled'])} · rounds "
              f"{panel.get('rounds', 2)} · judge {panel.get('judge_model', 'strongest')}")
    fix = _d(cfg, "fix_loop")
    if fix:
        print(f"fix loop: max {fix.get('max_rounds', 3)} round(s) · {', '.join(fix.get('severities') or [])} · "
              f"then {fix.get('on_exhausted', 'options')}")
    rules = _d(cfg, "rules")
    if rules:
        d = root / str(rules.get("dir", "rules"))
        n = len(list(d.rglob("*.md"))) if d.is_dir() else 0
        print(f"rules: {rules.get('dir', 'rules')}/ ({n} file(s)) · enforce={rules.get('enforce', 'gate')} · "
              f"max {rules.get('max_bytes_per_file', 2048)} B/file")
    ext = _d(cfg, "extensions")
    if ext:
        applied = sorted(reg.get("extensions") or []) if isinstance(reg, dict) else []
        print(f"extensions: {ext.get('dir', '.cecilia/extensions')} · applied: {', '.join(applied) or 'none'}")


# --------------------------------------------------------------------------- push lock

LOCK_BASE = "cecilia-push-locked-run-cecilia-mode-push://"
LOCK_KEY = f"url.{LOCK_BASE}.pushinsteadof"
LOCK_PREFIXES = ["https://", "http://", "ssh://", "git://", "git@", "file://", "/", "./", "../", "~"]


def _git(root: Path, *args, check=False):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=check,
                          env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"))


def push_lock_status(root: Path) -> bool:
    out = _git(git_root(root), "config", "--local", "--get-all", LOCK_KEY)
    return out.returncode == 0 and bool(out.stdout.strip())


def set_push_lock(root: Path, on: bool) -> str:
    """Switch the lock. Returns a one-line description. Raises RuntimeError outside a git repository.
    State goes to `.cecilia/pushlock.json` (the workspace in workspace mode); the lock itself is git config of
    the project repository (`.git/config` — the only place git reads it)."""
    home, root = root, git_root(root)
    if _git(root, "rev-parse", "--git-dir").returncode != 0:
        raise RuntimeError("not a git repository")
    state_file = home / ".cecilia" / "pushlock.json"
    state = {}
    if state_file.is_file():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except ValueError:
            state = {}
    remotes = [r for r in _git(root, "remote").stdout.split() if r]
    if on:
        _git(root, "config", "--local", "--unset-all", LOCK_KEY)
        for prefix in LOCK_PREFIXES:
            _git(root, "config", "--local", "--add", LOCK_KEY, prefix, check=True)
        saved = state.get("saved_pushurls", {})
        for r in remotes:        # an explicit pushurl ignores pushInsteadOf: swap it out
            cur = _git(root, "config", "--local", "--get-all", f"remote.{r}.pushurl").stdout.split()
            if cur and not all(u.startswith(LOCK_BASE) for u in cur):
                saved[r] = cur
                _git(root, "config", "--local", "--unset-all", f"remote.{r}.pushurl")
                _git(root, "config", "--local", f"remote.{r}.pushurl", LOCK_BASE + r, check=True)
        state = {"locked": True, "saved_pushurls": saved,
                 "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
        msg = f"push lock ON ({len(remotes)} remote(s))"
    else:
        _git(root, "config", "--local", "--unset-all", LOCK_KEY)
        for r, urls in state.get("saved_pushurls", {}).items():
            _git(root, "config", "--local", "--unset-all", f"remote.{r}.pushurl")
            for u in urls:
                _git(root, "config", "--local", "--add", f"remote.{r}.pushurl", u)
        for r in remotes:
            cur = _git(root, "config", "--local", "--get-all", f"remote.{r}.pushurl").stdout.split()
            if cur and all(u.startswith(LOCK_BASE) for u in cur):
                _git(root, "config", "--local", "--unset-all", f"remote.{r}.pushurl")
        state = {"locked": False, "saved_pushurls": {},
                 "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
        msg = "push lock OFF"
    (home / ".cecilia").mkdir(exist_ok=True)
    state_file.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return msg


YES_ONLY = "--yes is only for the Cecilia MCP server"


def split_yes(argv: list) -> tuple:
    """Remove `--yes` and `--by NAME` / `--by=NAME` -> (rest, yes, by). 20.2 non-interactive path: honoured only
    when env CECILIA_MCP=1 (set by `cecilia mcp` for its control tools); the guard still refuses agents."""
    rest, yes, by = [], False, None
    it = iter(argv)
    for a in it:
        if a == "--yes":
            yes = True
        elif a == "--by":
            by = next(it, "") or ""
        elif a.startswith("--by="):
            by = a.split("=", 1)[1]
        else:
            rest.append(a)
    return rest, yes, by


def yes_refused(yes: bool, by) -> str:
    """'' when the flags are fine, else the refusal message."""
    if by is not None and not yes:
        return "--by needs --yes"
    if yes and os.environ.get("CECILIA_MCP") != "1":
        return YES_ONLY
    return ""


def _confirm(word: str) -> bool:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("ERROR: this needs your interactive terminal.", file=sys.stderr)
        return False
    return input(f"Type {word} to confirm: ").strip() == word


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
    argv, yes, by = split_yes(sys.argv[1:])
    refused = yes_refused(yes, by)
    if refused:
        print(f"ERROR: {refused}", file=sys.stderr)
        return 2
    by = (by or "mcp").strip() or "mcp"
    if argv and argv[0] == "push":
        root = find_root(Path.cwd().resolve())
        if yes:
            print(f"push confirmed non-interactively by {by} (--yes, Cecilia MCP server)")
        elif not _confirm("PUSH"):
            return 1
        was = push_lock_status(root)
        try:
            if was:
                set_push_lock(root, False)
            return subprocess.call(["git", "-C", str(git_root(root)), "push", *argv[1:]])
        finally:
            if was:
                print(set_push_lock(root, True))
    ap.add_argument("mode", nargs="?", choices=sorted(VALID))
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--push-lock", choices=["on", "off", "status"])
    args = ap.parse_args(argv)
    root = find_root(Path.cwd().resolve())

    if args.push_lock:
        try:
            if args.push_lock == "status":
                print("push lock: " + ("ON" if push_lock_status(root) else "off"))
                return 0
            if args.push_lock == "off" and not _confirm("UNLOCK"):
                return 1
            print(set_push_lock(root, args.push_lock == "on"))
            return 0
        except RuntimeError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 2

    if args.show or args.mode is None:
        print(read_mode(root))
        if args.show:
            show_config(root)
        return 0

    if not yes and not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("ERROR: changing Cecilia mode requires your interactive terminal.", file=sys.stderr)
        return 2

    current = read_mode(root)
    print(f"Project: {root}")
    print(f"Current: {current}")
    print(f"New:     {args.mode}")
    if yes:
        print(f"Confirmed non-interactively by {by} (--yes, Cecilia MCP server).")
    else:
        confirm = input(f"Type {args.mode.upper()} to confirm: ").strip()
        if confirm != args.mode.upper():
            print("Cancelled.")
            return 1

    rec = {
        "mode": args.mode,
        "set_by": by if yes else (os.environ.get("USER") or os.environ.get("USERNAME") or "human"),
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
    path = root / ".cecilia" / "mode.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    print(f"Mode set to {args.mode}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
