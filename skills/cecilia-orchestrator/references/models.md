# Model choice per agent

Models are **chosen automatically and shown, never asked separately.** Cecilia's defaults live in
`.cecilia/config.json` `models` (per role: a tier `strongest` | `balanced` | `fast`, a model name the host
lists, or `inherit`) and `consensus.models` (one entry per voter, e.g. `["opus","sonnet","sonnet"]`).
Reuse them; for a role with no entry pick by §2 yourself. Every choice appears on the ONE decision card
(`models`: role, model, why — `references/consensus.md` §7), where she may override any of them in her
answer; that is the only place models are asked about. There is no silent default: the card shows each.

Models are set **per agent inside each workflow option** (`units[].model`, test lens `model`, review
`model`; `assets/options-template.md`). Defaults: orchestrator, minutes writer and redteam strongest; dev
and test balanced (strongest for a CORE unit); the rest per §2. **Consensus voters** (planners,
diagnosers, review voters) get *different* models when the host lists more than one — independence
beats a uniform top tier; one model only → the card says `independence: weak`. `workflow.py brief` puts
the chosen model in the brief's second line; launch the agent with that model.

## 1. Get the real list first

Before choosing, read the model options the host actually offers (in Claude Code: the `model` field of
the sub-agent tool). **Never invent or guess a model name**, and never offer one the host does not
list. The table below is what is current at the time of writing; when it disagrees with the host,
the host wins and the table is stale.

| Tier | Typical choice | Strong at |
|---|---|---|
| Strongest | the largest model the host lists | ambiguity, contradictions, architecture trade-offs, finding what is *missing* |
| Balanced | the mid-size model | executing a clear brief, volume of code and tests |
| Fast | the smallest model | mechanical passes with no judgement |

Offer only names the host actually lists, in the host's own spelling. `inherit` (the session's model)
is always a valid answer.

## 2. Recommendation per role

| Role | Recommend | Why | What goes wrong one tier down |
|---|---|---|---|
| cecilia-discovery | **strongest** | Its failure mode is a confident wrong description of a live system, which every later role inherits without suspecting it. Judging what a label has earned — verified vs inferred vs unknown — is exactly the judgement weaker tiers skip. | Smooth, plausible documentation of flows that were never traced; `[inferred]` quietly written as fact. |
| cecilia-design | strongest | Its whole job is spotting what the brief does not say and what two decisions do to each other. | Plausible docs with silent gaps; the cost lands in dev, three steps later. |
| cecilia-plan | strongest | Traceability and dependency order: one missed link and a batch blocks another mid-run. | Batches that look tidy but share files, or an ID that lands nowhere. |
| cecilia-review | strongest | An independent judge that misses the defect is worse than no review — it adds false confidence. | Style comments instead of failure scenarios. |
| cecilia-dev-be / dev-fe | balanced, **strongest for CORE** | On a plan + LLD that settle the behaviour, this is execution. | Fine for CRUD. For money/state machines/concurrency/idempotency (`cecilia-design`'s CORE test) use strongest. |
| cecilia-db | **strongest** | Its mistakes land on data that already exists: a lock on a live table, a wrong partition key, a constraint dropped for speed. Reading plans and judging lock levels is judgement, not execution. | Plausible indexes that serve no query; DDL whose lock level was never checked. |
| cecilia-ui | strongest for new flows and design systems, balanced for screen additions | Completeness of states and accessibility is where it fails, and nobody downstream catches a missing state until users do. | Happy-path screens; contrast eyeballed instead of measured. |
| cecilia-test | balanced | Test cases come from AC/LLD/API ids; deriving them is mostly mechanical. | Happy-path-only suites; raise a tier when the batch is CORE or the docs are thin. |
| cecilia-devops | **strongest** | It reads live state, judges blast radius and composes commands Cecilia will run against real environments. A plausible-looking wrong command is the expensive failure mode here, and the feedback loop is an outage. | Confidently-remembered flags that no longer exist, a missed `forces replacement` in a plan, a rollback path that was never actually checked. |
| cecilia-orchestrator | **strongest** (v20) | It transcribes the merged plan into options, anonymizes findings and keeps the run on the files — one leaked author or wrong wave costs every agent in it. | Overlapping units, a wrong lens choice, a panel that leaks who wrote what. |
| consensus voters · minutes writer · redteam lens | **mixed** voters (strongest + balanced), **strongest** minutes and redteam | Voters must disagree for the right reasons — different models make independent errors; the minutes drive the fix loop; redteam must find what the others did not. | Three copies of one blind spot; minutes that drift from the tally; attacks that stay on the happy path. |
| cecilia-review (verify mode) | **strongest** | It is the last thing standing between a wrong number and Cecilia acting on it, and its failure mode is silent — a PASS that should have been a FAIL. | Checking plausibility instead of the source; missed omissions. |
| mechanical pass | fast | Inventory, status collection, formatting checks. | — no role skill runs here; this skill does not do such passes itself either (golden rule 1). |

Two rules of thumb behind every choice (one of them is usually the card's why):

- **Spend where the mistake is found latest.** A weak design or plan is paid for by every role after
  it; a weak dev agent is caught by test and review the same day.
- **Docs quality decides dev's tier**, not the feature's size. Thin or contradictory docs turn dev
  into a judgement job.

## 3. Showing and overriding (on the card only)

The card's `models` rows carry the recommendation and the "what goes wrong" line of §2 as the why, e.g.
`cecilia-dev-be (B-01) · opus · CORE: stock is deducted before payment confirms`. Cecilia overrides in her
answer ("dev dùng sonnet", "tất cả opus"): put it into `options-input.json`, re-run `workflow.py options`
and `decision`, then record her answer (`consensus.md` §7). Never ask a model question on its own — not
per role, not on resume, not on a loop. On a **loop** (`presets.md` §4) a repeat failure is a reason to
raise a tier on the next card.

## 4. Recording and honouring

- Write the model into run log §1 and into every turn row in §3. A bad output weeks later must be
  traceable to the tier it ran on.
- Put the model in the brief header too, so the report carries it.
- **Requested model unavailable** → do not substitute silently: put the substitute on the card (or, after
  the answer, in the next report) and record `model: <actual> (requested <X>, không khả dụng)` in the run log.
- **The host cannot set a model at all** (`fallback.md`) → say so once, record
  `model: session default (requested <X>)`, and warn her where that matters — a design, plan or
  review step she wanted on the strongest tier.
