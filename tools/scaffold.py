#!/usr/bin/env python3
"""Scaffold a new Cecilia role, flow or lens from templates/ and validate it against the registry (v20).

    scaffold.py role  <name> [--agent-type writer|tester|reviewer] [--lane GLOB ...] [--kind test|review]
                             [--consumes X ...] [--produces X ...] [--describe TEXT] [--when TEXT]
    scaffold.py flow  <name> [--describe TEXT]
    scaffold.py lens  <name> --kind test|review [--describe TEXT] [--when TEXT]
    common:  [--target proposal|repo] [--workspace WS] [--out DIR] [--force]
    scaffold.py --check DIR [--workspace WS]      validate an existing proposal only (no writes)

Targets
  proposal (default)  a self-contained overlay in <ws>/tensura/extensions/<name>/ with the layout of
                      .cecilia/extensions/: registry/{roles|flows|lenses/<kind>}/<name>.json, skills/<role>/…,
                      flows/<name>.md, lenses/<kind>/<name>.md, rules/{roles|flows|lenses}/<name>.md.
                      Cecilia applies it herself: `cecilia extension apply tensura/extensions/<name>`.
  repo                the Cecilia source repo (or --out DIR holding a copy of it): registry/…, skills/cecilia-<name>/…,
                      shared/flows/<name>.md, skills/cecilia-{test|review}/references/lenses/<name>.md.

Names are normalised (kebab-case; roles get the `cecilia-` prefix). Existing files are never overwritten without
--force; a name that already exists in the core registry (or in the workspace's applied extensions) is refused.
After writing, the result is validated with tools/registry.py (core + overlay for proposals) plus the SKILL.md
card rules; any error → exit 1. `TODO(extend)` markers are listed after scaffolding and are errors for --check.
This tool never writes under `.cecilia/` — applying an extension is human-only.
Stdlib only, Python 3.9+.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
sys.path.insert(0, str(ROOT / "tools"))

WHATS = ("role", "flow", "lens")
AGENT_TYPES = ("writer", "tester", "reviewer")
LENS_KINDS = ("test", "review")
NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
PLACEHOLDER = re.compile(r"\{\{([a-z0-9_]+)\}\}")
LEFTOVER = re.compile(r"\{\{[^{}\n]*\}\}")          # any {{…}} left in a filled file is a mistake
TODO = "TODO(extend)"
DESC_MAX = 450
CARD_MAX = 5000
READ_FIRST = "**Read first:** `references/common/core-min.md`"
RESERVED = {"cecilia-orchestrator", "orchestrator", "cecilia", "cecilia-cecilia"}


class ScaffoldError(Exception):
    pass


# ---------------------------------------------------------------- names

def normalise(what: str, raw: str) -> str:
    """'Data Eng' -> 'cecilia-data-eng' (role) / 'data-eng' (flow, lens)."""
    s = raw.strip().lower().replace("_", "-").replace(" ", "-")
    s = re.sub(r"[^a-z0-9-]", "", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    if what == "role":
        while s.startswith("cecilia-"):
            s = s[len("cecilia-"):]
        s = f"cecilia-{s}" if s else ""
    if not s or not NAME_RE.match(s) or s in RESERVED or s == "cecilia-":
        raise ScaffoldError(f"invalid {what} name {raw!r} (use letters, digits and '-', starting with a letter)")
    return s


def short(name: str) -> str:
    return name[len("cecilia-"):] if name.startswith("cecilia-") else name


# ---------------------------------------------------------------- filling templates

def fill_text(text: str, values: dict) -> str:
    def rep(m):
        key = m.group(1)
        if key not in values:
            raise ScaffoldError(f"template placeholder {{{{{key}}}}} has no value")
        v = values[key]
        return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    return PLACEHOLDER.sub(rep, text)


def fill_json(obj, values: dict):
    """A string that is exactly '{{key}}' becomes the typed value (list, bool, null); others are text-filled."""
    if isinstance(obj, dict):
        return {k: fill_json(v, values) for k, v in obj.items()}
    if isinstance(obj, list):
        return [fill_json(v, values) for v in obj]
    if isinstance(obj, str):
        m = PLACEHOLDER.fullmatch(obj)
        if m:
            if m.group(1) not in values:
                raise ScaffoldError(f"template placeholder {obj} has no value")
            return values[m.group(1)]
        return fill_text(obj, values)
    return obj


def template(rel: str) -> str:
    p = TEMPLATES / rel
    if not p.is_file():
        raise ScaffoldError(f"template {p} missing")
    return p.read_text(encoding="utf-8")


def render_manifest(what: str, values: dict) -> str:
    obj = fill_json(json.loads(template(f"{what}/manifest.json")), values)
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def rules_file(kind: str, name: str, values: dict) -> str:
    """The per-project rules slot. Same format as `cecilia init` writes (templates/rules/<kind>.md) when present."""
    shared = TEMPLATES / "rules" / f"{kind}.md"
    if shared.is_file():
        return shared.read_text(encoding="utf-8").replace("__NAME__", name).replace("__SHORT__", short(name))
    if kind == "role":
        return fill_text(template("role/rules.md"), values)
    return (f"# Rules for the {name} {kind}\n\n<!-- cecilia-rules v20 · one rule per line `- PR-nn: text`; "
            f"only Cecilia edits rules/. Rules only tighten. -->\n")


def md_list(items, empty="nothing") -> str:
    return ", ".join(f"`{x}`" for x in items) if items else empty


# ---------------------------------------------------------------- per artefact

def role_values(name: str, a) -> dict:
    sh = short(name)
    at = a.agent_type or "writer"
    if at not in AGENT_TYPES:
        raise ScaffoldError(f"--agent-type must be one of {', '.join(AGENT_TYPES)}")
    if at == "reviewer" and a.lane:
        raise ScaffoldError("a reviewer is read-only: it takes no --lane")
    if a.lane:
        lane = list(a.lane)
    elif at == "writer":
        lane = [f"tensura/docs/{sh}/**"]
    elif at == "tester":
        lane = ["tests/**", "**/*.test.*", "**/*.spec.*"]
    else:
        lane = []
    positive = [g for g in lane if not g.startswith("!")]
    if at == "reviewer":
        kind = "read"
    elif positive and all(g.startswith("tensura/") for g in positive):
        kind = "docs"
    else:
        kind = "code"
    lenses = a.kind or ("test" if at == "tester" else None)
    describe = (a.describe or "").strip()
    if describe:
        description = describe if describe.endswith(".") else describe + "."
        purpose = description
    else:
        description = f"{TODO} one line — what {name} does, for which task, and what it never does."
        purpose = f"{TODO} one paragraph — the single responsibility of this role."
    report = f"tensura/reports/<TASK>/{sh}.md"
    consumes = list(a.consumes or ["brief"])
    produces = list(a.produces or (["report"] if at == "reviewer" else [sh, "report"]))
    parts = [p for p in sh.split("-") if p]
    prefix = "".join(p[0] for p in parts[:2]).upper() or "S"
    if at == "reviewer":
        a2 = "read the brief's inputs, code and docs; run read-only local checks; return the report as text"
        a3 = "any command that writes, any non-local host"
        a4 = "edit code, docs or rules; approve its own findings; push/PR, production, secrets"
        lane_md = "its report (returned as text; the orchestrator stores it)"
    else:
        what = "tests" if at == "tester" else "outputs"
        a2 = f"its {what} inside its lane on a task branch; local checks and runs"
        a3 = "installs, downloads, shared/staging systems, deletes, any network write"
        a4 = "push/PR, merge, production, IAM, secrets (write the commands for Cecilia)"
        lane_md = md_list(lane)
    return {
        "name": name, "short": sh, "agent_type": at, "kind": kind, "description": description,
        "default_on": True, "model": "strongest" if at == "reviewer" else "balanced",
        "consumes": consumes, "produces": produces, "lane": lane, "report": report,
        "review_guide": [f"../{name}/references/review-guide.md"], "lenses": lenses,
        "title": sh.replace("-", " "), "purpose": purpose, "prefix": prefix,
        "authority_a2": a2, "authority_a3": a3, "authority_a4": a4, "lane_md": lane_md,
        "consumes_md": md_list(consumes), "produces_md": md_list(produces),
        "dispatch_when": (a.when or f"{TODO} the tasks or signals for which the orchestrator picks this role."),
        "not_for": f"{TODO} the neighbouring roles' work (name the role to hand off to).",
    }


def lens_values(name: str, a) -> dict:
    if a.kind not in LENS_KINDS:
        raise ScaffoldError("a lens needs --kind test|review")
    summary = (a.describe or f"{TODO} one line — what this lens looks for.").strip()
    return {
        "name": name, "kind": a.kind, "summary": summary,
        "when": (a.when or f"{TODO} what a change must touch for this lens to be picked").strip(),
        "owner": "cecilia-test" if a.kind == "test" else "cecilia-review",
        "shared_rules": "`../workflow.md` §Lenses" if a.kind == "test" else "`../panel.md` §3–§6",
        "report_name": f"{a.kind}-{name}", "guide": "",
    }


def plan(what: str, name: str, a, target: str) -> dict:
    """relative path -> file content (relative to the repo root or to the proposal folder)."""
    files: dict = {}
    if what == "role":
        v = role_values(name, a)
        files[f"registry/roles/{name}.json"] = render_manifest("role", v)
        files[f"skills/{name}/SKILL.md"] = fill_text(template("role/SKILL.md"), v)
        files[f"skills/{name}/references/workflow.md"] = fill_text(template("role/references/workflow.md"), v)
        files[f"skills/{name}/references/review-guide.md"] = fill_text(template("role/review-guide.md"), v)
        if target == "proposal":
            files[f"rules/roles/{short(name)}.md"] = rules_file("role", name, v)
    elif what == "flow":
        guide = f"shared/flows/{name}.md" if target == "repo" else f"flows/{name}.md"
        v = {"name": name, "guide": guide,
             "summary": (a.describe or f"{TODO} one line — what this flow is for.").strip()}
        files[f"registry/flows/{name}.json"] = render_manifest("flow", v)
        files[guide] = fill_text(template("flow/guide.md"), v)
        if target == "proposal":
            files[f"rules/flows/{name}.md"] = rules_file("flow", name, v)
    else:
        v = lens_values(name, a)
        owner = v["owner"]
        v["guide"] = (f"skills/{owner}/references/lenses/{name}.md" if target == "repo"
                      else f"lenses/{a.kind}/{name}.md")
        files[f"registry/lenses/{a.kind}/{name}.json"] = render_manifest("lens", v)
        files[v["guide"]] = fill_text(template("lens/guide.md"), v)
        if target == "proposal":
            files[f"rules/lenses/{name}.md"] = rules_file("lens", name, v)
    for rel, text in files.items():
        left = LEFTOVER.findall(text)
        if left:
            raise ScaffoldError(f"{rel}: unfilled placeholders {sorted(set(left))}")
    return files


# ---------------------------------------------------------------- locations

def find_workspace(start: Path):
    p = start.resolve()
    for d in (p, *p.parents):
        if (d / ".cecilia" / "config.json").is_file():
            return d
    return None


def refuse_control_path(path: Path) -> None:
    if ".cecilia" in path.resolve().parts:
        raise ScaffoldError(f"{path}: scaffold never writes under .cecilia/ — "
                            "Cecilia applies a proposal with `cecilia extension apply`")


def write_files(base: Path, files: dict, force: bool) -> list:
    refuse_control_path(base)
    existing = [rel for rel in files if (base / rel).exists()]
    if existing and not force:
        raise ScaffoldError("refusing to overwrite (use --force): " + ", ".join(str(base / r) for r in existing))
    written = []
    for rel, text in files.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        written.append(p)
    return written


# ---------------------------------------------------------------- validation

def check_card(skill_dir: Path) -> list:
    """The SKILL.md card rules of tools/validate.py, for one skill folder."""
    errs = []
    sk = skill_dir / "SKILL.md"
    name = skill_dir.name
    if not sk.is_file():
        return [f"{name}: SKILL.md missing"]
    raw = sk.read_bytes()
    if b"\r\n" in raw:
        errs.append(f"{name}: SKILL.md has CRLF line endings")
    if len(raw) > CARD_MAX:
        errs.append(f"{name}: SKILL.md is {len(raw)} bytes (card limit {CARD_MAX}; move detail to references/)")
    text = raw.decode("utf-8")
    lines = text.split("\n")
    if lines[0] != "---" or "---" not in lines[1:]:
        return errs + [f"{name}: SKILL.md needs a --- frontmatter block"]
    end = lines.index("---", 1)
    fm = {}
    for line in lines[1:end]:
        m = re.match(r"^([a-z]+): (.*)$", line)
        if not m:
            errs.append(f"{name}: frontmatter line not `key: value` on one line: {line[:60]}")
            continue
        fm[m.group(1)] = m.group(2)
    if set(fm) != {"name", "description"}:
        errs.append(f"{name}: frontmatter keys must be exactly name, description (got {sorted(fm)})")
    if fm.get("name") != name:
        errs.append(f"{name}: frontmatter name {fm.get('name')!r} does not match the folder")
    d = fm.get("description", "")
    if not d or len(d) > DESC_MAX:
        errs.append(f"{name}: description is {len(d)} characters (1..{DESC_MAX})")
    for key, val in fm.items():
        if ": " in val:
            errs.append(f"{name}: `{key}` contains ': ' (YAML would read a mapping)")
        if " #" in val:
            errs.append(f"{name}: `{key}` contains ' #' (YAML comment)")
        if val[:1] in set("-?:,[]{}#&*!|>'\"%@`"):
            errs.append(f"{name}: `{key}` starts with a YAML indicator")
    body = "\n".join(lines[end + 1:])
    if "v20" not in body[:400]:
        errs.append(f"{name}: SKILL.md title must state v20")
    if READ_FIRST not in body:
        errs.append(f"{name}: SKILL.md must contain {READ_FIRST}")
    return errs


def _registry():
    try:
        import registry  # type: ignore
    except ImportError as e:  # pragma: no cover — shipped together
        raise ScaffoldError(f"tools/registry.py not importable: {e}")
    return registry


def _validate(reg_mod, root: Path, extensions=None) -> list:
    return reg_mod.validate(reg_mod.load(root, extensions=extensions), root)


def applied_names(ws) -> dict:
    """Names already in <ws>/.cecilia/extensions/registry (read-only)."""
    out: dict = {}
    if not ws:
        return out
    base = Path(ws) / ".cecilia" / "extensions" / "registry"
    for sub in ("roles", "flows", "lenses/test", "lenses/review", "agent-types"):
        d = base / sub
        if d.is_dir():
            out[sub] = {f.stem for f in d.glob("*.json")}
    return out


def core_names(reg_mod, root: Path) -> dict:
    reg = reg_mod.load(root)
    return {"roles": set(reg["roles"]), "flows": set(reg["flows"]), "agent-types": set(reg["agent_types"]),
            "lenses/test": set(reg["lenses"]["test"]), "lenses/review": set(reg["lenses"]["review"])}


def _section(what: str, kind) -> str:
    return {"role": "roles", "flow": "flows"}.get(what) or f"lenses/{kind}"


def _review_guide_shim(errs: list, ext: Path) -> list:
    """registry.validate resolves review guides in core skills/cecilia-review/ only; an extension role ships its
    own guide as ../<role>/references/review-guide.md. Keep that error only when the file is really missing."""
    out = []
    pat = re.compile(r"^roles/(\S+): review guide skills/cecilia-review/(\S+) missing$")
    for e in errs:
        m = pat.match(e)
        if m:
            p = Path(os.path.normpath(ext / "skills" / "cecilia-review" / m.group(2)))
            if p.is_file() and ext.resolve() in p.resolve().parents:
                continue
        out.append(e)
    return out


def validate_proposal(prop: Path, ws=None, strict: bool = False) -> tuple:
    """(errors, warnings) for a proposal folder, validated as an overlay on the core registry."""
    reg_mod = _registry()
    errs, warns = [], []
    if not prop.is_dir():
        return [f"{prop}: not a folder"], warns
    if not (prop / "registry").is_dir():
        errs.append(f"{prop}: no registry/ folder — not a Cecilia extension proposal")
    base_errs = set(_validate(reg_mod, ROOT))
    warns += [f"core registry (not this proposal): {e}" for e in sorted(base_errs)]
    new = [e for e in _validate(reg_mod, ROOT, extensions=prop) if e not in base_errs]
    errs += _review_guide_shim(new, prop)
    taken = applied_names(ws)
    for sub, names in taken.items():
        d = prop / "registry" / sub
        for f in (sorted(d.glob("*.json")) if d.is_dir() else []):
            if f.stem in names:
                errs.append(f"registry/{sub}/{f.name}: {f.stem!r} collides with an extension already applied "
                            f"in {Path(ws) / '.cecilia' / 'extensions'}")
    for skill in sorted((prop / "skills").glob("*")) if (prop / "skills").is_dir() else []:
        if skill.is_dir():
            errs += check_card(skill)
    errs += _text_checks(prop, strict, warns)
    return errs, warns


def _text_checks(base: Path, strict: bool, warns: list, files=None) -> list:
    errs = []
    paths = files if files is not None else [p for p in sorted(base.rglob("*")) if p.is_file()]
    for p in paths:
        if p.suffix not in {".md", ".json"}:
            continue
        text = p.read_text(encoding="utf-8")
        rel = p.relative_to(base) if base in p.parents else p
        if LEFTOVER.search(text):
            errs.append(f"{rel}: unfilled {{{{placeholder}}}}")
        n = text.count(TODO)
        if n:
            (errs if strict else warns).append(f"{rel}: {n} {TODO} marker(s) left — fill them")
    return errs


# ---------------------------------------------------------------- commands

def scaffold(a) -> int:
    reg_mod = _registry()
    name = normalise(a.what, a.name)
    if a.what == "lens" and a.kind not in LENS_KINDS:
        raise ScaffoldError("a lens needs --kind test|review")
    section = _section(a.what, a.kind)
    target = a.target
    ws = None
    if target == "proposal":
        ws = Path(a.workspace).resolve() if a.workspace else find_workspace(Path.cwd())
        if a.out:
            base = Path(a.out).resolve()
        elif ws:
            base = ws / "tensura" / "extensions" / name
        else:
            raise ScaffoldError("no workspace found (folder with .cecilia/config.json) — pass --workspace or --out")
        if name in core_names(reg_mod, ROOT).get(section, set()):
            raise ScaffoldError(f"{a.what} {name!r} already exists in the core registry — pick another name")
        if name in applied_names(ws).get(section, set()):
            raise ScaffoldError(f"{a.what} {name!r} is already applied in {ws / '.cecilia' / 'extensions'}")
    else:
        base = Path(a.out).resolve() if a.out else ROOT
        if not (base / "registry").is_dir():
            raise ScaffoldError(f"{base}: not a Cecilia source repo (no registry/)")
        if name in core_names(reg_mod, base).get(section, set()) and not a.force:
            raise ScaffoldError(f"{a.what} {name!r} already exists in {base / 'registry'} (use --force to rewrite it)")
    files = plan(a.what, name, a, target)
    base_errs = set(_validate(reg_mod, base)) if target == "repo" else set()
    written = write_files(base, files, a.force)

    warns: list = []
    if target == "proposal":
        errs, warns = validate_proposal(base, ws, strict=False)
    else:
        errs = [e for e in _validate(reg_mod, base) if e not in base_errs]
        warns = [f"registry (before this scaffold): {e}" for e in sorted(base_errs)]
        if a.what == "role":
            errs += check_card(base / "skills" / name)
        errs += _text_checks(base, False, warns, files=written)

    print(f"scaffold {a.what} {name} → {base}  (target: {target})")
    for p in written:
        print(f"  wrote {p.relative_to(base).as_posix()}")
    for w in warns:
        print(f"  note: {w}")
    for e in errs:
        print(f"  ERROR: {e}")
    if errs:
        print(f"FAIL — {len(errs)} error(s)")
        return 1
    print("PASS — registry and card checks")
    if target == "proposal":
        rel = base.relative_to(ws).as_posix() if ws and ws in base.parents else str(base)
        print(f"next: fill every {TODO}, run `scaffold.py --check {rel}`, then Cecilia runs "
              f"`cecilia extension apply {rel}` herself.")
    else:
        print("next: fill every TODO(extend), then python3 tools/sync_common.py · tools/build_adapters.py · "
              "tools/validate.py · python3 -m unittest discover -s tests")
    return 0


def check(a) -> int:
    prop = Path(a.check).resolve()
    ws = Path(a.workspace).resolve() if a.workspace else find_workspace(prop)
    errs, warns = validate_proposal(prop, ws, strict=True)
    for w in warns:
        print(f"  note: {w}")
    for e in errs:
        print(f"  ERROR: {e}")
    print(("FAIL" if errs else "PASS") + f" — {prop} ({len(errs)} error(s))")
    return 1 if errs else 0


def _utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv=None) -> int:
    _utf8_console()
    ap = argparse.ArgumentParser(description="Scaffold a Cecilia role, flow or lens (v20).")
    ap.add_argument("what", nargs="?", choices=WHATS)
    ap.add_argument("name", nargs="?")
    ap.add_argument("--kind", choices=LENS_KINDS, help="lens kind; for a role: the lens kind it takes")
    ap.add_argument("--agent-type", choices=AGENT_TYPES, help="role permissions (default writer)")
    ap.add_argument("--lane", nargs="+", metavar="GLOB", help="role write lane (tensura/… = workspace, else project)")
    ap.add_argument("--consumes", nargs="+", metavar="ARTEFACT")
    ap.add_argument("--produces", nargs="+", metavar="ARTEFACT")
    ap.add_argument("--describe", metavar="TEXT", help="one line: role description / flow or lens summary")
    ap.add_argument("--when", metavar="TEXT", help="role: when to dispatch it · lens: what it must touch")
    ap.add_argument("--target", choices=("proposal", "repo"), default="proposal")
    ap.add_argument("--workspace", metavar="WS")
    ap.add_argument("--out", metavar="DIR", help="proposal folder, or repo root for --target repo")
    ap.add_argument("--force", action="store_true", help="overwrite existing files")
    ap.add_argument("--check", metavar="DIR", help="validate an existing proposal folder only")
    a = ap.parse_args(argv)
    try:
        if a.check:
            return check(a)
        if not a.what or not a.name:
            ap.error("give role|flow|lens <name>, or --check DIR")
        return scaffold(a)
    except ScaffoldError as e:
        print(f"scaffold: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
