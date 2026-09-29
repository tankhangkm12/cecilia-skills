# GitLab CI

## 1. Shape

```yaml
stages: [lint, test, build, deploy]

default:
  interruptible: true            # superseded pipelines get cancelled
  timeout: 15m                   # every job, always

variables:
  DOCKER_BUILDKIT: "1"

workflow:                        # avoid duplicate branch+MR pipelines
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
```

- **`rules:` not `only/except`** — `only/except` is legacy and does not compose.
- `needs:` to build a DAG so jobs start as soon as their own dependency is ready, instead of waiting
  for a whole stage.
- `extends:` and `include:` for shared definitions; `include: project:` with a **pinned ref** for
  shared pipeline libraries — never a moving branch.
- The duplicate-pipeline problem (a push creating both a branch pipeline and an MR pipeline) is the
  most common source of wasted minutes; the `workflow:` block above is the fix.

## 2. Secrets and variables

- CI/CD variables, **masked** and **protected**. Masked hides them from logs (with the same caveat as
  everywhere: a transformed value prints in the clear). Protected restricts them to protected
  branches and tags — that is what keeps them away from an arbitrary branch's pipeline.
- Never a secret in `.gitlab-ci.yml`, never in a job's `variables:` block.
- Scope by environment where possible, so a staging job cannot read production's values.
- **Fork merge requests do not get protected variables**, and that is correct. Do not widen it.
- Prefer ID tokens / OIDC to a cloud role or Vault over long-lived keys.
- `CI_JOB_TOKEN` is scoped and short-lived — prefer it to a personal access token; if a PAT or deploy
  token is unavoidable, scope it minimally, give it an expiry, and record its rotation owner.

## 3. Runners

Know which runner executes the job and whether it is shared. On a shared runner, assume anything on
disk is visible to others; on a self-hosted one with the shell executor, the job runs as a user on a
real machine with whatever that user can reach — prefer the docker executor with a pinned image.
Tag jobs so they land on the runner intended, and never leave state in the workspace between jobs
(`GIT_STRATEGY`, clean up after).

## 4. Environments, deploys and rollback

```yaml
deploy_staging:
  stage: deploy
  environment:
    name: staging
    url: https://staging.example.com
    on_stop: stop_staging
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
      when: manual              # a human presses it
```

- GitLab **environments** give deployment history and the "rollback" button — that history is only
  meaningful if every deploy goes through the environment rather than a raw script.
- `when: manual` plus a protected environment is how a production deploy gets its human gate; that
  gate is Cecilia's (`authority.md` §1).
- Review apps: `environment.on_stop` with an expiry, or they accumulate silently
  (`environments.md` §4).
- Rollback still has to be rehearsed (`deploy-and-rollback.md` §4) — the button is not proof.

## 5. Caching and artifacts

`cache:` keyed on the lockfile (`key: files: [package-lock.json]`), with `policy: pull` on jobs that
only read it. `artifacts:` for things later jobs need, with a short `expire_in`. Cache is an
optimisation that may be empty; artifacts are a contract that must be there. Never depend on a cache
for correctness.

## 6. Debugging

`glab ci status` / `glab ci trace` (or the gitlab MCP server) · `CI_DEBUG_TRACE` only on a branch
with no protected variables in scope — it prints the environment, secrets included · validate the
config with the CI Lint endpoint before pushing · reproduce in the same image locally
(`mcp-and-tools.md` §4).

## 7. Checklist

- [ ] `rules:` everywhere; `workflow:` block prevents duplicate pipelines
- [ ] `timeout` and `interruptible` on every job; `needs:` where it shortens the critical path
- [ ] Variables masked and protected; scoped per environment; forks get none
- [ ] `include:` pinned to a ref, not a branch
- [ ] Runner type understood; no state left between jobs
- [ ] Deploys go through an `environment` with history and `on_stop`
- [ ] Production deploy `when: manual` on a protected environment
- [ ] `CI_DEBUG_TRACE` never enabled where protected variables are in scope
