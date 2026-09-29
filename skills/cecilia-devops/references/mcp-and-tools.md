# Working through MCP, CLI, or neither

Cecilia's rule: prefer an MCP server when one is connected, fall back to the CLI, and when neither is
reachable, write the commands for her rather than guessing. Never state live state you could not read.

## 1. Discover, at the start of every run (Y0)

List the MCP tools actually present in this session and the CLIs actually installed — do not assume
either from the project's nature or from a previous run. Tools appear and disappear between sessions.

| Job | MCP, if present | CLI fallback | Neither |
|---|---|---|---|
| Repo, PRs, branch protection | github / gitlab server | `gh`, `glab`, `git` | compose commands for Cecilia |
| Pipelines, runs, job logs | same server's actions/pipeline tools | `gh run`, `glab ci` | ask her to paste the failing log |
| Cluster state | kubernetes server | `kubectl`, `helm` | ask for `kubectl get ... -o wide` output |
| Cloud resources | aws / gcp / azure server | provider CLI | ask, or read IaC state read-only |
| IaC | terraform server | `terraform`, `pulumi` | ask her to run `plan` and paste it |
| Containers, registry | docker server | `docker`, `crane`, `skopeo` | ask |
| Errors, traces, metrics | sentry / datadog / grafana server | provider CLI | ask for a screenshot or an export |
| Tickets, incidents | jira / linear server | provider CLI | record in `tensura/reports/` only |

Write the result into the Y0 summary and the report, in one line each:
`MCP: github, kubernetes · CLI: git, docker, kubectl, helm · thiếu: terraform, cloud CLI`.

That line matters later: a reader needs to know whether "staging runs v1.4.2" was read from the
cluster or taken from a file.

## 2. Order of preference, and why

1. **MCP** — authenticated, scoped, auditable, and it returns structured data instead of text to
   parse. Prefer it even when a CLI would work.
2. **CLI** — when no server covers the job. Watch the ambient context: `kubectl` uses whatever
   context is current, `aws` whatever profile and region. State the context/profile/region in every
   approval quote and never rely on the default being what you expect.
3. **Neither** — compose the exact command for Cecilia, say what output you need back, and wait.
   This is a normal outcome, not a failure; say it plainly and keep working on what is reachable.

Tier rules from `authority.md` apply identically to all three. An MCP tool that can reach
production is still production: the agent does not use it; Cecilia does. The transport does not grant permission.

## 3. Never guess live state

If a claim about the running system cannot be traced to something read in this session, it is not a
claim. Use the confidence labels from `common/core.md` §7 on every non-trivial statement:

- `[verified]` — read it this session, and say from where: *"staging chạy v1.4.2 `[verified]` —
  `kubectl get deploy orders -n staging`"*.
- `[inferred]` — reasoned from the repo or from an earlier report; name what it was inferred from.
- `[unverified]` — could not check. Say why, and what would let you check it.

A validator or linter that is not installed produces `[unverified]`, never a pass. Do not install
tooling on Cecilia's machine or in the cluster to close that gap without asking.

## 4. Diagnosing a red pipeline

Order matters — the cheapest and most decisive first:

1. Read the **failing job's log**, not the summary, and find the first error, not the last. A later
   error is usually a consequence.
2. Compare with the **last green run**: what changed — the code, the pipeline file, a dependency
   version, a base image tag, a runner image, a secret's expiry, or nothing at all (then it is
   flaky or external).
3. Check whether it fails **only in CI**: different OS, different arch, no TTY, a clean cache, no
   network to a host the developer's machine can reach, a missing secret on fork PRs, a clock skew.
4. Reproduce **locally in the same container** before changing the pipeline — changing CI to see what
   happens is a loop that costs a run each time and teaches nothing.
5. Only then fix, and fix the cause: a retry around a flaky step is a decision for Cecilia, with the
   trade-off stated, never a quiet patch.

## 5. Research before proposing a tool or a version

`common/capabilities.md` applies. Official docs first (Context7 MCP if available), then release notes,
then reputable community sources. Cite source and version in the PR and in
the infrastructure doc. Infrastructure syntax and defaults change fast and confidently-remembered
flags are a common way to lose an afternoon — if you cannot check it, mark the option
`[unverified]` and say so before Cecilia decides on it.
