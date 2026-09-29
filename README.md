# Cecilia v20 — đội agent cho solo dev: orchestrator chỉ điều phối, nhiều agent song song, có kiểm soát

Bản 20.2.0 · 2026-09-29 · **Claude Code** · **Antigravity** · Windows / macOS / Linux · chỉ cần **uv** (uv tự lo Python).

Bạn giao task, **chọn phương án làm việc**, xem diff, **tự push / mở PR / merge / deploy**. Orchestrator là luồng chính
của host: nó chỉ lập workflow và giao việc — dev, test, review, DBA, DevOps, người dùng API là các agent riêng, chạy
song song khi việc độc lập. Mọi thứ ở máy bạn: **không đưa gì ra khỏi máy**, **không một file Cecilia nào trong dự án**.

## Cài và dùng — 3 lệnh

```bash
# 1. Một lần mỗi máy (cần uv: https://docs.astral.sh/uv/ — Windows: winget install astral-sh.uv)
uv tool install git+https://github.com/<you>/cecilia-skills@v20.2.0

# 2. Một lần mỗi dự án: tạo workspace cạnh dự án (hỏi trước khi ghi; dự án không bị đụng tới)
cecilia init D:\projects\shop            # → D:\projects\shop.cecilia\

# 3. Làm việc: mở WORKSPACE (không mở dự án)
cd D:\projects\shop.cecilia && claude    # Claude Code — luồng chính là cecilia-orchestrator
cecilia open shop --agy                  # Antigravity CLI — chạy agy TRONG workspace (không chạy từ home)
```

Lệnh hằng ngày: `cecilia status` · `cecilia doctor` · `cecilia mode controlled` · `cecilia approve <plan> --task T-B01` ·
`cecilia flow team` · `cecilia rules list` · `cecilia push -u origin <nhánh>` (bạn push) · `cecilia upgrade` · `cecilia help`.
Chi tiết: `docs/INSTALL.md`. Sau khi cài: `docs/HOST-SMOKE.md`. Từ v19.2 lên: `docs/MIGRATION.md`.

## Antigravity (khuyến nghị)

Dùng `agy` ≥ 1.2.7, luôn mở bằng `cecilia open <dự án> --agy` (thêm `--skip-permissions` nếu muốn; guard vẫn
chạy, A3 vẫn hỏi với `antigravity.ask: "force_ask"`). Orchestrator chỉ giao việc qua `invoke_subagent`; gọi
subagent lỗi thì dừng và báo, không tự làm; không có tool MCP (k8s/Proxmox do `cecilia-discovery` /
`cecilia-devops`). Phiếu bầu chỉ tính khi do chính subagent ghi. Model theo vai: `antigravity.models`. Điều khiển
từ LLM khác: `cecilia mcp`. Hướng dẫn đầy đủ (tiếng Việt): **`docs/ANTIGRAVITY.md`**.

## Mới trong V20

| | |
|---|---|
| **Orchestrator chỉ điều phối** | Là luồng chính của host (Claude Code `"agent": "cecilia-orchestrator"`, Antigravity `mainAgent`). Chỉ ghi trong `tensura/` của workspace; không code, không test, không review — kể cả FAST (FAST = giao đúng một vai với brief 3 dòng). Bảo nó "tự sửa đi" thì nó vẫn giao việc. Claude Code: guard chặn nó ghi ra ngoài `tensura/`. |
| **Workflow + phương án** | Từ STANDARD: orchestrator đưa 2–3 phương án khác nhau ở số agent mỗi loại, cách chia việc (`module` / `layer` / `competing`), lens test/review, thời gian + token dự kiến, model từng agent. Bạn chọn; lựa chọn được đóng băng vào `tensura/tasks/<TASK>/workflow.json` (có hash). Chưa chọn thì không agent ghi nào được giao việc. |
| **Song song thật** | Không có trần cấu hình (`parallel.limits.* = null`) — phương án bạn chọn quyết định số agent (ví dụ 3 × dev-be trên các unit rời nhau, 5 × test với lens khác nhau); giới hạn của host vẫn áp dụng (Claude Code: 20 agent cùng lúc). |
| **7 lens test** | `functional` · `integration` · `concurrency-perf` · `security` · `ui` (trình duyệt thật, a11y) · `database` · `infra` (chỉ validate, không apply). Mỗi lens một agent test riêng. |
| **Hội đồng review từ STANDARD** | 2 vòng (vòng 1 độc lập → vòng 2 phản biện chéo ẩn danh) + judge. STANDARD 3–4 lens theo diff; CONTROLLED 5–6 lens + red team; FAST một reviewer. |
| **Vòng sửa tự động, tối đa 3** | Sửa BLOCKER + SHOULD-FIX judge đã CHẤP NHẬN; mỗi vòng test lại lens bị ảnh hưởng và review lại lens có finding trên SHA mới. TRANH CHẤP hoặc hết 3 vòng → dừng, đưa bạn phương án. |
| **Lane** | Mỗi vai chỉ ghi trong lane của nó (`lanes` trong config, sinh từ registry, bạn sửa được). Ra ngoài lane → Claude Code chặn và agent ghi `HANDOFF: needs <vai>`. |
| **Thư mục `rules/`** | Luật riêng của dự án trong workspace: `rules/_project.md`, `rules/roles/<vai>.md`, `rules/flows/<flow>.md`, `rules/lenses/<lens>.md`. Agent luôn đọc (brief nhúng nguyên văn, có hash), chỉ bạn sửa (`cecilia rules …`). Luật chỉ được siết thêm, không nới A3/A4. |
| **Flow `personal` / `team`** | `personal` = cách làm v19.2. `team`: nhận ticket, mẫu tên nhánh/commit/PR, báo leader khi đụng kiến trúc/contract/schema/dependency/bảo mật, giới hạn cỡ PR, xuất docs, đọc comment review. Đổi bằng `cecilia flow team`. |
| **`cecilia-extend` + templates** | Vai thứ 13: dựng vai/flow/lens mới từ `templates/`, validate, đề xuất ở `tensura/extensions/<tên>/`; bạn áp dụng bằng `cecilia extension apply tensura/extensions/<tên>` (chỉ người). |
| **Registry SOLID** | Vai = chuyên môn (skill) · flow = quy trình · agent type = quyền · guard = cưỡng chế · adapter = định dạng host. Thêm vai/flow/lens = **một manifest** trong `registry/` + file guide/skill; bảng và adapter được sinh (`shared/generated/`). |

Giữ nguyên từ v19.2: A0–A4, local-only, guard A3/A4, `cecilia approve` cho CONTROLLED, workspace mode, lessons,
conventions. Giới hạn của V20: `docs/LIMITATIONS.md` (từ 20.2 guard trên Antigravity nhận vai từ dòng brief của từng subagent).

## Workspace — dự án sạch tuyệt đối

```text
D:\projects\
├── shop\                  dự án — chỉ có code của bạn; Cecilia không ghi một file nào vào đây
└── shop.cecilia\          workspace — chỉ ở máy bạn, không phải git remote, không push đi đâu
    ├── CLAUDE.md · AGENTS.md      cho agent biết dự án ở đâu
    ├── .claude\ · .agents\        skills, agents, hook guard (orchestrator = luồng chính)
    ├── .cecilia\                  config, registry.json, mode, approvals, extensions\
    ├── rules\                     luật của dự án — chỉ bạn sửa
    ├── tensura\                   docs, plans, reports, tasks\<TASK>\{workflow.json, run.json, state.md}, backups
    ├── .worktrees\                worktree của dự án khi chạy song song
    └── shop.code-workspace        mở workspace + dự án cùng lúc
```

Guard **chặn** agent ghi file Cecilia vào dự án, chặn mọi push/PR/comment, chặn sửa file điều khiển (`.cecilia/`,
`rules/`, hooks) và — trên Claude Code — chặn orchestrator ghi ngoài `tensura/`, vai ghi ngoài lane, giao việc ghi
khi chưa có workflow đã chọn, vòng sửa thứ 4.

## 13 vai

Bảng đầy đủ (agent type, lane, đọc gì, sinh gì, báo cáo, guide review, file luật) sinh từ registry:
`shared/generated/roster.md`; flow: `shared/generated/flows.md`; lens: `shared/generated/lenses.md`.

| Skill | Vai trò |
|---|---|
| `cecilia-orchestrator` | luồng chính: chọn mode, đưa phương án, đóng băng workflow, giao việc song song, vòng sửa, chỉ ghi `tensura/` |
| `cecilia-discovery` · `cecilia-design` · `cecilia-plan` | as-built / yêu cầu · kiến trúc, contract · plan |
| `cecilia-db` · `cecilia-devops` | database (dự báo, mở rộng, backup/DR) · CI/CD, container, IaC |
| `cecilia-dev-be` · `cecilia-dev-fe` · `cecilia-ui` | code backend · frontend · thiết kế giao diện (**tắt mặc định**) |
| `cecilia-test` | test theo lens, nhiều agent song song |
| `cecilia-review` · `cecilia-api-ux` | review theo lens, chỉ đọc · người dùng API, chỉ đọc code |
| `cecilia-extend` | dựng vai/flow/lens mới, chỉ đề xuất |

## Quyền hạn

| Mức | Nghĩa | Ai quyết |
|---|---|---|
| A0 / A1 | đọc, search web, tra docs / viết docs, báo cáo trong workspace | agent |
| A2 | sửa code/test/config **trong lane, trên nhánh task** | FAST: task bạn giao · STANDARD: sau khi bạn chọn phương án · CONTROLLED: trong G2 scope |
| A3 | hệ thống chung, cài dependency, `git pull`, xoá/huỷ việc, sửa file hạ tầng/migration | agent hỏi đúng lệnh, bạn duyệt từng lệnh |
| A4 | **push, PR/MR, comment**, merge, production, IAM, secret, release, tắt guard, sửa `rules/`, áp extension | chỉ bạn |

## Config — `shop.cecilia/.cecilia/config.json` (bạn sửa tay, agent chỉ đọc)

Khoá mới của V20 (các khoá v19.2 giữ nguyên; `cecilia upgrade` thêm khoá thiếu, không đổi giá trị bạn đã đặt):

```json
{
  "flow": "personal",
  "orchestration": { "orchestrator_writes": "tensura-only", "workflow_required_from": "standard", "options": 3 },
  "parallel": { "limits": { "dev": null, "test": null, "review": null }, "wave_checkin": "auto" },
  "lanes": { "cecilia-dev-be": ["src/**", "app/**", "server/**", "…"] },
  "test": { "lenses": ["functional", "integration", "concurrency-perf", "security", "ui", "database", "infra"] },
  "review": { "panel": { "from": "standard", "reviewers": { "standard": 3, "controlled": 5 }, "rounds": 2 } },
  "fix_loop": { "max_rounds": 3, "severities": ["BLOCKER", "SHOULD-FIX"], "on_exhausted": "options" },
  "rules": { "dir": "rules", "enforce": "gate", "max_bytes_per_file": 2048 }
}
```

Kiểm tra: `cecilia mode --show` và `cecilia doctor`.

## Repo này (cái bạn push lên git)

```text
pyproject.toml   gói uv (lệnh `cecilia`, uv tự cài Python ≥ 3.10, chỉ thư viện chuẩn)
src/cecilia/     CLI: init · open · doctor · upgrade · mode · approve · flow · rules · extension · scaffold · push · …
registry/        manifest JSON: agent-types/ · roles/ · flows/ · lenses/{test,review}/ — nguồn duy nhất của vai/flow/lens
templates/       khung cho vai/flow/lens mới (cecilia-extend, `cecilia scaffold`) và rules/ của workspace
skills/          13 skills (mỗi skill tự đủ: references/common/*, scripts/…)
shared/          core-min (luôn nạp), core, git, parallel, … · flows/ (guide từng flow) · generated/ (bảng sinh từ registry) · scoped/
adapters/        Claude Code / Antigravity — sinh từ registry (tools/build_adapters.py)
guard/           guard + policy.json + doctor + mode/approval/khoá push
tools/           registry · roster · build_adapters · scaffold · setup · install · validate · tokens · guard_corpus · rules.json · evals/
tests/           test hồi quy (`uv run python -m unittest discover -s tests`)
docs/            INSTALL · HOST-SMOKE · MIGRATION · LIMITATIONS · PROMPTS · COMPATIBILITY · EXTENDING · RELEASE · DESIGN-V20
```

Phát triển trên chính repo: `uv run cecilia validate` · `uv run python -m unittest discover -s tests` ·
`uv run cecilia tokens --check`. Trước khi gắn tag: `docs/RELEASE.md`. Thêm vai/flow/lens: `docs/EXTENDING.md`.
Lịch sử thay đổi (kể cả v19.x): `CHANGELOG.md`.
