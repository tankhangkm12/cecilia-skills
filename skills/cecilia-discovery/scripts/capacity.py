#!/usr/bin/env python3
"""Capacity calculator for Cecilia roles — numbers computed, not guessed (common v19).

Every command prints the formula, the inputs (with which ones are assumptions), a low / expected / high
table and a sensitivity ranking (which input moves the result most). Results are PROJECTIONS: label them
[projected] and confirm with a measurement when one is possible (commands printed at the end).

Numeric inputs accept one value or three: "LOW,EXPECTED,HIGH".

  capacity.py rowsize     --engine postgres --columns "id:bigint,user_id:bigint,total:numeric(19,4),status:varchar(20)=8?,created_at:timestamptz"
  capacity.py growth      --engine postgres --columns "..." --users 10000,50000,200000 --rows-per-user-month 2,4,8 \
                          --months 12 --index "user_id:bigint,created_at:timestamptz" --index "status:varchar(20)=8"
  capacity.py connections --engine postgres --connections 1000 --active-ratio 0.1,0.2,0.4
  capacity.py throughput  --rps 200,500,1000 --latency-ms 80 --cpu-ms 12 --db-ms 15 --cores 2
  capacity.py bandwidth   --rps 200,500,1000 --payload-kb 4,8,16
  capacity.py contention  --rps-per-key 0.1,5,200 --window-ms 50 --retries 2       # optimistic lock / hot row
  capacity.py forecast    --users 20000,50000,100000 --monthly-growth 0.03,0.08,0.15 --rows-per-user-month 2,4,8 \
                          --row-bytes 180 --index-bytes-per-row 90 --months 36 --peak-factor 5,10,30 \
                          --ram-gb 16 --storage-gb 500 --write-limit 3000 --restore-mbps 100,200,400 --rto-minutes 60
  capacity.py threshold   (same inputs as forecast — prints only the "when does it break" table)
  capacity.py docsize     --fields "_id:objectId,userId:objectId,status:string=8,total:decimal128,items:array=400,createdAt:date"
  capacity.py restore     --data-gb 50,120,300 --restore-mbps 100,200,400 --index-factor 0.3,0.6,1.0 --rto-minutes 60

Column syntax: name:type[=AVG_BYTES][?]   ? = nullable, =N = average stored bytes for variable types.
Standard library only; Python 3.9+.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys

MB = 1024 ** 2
GB = 1024 ** 3

# ------------------------------------------------------------------------------------------ inputs


def triple(text):
    """'5' -> (5,5,5); '2,5,10' -> (2,5,10)."""
    parts = [float(x) for x in str(text).split(",")]
    if len(parts) == 1:
        return (parts[0],) * 3
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(f"expected 1 or 3 comma-separated numbers, got {text!r}")
    return tuple(parts)


COLUMN = re.compile(r"^\s*(?P<name>[A-Za-z_][\w]*)\s*:\s*(?P<type>[A-Za-z][A-Za-z0-9 ]*?)\s*(\((?P<args>[\d, ]+)\))?"
                    r"\s*(=(?P<avg>\d+))?\s*(?P<null>\?)?\s*$")


def parse_columns(spec: str):
    cols = []
    for raw in re.split(r",(?![^()]*\))", spec):
        if not raw.strip():
            continue
        m = COLUMN.match(raw)
        if not m:
            raise SystemExit(f"cannot parse column {raw!r} — use name:type[(args)][=AVG_BYTES][?]")
        args = [int(a) for a in (m.group("args") or "").replace(" ", "").split(",") if a]
        cols.append({"name": m.group("name"), "type": m.group("type").strip().lower(), "args": args,
                     "avg": int(m.group("avg")) if m.group("avg") else None, "nullable": bool(m.group("null"))})
    if not cols:
        raise SystemExit("no columns given")
    return cols

# ------------------------------------------------------------------------------------------ engines
# Sizes follow the vendors' storage docs:
#  PostgreSQL "Database Page Layout" (8 KiB pages, 24-byte page header, 23-byte tuple header, 4-byte line
#  pointer, MAXALIGN 8) and "Numeric Types"/"Character Types" (1-byte varlena header up to 126 bytes).
#  MySQL "Data Type Storage Requirements" and InnoDB row formats (16 KiB pages, 5-byte record header,
#  6-byte DB_TRX_ID, 7-byte DB_ROLL_PTR, pages filled to ~15/16 on ordered inserts).


def pg_col(c, notes):
    t, a = c["type"], c["args"]
    fixed = {"smallint": 2, "int2": 2, "integer": 4, "int": 4, "int4": 4, "bigint": 8, "int8": 8,
             "real": 4, "float4": 4, "double precision": 8, "float8": 8, "boolean": 1, "bool": 1, "date": 4,
             "timestamp": 8, "timestamptz": 8, "time": 8, "uuid": 16, "money": 8, "serial": 4, "bigserial": 8}
    if t in fixed:
        return fixed[t]
    if t in {"numeric", "decimal"}:
        p = a[0] if a else 19
        return 3 + 2 * math.ceil(p / 4)  # header + 2 bytes per 4 decimal digits (upper bound)
    if t in {"varchar", "character varying", "text", "char", "character", "bytea", "jsonb", "json"}:
        if c["avg"] is not None:
            content = c["avg"]
        elif t in {"varchar", "character varying", "char", "character"} and a:
            content = a[0] // 2
            notes.append(f"{c['name']}: avg length not given — assumed half of {t}({a[0]}) = {content} B")
        else:
            content = 64
            notes.append(f"{c['name']}: avg size not given — assumed 64 B; pass ={c['name']}_bytes")
        return content + (1 if content <= 126 else 4)
    raise SystemExit(f"postgres: unknown type {t!r} for column {c['name']} — add it or give name:bytea=N")


MYSQL_DIG = [0, 1, 1, 2, 2, 3, 3, 4, 4, 4]


def mysql_col(c, notes):
    t, a = c["type"], c["args"]
    fixed = {"tinyint": 1, "boolean": 1, "bool": 1, "smallint": 2, "mediumint": 3, "int": 4, "integer": 4,
             "bigint": 8, "float": 4, "double": 8, "date": 3, "year": 1, "binary": a[0] if a else 16}
    if t in fixed:
        return fixed[t]
    if t in {"datetime", "timestamp", "time"}:
        fsp = a[0] if a else 0
        base = {"datetime": 5, "timestamp": 4, "time": 3}[t]
        return base + (fsp + 1) // 2
    if t in {"decimal", "numeric"}:
        p = a[0] if a else 10
        s = a[1] if len(a) > 1 else 0
        i, f = p - s, s
        return (i // 9) * 4 + MYSQL_DIG[i % 9] + (f // 9) * 4 + MYSQL_DIG[f % 9]
    if t in {"varchar", "varbinary", "char", "text", "mediumtext", "longtext", "blob", "json"}:
        if c["avg"] is not None:
            content = c["avg"]
        elif t in {"varchar", "varbinary", "char"} and a:
            content = a[0] // 2
            notes.append(f"{c['name']}: avg length not given — assumed half of {t}({a[0]}) = {content} B "
                         "(utf8mb4: up to 4 B per character)")
        else:
            content = 64
            notes.append(f"{c['name']}: avg size not given — assumed 64 B")
        return content + (1 if content <= 255 else 2)
    raise SystemExit(f"mysql: unknown type {t!r} for column {c['name']}")


def align8(n):
    return (n + 7) // 8 * 8


def row_bytes(engine, cols, notes):
    """Stored bytes per row including engine overhead (before page-fill)."""
    if engine == "postgres":
        data = sum(pg_col(c, notes) for c in cols)
        header = 23 + (math.ceil(len(cols) / 8) if any(c["nullable"] for c in cols) else 0)
        tuple_b = align8(align8(header) + data)
        return tuple_b + 4, {"tuple header": align8(header), "data": data, "line pointer": 4,
                             "alignment padding": tuple_b - align8(header) - data}
    data = sum(mysql_col(c, notes) for c in cols)
    var_hdr = sum(1 for c in cols if c["type"] in {"varchar", "varbinary", "text", "blob", "json"})
    nulls = math.ceil(sum(c["nullable"] for c in cols) / 8)
    overhead = 5 + 6 + 7 + nulls + var_hdr
    return data + overhead, {"record header + trx id + roll ptr": 18, "null bitmap": nulls,
                             "var-length headers": var_hdr, "data": data}


def page_geometry(engine):
    if engine == "postgres":
        return 8192, 8192 - 24, 1.0      # page, usable, default heap fillfactor 100
    return 16384, 16384 - 38 - 8, 15 / 16   # FIL header+trailer; ordered-insert fill


def table_bytes(engine, rows, per_row):
    page, usable, fill = page_geometry(engine)
    per_page = max(1, int(usable * fill // per_row))
    return math.ceil(rows / per_page) * page, per_page


def index_bytes(engine, rows, key_cols, pk_bytes, notes):
    """B-tree leaf estimate: entry = key + overhead (+ PK on InnoDB secondary). Upper levels ≈ +1%."""
    if engine == "postgres":
        key = sum(pg_col(c, notes) for c in key_cols)
        entry = align8(8 + key) + 4           # IndexTuple header + key, + line pointer
        usable, fill = 8192 - 24 - 16, 0.90   # btree default fillfactor 90
        page = 8192
    else:
        key = sum(mysql_col(c, notes) for c in key_cols)
        entry = key + pk_bytes + 6
        usable, fill, page = 16384 - 46, 15 / 16, 16384
    per_page = max(1, int(usable * fill // entry))
    return math.ceil(rows / per_page) * page * 1.01

# ------------------------------------------------------------------------------------------ output


def human(n):
    for unit, size in (("TB", 1024 ** 4), ("GB", GB), ("MB", MB), ("KB", 1024)):
        if abs(n) >= size:
            return f"{n / size:,.2f} {unit}"
    return f"{n:,.0f} B"


def sensitivity(fn, params):
    """% change of the expected result when each numeric input moves +20%."""
    base = fn(params)
    out = []
    for k, v in params.items():
        if isinstance(v, (int, float)) and v:
            p = dict(params)
            p[k] = v * 1.2
            out.append((k, (fn(p) - base) / base * 100 if base else 0.0))
    return sorted(out, key=lambda x: -abs(x[1]))


def report(title, formula, inputs, rows, assumptions, verify, sens=None, as_json=False):
    if as_json:
        print(json.dumps({"title": title, "formula": formula, "inputs": inputs, "results": rows,
                          "assumptions": assumptions, "sensitivity": sens or [], "verify": verify},
                         indent=2, ensure_ascii=True))
        return
    print(f"## {title}  [projected]\n")
    print("Formula:")
    for f in formula:
        print(f"  {f}")
    print("\nInputs:")
    for k, v in inputs.items():
        print(f"  - {k}: {v}")
    headers = list(rows[0].keys())
    print("\n| " + " | ".join(headers) + " |")
    print("|" + "---|" * len(headers))
    for r in rows:
        print("| " + " | ".join(str(r[h]) for h in headers) + " |")
    if sens:
        print("\nSensitivity (+20% on one input → change of the expected result):")
        for k, pct in sens:
            print(f"  - {k}: {pct:+.1f}%")
    if assumptions:
        print("\nAssumptions (confirm or replace with measured values):")
        for a in assumptions:
            print(f"  - {a}")
    print("\nVerify with a measurement:")
    for v in verify:
        print(f"  - {v}")

# ------------------------------------------------------------------------------------------ commands

VERIFY_SIZE = {
    "postgres": ["after seeding N representative rows: SELECT pg_size_pretty(pg_table_size('t')), "
                 "pg_size_pretty(pg_indexes_size('t')), pg_size_pretty(pg_total_relation_size('t'));",
                 "divide by N for bytes/row and compare with this projection"],
    "mysql": ["after seeding N rows and ANALYZE TABLE t: SELECT data_length, index_length FROM "
              "information_schema.tables WHERE table_name='t';"],
}


def cmd_rowsize(a):
    notes = []
    cols = parse_columns(a.columns)
    per_row, parts = row_bytes(a.engine, cols, notes)
    tb, per_page = table_bytes(a.engine, 1_000_000, per_row)
    rows = [{"part": k, "bytes": v} for k, v in parts.items()]
    rows.append({"part": "**stored per row**", "bytes": per_row})
    rows.append({"part": f"rows per page ({page_geometry(a.engine)[0] // 1024} KiB)", "bytes": per_page})
    rows.append({"part": "1,000,000 rows (heap/clustered, no secondary indexes)", "bytes": human(tb)})
    report(f"Row size — {a.engine}", ["row = engine overhead + Σ column bytes (aligned)",
                                      "rows/page = usable page bytes × fill ÷ row"],
           {"engine": a.engine, "columns": a.columns}, rows,
           notes + ["estimate within roughly ±20%; TOAST/off-page storage of large values not modelled"],
           VERIFY_SIZE[a.engine], as_json=a.json)


def growth_model(p, engine, per_row, idx_specs, pk_bytes, notes):
    rows = p["users"] * p["rows_per_user_month"] * p["months"] + p["existing_rows"]
    heap, _ = table_bytes(engine, rows, per_row)
    idx = sum(index_bytes(engine, rows, cols, pk_bytes, notes) for cols in idx_specs)
    return rows, heap, idx, (heap + idx) * p["bloat"]


def cmd_growth(a):
    notes = []
    cols = parse_columns(a.columns)
    per_row, _ = row_bytes(a.engine, cols, notes)
    pk_cols = [cols[0]]
    pk_bytes = pg_col(cols[0], []) if a.engine == "postgres" else mysql_col(cols[0], [])
    idx_specs = [pk_cols] + [parse_columns(i) for i in (a.index or [])]
    names = ("low", "expected", "high")
    rows_out = []
    for i, name in enumerate(names):
        p = {"users": a.users[i], "rows_per_user_month": a.rows_per_user_month[i], "months": a.months,
             "existing_rows": a.existing_rows, "bloat": a.bloat[i]}
        rows, heap, idx, total = growth_model(p, a.engine, per_row, idx_specs, pk_bytes, notes)
        r = {"scenario": name, "users": f"{p['users']:,.0f}", "rows": f"{rows:,.0f}", "table": human(heap),
             "indexes": human(idx), "total × bloat": human(total)}
        if a.replicas:
            r[f"× {a.replicas + 1} copies (primary + replicas)"] = human(total * (a.replicas + 1))
        if a.price_gb_month:
            r["storage cost / month"] = f"{total * (a.replicas + 1) / GB * a.price_gb_month:,.2f}"
        rows_out.append(r)
    exp = {"users": a.users[1], "rows_per_user_month": a.rows_per_user_month[1], "months": a.months,
           "existing_rows": a.existing_rows, "bloat": a.bloat[1]}
    sens = sensitivity(lambda q: growth_model(q, a.engine, per_row, idx_specs, pk_bytes, [])[3], exp)
    report(f"Table growth after {a.months} months — {a.engine}",
           ["rows = users × rows/user/month × months + existing",
            f"table = ceil(rows ÷ rows_per_page) × page   (row = {per_row} B)",
            "index = Σ ceil(rows ÷ entries_per_page) × page  (PK + each --index)",
            "total = (table + indexes) × bloat factor"],
           {"engine": a.engine, "users": a.users, "rows per user per month": a.rows_per_user_month,
            "months": a.months, "existing rows": a.existing_rows, "indexes": ["PK"] + (a.index or []),
            "bloat factor": a.bloat},
           rows_out,
           notes + ["bloat factor covers dead tuples/fragmentation (PG update-heavy tables: 1.2–2.0)",
                    "WAL/binlog, backups and temp space are extra — size them separately"],
           VERIFY_SIZE[a.engine], sens, a.json)


def conn_model(p, engine):
    if engine == "postgres":
        idle = p["connections"] * p["base_mb"]
        active = p["connections"] * p["active_ratio"] * p["work_mem_mb"] * p["ops_per_query"]
    else:
        idle = p["connections"] * p["base_mb"]
        active = p["connections"] * p["active_ratio"] * p["session_buffers_mb"]
    return idle, active, idle + active


def cmd_connections(a):
    names = ("low", "expected", "high")
    rows = []
    for i, name in enumerate(names):
        p = {"connections": a.connections[i], "base_mb": a.base_mb[i], "active_ratio": a.active_ratio[i],
             "work_mem_mb": a.work_mem_mb[i], "ops_per_query": a.ops_per_query[i],
             "session_buffers_mb": a.session_buffers_mb[i]}
        idle, active, total = conn_model(p, a.engine)
        rows.append({"scenario": name, "connections": f"{p['connections']:,.0f}", "baseline": human(idle * MB),
                     "active query memory": human(active * MB), "connection RAM": human(total * MB),
                     "+ shared cache": human((total + a.shared_mb) * MB)})
    exp = {"connections": a.connections[1], "base_mb": a.base_mb[1], "active_ratio": a.active_ratio[1],
           "work_mem_mb": a.work_mem_mb[1], "ops_per_query": a.ops_per_query[1],
           "session_buffers_mb": a.session_buffers_mb[1]}
    sens = sensitivity(lambda q: conn_model(q, a.engine)[2], exp)
    if a.engine == "postgres":
        formula = ["baseline = connections × per-backend memory (process per connection)",
                   "active = connections × active ratio × work_mem × sort/hash operations per query",
                   "total = baseline + active (+ shared_buffers, reported separately)"]
        assumptions = ["per-backend baseline memory (default 2,5,10 MB) varies with version, catalog size and "
                       "extensions — measure it", "work_mem is per operation, not per query",
                       "a pooler (PgBouncer) cuts server connections to the pool size — model that number"]
        verify = ["PG 14+: SELECT sum(total_bytes) FROM pg_backend_memory_contexts; (per backend)",
                  "OS: PSS/RSS of postgres backend processes (smem / ps) under load"]
    else:
        formula = ["baseline = connections × per-thread memory (thread stack + net buffers)",
                   "active = connections × active ratio × per-session buffers used by queries "
                   "(sort/join/read buffers, allocated on demand)",
                   "total = baseline + active (+ innodb_buffer_pool_size, reported separately)"]
        assumptions = ["per-thread baseline (default 1,1.5,3 MB) — thread_stack plus buffers",
                       "session buffers (default 1,2,8 MB) depend on sort_buffer_size, join_buffer_size, "
                       "read_buffer_size and the queries"]
        verify = ["performance_schema.memory_summary_by_thread_by_event_name under load",
                  "SELECT * FROM sys.memory_global_total;"]
    report(f"Connection memory — {a.engine}", formula,
           {"engine": a.engine, "connections": a.connections, "baseline MB": a.base_mb,
            "active ratio": a.active_ratio, "work_mem MB": a.work_mem_mb, "ops/query": a.ops_per_query,
            "session buffers MB": a.session_buffers_mb, "shared cache MB": a.shared_mb},
           rows, assumptions, verify, sens, a.json)


def thr_model(p):
    in_flight = p["rps"] * p["latency_ms"] / 1000
    cpu_cores = p["rps"] * p["cpu_ms"] / 1000
    instances = math.ceil(cpu_cores / (p["cores"] * p["target_util"])) if p["cores"] else 0
    db_conns = p["rps"] * p["db_ms"] / 1000
    return in_flight, cpu_cores, instances, db_conns


def cmd_throughput(a):
    rows = []
    names = ("low", "expected", "high")
    for i, name in enumerate(names):
        p = {"rps": a.rps[i], "latency_ms": a.latency_ms[i], "cpu_ms": a.cpu_ms[i], "db_ms": a.db_ms[i],
             "cores": a.cores, "target_util": a.target_util}
        in_flight, cpu, inst, dbc = thr_model(p)
        rows.append({"scenario": name, "rps": f"{p['rps']:,.0f}", "requests in flight": f"{in_flight:,.1f}",
                     "CPU cores busy": f"{cpu:,.2f}", f"instances ({a.cores:g} cores @ {a.target_util:.0%})": inst,
                     "DB connections busy": f"{dbc:,.1f}",
                     "pool per instance (×1.5 headroom)": math.ceil(dbc * 1.5 / max(inst, 1))})
    exp = {"rps": a.rps[1], "latency_ms": a.latency_ms[1], "cpu_ms": a.cpu_ms[1], "db_ms": a.db_ms[1],
           "cores": a.cores, "target_util": a.target_util}
    sens = sensitivity(lambda q: thr_model(q)[1], exp)
    report("Throughput, instances and pool size",
           ["in flight = rps × latency (Little's law L = λW)",
            "CPU cores busy = rps × CPU ms per request ÷ 1000",
            "instances = ceil(cores busy ÷ (cores per instance × target utilisation))",
            "DB connections busy = rps × DB time per request ÷ 1000"],
           {"rps": a.rps, "latency ms (p50-ish)": a.latency_ms, "CPU ms/request": a.cpu_ms,
            "DB ms/request": a.db_ms, "cores/instance": a.cores, "target utilisation": a.target_util},
           rows, ["CPU and DB ms per request come from a profile or APM of the real endpoint",
                  "p99 bursts need headroom beyond the average; add replicas for availability"],
           ["load test the endpoint at the expected rps and read CPU per request and pool wait time"],
           sens, a.json)


def cmd_bandwidth(a):
    rows = []
    for i, name in enumerate(("low", "expected", "high")):
        bps = a.rps[i] * a.payload_kb[i] * 1024 * 8
        day = a.rps[i] * a.payload_kb[i] * 1024 * 86400 * a.daily_duty
        rows.append({"scenario": name, "rps": f"{a.rps[i]:,.0f}", "payload": f"{a.payload_kb[i]:g} KB",
                     "Mbit/s": f"{bps / 1e6:,.1f}", "per day": human(day), "per month": human(day * 30)})
    report("Bandwidth", ["Mbit/s = rps × payload × 8", "per day = rps × payload × 86,400 × duty cycle"],
           {"rps": a.rps, "payload KB": a.payload_kb, "duty cycle (share of day at this rps)": a.daily_duty},
           rows, ["compression, CDN hits and protocol overhead not modelled"],
           ["read the load balancer / CDN metrics for bytes out per request"], as_json=a.json)


# ------------------------------------------------------------------------------------------ v19 commands

def contention_model(p):
    """Poisson arrivals on one key: P(conflict per attempt) = 1 − e^(−λ·w)."""
    lam, w = p["rps"], p["window_ms"] / 1000
    per_attempt = 1 - math.exp(-lam * w)
    visible = per_attempt ** (int(p["retries"]) + 1)
    extra_ms = sum(per_attempt ** k * (p["window_ms"] + p["backoff_ms"]) for k in range(1, int(p["retries"]) + 1))
    ceiling = 1000 / p["window_ms"] if p["window_ms"] else float("inf")
    return per_attempt, visible, extra_ms, ceiling


def cmd_contention(a):
    rows = []
    for i, name in enumerate(("low", "expected", "high")):
        p = {"rps": a.rps_per_key[i], "window_ms": a.window_ms[i], "retries": a.retries, "backoff_ms": a.backoff_ms}
        per, vis, extra, ceil = contention_model(p)
        verdict = "fine" if vis <= 0.01 else ("retry + clear UX" if vis <= 0.10 else "redesign (see contention.md)")
        rows.append({"scenario": name, "writes/s on one key": f"{p['rps']:g}", "read→write window": f"{p['window_ms']:g} ms",
                     "conflict per attempt": f"{per:.1%}", f"users rejected after {a.retries} retries": f"{vis:.2%}",
                     "extra latency (avg)": f"{extra:,.0f} ms", "max commits/s per key": f"{ceil:,.0f}", "verdict": verdict})
    exp = {"rps": a.rps_per_key[1], "window_ms": a.window_ms[1], "retries": a.retries, "backoff_ms": a.backoff_ms}
    sens = [x for x in sensitivity(lambda q: contention_model(q)[1] or 1e-12, exp) if x[0] in {"rps", "window_ms"}]
    report("Contention on one key (optimistic lock, unique slot, hot row)",
           ["P(conflict per attempt) = 1 − e^(−λ·w)   λ = writes/s on the same key, w = read→write window",
            "P(user sees a rejection) ≈ P^(retries+1)   (independent retries)",
            "extra latency ≈ Σ_k P^k × (w + backoff)",
            "max successful commits/s on one key ≈ 1000 ÷ w(ms)   (serialised)"],
           {"writes/s per key": a.rps_per_key, "window ms": a.window_ms, "retries": a.retries, "backoff ms": a.backoff_ms},
           rows, ["arrivals on the key are Poisson (flash sales are burstier: use the peak rate, not the average)",
                  "w is the time between reading the version and the write that checks it — measure it in the code path"],
           ["log 409/conflict responses per endpoint and key for a day, or replay a peak locally with k6/wrk "
            "against a local database and count conflicts"], sens, a.json)


def forecast_rows(a, i):
    """Month-by-month model for scenario i: users grow by (1+g) each month, rows by users × rate, minus retention."""
    users, g, rate = a.users[i], a.monthly_growth[i], a.rows_per_user_month[i]
    rows_total, months, per_month = a.existing_rows, [], []
    for m in range(1, a.months + 1):
        users_m = users * (1 + g) ** m
        new_rows = users_m * rate
        per_month.append(new_rows)
        rows_total += new_rows
        if a.retention_months and m > a.retention_months:
            rows_total -= per_month[m - a.retention_months - 1]
        data = rows_total * a.row_bytes * a.bloat[i]
        idx = rows_total * a.index_bytes_per_row * a.bloat[i]
        writes_avg = new_rows / (30 * 86400)
        writes_peak = writes_avg * a.peak_factor[i]
        hot = (idx + min(data, per_month[-1] * a.hot_months * a.row_bytes)) if data else 0
        restore_min = (data + idx) / (a.restore_mbps[i] * MB) / 60 if a.restore_mbps[i] else 0
        months.append({"month": m, "users": users_m, "rows": rows_total, "data": data, "index": idx,
                       "writes_avg": writes_avg, "writes_peak": writes_peak, "hot": hot, "restore_min": restore_min})
    return months


def thresholds(a, months):
    checks = []
    if a.ram_gb:
        checks.append(("hot set (indexes + recent data) > 70% of RAM", lambda r: r["hot"] > 0.7 * a.ram_gb * GB))
    if a.storage_gb:
        checks.append(("data + indexes > 80% of storage", lambda r: r["data"] + r["index"] > 0.8 * a.storage_gb * GB))
    if a.write_limit:
        checks.append((f"peak writes/s > {a.write_limit:g} (one primary)", lambda r: r["writes_peak"] > a.write_limit))
    if a.rto_minutes:
        checks.append((f"full restore > RTO {a.rto_minutes:g} min", lambda r: r["restore_min"] > a.rto_minutes))
    checks.append(("single table > 100M rows (partition/TTL question)", lambda r: r["rows"] > 1e8))
    out = []
    for label, fn in checks:
        hit = next((r["month"] for r in months if fn(r)), None)
        out.append((label, hit))
    return out


def cmd_forecast(a, only_thresholds=False):
    names = ("low", "expected", "high")
    table, breaks = [], {}
    for i, name in enumerate(names):
        months = forecast_rows(a, i)
        for r in months:
            if r["month"] in a.report_months:
                table.append({"scenario": name, "month": r["month"], "users": f"{r['users']:,.0f}",
                              "rows": f"{r['rows']:,.0f}", "data": human(r["data"]), "indexes": human(r["index"]),
                              "writes/s avg → peak": f"{r['writes_avg']:,.1f} → {r['writes_peak']:,.0f}",
                              "hot set": human(r["hot"]), "restore": f"{r['restore_min']:,.0f} min"})
        for label, hit in thresholds(a, months):
            breaks.setdefault(label, {})[name] = f"month {hit}" if hit else f"> {a.months} months"
    break_rows = [{"threshold": k, **v} for k, v in breaks.items()]
    formula = ["users(m) = users₀ × (1 + g)^m", "rows(m) = Σ users(k) × rows/user/month − rows older than retention",
               "size = rows × bytes/row × bloat (+ indexes × bloat)", "writes/s = new rows per month ÷ 2,592,000 × peak factor",
               "hot set ≈ indexes + last N months of data", "restore = (data + indexes) ÷ restore MB/s"]
    inputs = {"users now": a.users, "monthly growth": a.monthly_growth, "rows/user/month": a.rows_per_user_month,
              "bytes/row": a.row_bytes, "index bytes/row": a.index_bytes_per_row, "bloat": a.bloat,
              "peak factor": a.peak_factor, "retention months": a.retention_months or "keep all",
              "RAM GB": a.ram_gb, "storage GB": a.storage_gb, "write limit/s": a.write_limit, "RTO min": a.rto_minutes}
    exp_i = 1

    def expected_rows(q):
        a2 = argparse.Namespace(**{**vars(a), "users": (q["users"],) * 3, "monthly_growth": (q["growth"],) * 3,
                                   "rows_per_user_month": (q["rate"],) * 3})
        return forecast_rows(a2, 1)[-1]["rows"]
    sens = sensitivity(expected_rows, {"users": a.users[exp_i], "growth": a.monthly_growth[exp_i] or 1e-9,
                                       "rate": a.rows_per_user_month[exp_i]})
    verify = ["seed a local copy with the expected month-12 row count (generate_series / a load script) and read the real "
              "table + index size", "compare the growth rate with the production metric each month and re-run"]
    assumptions = ["compound growth continues for the whole horizon — the high case is the one to plan headroom for",
                   "bytes/row from `capacity.py rowsize`/`docsize` or a measured sample", "peak factor from real traffic (sales days)"]
    if not only_thresholds:
        report("Data growth forecast", formula, inputs, table, assumptions, verify, sens, a.json)
        if not a.json:
            print()
    report("When does it break (first month a threshold is crossed)", formula[-2:], inputs, break_rows,
           ["thresholds are planning lines, not engine limits: 70% RAM hot set, 80% disk, RTO from the business"],
           ["watch the same metrics in monitoring and set alerts at these lines"], None, a.json)


BSON = {"objectid": 12, "int32": 4, "int": 4, "int64": 8, "long": 8, "double": 8, "decimal128": 16, "decimal": 16,
        "bool": 1, "boolean": 1, "date": 8, "timestamp": 8, "null": 0, "uuid": 21}


def cmd_docsize(a):
    fields = [f.strip() for f in re.split(r",(?![^()]*\))", a.fields) if f.strip()]
    rows, total = [], 5            # int32 length + trailing 0x00
    for f in fields:
        m = re.match(r"^(?P<name>[\w.$]+)\s*:\s*(?P<type>\w+)(=(?P<avg>\d+))?$", f)
        if not m:
            raise SystemExit(f"bad field spec {f!r} (name:type[=avg])")
        name, typ, avg = m.group("name"), m.group("type").lower(), int(m.group("avg") or 0)
        head = 1 + len(name.encode()) + 1               # type byte + key cstring
        if typ in BSON:
            val = BSON[typ]
        elif typ in {"string", "str"}:
            val = 4 + (avg or 16) + 1
        elif typ in {"array", "object", "doc", "binary"}:
            val = avg or 64
        else:
            raise SystemExit(f"unknown type {typ}")
        rows.append({"field": name, "type": typ, "bytes": head + val})
        total += head + val
    per_doc = total
    lo, ex, hi = a.compression
    rows.append({"field": "**document (BSON)**", "type": "", "bytes": per_doc})
    for n in (1_000_000, 10_000_000, 100_000_000):
        rows.append({"field": f"{n:,} docs on disk (compressed ×{ex:g})", "type": "", "bytes": human(n * per_doc * ex)})
    report("MongoDB document size (BSON + WiredTiger)",
           ["field = 1 type byte + key name + 1 + value", "document = 4 + Σ fields + 1",
            "on disk ≈ BSON × compression ratio (snappy/zstd); every index ≈ key bytes + ~20 B per entry"],
           {"fields": a.fields, "compression ratio (low/exp/high)": a.compression}, rows,
           ["long field names cost bytes in EVERY document — short names matter at 100M docs",
            "arrays/objects: give their average stored size with =N"],
           ["insert a representative sample and read db.coll.stats() → avgObjSize, storageSize, totalIndexSize"],
           None, a.json)


def cmd_restore(a):
    rows = []
    for i, name in enumerate(("low", "expected", "high")):
        load_min = a.data_gb[i] * 1024 / a.restore_mbps[i] / 60
        idx_min = load_min * a.index_factor[i]
        replay_min = (a.wal_gb[i] * 1024 / a.restore_mbps[i] / 60) if a.wal_gb else 0
        total = load_min + idx_min + replay_min + a.fixed_minutes
        rows.append({"scenario": name, "data": f"{a.data_gb[i]:g} GB", "load": f"{load_min:,.0f} min",
                     "rebuild indexes": f"{idx_min:,.0f} min", "replay (PITR)": f"{replay_min:,.0f} min",
                     "total": f"{total:,.0f} min",
                     "within RTO?": ("yes" if total <= a.rto_minutes else "NO") if a.rto_minutes else "—"})
    report("Restore time vs RTO",
           ["load = data ÷ restore throughput", "indexes = load × index factor (logical restores rebuild them)",
            "replay = WAL/oplog to replay for point-in-time ÷ throughput", "total = load + indexes + replay + fixed steps"],
           {"data GB": a.data_gb, "restore MB/s": a.restore_mbps, "index factor": a.index_factor,
            "WAL/oplog GB": a.wal_gb or "none", "fixed minutes (provision, DNS, checks)": a.fixed_minutes,
            "RTO minutes": a.rto_minutes or "not set"}, rows,
           ["physical/snapshot restores skip the index rebuild (factor ≈ 0); logical dumps do not",
            "throughput is the slowest of: network, disk write, CPU for decompression"],
           ["time a real restore drill of the latest backup into a scratch instance; that number replaces this one"],
           None, a.json)

# ------------------------------------------------------------------------------------------ main


def _utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv=None) -> int:
    _utf8_console()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, engine=True):
        if engine:
            p.add_argument("--engine", choices=["postgres", "mysql"], default="postgres")
        p.add_argument("--json", action="store_true")

    p = sub.add_parser("rowsize")
    common(p)
    p.add_argument("--columns", required=True)
    p.set_defaults(fn=cmd_rowsize)

    p = sub.add_parser("growth")
    common(p)
    p.add_argument("--columns", required=True)
    p.add_argument("--users", type=triple, required=True)
    p.add_argument("--rows-per-user-month", type=triple, required=True)
    p.add_argument("--months", type=int, default=12)
    p.add_argument("--existing-rows", type=float, default=0)
    p.add_argument("--index", action="append", help="columns of one secondary index; repeat per index")
    p.add_argument("--bloat", type=triple, default=(1.1, 1.2, 1.5))
    p.add_argument("--replicas", type=int, default=0)
    p.add_argument("--price-gb-month", type=float, default=0.0)
    p.set_defaults(fn=cmd_growth)

    p = sub.add_parser("connections")
    common(p)
    p.add_argument("--connections", type=triple, required=True)
    p.add_argument("--base-mb", type=triple, default=None)
    p.add_argument("--active-ratio", type=triple, default=(0.1, 0.2, 0.4))
    p.add_argument("--work-mem-mb", type=triple, default=(4, 4, 16))
    p.add_argument("--ops-per-query", type=triple, default=(1, 2, 4))
    p.add_argument("--session-buffers-mb", type=triple, default=(1, 2, 8))
    p.add_argument("--shared-mb", type=float, default=0.0)
    p.set_defaults(fn=cmd_connections)

    p = sub.add_parser("throughput")
    common(p, engine=False)
    p.add_argument("--rps", type=triple, required=True)
    p.add_argument("--latency-ms", type=triple, required=True)
    p.add_argument("--cpu-ms", type=triple, required=True)
    p.add_argument("--db-ms", type=triple, default=(0, 0, 0))
    p.add_argument("--cores", type=float, default=2)
    p.add_argument("--target-util", type=float, default=0.6)
    p.set_defaults(fn=cmd_throughput)

    p = sub.add_parser("bandwidth")
    common(p, engine=False)
    p.add_argument("--rps", type=triple, required=True)
    p.add_argument("--payload-kb", type=triple, required=True)
    p.add_argument("--daily-duty", type=float, default=0.5)
    p.set_defaults(fn=cmd_bandwidth)

    p = sub.add_parser("contention", help="optimistic lock / hot row: rejection rate and ceiling")
    common(p, engine=False)
    p.add_argument("--rps-per-key", type=triple, required=True, help="writes/s on the SAME key (peak)")
    p.add_argument("--window-ms", type=triple, required=True, help="read-version → conditional write window")
    p.add_argument("--retries", type=int, default=0)
    p.add_argument("--backoff-ms", type=float, default=20)
    p.set_defaults(fn=cmd_contention)

    def forecast_args(p):
        common(p, engine=False)
        p.add_argument("--users", type=triple, required=True)
        p.add_argument("--monthly-growth", type=triple, default=(0.0, 0.0, 0.0), help="0.05 = +5%% per month")
        p.add_argument("--rows-per-user-month", type=triple, required=True)
        p.add_argument("--row-bytes", type=float, required=True, help="from rowsize/docsize or a measured sample")
        p.add_argument("--index-bytes-per-row", type=float, default=0.0)
        p.add_argument("--existing-rows", type=float, default=0.0)
        p.add_argument("--months", type=int, default=36)
        p.add_argument("--report-months", type=lambda t: [int(x) for x in t.split(",")], default=[6, 12, 24, 36])
        p.add_argument("--retention-months", type=int, default=0)
        p.add_argument("--bloat", type=triple, default=(1.1, 1.2, 1.5))
        p.add_argument("--peak-factor", type=triple, default=(3, 5, 10))
        p.add_argument("--hot-months", type=float, default=3.0, help="recent months counted in the hot set")
        p.add_argument("--ram-gb", type=float, default=0.0)
        p.add_argument("--storage-gb", type=float, default=0.0)
        p.add_argument("--write-limit", type=float, default=0.0, help="writes/s one primary sustains (measured)")
        p.add_argument("--restore-mbps", type=triple, default=(0, 0, 0))
        p.add_argument("--rto-minutes", type=float, default=0.0)

    p = sub.add_parser("forecast", help="data growth with compound growth, seasonality, retention + thresholds")
    forecast_args(p)
    p.set_defaults(fn=cmd_forecast)
    p = sub.add_parser("threshold", help="only the 'when does it break' table of forecast")
    forecast_args(p)
    p.set_defaults(fn=lambda a: cmd_forecast(a, only_thresholds=True))

    p = sub.add_parser("docsize", help="MongoDB BSON document size")
    common(p, engine=False)
    p.add_argument("--fields", required=True)
    p.add_argument("--compression", type=triple, default=(0.4, 0.55, 0.8))
    p.set_defaults(fn=cmd_docsize)

    p = sub.add_parser("restore", help="restore time vs RTO")
    common(p, engine=False)
    p.add_argument("--data-gb", type=triple, required=True)
    p.add_argument("--restore-mbps", type=triple, required=True)
    p.add_argument("--index-factor", type=triple, default=(0.0, 0.5, 1.0))
    p.add_argument("--wal-gb", type=triple, default=None)
    p.add_argument("--fixed-minutes", type=float, default=10)
    p.add_argument("--rto-minutes", type=float, default=0.0)
    p.set_defaults(fn=cmd_restore)

    a = ap.parse_args(argv)
    if getattr(a, "cmd", None) == "connections" and a.base_mb is None:
        a.base_mb = (2, 5, 10) if a.engine == "postgres" else (1, 1.5, 3)
    a.fn(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
