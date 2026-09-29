# Prompt mẫu — Cecilia v20

Mở **workspace** (`cd <dự án>.cecilia && claude`) rồi dùng các prompt dưới. Agent làm code trong dự án,
ghi docs/báo cáo vào `tensura/` của workspace, không push — cuối task đưa bạn lệnh `cecilia push …` + `gh pr create …`.
Từ v20 bạn nói chuyện với **orchestrator** (luồng chính): nó không tự code/test/review mà giao cho đúng vai.

## V20 — phương án, song song, lens, luật, flow

**Chọn phương án trước khi làm (STANDARD)**
> Task SHOP-42: thêm lịch sử đơn hàng (API + màn hình). Đưa tôi 2–3 phương án: bao nhiêu dev/test/reviewer, chia
> theo module hay theo tầng, lens test nào, thời gian và token dự kiến, model từng agent. Tôi chọn rồi mới giao việc.

> Chọn phương án B. Đóng băng vào workflow.json rồi giao việc.

**Nhiều dev song song**
> Phương án với 3 dev-be, mỗi người một unit rời nhau (orders, payments, notifications), mỗi người một worktree.
> 1 dev-fe cho màn hình. Test: functional + integration + concurrency-perf. Báo tôi khi cả wave xong.

**Test theo lens**
> Chạy test cho nhánh này với các lens functional, security, database — mỗi lens một agent, gộp kết quả bằng
> `workflow.py merge-tests`.

**Review + vòng sửa**
> Hội đồng review 4 lens theo diff, 2 vòng + judge. Finding được CHẤP NHẬN thì tự sửa, tối đa 3 vòng; mục TRANH CHẤP
> hoặc hết vòng thì dừng và đưa tôi phương án.

**"Tự sửa đi" vẫn là giao việc**
> Sửa nhanh cái typo trong `app/orders.py` giúp tôi, tự làm luôn cũng được.
(Orchestrator vẫn giao cho dev-be với brief 3 dòng — nó không ghi code.)

**Lane và hand-off**
> dev-fe: màn hình lịch sử đơn cần thêm field `status` ở API. Nếu đụng code backend thì dừng và ghi HANDOFF cho
> dev-be, đừng tự sửa.

**Luật của dự án (bạn tự ghi, agent chỉ đọc)**
> Tôi vừa thêm `- PR-03: không dùng console.log trong src/` vào `rules/_project.md`. Từ giờ mọi brief phải nhúng luật
> này; báo cáo ghi dòng `Rules:` với các PR-id đã áp dụng.

**Làm theo team**
> (sau khi bạn chạy `cecilia flow team`) Ticket SHOP-51: nhận ticket, đặt nhánh theo mẫu, commit đúng
> `commit_pattern`, PR body theo template, PR ≤ 400 dòng; đụng schema hay contract thì dừng và soạn tin báo leader.

> Đọc comment review trên PR #57 (tôi dán vào `tensura/tasks/SHOP-51/review-comments.md`) và lập danh sách sửa.

**Thêm vai / flow / lens**
> Dùng cecilia-extend: tạo vai `cecilia-mobile` (React Native), lane `mobile/**`, đọc api-contract, sinh code + report.
> Validate xong để ở `tensura/extensions/`; tôi tự chạy `cecilia extension apply`.

## FAST

**Task rất nhỏ**
> FAST: sửa typo/label này và chạy check liên quan. Đừng tạo plan file hay gọi reviewer nếu không phát hiện rủi ro mới.

**Bug biết rõ nguyên nhân**
> FAST: fix nil pointer ở `OrderHandler`, thêm regression test tối thiểu, báo cho tôi file nào đổi và test nào đã chạy.

## STANDARD — mặc định

**Backend feature**
> Dùng cecilia-dev-be, STANDARD. Thêm endpoint lấy profile theo pattern hiện có. Short plan trong chat,
> code + test local; đừng hỏi duyệt từng file. Dependency mới thì hỏi tôi; push/PR để tôi tự làm — đưa lệnh.

**Full-stack feature — chạy song song**
> Dùng cecilia-orchestrator, STANDARD, task <SHOP-42>. Plan theo docs hiện có; BE ‖ FE ‖ DevOps chạy cùng
> lúc, mỗi vai một worktree + nhánh riêng; xong thì ghép nhánh integration và test chung. Đưa plan cho
> tôi duyệt trước.

**Bug chưa rõ nguyên nhân**
> Dùng cecilia-orchestrator, STANDARD. Reproduce trước, tìm root cause, short plan, sửa, regression
> test. Nếu phát hiện migration/auth/infra/public-contract thì dừng trước phần đó và đề xuất CONTROLLED.

**Database (cecilia-db)**
> Dùng cecilia-db. Query danh sách đơn ở `OrderRepository.findByCustomer` chậm (~800 ms). Tìm nguyên
> nhân bằng EXPLAIN trên DB local có seed ~2 triệu dòng, đề xuất index/đổi query, đo trước/sau.

> Dùng cecilia-db, CONTROLLED. Bảng `booking_events` tăng ~5 triệu dòng/tháng. Đề xuất partition +
> retention (các phương án, không tạo partition trong trigger), migration có rollback, job tạo partition trước.

**Dự báo tăng trưởng + chiến lược mở rộng (cecilia-db)**
> Dùng cecilia-db. Hỏi tôi các giả định còn thiếu (user hiện tại, tăng trưởng/tháng thấp–dự kiến–cao, số đơn/user,
> peak, retention, RAM/đĩa hiện tại, RTO). Dự báo 36 tháng cho `orders`, `order_items`, `events` bằng
> `capacity.py forecast`, chỉ ra tháng chạm từng ngưỡng, rồi đưa các bậc mở rộng phù hợp (thang 10 bậc) với
> trigger lên bậc — tôi chọn.

**Chọn cơ sở dữ liệu**
> Dùng cecilia-db: dự án này nên giữ PostgreSQL hay chuyển/bổ sung MongoDB cho catalog? So sánh theo workload
> và cơ chế (MVCC, transaction, join, replication, sharding, backup), ≥ 3 phương án gồm giữ nguyên, kế hoạch POC,
> viết ADR có điều kiện xem lại. Nguồn chính thức có ngày.

**Backup / DR**
> Dùng cecilia-db: đề xuất RPO/RTO, cách backup + PITR, tính thời gian restore bằng `capacity.py restore`, viết
> DR runbook và diễn tập restore trên DB local.

**Dữ liệu cá nhân**
> Dùng cecilia-db: lập bảng dữ liệu cá nhân (§17 database doc) và checklist theo Luật BVDLCN Việt Nam + GDPR,
> chỉ ra gap và ai xử lý. Không phải tư vấn pháp lý — ghi câu hỏi cho luật sư.

**API dưới góc người dùng (cecilia-api-ux)**
> Dùng cecilia-api-ux, review `api/shop.yaml` như dev mobile làm màn checkout và danh sách đơn: số call, độ sâu,
> N+1, payload, lỗi có xử lý được không, idempotency. Flash sale 20 lượt ghi/giây/SKU với optimistic lock — tỉ lệ
> bị từ chối bao nhiêu? Findings AUX-nn có owner và tiêu chí đo; không sửa gì.

> Dùng cecilia-api-ux: so `api/shop-v1.yaml` với `api/shop-v2.yaml`, liệt kê breaking change và kế hoạch
> chuyển đổi cho client.

**Giao diện (cecilia-ui — bật trong `.cecilia/config.json` trước)**
> Dùng cecilia-ui cho app `web`: thiết kế luồng đặt vé SCR-01..SCR-05. Hỏi tôi dùng Penpot, Figma
> hay Markdown. Wireframe trước, tôi duyệt rồi mới làm hi-fi; đủ mọi state; kiểm tra contrast.

> Dùng cecilia-review mode ui để review `web-ui.md`, tokens và `ui-exports/` trước khi dev-fe code.

**Frontend nhìn bằng trình duyệt**
> Dùng cecilia-dev-fe, STANDARD: làm SCR-03 danh sách đơn theo `web-ui.md`. Sau khi code, mở bằng
> Playwright CLI, chụp đủ state (loading/empty/lỗi 409/nhiều dòng) ở 390/768/1440, so với `ui-exports/`,
> đo contrast, kiểm guideline; đưa tôi bảng bằng chứng.

**Làm giao diện từ ảnh**
> Dùng cecilia-dev-fe: đây là ảnh chụp màn hình thanh toán tôi muốn (ảnh tham khảo, không phải của mình).
> Theo `image-to-code.md`: lấy bố cục, map màu về token hiện có, state nào ảnh không có thì hỏi tôi;
> dựng xong chụp lại và so với ảnh.

**Style guide**
> Tôi đã đặt `ui.style: "minimalist"`. Dùng cecilia-ui thiết kế trang cài đặt — phần brand chưa quy định
> thì theo minimalist, ghi rõ luật nào lấy từ đâu.

**Cần số liệu để quyết**
> Dùng cecilia-db: bảng `bookings` sau 24 tháng nếu có 10k/50k/200k user, mỗi user 2/4/8 vé/tháng thì
> bao nhiêu GB (có index, 1 replica)? 1000 connection tốn bao nhiêu RAM? Chạy capacity.py, cho tôi bảng
> thấp/dự kiến/cao và ngưỡng nào thì cần partition.

**Phương án khách quan**
> Dùng cecilia-design: chọn cách gửi thông báo (queue / cron / webhook…). Search web, cho tôi ≥ 3 phương án
> cùng tiêu chí (độ trễ, chi phí, độ phức tạp, rủi ro), có nguồn, đề xuất để riêng.

**Rollback**
> Hoàn tác toàn bộ task <SHOP-42-B01> theo khối Rollback trong báo cáo — cho tôi xem lệnh trước khi chạy.

**Hội đồng review**
> Dùng cecilia-orchestrator: hội đồng review nhánh feature/SHOP-42-01 so với develop — 3 reviewer theo góc nhìn phù
> hợp với diff + red team, 2 vòng, judge chốt; mục nào tranh chấp thì hỏi tôi.

**Quy ước và bài học**
> Dùng cecilia-discovery: dựng `tensura/conventions.md` cho dự án này (lệnh test/build, cấu trúc, đặt tên, pattern).
> Cuối mỗi task, ghi bài học vào `tensura/lessons.md`; đánh `[generic?]` cái nào nên đưa vào skill.

**Review PR**
> Dùng cecilia-review, mode code, review PR #<31> tại SHA <...>, đối chiếu behavior/docs hiện có.

## CONTROLLED

Dùng cho task rủi ro cao hoặc khi bạn muốn exact scope:

```bash
cecilia mode controlled
```

**Migration / auth / infra**
> CONTROLLED: dùng orchestrator cho task <...>. Design/plan vừa đủ, exact cecilia-scope, test và
> independent review trước G3. Tôi sẽ tự approve G2 và mọi A3/A4.

**Release**
> CONTROLLED: chuẩn bị G4 packet cho artifact <...>. Tôi tự trigger production.

Sau task controlled:

```bash
cecilia mode standard
```

## Human-only controls

Sửa tay `<dự án>.cecilia/.cecilia/config.json` để bật/tắt vai, `lanes`, `orchestration`, `parallel.limits`, `test.lenses`, `review.panel`, `fix_loop`, `profiles`, `tool_rules`, `plan_first`, `git`, `models`, `docs_layout`. Luật dự án ở `rules/`. Rồi:

```bash
cecilia mode --show
cecilia mode fast
cecilia mode standard
cecilia mode controlled
cecilia approve tensura/plans/<plan>.md --task <TASK-B01>
cecilia approve --list
cecilia approve --revoke <TASK-B01>
cecilia flow team                 # hoặc: cecilia flow personal
cecilia rules list                # xem luật; kiểm: cecilia rules lint
cecilia rules add --project "không dùng console.log trong src/"   # hoặc --role dev-be / --flow team / --lens security
cecilia extension list            # đề xuất của cecilia-extend
cecilia extension apply tensura/extensions/<tên>                  # chỉ bạn chạy
```

**Tiếp tục task / đẩy code (bạn làm)**
> Tiếp tục task <SHOP-42> (đọc `tensura/tasks/SHOP-42/state.md`).

```bash
cecilia push -u origin feature/SHOP-42-01-order          # trong workspace hoặc dự án
cd D:\projects\shop
gh pr create --draft --base develop --head feature/SHOP-42-01-order --body-file D:\projects\shop.cecilia\tensura\reports\SHOP-42\pr-body.md
```
