# Supply chain — dependencies, builds, and what ships

## 1. Counted, never estimated

Run a real scanner and report counts with the tool, its version and the date (`common/evidence.md`):

| Ecosystem | Usual tools |
|---|---|
| Node | `npm audit`, `osv-scanner`, `pnpm audit` |
| Python | `pip-audit`, `osv-scanner`, `safety` |
| Java | `mvn dependency-check`, `gradle dependencyCheckAnalyze`, `osv-scanner` |
| Containers | `trivy image`, `grype` |
| Any | `osv-scanner` over the lockfile |

No scanner available → say so, label `[unverified]`, and propose one (`common/capabilities.md` — it is a
tool proposal with an access scope, and it needs Cecilia's approval like any other).

```
dependency findings — 3 critical, 11 high, 26 moderate — npm audit (npm 10.8, lockfile v3), 2026-09-20 [verified]
```

## 2. Triage — a CVE list is not a finding list

A raw scanner report is noise until each item answers three questions:

1. **Is the vulnerable path reachable from our code?** A parser flaw in a dev-only build tool is not
   the same as one in the request path. Say which, and how you determined it.
2. **Can the stated attacker reach it?** (from the threat model's actors)
3. **What does the fix cost?** patch version · minor bump · major bump with breaking changes · no fix
   available, needs a mitigation.

Report only what survives those three, ordered by reachable-and-exploitable first. Everything else
goes in a counted line, not in individual rows.

## 3. Beyond CVEs

| Risk | What to look for |
|---|---|
| Unmaintained | last release date, open critical issues, single maintainer, archived repo |
| Typosquats and confusion | package names one character from a popular one; an internal name also on the public registry |
| Install-time execution | postinstall scripts in the tree |
| Lockfile integrity | lockfile committed, integrity hashes present, no `latest` or floating ranges in production deps |
| Licence | anything copyleft in a product that ships; anything with no licence at all |
| Build-time access | what the CI can reach while building (`cecilia-devops` owns the pipeline; this is a finding to hand over) |
| Base images | pinned by digest, still receiving updates, non-root |
| Vendored code | copies nobody updates, and nobody scans |

## 4. What ships

The bundle and the image are part of the supply chain:

- **Frontend**: no secrets, no internal URLs, no source maps in production unless deliberate, no
  admin-only code paths shipped to everyone (`cecilia-dev-fe` measures the bundle; you read what is
  *in* it).
- **Backend image**: no build secrets in layers, no `.env`, no `.git`, no test fixtures with real data.
- **Both**: what the artifact reveals about internal structure — endpoint lists, feature flags,
  employee names in comments.

## 5. Handover

Every finding names the role that fixes it: a dependency bump is `cecilia-dev-be`/`cecilia-dev-fe`
(and a dependency change needs Cecilia's approval — `common/core.md` §2); a base image or CI permission
is `cecilia-devops`; a policy (who may add dependencies, what licences are allowed) is Cecilia's.

This skill never bumps a dependency itself, and never "just tries" an upgrade.
