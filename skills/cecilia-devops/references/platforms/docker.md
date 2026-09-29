# Docker — images and compose

## 1. Image rules

- **Multi-stage.** Build tooling, compilers and dev dependencies stay in the build stage; the final
  stage holds the artifact and its runtime only. Smaller is not the point — a smaller attack surface
  and a faster pull are.
- **Pin the base image by digest**, not by a moving tag. `node:20` changes underneath you; the
  rebuild that "changed nothing" is a well-known way to lose a day.
- **Layer for cache**: dependency manifests copied and installed *before* the source is copied, so a
  source edit does not reinstall everything. Order from least to most frequently changed.
- **Run as a non-root user**, created in the image, owning only what it must write. Read-only root
  filesystem where the app allows it, with explicit writable volumes.
- **`.dockerignore` first** — `.git`, `node_modules`, `.env`, build output, test fixtures, CI
  files. Without it the build context leaks secrets into the daemon and slows every build.
- **One process concern per image.** Needing a supervisor inside is a signal to split.
- **`ENTRYPOINT` in exec form** (`["./app"]`), so signals reach the process and the container stops
  in seconds instead of being killed after a timeout. Handle `SIGTERM` for graceful shutdown.
- Label the image with the commit sha, build time and version; that is often the only way to answer
  "what is actually running".

## 2. Secrets and builds

Never a secret in a `Dockerfile`, a build arg, an `ENV`, or any intermediate layer — **`docker
history` reveals all of them**, and deleting a file in a later layer does not remove it from the
earlier one. Use BuildKit build secrets (`--mount=type=secret`) for build-time credentials, and
runtime injection (env var or mounted file) for everything else (`secrets.md`).

Registry credentials: `docker login --password-stdin`, never `--password` in argv.

## 3. Verifying an image before it ships

Build it, then: run it and hit the health endpoint · check the user is not root
(`docker run --rm img id`) · check the size and the layer list for anything unexpected ·
`docker history` for leaked values · scan for vulnerabilities · confirm it stops within a few seconds
on `docker stop`. Record the digest — that is what gets deployed
(`deploy-and-rollback.md` §1).

## 4. Compose

Compose is for local development and small single-host deployments. Using it as the production
orchestrator is a decision to state explicitly with its consequences (no rolling update, no self
healing, one host), not a default to slide into.

- Pin image digests here too; never `:latest`.
- No secrets in the file — `env_file` pointing outside the repo, or the host's environment.
- Every service declares a `healthcheck`, and dependents use `depends_on: condition:
  service_healthy` — plain `depends_on` waits for *start*, not for *ready*, which is why "it works
  on the second run".
- Named volumes for anything that must survive; say out loud what a `docker compose down -v` destroys.
- Set resource limits, or one runaway container takes the host down with it.

## 5. Checklist

- [ ] Multi-stage; final image has no build tooling
- [ ] Base image pinned by digest; `.dockerignore` present and complete
- [ ] Non-root user; read-only root fs where possible
- [ ] Dependencies layered before source for cache
- [ ] Exec-form entrypoint; SIGTERM handled; stops promptly
- [ ] No secret in any layer, arg or env — `docker history` checked
- [ ] Health endpoint verified by actually running the image
- [ ] Scanned; digest recorded for deployment
