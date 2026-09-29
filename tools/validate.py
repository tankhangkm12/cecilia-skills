#!/usr/bin/env python3
"""Validate the Cecilia v20 package. Run from anywhere: `python3 tools/validate.py`.

Checks the package's structure and its declared configuration — not live host behaviour (that is
docs/HOST-SMOKE.md; the release gate is docs/RELEASE.md). Exit 0 only when every check passes and every skill
in the roster (tools/roster.py over tools/registry.py) was checked.

v20 additions: registry errors (tools/registry.py `validate`), stale in-project commands in agent-facing
markdown, repo paths named in docs/*.md and tools/*.py docstrings exist, one version everywhere, the rule
ledger with `tools/rules-patch-*.json` overlays, "v20" in every SKILL.md heading.
Python ≥ 3.9, standard library only.
"""
from __future__ import annotations

import ast
import json
import py_compile
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from roster import ROLES, DEFAULT_OFF, ORCHESTRATOR, all_names  # noqa: E402  — the one roster

try:  # v20: the roster is a layer over the registry (tools/registry.py)
    import registry as REGISTRY  # type: ignore  # noqa: E402
except ImportError:  # pragma: no cover — reported by check_registry()
    REGISTRY = None

MAJOR = "v20"
ROSTER = all_names()
STALE = [r"cecilia-ba\b", r"cecilia-onboard\b", r"cecilia-design-be\b", r"cecilia-design-fe\b",
         r"cecilia-security\b", r"cecilia-lead\b", r"cecilia-verify\b", r"\.locks/", r"common v10",
         r"\breporting\.md\b", r"\bgit-flow\.md\b", r"\bpull-request\.md\b",
         r"\btooling\.md\b", r"\bresearch\.md\b", r"\bmetrics-template\.md\b"]
# v19+: agents hand Cecilia `cecilia mode|approve|push …`; the in-project scripts are the legacy layout only.
STALE_COMMANDS = re.compile(r"cecilia_(?:mode|approve)\.py")
LEGACY_MARK = re.compile(r"legacy:|in-project", re.I)
DESC_MAX = 450          # L0: characters per description (loaded in every session)
CARD_MAX = 5000         # L1: bytes per SKILL.md card
CORE_MIN_MAX = 5500     # L2: bytes of shared/core-min.md (v20: +lanes, rules, HANDOFF, orchestrator-only)
PATH_REF = re.compile(r"`((?:references|assets|scripts)/[^`\s]+?)`")
COMMON_REF = re.compile(r"`common/([a-z-]+\.md)`")
BACKTICK = re.compile(r"`([^`\n]+)`")
REPO_PATH = re.compile(r"(?<![\w/.<-])((?:docs|tools)/[\w./-]+?\.(?:md|py|json))(?![\w/])")

errors: list[str] = []
checked: dict = {"skills": 0, "files": 0, "links": 0}


def err(msg):
    errors.append(msg)


def frontmatter(path: Path):
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        err(f"{path}: BOM")
    if b"\r\n" in raw:
        err(f"{path}: CRLF line endings")
    text = raw.decode("utf-8")
    lines = text.split("\n")
    if lines[0] != "---":
        err(f"{path}: first line must be ---")
        return {}
    try:
        end = lines.index("---", 1)
    except ValueError:
        err(f"{path}: frontmatter not closed")
        return {}
    fm = {}
    for line in lines[1:end]:
        m = re.match(r"^([a-z]+): (.*)$", line)
        if not m:
            err(f"{path}: frontmatter line not `key: value` on one line: {line[:60]}")
            continue
        fm[m.group(1)] = m.group(2)
    return fm


def skill_heading(text: str) -> str:
    """The first Markdown `# ` heading of a SKILL.md body (after the frontmatter)."""
    body = text.split("\n---", 1)[1] if "\n---" in text else text
    for line in body.splitlines():
        if line.startswith("# "):
            return line
    return ""


def check_skill(skill_dir: Path):
    name = skill_dir.name
    sk = skill_dir / "SKILL.md"
    if not sk.is_file():
        err(f"{name}: SKILL.md missing")
        return
    fm = frontmatter(sk)
    if set(fm) != {"name", "description"}:
        err(f"{name}: frontmatter keys must be exactly name, description (got {sorted(fm)})")
    if fm.get("name") != name:
        err(f"{name}: name '{fm.get('name')}' does not match folder")
    d = fm.get("description", "")
    b = len(d.encode("utf-8"))
    if not d or b > 1024:
        err(f"{name}: description is {b} bytes (must be 1..1024)")
    for key, val in fm.items():
        if ": " in val:
            err(f"{name}: `{key}` contains ': ' (YAML would read a mapping)")
        if " #" in val:
            err(f"{name}: `{key}` contains ' #' (YAML comment)")
        if val[:1] in set("-?:,[]{}#&*!|>'\"%@`"):
            err(f"{name}: `{key}` starts with a YAML indicator")
    try:
        import yaml  # type: ignore
        text = sk.read_text(encoding="utf-8").split("\n---", 1)[0].lstrip("-\n")
        parsed = yaml.safe_load(text)
        if parsed.get("name") != name:
            err(f"{name}: PyYAML parse disagrees on name")
    except ImportError:
        pass
    except Exception as e:
        err(f"{name}: PyYAML failed: {e}")
    heading = skill_heading(sk.read_text(encoding="utf-8"))
    if MAJOR not in heading:
        err(f"{name}: SKILL.md heading should state {MAJOR} (got {heading[:70]!r})")
    if len(d) > DESC_MAX:
        err(f"{name}: description is {len(d)} characters (card limit {DESC_MAX})")
    size = len(sk.read_bytes())
    if size > CARD_MAX:
        err(f"{name}: SKILL.md is {size} bytes (card limit {CARD_MAX}; move detail to references/)")

    for f in sorted(skill_dir.rglob("*")):
        if not f.is_file() or f.suffix not in {".md", ".json", ".py"}:
            continue
        checked["files"] += 1
        text = f.read_text(encoding="utf-8")
        rel = f.relative_to(ROOT)
        in_common = "references/common" in f.as_posix()
        if not in_common and f.suffix == ".md":
            for pat in STALE:
                for m in re.finditer(pat, text):
                    line = text[:m.start()].count("\n") + 1
                    ctx = text.splitlines()[line - 1]
                    if "v14" in ctx or "v15" in ctx:
                        continue
                    err(f"{rel}:{line}: stale v14 reference `{m.group(0)}`")
        if f.suffix != ".md":
            continue
        for m in PATH_REF.finditer(text):
            ref = m.group(1).rstrip(".,;:)")
            if "<" in ref or "|" in ref or "*" in ref or "{" in ref:
                continue
            ref = ref.split("#")[0].split(" §")[0]
            checked["links"] += 1
            if not (skill_dir / ref).exists():
                err(f"{rel}: reference `{ref}` does not exist in {name}")
        for m in COMMON_REF.finditer(text):
            checked["links"] += 1
            if not (skill_dir / "references" / "common" / m.group(1)).exists():
                err(f"{rel}: `common/{m.group(1)}` does not exist")
    checked["skills"] += 1


def run_tool(args):
    r = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return r.returncode, (r.stdout + r.stderr).strip()


# ---------------------------------------------------------------------------------------------------- registry

def load_registry(root: Path = ROOT):
    """(registry dict or None, errors). `registry.validate()` errors are validate errors."""
    if REGISTRY is None:
        return None, ["tools/registry.py missing or does not import (v20 roster layer)"]
    try:
        reg = REGISTRY.load(root)
    except Exception as e:  # noqa: BLE001 — any load failure is a finding, not a crash
        return None, [f"registry: load failed: {e}"]
    try:
        problems = [f"registry: {p}" for p in REGISTRY.validate(reg, root)]
    except Exception as e:  # noqa: BLE001
        problems = [f"registry: validate failed: {e}"]
    return reg, problems


def check_registry():
    reg, problems = load_registry(ROOT)
    for p in problems:
        err(p)
    if reg is None:
        return None
    roles = set(reg.get("roles", {}))
    expected = set(ROSTER) - {ORCHESTRATOR}
    if roles - {ORCHESTRATOR} != expected:
        err(f"registry roles {sorted(roles)} differ from the roster {sorted(expected)}")
    checked["registry"] = {"roles": len(roles), "flows": len(reg.get("flows", {})),
                           "lenses": {k: len(v) for k, v in reg.get("lenses", {}).items()}}
    return reg


# ------------------------------------------------------------------------------------------- stale commands

def stale_commands(root: Path = ROOT) -> list[str]:
    """Agent-facing markdown (skills/, shared/) must not tell agents to run the in-project scripts
    `cecilia_mode.py` / `cecilia_approve.py`; use `cecilia mode|approve|push …`. A line about the legacy
    in-project layout may keep them when it says so (`legacy:` or `in-project` on the same line).
    Copies under references/common/ are skipped (their source in shared/ is checked)."""
    found = []
    for base in ("skills", "shared"):
        for f in sorted((root / base).rglob("*.md")) if (root / base).is_dir() else []:
            if "references/common" in f.as_posix():
                continue
            for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                m = STALE_COMMANDS.search(line)
                if m and not LEGACY_MARK.search(line):
                    found.append(f"{f.relative_to(root).as_posix()}:{n}: stale command `{m.group(0)}` — agents "
                                 f"hand Cecilia `cecilia mode|approve …` (mark a legacy in-project line with `legacy:`)")
    return found


# ---------------------------------------------------------------------------------------------- repo paths

def _docstrings(py: Path) -> list[str]:
    try:
        tree = ast.parse(py.read_text(encoding="utf-8"))
    except (SyntaxError, ValueError):
        return []
    out = []
    for node in [tree, *ast.walk(tree)]:
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node)
            if doc:
                out.append(doc)
    return out


def repo_paths(root: Path = ROOT) -> list[str]:
    """Every `docs/<name>.md` / `tools/<name>.py` (or .json) path named in backticks in docs/*.md and README.md,
    and in the docstrings of tools/*.py, must exist. Placeholders (`<…>`, `*`) are skipped."""
    found, seen = [], 0
    sources = [(p, [p.read_text(encoding="utf-8")]) for p in sorted((root / "docs").glob("*.md"))]
    if (root / "README.md").is_file():
        sources.append((root / "README.md", [(root / "README.md").read_text(encoding="utf-8")]))
    for py in sorted((root / "tools").glob("*.py")):
        sources.append((py, _docstrings(py)))
    for src, texts in sources:
        is_py = src.suffix == ".py"
        for text in texts:
            spans = [text] if is_py else [m.group(1) for m in BACKTICK.finditer(text)]
            for span in spans:
                for m in REPO_PATH.finditer(span):
                    ref = m.group(1).rstrip(".")
                    if any(c in ref for c in "<>*{}|"):
                        continue
                    seen += 1
                    if not (root / ref).exists():
                        found.append(f"{src.relative_to(root).as_posix()}: names `{ref}`, which does not exist")
    checked["repo_paths"] = seen
    return sorted(set(found))


# ------------------------------------------------------------------------------------------------ versions

def _grab(path: Path, pattern: str):
    if not path.is_file():
        return None
    m = re.search(pattern, path.read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else None


def version_sources(root: Path = ROOT) -> dict:
    """Every place that states the package version (docs/EXTENDING.md §version lists the same files)."""
    pol = None
    try:
        pol = json.loads((root / "guard/policy.json").read_text(encoding="utf-8")).get("version")
    except (OSError, ValueError):
        pass
    readme = root / "README.md"
    head = "\n".join(readme.read_text(encoding="utf-8").splitlines()[:5]) if readme.is_file() else ""
    m = re.search(r"\b(\d+\.\d+\.\d+)\b", head)
    return {
        "tools/roster.py VERSION": _grab(root / "tools/roster.py", r'^VERSION\s*=\s*"([^"]+)"'),
        "tools/registry.py VERSION": _grab(root / "tools/registry.py", r'^VERSION\s*=\s*"([^"]+)"'),
        "pyproject.toml version": _grab(root / "pyproject.toml", r'^version\s*=\s*"([^"]+)"'),
        "src/cecilia/__init__.py __version__": _grab(root / "src/cecilia/__init__.py", r'^__version__\s*=\s*"([^"]+)"'),
        "guard/cecilia_guard.py VERSION": _grab(root / "guard/cecilia_guard.py", r'^VERSION\s*=\s*"([^"]+)"'),
        "guard/policy.json version": pol,
        "shared/scripts/cecilia_check.py VERSION": _grab(root / "shared/scripts/cecilia_check.py",
                                                         r'^VERSION\s*=\s*"([^"]+)"'),
        "README.md first lines": m.group(1) if m else None,
        "CHANGELOG.md first entry": _grab(root / "CHANGELOG.md", r"^## v(\d+\.\d+\.\d+)"),
        "docs/INSTALL.md install tag": _grab(root / "docs/INSTALL.md", r"cecilia-skills@v(\d+\.\d+\.\d+)"),
    }


def version_mismatches(root: Path = ROOT) -> list[str]:
    src = version_sources(root)
    want = src["tools/roster.py VERSION"]
    out = []
    for where, v in src.items():
        if v is None:
            out.append(f"version: {where} not found (expected {want})")
        elif v != want:
            out.append(f"version: {where} is {v}, tools/roster.py VERSION is {want}")
    readme = root / "README.md"
    if readme.is_file() and want:
        title = readme.read_text(encoding="utf-8").splitlines()[0]
        major = "v" + want.split(".")[0]
        if major not in title:
            out.append(f"version: README.md title should name {major}")
    checked["version"] = want
    return out


# ----------------------------------------------------------------------------------------------- rule ledger

def load_ledger(root: Path = ROOT) -> list[dict]:
    """tools/rules.json with every tools/rules-patch-*.json applied over it by id (the integrator merges the
    patches later). A patch entry is {"id","file","phrase"|"must_contain","note"} or {"id","dropped":true,
    "reason"}; all entries with one id replace that id's ledger rule (several phrases = several entries)."""
    rules = json.loads((root / "tools" / "rules.json").read_text(encoding="utf-8"))["rules"]
    patched: dict[str, list[dict]] = {}
    for pf in sorted((root / "tools").glob("rules-patch-*.json")):
        data = json.loads(pf.read_text(encoding="utf-8"))
        entries = data.get("rules", []) if isinstance(data, dict) else data
        for e in entries:
            if not isinstance(e, dict) or not e.get("id"):
                raise ValueError(f"{pf.name}: entry without an id: {e!r}")
            patched.setdefault(e["id"], []).append({**e, "_patch": pf.name})
    out = [r for r in rules if r["id"] not in patched]
    for rid, entries in patched.items():
        if any(e.get("dropped") for e in entries):
            e = entries[-1]
            out.append({"id": rid, "rule": e.get("note", ""), "dropped": True,
                        "reason": e.get("reason") or e.get("note"), "patch": e["_patch"]})
            continue
        for i, e in enumerate(entries):
            phrases = e.get("must_contain") or ([e["phrase"]] if e.get("phrase") else [])
            if not e.get("file") or not phrases:
                raise ValueError(f"{e['_patch']}: {rid} needs `file` and `phrase`")
            out.append({"id": rid, "rule": e.get("note", ""), "file": e["file"], "must_contain": phrases,
                        "patch": e["_patch"], "part": i})
    return out


def ledger_problems(root: Path = ROOT) -> tuple[list[str], str]:
    """Each kept rule must still be findable (every phrase present in its file); dropped rules need a reason;
    kept ≥ 95 % of the rule ids."""
    if not (root / "tools" / "rules.json").is_file():
        return ["tools/rules.json (rule ledger) missing"], ""
    try:
        rules = load_ledger(root)
    except (OSError, ValueError, KeyError) as e:
        return [f"rule ledger: {e}"], ""
    out = []
    cache: dict[Path, str] = {}
    for r in rules:
        if r.get("dropped"):
            if not r.get("reason"):
                out.append(f"rule {r['id']}: dropped without a reason")
            continue
        f = root / r["file"]
        if not f.is_file():
            out.append(f"rule {r['id']}: file {r['file']} missing")
            continue
        if f not in cache:
            cache[f] = " ".join(f.read_text(encoding="utf-8").split())
        for phrase in r["must_contain"]:
            if " ".join(phrase.split()) not in cache[f]:
                src = f" [{r['patch']}]" if r.get("patch") else ""
                out.append(f"rule {r['id']} ({r.get('rule', '')[:50]}…){src}: phrase not found in {r['file']}: {phrase!r}")
    ids = {r["id"] for r in rules}
    dropped = {r["id"] for r in rules if r.get("dropped")}
    share = (len(ids) - len(dropped)) / len(ids) if ids else 0
    patches = len({r["patch"] for r in rules if r.get("patch")})
    summary = f"{len(ids) - len(dropped)}/{len(ids)} kept ({share:.1%})" + (f", {patches} patch file(s)" if patches else "")
    if share < 0.95:
        out.append(f"rule ledger: only {share:.1%} of the ledger rules kept (need ≥ 95%)")
    return out, summary


def check_rule_ledger():
    problems, summary = ledger_problems(ROOT)
    for p in problems:
        err(p)
    checked["rules"] = summary


# -------------------------------------------------------------------------------------------- adapters/guard

def check_adapters():
    code, out = run_tool(["tools/build_adapters.py", "--check"])
    if code:
        err("adapters: " + out[-1500:])
    for f in (ROOT / "adapters").rglob("*.json"):
        try:
            json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            err(f"{f.relative_to(ROOT)}: invalid JSON: {e}")
    for f in (ROOT / "adapters").rglob("*.md"):
        text = f.read_text(encoding="utf-8")
        m = re.search(r"^name: (\S+)$", text, re.M)
        if m and m.group(1) not in ROSTER:
            err(f"{f.relative_to(ROOT)}: agent for unknown skill {m.group(1)}")
        if m:
            fm = text.split("\n---", 1)[0]
            for line in fm.splitlines()[1:]:
                if line.startswith("description: ") and ": " in line[len("description: "):]:
                    err(f"{f.relative_to(ROOT)}: description contains ': '")
    review = (ROOT / "adapters/claude-code/agents/cecilia-review.md").read_text(encoding="utf-8")
    tools_line = re.search(r"^tools: (.*)$", review, re.M).group(1)
    if any(t in tools_line for t in ("Write", "Edit", "Bash", "Agent")):
        err("claude review agent must not have write, shell or delegation tools")
    settings_file = ROOT / "adapters/claude-code/settings.cecilia.json"
    settings = settings_file.read_text(encoding="utf-8")
    if "__CECILIA_PYTHON__" not in settings or "__CECILIA_GUARD__" not in settings:
        err("claude settings hook must use the __CECILIA_PYTHON__/__CECILIA_GUARD__ placeholders (install.py fills them)")
    # v20: the workflow gate sees sub-agent dispatches (DESIGN-V20 §5.3)
    matchers = re.findall(r'"matcher"\s*:\s*"([^"]*)"', settings)
    if not any(re.search(r"(^|\|)Agent(\||$)", mt) and re.search(r"(^|\|)Task(\||$)", mt) for mt in matchers):
        err("claude settings: the PreToolUse matcher must include Agent|Task (v20 workflow gate)")
    if (ROOT / "adapters/codex").exists():
        err("adapters/codex must not exist (Claude Code + Antigravity only)")
    ag = (ROOT / "adapters/antigravity/agents/cecilia-review/agent.md").read_text(encoding="utf-8")
    if any(t in ag for t in ("write_to_file", "replace_file_content", "run_command", "invoke_subagent")):
        err("antigravity review agent must not have write, command or delegation tools")
    orch = ROOT / f"adapters/antigravity/agents/{ORCHESTRATOR}/agent.md"
    if orch.is_file() and not re.search(r"^mainAgent: true$", orch.read_text(encoding="utf-8"), re.M):
        err("antigravity orchestrator agent must be the main agent (`mainAgent: true`, v20)")


def check_guard():
    required = ("guard/cecilia_guard.py", "guard/cecilia_approve.py", "guard/cecilia_mode.py", "guard/cecilia_doctor.py",
                "tools/check_packet.py", "skills/cecilia-orchestrator/scripts/workflow.py", "shared/scripts/capacity.py",
                "shared/scripts/cecilia_check.py", "skills/cecilia-api-ux/scripts/apikit.py",
                "shared/scoped/frontend/uikit.py", "tools/install.py", "tools/sync_common.py", "tools/tokens.py",
                "tools/roster.py", "tools/registry.py", "tools/scaffold.py", "tools/build_adapters.py",
                "tools/guard_corpus.py", "tools/setup.py", "tools/package.py", "tools/evals/run_evals.py",
                "tools/workspace_tools.py", "src/cecilia/cli.py", "src/cecilia/__init__.py")
    for f in required:
        if not (ROOT / f).is_file():
            err(f"{f}: missing")
            continue
        try:
            py_compile.compile(str(ROOT / f), doraise=True)
        except py_compile.PyCompileError as e:
            err(f"{f}: does not compile: {e}")
    code, out = run_tool(["shared/scoped/frontend/uikit.py", "contrast", "#767676", "#ffffff", "--json"])
    if code or '"ratio": 4.54' not in out:
        err("uikit.py contrast must report 4.54 for #767676 on white")
    cfg_file = ROOT / "shared/scoped/frontend/playwright-cli.config.json"
    try:
        origins = json.loads(cfg_file.read_text(encoding="utf-8"))["network"]["allowedOrigins"]
        if not origins or any("localhost" not in o and "127.0.0.1" not in o for o in origins):
            err("playwright-cli.config.json must allow local origins only")
    except (OSError, ValueError, KeyError) as e:
        err(f"playwright-cli.config.json unreadable: {e}")
    for cmd in ("gh pr merge 1", "git push origin feature/x", "gh pr create --draft", "git push --no-verify"):
        code, out = run_tool(["guard/cecilia_guard.py", "--explain", cmd])
        if code or '"deny"' not in out:
            err(f"guard: `{cmd}` must be denied (local-only)")
    for cmd in ("cecilia flow team", "cecilia rules add --project x", "cecilia extension apply tensura/extensions/x"):
        code, out = run_tool(["guard/cecilia_guard.py", "--explain", cmd])
        if code or '"deny"' not in out:
            err(f"guard: `{cmd}` must be denied (human-only, v20)")
    for e in version_mismatches(ROOT):
        err(e)
    try:
        pol = json.loads((ROOT / "guard/policy.json").read_text(encoding="utf-8"))
        for key in ("default_profiles", "local_only_paths", "live_tools"):
            if not pol.get(key):
                err(f"guard/policy.json: `{key}` missing or empty")
    except (OSError, ValueError) as e:
        err(f"guard/policy.json unreadable: {e}")
    sys.path.insert(0, str(ROOT / "guard"))
    import cecilia_approve  # type: ignore
    text = (ROOT / "skills/cecilia-plan/assets/plan-template.md").read_text(encoding="utf-8")
    blocks = cecilia_approve.parse_blocks(text.replace("<TASK>", "SHOP-42"))
    if not blocks:
        err("plan template has no cecilia-scope block")
    for _, b in blocks:
        try:
            cecilia_approve.validate(b)
        except cecilia_approve.ScopeError as e:
            err(f"plan template scope block invalid: {e}")


def check_read_first():
    """Every skill reads core-min.md first (L2); core-min stays small and routes to core.md."""
    for name in ROSTER:
        sk = ROOT / "skills" / name / "SKILL.md"
        if not sk.is_file():
            continue
        if "**Read first:** `references/common/core-min.md`" not in sk.read_text(encoding="utf-8"):
            err(f"{name}/SKILL.md: must start its references with **Read first:** `references/common/core-min.md`")
    core_min = ROOT / "shared" / "core-min.md"
    if not core_min.is_file():
        err("shared/core-min.md missing")
    elif len(core_min.read_bytes()) > CORE_MIN_MAX:
        err(f"shared/core-min.md is {len(core_min.read_bytes())} bytes (limit {CORE_MIN_MAX})")


def check_tokens():
    code, out = run_tool(["tools/tokens.py", "--check"])
    if code:
        err("token budgets: " + out[-800:])


def _table_rows(text: str) -> set[str]:
    return {m.group(1) for m in re.finditer(r"^\|\s*`?(cecilia-[a-z-]+)`?\s*\|", text, re.M)}


def check_role_wiring(reg):
    """Every role has a review guide, an ownership/lane row and a clean default config.

    v20: the tables are generated from the registry (`shared/generated/roster.md`, by tools/build_adapters.py);
    a hand table that still exists (review SKILL.md "Review guide per role", shared/workspace.md ownership) must
    not miss a role either."""
    roles = [n for n in ROSTER if n != ORCHESTRATOR]
    generated = ROOT / "shared/generated/roster.md"
    if reg is not None:
        if not generated.is_file():
            err("shared/generated/roster.md missing (tools/build_adapters.py writes it from the registry)")
        else:
            rows = _table_rows(generated.read_text(encoding="utf-8"))
            for name in roles:
                if name not in rows:
                    err(f"shared/generated/roster.md: role {name} has no row")
        for name in roles:
            if name != "cecilia-review" and not reg.get("roles", {}).get(name, {}).get("review_guide"):
                err(f"registry: role {name} has no review guide (review_guide)")
    review = (ROOT / "skills/cecilia-review/SKILL.md").read_text(encoding="utf-8")
    section = review.split("## Review guide per role", 1)
    if len(section) == 2:
        table = section[1].split("\n## ", 1)[0]
        for name in roles:
            if name == "cecilia-review":
                continue
            row = next((l for l in table.splitlines() if l.startswith(f"| {name} |")), None)
            if not row:
                err(f"cecilia-review/SKILL.md: role {name} has no review guide row")
            elif "references/" not in row:
                err(f"cecilia-review/SKILL.md: role {name} row names no guide file")
    elif reg is None:
        err("cecilia-review/SKILL.md: missing '## Review guide per role' table (and no registry)")
    workspace = (ROOT / "shared/workspace.md").read_text(encoding="utf-8")
    if reg is None or "generated/roster.md" not in workspace:
        for name in [ORCHESTRATOR, *roles] if reg is None else roles:
            if f"| {name} |" not in workspace:
                err(f"shared/workspace.md: role {name} has no ownership row (or link shared/generated/roster.md)")
    unknown = DEFAULT_OFF - set(ROLES)
    if unknown:
        err(f"tools/roster.py: DEFAULT_OFF names unknown roles {sorted(unknown)}")
    kinds = {"code", "docs", "design", "read"}
    if reg is not None:
        kinds |= {r.get("kind") for r in reg.get("roles", {}).values() if r.get("kind")}
    for name, (kind, _) in ROLES.items():
        if kind not in kinds:
            err(f"tools/roster.py: {name} has unknown kind {kind}")
    # a design-kind agent may use design MCP but never a shell
    for name, (kind, _) in ROLES.items():
        if kind != "design":
            continue
        claude_file = ROOT / f"adapters/claude-code/agents/{name}.md"
        if not claude_file.is_file():
            err(f"{claude_file.relative_to(ROOT)} missing")
            continue
        deny = re.search(r"^disallowedTools: (.*)$", claude_file.read_text(encoding="utf-8"), re.M)
        if not deny or "Bash" not in deny.group(1):
            err(f"claude agent {name} (design kind) must disallow Bash")


def _utf8_console() -> None:
    """Windows consoles default to a legacy code page; keep output readable and crash-free."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main() -> int:
    _utf8_console()
    names = sorted(p.name for p in (ROOT / "skills").iterdir() if p.is_dir() and not p.name.startswith((".", "_")))
    if names != ROSTER:
        err(f"roster must be exactly {ROSTER}, got {names}")
    for n in names:
        check_skill(ROOT / "skills" / n)
    code, out = run_tool(["tools/sync_common.py", "--check"])
    if code:
        err(out)
    reg = check_registry()
    check_adapters()
    check_guard()
    check_role_wiring(reg)
    check_read_first()
    for e in stale_commands(ROOT):
        err(e)
    for e in repo_paths(ROOT):
        err(e)
    check_rule_ledger()
    check_tokens()
    ok = not errors and checked["skills"] == len(ROSTER)
    print(json.dumps({"result": "PASS" if ok else "FAIL", "checked": checked, "errors": errors,
                      "scope": "package structure and declared config — not live host behaviour"},
                     indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
