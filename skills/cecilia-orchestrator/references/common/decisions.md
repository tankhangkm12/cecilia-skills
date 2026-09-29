# Asking, options and research — how decisions reach Cecilia (common v20)

<!-- common v20 — canonical copy in shared/, synced into every skill by tools/sync_common.py. Do not edit a copy. -->

Cecilia decides; a role's job is to make each decision easy to get right: researched, compared on
numbers, several real options, a recommendation kept separate — and asked as few times as possible.

## 1. Rules for asking

1. **Homework first.** Read the docs, plan, decisions, reports and repo that are reachable, and research
   (§7). State what you found ("Đã đọc: …"); never ask what a file already says. **Facts are measured,
   never asked** — a path, version, config value, behaviour or cluster state is read or run and labelled;
   only preferences and risk choices are questions.
2. **Sort before asking.** For each question: would my options or recommendation change depending on
   another unanswered question? Yes → **dependent**, ask it alone, after the one it depends on. No →
   **independent**, it goes in one grouped gate.
3. **Every question has options** (§6) with gain/cost and a bolded recommendation tied to this project.
   Never an open "how do you want it?".
4. **Every grouped gate is answerable in one line.** `theo đề xuất hết` must be a complete, valid answer.
   Cap: 6 rows; more → two gates, the blocking one first.
5. **Material scope questions first.** Do not ask for formal scope metadata in FAST/STANDARD just to fill
   a template.
6. **Stop after asking.** No work in the meantime that the answer could invalidate.
7. **Use the host's question tool if it has one** — one call for the whole gate, one question per row.

FAST often asks nothing; STANDARD asks only real unknowns; CONTROLLED uses the full gate discipline.
**In an orchestrated task (from STANDARD) a role never asks Cecilia directly:** its questions go into its
report (`PENDING QUESTIONS`, or the merged plan's open points), and the orchestrator puts them on the task's
ONE decision card (`tensura/decisions/<TASK>.md`, defaults pre-selected, one reply answers all).

## 2. Grouped gate

```
**[cecilia-dev-be · D1 · SHOP-42 B-01] Gate 1/~2 — 3 câu độc lập**

Đã đọc: plan §B-01, order-design.md, order-api.yaml. Đã tìm: <sources, §7>. Các file không trả lời những câu dưới.

| # | Câu hỏi | Vì sao quan trọng | A | B | C | Đề xuất |
|---|---|---|---|---|---|---|
| 1 | Base branch? | quyết định PR đích | `develop` | `epic/SHOP-42` | `main` | **B** — epic đang mở |
| 2 | Tiền lưu dạng gì? | sai là mất tiền | `decimal(19,4)` | `bigint` minor units | `float` (loại: sai số) | **B** — không sai số, cộng nhanh |

Trả lời gọn: `1B 2B`, hoặc `theo đề xuất hết`.
```

## 3. Dependent question — the full option table

```
**[cecilia-design · S2 · order] Q2/~3 — Chống ghi đè trạng thái đơn đồng thời bằng gì?**

Vì sao: <1–2 dòng>. Đã tìm: <nguồn, ngày>.

| Tiêu chí (cùng cho mọi phương án) | A · optimistic lock | B · conditional update | C · SELECT … FOR UPDATE |
|---|---|---|---|
| Đúng khi 2 request đồng thời | có (retry) | chỉ cho chuyển trạng thái | có |
| Chi phí / độ trễ (số) | +1 cột, retry ~x% ở tải y | 0 | giữ khóa ~z ms |
| Độ phức tạp code | trung bình | thấp | trung bình |
| Rủi ro | retry storm | bỏ sót cập nhật ngoài trạng thái | deadlock nếu sai thứ tự |
| Nguồn | <link, ngày> | <link> | <link> |

**Tôi nghiêng về B** vì <lý do theo dự án>. Trả lời A/B/C hoặc mô tả cách của bạn.
```

## 4. Answers

- Record every answer where the skill says (decision log, plan, report) with the date and "decided by:
  Cecilia" — including rows answered by `theo đề xuất hết`.
- "Tùy bạn" / "không biết": ask once more with the concrete consequence of each option. Still no
  choice → take the recommendation, label it `[agent-chosen — needs review]`, list it first in the next
  report. Never let an agent choice look like her decision.
- Partial answer → re-ask only the missing rows. An unanswered row is not approval.
- An answer that contradicts the docs or an earlier decision → show both, ask which wins.

## 5. Running as a sub-agent

A sub-agent cannot reach Cecilia. It does all work possible before its gate, returns its questions
already sorted (one independent group + the dependent ones, each with options, research and a
recommendation), and stops. The orchestrator relays them. Never pass a gate by guessing.

## 6. Options — more than one, honestly compared

When a real choice exists (technology, design, data model, algorithm, infrastructure, trade-off):

1. **At least three options**, when three genuinely exist: the obvious one, a meaningfully different one,
   and — when it applies — **keep things as they are / do nothing**. Two only when the choice is truly
   binary; say so. Never pad with a strawman: an option you would never recommend states why it was
   rejected in one line.
2. **Same criteria for every option**, in one table: correctness/risk, measured or projected numbers
   (latency, RAM, storage, cost — `numbers.md`), effort as scope (files, modules, migrations — never
   hours), operability, reversibility, fit with the repo and team.
3. **Numbers over adjectives.** "Nhanh hơn" is not a criterion; "p95 40 ms vs 180 ms at 200 rps
   [projected]" is.
4. **Recommendation separate from the comparison**, with the reason tied to this project, and what
   would change the recommendation ("nếu traffic > 5k rps thì chọn C").
5. **Bias check** before sending: Am I recommending the first idea, the familiar tool, or the one already
   in the code only because it is there? Did I search for how others solved it? Is there a cheaper
   option I dismissed without numbers?

Low-stakes conventions may be one "approve this table" question. FAST work states the one sensible way.

## 7. Research — search before proposing

Search the web (the host's search/fetch tools) **before** proposing when the answer depends on the world
outside the repo:

- current versions, deprecations, breaking changes, security advisories, licences;
- how a library, engine or platform actually behaves (official docs for the version in use);
- existing solutions and prior art ("how do teams solve X with Y"), benchmarks, known pitfalls (issue
  trackers, postmortems, maintainers' posts);
- prices and limits of managed services (dated).

Rules: official docs, release notes and source code first; community posts as supporting evidence;
record each source as `title — URL — date read` in the report or decision log; mark claims you could
not source `[unverified]`; never paste secrets, customer data or private code into a search. No web
access on this host → say so once and label version/behaviour claims `[unverified]`.

## 8. Record

Decisions go to `tensura/docs/DECISIONS.md` as `D-nn` with: question · options compared (table or
link) · chosen · decided by · date · sources · what would reopen it.
