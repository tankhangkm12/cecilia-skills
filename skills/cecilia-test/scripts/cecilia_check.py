#!/usr/bin/env python3
"""cecilia_check — run the repository's own quality checks and record what really happened (common v20).

    python scripts/cecilia_check.py --task SHOP-42              # detect, run, write evidence
    python scripts/cecilia_check.py --task SHOP-42 --plan       # print the commands only
    python scripts/cecilia_check.py --task SHOP-42 --steps test,secrets --base origin/develop

Steps (each skipped when the repository has nothing for it):
  lint · typecheck · build · test   the repo's own scripts/tools (package.json scripts, ruff/pytest/mypy,
                                    mvn/gradle, go, cargo, dotnet) — nothing is installed;
  secrets   gitleaks on the task's commits + staged + untracked files; without gitleaks a built-in scan of
            the changed files for high-confidence patterns (weaker — reported as such);
  deps      when a dependency manifest changed: the added packages, whether they exist on the registry, their
            age and licence, names one edit away from a popular package (typosquats, invented names), known
            vulnerabilities (osv-scanner / npm audit / pip-audit when available);
  size      size of the build output (dist/, build/, .next/, out/, target/) and the change since this task's
            first run;
  rules     (v20, workspace with rules/) every role report of the task carries `Rules: <hash>` equal to the hash
            of its rules files (project + role + flow + lens), and the `cecilia-check` blocks of those rules run:
            forbid_regex over the lines the task added (optionally limited to `paths`), require_command in the
            project;
  flow      (v20, team flow only) branch name vs branch_pattern, commit subjects vs commit_pattern, pr-body.md
            headings vs the PR template's headings, diff size vs max_pr_lines (warning).

Writes tensura/reports/<TASK>/evidence.json (in the Cecilia workspace when there is one) (sha, branch, base, command, exit code, seconds, status, the
failing tail) and prints a summary of at most 15 lines. Reports quote this file instead of re-typing
results; a reviewer can re-run any step. A missing tool is `unverified`, never `pass`.

Exit code: 0 all run steps passed (or were skipped), 1 a step failed, 2 usage error.
Python ≥ 3.9, standard library only. Network is used only to read public registries (deps step).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import hashlib
import re
import shlex
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

VERSION = "20.2.0"
STEPS = ("lint", "typecheck", "build", "test", "secrets", "deps", "size", "rules", "flow")
MANIFESTS = {"package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb", "requirements.txt",
             "requirements-dev.txt", "pyproject.toml", "poetry.lock", "uv.lock", "Pipfile", "Pipfile.lock", "pom.xml",
             "build.gradle", "build.gradle.kts", "go.mod", "go.sum", "Cargo.toml", "Cargo.lock", "Gemfile",
             "Gemfile.lock", "composer.json", "composer.lock"}
BUILD_DIRS = ("dist", "build", ".next", "out", "target", ".output", "storybook-static")
COPYLEFT = re.compile(r"\b(A?GPL|LGPL|SSPL|EUPL|OSL|CC-BY-SA)", re.I)
POPULAR_NPM = """react react-dom next vue nuxt svelte angular express koa fastify nestjs axios lodash underscore moment dayjs
date-fns uuid chalk commander yargs dotenv cors body-parser jsonwebtoken bcrypt bcryptjs mongoose sequelize prisma typeorm
knex pg mysql2 redis ioredis socket.io ws zod yup joi ajv webpack vite rollup esbuild babel typescript eslint prettier jest
vitest mocha chai sinon supertest cypress playwright puppeteer tailwindcss postcss autoprefixer sass styled-components
@emotion/react @mui/material antd bootstrap jquery rxjs redux @reduxjs/toolkit zustand mobx react-router react-router-dom
react-query @tanstack/react-query swr graphql apollo-server @apollo/client node-fetch cross-fetch got superagent formik
react-hook-form classnames clsx framer-motion three d3 chart.js recharts lodash-es ramda immer nanoid bluebird async
debug winston pino morgan helmet multer sharp jimp nodemailer stripe aws-sdk @aws-sdk/client-s3 firebase firebase-admin
@supabase/supabase-js openai langchain cheerio xml2js csv-parse papaparse yaml js-yaml minimist glob rimraf mkdirp
fs-extra concurrently nodemon ts-node tsx husky lint-staged commitlint semver inquirer ora""".split()
POPULAR_PY = """requests numpy pandas django flask fastapi pydantic sqlalchemy alembic celery redis pytest boto3 botocore
urllib3 certifi idna charset-normalizer six python-dateutil pyyaml jinja2 click rich typer httpx aiohttp uvicorn gunicorn
psycopg2 psycopg2-binary pymongo motor scipy scikit-learn matplotlib seaborn tensorflow torch transformers openai
langchain beautifulsoup4 lxml pillow cryptography pyjwt bcrypt passlib marshmallow attrs orjson ujson black ruff mypy
flake8 isort pre-commit tox coverage hypothesis faker tqdm loguru structlog sentry-sdk""".split()
SECRET_RX = [
    ("private key", re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY")),
    ("AWS access key", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}")),
    ("Slack token", re.compile(r"\bxox[abpr]-[A-Za-z0-9-]{10,}")),
    ("Stripe key", re.compile(r"\b(sk|rk)_live_[A-Za-z0-9]{20,}")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("OpenAI/Anthropic key", re.compile(r"\bsk-(proj-|ant-)?[A-Za-z0-9_-]{32,}")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{15,}\.eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}")),
    ("URL with password", re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s:/@'\"]+:[^\s@/'\"]{6,}@[^\s'\"]+", re.I)),
    ("assigned secret", re.compile(r"(?i)\b(api[_-]?key|secret|password|passwd|token|client[_-]?secret)\b\s*[:=]\s*['\"][^'\"\s]{12,}['\"]")),
]


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def which(name: str) -> str | None:
    return shutil.which(name)


def sh(cmd: list[str], cwd: Path, timeout: int, env=None) -> tuple[int, str, float]:
    exe = which(cmd[0]) or cmd[0]
    t0 = time.time()
    try:
        r = subprocess.run([exe, *cmd[1:]], cwd=str(cwd), capture_output=True, text=True, timeout=timeout,
                           env=dict(os.environ, CI="1", FORCE_COLOR="0", NO_COLOR="1", **(env or {})),
                           encoding="utf-8", errors="replace")
        return r.returncode, (r.stdout or "") + (r.stderr or ""), time.time() - t0
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "") if isinstance(e.stdout, str) else ""
        return 124, out + f"\n[timeout after {timeout}s]", time.time() - t0
    except OSError as e:
        return 127, str(e), time.time() - t0


def git(root: Path, *args) -> str:
    code, out, _ = sh(["git", "-C", str(root), "--no-optional-locks", *args], root, 60,
                      env={"GIT_OPTIONAL_LOCKS": "0"})
    return out.strip() if code == 0 else ""


def tail(text: str, n: int = 30) -> str:
    lines = [l for l in text.splitlines() if l.strip()]
    return "\n".join(lines[-n:])


# --------------------------------------------------------------------------- detection

def node_pm(root: Path) -> str:
    if (root / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (root / "yarn.lock").exists():
        return "yarn"
    if (root / "bun.lockb").exists() or (root / "bun.lock").exists():
        return "bun"
    return "npm"


def detect(root: Path) -> dict:
    """{step: [(label, argv)]} for what this repository defines. Nothing is invented."""
    plan: dict = {s: [] for s in ("lint", "typecheck", "build", "test")}
    pj = root / "package.json"
    if pj.is_file():
        try:
            scripts = json.loads(pj.read_text(encoding="utf-8")).get("scripts", {}) or {}
        except ValueError:
            scripts = {}
        pm = node_pm(root)
        run = [pm, "run"] if pm != "yarn" else ["yarn"]
        pick = {"lint": ["lint"], "typecheck": ["typecheck", "type-check", "check-types", "tsc", "types"],
                "build": ["build"], "test": ["test:ci", "test:unit", "test"]}
        for step, names in pick.items():
            for n in names:
                if n in scripts and "watch" not in scripts[n] and not re.search(r"\bdev\b|serve", scripts[n]):
                    plan[step].append((f"{pm} {n}", run + [n]))
                    break
        if not plan["typecheck"] and (root / "tsconfig.json").is_file() and (root / "node_modules/.bin/tsc").exists():
            plan["typecheck"].append(("tsc --noEmit", ["npx", "--no-install", "tsc", "--noEmit"]))
    pyproj = (root / "pyproject.toml").read_text(encoding="utf-8", errors="ignore") if (root / "pyproject.toml").is_file() else ""
    is_py = bool(pyproj) or any((root / f).is_file() for f in ("requirements.txt", "setup.py", "setup.cfg", "Pipfile"))
    if is_py:
        if which("ruff") and ("ruff" in pyproj or (root / "ruff.toml").exists() or (root / ".ruff.toml").exists()):
            plan["lint"].append(("ruff check", ["ruff", "check", "."]))
        elif which("flake8") and ((root / ".flake8").exists() or "flake8" in pyproj):
            plan["lint"].append(("flake8", ["flake8"]))
        if which("mypy") and ("mypy" in pyproj or (root / "mypy.ini").exists()):
            plan["typecheck"].append(("mypy", ["mypy", "."]))
        if any((root / d).is_dir() for d in ("tests", "test")) or "pytest" in pyproj:
            py = which("pytest")
            plan["test"].append(("pytest", ["pytest", "-q"] if py else [sys.executable, "-m", "pytest", "-q"]))
    if (root / "pom.xml").is_file():
        mvn = "./mvnw" if (root / "mvnw").exists() else "mvn"
        plan["build"].append(("mvn verify", [mvn, "-q", "-B", "verify"]))
    elif (root / "build.gradle").is_file() or (root / "build.gradle.kts").is_file():
        gw = "./gradlew" if (root / "gradlew").exists() else "gradle"
        plan["build"].append(("gradle build", [gw, "build", "-q"]))
    if (root / "go.mod").is_file():
        plan["lint"].append(("go vet", ["go", "vet", "./..."]))
        plan["build"].append(("go build", ["go", "build", "./..."]))
        plan["test"].append(("go test", ["go", "test", "./..."]))
    if (root / "Cargo.toml").is_file():
        plan["build"].append(("cargo build", ["cargo", "build", "-q"]))
        plan["test"].append(("cargo test", ["cargo", "test", "-q"]))
    slns = list(root.glob("*.sln"))
    if slns:
        plan["build"].append(("dotnet build", ["dotnet", "build", str(slns[0].name)]))
        plan["test"].append(("dotnet test", ["dotnet", "test", str(slns[0].name)]))
    return plan


def changed_files(root: Path, base: str) -> list[str]:
    files = set()
    if base:
        files.update(git(root, "diff", "--name-only", f"{base}...HEAD").splitlines())
    files.update(git(root, "diff", "--name-only").splitlines())
    files.update(git(root, "diff", "--name-only", "--cached").splitlines())
    files.update(git(root, "ls-files", "--others", "--exclude-standard").splitlines())
    return sorted(f for f in files if f)


def default_base(root: Path) -> str:
    for cand in ("origin/develop", "develop", "origin/main", "main", "origin/master", "master"):
        if git(root, "rev-parse", "--verify", "--quiet", cand):
            mb = git(root, "merge-base", "HEAD", cand)
            if mb:
                return mb
    return ""


# --------------------------------------------------------------------------- secrets

def secrets_step(root: Path, base: str, files: list[str], timeout: int) -> dict:
    if which("gitleaks"):
        out_all, findings, cmds = "", 0, []
        code_help, help_out, _ = sh(["gitleaks", "--help"], root, 30)
        modern = " git " in help_out or "\n  git" in help_out
        runs = []
        if modern:
            if base:
                runs.append(["gitleaks", "git", "--redact", "--no-banner", "--exit-code", "1", "--log-opts", f"{base}..HEAD", "."])
            runs.append(["gitleaks", "git", "--staged", "--redact", "--no-banner", "--exit-code", "1", "."])
        else:
            if base:
                runs.append(["gitleaks", "detect", "--redact", "--no-banner", "--log-opts", f"{base}..HEAD"])
            runs.append(["gitleaks", "protect", "--staged", "--redact", "--no-banner"])
        for argv in runs:
            code, out, _ = sh(argv, root, timeout)
            cmds.append(" ".join(argv))
            out_all += out
            if code == 1:
                findings += max(1, len(re.findall(r"(?im)^\s*(Finding|RuleID):", out)) // 1)
            elif code not in (0, 1):
                return {"status": "unverified", "tool": "gitleaks", "cmd": cmds, "detail": tail(out, 10)}
        untracked = [f for f in git(root, "ls-files", "--others", "--exclude-standard").splitlines() if f]
        extra = builtin_scan(root, untracked)
        n = findings + len(extra)
        return {"status": "fail" if n else "pass", "tool": "gitleaks" + (" + builtin(untracked)" if untracked else ""),
                "cmd": cmds, "findings": n, "files": sorted({f["file"] for f in extra}), "detail": tail(out_all, 15)}
    found = builtin_scan(root, files)
    return {"status": "fail" if found else "unverified", "tool": "builtin (weaker than gitleaks)",
            "findings": len(found), "files": sorted({f["file"] for f in found}),
            "detail": "; ".join(f"{f['file']}:{f['line']} {f['kind']}" for f in found[:10]),
            "note": "gitleaks not installed — the built-in scan covers high-confidence patterns in changed files only. "
                    "Installing gitleaks is A3: quote the install command for Cecilia."}


def builtin_scan(root: Path, files: list[str]) -> list[dict]:
    hits = []
    for rel in files:
        p = root / rel
        if not p.is_file() or p.stat().st_size > 1_000_000 or any(part in {"node_modules", ".git"} for part in p.parts):
            continue
        if re.search(r"\.(png|jpe?g|gif|webp|ico|pdf|zip|gz|woff2?|ttf|lock|min\.js)$", rel, re.I):
            continue
        if re.search(r"(^|/)\.env\.(example|sample|template)$", rel):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for kind, rx in SECRET_RX:
                if rx.search(line) and "example" not in line.lower() and "placeholder" not in line.lower():
                    hits.append({"file": rel, "line": i, "kind": kind})
                    break
    return hits


# --------------------------------------------------------------------------- dependencies

def lev1(a: str, b: str) -> bool:
    """Edit distance exactly 1 (or a swapped pair)."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        return len(diff) == 1 or (len(diff) == 2 and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]])
    s, t = (a, b) if len(a) < len(b) else (b, a)
    for i in range(len(t)):
        if t[:i] + t[i + 1:] == s:
            return True
    return False


def fetch_json(url: str, timeout: int = 10):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "cecilia-check"}), timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def npm_added(root: Path, base: str) -> dict:
    now_pkg = json.loads((root / "package.json").read_text(encoding="utf-8")) if (root / "package.json").is_file() else {}
    old_text = git(root, "show", f"{base}:package.json") if base else ""
    try:
        old_pkg = json.loads(old_text) if old_text else {}
    except ValueError:
        old_pkg = {}
    added = {}
    for sec in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        for name, ver in (now_pkg.get(sec) or {}).items():
            if name not in (old_pkg.get(sec) or {}) and not any(name in (old_pkg.get(s) or {}) for s in
                                                                  ("dependencies", "devDependencies")):
                added[name] = ver
    return added


def py_added(root: Path, base: str) -> dict:
    added = {}
    for f in ("requirements.txt", "requirements-dev.txt"):
        cur = (root / f).read_text(encoding="utf-8", errors="ignore") if (root / f).is_file() else ""
        old = git(root, "show", f"{base}:{f}") if base else ""
        names = lambda t: {re.split(r"[<>=!~\[; ]", l.strip())[0].lower(): l.strip() for l in t.splitlines()  # noqa: E731
                           if l.strip() and not l.strip().startswith(("#", "-"))}
        for n, spec in names(cur).items():
            if n and n not in names(old):
                added[n] = spec
    return added


def deps_step(root: Path, base: str, files: list[str], offline: bool, timeout: int) -> dict:
    touched = [f for f in files if Path(f).name in MANIFESTS]
    if not touched:
        return {"status": "skip", "detail": "no dependency manifest changed"}
    report = {"status": "pass", "manifests": touched, "added": [], "flags": [], "audit": None}
    npm_new = npm_added(root, base) if (root / "package.json").is_file() else {}
    py_new = py_added(root, base)
    for name, spec in npm_new.items():
        item = {"eco": "npm", "name": name, "spec": spec}
        close = [p for p in POPULAR_NPM if lev1(name.lower(), p)]
        if close:
            item["typosquat_of"] = close
            report["flags"].append(f"{name}: one edit away from popular '{close[0]}' — typo or typosquat?")
        if not offline:
            meta = fetch_json(f"https://registry.npmjs.org/{name.replace('/', '%2F')}")
            if meta is None:
                item["registry"] = "unverified"
            elif "error" in meta or "name" not in meta:
                item["registry"] = "NOT FOUND"
                report["flags"].append(f"{name}: not on the npm registry — invented name?")
            else:
                created = (meta.get("time") or {}).get("created", "")
                item["created"] = created[:10]
                item["license"] = (meta.get("license") if isinstance(meta.get("license"), str) else
                                   (meta.get("license") or {}).get("type", "")) or ""
                if created and (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(
                        created.replace("Z", "+00:00"))).days < 90:
                    report["flags"].append(f"{name}: first published {created[:10]} (< 90 days)")
                if COPYLEFT.search(item["license"] or ""):
                    report["flags"].append(f"{name}: licence {item['license']} (copyleft) — Cecilia decides")
                dl = fetch_json(f"https://api.npmjs.org/downloads/point/last-week/{name}")
                if dl and isinstance(dl.get("downloads"), int):
                    item["weekly_downloads"] = dl["downloads"]
                    if dl["downloads"] < 500:
                        report["flags"].append(f"{name}: {dl['downloads']} downloads last week")
        size_dir = root / "node_modules" / name
        if size_dir.is_dir():
            item["installed_kb"] = round(dir_size(size_dir) / 1024)
        report["added"].append(item)
    for name, spec in py_new.items():
        item = {"eco": "pypi", "name": name, "spec": spec}
        close = [p for p in POPULAR_PY if lev1(name, p)]
        if close:
            item["typosquat_of"] = close
            report["flags"].append(f"{name}: one edit away from popular '{close[0]}' — typo or typosquat?")
        if not offline:
            meta = fetch_json(f"https://pypi.org/pypi/{name}/json")
            if meta is None:
                item["registry"] = "NOT FOUND or offline"
                report["flags"].append(f"{name}: not found on PyPI (or offline) — invented name?")
            else:
                info = meta.get("info") or {}
                item["license"] = info.get("license") or ""
                if COPYLEFT.search(item["license"] or ""):
                    report["flags"].append(f"{name}: licence {item['license']} (copyleft) — Cecilia decides")
        report["added"].append(item)
    if which("osv-scanner"):
        code, out, _ = sh(["osv-scanner", "--recursive", "--format", "json", "."], root, timeout)
        vulns = len(re.findall(r'"id":\s*"(GHSA|CVE|PYSEC|OSV)-', out))
        report["audit"] = {"tool": "osv-scanner", "vulnerabilities": vulns, "exit": code}
    elif (root / "package-lock.json").is_file() and which("npm") and not offline:
        code, out, _ = sh(["npm", "audit", "--json", "--omit=dev"], root, timeout)
        try:
            meta = json.loads(out[out.index("{"):]).get("metadata", {}).get("vulnerabilities", {})
        except (ValueError, AttributeError):
            meta = {}
        report["audit"] = {"tool": "npm audit", "high": meta.get("high", 0), "critical": meta.get("critical", 0)}
    elif py_new and which("pip-audit") and not offline:
        code, out, _ = sh(["pip-audit", "-r", "requirements.txt", "-f", "json"], root, timeout)
        report["audit"] = {"tool": "pip-audit", "vulnerabilities": len(re.findall(r'"id":', out)), "exit": code}
    else:
        report["audit"] = {"tool": None, "status": "unverified — no osv-scanner / npm audit / pip-audit available"}
    audit = report["audit"] or {}
    if audit.get("critical") or audit.get("high") or audit.get("vulnerabilities"):
        report["flags"].append(f"known vulnerabilities: {json.dumps({k: v for k, v in audit.items() if k != 'tool'})}")
    if any("NOT FOUND" in f or "typosquat" in f for f in report["flags"]):
        report["status"] = "fail"
    elif report["flags"]:
        report["status"] = "review"
    return report


# --------------------------------------------------------------------------- size

def dir_size(p: Path) -> int:
    total = 0
    for f in p.rglob("*"):
        try:
            if f.is_file():
                total += f.stat().st_size
        except OSError:
            continue
    return total


def size_step(root: Path, previous: dict | None) -> dict:
    sizes = {d: dir_size(root / d) for d in BUILD_DIRS if (root / d).is_dir()}
    if not sizes:
        return {"status": "skip", "detail": "no build output directory"}
    out = {"status": "pass", "bytes": sizes}
    prev = ((previous or {}).get("size") or {}).get("first_bytes") or ((previous or {}).get("size") or {}).get("bytes")
    out["first_bytes"] = prev or sizes
    if prev:
        out["delta_bytes"] = {d: sizes.get(d, 0) - prev.get(d, 0) for d in sizes}
    return out


# --------------------------------------------------------------------------- rules + flow (v20)

def short(name: str) -> str:
    return name[len("cecilia-"):] if name.startswith("cecilia-") else name


def rules_hash(ws: Path, role: str | None, flow: str, lens: str | None) -> str:
    """DESIGN-V20 §3 — the same algorithm as workflow.py and the guard (copied on purpose: this script ships alone)."""
    files = ["rules/_project.md"] + ([f"rules/roles/{short(role)}.md"] if role else []) + \
            [f"rules/flows/{flow}.md"] + ([f"rules/lenses/{lens}.md"] if lens else [])
    h = hashlib.sha256()
    for rel in files:
        p = ws / rel
        if p.is_file():
            h.update(rel.encode() + b"\n" + p.read_bytes() + b"\n")
    return h.hexdigest()[:12]


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def ws_state(home: Path) -> tuple[dict, dict]:
    cfg, reg = read_json(home / ".cecilia" / "config.json"), read_json(home / ".cecilia" / "registry.json")
    return (cfg if isinstance(cfg, dict) else {}), (reg if isinstance(reg, dict) else {})


CORE_SHORTS = ("dev-be", "dev-fe", "db", "test", "review", "devops", "design", "ui", "plan", "discovery", "api-ux",
               "extend", "orchestrator")


def report_role(stem: str, reg: dict) -> tuple[str | None, str | None]:
    """`dev-be`, `dev-be-2`, `test-security`, `review-data-1` -> (cecilia role, lens or None)."""
    shorts = {s: f"cecilia-{s}" for s in CORE_SHORTS}
    shorts.update({short(n): n for n in (reg.get("roles") or {})})
    lenses = {n for k in ("test", "review") for n in ((reg.get("lenses") or {}).get(k) or {})}
    base = re.sub(r"-\d+$", "", stem)
    for key in sorted(shorts, key=len, reverse=True):
        if base == key:
            return shorts[key], None
        if base.startswith(key + "-"):
            rest = base[len(key) + 1:]
            return shorts[key], (rest if rest in lenses else None)
    return None, None


def glob_rx(pattern: str) -> re.Pattern:
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif pattern[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(out + r"\Z")


def in_paths(rel: str, globs) -> bool:
    if not globs:
        return True
    pos = [g for g in globs if not g.startswith("!")]
    neg = [g[1:] for g in globs if g.startswith("!")]
    return (not pos or any(glob_rx(g).match(rel) for g in pos)) and not any(glob_rx(g).match(rel) for g in neg)


def added_lines(root: Path, base: str) -> dict:
    """{file: [(line number, text)]} of what the task added: tracked changes vs base (or HEAD) + untracked files."""
    out: dict = {}
    cur, n = None, 0
    for line in git(root, "diff", "-U0", "--no-color", "--no-ext-diff", base or "HEAD").splitlines():
        if line.startswith("+++ "):
            cur = line[6:] if line.startswith("+++ b/") else None
        elif line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            n = int(m.group(1)) if m else 0
        elif line.startswith("+") and cur:
            out.setdefault(cur, []).append((n, line[1:]))
            n += 1
    for rel in git(root, "ls-files", "--others", "--exclude-standard").splitlines():
        p = root / rel
        try:
            if p.is_file() and p.stat().st_size <= 1_000_000:
                out[rel] = list(enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1))
        except OSError:
            continue
    return out


CHECK_BLOCK = re.compile(r"^```[ \t]*cecilia-check[ \t]*\r?\n(.*?)^```", re.M | re.S)


def rule_checks(path: Path) -> tuple[list, str]:
    try:
        text = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8", errors="replace"), flags=re.S)
    except OSError:
        return [], ""
    checks, err = [], ""
    for m in CHECK_BLOCK.finditer(text):
        try:
            data = json.loads(m.group(1))
            checks += [c for c in data if isinstance(c, dict)] if isinstance(data, list) else []
        except ValueError as e:
            err = f"{path.name}: cecilia-check block is not valid JSON ({e})"
    return checks, err


def rules_step(root: Path, home: Path, task: str, base: str, timeout: int) -> dict:
    if not (home / "rules").is_dir():
        return {"status": "skip", "detail": "no rules/ folder (v19 layout or in-project install)"}
    cfg, reg = ws_state(home)
    flow = cfg.get("flow") if isinstance(cfg.get("flow"), str) and cfg.get("flow") else "personal"
    enforce = ((cfg.get("rules") or {}) if isinstance(cfg.get("rules"), dict) else {}).get("enforce", "gate")
    problems, warnings, ok = [], [], []
    seen: dict = {}                                  # role -> {lens}
    reports = sorted((home / "tensura" / "reports" / task).glob("*.md"))
    for f in reports:
        role, lens = report_role(f.stem, reg)
        if not role:
            continue
        seen.setdefault(role, set()).add(lens)
        want = rules_hash(home, role, flow, lens)
        m = re.search(r"(?im)^[\s>*_`-]*Rules[*_`]*\s*:\s*[*_`]*([0-9a-f]{12})\b",
                      f.read_text(encoding="utf-8", errors="replace"))
        msg = (f"{f.name}: no 'Rules: <hash>' line (want {want})" if not m else
               f"{f.name}: Rules {m.group(1)} != {want} (rules changed or not read)" if m.group(1) != want else "")
        if not msg:
            ok.append(f.name)
        elif enforce != "off":
            (problems if enforce == "gate" else warnings).append(msg)
    run = read_json(home / "tensura" / "tasks" / task / "run.json")
    for a in (run.get("agents") or []) if isinstance(run, dict) else []:
        if isinstance(a, dict) and isinstance(a.get("role"), str):
            lens = a.get("lens") if isinstance(a.get("lens"), str) and a.get("lens") not in {"", "-"} else None
            seen.setdefault(a["role"], set()).add(lens)
    files = [home / "rules" / "_project.md", home / "rules" / "flows" / f"{flow}.md"]
    files += [home / "rules" / "roles" / f"{short(r)}.md" for r in sorted(seen)]
    files += [home / "rules" / "lenses" / f"{ln}.md" for ln in sorted({x for v in seen.values() for x in v if x})]
    checks = []
    for f in files:
        found, err = rule_checks(f)
        checks += [(f.relative_to(home).as_posix(), c) for c in found]
        if err:
            problems.append(err)
    ran = []
    added = added_lines(root, base) if any("forbid_regex" in c for _, c in checks) else {}
    for rel, c in checks:
        cid = str(c.get("id", "?"))
        if "forbid_regex" in c:
            try:
                rx = re.compile(str(c["forbid_regex"]))
            except re.error as e:
                problems.append(f"{cid} ({rel}): forbid_regex does not compile ({e})")
                continue
            hits = [f"{fn}:{n}" for fn, lines in sorted(added.items()) if in_paths(fn, c.get("paths"))
                    for n, text in lines if rx.search(text)]
            ran.append(f"{cid} forbid: {len(hits)} hit(s)")
            if hits:            # locations only — the matching text is never echoed (it may be a secret)
                problems.append(f"{cid} ({rel}): forbidden pattern at " + ", ".join(hits[:5])
                                + (f" … +{len(hits) - 5}" if len(hits) > 5 else ""))
        elif "require_command" in c:
            cmd = str(c["require_command"])
            try:
                argv = shlex.split(cmd, posix=os.name != "nt")
            except ValueError:
                argv = []
            if not argv:
                problems.append(f"{cid} ({rel}): require_command is empty or unparsable")
                continue
            code, out, secs = sh(argv, root, timeout)
            ran.append(f"{cid} `{cmd}` exit {code}")
            if code != 0:
                problems.append(f"{cid} ({rel}): `{cmd}` exited {code}: {tail(out, 3)[:200]}")
    if not reports and not checks and not seen:
        return {"status": "skip", "detail": "no role report and no cecilia-check rule for this task yet", "flow": flow}
    status = "fail" if problems else ("review" if warnings else "pass")
    detail = "; ".join(problems[:3] + warnings[:2]) or f"{len(ok)} report(s) with the current Rules hash, " \
             f"{len(ran)} machine check(s) passed"
    return {"status": status, "flow": flow, "enforce": enforce, "reports_ok": ok, "problems": problems,
            "warnings": warnings, "checks": ran, "detail": detail}


def pattern_rx(pattern: str) -> re.Pattern:
    parts = re.split(r"(\{[^}]+\})", pattern)
    names = {"ticket": r"[A-Za-z0-9][A-Za-z0-9._-]*", "slug": r"[A-Za-z0-9][A-Za-z0-9._-]*"}
    return re.compile("".join(names.get(p[1:-1], r"[^/]+") if p.startswith("{") else re.escape(p) for p in parts))


def headings(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", m.group(1).strip(" #").lower()) for m in re.finditer(r"(?m)^#{1,6}\s+(.+)$", text)]


def flow_step(root: Path, home: Path, task: str, base: str) -> dict:
    cfg, reg = ws_state(home)
    flow = cfg.get("flow") if isinstance(cfg.get("flow"), str) and cfg.get("flow") else "personal"
    if flow != "team":
        return {"status": "skip", "detail": f"flow {flow} — no team checks"}
    settings = dict((((reg.get("flows") or {}).get("team") or {}).get("settings")) or {})
    over = ((cfg.get("flows") or {}) if isinstance(cfg.get("flows"), dict) else {}).get("team")
    settings.update(over if isinstance(over, dict) else {})
    problems, warnings, checked = [], [], []
    branch = git(root, "rev-parse", "--abbrev-ref", "HEAD")
    if settings.get("branch_pattern") and branch:
        checked.append("branch")
        if not pattern_rx(str(settings["branch_pattern"])).fullmatch(branch):
            problems.append(f"branch '{branch}' does not match {settings['branch_pattern']}")
    if settings.get("commit_pattern") and base:
        checked.append("commits")
        try:
            rx = re.compile(str(settings["commit_pattern"]))
        except re.error as e:
            rx = None
            problems.append(f"flows.team.commit_pattern does not compile ({e})")
        subjects = [x for x in git(root, "log", "--format=%s", f"{base}..HEAD").splitlines() if x.strip()]
        bad = [x for x in subjects if rx and not x.startswith("Merge ") and not rx.match(x)]
        if bad:
            problems.append(f"{len(bad)} commit subject(s) not matching commit_pattern, e.g. '{bad[0][:60]}'")
    tpl = root / str(settings.get("pr_template") or "")
    body = home / "tensura" / "reports" / task / "pr-body.md"
    if settings.get("pr_template") and tpl.is_file() and body.is_file():
        checked.append("pr-body")
        want = headings(tpl.read_text(encoding="utf-8", errors="replace"))
        have = set(headings(body.read_text(encoding="utf-8", errors="replace")))
        missing = [h for h in want if h not in have]
        if missing:
            problems.append("pr-body.md misses template heading(s): " + ", ".join(missing[:5]))
    limit = settings.get("max_pr_lines")
    if isinstance(limit, int) and limit > 0 and base:
        checked.append("size")
        stat = git(root, "diff", "--shortstat", base)
        n = sum(int(x) for x in re.findall(r"(\d+) (?:insertion|deletion)", stat))
        if n > limit:
            warnings.append(f"diff is {n} lines > max_pr_lines {limit} — split the PR or tell Cecilia why")
    status = "fail" if problems else ("review" if warnings else "pass")
    return {"status": status, "flow": flow, "checked": checked, "problems": problems, "warnings": warnings,
            "detail": "; ".join(problems[:2] + warnings[:1]) or ("checked " + ", ".join(checked) if checked else
                                                                  "nothing to check yet")}


# --------------------------------------------------------------------------- main

def locate(project_arg: str) -> tuple[Path, Path]:
    """(code root, docs home). Workspace mode: the workspace's config names the project; evidence stays in the
    workspace's tensura/. In-project install: both are the repository."""
    here = Path.cwd().resolve()
    starts = [here, Path(__file__).resolve().parent]
    for start in starts:
        for d in [start, *start.parents]:
            cfg_file = d / ".cecilia" / "config.json"
            if cfg_file.is_file():
                try:
                    proj = (json.loads(cfg_file.read_text(encoding="utf-8-sig")).get("workspace") or {}).get("project")
                except (OSError, ValueError, AttributeError):
                    proj = None
                if isinstance(proj, str) and proj.strip():
                    code = Path(project_arg).resolve() if project_arg else Path(proj)
                    return code, d
                if start == here:
                    code = Path(project_arg).resolve() if project_arg else d
                    return code, d
                break
    code = Path(project_arg or ".").resolve()
    return code, code


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True, help="task id; evidence goes to tensura/reports/<TASK>/evidence.json")
    ap.add_argument("--project", default="", help="repository root (default: the workspace's project, else the "
                                                "folder holding .cecilia/, else the current directory)")
    ap.add_argument("--steps", default=",".join(STEPS), help="comma list of " + ", ".join(STEPS))
    ap.add_argument("--base", default="", help="base ref for 'what changed' (default: merge-base with develop/main)")
    ap.add_argument("--plan", action="store_true", help="print the detected commands; run nothing")
    ap.add_argument("--offline", action="store_true", help="deps step: no registry look-ups")
    ap.add_argument("--timeout", type=int, default=900, help="seconds per command (default 900)")
    ap.add_argument("--out", default="", help="evidence path (default tensura/reports/<TASK>/evidence.json)")
    a = ap.parse_args()
    root, home = locate(a.project)
    steps = [s.strip() for s in a.steps.split(",") if s.strip()]
    bad = [s for s in steps if s not in STEPS]
    if bad or not re.match(r"^[A-Za-z0-9._-]+$", a.task):
        print(f"usage error: unknown steps {bad}" if bad else "usage error: --task must be an id like SHOP-42")
        return 2
    plan = detect(root)
    if a.plan:
        for s in steps:
            if s in plan:
                print(f"{s:9} " + (" | ".join(label + ": " + " ".join(cmd) for label, cmd in plan[s]) or "(nothing defined)"))
            else:
                print(f"{s:9} (built-in step)")
        return 0
    out_file = Path(a.out) if a.out else home / "tensura" / "reports" / a.task / "evidence.json"
    previous = None
    if out_file.is_file():
        try:
            previous = json.loads(out_file.read_text(encoding="utf-8"))
        except ValueError:
            previous = None
    base = a.base or default_base(root)
    files = changed_files(root, base)
    ev = {"tool": "cecilia_check", "version": VERSION, "task": a.task, "started": now(), "project": str(root),
          "sha": git(root, "rev-parse", "HEAD"), "branch": git(root, "rev-parse", "--abbrev-ref", "HEAD"),
          "base": base, "dirty": bool(git(root, "status", "--porcelain")), "changed_files": len(files), "steps": []}
    failed = False
    for s in steps:
        if s in plan:
            if not plan[s]:
                ev["steps"].append({"step": s, "status": "skip", "detail": "nothing defined in this repository"})
                continue
            for label, cmd in plan[s]:
                if not which(cmd[0]) and not cmd[0].startswith("./") and cmd[0] != sys.executable:
                    ev["steps"].append({"step": s, "label": label, "cmd": " ".join(cmd), "status": "unverified",
                                        "detail": f"{cmd[0]} not installed"})
                    continue
                code, out, secs = sh(cmd, root, a.timeout)
                rec = {"step": s, "label": label, "cmd": " ".join(cmd), "exit": code, "seconds": round(secs, 1),
                       "status": "pass" if code == 0 else "fail"}
                if code != 0:
                    rec["tail"] = tail(out)
                    failed = True
                counts = list(dict.fromkeys(f"{n} {w}" for n, w in re.findall(r"(\d+)\s+(passed|failed|skipped|tests?)\b", out)))
                if counts:
                    rec["counts"] = " ".join(counts[-4:])
                ev["steps"].append(rec)
        elif s == "secrets":
            r = secrets_step(root, base, files, a.timeout)
            ev["steps"].append({"step": "secrets", **r})
            failed |= r["status"] == "fail"
        elif s == "deps":
            r = deps_step(root, base, files, a.offline, a.timeout)
            ev["steps"].append({"step": "deps", **r})
            failed |= r["status"] == "fail"
        elif s == "rules":
            r = rules_step(root, home, a.task, base, a.timeout)
            ev["steps"].append({"step": "rules", **r})
            failed |= r["status"] == "fail"
        elif s == "flow":
            r = flow_step(root, home, a.task, base)
            ev["steps"].append({"step": "flow", **r})
            failed |= r["status"] == "fail"
        elif s == "size":
            r = size_step(root, previous)
            ev["size"] = r
            ev["steps"].append({"step": "size", "status": r["status"],
                                "detail": ", ".join(f"{k} {v // 1024} KB" for k, v in (r.get("bytes") or {}).items())
                                + ("" if "delta_bytes" not in r else " · Δ " + ", ".join(
                                    f"{k} {v // 1024:+} KB" for k, v in r["delta_bytes"].items()))})
    ev["finished"] = now()
    ev["result"] = "fail" if failed else "pass"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(ev, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [f"cecilia_check {a.task} @ {ev['sha'][:10] or '?'} ({ev['branch'] or '?'}) → {ev['result'].upper()}"]
    for st in ev["steps"][:12]:
        extra = st.get("counts") or st.get("detail") or ""
        if st["step"] == "deps" and st.get("flags"):
            extra = "; ".join(st["flags"][:2])
        lines.append(f"  {st['step']:9} {st['status']:10} {st.get('cmd', st.get('tool', ''))[:50]}  {str(extra)[:70]}")
    lines.append(f"  evidence: {out_file}")
    print("\n".join(lines[:15]))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
