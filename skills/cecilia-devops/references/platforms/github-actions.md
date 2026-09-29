# GitHub Actions

## 1. Permissions — the default is too broad

Set `permissions` at the top of every workflow, then widen per job:

```yaml
permissions:
  contents: read          # default for the whole workflow
jobs:
  publish:
    permissions:
      contents: read
      packages: write     # only this job, only what it needs
      id-token: write     # OIDC, so no long-lived cloud keys
```

Prefer **OIDC** to a cloud role over stored access keys — nothing long-lived to leak or rotate.

## 2. Untrusted input — the mistake that loses repositories

- **`pull_request_target` runs with the base repo's secrets and write token.** Never check out and
  run the PR's code in it. Use it only for jobs that touch no PR code (labelling, commenting).
- `pull_request` from a fork gets no secrets. That is correct — do not "fix" it.
- Never interpolate untrusted values (`github.event.pull_request.title`, branch names, issue bodies)
  directly into a `run:` block: that is shell injection into your own runner. Pass through `env:` and
  reference the variable.
- `workflow_run` inherits elevated context — treat its inputs as untrusted too.

## 3. Pin what executes

Third-party actions by **commit SHA**, not a tag — tags move:

```yaml
- uses: actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8  # v5.0.0
```

Pin container images by digest, and tool versions explicitly. Keep a comment with the human-readable
version so updates are reviewable.

## 4. Practical shape

```yaml
concurrency:                       # cancel superseded runs on the same ref
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
jobs:
  test:
    timeout-minutes: 15            # every job, always
```

- `actions/cache` keyed on the lockfile hash, with `restore-keys` for a partial hit; setup actions
  usually have caching built in — use it rather than rolling your own.
- Matrix for real variation (versions, OS), with `fail-fast: false` when you want the full picture.
- Reusable workflows (`workflow_call`) for shared logic; composite actions for shared steps. Copy the
  same 40 lines into six workflows and they will diverge.
- **Environments** (`environment: production`) give required reviewers and environment-scoped
  secrets — this is how a production deploy gets a human gate, and it matches `authority.md`: the
  approval lives in the platform, not in a convention.
- Artifacts between jobs via `upload-artifact`/`download-artifact`; never rebuild
  (`deploy-and-rollback.md` §1).

## 5. Secrets

Repository, environment or organization secrets only — never in the workflow file, never in
`env:` at workflow level where every job inherits them. They are masked in logs, but masking is
pattern-matching: a transformed secret (base64'd, split, JSON-encoded) prints in the clear. Never
echo one, and never pass one in argv (`secrets.md` §2).

`GITHUB_TOKEN` expires with the run and is preferable to a PAT. If a PAT is unavoidable, it is
fine-grained, minimally scoped, expiring, and its rotation owner is written in
the infrastructure doc.

## 6. Debugging

`gh run list` / `gh run view <id> --log-failed` (or the github MCP server) · re-run a single failed
job rather than the whole workflow · `ACTIONS_STEP_DEBUG` as a repository secret for verbose logs,
removed afterwards · reproduce inside the same container image locally before editing the workflow
(`mcp-and-tools.md` §4).

## 7. Checklist

- [ ] `permissions` set explicitly, least privilege, widened only per job
- [ ] OIDC instead of long-lived cloud credentials
- [ ] No untrusted interpolation into `run:`; `pull_request_target` runs no PR code
- [ ] Third-party actions pinned by SHA; images by digest
- [ ] `timeout-minutes` on every job; concurrency group cancels superseded runs
- [ ] Caches keyed on lockfiles; artifacts reused, not rebuilt
- [ ] Production deploy behind an Environment with required reviewers
- [ ] No secret in the workflow file, in argv, or echoed
