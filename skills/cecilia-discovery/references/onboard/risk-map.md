# Risk map — where this system is most likely to hurt

Produced at K6, ranked, every row carrying evidence. This is often the single most valuable output of
an onboarding pass: Cecilia may not read all seven documents, but she will act on this one.

## 1. What to look for

| # | Risk | How it shows up in a survey |
|---|---|---|
| 1 | **Money / stock / points touched without a mechanism** | arithmetic on balances with no transaction, no locking, no idempotency key; float money types |
| 2 | **Check-then-act races** | uniqueness or state checked in code, then written — with no DB constraint behind it |
| 3 | **No tests where change is frequent** | high git churn ∩ zero coverage — this is where the next incident comes from |
| 4 | **No tests where the blast radius is large** | shared modules, auth, the error catalog, anything imported everywhere |
| 5 | **External calls inside transactions** | a partner timeout holding a DB lock; look in every service with an SDK import |
| 6 | **Secrets in the repo or in logs** | committed `.env`, literals that look like keys, whole-object logging near auth or payment |
| 7 | **EOL / unmaintained dependencies** | last release date, known advisories — research it (`common/capabilities.md`), do not guess |
| 8 | **Single points of knowledge** | a module one person has touched for two years (`git shortlog -sn -- <path>`) |
| 9 | **Frozen critical code** | untouched for years, imported everywhere, no tests: nobody dares, so it never improves |
| 10 | **Silent failure paths** | empty catch, `catch → return null`, swallowed promise rejections, consumers with no DLQ |
| 11 | **Undocumented external contracts** | endpoints or events consumed by parties you cannot see; changing them is invisible until it breaks |
| 12 | **Environment coupling** | non-production code paths that can reach production data, shared databases, one credential for all environments |

## 2. Row format

```markdown
| # | Risk | Evidence | Likelihood | Impact | What it would cost to find out more | Suggested owner |
|---|---|---|---|---|---|---|
| R-02 | balance update is read-compute-write with no lock or version column | `wallet.service.ts:64-79` [verified from code]; `wallets` has no version column [verified at runtime] | H — two concurrent top-ups are plausible in normal use | H — money wrong, silently | one concurrency test against staging, ~half a batch | cecilia-test then cecilia-dev-be |
```

Likelihood and impact are stated with a reason, never as bare letters. "H" with no sentence behind it
is a feeling.

## 3. Ranking

Order by **impact × how quietly it fails**. A loud failure (crash, 500) is cheaper than a quiet one
(wrong number written to the database, a message silently dropped): the loud one gets found, the quiet
one gets found by a customer months later, with no way to reconstruct what happened.

## 4. What this section must not become

Not a refactor wish list. Every row names a **failure**, not a preference — no "this could be cleaner",
no architecture opinions, no style. If a row cannot state what goes wrong and for whom, it belongs in
the report's observations, not in the risk map. The risk map's authority comes from every row being
something Cecilia would genuinely rather know than not know.

## 5. Handing it on

Each row carries a suggested next step, not a fix: a test that would confirm it (`cecilia-test`), a
review that would judge it (`cecilia-review`), a plan task to address it (`cecilia-plan`), or an
experiment that would answer an `[unknown]`. This skill never fixes anything itself, and a risk map
that reads like a to-do list invites exactly that.
