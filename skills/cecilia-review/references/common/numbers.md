# Numbers — measure, project, calculate (common v20)

<!-- common v20 — canonical copy in shared/, synced into every skill by tools/sync_common.py. Do not edit a copy. -->

Cecilia decides on numbers. A number is either **measured** (a tool read it) or **projected** (computed
from stated inputs) — never guessed. Arithmetic is done by running code, not in the head.

## 1. Two kinds of number

| Kind | Label | Must carry |
|---|---|---|
| **Measured** | `[verified]` + `M-nn` | `value — formula — source command/file/tool — revision — date` (`evidence.md` §1) |
| **Projected** | `[projected]` | formula · every input with its source (measured / doc / Cecilia / assumption) · low / expected / high · the input that moves it most · how to verify it by measurement |

Never estimated at all: effort or time to do the work (size is scope — files, modules, IDs).

## 2. When to project

Whenever a decision depends on scale — before Cecilia chooses, not after:

| Question | Command (`scripts/capacity.py`) |
|---|---|
| How big is one row / how many fit a page? | `rowsize --engine postgres --columns "id:bigint,…"` |
| How big will table X be at N users after M months (table + indexes + replicas + cost)? | `growth --columns … --users L,E,H --rows-per-user-month L,E,H --months M --index … --replicas R --price-gb-month P` |
| How much RAM do N connections take? | `connections --engine postgres --connections N [--base-mb …] [--work-mem-mb …]` |
| How many instances / DB connections for R requests per second? | `throughput --rps L,E,H --latency-ms … --cpu-ms … --db-ms …` |
| How much traffic leaves the service? | `bandwidth --rps … --payload-kb …` |

Run it with the host's Python (`python3` / `python` / `py`) from the skill's folder
(`.claude/skills/<skill>/scripts/capacity.py` or `.agents/skills/<skill>/scripts/capacity.py`); paste
its table into the report or decision. `--json` gives machine-readable output.

Something the script does not model (queue depth, cache hit ratio, cost of a managed service, bundle
size) → write the calculation as a few lines of Python in the report's appendix and run it; show the
formula and the inputs the same way.

## 3. Inputs — where each number comes from

Prefer, in order: **measured in this project** (APM, `EXPLAIN ANALYZE`, `pg_stat_statements`, load test,
table sizes) → **Cecilia's business numbers** (users, orders per user, growth, retention) → **vendor
documentation** (with URL and date, `decisions.md` §7) → **assumption**, stated as such with a range.
Ask Cecilia for business inputs you do not have — in one grouped gate with a proposed range each.

## 4. Presenting a projection

```
### Bảng orders sau 24 tháng [projected]
Công thức: rows = users × đơn/user/tháng × tháng; size = (table + indexes) × bloat
Đầu vào: users 10k/50k/200k (Cecilia, 2026-09-24) · đơn/user/tháng 2/4/8 (giả định — cần số thật) ·
         row 132 B (capacity.py rowsize, schema order-database.md §3) · bloat 1.1/1.2/1.5 (giả định)
| kịch bản | rows | table | indexes | tổng | ×2 bản (replica) | lưu trữ / tháng |
|---|---|---|---|---|---|---|
| thấp | 480k | 61 MB | 39 MB | 111 MB | 222 MB | 0.02 USD |
| dự kiến | 4.8M | 615 MB | 393 MB | 1.18 GB | 2.36 GB | 0.27 USD |
| cao | 38.4M | 4.8 GB | 3.1 GB | 11.8 GB | 23.6 GB | 2.72 USD |
Nhạy nhất: số đơn/user/tháng và số user (+20% → +20%).
Kiểm chứng: seed 1M dòng mẫu, đo pg_total_relation_size, so với 128 MB dự kiến cho heap.
Ảnh hưởng quyết định: dưới ~50 GB → chưa cần partition; cao > 10 GB/năm → xem partition theo tháng.
```

Always end with **what the number means for the decision** — the threshold that would change it.

## 5. Common reference points (verify for your version)

- PostgreSQL: one process per connection; memory per backend is a few MB before query work, plus
  `work_mem` per sort/hash **operation**; `shared_buffers` is shared. MySQL: one thread per connection,
  per-session buffers allocated on demand, `innodb_buffer_pool_size` shared.
- Little's law: requests in flight = arrival rate × time in system.
- Storage for replicas, backups (retention × full + incrementals), WAL/binlog and free space for
  maintenance is **on top of** the table size.

These are starting points for the calculation, not answers; the answer is the measured or computed number.
