# Lens: infra (cecilia-test v20)

Brief header `LENS=infra`. Shared lens rules (files, isolation, report, lane): `../workflow.md` §Lenses.

## Attacks
Pipelines, images, IaC and deploy config: do they validate, do they do what the `OPS` row says, and what
would they change if applied. **Validate only, never apply.**

## Oracle
Plan `OPS` row · infrastructure doc (environments, sizes, secrets handling, rollback) · NFR availability
and recovery numbers · the repo's own lint/policy config.

## Techniques
- **Validate and lint:** `terraform fmt -check` + `terraform validate`, `tflint`; `helm lint` +
  `helm template`; `kubectl apply --dry-run=client` / `kubeconform`; `hadolint`; `actionlint` / pipeline
  linters; `docker build` locally; policy tools (`checkov`, `tfsec`, `conftest`) when the repo has them.
- **Plan only:** `terraform plan` / `pulumi preview` against a local or mocked backend, or a plan Cecilia
  ran and handed over. Read the plan: destroys, replacements, public exposure, IAM widening → findings.
- **Secrets:** none in files, images, logs or plan output; referenced from the secret store as documented.
- **Rollback:** the documented rollback is executable on paper (previous image tag, `down` path, flag).
- **Pipelines:** required checks, order (migrate before deploy), manual gate for production.
- Image: non-root user, pinned base digest, size recorded.

## Files
Test harness and fixtures in `<repo test root>/infra/...` (e.g. `conftest` policies, `terratest` in
plan-only mode). Never edits the IaC under test.

## Environment
Local tools only, own working dir; a remote state backend or cloud credentials needed → A3 request to
Cecilia with the exact command, rows marked `[unverified]` meanwhile.

## Report
`tensura/reports/<TASK>/test-infra.md`: table `artifact · command · result`, plan summary (add/change/
destroy counts and each destroy named), BUG table (`BUG-infra-nn`).

## Never
`terraform apply`, `pulumi up`, `kubectl apply` without `--dry-run`, `helm install/upgrade`, a pipeline run
or any change to a real environment (A4) · touch secrets/IAM · fix IaC (`HANDOFF: needs cecilia-devops`).
