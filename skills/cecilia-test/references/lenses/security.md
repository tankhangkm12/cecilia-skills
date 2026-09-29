# Lens: security (cecilia-test v20)

Brief header `LENS=security`. Shared lens rules (files, isolation, report, lane): `../workflow.md` §Lenses.

## Attacks
Who can do what to whose data: authentication, authorization and ownership, hostile input, leaks of
secrets or personal data, abuse of a legitimate feature.

## Oracle
The authZ matrix and threat model (`tensura/docs/.../security.md`, design's `authz-matrix`) · API contract
(documented 401/403/404 per role) · NFR security items · OWASP ASVS level Cecilia chose.

## Techniques
- **AuthZ / IDOR:** every endpoint × anonymous, wrong role, **other user's / other tenant's resource**;
  expect the documented 404/403, never data. Ids in path, query, body and nested objects.
- **AuthN:** missing, expired, tampered, wrong-audience token; logout and reuse.
- **Injection:** SQL/NoSQL/command/template probes on every parameter incl. sort, filter and headers;
  **mass assignment** (extra fields like `role`, `ownerId`, `price`).
- **Secrets and data exposure:** responses, errors (stack traces, SQL), logs and headers carry no secret
  or unnecessary personal data; security headers and CORS as documented.
- Rate limits on login/OTP, file upload type/size, dependency audit (`npm audit`, `pip-audit`) if available.
- Map each finding to OWASP Top 10 / ASVS; severity Critical/High for any cross-user data access.

## Files
`<repo test root>/security/...` or suffix `.security`. Synthetic users per role and tenant, created by the
test, never real accounts.

## Environment
Local app and DB only: own ports and DB from RUNTIME. Staging or shared targets are A3; production and
third parties never.

## Report
`tensura/reports/<TASK>/test-security.md`: matrix `endpoint · anon · wrong role · other owner · result`,
probes run, OWASP mapping, BUG table (`BUG-security-nn`). Redact tokens and personal data in evidence.

## Never
Test production, third parties or real data · run exploits/fuzzers against anything not local · keep a
working exploit beyond the minimal repro · fix a hole (`HANDOFF: needs cecilia-dev-be`). Real data
exposure found → stop and report at once.
