#!/usr/bin/env python3
"""Measure how much instruction text Cecilia puts in front of a model — and fail when a budget is broken.

    python tools/tokens.py                 # table
    python tools/tokens.py --json          # machine-readable
    python tools/tokens.py --check         # exit 1 when a budget in tools/token_budget.json is exceeded

What is measured (static — the text the skills tell a model to read, not a live transcript):
  * descriptions — every skill's frontmatter description (the host lists them in every session);
  * mandatory    — per role: SKILL.md plus every file on its **Read first:** line;
  * scenarios    — typical tasks from tools/token_budget.json: the files each role in the chain reads,
                   and how much of that is the same shared file read again by another role.

Tokens are estimated as bytes / 4 (English Markdown); the evals (tools/evals/) record real usage.
Python ≥ 3.9, standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUDGET = ROOT / "tools" / "token_budget.json"
READ_FIRST = re.compile(r"\*\*Read first:\*\*([^\n]*)")
PATHS = re.compile(r"`((?:references|assets|scripts)/[^`\s]+)`")


def tok(n_bytes: int) -> int:
    return round(n_bytes / 4)


def size(p: Path) -> int:
    return p.stat().st_size if p.is_file() else 0


def description(skill: Path) -> str:
    if not (skill / "SKILL.md").is_file():
        return ""
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    m = re.search(r"^description: (.*)$", text, re.M)
    return m.group(1) if m else ""


def mandatory_files(skill: Path) -> list[Path]:
    if not (skill / "SKILL.md").is_file():
        return []
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    files = [skill / "SKILL.md"]
    m = READ_FIRST.search(text)
    if m:
        files += [skill / rel for rel in PATHS.findall(m.group(1))]
    return files


def measure() -> dict:
    skills = sorted(p for p in (ROOT / "skills").iterdir() if p.is_dir() and (p / "SKILL.md").is_file())
    desc = {s.name: len(description(s).encode("utf-8")) for s in skills}
    mand = {}
    for s in skills:
        files = mandatory_files(s)
        mand[s.name] = {"bytes": sum(size(f) for f in files), "files": [f.relative_to(s).as_posix() for f in files]}
    cfg = json.loads(BUDGET.read_text(encoding="utf-8")) if BUDGET.is_file() else {"scenarios": {}, "budgets": {}}
    scen = {}
    exempt = set(cfg.get("reread_exempt", []))
    for name, chain in cfg.get("scenarios", {}).items():
        seen: Counter = Counter()
        total = 0
        per_role = {}
        for role, rels in chain.items():
            files = [ROOT / "skills" / role / r for r in rels]
            missing = [str(f.relative_to(ROOT)) for f in files if not f.is_file()]
            b = sum(size(f) for f in files)
            per_role[role] = {"bytes": b, "missing": missing}
            total += b
            for f in files:
                # the same shared file read by another role: key by name under references/common
                key = f.name if "references/common" in f.as_posix() else f.relative_to(ROOT).as_posix()
                if key in exempt:
                    continue
                seen[(key, size(f))] += 1
        reread = sum(sz * (n - 1) for (key, sz), n in seen.items() if n > 1)
        scen[name] = {"bytes": total, "reread_bytes": reread, "roles": per_role}
    return {"descriptions": desc, "mandatory": mand, "scenarios": scen}


def check(m: dict) -> list[str]:
    cfg = json.loads(BUDGET.read_text(encoding="utf-8"))
    b = cfg.get("budgets", {})
    errors = []
    for name, n in m["descriptions"].items():
        if n > b.get("description_bytes", 10**9):
            errors.append(f"{name}: description {n} B > {b['description_bytes']} B")
    total_desc = sum(m["descriptions"].values())
    if total_desc > b.get("descriptions_total_bytes", 10**9):
        errors.append(f"descriptions total {total_desc} B > {b['descriptions_total_bytes']} B")
    for name, v in m["mandatory"].items():
        if v["bytes"] > b.get("mandatory_bytes", 10**9):
            errors.append(f"{name}: mandatory read {v['bytes']} B > {b['mandatory_bytes']} B")
    for name, v in m["scenarios"].items():
        for role, r in v["roles"].items():
            if r["missing"]:
                errors.append(f"scenario {name}/{role}: missing files {r['missing']}")
        lim = b.get("scenario_bytes", {}).get(name)
        if lim and v["bytes"] > lim:
            errors.append(f"scenario {name}: {v['bytes']} B > {lim} B")
        share = b.get("reread_share_max")
        if share is not None and v["bytes"] and v["reread_bytes"] / v["bytes"] > share:
            errors.append(f"scenario {name}: re-read share {v['reread_bytes'] / v['bytes']:.0%} > {share:.0%}")
    return errors


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    m = measure()
    if a.json:
        print(json.dumps(m, indent=2))
    elif not a.check:
        d = m["descriptions"]
        print(f"descriptions (every session): {sum(d.values())} B ≈ {tok(sum(d.values()))} tok  "
              f"(max {max(d.values())} B, {max(d, key=d.get)})")
        print("mandatory read per role:")
        for name, v in m["mandatory"].items():
            print(f"  {name:22} {v['bytes']:7} B ≈ {tok(v['bytes']):6} tok  {', '.join(v['files'])}")
        for name, v in m["scenarios"].items():
            share = v["reread_bytes"] / v["bytes"] if v["bytes"] else 0
            print(f"scenario {name}: {v['bytes']} B ≈ {tok(v['bytes'])} tok · re-read {share:.0%}")
            for role, r in v["roles"].items():
                print(f"    {role:22} {r['bytes']:7} B ≈ {tok(r['bytes']):6} tok"
                      + (f"  MISSING {r['missing']}" if r["missing"] else ""))
    if a.check:
        errors = check(m)
        for e in errors:
            print("BUDGET:", e)
        if not errors:
            print("token budgets: PASS")
        return 1 if errors else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
