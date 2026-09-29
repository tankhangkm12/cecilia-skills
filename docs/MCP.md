# `cecilia mcp` — drive Cecilia from another LLM

`cecilia mcp` is a Model Context Protocol server (Python stdlib only). With it, another LLM client (Antigravity,
Claude Desktop, Claude Code, Cursor, or any other MCP client) can start work in your Cecilia workspaces, follow
it, show you the decision card, pass your answer back, and — if you allow it — run the commands that are otherwise
yours alone (mode, approve, flow, rules add, extension apply, push). The work itself always runs as
**cecilia-orchestrator** inside the workspace, and the workspace's guard hooks apply to every tool call.

## Connect

Print ready-to-paste snippets:

```
cecilia mcp --print-config
```

| Client | How |
|---|---|
| Antigravity | `~/.gemini/config/mcp_config.json` (Windows: `%USERPROFILE%\.gemini\config\mcp_config.json`) → `{"mcpServers": {"cecilia": {"command": "cecilia", "args": ["mcp"]}}}` |
| Claude Desktop | `claude_desktop_config.json` → the same `{"mcpServers": {"cecilia": {"command": "cecilia", "args": ["mcp"]}}}`. If Desktop cannot find `cecilia`, use the full path that `--print-config` prints (Windows: `…\.local\bin\cecilia.exe`). |
| Claude Code | `claude mcp add cecilia -- cecilia mcp` |
| Cursor / others (stdio) | the same `command` + `args` in the client's MCP config |
| Any client (HTTP) | run `cecilia mcp --http 8765`, then use `{"type": "http", "url": "http://127.0.0.1:8765/mcp"}` |

The default transport is stdio: newline-delimited JSON-RPC on stdin/stdout, with logs on stderr only.
`--http [HOST:]PORT` serves Streamable HTTP. It takes `POST /mcp` and replies with `application/json` (there is
no SSE). `GET` and `DELETE` get 405. Protocol versions 2025-06-18, 2025-03-26 and 2024-11-05 are supported.

Run the server **outside** the workspace (from your client), not as a tool of an agent inside it: the server is
the supervisor of the orchestrator, not one of its agents.

## No authentication → 127.0.0.1 / stdio only

The server has no authentication, and with the control tools it can approve plans and push. So:
- Prefer stdio (the client starts the server; nothing listens on the network).
- HTTP listens on **127.0.0.1 only**. `--http 0.0.0.0:…` or any other non-loopback host is refused.
- The `Origin` header must be absent or `http(s)://localhost` / `http(s)://127.0.0.1` (any port). Any other
  origin gets 403, which blocks DNS rebinding from a web page.
- Never expose the port through tunnels, port forwarding or reverse proxies.

## Hosts: Antigravity first

`cecilia_start_task(workspace, prompt, host=auto|agy|claude|inbox)`:

| host | What runs |
|---|---|
| `agy` | Antigravity CLI headless, detached, in the workspace (below). |
| `claude` | `claude -p --agent cecilia-orchestrator --output-format stream-json --verbose --permission-mode <mcp.permission_mode, default acceptEdits>` (the prompt goes through stdin). Never `bypassPermissions`. |
| `inbox` | Only queues the prompt in `tensura/inbox/<id>.json`; the orchestrator picks it up when the workspace is next opened. |
| `auto` (default) | `agy` when `agy` is installed **and** the workspace has `.agents/`; else `claude` when installed and the workspace has `.claude/`; else `inbox`. |

### The agy run

```
agy -p "[via cecilia-mcp] <prompt>" --agent cecilia-orchestrator --output-format json
    --print-timeout <mcp.agy_timeout_min, default 60>m [--dangerously-skip-permissions]
    [--conversation <id>]                      # cecilia_send / cecilia_decide resume the same conversation
```

- `cwd` is the workspace, so its `.agents/` (hooks, agents, main agent) is loaded — starting `agy` from your home
  folder loads none of it.
- `--dangerously-skip-permissions` is on by default (`mcp.agy_skip_permissions: true`, your choice: headless agy
  otherwise soft-denies every tool that needs approval). The guard hooks in `.agents/hooks.json` still decide every
  tool call. Set it to `false` to drop the flag.
- stdin is `/dev/null` (agy print mode can hang when stdin is an open pipe, bug #318); stdout and stderr go to
  `tensura/runs/<RUN>.out` / `.err`; Windows: `CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW` (no console windows
  for the commands agy runs).
- Wall clock: `cecilia_run` kills a run still alive after `agy_timeout_min` + 2 minutes (status `failed`, hint).
- `cecilia_cancel` kills the process tree (`taskkill /T /F` on Windows, the process group elsewhere).
- The run record `tensura/runs/<RUN>.json` has `host: "agy"`, the turns, and the conversation id once known.

**How cecilia_run reads the result.** It parses the JSON envelope on stdout (`conversation_id`, `status`,
`response`, `error`, `usage`). On Windows agy's stdout is often **empty** in a non-TTY even though the run
succeeded (bug #76), so when there is no envelope the server recovers:
1. the conversation id: from `~/.gemini/antigravity-cli/cache/last_conversations.json` (the entry whose cwd is
   the workspace, active since the run started; unknown shapes are tolerated), else the `brain/<id>/` folder
   active since the start whose first user input is our prompt, else the newest such folder that is not a
   subagent's (a subagent's first input is a `[cecilia-brief …]`);
2. the answer: the last `PLANNER_RESPONSE` in `brain/<id>/.system_generated/logs/transcript.jsonl` after our
   prompt; the run is `running` while the process is alive, `finished` when it has exited with an answer.
`cecilia_run` then shows `recovered_from_transcript: true`. `CECILIA_AGY_HOME` overrides
`~/.gemini/antigravity-cli` (tests).

Envelope status `SUCCESS` → `finished`; `WAITING` → `finished` with a hint (a tool needed approval — answer with
`cecilia_send`, or allow skip-permissions); `ERROR` / `CANCELED` / `INTERRUPTED` / `INVALID` → `failed`.

**Windows and `agy.cmd`.** The server looks for `agy.exe` first. If only an `agy.cmd`/`agy.bat` shim is on PATH it
reads the shim and starts the program it points to (an `.exe`, or `node` + the script), so the prompt never
passes through cmd.exe. If the shim cannot be resolved, it runs it through `cmd.exe /d /v:off /s /c` with every
argument quoted: newlines in the prompt become spaces, and a prompt containing `"` or `%` is refused with a clear
message (cmd.exe cannot pass those safely). Point `mcp.agy_path` (or env `CECILIA_AGY`) at `agy.exe` to avoid it.

## Tools

| Tool | What it does |
|---|---|
| `cecilia_workspaces(root?)` | Lists the workspaces registered in `~/.cecilia/workspaces.json`. With `root`, it also scans that folder for `*.cecilia` workspaces. |
| `cecilia_status(workspace)` | Mode (read like the guard), flow, open tasks, open decision cards, inbox items, MCP runs, the control tools available, and what stays human-only. |
| `cecilia_start_task(workspace, prompt, host)` | See *Hosts* above. |
| `cecilia_run(workspace, run_id, tail=20)` | Status (running/finished/failed/cancelled), session/conversation id, last assistant texts, final result, cost (claude) or usage (agy), permission denials, and any human-only command the agent asks for (`human_commands`). |
| `cecilia_send(workspace, run_id, message)` | Continues a finished run: agy `--conversation <id>`, claude `--resume <session>`. |
| `cecilia_decision(workspace, task)` | Returns the decision card (`tensura/decisions/<task>.md` + `.json`). |
| `cecilia_decide(workspace, task, option, answers={}, note="")` | Runs `workflow.py answer … --by mcp`, then resumes the task's run with "Decision recorded … Continue the workflow." |
| `cecilia_read(workspace, path)` | Reads a file or lists a folder under `<workspace>/tensura` only. `..`, absolute paths and escaping symlinks are refused. The limit is 200 KB. Secrets are redacted. |
| `cecilia_cancel(workspace, run_id)` | Kills the run's process tree and marks the run cancelled. |

### Control tools

| Tool | Runs |
|---|---|
| `cecilia_mode(workspace, mode)` | `cecilia mode MODE --yes --by mcp` |
| `cecilia_approve(workspace, plan, task?, all=false, hours?)` | `cecilia approve <tensura/…plan> [--task T \| --all] [--hours H] --yes --by mcp` |
| `cecilia_flow(workspace, flow)` | `cecilia flow NAME --yes --by mcp` |
| `cecilia_rules_add(workspace, text, role \| project=true \| flow \| lens)` | `cecilia rules add --role R … "text" --yes --by mcp` |
| `cecilia_extension_apply(workspace, dir)` | `cecilia extension apply <tensura/extensions/DIR> --yes --by mcp` (then the workspace upgrade) |
| `cecilia_push(workspace, args=[])` | `cecilia push [ARGS] --yes --by mcp` (unlocks and relocks the push lock) |

Each runs the real `cecilia` command in the workspace with env `CECILIA_MCP=1`, captures its output, and appends
one line to **`<workspace>/tensura/audit/control.jsonl`**:
`{"ts", "by": "mcp", "command", "args", "result": "ok"|"failed", "exit", "output"}` (output redacted, last
2000 characters). A non-zero exit is returned as the tool error with the command's own output — for
`cecilia_approve` that is the lint findings: nothing is approved and there is no way to force it (send the plan
back to the orchestrator). Every check of the interactive path still applies: a known flow, rules only tighten
and must lint, an extension proposal must pass its check, plans stay confined to `tensura/`.
`cecilia_push` accepts a remote name, plain refspecs and `-u/--set-upstream`, `--tags`, `--follow-tags`,
`--dry-run`, `-v`, `-q`, `--atomic`, `--porcelain`, `--progress`, `--force-with-lease[=…]`, `--force-if-includes`;
`--force`, `+refspec`, `:delete`, `--mirror`, `--delete`, `--receive-pack/--exec`, `--no-verify`, push options
and URLs are refused (those stay in your terminal). git never prompts (`GIT_TERMINAL_PROMPT=0`).

The `--yes --by NAME` path of `cecilia_mode.py`, `cecilia_approve.py` (also with `--all`) and of `cecilia flow /
rules add / extension apply / push` is honoured **only** when env `CECILIA_MCP=1`; anywhere else the command prints
`--yes is only for the Cecilia MCP server` and exits 2, and the interactive behaviour (terminal + typed
confirmation) is unchanged. The server gives `CECILIA_MCP=1` only to these control commands, never to agy/claude
runs. The guard still refuses these commands to agents inside the workspace unless you list them in
`guard.agent_may_run` — so an agent cannot approve its own plan, with or without `--yes`. If a workspace's
`.cecilia/bin` tools predate `--yes`, the tool error says to run `cecilia upgrade`.

The connected LLM should use a control tool only when you asked for that exact action (or confirmed it in the
conversation) — never because the orchestrator asked for it.

## Configuration

Workspace `.cecilia/config.json` (per workspace) and `~/.cecilia/mcp.json` (server-wide, `{"mcp": {…}}`; the path
can be changed with env `CECILIA_MCP_CONFIG`); the workspace value wins:

```json
{"mcp": {
  "control": "all",
  "agy_skip_permissions": true,
  "agy_timeout_min": 60,
  "agy_path": "C:\\Users\\me\\AppData\\Local\\agy\\agy.exe",
  "permission_mode": "acceptEdits"
}}
```

- `control`: `"all"` (default), `"none"`, or a list such as `["mode", "approve"]`. Anything unrecognised means
  none. The server-wide value (env `CECILIA_MCP_CONTROL`, else `~/.cecilia/mcp.json`) decides which control tools
  are **listed**; a workspace's own `"none"` refuses them for that workspace. With `"none"` those commands are
  human-only again: the LLM shows you the command and you run it in your own terminal.
- `permission_mode` (claude only): `default`, `acceptEdits` or `plan`. Claude runs never get
  `bypassPermissions`.

## Typical flow

1. `cecilia_workspaces` → pick the workspace.
2. `cecilia_start_task(workspace, "add a cart page")` → a `run_id` (host `agy` on an Antigravity workspace).
3. Poll `cecilia_run(run_id)` (agy runs take minutes) until it is finished; then `cecilia_status` for an open
   decision card.
4. `cecilia_decision(task)` and show the card to the user. The user chooses.
5. `cecilia_decide(task, option, answers)` records the answer and resumes the run.
6. Poll `cecilia_run` again; `cecilia_send` for follow-ups. If the run asks for `cecilia approve …` or
   `cecilia push`, ask the user; with their yes, use `cecilia_approve` / `cecilia_push`, else hand them the command.
