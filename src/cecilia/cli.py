"""`cecilia` — one command for everything, so you never deal with Python yourself (uv brings it).

    cecilia init D:\\projects\\shop            create the workspace D:\\projects\\shop.cecilia (asks before writing)
    cecilia init D:\\projects\\shop --yes      same, no questions
    cecilia open [shop]                        how to open the workspace; --claude starts Claude Code in it,
                                               --agy [--skip-permissions] starts the Antigravity CLI in it
    cecilia doctor [shop]                      health check (hooks really run, project untouched, secrets in MCP files)
    cecilia upgrade [shop]                     refresh skills/agents/guard in a workspace after `uv tool upgrade cecilia`
    cecilia upgrade --all                      the same for every workspace in ~/.cecilia/workspaces.json
    cecilia workspaces                         list the registered workspaces (init/upgrade register them)
      init/upgrade --python PY                 interpreter the guard hooks run (default `python` on Windows,
                                               `python3` elsewhere, from PATH); stored as guard.python
    cecilia mode [fast|standard|controlled]    show or switch the work mode (asks you to type it)
    cecilia flow [personal|team]               show or switch the flow — the process (asks you to type it)
    cecilia rules list | show [role] | lint    the workspace rules/ folder (project, per role, per flow, per lens)
    cecilia rules add --role R "text"          add a rule (or --project / --flow F / --lens L); rules only tighten
    cecilia extension list | check DIR         new roles/flows/lenses proposed by cecilia-extend (tensura/extensions/)
    cecilia extension apply DIR                copy a checked proposal into .cecilia/extensions and upgrade (asks)
    cecilia scaffold …                         templates for a new role/flow/lens (tools/scaffold.py)
    cecilia approve <plan.md> --task T-B01     approve a CONTROLLED scope (G2)
    cecilia push [git push args]               push the project yourself (unlocks and relocks the push lock)
    cecilia push-lock on|off|status            git-level push lock in the project's .git/config (optional)
    cecilia status [shop]                      open tasks (flow, chosen workflow, fix round, agents), what waits for
                                               you, branch, worktrees, recent guard refusals
    cecilia lessons [--all D:\\projects]        lessons marked [generic?] that you may promote into the skills
    cecilia scorecard [shop]                   per role: reports, deviations, self-checks, guard refusals
    cecilia clean [--apply] [--days 30]        finished worktrees and old backups (lists; --apply asks first)
    cecilia where                              where this Cecilia's files are
    cecilia mcp [--http PORT] [--print-config] MCP server so another LLM can start/watch/answer runs (docs/MCP.md)
    cecilia validate | tokens | corpus | evals developer checks of the Cecilia package itself

A workspace is found from the argument (a project, its workspace, or a name next to the current folder), else
from the current folder (`flow`, `rules`, `extension`: the current folder). Nothing here ever pushes or publishes
on its own; `cecilia push` is you pushing. `mode`, `flow`, `rules add`, `extension apply`, `approve` and `push`
are yours alone: they need your terminal, and the guard refuses them to agents. Their `--yes --by NAME` form is
only for the `cecilia mcp` control tools (honoured only with env CECILIA_MCP=1; see docs/MCP.md).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__


def data_root() -> Path:
    """Installed: cecilia/_data (the repository layout). From a clone: the repository itself."""
    here = Path(__file__).resolve().parent
    packaged = here / "_data"
    if (packaged / "skills").is_dir():
        return packaged
    repo = here.parent.parent
    if (repo / "skills").is_dir():
        return repo
    raise SystemExit("cecilia: package data not found — reinstall with `uv tool install --force git+<repo>`")


DATA = data_root()


def run_py(script: Path, *args: str, cwd: Path | None = None) -> int:
    return subprocess.call([sys.executable, str(script), *args], cwd=str(cwd) if cwd else None)


def _cfg_project(home: Path):
    try:
        cfg = json.loads((home / ".cecilia" / "config.json").read_text(encoding="utf-8-sig"))
        proj = (cfg.get("workspace") or {}).get("project")
        return Path(proj) if proj else None
    except (OSError, ValueError, AttributeError):
        return None


def find_workspace(arg: str | None) -> tuple[Path, Path]:
    """(workspace, project) from an argument or the current folder."""
    cands: list[Path] = []
    if arg:
        p = Path(arg).expanduser()
        if not p.is_absolute():
            p = (Path.cwd() / p)
        p = p.resolve()
        cands += [p, p.parent / f"{p.name}.cecilia"]
    else:
        cwd = Path.cwd().resolve()
        cands += [cwd, *cwd.parents]
        cands += [d.parent / f"{d.name}.cecilia" for d in [cwd, *cwd.parents]]
    for c in cands:
        proj = _cfg_project(c) if (c / ".cecilia").is_dir() else None
        if proj:
            return c, proj
    for c in cands:                                   # older in-project layout: .cecilia/ inside the repository
        if (c / ".cecilia" / "bin").is_dir():
            return c, c
    raise SystemExit("cecilia: no workspace found" + (f" for {arg}" if arg else " here") +
                     " — create one with `cecilia init <project folder>`")


def warn_ephemeral_python():
    exe = str(Path(sys.executable)).replace("\\", "/").lower()
    if "/uv/cache/" in exe or "archive-v0" in exe:
        print("WARNING: running from a temporary uv environment (uvx) — `cecilia upgrade`/`doctor` will not be there "
              "later. Install once with `uv tool install git+<repo>`. (The guard hooks run `python` from PATH, "
              "not this interpreter.)")


def split_python(args: list[str]) -> tuple[list[str], str | None]:
    """Remove `--python PY` / `--python=PY` from args; returns (rest, PY or None)."""
    rest, py = [], None
    it = iter(args)
    for a in it:
        if a == "--python":
            py = next(it, None)
        elif a.startswith("--python="):
            py = a.split("=", 1)[1]
        else:
            rest.append(a)
    return rest, (py or "").strip() or None


def cmd_init(args: list[str]) -> int:
    if not args or args[0].startswith("-"):
        print("usage: cecilia init <project folder> [--workspace PATH] [--host claude|antigravity] [--yes] "
              "[--dry-run] [--push-lock] [--python PY]")
        return 2
    project = Path(args[0]).expanduser()
    project = (Path.cwd() / project).resolve() if not project.is_absolute() else project.resolve()
    rest = args[1:]
    dry = "--dry-run" in rest
    rest = [a for a in rest if a != "--dry-run"]
    warn_ephemeral_python()
    return run_py(DATA / "tools" / "setup.py", "--project", str(project), *([] if dry else ["--apply"]), *rest)


def _upgrade_one(ws: Path, proj: Path, extra: list[str], python: str | None, doctor: bool = True) -> int:
    hosts = []
    if (ws / ".claude").is_dir():
        hosts += ["--host", "claude"]
    if (ws / ".agents").is_dir():
        hosts += ["--host", "antigravity"]
    hosts = hosts or ["--host", "claude", "--host", "antigravity"]
    where = [] if ws == proj else ["--workspace", str(ws)]
    code = run_py(DATA / "tools" / "install.py", "--project", str(proj), *where, *hosts,
                  "--upgrade", *(["--python", python] if python else []),
                  *(["--apply"] if "--dry-run" not in extra else []))
    if doctor and code == 0 and "--dry-run" not in extra:
        run_py(ws / ".cecilia" / "bin" / "cecilia_doctor.py", "--project", str(ws))
    return code


def workspaces_file() -> Path:
    """~/.cecilia/workspaces.json — {"workspaces": [{"workspace","project","name","updated"}]} (install.py writes it;
    the MCP server reads it). CECILIA_WORKSPACES overrides the path."""
    env = os.environ.get("CECILIA_WORKSPACES")
    return Path(env) if env else Path.home() / ".cecilia" / "workspaces.json"


def registered_workspaces() -> list[dict]:
    try:
        data = json.loads(workspaces_file().read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    items = data.get("workspaces") if isinstance(data, dict) else None
    return [w for w in items or [] if isinstance(w, dict) and w.get("workspace")]


def cmd_workspaces(args: list[str]) -> int:
    items = registered_workspaces()
    if "--json" in args:
        print(json.dumps({"file": str(workspaces_file()), "workspaces": items}, indent=2, ensure_ascii=False))
        return 0
    if not items:
        print(f"No workspaces registered in {workspaces_file()} — `cecilia init <project>` or `cecilia upgrade` "
              "in a workspace registers it.")
        return 0
    print(f"{len(items)} workspace(s) in {workspaces_file()}:")
    for w in items:
        here = (Path(w["workspace"]) / ".cecilia").is_dir()
        print(f"  {str(w.get('name') or ''):20} {w['workspace']}{'' if here else '   (missing)'}\n"
              f"  {'':20} project {w.get('project', '?')} · updated {w.get('updated', '?')}")
    return 0


def cmd_upgrade_all(extra: list[str], python: str | None) -> int:
    items = registered_workspaces()
    if not items:
        print(f"No workspaces registered in {workspaces_file()}.")
        return 0
    results = []
    for w in items:
        ws, proj = Path(w["workspace"]), Path(w.get("project") or w["workspace"])
        if not (ws / ".cecilia").is_dir() or not proj.is_dir():
            results.append((ws, "skipped — " + ("workspace" if not (ws / ".cecilia").is_dir() else "project")
                            + " folder no longer exists"))
            continue
        print(f"\n=== {w.get('name') or ws.name}: {ws}")
        code = _upgrade_one(ws, proj, extra, python, doctor=False)
        results.append((ws, "upgraded" if code == 0 else f"FAILED (exit {code})"))
    print("\nUpgrade --all:")
    for ws, res in results:
        print(f"  {res:40} {ws}")
    print("Check each with `cecilia doctor <workspace>`.")
    return 1 if any(r.startswith("FAILED") for _, r in results) else 0


def cmd_upgrade(args: list[str]) -> int:
    args, python = split_python(args)
    warn_ephemeral_python()
    extra = [a for a in args if a.startswith("-")]
    if "--all" in args:
        return cmd_upgrade_all(extra, python)
    pos = [a for a in args if not a.startswith("-")]
    ws, proj = find_workspace(pos[0] if pos else None)
    return _upgrade_one(ws, proj, extra, python)


AGY_WARNING = ("Note: agy loads Cecilia's hooks, agents and main agent only from the workspace's .agents/ — agy started "
               "from any other folder (e.g. your home) runs WITHOUT Cecilia.")


def find_agy() -> str | None:
    """The Antigravity CLI on PATH (`agy`, or its Windows shims agy.cmd / agy.exe)."""
    for name in ("agy", "agy.cmd", "agy.exe"):
        exe = shutil.which(name)
        if exe:
            return exe
    return None


def agy_argv(agy: str, args: list[str]) -> list[str]:
    """argv for `cecilia open … --agy [--skip-permissions] [-- extra agy args]`."""
    extra = args[args.index("--") + 1:] if "--" in args else []
    head = args[:args.index("--")] if "--" in args else args
    argv = [agy]
    if "--skip-permissions" in head or "--dangerously-skip-permissions" in head:
        argv.append("--dangerously-skip-permissions")
    return argv + extra


def cmd_open(args: list[str]) -> int:
    ws, proj = find_workspace(args[0] if args and not args[0].startswith("-") else None)
    cw = ws / f"{proj.name}.code-workspace"
    print(f"Workspace: {ws}\nProject:   {proj}\n")
    print(f"Claude Code:  cd \"{ws}\"  then  claude")
    print(f"Antigravity:  open {cw}")
    print(f"Antigravity CLI:  cecilia open {proj.name} --agy [--skip-permissions]   (agy in the workspace)")
    if "--agy" in args:
        print(AGY_WARNING)
        exe = find_agy()
        if not exe:
            print("agy not found on PATH — install the Antigravity CLI, or `cd` to the workspace and start it there")
            return 1
        return subprocess.call(agy_argv(exe, args), cwd=str(ws))
    if "--claude" in args:
        exe = shutil.which("claude")
        if not exe:
            print("claude not found on PATH")
            return 1
        return subprocess.call([exe], cwd=str(ws))
    return 0


def in_ws(tool: str, args: list[str], cwd_ws: bool = True) -> int:
    ws, _ = find_workspace(None)
    return run_py(ws / ".cecilia" / "bin" / tool, *args, cwd=ws if cwd_ws else None)


YES_ONLY = "--yes is only for the Cecilia MCP server"
YES_COMMANDS = {"mode", "approve", "push", "flow", "rules", "extension"}


def split_yes(args: list[str]) -> tuple[list[str], bool, str | None]:
    """Remove `--yes` and `--by NAME` / `--by=NAME` -> (rest, yes, by)."""
    rest, yes, by = [], False, None
    it = iter(args)
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


def yes_refusal(args: list[str]) -> str:
    """20.2: `--yes --by NAME` on the human-only commands is the `cecilia mcp` control path — honoured only when
    env CECILIA_MCP=1 (the MCP server sets it for the command it runs). '' when fine, else the refusal."""
    _, yes, by = split_yes(args)
    if by is not None and not yes:
        return "--by needs --yes"
    if yes and os.environ.get("CECILIA_MCP") != "1":
        return YES_ONLY
    return ""


def _workspace_tools():
    import importlib.util
    spec = importlib.util.spec_from_file_location("cecilia_workspace_tools", DATA / "tools" / "workspace_tools.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def cmd_workspace_tool_yes(cmd: str, args: list[str], by: str, ws: Path, proj: Path) -> int:
    """Non-interactive flow / rules add / extension apply for `cecilia mcp` (CECILIA_MCP=1 checked by the caller).
    Same checks as the interactive path (known flow, rule lint + tighten-only, extension check), minus typing."""
    wt = _workspace_tools()
    usage = {"flow": "usage: cecilia flow NAME --yes --by WHO",
             "rules": 'usage: cecilia rules add (--project | --role R | --flow F | --lens L) "text" --yes --by WHO',
             "extension": "usage: cecilia extension apply DIR --yes --by WHO"}[cmd]
    if cmd == "flow":
        pos = [a for a in args if not a.startswith("-")]
        if len(pos) != 1:
            print(usage)
            return 2
        names = wt.flow_names(ws)
        if pos[0] not in names:
            print(f"unknown flow '{pos[0]}' — one of: {', '.join(names)}")
            return 2
        print(f"Confirmed non-interactively by {by} (--yes, Cecilia MCP server).")
        return wt.set_flow(ws, pos[0])
    if cmd == "rules":
        if not args or args[0] != "add":
            print("--yes applies to `rules add` only\n" + usage)
            return 2
        targets, words = [], []
        it = iter(args[1:])
        for a in it:
            if a == "--project":
                targets.append(("project", ""))
            elif a in {"--role", "--flow", "--lens"}:
                targets.append((a[2:], next(it, "")))
            elif a.startswith(("--role=", "--flow=", "--lens=")):
                k, v = a[2:].split("=", 1)
                targets.append((k, v))
            else:
                words.append(a)
        text = " ".join(words)
        if len(targets) != 1 or not text.strip():
            print(usage)
            return 2
        print(f"Confirmed non-interactively by {by} (--yes, Cecilia MCP server).")
        ok, msg = wt.add_rule(ws, targets[0][0], targets[0][1], text)
        print(msg)
        return 0 if ok else 1
    if len(args) != 2 or args[0] != "apply":
        print("--yes applies to `extension apply` only\n" + usage)
        return 2
    prop = wt.proposal_dir(ws, args[1])
    errs = wt.check_extension(ws, prop)
    for e in errs:
        print(e)
    print(("FAIL" if errs else "PASS") + f" — proposal {prop.name}: {len(wt.proposal_files(prop))} file(s), "
          f"{len(errs)} error(s)")
    if errs:
        return 1
    print(f"Confirmed non-interactively by {by} (--yes, Cecilia MCP server).")
    for dest in wt.copy_extension(ws, prop):
        print(f"  + {dest.relative_to(ws).as_posix()}")
    hosts = [x for h, d in (("claude", ".claude"), ("antigravity", ".agents")) if (ws / d).is_dir()
             for x in ("--host", h)] or ["--host", "claude", "--host", "antigravity"]
    where = [] if ws == proj else ["--workspace", str(ws)]
    return run_py(DATA / "tools" / "install.py", "--project", str(proj), *where, *hosts, "--upgrade", "--apply")


def cmd_workspace_tool(cmd: str, args: list[str]) -> int:
    """flow / rules / extension -> tools/workspace_tools.py. `rules add --project` / `--role` / `--flow` / `--lens`
    are renamed so they do not clash with the tool's own --project/--workspace."""
    refused = yes_refusal(args)
    if refused:
        print(f"cecilia: {refused}", file=sys.stderr)
        return 2
    ws, proj = find_workspace(None)
    rest, yes, by = split_yes(args)
    if yes:
        return cmd_workspace_tool_yes(cmd, rest, (by or "mcp").strip() or "mcp", ws, proj)
    opts: list[str] = []
    pos: list[str] = []
    it = iter(args)
    for a in it:
        if cmd == "rules" and a == "--project":
            opts.append("--rule-project")
        elif cmd == "rules" and a in {"--role", "--flow", "--lens"}:
            opts += [f"--rule-{a[2:]}", next(it, "")]
        elif cmd == "rules" and a.startswith(("--role=", "--flow=", "--lens=")):
            k, v = a[2:].split("=", 1)
            opts += [f"--rule-{k}", v]
        else:
            pos.append(a)
    return run_py(DATA / "tools" / "workspace_tools.py", cmd, "--workspace", str(ws), "--project", str(proj),
                  *opts, *(["--", *pos] if pos else []))


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print(__doc__)
        return 0
    cmd, args = argv[0], argv[1:]
    if cmd in {"-V", "--version", "version"}:
        print(f"cecilia {__version__} (Python {sys.version.split()[0]}, {sys.executable})")
        return 0
    if cmd == "init":
        return cmd_init(args)
    if cmd == "upgrade":
        return cmd_upgrade(args)
    if cmd == "workspaces":
        return cmd_workspaces(args)
    if cmd == "open":
        return cmd_open(args)
    if cmd == "doctor":
        ws, _ = find_workspace(args[0] if args and not args[0].startswith("-") else None)
        return run_py(ws / ".cecilia" / "bin" / "cecilia_doctor.py", "--project", str(ws),
                      *[a for a in args if a.startswith("-")])
    if cmd in YES_COMMANDS and yes_refusal(args):     # --yes --by: the `cecilia mcp` control path only
        print(f"cecilia: {yes_refusal(args)}", file=sys.stderr)
        return 2
    if cmd == "mode":
        return in_ws("cecilia_mode.py", args or ["--show"])
    if cmd == "approve":
        return in_ws("cecilia_approve.py", args)
    if cmd == "push":
        return in_ws("cecilia_mode.py", ["push", *args])
    if cmd == "push-lock":
        return in_ws("cecilia_mode.py", ["--push-lock", *(args or ["status"])])
    if cmd in {"status", "lessons", "scorecard", "clean"}:
        pos = [x for x in args if not x.startswith("-")]
        if cmd == "lessons" and "--all" in args:
            i = args.index("--all")
            scan = args[i + 1] if i + 1 < len(args) else str(Path.cwd())
            ws, proj = (Path.cwd(), Path.cwd())
            return run_py(DATA / "tools" / "workspace_tools.py", "lessons", "--workspace", str(ws), "--project",
                          str(proj), "--all", scan)
        ws, proj = find_workspace(pos[0] if pos and cmd != "clean" else (pos[0] if pos else None))
        flags = [x for x in args if x.startswith("-")]
        if "--days" in args:
            i = args.index("--days")
            flags = [f for f in flags if f != "--days"] + ["--days", args[i + 1]]
        return run_py(DATA / "tools" / "workspace_tools.py", cmd, "--workspace", str(ws), "--project", str(proj), *flags)
    if cmd in {"flow", "rules", "extension"}:
        return cmd_workspace_tool(cmd, args)
    if cmd == "scaffold":
        script = DATA / "tools" / "scaffold.py"
        if not script.is_file():
            print("cecilia: tools/scaffold.py is not in this package")
            return 2
        return run_py(script, *args)
    if cmd == "mcp":                                  # MCP server (B6): stdio, or --http on 127.0.0.1 only
        from .mcp_server import main as mcp_main
        return mcp_main(args)
    if cmd == "where":
        print(f"cecilia {__version__}\npackage data: {DATA}\npython: {sys.executable}")
        return 0
    dev = {"validate": "tools/validate.py", "tokens": "tools/tokens.py", "corpus": "tools/guard_corpus.py",
           "evals": "tools/evals/run_evals.py", "package": "tools/package.py"}
    if cmd in dev:
        return run_py(DATA / dev[cmd], *args, cwd=DATA)
    print(f"cecilia: unknown command '{cmd}' — `cecilia help`")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
