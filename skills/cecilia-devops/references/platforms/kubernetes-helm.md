# Kubernetes and Helm

## 1. Before every command: which cluster?

`kubectl` and `helm` act on whatever context is current, and the difference between staging and
production is one forgotten flag. State the context and namespace in every approval quote
(`authority.md` §3) and prefer explicit `--context` and `-n` on every command rather than relying on
the current one. Production contexts are Cecilia's only (`authority.md` §1) — never selected by the agent.

## 2. Workload essentials

Each of these has a specific failure it prevents; none is boilerplate.

- **Probes**: readiness and liveness separate, per `observability.md` §1. Add a startup probe for
  slow boots, or liveness kills the pod mid-startup, forever.
- **Resources**: requests always (the scheduler is blind without them); memory limit always (no
  limit means the node dies instead of the pod). CPU limits throttle — set them deliberately, not
  reflexively.
- **Replicas ≥ 2 plus a PodDisruptionBudget** for anything that must stay up, or a node drain takes
  the service with it. Spread across nodes/zones with anti-affinity.
- **`terminationGracePeriodSeconds`** long enough for in-flight requests, and a `preStop` sleep so
  the endpoint is removed from the load balancer before the process stops — the usual cause of
  errors during an otherwise clean deploy.
- **Rolling update** with `maxUnavailable: 0` when the service must not lose capacity.
- **Security context**: non-root, `readOnlyRootFilesystem`, drop all capabilities, `seccompProfile:
  RuntimeDefault`.
- **Image by digest**, `imagePullPolicy: IfNotPresent` with an immutable reference.

## 3. Config and secrets

ConfigMap for non-secret config, Secret for the rest — remembering that a Kubernetes Secret is
base64, **not encryption**: anyone who can read it in the namespace can read the value. Prefer an
external secrets operator or a CSI driver so the value never exists in a manifest or in etcd
unencrypted (`secrets.md` §3). Never `kubectl get secret -o yaml` to "check" a value.

Config change must actually restart the pods — a ConfigMap edit alone does nothing to a running
Deployment. Use a checksum annotation on the pod template so a config change rolls the pods.

## 4. Helm

- `helm lint`, then `helm template` and read the rendered output — the rendered YAML is what ships,
  and the chart is only how it was produced.
- `helm diff upgrade` before every upgrade, and put that diff in the approval quote. It reads live state, so it is itself an A3 read.
- Values files per environment (`values.staging.yaml`), never conditionals on environment names
  buried in templates.
- `--atomic --timeout` so a failed upgrade rolls itself back instead of leaving half a release.
- Pin chart and subchart versions; `helm dependency update` is a change that belongs in the PR.
- Rollback is `helm rollback <release> <revision>` — check the revision exists (`helm history`)
  **before** offering it as the rollback path, and rehearse it (`deploy-and-rollback.md` §4).
- Never `helm upgrade --force`; it replaces resources and drops things you did not intend.

Kustomize instead of Helm: same discipline — `kustomize build` and read the output, overlays per
environment, no patching by hand in the cluster.

## 5. Diagnosing (live reads — A3 in non-prod; in production, commands for Cecilia to run)

```
kubectl get deploy,rs,pod -n <ns> -o wide          what exists, what is ready
kubectl describe pod <pod> -n <ns>                 Events — the answer is usually here
kubectl logs <pod> -n <ns> --previous              why the last container died
kubectl get events -n <ns> --sort-by=.lastTimestamp
kubectl top pod -n <ns>                            pressure
kubectl rollout status deploy/<name> -n <ns>
kubectl rollout history deploy/<name> -n <ns>      revisions available to roll back to
```

Common signatures: `CrashLoopBackOff` → read `logs --previous`, not the current empty log ·
`ImagePullBackOff` → tag, digest or registry credentials · `Pending` → resources, node selector or
an unbound volume (`describe` says which) · `OOMKilled` in the last state → the memory limit, not the
code, until proven otherwise · ready but failing → readiness is lying about a dependency.

## 6. Control plane and etcd (kubeadm / stacked etcd)

- **Measure before concluding.** NotReady flapping, `leader changed`, `request timed out` → read the node's
  kubelet log, `etcd_disk_wal_fsync_duration_seconds` (p99 should stay under ~10 ms), peer RTT, and the
  hypervisor's CPU steal / memory ballooning / disk latency for that VM. Label each cause `[verified]` or
  `[inferred]`; a plan built on an `[inferred]` cause starts with a read-only measuring step.
- **One member unhealthy, quorum intact** → fix or replace that member: `etcdctl member remove` then re-add it
  with a clean data dir (kubeadm: `kubeadm join --control-plane` after `kubeadm reset` on that node). Never
  restore a snapshot for this.
- **Quorum lost** → snapshot restore on **every** member with the same `--initial-cluster` and a new
  cluster token, all started together. A restore on one member alone forks the cluster.
- **Snapshots** hold every Secret: `chmod 0600`, verify with `etcdctl snapshot status`, copy off the node
  before any risky step. Hypervisor snapshots of control-plane VMs are rolled back all together or not at
  all (never one master alone).
- Taking or copying a snapshot, `member remove/add`, `kubeadm reset` and VM changes are A3 each; in
  production they are commands for Cecilia to run.

## 7. Checklist

- [ ] Context and namespace explicit in every command and every approval quote
- [ ] Probes separate and correct; startup probe where boot is slow
- [ ] Requests set, memory limit set; replicas + PDB for anything that must stay up
- [ ] Graceful shutdown: grace period and preStop
- [ ] Non-root, read-only fs, capabilities dropped
- [ ] Image by digest
- [ ] Secrets not plain in manifests; config changes actually roll the pods
- [ ] `helm diff`/`kustomize build` output read and included in the approval
- [ ] Rollback revision confirmed to exist and rehearsed
