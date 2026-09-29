# Cecilia trên Antigravity (`agy`) — hướng dẫn nhanh

Antigravity là host chính của Cecilia từ 20.2. Tài liệu này cho người dùng `agy` (CLI) hằng ngày.
Cần **agy ≥ 1.2.7** (bản cũ hơn: main agent tuỳ biến không gọi được subagent nào).

## 1. Cài và nâng cấp

```bash
uv tool install git+https://github.com/<you>/cecilia-skills@<tag>   # lần đầu (cần uv)
cecilia init D:\projects\shop                                       # một lần mỗi dự án → D:\projects\shop.cecilia\
```

Nâng cấp: `uv tool uninstall cecilia` → `uv tool install …@<tag mới>` → `cecilia upgrade D:\projects\shop`
(hoặc `cecilia upgrade --all`). Chưa chạy `cecilia upgrade` thì workspace vẫn dùng skill, agent và hook cũ.
Sau đó chạy `cecilia doctor shop`: mọi dòng hook phải PASS.

## 2. Mở đúng cách

```bash
cecilia open shop --agy                      # chạy agy TRONG workspace shop.cecilia
cecilia open shop --agy --skip-permissions   # thêm --dangerously-skip-permissions
```

agy chỉ nạp hook, agent và main agent của Cecilia từ `.agents/` của **thư mục đang đứng**. Chạy `agy` từ thư mục
home (`C:\Users\<bạn>`) hay từ thư mục dự án thì **không có Cecilia**: không guard, không orchestrator — agent
chính sẽ tự làm hết. Luôn mở bằng lệnh trên (hoặc `cd D:\projects\shop.cecilia` rồi `agy`).

## 3. Làm việc: một câu là đủ

Gõ một câu, ví dụ `sửa lỗi hủy đơn hoàn tiền hai lần`. Orchestrator (luồng chính) **không tự làm**: nó gọi
`cecilia-discovery` đo sự thật, 3 planner lập và bỏ phiếu kế hoạch, rồi đưa bạn **một thẻ quyết định**
(`tensura/decisions/<TASK>.md`, hiện qua `ask_question`): các phương án, model từng vai, câu hỏi có sẵn mặc định.
Trả lời `A` = chọn phương án A với mọi mặc định. Sau đó các agent chạy song song theo đợt, test theo lens,
review bằng hội đồng, vòng sửa tối đa 3.

**Quá bán.** Kế hoạch, nguyên nhân gốc, finding review và kết luận PASS/FAIL do 3 agent độc lập bỏ phiếu có bằng
chứng; `workflow.py tally` đếm, thông qua khi **hơn một nửa** phiếu hợp lệ đồng ý. Không đủ quá bán → câu hỏi
trên thẻ. Phiếu chỉ tính khi do chính subagent bỏ phiếu ghi (guard ghi ai viết file vào
`.cecilia/provenance.jsonl`): phiếu orchestrator tự viết bị loại; phiếu không xác minh được → thẻ ghi
"independence unverified". CONTROLLED: một phiếu cảnh báo mất dữ liệu/secret/phá huỷ không bị áp đảo — bạn quyết.

## 4. Kubernetes, Proxmox và các MCP khác

- Orchestrator **không có** tool MCP. Đọc/chẩn đoán cluster, VM → nó gọi `cecilia-discovery` (hoặc 3
  người chẩn đoán của vai phụ trách); thay đổi → `cecilia-devops`, và mỗi thao tác ghi (scale, delete, exec,
  restart…) là A3: agent trích đúng lệnh, bạn duyệt từng lệnh.
- Guard nhận ra vai của từng subagent từ dòng `[cecilia-brief … ROLE=…]` ở tin nhắn đầu của nó. Subagent
  không có dòng đó bị coi là orchestrator → bị chặn MCP và chặn ghi ngoài `tensura/`.
- Orchestrator gọi MCP, tự viết phiếu, gọi agent lạ (`research`, `teamwork_*`) → guard chặn, kèm lý do.

## 5. `--dangerously-skip-permissions` và `antigravity.ask`

Skip-permissions chỉ bỏ hộp hỏi của agy; **guard vẫn chạy**: DENY vẫn là DENY, lệnh chỉ-người
(`cecilia mode|approve|flow|rules add|extension apply|push`) vẫn bị từ chối. Với thao tác A3, config
`.cecilia/config.json` → `"antigravity": {"ask": …}` quyết định:

| Giá trị | Nghĩa |
|---|---|
| `"force_ask"` (mặc định) | A3 luôn hỏi bạn, **kể cả** khi chạy `--dangerously-skip-permissions` |
| `"ask"` | hỏi theo quyền thường của agy — dưới skip-permissions sẽ tự được duyệt |

Khuyên giữ `force_ask`.

## 6. Model theo vai (`antigravity.models`)

Mặc định orchestrator, plan, review chạy `pro`; các vai khác `inherit` (model của phiên, ví dụ Flash). Đổi:

```json
"antigravity": { "models": { "dev-be": "pro", "test": "flash", "review": "pro" } }
```

Giá trị: `inherit` · `flash` · `pro` · hoặc id model. Sửa xong chạy `cecilia upgrade shop` để ghi lại agent.
Chạy cả phiên bằng Flash thì kế hoạch và phiếu bầu yếu hơn — thẻ sẽ nói nếu các phiếu cùng một model.

## 7. Điều khiển từ LLM khác: `cecilia mcp`

`cecilia mcp` là MCP server: Claude Desktop, Claude Code, Cursor… giao việc vào workspace, theo dõi, đọc thẻ và
chuyển câu trả lời của bạn. Với Antigravity nó chạy `agy` ở chế độ nền (headless) trong workspace. Các tool
điều khiển (mode, approve, flow, rules, extension, push) chỉ có qua server này, mỗi lần gọi ghi vào
`tensura/audit/control.jsonl` (ai, lệnh, kết quả). Kết nối và danh sách tool: `docs/MCP.md`.

## 8. Mở quyền cho agent: `guard.agent_may_run`

Mặc định agent trong workspace không được chạy lệnh chỉ-người (để không tự duyệt kế hoạch của mình). Muốn mở:

```json
"guard": { "agent_may_run": ["flow", "rules add"] }
```

Tên hợp lệ: `mode`, `approve`, `flow`, `rules add` (`rules` = mọi thay đổi rules), `extension apply`, `push`.
Mở `approve` hay `push` là bỏ lớp bảo vệ quan trọng nhất — chỉ khi bạn chấp nhận rủi ro đó.

## 9. Xử lý sự cố

| Triệu chứng | Làm gì |
|---|---|
| `subagent not found` / không được phép gọi | `agy --version` phải ≥ 1.2.7; `cecilia upgrade shop`; `cecilia doctor shop`. Orchestrator phải dừng và báo lỗi, không tự làm |
| Guard không chặn gì, orchestrator tự sửa code | agy mở sai thư mục (mục 2), hoặc hook không chạy → `cecilia doctor shop` |
| Hook báo lỗi / "internal error" | `cecilia doctor shop`, rồi `cecilia upgrade shop` nếu đường dẫn Python đổi |
| Chạy nền (MCP, `agy -p`) trả stdout rỗng dù thành công | lỗi của agy trên Windows; MCP server tự đọc câu trả lời từ transcript |
| `agy -p` treo | lỗi agy khi stdin là pipe mở; MCP server luôn đóng stdin và có giới hạn thời gian |
| Thẻ ghi "independence unverified" | có phiếu không do subagent bỏ phiếu ghi — xem `votes/<stage>-result.md`, cho chạy lại người bỏ phiếu đó |

Chi tiết cho orchestrator: `skills/cecilia-orchestrator/references/antigravity.md`.
