#!/usr/bin/env python3
"""The Cecilia registry — roles, agent types, flows and lenses as one JSON manifest each (v20).

Layers (SOLID): role = expertise (its skill) · flow = process · agent type = permissions · guard = enforcement ·
adapter = host format. A new role/flow/lens is one manifest under `registry/` plus its guide/skill files; the
host adapters and the tables in `shared/generated/` are generated from here (tools/build_adapters.py).

API (used by roster.py, build_adapters.py, validate.py, install.py, scaffold.py):
    load(root=None, extensions=None) -> dict     merged registry
    validate(reg, root=None) -> list[str]        [] = OK
    compile(reg) -> dict                         snapshot the installer writes to <ws>/.cecilia/registry.json
    short(name) -> str                           "cecilia-dev-be" -> "dev-be"
    default_lanes(reg) -> dict[str, list[str]]

CLI: python tools/registry.py --check [--extensions DIR]   prints errors, exit 1 on any
     python tools/registry.py [--extensions DIR]           prints the compiled snapshot (JSON)
Schema reference: registry/README.md. Stdlib only, Python 3.9+.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

VERSION = "20.2.0"
ROOT = Path(__file__).resolve().parent.parent

STEPS = ("intake", "plan", "approve", "dispatch", "review", "handoff", "finish")
LENS_KINDS = ("test", "review")
KINDS = ("orchestrator", "code", "docs", "design", "read")
WRITES = ("lane", "tensura-only", "none")
NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
# Paths every role may write besides its lane (DESIGN-V20 §1).
IMPLICIT_LANE = ("tensura/reports/<TASK>/**", "tensura/tasks/<TASK>/**", "tensura/backups/<TASK>/**")

# section -> (sub-folder under registry/, lens kind or None)
_SECTIONS = (("agent_types", "agent-types", None), ("roles", "roles", None), ("flows", "flows", None),
             ("lenses", "lenses/test", "test"), ("lenses", "lenses/review", "review"))


def short(name: str) -> str:
    """"cecilia-dev-be" -> "dev-be" (a name without the prefix is returned unchanged)."""
    return name[len("cecilia-"):] if name.startswith("cecilia-") else name


def _empty() -> dict:
    return {"version": VERSION, "agent_types": {}, "roles": {}, "flows": {},
            "lenses": {k: {} for k in LENS_KINDS}}


def _read_dir(home: Path, source: str, reg: dict, errors: list) -> None:
    """Read `<home>/registry/**`; `home` = repo root (core) or the extensions folder."""
    base = home / "registry"
    for section, sub, lens_kind in _SECTIONS:
        folder = base / sub
        if not folder.is_dir():
            continue
        target = reg["lenses"][lens_kind] if lens_kind else reg[section]
        label = sub if lens_kind else section
        for f in sorted(folder.glob("*.json")):
            rel = f"{source}:{sub}/{f.name}"
            try:
                obj = json.loads(f.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError) as e:
                errors.append(f"{rel}: unreadable JSON ({e})")
                continue
            if not isinstance(obj, dict):
                errors.append(f"{rel}: must be a JSON object")
                continue
            name = obj.get("name")
            if name != f.stem:
                errors.append(f"{rel}: name {name!r} must equal the file name {f.stem!r}")
                continue
            if name in target:
                where = target[name].get("_source", "core")
                errors.append(f"{rel}: {label} {name!r} collides with the {where} registry")
                continue
            obj["_source"] = source
            obj["_base"] = str(home)
            target[name] = obj


def load(root: Path | None = None, extensions: Path | None = None) -> dict:
    """Merged registry. `root` = repo (or installed data) root holding `registry/`; `extensions` =
    `<ws>/.cecilia/extensions` (manifests in `registry/`, skills in `skills/<name>/`). Problems found while
    reading (bad JSON, name/file mismatch, collisions with the core registry) land in reg["errors"] and are
    reported by validate()."""
    root = Path(root) if root else ROOT
    reg = _empty()
    errors: list = []
    if not (root / "registry").is_dir():
        errors.append(f"{root / 'registry'}: registry folder missing")
    _read_dir(root, "core", reg, errors)
    if extensions is not None:
        ext = Path(extensions)
        if ext.exists() and not ext.is_dir():
            errors.append(f"{ext}: extensions path is not a folder")
        else:
            _read_dir(ext, "extension", reg, errors)
    reg["errors"] = errors
    reg["_root"] = str(root)
    return reg


# ---------------------------------------------------------------- validation

def _is_str_list(v) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) and x for x in v)


def _check_keys(obj: dict, spec: dict, where: str, errs: list) -> None:
    for key, types in spec.items():
        if key not in obj:
            errs.append(f"{where}: missing key {key!r}")
        elif not isinstance(obj[key], types):
            names = "/".join(t.__name__ if t is not type(None) else "null" for t in
                             (types if isinstance(types, tuple) else (types,)))
            errs.append(f"{where}: {key!r} must be {names}")


def _tools_ok(v) -> bool:
    return v is None or v == "inherit" or _is_str_list(v) or v == []


def _guide_path(item: dict, rel: str, root: Path) -> Path:
    """Guides of extension items resolve inside the extension folder first, then the repo."""
    rel = rel.split("#", 1)[0]
    if item.get("_source") == "extension":
        p = Path(item["_base"]) / rel
        if p.exists():
            return p
    return root / rel


def _skill_file(role: dict, root: Path) -> Path:
    if role.get("_source") == "extension":
        return Path(role["_base"]) / "skills" / role["name"] / "SKILL.md"
    return root / "skills" / role["name"] / "SKILL.md"


def validate(reg: dict, root: Path | None = None) -> list[str]:
    """Schema + references: agent types exist, skill folders, review guides, flow guide sections, lens guides.
    Returns error strings; [] = OK."""
    root = Path(root) if root else Path(reg.get("_root") or ROOT)
    errs = list(reg.get("errors", []))

    for name, at in sorted(reg.get("agent_types", {}).items()):
        w = f"agent-types/{name}"
        _check_keys(at, {"name": str, "summary": str, "writes": str, "may_dispatch": bool, "main_thread": bool,
                         "claude": dict, "antigravity": dict}, w, errs)
        if at.get("writes") not in WRITES:
            errs.append(f"{w}: writes must be one of {', '.join(WRITES)}")
        cl, ag = at.get("claude") or {}, at.get("antigravity") or {}
        if isinstance(cl, dict):
            if cl.get("tools") is None or not _tools_ok(cl.get("tools")):
                errs.append(f"{w}: claude.tools must be a list of tool names or \"inherit\"")
            if not isinstance(cl.get("disallowedTools"), list) or not all(isinstance(t, str) for t in cl["disallowedTools"]):
                errs.append(f"{w}: claude.disallowedTools must be a list")
        if isinstance(ag, dict):
            if not _is_str_list(ag.get("tools")):
                errs.append(f"{w}: antigravity.tools must be a list of tool names")
            if "commandExecutionPolicy" in ag and not isinstance(ag["commandExecutionPolicy"], str):
                errs.append(f"{w}: antigravity.commandExecutionPolicy must be a string")
    mains = [n for n, at in reg.get("agent_types", {}).items() if at.get("main_thread") is True]
    if len(mains) > 1:
        errs.append(f"agent-types: only one agent type may be main_thread, got {mains}")

    review_dir = root / "skills" / "cecilia-review"
    for name, r in sorted(reg.get("roles", {}).items()):
        w = f"roles/{name}"
        _check_keys(r, {"name": str, "agent_type": str, "kind": str, "description": str, "default_on": bool,
                        "model": str, "consumes": list, "produces": list, "lane": list, "report": str,
                        "review_guide": list, "rules_slot": str, "lenses": (str, type(None)), "overrides": dict},
                    w, errs)
        if not NAME_RE.match(name):
            errs.append(f"{w}: name must be lower-kebab-case")
        if r.get("agent_type") not in reg.get("agent_types", {}):
            errs.append(f"{w}: unknown agent_type {r.get('agent_type')!r}")
        if r.get("kind") not in KINDS:
            errs.append(f"{w}: kind must be one of {', '.join(KINDS)}")
        desc = r.get("description")
        if isinstance(desc, str) and (not desc.strip() or "\n" in desc or ": " in desc):
            errs.append(f"{w}: description must be one non-empty line without ': '")
        if isinstance(r.get("model"), str) and not r["model"].strip():
            errs.append(f"{w}: model must not be empty")
        for key in ("consumes", "produces", "review_guide"):
            if isinstance(r.get(key), list) and not all(isinstance(x, str) and x for x in r[key]):
                errs.append(f"{w}: {key} must be a list of strings")
        if isinstance(r.get("lane"), list) and not all(isinstance(g, str) and g.strip("!") for g in r["lane"]):
            errs.append(f"{w}: lane globs must be non-empty strings")
        if r.get("rules_slot") != f"rules/roles/{short(name)}.md":
            errs.append(f"{w}: rules_slot must be rules/roles/{short(name)}.md")
        if r.get("lenses") not in (None,) + LENS_KINDS:
            errs.append(f"{w}: lenses must be null, \"test\" or \"review\"")
        ov = r.get("overrides")
        if isinstance(ov, dict):
            for host, keys in (("claude", ("tools", "disallowedTools")), ("antigravity", ("tools",))):
                h = ov.get(host, {})
                if not isinstance(h, dict):
                    errs.append(f"{w}: overrides.{host} must be an object")
                    continue
                for k in keys:
                    v = h.get(k)
                    ok = _tools_ok(v) if k == "tools" else (v is None or isinstance(v, list))
                    if not ok:
                        errs.append(f"{w}: overrides.{host}.{k} must be null, \"inherit\" or a list")
        if not _skill_file(r, root).is_file():
            errs.append(f"{w}: skill {_skill_file(r, root)} missing")
        for g in r.get("review_guide") or []:
            if not isinstance(g, str):
                continue
            rel = g.split("#", 1)[0]
            candidates = [Path(os.path.normpath(review_dir / rel))]
            if r.get("_source") == "extension":
                # an extension role may ship its own guide next to its skill: ../cecilia-<x>/references/…
                candidates.insert(0, Path(os.path.normpath(Path(r["_base"]) / "skills" / "cecilia-review" / rel)))
            if not any(c.is_file() for c in candidates):
                errs.append(f"{w}: review guide skills/cecilia-review/{g} missing")

    for name, fl in sorted(reg.get("flows", {}).items()):
        w = f"flows/{name}"
        _check_keys(fl, {"name": str, "summary": str, "rules_slot": str, "guide": str, "steps": list,
                         "settings": dict}, w, errs)
        if fl.get("rules_slot") != f"rules/flows/{name}.md":
            errs.append(f"{w}: rules_slot must be rules/flows/{name}.md")
        steps = fl.get("steps") if isinstance(fl.get("steps"), list) else []
        missing = [s for s in STEPS if s not in steps]
        if missing:
            errs.append(f"{w}: steps must declare all of {', '.join(STEPS)} (missing {', '.join(missing)})")
        if isinstance(fl.get("guide"), str):
            gp = _guide_path(fl, fl["guide"], root)
            if not gp.is_file():
                errs.append(f"{w}: guide {fl['guide']} missing")
            else:
                heads = {m.group(1).strip() for m in
                         re.finditer(r"^##\s+(.+?)\s*$", gp.read_text(encoding="utf-8"), re.M)}
                for s in steps:
                    if isinstance(s, str) and s not in heads:
                        errs.append(f"{w}: guide {fl['guide']} has no '## {s}' section")

    for kind in LENS_KINDS:
        for name, ln in sorted(reg.get("lenses", {}).get(kind, {}).items()):
            w = f"lenses/{kind}/{name}"
            _check_keys(ln, {"name": str, "kind": str, "summary": str, "guide": str, "when": str,
                             "rules_slot": str}, w, errs)
            if ln.get("kind") != kind:
                errs.append(f"{w}: kind must be {kind!r} (its folder)")
            if ln.get("rules_slot") != f"rules/lenses/{name}.md":
                errs.append(f"{w}: rules_slot must be rules/lenses/{name}.md")
            if isinstance(ln.get("guide"), str) and not _guide_path(ln, ln["guide"], root).is_file():
                errs.append(f"{w}: guide {ln['guide'].split('#', 1)[0]} missing")
    return errs


# ---------------------------------------------------------------- derived views

def default_lanes(reg: dict) -> dict:
    """role -> lane globs (config `lanes`; Cecilia may narrow them)."""
    return {name: list(r.get("lane") or []) for name, r in sorted(reg.get("roles", {}).items())}


def _public(obj):
    if isinstance(obj, dict):
        return {k: _public(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [_public(v) for v in obj]
    return obj


def compile(reg: dict) -> dict:   # noqa: A001 — name fixed by DESIGN-V20 §1
    """Deterministic JSON snapshot for <ws>/.cecilia/registry.json (read by the guard, workflow.py and
    cecilia_check.py). Each role also carries its agent type's `writes` and `may_dispatch`."""
    roles = {}
    for name, r in sorted(reg.get("roles", {}).items()):
        at = reg.get("agent_types", {}).get(r.get("agent_type"), {})
        role = _public(r)
        role["writes"] = at.get("writes")
        role["may_dispatch"] = bool(at.get("may_dispatch"))
        role["source"] = r.get("_source", "core")
        roles[name] = role
    return {
        "version": reg.get("version", VERSION),
        "steps": list(STEPS),
        "implicit_lane": list(IMPLICIT_LANE),
        "agent_types": _public(dict(sorted(reg.get("agent_types", {}).items()))),
        "roles": roles,
        "flows": _public(dict(sorted(reg.get("flows", {}).items()))),
        "lenses": {k: _public(dict(sorted(reg.get("lenses", {}).get(k, {}).items()))) for k in LENS_KINDS},
        "lanes": default_lanes(reg),
        "extensions": sorted(n for sec in ("agent_types", "roles", "flows") for n, v in reg.get(sec, {}).items()
                             if v.get("_source") == "extension")
                      + sorted(f"lens:{k}/{n}" for k in LENS_KINDS for n, v in reg.get("lenses", {}).get(k, {}).items()
                               if v.get("_source") == "extension"),
    }


def _utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv=None) -> int:
    _utf8_console()
    ap = argparse.ArgumentParser(description="Check or print the Cecilia registry.")
    ap.add_argument("--check", action="store_true", help="validate; print errors, exit 1 on any")
    ap.add_argument("--extensions", type=Path, default=None,
                    help="workspace extensions folder (<ws>/.cecilia/extensions)")
    ap.add_argument("--root", type=Path, default=None, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    reg = load(a.root, a.extensions)
    if a.check:
        errs = validate(reg, a.root)
        for e in errs:
            print(e)
        n = {k: len(reg[k]) for k in ("agent_types", "roles", "flows")}
        n.update({f"{k} lenses": len(v) for k, v in reg["lenses"].items()})
        print(("FAIL" if errs else "PASS") + f" — {len(errs)} error(s); " + ", ".join(f"{v} {k}" for k, v in n.items()))
        return 1 if errs else 0
    print(json.dumps(compile(reg), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
