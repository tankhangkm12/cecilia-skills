#!/usr/bin/env python3
"""Cecilia v20 setup wizard — detect the project, propose a config, install, check. Run it yourself (never an agent).

    python tools/setup.py --project D:\\projects\\shop                 # show what it would do (dry run)
    (the uv tool runs this as `cecilia init D:\\projects\\shop`; workspace D:\\projects\\shop.cecilia by default)
    python tools/setup.py --project D:\\projects\\shop --apply         # do it (asks before each step)
    python tools/setup.py --project … --apply --yes                   # no questions (accept the proposal)
    python tools/setup.py --project … --host claude                   # only one host (default: both)

Steps:
  1. Detect — languages, frontend, API contract, database/migrations, infra files, git state, MCP servers
     (context7, sequential thinking) — reading file names only; secrets in MCP files are never printed.
  2. Propose `.cecilia/config.json` — roles on/off with the reason, path profiles, tool rules for the MCP
     servers you have (context7 → docs-first gate on Claude Code; sequential thinking → report at decision points),
     and (v20) role `lanes` narrowed to the project's real top-level folders when that is obvious.
     An existing config is kept: only missing keys are added (same as the installer's migration).
  3. Install — the same plan as `tools/install.py --project … --apply` (skills, agents, hooks, guard,
     .git/info/exclude, push lock).
  4. Check — `cecilia_doctor.py` and a guard smoke test (`git push` must be denied, `git status` allowed).

Python ≥ 3.9, standard library only.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import install  # noqa: E402
from roster import ROLES, default_config, migrate_config  # noqa: E402

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "dist", "build", ".next", "target", ".cecilia", "tensura",
             ".worktrees", "__pycache__", ".claude", ".agents", "vendor", ".gradle", ".idea", ".vscode"}
MAX_FILES = 20000


def walk(project: Path):
    n = 0
    stack = [project]
    while stack:
        d = stack.pop()
        try:
            entries = list(d.iterdir())
        except OSError:
            continue
        for e in entries:
            if e.is_dir():
                if e.name not in SKIP_DIRS and not e.is_symlink():
                    stack.append(e)
            else:
                n += 1
                if n > MAX_FILES:
                    return
                yield e


def _read(p: Path, limit: int = 200_000) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")[:limit]
    except OSError:
        return ""


def detect(project: Path) -> dict:
    found = {"backend": [], "frontend": [], "api": [], "db": [], "infra": [], "tests": [], "notes": []}
    for f in walk(project):
        rel = f.relative_to(project).as_posix()
        name = f.name.lower()
        if name == "package.json":
            text = _read(f)
            if any(k in text for k in ('"react"', '"next"', '"vue"', '"@angular/core"', '"svelte"', '"vite"')):
                found["frontend"].append(rel)
            if any(k in text for k in ('"@nestjs/core"', '"express"', '"fastify"', '"koa"', '"hono"')):
                found["backend"].append(rel)
            if any(k in text for k in ('"prisma"', '"typeorm"', '"sequelize"', '"knex"', '"mongoose"', '"drizzle-orm"')):
                found["db"].append(rel + " (ORM)")
        elif name in {"pyproject.toml", "requirements.txt", "pom.xml", "build.gradle", "build.gradle.kts", "go.mod",
                      "cargo.toml", "gemfile", "composer.json"}:
            found["backend"].append(rel)
        elif name.endswith((".yaml", ".yml", ".json")) and ("openapi" in name or "swagger" in name):
            found["api"].append(rel)
        elif name.endswith((".yaml", ".yml")) and "/" in rel and _read(f, 2000).lstrip().startswith(("openapi:", "swagger:")):
            found["api"].append(rel)
        elif name == "schema.prisma" or "/migrations/" in f"/{rel}" or "/alembic/versions/" in f"/{rel}" \
                or "/db/migrate/" in f"/{rel}" or name.endswith(".sql"):
            found["db"].append(rel)
        if name.startswith("dockerfile") or name.startswith("docker-compose") or name.startswith("compose.") \
                or name.endswith(".tf") or rel.startswith((".github/workflows/", "k8s/", "helm/", "charts/", "deploy/",
                                                           "infra/", "terraform/", ".gitlab-ci")) or name == "jenkinsfile":
            found["infra"].append(rel)
        if any(s in f"/{rel}" for s in ("/test/", "/tests/", "/__tests__/", ".spec.", ".test.", "_test.")):
            found["tests"].append(rel)
    root_infra = detect_root_infra(project)
    found["infra"] += root_infra
    found["root_infra"] = sorted(set(root_infra))
    for k in ("backend", "frontend", "api", "db", "infra", "tests", "notes"):
        found[k] = sorted(set(found[k]))
    found["git"] = (project / ".git").exists()
    manifests = {"package.json", "pyproject.toml", "pom.xml", "build.gradle", "build.gradle.kts", "go.mod", "cargo.toml"}
    services = {str(Path(r).parent) for k in ("backend", "frontend") for r in found[k] if Path(r.split(" ")[0]).name.lower() in manifests}
    found["services"] = len(services)
    found["source_files"] = sum(1 for f in walk(project) if f.suffix.lower() in
                                {".py", ".ts", ".tsx", ".js", ".jsx", ".java", ".kt", ".go", ".rs", ".cs", ".rb", ".php", ".vue"})
    found["mcp"] = detect_mcp(project)
    return found


ROOT_INFRA_NAMES = {"kustomization.yaml", "kustomization.yml", "chart.yaml", "helmfile.yaml", "helmfile.yml"}
ROOT_INFRA_GLOBS = ["**/*.yaml", "**/*.yml", "**/*.tf", "**/*.tfvars", "**/Chart.yaml", "**/values*.yaml",
                    "**/kustomization.yaml"]


def _is_k8s_manifest(text: str) -> bool:
    """A YAML document with top-level `apiVersion:` and `kind:` (Kubernetes / Kustomize / Helm-rendered)."""
    lines = [ln for ln in text.splitlines() if ln and not ln.startswith((" ", "\t", "#"))]
    return any(ln.startswith("apiVersion:") for ln in lines) and any(ln.startswith("kind:") for ln in lines)


def detect_root_infra(project: Path) -> list[str]:
    """20.1: the project root itself is the infra folder (a k8s/Helm/Kustomize/Terraform repository) — top-level
    Kubernetes manifests, kustomization.yaml, Chart.yaml, helmfile.yaml or *.tf. Returns those root file names."""
    hits = []
    try:
        entries = sorted(project.iterdir())
    except OSError:
        return []
    for f in entries:
        if not f.is_file():
            continue
        name = f.name.lower()
        if name in ROOT_INFRA_NAMES or name.endswith((".tf", ".tfvars")):
            hits.append(f.name)
        elif name.endswith((".yaml", ".yml")) and _is_k8s_manifest(_read(f, 20000)):
            hits.append(f.name)
    return hits


def devops_base_lane() -> list[str]:
    """The registry lane of cecilia-devops (registry/roles/cecilia-devops.json)."""
    try:
        data = json.loads((ROOT / "registry" / "roles" / "cecilia-devops.json").read_text(encoding="utf-8"))
        lane = data.get("lane")
        if isinstance(lane, list):
            return [str(g) for g in lane]
    except (OSError, ValueError):
        pass
    return []


def apply_root_infra(cfg: dict, found: dict, why: list[str], existing: bool = False) -> None:
    """Infra at the project root: devops lane = registry lane + root-level globs; the infra profile also matches
    root-relative manifests (`deployment.yaml`, `main.tf`), so edits there ask like any infra edit."""
    if not found.get("root_infra"):
        return
    lanes = cfg.get("lanes") if isinstance(cfg.get("lanes"), dict) else {}
    cur = lanes.get("cecilia-devops") if isinstance(lanes.get("cecilia-devops"), list) else []
    base = list(cur) if existing and cur else (devops_base_lane() or list(cur))
    before = list(cur)
    lanes["cecilia-devops"] = base + [g for g in ROOT_INFRA_GLOBS if g not in base]
    cfg["lanes"] = lanes
    profiles = cfg.get("profiles") if isinstance(cfg.get("profiles"), list) else []
    infra = next((p for p in profiles if isinstance(p, dict) and p.get("name") == "infra"), None)
    if infra is None:
        infra = {"name": "infra", "level": "ask", "paths": []}
        profiles.insert(0, infra)
    paths = infra.get("paths") if isinstance(infra.get("paths"), list) else []
    infra["paths"] = paths + [g for g in ROOT_INFRA_GLOBS if g not in paths]
    cfg["profiles"] = profiles
    roles = cfg.get("roles") if isinstance(cfg.get("roles"), dict) else None
    if roles is not None and "cecilia-devops" in roles and not existing:
        roles["cecilia-devops"] = True
    if existing and lanes["cecilia-devops"] == before and set(ROOT_INFRA_GLOBS) <= set(paths):
        return
    why.append("infra root — the project root holds infra files (" + ", ".join(found["root_infra"][:4])
               + (" …" if len(found["root_infra"]) > 4 else "") + "): cecilia-devops lane and the infra profile "
               "cover root-level *.yaml/*.yml/*.tf (edits there ask)")


def detect_mcp(project: Path) -> dict:
    """Which MCP servers are configured — by server name only; values are never read out or printed."""
    home = Path.home()
    files = [project / ".mcp.json", home / ".claude.json", home / ".gemini/antigravity/mcp_config.json",
             home / ".gemini/config/mcp_config.json", home / ".gemini/settings.json"]
    names: set[str] = set()
    for f in files:
        if not f.is_file():
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        stack = [data]
        while stack:
            o = stack.pop()
            if isinstance(o, dict):
                for k, v in o.items():
                    if k in ("mcpServers", "servers") and isinstance(v, dict):
                        names.update(str(n).lower() for n in v)
                    stack.append(v)
            elif isinstance(o, list):
                stack.extend(o)
    return {"context7": any("context7" in n for n in names),
            "sequential": any("sequential" in n for n in names),
            "servers": sorted(names)}


def propose(project: Path, found: dict, home: Path | None = None, scale_arg: str = "") -> tuple[dict, list[str]]:
    """Return (config, reasons). An existing config is migrated, never overwritten. `home` is the workspace
    (workspace mode) or None (in-project)."""
    why: list[str] = []
    cfg_file = (home or project) / ".cecilia" / "config.json"
    if cfg_file.is_file():
        try:
            old = json.loads(cfg_file.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            old = None
        if isinstance(old, dict):
            new, changes = migrate_config(old)
            if home is not None:
                new.setdefault("workspace", {"project": str(project)})
            why.append(f"existing .cecilia/config.json kept; {len(changes)} missing key(s) added")
            apply_root_infra(new, found, why, existing=True)   # additive: root-level infra globs only
            return new, why
    cfg = default_config()
    if home is not None:
        cfg["workspace"] = {"project": str(project)}
    roles = cfg["roles"]
    be, fe, api, db, infra = (bool(found[k]) for k in ("backend", "frontend", "api", "db", "infra"))
    def role(name: str, on: bool, reason: str):
        if name in roles:
            roles[name] = on
            why.append(f"{name:22} {'on ' if on else 'off'} — {reason}")
    role("cecilia-dev-be", be or not fe, "backend files found" if be else ("no backend detected" if fe else "default"))
    role("cecilia-dev-fe", fe, "frontend framework found" if fe else "no frontend framework in package.json")
    role("cecilia-db", db or be, "migrations/schema/ORM found" if db else ("backend without DB files — kept on" if be else "no DB"))
    role("cecilia-devops", infra, "CI/Docker/IaC files found (strict: every infra edit asks)" if infra else "no infra files")
    role("cecilia-api-ux", api or be, "API contract found" if api else ("backend found — review APIs as consumers" if be else "no API"))
    role("cecilia-ui", False, "off by default — turn on when you design screens with it")
    rules = []
    if found["mcp"]["context7"]:
        rules.append({"id": "docs-first", "tools": ["context7"], "enforce": "gate",
                      "why": "look up the library's current docs before writing code that uses it"})
        why.append("tool rule docs-first — context7 found: edits adding imports are gated on Claude Code, reported on Antigravity")
    else:
        why.append("no context7 MCP found — no docs-first rule (add one later in tool_rules)")
    if found["mcp"]["sequential"]:
        rules.append({"id": "think-at-decisions", "tools": ["sequential"], "enforce": "report", "when": "decision",
                      "why": "structured thinking before presenting options"})
        why.append("tool rule think-at-decisions — sequential thinking found: reminded and reported, never gated")
    cfg["tool_rules"] = rules
    scale = scale_arg or ("large" if found["source_files"] > 1500 or found["services"] >= 3 else
                          "small" if found["source_files"] < 150 and found["services"] <= 1 else "standard")
    cfg["scale"] = scale
    lanes, narrowed = narrow_lanes(project, cfg.get("lanes"))
    if narrowed:
        cfg["lanes"] = lanes
        why.append(f"lanes      — {len(narrowed)} role lane(s) narrowed to folders that exist: " + ", ".join(narrowed[:6])
                   + (" …" if len(narrowed) > 6 else "") + " (edit `lanes` to change)")
    apply_root_infra(cfg, found, why)
    why.append(f"scale {scale:9} — {found['source_files']} source files, {found['services']} service manifest(s)"
               + (" (your choice)" if scale_arg else ""))
    panel = cfg.get("review", {}).get("panel", {})
    if scale == "small":
        for r in ("cecilia-discovery", "cecilia-design", "cecilia-plan", "cecilia-api-ux"):
            if r in roles and not (r == "cecilia-api-ux" and api):
                roles[r] = False
        why.append("small      — discovery/design/plan off (turn on when needed); review panel as configured")
    elif scale == "large":
        if isinstance(panel.get("reviewers"), dict):         # v20: {"standard": 3, "controlled": 5}
            panel["reviewers"] = {"standard": 4, "controlled": 6}
            size = "4 lenses in STANDARD, 6 in CONTROLLED"
        else:
            panel["reviewers"] = 4
            size = "4 reviewers"
        if found["services"] >= 3:
            cfg["docs_layout"] = "microservices"
            why.append(f"large      — docs_layout microservices, review panel with {size}")
        else:
            why.append(f"large      — review panel with {size}")
    return cfg, why


def narrow_lanes(project: Path, lanes) -> tuple[dict, list[str]]:
    """Best effort: drop lane globs whose literal top-level folder does not exist in the project
    (`backend/**` when there is no backend/). A role keeps its default lane when nothing of it would remain, and
    `tensura/` (workspace) globs and exclusions (`!…`) are always kept. Returns (lanes, [narrowed roles])."""
    if not isinstance(lanes, dict):
        return lanes, []
    out, narrowed = {}, []
    for role, globs in lanes.items():
        if not isinstance(globs, list):
            out[role] = globs
            continue
        keep = []
        for g in globs:
            first = str(g).split("/", 1)[0]
            literal = "/" in str(g) and first and not any(c in first for c in "*?[{!") and first != "tensura"
            if not literal or (project / first).is_dir():
                keep.append(g)
        positive = [g for g in keep if not str(g).startswith("!")]
        if positive and len(keep) < len(globs):
            out[role] = keep
            narrowed.append(role.replace("cecilia-", ""))
        else:
            out[role] = globs
    return out, narrowed


def ask(q: str, yes: bool) -> bool:
    if yes:
        return True
    try:
        return input(f"{q} [y/N] ").strip().lower() in {"y", "yes", "c", "có", "co"}
    except EOFError:
        return False


def smoke(project: Path, home: Path | None = None) -> list[str]:
    guard = (home or project) / ".cecilia" / "bin" / "cecilia_guard.py"
    ws = ["--workspace", str(home)] if home else []
    out = []
    for cmd, want in (("git push origin HEAD", "deny"), ("git status", "allow")):
        if not guard.is_file():
            out.append(f"SKIP  guard not installed ({cmd})")
            continue
        r = subprocess.run([sys.executable, str(guard), "--explain", cmd, "--cwd", str(project), *ws],
                           capture_output=True, text=True, timeout=30)
        got = "?"
        try:
            got = json.loads(r.stdout).get("decision", "?")
        except ValueError:
            pass
        out.append(f"{'OK  ' if got == want else 'FAIL'}  guard: `{cmd}` → {got} (want {want})")
    return out


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True, help="absolute path of the repository")
    ap.add_argument("--host", action="append", choices=["claude", "antigravity"])
    ap.add_argument("--apply", action="store_true", help="write files (default: dry run)")
    ap.add_argument("--yes", action="store_true", help="accept every step without asking")
    ap.add_argument("--no-push-lock", action="store_true", help="in-project mode: skip the push lock")
    ap.add_argument("--push-lock", action="store_true", help="workspace mode: add the git-level push lock too "
                    "(writes the project's .git/config)")
    ap.add_argument("--workspace", default="auto", help="workspace folder (default: <project>.cecilia next to it)")
    ap.add_argument("--in-project", action="store_true", help="older layout: install inside the project")
    ap.add_argument("--scale", choices=["small", "standard", "large"], default="",
                    help="how much ceremony by default (proposed from the repository size when omitted)")
    ap.add_argument("--json", action="store_true", help="print detection + proposal as JSON and stop")
    ap.add_argument("--python", help="interpreter the guard hooks run (default `python` on Windows, `python3` "
                    "elsewhere, from PATH); stored as guard.python in .cecilia/config.json")
    a = ap.parse_args()
    a.python = (a.python or "").strip() or None
    project = Path(a.project)
    if not project.is_absolute() or not project.is_dir():
        print("ERROR: --project must be an existing absolute path", file=sys.stderr)
        return 2
    project = project.resolve()
    if project == Path.home().resolve():
        print("ERROR: --project must be a repository, not your home folder", file=sys.stderr)
        return 2
    hosts = set(a.host or ["claude", "antigravity"])
    home = None
    if not a.in_project:
        home = install.default_workspace(project) if a.workspace == "auto" else Path(a.workspace)
        if not home.is_absolute():
            print("ERROR: --workspace must be an absolute path", file=sys.stderr)
            return 2
        home = home.resolve()
    found = detect(project)
    cfg, why = propose(project, found, home, a.scale)
    if a.python:
        guard_cfg = cfg.get("guard") if isinstance(cfg.get("guard"), dict) else {}
        guard_cfg["python"] = a.python
        cfg["guard"] = guard_cfg
        why.append(f"guard.python — hooks run `{a.python}` (--python)")
    if a.json:
        print(json.dumps({"detected": found, "config": cfg, "reasons": why}, indent=2, ensure_ascii=False))
        return 0

    print(f"Cecilia v20 setup — {project}")
    print(f"Workspace: {home}  (the project folder is not touched)" if home else
          "Layout: in-project (files inside the repository, hidden by .git/info/exclude)")
    print("\n1. Detected")
    for k in ("backend", "frontend", "api", "db", "infra", "tests"):
        items = found[k]
        print(f"   {k:9} {len(items):4d}  {', '.join(items[:3])}{' …' if len(items) > 3 else ''}")
    if found["git"]:
        print("   git       yes")
    elif home:
        print("   git       no (fine for the workspace layout; branches/worktrees need git)")
    else:
        print("   git       NO — run `git init` first (the in-project layout needs .git/info/exclude)")
    print(f"   MCP       context7={'yes' if found['mcp']['context7'] else 'no'} · "
          f"sequential thinking={'yes' if found['mcp']['sequential'] else 'no'} · {len(found['mcp']['servers'])} server(s)")
    print("\n2. Proposed .cecilia/config.json")
    for w in why:
        print("   " + w)
    if not found["git"] and not home:
        print("\nStopped: the in-project layout needs a git repository (git init + first commit, then run this "
              "again) — or drop --in-project for the workspace layout.")
        return 1
    if not a.apply:
        print("\nDry run — nothing written. Re-run with --apply (add --yes to skip questions).")
        return 0

    q = (f"\nCreate the workspace {home} (skills, agents, guard hooks, config — nothing inside the project)?" if home
         else "\nInstall Cecilia into this project (skills, agents, guard hooks, exclude, push lock)?")
    if not ask(q, a.yes):
        print("Nothing written.")
        return 0
    install.choose_hook_form("auto")
    if home:
        plan = install.build_workspace(project, home, hosts, upgrade=(home / ".cecilia").is_dir(), push_lock=a.push_lock,
                                       python=a.python)
    else:
        plan = install.build_project(project, hosts, upgrade=(project / ".cecilia").is_dir(),
                                     push_lock=not a.no_push_lock, python=a.python)
    if plan.conflicts:
        print("Conflicts (left as they are):")
        for dest, reason in plan.conflicts:
            print("   !", plan.display(dest), "-", reason)
    install.apply(plan)
    print(f"   installed: {len(plan.create)} new, {len(plan.replace)} replaced (backups in {plan.display(plan.backup)})")
    for note in plan.notes:
        print("   *", note)

    cfg_file = (home or project) / ".cecilia" / "config.json"
    if ask("Write the proposed .cecilia/config.json (existing values are kept)?", a.yes):
        cfg_file.parent.mkdir(parents=True, exist_ok=True)
        if cfg_file.is_file():
            backup = cfg_file.with_suffix(".json.bak")
            backup.write_text(cfg_file.read_text(encoding="utf-8-sig"), encoding="utf-8")
        cfg_file.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("   config written")
    try:
        reg = install.register_workspace(home or project, project)
        print(f"   registered in {reg}")
    except OSError as e:
        print(f"   WARNING: workspace not registered ({e})")

    print("\n4. Checks")
    doctor = (home or project) / ".cecilia" / "bin" / "cecilia_doctor.py"
    if doctor.is_file():
        r = subprocess.run([sys.executable, str(doctor), "--project", str(home or project)], capture_output=True,
                           text=True, timeout=120)
        print("\n".join("   " + line for line in r.stdout.strip().splitlines()[-25:]))
    for line in smoke(project, home):
        print("   " + line)
    if home:
        print(f"\nNext: Antigravity CLI — cecilia open \"{project}\" --agy   ·   Antigravity IDE — open "
              f"{home / (project.name + '.code-workspace')}   ·   Claude Code — cd \"{home}\" && claude")
        print("Then run the host smoke list (docs/HOST-SMOKE.md).")
    else:
        print("\nNext: open the project in Claude Code / Antigravity and run the host smoke list (docs/HOST-SMOKE.md).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
