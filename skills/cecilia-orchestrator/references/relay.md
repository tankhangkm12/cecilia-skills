# Relaying questions from an agent to Cecilia

A sub-agent cannot talk to Cecilia. It stops at its gate and returns `PENDING QUESTIONS`, already
sorted into one independent group and the dependent ones (`common/decisions.md` §5). Carrying those
questions across is this skill's main job, and the one place where it may not be a passive pipe.

In a wave, several members return their questions at the same time. That is the case this file is
built for: triage all of them together, merge duplicates across members, then ask the whole wave's
independent questions in **one** grouped gate. Three agents stopping at once must cost Cecilia one
gate, not three.

Before O2 there is no relay: every preference and risk choice goes on the task's ONE decision card
(`references/consensus.md` §7). After it, a member's real preference/risk question re-issues that card
(`workflow.py decision`) or, when the script cannot carry it, uses the grouped gate below in the card's
shape — defaults pre-selected, one reply answers all. A question about a **fact** is never relayed.

## 1. Triage before relaying — never forward blindly

For each returned question, in order:

| Check | If yes |
|---|---|
| Already answered in run log §4, `tensura/docs/DECISIONS.md`, the plan, or an earlier report? | **Do not relay.** Send the decision back in the re-launch brief, with its source path, and note in run log §6 that the agent missed it. Two misses by the same role → say so to Cecilia; the brief's Read block is probably pointing at the wrong file. |
| Answered by a file the agent simply did not read? | **Do not relay.** `common/decisions.md` §1. Re-launch with that path added and say which file answers it. |
| Not actually blocking this step? | Hold it. List it in run log §5 and raise it when the role that needs it runs. |
| A fact the agent (or another role) can measure — a file, a config value, a command's output, a cluster state? | **Do not relay.** Facts are measured, never asked: re-launch it (or dispatch the role that may read it) with "measure it, label the evidence". |
| Two agents asking the same thing? | Merge into one question, attribute both. |
| No options, or an open "how do you want it?" | Send it back to the agent, or add the options yourself **only** as presentation of the agent's own analysis. Never invent a technical option the agent did not raise — that would be the orchestrator designing (golden rule 1). |

Report the triage in one line at O5: `W5 · 7 câu từ 3 agent — 2 đã có quyết định, 1 hoãn, 2 trùng gộp lại, còn 3 câu.`

## 2. Asking

`common/decisions.md` §2–3 is binding, and the agent has already done the sorting. Two shapes, in this order.

**The grouped gate — every independent question in the wave, one message.** Keep each agent's own
options and recommendation; it did the reading. Mark which agent asks each row:

```
**[cecilia-orchestrator · O5 · SHOP-42 · W5] Gate 1/~2 — 3 câu độc lập từ 2 agent**

| # | Agent | Câu hỏi | Vì sao quan trọng | A | B | Đề xuất |
|---|---|---|---|---|---|---|
| 1 | dev-be | Base branch cho B-02? | quyết định PR đích | `develop` | `epic/SHOP-42` | **B** — epic đang mở |
| 2 | dev-fe | Mock server chạy ở port nào? | FE verify trước khi ghép thật | 4010 | 3001 | **A** — mặc định của Prism |
| 3 | test | Ngưỡng coverage cho batch này? | quyết định lúc nào TEST-B02 xong | 70% | 80% | **A** — bằng repo hiện tại |

**Trả lời gọn:** `1B 2A 3A`, hoặc `theo đề xuất hết`, hoặc nêu lựa chọn của bạn cho từng dòng.
```

**Then the dependent ones, one per turn**, each with the agent's full trade-off table:

```
**[cecilia-orchestrator · O5 · SHOP-42 · W5 · cecilia-dev-be] Q1/2 — Đơn hết hàng giữa chừng thì sao?**

Từ cecilia-dev-be (B-02). Vì sao quan trọng: <1–2 dòng của agent>.

| # | Option | Gain | Cost |
|---|---|---|---|
| A | ... | ... | ... |
| B | ... | ... | ... |

**cecilia-dev-be nghiêng về A** vì <lý do của agent>.
Trả lời A/B, hoặc nêu lựa chọn của bạn.
```

If the orchestrator's own state-reading disagrees with the agent's framing — the plan says something
else, an earlier report already went the other way — add one line under the table:
`Ghi chú điều phối: plan B-02 §3 nói ngược lại; xem <path>.` One line, facts only, no opinion on the
technical choice.

Order: blocking first, then by how much later work depends on them. A question that blocks two
members of the wave outranks one that blocks one.

**Never promote a dependent question into the gate to save a turn.** If the agent marked it dependent,
it is dependent — the agent read the files and the orchestrator did not. Re-sorting an agent's
questions is the orchestrator making a technical judgement (golden rule 1).

## 3. "Tuỳ bạn" / "không biết"

`common/decisions.md` §3, with one addition: the fallback answer is **the agent's** recommendation, never
the orchestrator's.

1. Ask once more with the concrete consequence of each option.
2. Still no choice → take the agent's recommendation, record it in run log §4 as
   `[agent-chosen — needs review]`, and put it first in the next report and in the O6 close.
3. Never let it read as settled. The re-launch brief carries it as
   `AGENT-CHOSEN (chưa duyệt): <answer>` so the role knows it is standing on soft ground.

## 4. Recording

Every answer goes into run log §4 immediately: date, which agent asked, the question, the answer,
`decided by: Cecilia` or `[agent-chosen — needs review]`. The role skill will also record it in its
own place (decision log / plan / report) — the brief tells it to. Both, not either.

## 5. Re-launch

Once every blocking question is answered: re-launch **only the members that asked**, with the answers
block (`brief-more.md` §6), same scope, same model unless changed. New run-log row each — a
re-launch is a new turn, not an edit of the old one.

Members of the same wave that returned clean are not re-launched and not re-checked; their output
stands. Their worktrees stay in place until the wave closes, because the re-launched member may still
write into paths next to theirs.

The wave is not closed, and wave N+1 does not start, until every re-launched member has returned and
passed the §"Between waves" checks. An answer that changes scope rather than a detail is not a
re-launch at all: go back to O2 and re-approve the wave plan, because a changed scope changes the
write sets the grouping was computed from.

## 6. BLOCKED is not a question

`STATUS: BLOCKED` means the agent cannot proceed at all — no access to a doc, environment down, the
plan contradicts itself, a hard stop was hit. Do not relay it as a multiple-choice question. Report
it plainly: what is blocked, the evidence, and 2–3 ways forward including "the role that owns this
fixes it first" (a contradictory plan is `cecilia-plan`'s to fix, not dev's). Then ask what to do.

The run stops until it is resolved. Run log status → `BLOCKED`. One blocked member blocks its wave,
not the other members' completed work — let the rest of the wave finish and report, then stop.

## 7. Nobody is answering

If the orchestrator itself runs unattended (scheduled, background): do not guess on Cecilia's behalf
and do not launch the next wave. Let the current wave finish, write everything into the run log —
config, turn log, every open question with the agent's options and recommendation, the exact point
where the run stopped — keep its worktrees and branches as they are,
set status `WAITING_FOR_CECILIA`, and stop. A gate is never passed because nobody replied
(`common/decisions.md` §5).

Auto-continue (`parallel.wave_checkin: auto`) does not change this. `auto` skips the *check-in* after a
clean wave; it never answers a question, and a wave with a pending question is never clean.

## 8. Action quotes are relayed verbatim

Push and PR are not quotes: they are A4 for agents (local-only, `common/git-handoff.md` §1). Collect the
push + `gh pr create --draft … --body-file …` commands from the role reports into the one copy-paste
block of the finish (`references/workflow.md` O5); never relay them as questions.

When a member returns an A3 action quote (`common/core.md` §5.3) — a staging apply, a
dependency — show it to Cecilia **exactly as the member wrote it**. Quotes that are ready at the same time
(a parallel wave) go in **one numbered message**, each quote complete and verbatim; Cecilia answers per
item (`1y 2y 3n`, `core.md` §5.3). Never answer one yourself, never turn them into one blanket approval,
never treat an earlier yes as covering a new quote, never under `auto`; an unanswered item is a no. After her yes, re-launch the member with `APPROVED ACTION: <the exact command> — Cecilia, <time>` and record the
result. An A4 request (merge, production, secrets, release) is never relayed as a question: it is
handed to Cecilia as a prepared command for her to run herself.
