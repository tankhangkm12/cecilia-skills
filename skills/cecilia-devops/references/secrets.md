# Secrets — the agent never handles a value

Cecilia's rule, without exception: **the agent builds the path a secret travels; Cecilia is the only
one who touches the value.** Not read, not printed, not logged, not written to a file, not repeated
back, not stored "temporarily". This holds even when she pastes one into the chat, even during an
incident, even when it would take one command to finish the job.

Read this file before any step that involves a credential, key, token, password, certificate or
connection string — every time, not once per project.

## 1. What the agent does and does not do

| Does | Does not |
|---|---|
| Names: `DB_PASSWORD`, `STRIPE_SECRET_KEY` | Values, ever |
| Source of truth per environment (which manager, which path/ARN) | Read the value from that manager unaided (§4) |
| Who may read it (role, policy, service account) | Grant itself that permission |
| Which process consumes it and how it arrives (env var, mounted file, stdin) | Put it in a command's arguments |
| `.env.example` with fake values and a comment per key | `.env` with real values |
| Check a secret **exists** and is non-empty, and its metadata (version, age, last rotation) | Check it by printing it |
| Compose the command Cecilia runs (§2, §3) | Run that command on her behalf |

Verifying existence without revealing: compare a length or a hash the tool gives you, or use the
manager's "describe" call that returns metadata only. Never `echo $VAR`, never `cat` the file, never
`kubectl get secret -o yaml` (that is base64, which is not encryption), never `terraform show` on
state that holds the value, never `set -x` while a secret is in scope.

## 2. Protocol A — Cecilia types it, RAM only

This is the default whenever a secret must go into an install, an apply or a one-off command.

The agent **composes** a single command and hands it to Cecilia. She runs it in her own terminal. The
value exists only in that shell's memory, never in history, never in a log, never in a file.

```bash
# Leading space keeps the line out of history when HISTCONTROL includes ignorespace.
 read -rs -p "DB_PASSWORD: " DB_PASSWORD && echo && \
   TF_VAR_db_password="$DB_PASSWORD" terraform apply -input=false && \
   unset DB_PASSWORD
```

Rules for composing that command:

- **`read -rs`** — `-s` suppresses echo, `-r` stops backslash mangling. Always print a newline after
  (`&& echo`), or her next prompt lands on the same line.
- **One line, ending in `unset`.** Read, use, unset — chained, so the value cannot outlive the
  command even if a middle step fails (use `; unset VAR` rather than `&& unset VAR` when the consuming
  command may fail and the variable must still go).
- **Never in argv.** `--password "$VAR"` is visible in `ps` to every user on the box and often lands
  in shell history. Pass it as an environment variable the tool already reads
  (`TF_VAR_*`, `PGPASSWORD`, `AWS_SECRET_ACCESS_KEY`, `GITHUB_TOKEN`), or on stdin.
- **Stdin is best where the tool supports it**: `docker login -u "$USER" --password-stdin <<<"$TOKEN"`,
  `gh auth login --with-token <<<"$TOKEN"`, `kubectl create secret generic app --from-env-file=-`.
- **Files only as a last resort**: `umask 077` before creating, under `/dev/shm` or another tmpfs if
  available, and `shred -u` (or `rm -P`) in the same command line.
- Tell her in one line what the command does and what it will leave behind (usually: nothing).

Then: **stop and wait.** She says it is set. Only then does the agent continue, using the resource
without ever reading it back. When the work is done, hand her the revocation line
(`unset VAR`, `history -d`, close the shell, or the manager's revoke/rotate command as appropriate)
and say explicitly that the credential can now be withdrawn.

## 3. Protocol B — the secret lives in a manager

Cecilia may instead put the value in KMS, Vault, SSM Parameter Store, Secrets Manager, or the CI
provider's secret store, and tell the agent to use it.

**The agent asks her before every single retrieval** — per secret, per environment, per run. A "yes"
last week is not a "yes" now. The question states: which secret, which environment, which command
will consume it, and why it cannot be done without the value.

Preferred, in order:

1. **Never retrieve it at all.** Give the workload permission to read it itself: an IAM role, a
   Kubernetes `secretKeyRef`, a CI secret bound to the job, a CSI secrets driver. The value then goes
   manager → workload and no human or agent is on the path. Propose this first every time.
2. **Reference, not value.** Pass an ARN, a path, a version id.
3. **Retrieval into an environment variable** inside one command that also uses and unsets it, with
   the retrieval's own output never printed. Only with the per-retrieval approval above.

Never copy a value from one manager to another by passing through the agent's context. Use the
manager's replication, or Protocol A.

## 4. If a value is exposed anyway

She pastes one into the chat · it appears in a tool result, a log line, an error message, a
`terraform plan` output · it is committed. Then, immediately and in this order:

1. **Do not repeat it.** Not in the report, not in the PR, not quoted back to confirm, not partially
   masked — masking still confirms length and prefix.
2. **Say plainly that it must be treated as compromised**, and that rotating is not optional because
   it has been somewhere it cannot be recalled from.
3. **Give the rotation steps** for that specific secret: rotate at the source, update every consumer
   (list them from the wiring the skill already knows), verify, then revoke the old version — in that
   order, so nothing breaks between rotate and update.
4. If it reached git: say that rewriting history does not undo it — forks, clones, caches and
   mirrors keep it. Rotate first; history cleanup is cosmetic afterwards.
5. Record the event as `INC-nn` (`incidents.md`) with the secret's **name** only.

## 5. Wiring rules for the files the skill does own

- One source of truth per secret per environment; the same name everywhere so a grep finds every use.
- Secrets never have defaults and never fall back — missing secret means the app fails at startup
  with a clear message, never boots degraded (matches `cecilia-dev-be` / `cecilia-dev-fe`'s config rule: validate at
  startup, fail fast).
- Nothing secret in: repo files, image layers, build args, `docker history`, CI logs, manifest
  `env:` literals, Terraform variables with defaults, error messages, URLs, or anything that ends up
  in a dashboard label.
- CI: use the provider's secret store, mark it masked/protected, scope it to the jobs and branches
  that need it, and never let it reach a workflow triggered by a fork's pull request.
- Every secret gets a rotation answer in the infrastructure doc: who rotates it, how often, what
  breaks during rotation. "Nobody has ever rotated it" is an answer worth writing down.
- Run a secret scan over the diff at Y5. A hit blocks the PR — no exceptions for test fixtures.

## 6. Checklist before any PR that touches secret wiring

- [ ] No value appears in any file, command, report, PR body or chat message
- [ ] Every new key is in `.env.example` with a fake value and a one-line comment
- [ ] Source of truth and reader permission named per environment
- [ ] Consumer receives it by env var, mount or stdin — never argv, never a repo file
- [ ] Rotation owner and procedure written into the infrastructure doc
- [ ] Secret scan run over the diff and clean
- [ ] Any command handed to Cecilia ends by unsetting or revoking
