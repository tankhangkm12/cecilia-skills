# Mở rộng bộ Cecilia — v20, quanh registry

Từ v20, vai (role), flow và lens **không còn nằm rải trong bảng viết tay**: mỗi cái là **một manifest JSON** trong
`registry/` cộng file skill/guide của nó. Bảng (`shared/generated/roster.md`, `flows.md`, `lenses.md`) và agent của
2 host (`adapters/`) đều được sinh ra. Schema đầy đủ: `registry/README.md`.

| Lớp | Là gì | Ở đâu |
|---|---|---|
| Vai = chuyên môn | skill: thẻ `SKILL.md` + `references/` | `skills/cecilia-<tên>/` + `registry/roles/cecilia-<tên>.json` |
| Flow = quy trình | 7 bước `intake … finish`, settings | `registry/flows/<tên>.json` + `shared/flows/<tên>.md` |
| Lens = góc test/review | khi nào chọn, hướng dẫn | `registry/lenses/{test,review}/<tên>.json` + guide |
| Agent type = quyền | ghi `lane` / `tensura-only` / `none`, tool từng host | `registry/agent-types/<tên>.json` |
| Guard = cưỡng chế | lane, workflow, rules, A3/A4 | `guard/` (đọc `.cecilia/registry.json`) |
| Adapter = định dạng host | agent Claude Code / Antigravity | `adapters/` — sinh, không sửa tay |

## Cách nhanh nhất: nhờ `cecilia-extend` hoặc `cecilia scaffold`

> Dùng cecilia-extend: tạo lens test `a11y-deep` (kiểm tra bàn phím + screen reader cho mọi màn hình mới).

Agent dựng từ `templates/`, validate, đề xuất ở `tensura/extensions/<tên>/` của workspace. Bạn đọc rồi tự áp dụng:
`cecilia extension check tensura/extensions/<tên>` rồi `cecilia extension apply tensura/extensions/<tên>` (chỉ người; ghi vào `.cecilia/extensions/` của workspace đó, không đụng repo Cecilia).
Muốn đưa vào **repo Cecilia** cho mọi dự án: `python tools/scaffold.py role|flow|lens <tên> --target repo` (hoặc
`cecilia scaffold …`), điền các chỗ `TODO(extend)`, rồi làm bước "Luôn chạy" ở dưới.

## Thêm tay

**Vai mới**
1. `registry/roles/cecilia-<tên>.json`: `agent_type` (`writer` / `tester` / `reviewer`), `kind`, `description` một
   câu (không chứa ": "), `default_on`, `model`, `consumes`/`produces`, `lane` (glob; `tensura/…` là của workspace),
   `report`, `review_guide` (file trong `skills/cecilia-review/`), `rules_slot` = `rules/roles/<tên>.md`,
   `overrides` nếu tool khác agent type.
2. `skills/cecilia-<tên>/SKILL.md` dạng thẻ: frontmatter chỉ `name` + `description` (≤ 450 ký tự, không ": "), tiêu
   đề có "v20", dòng **Read first:** `references/common/core-min.md`, bảng **Authority**, cả file ≤ 5 KB, chi tiết ở
   `references/workflow.md`. Khung: `templates/role/SKILL.md`. Báo cáo kết thúc bằng dòng `Rules:` và `HANDOFF:` khi
   dừng vì lane.
3. Guide review cho vai (nếu chưa có) trong `skills/cecilia-review/references/`.
4. Có luồng điển hình → thêm kịch bản vào `tools/token_budget.json`; luật bắt buộc mới → `tools/rules.json`.

**Flow mới** — `registry/flows/<tên>.json` (đủ 7 bước, `settings` mặc định) + `shared/flows/<tên>.md` với một mục
`## <bước>` cho mỗi bước; file luật `rules/flows/<tên>.md` được tạo ở workspace khi `cecilia upgrade`.

**Lens mới** — `registry/lenses/test/<tên>.json` + `skills/cecilia-test/references/lenses/<tên>.md`, hoặc
`registry/lenses/review/<tên>.json` + một mục `## <tên>` trong `skills/cecilia-review/references/panel.md`. Trường
`when` nói thay đổi nào thì orchestrator chọn lens đó.

**Stack / platform / engine** (không cần manifest): `skills/cecilia-dev-be/references/stacks/<stack>.md` theo
`_new-stack.md`; `skills/cecilia-devops/references/platforms/<platform>.md` theo `_new-platform.md`;
`skills/cecilia-db/references/engines/<engine>.md` theo `_new-engine.md`.

**Luật dùng chung** — sửa `shared/` (không sửa bản chép trong skill), chạy `sync_common.py`; luật bắt buộc mới →
một dòng trong `tools/rules.json`. File chỉ vài vai cần: `shared/scoped/` + `SCOPED` trong `tools/sync_common.py`.
Luật **của một dự án** thì không sửa repo: ghi vào `rules/` của workspace (`cecilia rules …`).

**Connector cần guard riêng** — `guard/cecilia_guard.py` (`MCP_DENY`, `MCP_ASK`, `DESIGN_SERVER`) + dòng trong
`tests/corpus/*.jsonl`, chạy `tools/guard_corpus.py` và HOST-SMOKE.

## Luôn chạy (mọi thay đổi)

```bash
python3 tools/registry.py --check         # manifest đúng schema, file guide/skill tồn tại
python3 tools/build_adapters.py           # sinh lại agent 2 host + shared/generated/*.md từ registry
python3 tools/sync_common.py              # chép shared/ vào từng skill
python3 tools/validate.py                 # PASS mới được đóng gói
python3 tools/tokens.py --check
python3 -m unittest discover -s tests
```

`validate.py` in lỗi cụ thể khi thiếu bước nào — cứ làm theo lỗi nó in ra. Dự án đã cài: `cecilia upgrade <dự án>`
để workspace nhận vai/flow/lens mới (config, `registry.json`, `rules/`).

## Nâng version

Mọi file dưới đây mang cùng một version — `validate.py` báo lỗi nếu lệch:

| File | Chỗ |
|---|---|
| `tools/roster.py` | `VERSION` |
| `tools/registry.py` | `VERSION` (bản chụp `.cecilia/registry.json`) |
| `pyproject.toml` | `version` |
| `src/cecilia/__init__.py` | `__version__` |
| `guard/cecilia_guard.py` | `VERSION` |
| `guard/policy.json` | `"version"` |
| `shared/scripts/cecilia_check.py` | `VERSION` (rồi `sync_common.py` chép vào skill) |
| `README.md` | tiêu đề (vNN) và dòng "Bản x.y.z", lệnh cài `@vx.y.z` |
| `CHANGELOG.md` | mục `## vx.y.z` đầu tiên |
| `docs/INSTALL.md` | tag trong lệnh `uv tool install …@vx.y.z` |
| `docs/MIGRATION.md` · `docs/HOST-SMOKE.md` | mục cho bản mới (không kiểm tự động) |

Bản major mới: đổi thêm "vNN" trong tiêu đề mọi `SKILL.md` (validate kiểm), `MAJOR` trong `tools/validate.py`,
`build_adapters.py` và tiêu đề các file docs. Sau đó `python3 tools/build_adapters.py` (header của
`shared/generated/`), rồi cổng phát hành `docs/RELEASE.md`, rồi `python3 tools/package.py` (tạo `CHECKSUMS.json` và
file zip trong `dist/`).
