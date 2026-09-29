# Frontend security — the DOM, tokens, the bundle, and what never gets logged

Everything shipped to the browser is public and modifiable. The client's job is to make the **honest**
path safe and pleasant; it is never the enforcement point. Every rule below assumes the server still
checks — see the authZ matrix in `tensura/docs/system/security.md` for who may do what.

## A. What never reaches the DOM

- **Never render user or server text as HTML.** No `dangerouslySetInnerHTML`, `v-html`,
  `innerHTML`, `document.write` with anything that did not come from a trusted, sanitized source. If
  rich text is genuinely required by the design, it is sanitized with a maintained library
  (DOMPurify), server-side if possible, and the decision is recorded — it is not a component-level
  choice.
- **URLs are injection surfaces.** Validate any href/src that comes from data: allow `http(s)` and
  relative only; `javascript:`, `data:` and `blob:` from user input are rejected. External links get
  `rel="noopener noreferrer"`.
- **Never build a component from a server-supplied component name or template string.** Map an
  identifier to a fixed, local registry instead.
- `<iframe>` of third-party content is sandboxed, or it is a question for Cecilia.
- Content-Security-Policy is a real control, not a header to copy: no `unsafe-inline`/`unsafe-eval`
  unless the framework forces it and the exception is recorded. Adding or widening a CSP directive is
  a change that needs approval.

## B. Tokens, session and storage

| Where | Verdict |
|---|---|
| httpOnly + Secure + SameSite cookie, set by the server | **best** — script cannot read it |
| in memory (module variable, store) | acceptable; lost on reload, refresh flow restores it |
| `localStorage` / `sessionStorage` | only if the docs already chose it; any XSS reads it. Say so once in the report rather than silently adopting it |
| the URL, a query param, a log, an analytics event | **never** |

- The storage choice belongs to `security.md` / the FE design. If neither settles it, ask (F2) —
  do not pick it inside a component.
- Logout clears every client copy: memory, storage, cached queries, and any in-flight refresh.
- Never decode a JWT to decide what a user *may* do; decode only to display or to know it expired.
  Permission comes from the server's response, and `403` is the authority.

## C. Client validation mirrors, never replaces

- Client rules exist for **speed of feedback**. The server stays the authority and its `errorCode`
  drives the final message (`api-contract.md` §3).
- Never contradict the server: if the client accepts what the server rejects, the user hits a dead end;
  if the client rejects what the server accepts, a legitimate action becomes impossible. A mismatch
  found while building is a finding, not something to "fix" on the client.
- **Hidden is not forbidden.** Hiding a button for a role is UX, never a permission control — the
  endpoint must reject it too. If it does not, that is a security finding for `cecilia-review` (security mode).
- Bound every input the same way the contract does: lengths, ranges, enum values, array sizes, file
  mime + size. Uploads are validated client-side for *feedback* and always re-checked server-side.

## D. Nothing secret is in the bundle

- Anything reaching the browser is public. `NEXT_PUBLIC_*`, `VITE_*`, `REACT_APP_*` and every value
  inlined at build time are **published**, not configured.
- API keys for third-party services that bill or grant write access do not belong in a frontend build;
  they go behind a backend route. If the design implies one in the client, stop and ask.
- Source maps in production expose the source; publishing them is a decision, not a default.
- A new dependency is a supply-chain change and an A3 action (`common/core.md` §2) — it ships to every
  visitor's browser.

## E. Logs, analytics and error reporting

- **No PII, no tokens, no full payloads** in `console`, analytics events or error reports: no email,
  phone, address, full name, card data, national id, auth header, session cookie, password field.
  Masked forms where something is needed (`u***@x.com`, `****1234`).
- Error reporting (Sentry-style) is configured with scrubbing **before** it is enabled, and enabling it
  at all is a tooling proposal (`common/capabilities.md`), never an autonomous adoption.
- What is worth reporting: the `errorCode`, the `requestId` (`api-contract.md` §4), the route, the
  `SCR` id, and whether it was the mock or the real API. That set makes a bug reproducible; a raw
  payload dump does not, and it leaks.
- `console.log` left in shipped code is noise and sometimes a leak — remove it; use the framework's
  logger or a debug flag if something must stay.
- Every route has an error boundary so one failing component does not blank the app, and the boundary's
  fallback is a **designed state**, not a bare message.

## F. Third-party scripts

Each one runs with full access to the page, so each one is a decision: who owns it, what it reads, can
it be loaded with `defer`/`async` from a pinned version with Subresource Integrity, and what breaks if
it fails. Adding one is a hard stop — it changes the security posture and the performance budget at
once (`common/capabilities.md`).
