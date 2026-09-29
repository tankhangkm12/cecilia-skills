#!/usr/bin/env python3
"""Build dist/cecilia-v<VERSION>.zip (whole package, VERSION from tools/roster.py) and, with --per-skill, one zip per skill for hosts
that import skills one by one (e.g. claude.ai). Runs validate.py first and refuses to package a FAIL.
Writes CHECKSUMS.json (sha256 per file) into the package root before zipping.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCLUDE_DIRS = {"__pycache__", ".git", "dist", ".pytest_cache", ".venv", "build"}
NAME = "cecilia-skills"             # folder inside the zip = the repository you push
sys.path.insert(0, str(ROOT / "tools"))
from roster import VERSION  # noqa: E402


def files(base: Path):
    for f in sorted(base.rglob("*")):
        if f.is_file() and not (set(f.relative_to(base).parts) & EXCLUDE_DIRS) and f.suffix != ".pyc":
            yield f



def _utf8_console() -> None:
    """Windows consoles default to a legacy code page; keep output readable and crash-free."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

def main() -> int:
    _utf8_console()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--per-skill", action="store_true")
    a = ap.parse_args()
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "validate.py")], capture_output=True, text=True)
    if r.returncode:
        print(r.stdout, r.stderr)
        print("validate.py failed — not packaging")
        return 1
    sums = {f.relative_to(ROOT).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest()
            for f in files(ROOT) if f.name != "CHECKSUMS.json"}
    (ROOT / "CHECKSUMS.json").write_text(json.dumps(sums, indent=1, sort_keys=True) + "\n")
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    out = dist / f"cecilia-v{VERSION}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files(ROOT):
            z.write(f, f"{NAME}/{f.relative_to(ROOT).as_posix()}")
    print("wrote", out.relative_to(ROOT))
    if a.per_skill:
        for s in sorted((ROOT / "skills").iterdir()):
            p = dist / f"{s.name}-v{VERSION}.zip"
            with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
                for f in files(s):
                    z.write(f, f"{s.name}/{f.relative_to(s).as_posix()}")
            print("wrote", p.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
