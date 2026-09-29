#!/usr/bin/env python3
"""Generate every host adapter and the registry tables from one registry, so Claude Code and Antigravity cannot drift.

Reads registry/ (tools/registry.py): a role's permissions = its agent type's tools + the role's `overrides`;
its body text follows its `kind`. Writes adapters/claude-code/**, adapters/antigravity/** and
shared/generated/{roster,lenses,flows}.md. Run after changing anything under registry/; validate.py checks the
generated files are current (`--check`).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(Path(__file__).resolve().parent))
import registry as REG  # noqa: E402  — the one registry (tools/registry.py)
from roster import ORCHESTRATOR, ROLES, ORCH_DESC  # noqa: E402,F401  — compatibility names over the registry

BODY_COMMON = """Follow the preloaded `{name}` skill (v20) and its `references/common/core-min.md` exactly (open `core.md` for CONTROLLED work, gates or config). If the skill is not preloaded, read `{skills_dir}/{name}/SKILL.md` and the references it
names before anything else; if it is missing, return `STATUS: BLOCKED`.

Read `.cecilia/config.json` when present. If `roles.{name}` is false, do nothing and return
`STATUS: BLOCKED — {name} is disabled in .cecilia/config.json`. Decisions come as researched options
(`decisions.md`), numbers are computed (`numbers.md`, `scripts/capacity.py`). End every report with the
Rollback block (`git.md` §5) and a `Deviations:` line — `none`, or each place you did something other
than Cecilia's instruction or the docs, and why. Write the full report to `tensura/reports/<TASK>/<role>.md`
(when your kind can write) and return at most 15 lines: status, files changed, checks with numbers, rollback,
pending decisions, report path, Deviations. Update `tensura/tasks/<TASK>/state.md` at every stop.

Project rules come first: read `rules/_project.md`, `rules/roles/{short}.md`, the active flow's
`rules/flows/<flow>.md` and your lens's `rules/lenses/<lens>.md` (workspace root; your brief embeds them under
`## Rules (must follow)`) before the first step. They only tighten; A3/A4 safety still wins. Write only inside
your lane (`.cecilia/config.json` → `lanes.{name}`) plus `tensura/reports|tasks|backups/<TASK>/`; for anything
else stop and end the report with `HANDOFF: needs <role> — <what>`. The report also ends with
`Rules: <hash> (PR-ids applied)`.

Local-only: nothing you do leaves this machine. Never push, open or edit a PR/MR, comment on a host, create a
remote branch or tag, or change remotes — the guard denies it. Put the exact commands (push through
`cecilia push …`, `gh pr create --draft … --body-file tensura/reports/<TASK>/pr-body.md`) in
your report for Cecilia to run herself.

You cannot reach Cecilia. Do everything possible up to your next gate, then return the block your
brief asks for: questions sorted (independent / dependent) with options and a recommendation, and
every A3 action you need as a full action quote. Never run an A3 action yourself and never attempt an
A4 action. A guard or permission refusal is the system working: report it, do not retry another way.
"""
BODY_READ = """
You are read-only by construction: no edit, shell or delegation tools. Return your report as text for
the orchestrator or Cecilia to store. Scanners and builds, if needed, are run by another role or by
Cecilia in an approved sandbox and handed to you as evidence.
"""
BODY_CODE = """
Read `.cecilia/mode.json` when present. Before the first edit: task branch and start SHA (`git.md` §2),
backup of anything git does not hold (`git.md` §4) — in the worktree and branch your brief names. In
FAST/STANDARD, Cecilia's clear task authorizes local edits reasonably necessary for that task; if
`plan_first` is on for the mode, return your short plan and stop before the first edit until Cecilia
says OK. Write small, clean code (`code-quality.md`); commit per step. In CONTROLLED, confirm an
active scope exists and stay inside its `write` list. A3/A4 boundaries never change with mode. Before
calling the work done, run `scripts/cecilia_check.py --task <TASK>` and quote its summary line. Follow every
`tool_rules` entry in `.cecilia/config.json` (e.g. look up library docs before adding imports).
Documents and reports go to `tensura/` in the main checkout by the absolute path in your brief.
"""
BODY_DOCS = """
You write only your own documents under `tensura/`. You never edit code, config or infrastructure.
"""
BODY_DESIGN = """
You write only your own documents under `tensura/` (and exported design images under the app's
`ui-exports/`). You never edit code, config or infrastructure. Writing to a design tool (Penpot, Figma)
goes through the guard: when `.cecilia/config.json` sets `ui.design_writes` to "ask", every write is A3.
"""
BODY_ORCH = """You are Cecilia's coordinator for the cecilia v20 skill set, running as her main thread.
You only orchestrate: you write only under the workspace `tensura/` and never do specialist work — code,
tests, reviews, designs, migrations — not even in FAST (FAST = dispatch one role with a 3-line brief, no
workflow file). Scale the workflow to FAST / STANDARD / CONTROLLED and dispatch only roles that add value.
From STANDARD, propose 2–3 workflow options (agents per kind, how work is split, test/review lenses, projected
time and tokens) with `scripts/workflow.py options`; Cecilia chooses (`workflow.py choose`) and only then are
writers dispatched, each with the brief `workflow.py brief` prints (first line `[cecilia-brief …]`).
Read `.cecilia/config.json` first: plan only with roles set to true, follow the active `flow`, and tell
Cecilia when a step she needs belongs to a disabled role instead of skipping it silently. Launch every
member of a wave in the same turn (as many as the chosen option sets — several instances of one role on
disjoint units or lenses; the host's own limit still applies), each in its own worktree and branch with its
own ports and database (`parallel.md`), then integrate and test together. From STANDARD the review is a
panel of lenses; run the fix loop (at most `fix_loop.max_rounds` rounds) on what the judge accepted.
Follow the preloaded `cecilia-orchestrator` skill exactly (if not preloaded, read
`{skills_dir}/cecilia-orchestrator/SKILL.md` first).

Never do a role's work yourself. Dispatch only the cecilia role agents, each with a filled brief (mode, scope,
branch, allowed A3, files to read, report path); read their reports from `tensura/reports/<TASK>/` instead of
asking them to repeat. Dispatch `cecilia-api-ux` after an API contract is drafted and after backend work that
changes an API, when the role is on. A `HANDOFF: needs <role>` line in a report is your next dispatch. Stop
after every wave unless Cecilia chose `auto` for this run. Relay every question as a grouped gate and every
action quote verbatim; never approve, push, open a PR, merge, apply or release on her behalf (local-only).
Only Cecilia runs `cecilia mode`, `cecilia approve`, `cecilia push`, `cecilia flow`, `cecilia rules`,
`cecilia extension apply` (or the `.cecilia/bin` tools behind them), and only she edits `rules/`.
"""

BODY_BROWSER = """
UI work is checked in a real browser before it is called done (`visual-check.md`): the tool
`.cecilia/config.json` → `ui.browser` names (default `playwright-cli`), your own session `-s=<member>`,
local pages only; installing the CLI or a browser is A3 — return the quote, never install it yourself.
"""

# Roles that open the running app in a browser: may use a Playwright MCP server named `playwright`.
BROWSER_ROLES = {"cecilia-dev-fe", "cecilia-test"}

BODIES = {"code": BODY_CODE, "docs": BODY_DOCS, "design": BODY_DESIGN, "read": BODY_READ}


def registry() -> dict:
    reg = REG.load(ROOT)
    return reg


def claude_perms(reg: dict, role: dict):
    """(tools list or None = inherit the session's tools, disallowed list) — agent type, then role overrides."""
    at = reg["agent_types"][role["agent_type"]]["claude"]
    ov = (role.get("overrides") or {}).get("claude") or {}
    tools = ov.get("tools") if ov.get("tools") is not None else at.get("tools")
    deny = ov.get("disallowedTools") if ov.get("disallowedTools") is not None else at.get("disallowedTools")
    return (None if tools in (None, "inherit") else list(tools)), list(deny or [])


def antigravity_perms(reg: dict, role: dict):
    """(tools, commandExecutionPolicy or None). The policy is written only when the agent can run commands.
    20.2: `overrides.antigravity.extra_tools` appends to the agent type's (or the overridden) list — e.g.
    `call_mcp_tool` for the roles that reach clusters/databases/browsers through MCP (tools are an allow-list)."""
    at = reg["agent_types"][role["agent_type"]]["antigravity"]
    ov = (role.get("overrides") or {}).get("antigravity") or {}
    tools = list(ov["tools"] if ov.get("tools") is not None else at["tools"])
    extra = ov.get("extra_tools")
    for t in (extra if isinstance(extra, list) else []):
        if isinstance(t, str) and t and t not in tools:
            tools.append(t)
    policy = ov.get("commandExecutionPolicy") or at.get("commandExecutionPolicy") or "sandbox"
    return tools, (policy if "run_command" in tools else None)


AG_MODELS = ("inherit", "flash", "pro")


def antigravity_model(reg: dict, role: dict) -> str:
    """Antigravity `model:` for a role — role override, then agent type, else `inherit` (20.2: orchestrator, plan and
    review run on `pro`, everything else inherits the session's model). The installer may override per workspace
    (`.cecilia/config.json` → `antigravity.models`)."""
    at = reg["agent_types"][role["agent_type"]].get("antigravity") or {}
    ov = (role.get("overrides") or {}).get("antigravity") or {}
    m = ov.get("model") or at.get("model") or "inherit"
    return m if isinstance(m, str) and m.strip() else "inherit"


# 20.2: every tool the guard judges on Antigravity. MCP calls arrive as `call_mcp_tool`, dispatches as
# invoke_subagent/define_subagent; read-only tools (view_file, list_dir, …) stay out so they stay fast.
AG_GUARDED_TOOLS = ("run_command", "write_to_file", "replace_file_content", "multi_replace_file_content",
                    "call_mcp_tool", "invoke_subagent", "define_subagent")
AG_MATCHER = "|".join(AG_GUARDED_TOOLS)


def dispatchable(reg: dict) -> list:
    return [n for n in sorted(reg["roles"]) if not reg["agent_types"][reg["roles"][n]["agent_type"]].get("may_dispatch")]


def body_for(name: str, role: dict, skills_dir: str) -> str:
    body = BODY_COMMON.format(name=name, short=REG.short(name), skills_dir=skills_dir) + BODIES[role["kind"]]
    if name in BROWSER_ROLES:
        body += BODY_BROWSER
    return body


def yaml_list(items, indent="  "):
    return "\n".join(f"{indent}- {i}" for i in items)


def claude_files(reg: dict):
    out = {}
    for name, role in sorted(reg["roles"].items()):
        at = reg["agent_types"][role["agent_type"]]
        tools, deny = claude_perms(reg, role)
        if at.get("may_dispatch"):
            tools = [f"Agent({', '.join(dispatchable(reg))})"] + (tools or [])
            body = BODY_ORCH.format(skills_dir=".claude/skills")
        else:
            body = body_for(name, role, ".claude/skills")
        tools_line = f"tools: {', '.join(tools)}\n" if tools else ""
        deny_line = f"disallowedTools: {', '.join(deny)}\n" if deny else ""
        out[f"adapters/claude-code/agents/{name}.md"] = (
            f"---\nname: {name}\ndescription: {role['description']}\n{tools_line}{deny_line}"
            f"model: inherit\nskills:\n  - {name}\n---\n\n{body}")
    mains = [n for n, r in sorted(reg["roles"].items()) if reg["agent_types"][r["agent_type"]].get("main_thread")]
    settings = {
        # v20: the orchestrator is the session's main thread (it only orchestrates; the guard keeps it in tensura/).
        "agent": mains[0] if mains else ORCHESTRATOR,
        "permissions": {
            "defaultMode": "default",
            "allow": [
                "Bash(git status *)", "Bash(git diff *)", "Bash(git log *)", "Bash(git show *)",
                "Bash(git branch --show-current)", "Bash(git rev-parse *)", "Bash(git fetch *)",
                "Bash(ls *)", "Bash(pwd)",
            ],
            "ask": [
                "Bash(git push *)", "Bash(gh pr create *)", "Bash(gh pr edit *)", "Bash(gh pr comment *)",
                "Bash(gh pr ready *)", "Bash(glab mr create *)", "Bash(npm install *)", "Bash(pnpm add *)",
                "Bash(yarn add *)", "Bash(pip install *)", "Bash(kubectl *)", "Bash(helm *)",
                "Bash(terraform apply *)", "Bash(terraform plan *)", "Bash(rm *)", "Bash(npx skills *)",
                "Bash(playwright-cli install*)", "Bash(npx playwright install*)",
            ],
            "deny": [
                "Bash(gh pr merge *)", "Bash(glab mr merge *)", "Bash(git push --force *)", "Bash(git push -f *)",
                "Bash(npm publish *)", "Bash(gh release *)", "Bash(gh secret *)", "Bash(terraform destroy *)",
                "Read(**/.env)", "Read(**/.env.local)", "Read(**/.env.*.local)", "Read(**/.env.production)",
                "Read(**/.env.prod)", "Read(**/.env.staging)", "Read(**/.env.development)", "Read(**/.env.test)",
                "Read(**/*.pem)", "Read(**/*.key)", "Read(**/id_rsa*)", "Read(**/id_ed25519*)",
                "Read(**/*.p12)", "Read(**/*.pfx)", "Read(**/credentials.json)", "Read(**/secrets.yaml)",
                "Read(**/secrets.yml)", "Read(**/secrets.json)", "Read(**/.npmrc)", "Read(**/.pypirc)", "Read(**/.netrc)",
                "Edit(/.cecilia/**)", "Edit(/.claude/settings.json)", "Edit(/.claude/settings.local.json)",
                "Edit(/.claude/hooks/**)", "Edit(/.claude/agents/**)", "Edit(/.claude/skills/**)",
                "Edit(/.mcp.json)", "Edit(/.playwright/cli.config.json)",
            ],
        },
        "hooks": {
            "PreToolUse": [{
                # v20: Agent|Task too — the guard's workflow gate judges every dispatch of a writer/tester role.
                "matcher": "Bash|PowerShell|Edit|Write|MultiEdit|NotebookEdit|Agent|Task|mcp__.*",
                # Exec form (no shell): the same on Git Bash, PowerShell and POSIX, no quoting of paths with
                # spaces. install.py replaces the placeholders with the absolute Python and guard paths.
                "hooks": [{"type": "command", "command": "__CECILIA_PYTHON__",
                           "args": ["__CECILIA_GUARD__", "--host", "claude"], "timeout": 30}],
            }],
            # Reminds the model of the project's tool rules each turn (prints nothing when there are none).
            "UserPromptSubmit": [{
                "hooks": [{"type": "command", "command": "__CECILIA_PYTHON__",
                           "args": ["__CECILIA_GUARD__", "--host", "claude"], "timeout": 10}],
            }],
        },
    }
    perms = settings["permissions"]
    for key in ("ask", "deny"):   # Claude Code's PowerShell tool gets the same command rules as Bash
        perms[key] += [r.replace("Bash(", "PowerShell(", 1) for r in perms[key] if r.startswith("Bash(")]
    out["adapters/claude-code/settings.cecilia.json"] = json.dumps(settings, indent=2) + "\n"
    return out


def toml_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def antigravity_files(reg: dict):
    out = {}
    for name, role in sorted(reg["roles"].items()):
        at = reg["agent_types"][role["agent_type"]]
        tools, policy = antigravity_perms(reg, role)
        main = bool(at.get("main_thread"))
        body = BODY_ORCH.format(skills_dir="skills") if at.get("may_dispatch") else body_for(name, role, "skills")
        out[f"adapters/antigravity/agents/{name}/agent.md"] = (
            f"---\nname: {name}\ndescription: {role['description']}\ntools:\n{yaml_list(tools)}\n"
            f"mainAgent: {'true' if main else 'false'}\nsubagent: {'false' if main else 'true'}\n"
            f"model: {antigravity_model(reg, role)}\n"
            + (f"commandExecutionPolicy: \"{policy}\"\n" if policy else "")
            + f"skills:\n  - skills/{name}\n---\n\n# {name}\n\n{body}")
    handler = {"type": "command", "command": "__CECILIA_GUARD_COMMAND__", "timeout": 30}
    # One guard command for both events: it tells them apart by the payload (toolCall present = PreToolUse;
    # invocationNum without toolCall = PreInvocation, which injects the role's reminder). No Stop group (some agy
    # versions reject it). install.py replaces the placeholder in every handler.
    hooks = {"cecilia-guard": {
        "PreToolUse": [{"matcher": AG_MATCHER, "hooks": [dict(handler)]}],
        "PreInvocation": [{"hooks": [dict(handler, timeout=10)]}],
    }}
    out["adapters/antigravity/hooks.json"] = json.dumps(hooks, indent=2) + "\n"
    return out


# ---------------------------------------------------------------- shared/generated/*.md

GEN_HEAD = ("<!-- Generated by tools/build_adapters.py from registry/ — do not edit; change the manifest and "
            "re-run. -->\n\n")


def cell(v) -> str:
    if v is None or v == [] or v == "":
        return "—"
    if isinstance(v, list):
        return " ".join(f"`{x}`" for x in v).replace("|", "\\|")
    return str(v).replace("|", "\\|").replace("\n", " ")


def code(v) -> str:
    return "—" if not v else f"`{v}`".replace("|", "\\|")


def roster_md(reg: dict) -> str:
    lines = [f"# Roster (v{REG.VERSION}) — roles, agent types, lanes", "", GEN_HEAD.strip(), "",
             "Lanes: `tensura/…` globs are workspace-relative, all others project-relative, `!` excludes. Every role "
             "may also write " + ", ".join(f"`{p}`" for p in REG.IMPLICIT_LANE) + ". Cecilia narrows lanes per "
             "project in `.cecilia/config.json` → `lanes`. Review guides are paths inside the cecilia-review skill.",
             "", "## Roles", "",
             "| Role | Agent type | Kind | On by default | Model | Lane | Consumes | Produces | Report | Review guide | Rules slot |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, r in sorted(reg["roles"].items()):
        lines.append(f"| {name} | {r['agent_type']} | {r['kind']} | {'yes' if r['default_on'] else 'no'} | "
                     f"{r['model']} | {cell(r['lane'])} | {cell(r['consumes'])} | {cell(r['produces'])} | "
                     f"{code(r['report'])} | {cell(['cecilia-review/' + g for g in r['review_guide']])} | {code(r['rules_slot'])} |")
    lines += ["", "## Agent types (permissions)", "",
              "| Agent type | Writes | May dispatch | Main thread | Claude Code tools | Antigravity tools | Summary |",
              "|---|---|---|---|---|---|---|"]
    for name, at in sorted(reg["agent_types"].items()):
        ct = at["claude"]["tools"]
        ct = "inherit (session tools)" if ct == "inherit" else ", ".join(ct)
        deny = at["claude"].get("disallowedTools") or []
        if deny:
            ct += " · deny " + ", ".join(deny)
        lines.append(f"| {name} | {at['writes']} | {'yes' if at['may_dispatch'] else 'no'} | "
                     f"{'yes' if at['main_thread'] else 'no'} | {cell(ct)} | {cell(', '.join(at['antigravity']['tools']))} | "
                     f"{cell(at['summary'])} |")
    lines += ["", "## Effective permissions per role (agent type + role overrides; the v19.2 tool sets)", "",
              "| Role | Claude Code tools | Claude Code disallowed | Antigravity tools | Antigravity commands | Antigravity model |",
              "|---|---|---|---|---|---|"]
    for name, r in sorted(reg["roles"].items()):
        tools, deny = claude_perms(reg, r)
        if reg["agent_types"][r["agent_type"]].get("may_dispatch"):
            tools = ["Agent(<every other role>)"] + (tools or [])
        ag, policy = antigravity_perms(reg, r)
        lines.append(f"| {name} | {cell(', '.join(tools) if tools else 'inherit (session tools)')} | "
                     f"{cell(', '.join(deny))} | {cell(', '.join(ag))} | {policy or 'none'} | {antigravity_model(reg, r)} |")
    return "\n".join(lines) + "\n"


def lenses_md(reg: dict) -> str:
    lines = [f"# Lenses (v{REG.VERSION}) — test and review", "", GEN_HEAD.strip(), "",
             "One tester or reviewer instance runs one lens. The orchestrator picks lenses by what the change "
             "touches; the chosen workflow option names them."]
    for kind, title in (("test", "Test lenses (cecilia-test)"), ("review", "Review lenses (cecilia-review panel)")):
        lines += ["", f"## {title}", "", "| Lens | Checks | Pick when | Guide | Rules slot |", "|---|---|---|---|---|"]
        for name, ln in sorted(reg["lenses"][kind].items()):
            lines.append(f"| {name} | {cell(ln['summary'])} | {cell(ln['when'])} | {code(ln['guide'])} | "
                         f"{code(ln['rules_slot'])} |")
    return "\n".join(lines) + "\n"


def flows_md(reg: dict) -> str:
    lines = [f"# Flows (v{REG.VERSION})", "", GEN_HEAD.strip(), "",
             "The active flow is `.cecilia/config.json` → `flow` (only Cecilia changes it: `cecilia flow <name>`); "
             "its settings live under `flows.<name>`. Every flow declares the steps "
             + ", ".join(f"`{s}`" for s in REG.STEPS) + " and its guide has one `## <step>` section per step.",
             "", "| Flow | Summary | Steps | Guide | Rules slot |", "|---|---|---|---|---|"]
    for name, fl in sorted(reg["flows"].items()):
        lines.append(f"| {name} | {cell(fl['summary'])} | {' → '.join(fl['steps'])} | {code(fl['guide'])} | "
                     f"{code(fl['rules_slot'])} |")
    for name, fl in sorted(reg["flows"].items()):
        if not fl.get("settings"):
            continue
        lines += ["", f"## Settings — {name} (defaults for `flows.{name}`)", "", "| Key | Default |", "|---|---|"]
        for k, v in fl["settings"].items():
            lines.append(f"| {k} | {code(json.dumps(v, ensure_ascii=False))} |")
    return "\n".join(lines) + "\n"


def all_files():
    reg = registry()
    files = {}
    files.update(claude_files(reg))
    files.update(antigravity_files(reg))
    files["shared/generated/roster.md"] = roster_md(reg)
    files["shared/generated/lenses.md"] = lenses_md(reg)
    files["shared/generated/flows.md"] = flows_md(reg)
    return files


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
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    stale = []
    for rel, content in all_files().items():
        p = ROOT / rel
        if p.is_file() and p.read_text(encoding="utf-8") == content:
            continue
        if a.check:
            stale.append(rel)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8", newline="\n") as fh:   # LF on every OS (Python 3.9)
                fh.write(content)
            print("wrote", rel)
    if stale:
        print("adapters out of date — run tools/build_adapters.py:\n  " + "\n  ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
