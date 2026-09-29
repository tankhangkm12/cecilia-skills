#!/usr/bin/env python3
"""Run the guard corpus (tests/corpus/*.jsonl) inside a neutral fixture project and report the rates.

    python tools/guard_corpus.py            # summary + every miss
    python tools/guard_corpus.py --json

adversarial.jsonl  commands the guard must ask about or deny (the wanted decision, or stricter)
benign.jsonl       everyday commands that must pass untouched (0 false positives is the release gate)
out_of_scope.jsonl forms a command-line guard cannot model — listed, not scored (docs/LIMITATIONS.md)

Release gate (docs/RELEASE.md): adversarial ≥ 95 % right direction, push/PR category 100 %, benign 100 %.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "guard"))
sys.path.insert(0, str(ROOT / "tools"))
import cecilia_guard as G  # noqa: E402
import roster as R  # noqa: E402

RANK = {"allow": 0, "ask": 1, "deny": 2}


def build_fixture(base: Path, branch: str = "feature/T1-demo", mode: str = "standard", config: dict | None = None) -> Path:
    """A small repository with the shape of a real project: app code, infra, migrations, a local node_modules/.bin."""
    (base / ".git").mkdir(parents=True, exist_ok=True)
    (base / ".git" / "HEAD").write_text(f"ref: refs/heads/{branch}\n" if branch else "0" * 40 + "\n")
    (base / ".cecilia" / "approvals").mkdir(parents=True, exist_ok=True)
    (base / ".cecilia" / "mode.json").write_text(json.dumps({"mode": mode}))
    (base / ".cecilia" / "config.json").write_text(json.dumps(config or R.default_config(), indent=2))
    files = {
        "src/app.ts": "import React from 'react'\nexport const a = 1\n", "README.md": "# fixture\n",
        ".env.example": "DATABASE_URL=\n", ".env": "DATABASE_URL=postgres://u:p@localhost/db\n",
        "scripts/check.js": "console.log('ok')\n", "scripts/seed_local.py": "print('seed')\n",
        "scripts/deploy.sh": "echo deploy\n", "scripts/deploy.js": "console.log('deploy')\n",
        "scripts/release_notes_check.py": "print('notes')\n", "manage.py": "print('django')\n",
        "Dockerfile": "FROM node:22\n", ".github/workflows/ci.yml": "on: push\n", "charts/api/Chart.yaml": "name: api\n",
        "infra/main.tf": "", "prisma/schema.prisma": "", "prisma/migrations/.keep": "", "package.json": "{}\n",
        "x.sql": "select 1;\n", "evil.json": "{}\n", "server.js": "",
        "rules/_project.md": "# Project rules\n- PR-01: keep it small\n", "rules/roles/dev-be.md": "# dev-be\n",
    }
    for rel, text in files.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    for b in ("eslint", "vite", "tsc", "prisma", "jest", "playwright", "vitest", "knex"):
        p = base / "node_modules" / ".bin" / b
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("#!/bin/sh\n")
    return base


def load(name: str) -> list[dict]:
    f = ROOT / "tests" / "corpus" / name
    return [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]


def run(root: Path | None = None) -> dict:
    root = root or build_fixture(Path(tempfile.mkdtemp()))
    res = {"adversarial": [], "benign": [], "timings_ms": []}
    res.update({"holdout_adversarial": [], "holdout_benign": []})
    for kind in ("adversarial", "benign", "holdout_adversarial", "holdout_benign"):
        if not (ROOT / "tests" / "corpus" / f"{kind}.jsonl").is_file():
            continue
        for case in load(f"{kind}.jsonl"):
            t0 = time.perf_counter()
            d, why = G.decide_command(case["cmd"], root, root / case.get("cwd", "."))
            res["timings_ms"].append((time.perf_counter() - t0) * 1000)
            got = d or "allow"
            want = case["want"]
            ok = got == "allow" if kind.endswith("benign") else RANK[got] >= RANK[want]
            res[kind].append({**case, "got": got, "ok": ok, "reason": why})
    adv, ben = res["adversarial"], res["benign"]
    cats: dict = {}
    for c in adv:
        cats.setdefault(c["category"], [0, 0])
        cats[c["category"]][0] += c["ok"]
        cats[c["category"]][1] += 1
    t = sorted(res["timings_ms"])
    res["summary"] = {
        "adversarial": f"{sum(c['ok'] for c in adv)}/{len(adv)}",
        "adversarial_rate": sum(c["ok"] for c in adv) / len(adv),
        "benign": f"{sum(c['ok'] for c in ben)}/{len(ben)}",
        "benign_rate": sum(c["ok"] for c in ben) / len(ben),
        "by_category": {k: f"{v[0]}/{v[1]}" for k, v in sorted(cats.items())},
        "median_ms": round(t[len(t) // 2], 2), "p95_ms": round(t[int(len(t) * 0.95)], 2),
        "out_of_scope_listed": len(load("out_of_scope.jsonl")),
    }
    for kind in ("holdout_adversarial", "holdout_benign"):
        rows = res[kind]
        if rows:
            res["summary"][kind] = f"{sum(c['ok'] for c in rows)}/{len(rows)}"
            res["summary"][kind + "_rate"] = sum(c["ok"] for c in rows) / len(rows)
    return res


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    res = run()
    if a.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(res["summary"], indent=2, ensure_ascii=False))
        for kind in ("adversarial", "benign"):
            for c in res[kind]:
                if not c["ok"]:
                    print(f"MISS {kind:11} want {c['want']:5} got {c['got']:5}  {c['cmd']}")
    s = res["summary"]
    push = s["by_category"].get("push", "0/1").split("/")
    ok = s["adversarial_rate"] >= 0.95 and s["benign_rate"] == 1.0 and push[0] == push[1]
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
