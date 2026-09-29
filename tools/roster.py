"""The Cecilia roster — v20 compatibility layer over the registry (tools/registry.py, registry/*.json).

The roles themselves live in `registry/roles/<name>.json` (one manifest per role; see registry/README.md and
docs/EXTENDING.md). This module keeps the v19 names that build_adapters.py, validate.py, install.py, setup.py,
guard_corpus.py and the tests import:

  VERSION, ORCHESTRATOR, ORCH_DESC, ROLES (name -> (kind, description), every role except the orchestrator),
  DEFAULT_OFF, DEFAULT_MODELS, all_names(), default_config(), migrate_config(), UI_BROWSERS, UI_STYLES, policy()

kind:
  code    edits code/tests/config/migrations, runs local commands
  docs    writes only its own documents under tensura/
  design  writes its own documents under tensura/ and may use a design-tool MCP (Penpot, Figma)
  read    read-only; returns its report as text
(permissions come from the role's agent type — registry/agent-types/ — plus its overrides)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import registry as _registry  # noqa: E402  — the one registry (tools/registry.py)

VERSION = "20.2.0"

REGISTRY = _registry.load()

ORCHESTRATOR = "cecilia-orchestrator"
ORCH_DESC = REGISTRY["roles"][ORCHESTRATOR]["description"]

# name -> (kind, one-line description for the host agent file); every role except the orchestrator
ROLES: dict = {name: (r["kind"], r["description"]) for name, r in sorted(REGISTRY["roles"].items())
               if name != ORCHESTRATOR}

# Values accepted for ui.browser / ui.style (cecilia_mode.py --show keeps its own copy: it ships alone).
UI_BROWSERS = ("playwright-cli", "playwright-mcp", "none")
UI_STYLES = ("none", "taste", "minimalist", "soft", "brutalist", "redesign")

# Roles that are OFF in a fresh .cecilia/config.json (registry `default_on: false`). Every other role starts ON.
DEFAULT_OFF = {name for name, r in REGISTRY["roles"].items() if not r.get("default_on", True)}

# Model tier per role (registry `model`; orchestrator/references/models.md): where a mistake is found latest, spend more.
DEFAULT_MODELS = {name: r["model"] for name, r in sorted(REGISTRY["roles"].items()) if r.get("model")}

# The order Cecilia reads the test lenses in (DESIGN-V20 §0.4); lenses added later follow, sorted.
TEST_LENS_ORDER = ("functional", "integration", "concurrency-perf", "security", "ui", "database", "infra")


def all_names() -> list:
    """Every skill folder the package must contain, sorted."""
    return sorted([ORCHESTRATOR, *ROLES])


def policy() -> dict:
    """guard/policy.json — the guard's data; default profiles live there (one source)."""
    return json.loads((Path(__file__).resolve().parent.parent / "guard" / "policy.json").read_text(encoding="utf-8"))


def _test_lenses() -> list:
    known = list(REGISTRY["lenses"]["test"])
    return [n for n in TEST_LENS_ORDER if n in known] + sorted(n for n in known if n not in TEST_LENS_ORDER)


def default_config() -> dict:
    names = [ORCHESTRATOR, *ROLES]
    return {
        "roles": {name: name not in DEFAULT_OFF for name in names},
        "flow": "personal",
        "flows": {name: json.loads(json.dumps(f["settings"])) for name, f in sorted(REGISTRY["flows"].items())
                  if f.get("settings")},
        "plan_first": {"fast": False, "standard": True, "controlled": True},
        "docs_layout": "monolith",
        "docs_root": "",
        "ui": {"design_writes": "ask", "browser": "playwright-cli", "style": "none"},
        "git": {"model": "auto", "require_task_branch": True, "local_only": True,
                "protected": ["main", "master", "develop", "trunk", "production", "prod", "release/*"]},
        "profiles": policy()["default_profiles"],
        "tool_rules": [],
        "guard": {},
        "orchestration": {"orchestrator_writes": "tensura-only", "workflow_required_from": "standard", "options": 3},
        "parallel": {"limits": {"dev": None, "test": None, "review": None}, "wave_checkin": "auto"},
        "lanes": _registry.default_lanes(REGISTRY),
        "test": {"lenses": _test_lenses()},
        "review": {"panel": {"from": "standard", "reviewers": {"standard": 3, "controlled": 5},
                             "redteam_in": ["controlled"], "rounds": 2, "judge_model": "strongest",
                             "cross_model": ""}},
        "fix_loop": {"max_rounds": 3, "severities": ["BLOCKER", "SHOULD-FIX"], "on_exhausted": "options"},
        "rules": {"dir": "rules", "enforce": "gate", "max_bytes_per_file": 2048},
        "extensions": {"dir": ".cecilia/extensions"},
        "consensus": {"stages": ["plan", "review", "rootcause", "verdict"], "size": 3, "from_mode": "standard",
                      "models": [], "safety_veto": True, "provenance": "warn"},
        "automation": {"auto_discovery": True, "self_retry": 2},
        "antigravity": {"identity": "transcript", "main_agent": ORCHESTRATOR, "ask": "force_ask", "models": {}},
        "scale": "standard",               # small | standard | large (setup.py proposes one)
        "models": {n: DEFAULT_MODELS[n] for n in names if n in DEFAULT_MODELS},
    }


V19_KEYS = ("docs_root", "profiles", "tool_rules", "guard", "review", "scale")
# v20: added when absent; when present (dict), only the missing sub-keys are added — Cecilia's values stay.
V20_KEYS = ("flow", "flows", "orchestration", "parallel", "lanes", "test", "review", "fix_loop", "rules", "extensions",
            "consensus", "automation", "antigravity")


def _add_missing(cur: dict, base: dict, path: str, changes: list) -> None:
    for key, value in base.items():
        dotted = f"{path}.{key}"
        if key not in cur:
            cur[key] = json.loads(json.dumps(value))
            changes.append((dotted, "(absent)", json.dumps(value)[:70]))
        elif isinstance(cur[key], dict) and isinstance(value, dict):
            _add_missing(cur[key], value, dotted, changes)


def migrate_config(old: dict) -> tuple:
    """v18/v19 -> v20: add what is missing, never change what Cecilia set (a v19 `parallel.max_writers` or an
    integer `review.panel.reviewers` is kept as she wrote it). Returns (new, [(key, before, after)])."""
    new = json.loads(json.dumps(old))
    base = default_config()
    changes = []
    for key in V19_KEYS + tuple(k for k in V20_KEYS if k not in V19_KEYS):
        if key not in new:
            new[key] = json.loads(json.dumps(base[key]))
            changes.append((key, "(absent)", json.dumps(base[key])[:70]))
        elif isinstance(new[key], dict) and isinstance(base[key], dict) and key in V20_KEYS:
            _add_missing(new[key], base[key], key, changes)
    git = new.get("git") if isinstance(new.get("git"), dict) else None
    if git is not None and "local_only" not in git:
        git["local_only"] = True
        changes.append(("git.local_only", "(absent)", "true"))
    roles = new.get("roles") if isinstance(new.get("roles"), dict) else None
    if roles is not None:
        for name in base["roles"]:
            if name not in roles:
                roles[name] = base["roles"][name]
                changes.append((f"roles.{name}", "(absent)", json.dumps(base["roles"][name])))
    models = new.get("models") if isinstance(new.get("models"), dict) else None
    if models is not None and not models:
        new["models"] = base["models"]
        changes.append(("models", "{}", "tier per role (models.md)"))
    elif models is not None:
        for name, tier in base["models"].items():
            if name not in models:
                models[name] = tier
                changes.append((f"models.{name}", "(absent)", json.dumps(tier)))
    return new, changes
