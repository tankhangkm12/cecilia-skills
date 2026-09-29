# Terraform (and IaC generally)

Terraform destroys things. Every rule here exists because someone's `apply` did something they did
not read first.

## 1. Plan is not optional, and it must be read

`terraform plan` against real state is a live read (A3, or covered by an approved read-only session)
— always run first, always included in the apply quote (`authority.md` §3). Read the whole plan, not the summary line.

**Stop and ask** whenever the plan shows: any `destroy`, any `replace` (`-/+`), a change to a
stateful resource (database, volume, bucket, queue), a count going down, or anything you did not
expect. `create` and in-place `update` on stateless resources are the only routine outcomes.

Apply the **saved plan file** (`terraform plan -out=tf.plan` → `terraform apply tf.plan`), so what
runs is exactly what was approved rather than a fresh plan computed against state that may have moved.

Never `-auto-approve` outside a pipeline that a human approved, never `-target` to work around an
error (it hides dependency problems and leaves state inconsistent), never `-refresh=false` to make a
plan look clean.

## 2. State

- **Remote backend with locking and versioning** (S3 + DynamoDB, GCS, Terraform Cloud). Local state
  means one laptop is the source of truth for the infrastructure.
- **Separate state per environment** — never one state file holding staging and production. Separate
  directories or workspaces, and a backend key that names the environment.
- State holds secret values in plain text: treat the backend as a secret store — encrypted,
  access-controlled, never in the repo, never printed. `terraform show` and `terraform output` can
  reveal them, so never paste their raw output (`secrets.md`).
- Never edit state by hand. `import`, `mv` and `rm` are surgery: state the exact command, take a state
  backup first, and get approval per command.
- A lock left behind by a crashed run is a stop: find out what ran, do not `force-unlock` reflexively.

## 3. Structure

Modules for repetition, not for decoration — a module wrapping one resource adds indirection and no
value. Environments differ by `*.tfvars`, not by copies of the code. Version pin everything: the
Terraform version, every provider, every module source (a tag or commit, never a branch). Commit
`.terraform.lock.hcl`.

Variables get types, descriptions and validation; secrets get `sensitive = true` and **no default**.
Outputs expose references, not values.

## 4. Drift

Drift is someone changing things by hand; the plan finds it. Report it with the diff at Y2 and let
Cecilia choose — import it into code, or revert it — and never silently overwrite it. A destroy that
appears in a plan "for no reason" is almost always drift or a changed identifier, and applying
through it is how a database disappears.

Protect what must not be destroyed:

```hcl
lifecycle {
  prevent_destroy = true   # databases, buckets, anything holding data
}
```

Recognise the arguments that force replacement rather than update — names, identifiers, availability
zones, engine versions on some resources — before changing them. The plan says `forces replacement`;
that phrase means the data is going away.

## 5. In a pipeline

`fmt -check` and `validate` on every PR · `plan` on the PR with the output posted for review ·
`apply` only from the default branch, only after the PR was approved, using the saved plan ·
credentials via OIDC to a scoped role rather than long-lived keys · a policy scan (tfsec/checkov) as
a check Cecilia decides blocks or warns.

## 6. Checklist

- [ ] Plan read in full, included in the approval quote, applied from the saved plan file
- [ ] No unexplained destroy or replace; stateful resources have `prevent_destroy`
- [ ] Remote state, locked, versioned, encrypted, separate per environment
- [ ] Terraform, providers and modules version-pinned; lock file committed
- [ ] Secret variables `sensitive`, no defaults; no value printed or pasted
- [ ] Drift reported to Cecilia rather than overwritten
- [ ] Destroy path understood: what it would take away, and what backs it up
