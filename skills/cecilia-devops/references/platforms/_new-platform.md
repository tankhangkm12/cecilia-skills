# Detecting the stack, and working with one that has no guide

## 1. Detect from the repo before asking (Y0)

| Signature | Platform | Guide |
|---|---|---|
| `.github/workflows/*.yml` | GitHub Actions | `github-actions.md` |
| `.gitlab-ci.yml` | GitLab CI | `gitlab-ci.md` |
| `Jenkinsfile` | Jenkins | this file |
| `azure-pipelines.yml` | Azure Pipelines | this file |
| `.circleci/config.yml` | CircleCI | this file |
| `Dockerfile`, `docker-compose*.yml` | Docker | `docker.md` |
| `Chart.yaml`, `templates/*.yaml`, `kustomization.yaml` | Helm / Kustomize | `kubernetes-helm.md` |
| `k8s/`, `deploy/*.yaml` with `apiVersion:` | Kubernetes | `kubernetes-helm.md` |
| `*.tf`, `.terraform.lock.hcl` | Terraform | `terraform.md` |
| `Pulumi.yaml`, `cdk.json`, `serverless.yml`, `template.yaml` | Pulumi / CDK / Serverless / SAM | this file |
| `fly.toml`, `render.yaml`, `app.yaml`, `vercel.json`, `Procfile` | PaaS | this file |
| `ansible.cfg`, `playbook*.yml` | Ansible | this file |

Report what was found, including **mixed signals** — two CI systems, manifests that no pipeline
applies, a Dockerfile nothing builds. Half-migrations are common and they are exactly what nobody
mentions in the interview. Then confirm with Cecilia before building on any of it (Y1).

Nothing found → this is a choice, not a detection. Present options with trade-offs and let her pick
(`common/decisions.md` §1). Never install a platform because it is the popular one.

## 2. Working with a platform that has no guide here

The principles in `pipeline-design.md`, `deploy-and-rollback.md`, `environments.md`,
`observability.md`, `secrets.md` and `authority.md` are platform-independent — they all still apply.
Only the syntax is unknown. So:

1. **Read the repo's existing config first.** The established pattern in this repo outranks anything
   general (`common/workspace.md` §3). Copy its conventions: naming, structure, how environments are
   expressed.
2. **Research the actual version in use** (`common/capabilities.md`): official docs first, then release
   notes. Infrastructure syntax and defaults move quickly, and a confidently-remembered flag that no
   longer exists costs a pipeline run per attempt. Cite source and version.
3. **Find the platform's answers to these**, and write them into the infrastructure doc:
   - how a secret reaches a job without entering the log or argv
   - how an artifact is built once and promoted, referenced immutably
   - what the rollback command is, and whether it can be rehearsed
   - how a job's permissions are scoped, and what the default is
   - whether the config can be validated locally, and with what
4. **Cannot verify something** → mark it `[unverified]` and say so before Cecilia relies on it. Never
   present remembered syntax as checked.
5. If this platform will keep being used, say once that a guide for it is worth adding, and offer to
   write one from what this run established.

## 3. Notes for the common no-guide cases

**Jenkins** — declarative pipeline in a `Jenkinsfile` in the repo, never configured in the UI where
it cannot be reviewed. Credentials via the credentials binding, never as job parameters. Agents/nodes
pinned, workspaces cleaned.

**Azure Pipelines / CircleCI** — the ideas map directly: stages, caching keyed on lockfiles, secret
stores, environment approvals. The trap in both is untrusted-fork triggers receiving secrets; check
that setting explicitly.

**Pulumi / CDK** — infrastructure as a real program means real bugs; the `terraform.md` rules about
plan-before-apply, remote locked state, and no manual drift apply unchanged. A preview is not
optional.

**PaaS (Fly, Render, App Engine, Vercel, Heroku)** — most of the platform is the provider's, so the
work is configuration and the risk concentrates in two places: where secrets are set, and whether
rollback exists and has been tried. Check both first.

**Ansible** — idempotence is the property that matters; a playbook that is not safe to run twice is
not finished. Dry-run (`--check --diff`) before any run, and inventory per environment.
