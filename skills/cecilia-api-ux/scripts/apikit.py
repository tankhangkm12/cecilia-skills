#!/usr/bin/env python3
"""apikit — look at an API the way its consumers meet it (cecilia-api-ux, v19).

    apikit.py summary  api.yaml               # consistency lint: naming, pagination, errors, formats, status codes
    apikit.py journey  --calls "GET /cart > GET /products/{id} x12, GET /vouchers > POST /orders" --latency-ms 80
    apikit.py diff     old.yaml new.yaml      # what would break an existing client
    add --json to any command.

journey syntax: stages separated by ">" run one after another; calls separated by "," inside a stage run in
parallel; "xN" repeats a call N times (the N+1 pattern). The critical path is the sum of each stage's
slowest call. Latency per call: --latency-ms (one value or LOW,EXPECTED,HIGH).

Reads OpenAPI 3 as JSON, or YAML (PyYAML when installed; otherwise a built-in reader for the plain block
YAML specs are written in — anchors and flow collections spanning lines are not supported). Standard
library only; Python 3.9+. Everything it prints is [projected] or [verified from the spec]; it never calls
the API.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

METHODS = ("get", "put", "post", "delete", "patch", "options", "head")


# --------------------------------------------------------------------------- loading

def _scalar(v: str):
    v = v.strip()
    if v == "" or v == "~" or v == "null":
        return None
    if v in {"true", "True"}:
        return True
    if v in {"false", "False"}:
        return False
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [_scalar(x) for x in re.split(r",(?![^\[]*\])", inner)] if inner else []
    if v.startswith("{") and v.endswith("}"):
        inner = v[1:-1].strip()
        out = {}
        for part in re.split(r",(?![^{]*})", inner) if inner else []:
            k, _, val = part.partition(":")
            out[k.strip().strip("'\"")] = _scalar(val)
        return out
    if re.match(r"^-?\d+$", v):
        return int(v)
    if re.match(r"^-?\d+\.\d+$", v):
        return float(v)
    return v


def mini_yaml(text: str):
    """Block-style YAML subset: mappings, sequences, scalars, | and > block scalars, comments."""
    lines = []
    for raw in text.splitlines():
        if raw.strip().startswith("#") or not raw.strip() or raw.strip() in {"---", "..."}:
            lines.append(None if not raw.strip() else ("comment", raw))
            continue
        lines.append(("line", raw))
    rows = [(len(r[1]) - len(r[1].lstrip(" ")), r[1].strip()) if r and r[0] == "line" else None for r in lines]
    pos = 0

    def strip_comment(s: str) -> str:
        return re.sub(r"\s+#.*$", "", s) if "'" not in s and '"' not in s else s

    def block_scalar(indent: int, indicator: str):
        style = indicator[0]
        nonlocal pos
        out = []
        while pos < len(rows):
            r = rows[pos]
            if r is None:
                out.append("")
                pos += 1
                continue
            if r[0] <= indent:
                break
            out.append(lines[pos][1][indent + 2 if style else 0:].rstrip())
            pos += 1
        while out and out[-1] == "":
            out.pop()
        text = ("\n" if style == "|" else " ").join(x.strip() for x in out)
        return text if indicator.endswith("-") else text + "\n"

    def parse(indent: int):
        nonlocal pos
        while pos < len(rows) and rows[pos] is None:
            pos += 1
        if pos >= len(rows):
            return None
        ind, s = rows[pos]
        if s.startswith("- ") or s == "-":
            seq = []
            while pos < len(rows):
                while pos < len(rows) and rows[pos] is None:
                    pos += 1
                if pos >= len(rows):
                    break
                ind2, s2 = rows[pos]
                if ind2 != ind or not (s2.startswith("- ") or s2 == "-"):
                    break
                item = strip_comment(s2[2:].strip()) if s2 != "-" else ""
                if not item:
                    pos += 1
                    seq.append(parse(ind + 2))
                elif re.match(r"^[^'\"{\[][^:]*:\s", item + " ") and not item.startswith("{"):
                    rows[pos] = (ind + 2, item)          # "- key: value" starts a mapping at ind+2
                    lines[pos] = ("line", " " * (ind + 2) + item)
                    seq.append(parse(ind + 2))
                else:
                    pos += 1
                    seq.append(_scalar(item))
            return seq
        mapping = {}
        while pos < len(rows):
            while pos < len(rows) and rows[pos] is None:
                pos += 1
            if pos >= len(rows):
                break
            ind2, s2 = rows[pos]
            if ind2 < ind or (ind2 == ind and (s2.startswith("- ") or s2 == "-")):
                break
            if ind2 > ind:
                raise ValueError(f"unexpected indentation at line {pos + 1}")
            m = re.match(r"^(\"[^\"]*\"|'[^']*'|[^:]+?)\s*:(\s+(.*))?$", s2)
            if not m:
                raise ValueError(f"cannot read line {pos + 1}: {s2[:60]}")
            key = m.group(1).strip("'\"")
            val = strip_comment((m.group(3) or "").strip())
            pos += 1
            if val in {"|", ">", "|-", ">-", "|+", ">+"}:
                mapping[key] = block_scalar(ind, val)
            elif val.startswith("&") or val.startswith("*"):
                raise ValueError("YAML anchors are not supported by the built-in reader — install PyYAML or use JSON")
            elif val == "":
                nxt = next((r for r in rows[pos:] if r is not None), None)
                mapping[key] = parse(nxt[0]) if nxt and (nxt[0] > ind or (nxt[0] == ind and nxt[1].startswith("-"))) else None
            else:
                mapping[key] = _scalar(val)
        return mapping

    return parse(0)


def load(path: str) -> dict:
    text = Path(path).read_text(encoding="utf-8-sig")
    if path.endswith(".json") or text.lstrip().startswith("{"):
        return json.loads(text)
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text)
    except ImportError:
        return mini_yaml(text)


def resolve(spec: dict, node):
    """Follow a local $ref once (#/components/...)."""
    seen = 0
    while isinstance(node, dict) and "$ref" in node and seen < 20:
        ref = node["$ref"]
        if not ref.startswith("#/"):
            return node
        cur = spec
        for part in ref[2:].split("/"):
            cur = (cur or {}).get(part.replace("~1", "/").replace("~0", "~"), {})
        node = cur
        seen += 1
    return node


def operations(spec: dict):
    for path, item in (spec.get("paths") or {}).items():
        for method in METHODS:
            op = (item or {}).get(method)
            if isinstance(op, dict):
                yield path, method.upper(), op, item


# --------------------------------------------------------------------------- summary

def case_style(name: str) -> str:
    if "_" in name:
        return "snake"
    if "-" in name:
        return "kebab"
    if re.search(r"[a-z][A-Z]", name):
        return "camel"
    return "lower"


def schema_fields(spec, schema, depth=0):
    schema = resolve(spec, schema) or {}
    if depth > 4 or not isinstance(schema, dict):
        return {}
    out = {}
    for combo in ("allOf", "oneOf", "anyOf"):
        for part in schema.get(combo) or []:
            out.update(schema_fields(spec, part, depth + 1))
    if schema.get("type") == "array" or "items" in schema:
        out.update(schema_fields(spec, schema.get("items") or {}, depth + 1))
    for k, v in (schema.get("properties") or {}).items():
        out[k] = resolve(spec, v) or {}
    return out


def summary(spec: dict) -> dict:
    findings, ops = [], list(operations(spec))
    path_styles, field_styles, page_params, error_shapes, ids = {}, {}, {}, {}, {}
    for path, method, op, item in ops:
        where = f"{method} {path}"
        for seg in [s for s in path.split("/") if s and not s.startswith("{")]:
            path_styles.setdefault(case_style(seg), []).append(where)
        for p in [resolve(spec, p) for p in (op.get("parameters") or []) + (item.get("parameters") or [])]:
            if not isinstance(p, dict):
                continue
            n = p.get("name", "")
            if p.get("in") == "path":
                ids.setdefault(n, []).append(where)
            if p.get("in") == "query" and n.lower() in {"page", "limit", "offset", "cursor", "pagesize", "page_size",
                                                         "per_page", "size", "after", "before", "take", "skip"}:
                page_params.setdefault(n, []).append(where)
        responses = op.get("responses") or {}
        codes = [str(c) for c in responses]
        if not any(c.startswith("4") for c in codes):
            findings.append(("SHOULD-FIX", where, "no 4xx response documented — the client cannot plan for errors"))
        if method in {"POST", "PUT", "PATCH", "DELETE"} and "409" not in codes and re.search(r"(order|pay|stock|book|reserv|voucher|coupon|transfer)", path, re.I):
            findings.append(("QUESTION", where, "state-changing money/stock endpoint without 409 — what does a concurrent "
                                                "update return, and what does the user see?"))
        if method == "POST" and re.search(r"(order|pay|checkout|transfer|charge|book)", path, re.I):
            hdrs = [p for p in (op.get("parameters") or []) if isinstance(resolve(spec, p), dict)
                    and resolve(spec, p).get("in") == "header" and "idempot" in resolve(spec, p).get("name", "").lower()]
            if not hdrs:
                findings.append(("SHOULD-FIX", where, "no Idempotency-Key — a retried request after a timeout can charge/"
                                                      "order twice; the client cannot retry safely"))
        for code, resp in responses.items():
            resp = resolve(spec, resp) or {}
            for mt, body in ((resp.get("content") or {}).items()):
                fields = schema_fields(spec, (body or {}).get("schema") or {})
                if str(code).startswith(("4", "5")):
                    error_shapes.setdefault(",".join(sorted(fields)) or "(none)", []).append(f"{where} {code}")
                for fname, fs in fields.items():
                    field_styles.setdefault(case_style(fname), []).append(f"{where}.{fname}")
                    if re.search(r"(price|amount|total|cost|balance|fee)", fname, re.I) and fs.get("type") == "number" \
                            and fs.get("format") not in {"decimal"}:
                        findings.append(("SHOULD-FIX", f"{where}.{fname}", "money as a JSON number (float) — use a string "
                                                                            "decimal or integer minor units"))
                    if re.search(r"(At|_at|date|time)$", fname) and fs.get("type") == "string" and not fs.get("format"):
                        findings.append(("SUGGESTION", f"{where}.{fname}", "date/time without format (date-time, RFC 3339)"))
                if method == "GET" and str(code) == "200":
                    sch = resolve(spec, (body or {}).get("schema") or {}) or {}
                    is_list = sch.get("type") == "array" or any((resolve(spec, v) or {}).get("type") == "array"
                                                                 for v in (sch.get("properties") or {}).values())
                    has_page = any(where in v for v in page_params.values())
                    if is_list and not has_page and not path.endswith("}"):
                        findings.append(("SHOULD-FIX", where, "list without pagination — grows with the data; the client "
                                                              "downloads everything"))
    if len(path_styles) > 1:
        findings.append(("SUGGESTION", "paths", f"mixed path naming styles: {sorted(path_styles)}"))
    styles = {k: len(v) for k, v in field_styles.items() if k != "lower"}
    if len(styles) > 1:
        findings.append(("SHOULD-FIX", "fields", f"mixed field naming styles {styles} — pick one"))
    if len(page_params) > 2:
        findings.append(("SHOULD-FIX", "pagination", f"{len(page_params)} different pagination parameter names: "
                                                     f"{sorted(page_params)} — one convention"))
    if len([k for k in error_shapes if k != "(none)"]) > 1:
        findings.append(("SHOULD-FIX", "errors", f"{len(error_shapes)} different error body shapes — the client needs "
                                                 "one parser (e.g. RFC 9457 problem+json)"))
    idn = [n for n in ids if n.lower() in {"id"}]
    if idn and len(ids) > 3 and len({n for n in ids if n.lower().endswith("id")}) > 1 and "id" in ids:
        findings.append(("SUGGESTION", "path params", "both `{id}` and `{somethingId}` used — one style"))
    return {"operations": len(ops), "paths": len(spec.get("paths") or {}),
            "pagination_params": sorted(page_params), "error_shapes": len(error_shapes),
            "findings": [{"severity": s, "where": w, "finding": f} for s, w, f in findings]}


# --------------------------------------------------------------------------- journey

def journey(calls: str, latency: tuple) -> dict:
    stages = [s.strip() for s in calls.split(">") if s.strip()]
    rows, total, depth, n_plus_one = [], 0, 0, []
    for i, st in enumerate(stages, 1):
        parts = [p.strip() for p in st.split(",") if p.strip()]
        stage_calls = 0
        for p in parts:
            m = re.search(r"\s+x(\d+)$", p)
            n = int(m.group(1)) if m else 1
            name = re.sub(r"\s+x\d+$", "", p)
            stage_calls += n
            if n > 1:
                n_plus_one.append(f"{name} ×{n}")
            rows.append({"stage": i, "call": name, "times": n})
        total += stage_calls
        depth += 1
    crit = [depth * lat for lat in latency]
    return {"stages": depth, "requests": total, "critical_path_ms": crit, "n_plus_one": n_plus_one, "calls": rows}


# --------------------------------------------------------------------------- diff

def diff(old: dict, new: dict) -> list[dict]:
    out = []
    o_ops = {(p, m): op for p, m, op, _ in operations(old)}
    n_ops = {(p, m): op for p, m, op, _ in operations(new)}
    for key in o_ops:
        if key not in n_ops:
            out.append({"breaking": True, "where": f"{key[1]} {key[0]}", "change": "endpoint removed"})
    for key, nop in n_ops.items():
        oop = o_ops.get(key)
        if oop is None:
            continue
        where = f"{key[1]} {key[0]}"
        oreq = {p.get("name"): p for p in [resolve(old, x) for x in oop.get("parameters") or []] if isinstance(p, dict)}
        nreq = {p.get("name"): p for p in [resolve(new, x) for x in nop.get("parameters") or []] if isinstance(p, dict)}
        for n, p in nreq.items():
            if p.get("required") and (n not in oreq or not oreq[n].get("required")):
                out.append({"breaking": True, "where": where, "change": f"parameter '{n}' is now required"})
        ob = ((oop.get("requestBody") or {}).get("content") or {})
        nb = ((nop.get("requestBody") or {}).get("content") or {})
        for mt in nb:
            os_ = resolve(old, (ob.get(mt) or {}).get("schema") or {}) or {}
            ns = resolve(new, (nb.get(mt) or {}).get("schema") or {}) or {}
            added_req = set(ns.get("required") or []) - set(os_.get("required") or [])
            for f in sorted(added_req):
                out.append({"breaking": True, "where": where, "change": f"request field '{f}' is now required"})
        for code, oresp in (oop.get("responses") or {}).items():
            nresp = (nop.get("responses") or {}).get(code)
            if nresp is None:
                if str(code).startswith("2"):
                    out.append({"breaking": True, "where": where, "change": f"response {code} removed"})
                continue
            for mt, obody in ((resolve(old, oresp) or {}).get("content") or {}).items():
                nbody = ((resolve(new, nresp) or {}).get("content") or {}).get(mt)
                if not nbody:
                    continue
                of = schema_fields(old, obody.get("schema") or {})
                nf = schema_fields(new, nbody.get("schema") or {})
                for f in of:
                    if f not in nf:
                        out.append({"breaking": True, "where": f"{where} {code}", "change": f"response field '{f}' removed"})
                    elif of[f].get("type") != nf[f].get("type"):
                        out.append({"breaking": True, "where": f"{where} {code}",
                                    "change": f"'{f}' type {of[f].get('type')} → {nf[f].get('type')}"})
                    elif of[f].get("enum") and nf[f].get("enum") and set(nf[f]["enum"]) > set(of[f]["enum"]):
                        out.append({"breaking": False, "where": f"{where} {code}",
                                    "change": f"'{f}' enum gained {sorted(set(nf[f]['enum']) - set(of[f]['enum']))} — "
                                              "old clients must tolerate unknown values"})
    return out


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("summary")
    p.add_argument("spec")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("journey")
    p.add_argument("--calls", required=True)
    p.add_argument("--latency-ms", default="80", help="one value or LOW,EXPECTED,HIGH per call")
    p.add_argument("--screen", default="")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("diff")
    p.add_argument("old")
    p.add_argument("new")
    p.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.cmd == "summary":
        r = summary(load(a.spec))
        if a.json:
            print(json.dumps(r, indent=2, ensure_ascii=False))
        else:
            print(f"{r['operations']} operations on {r['paths']} paths · pagination params {r['pagination_params'] or '—'} "
                  f"· {r['error_shapes']} error body shape(s)  [verified from the spec]")
            for f in r["findings"]:
                print(f"  {f['severity']:10} {f['where']:40} {f['finding']}")
        return 0
    if a.cmd == "journey":
        lat = tuple(float(x) for x in a.latency_ms.split(","))
        lat = lat * 3 if len(lat) == 1 else lat
        r = journey(a.calls, lat)
        if a.json:
            print(json.dumps(r, indent=2))
        else:
            print(f"{a.screen or 'screen'}: {r['requests']} requests in {r['stages']} sequential stage(s) · critical path "
                  f"≈ {' / '.join(f'{x:,.0f}' for x in r['critical_path_ms'])} ms (low/exp/high)  [projected]")
            if r["n_plus_one"]:
                print("  N+1 on the client: " + ", ".join(r["n_plus_one"]) + " — batch endpoint, include/expand, or embed")
        return 0
    r = diff(load(a.old), load(a.new))
    if a.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        br = [x for x in r if x["breaking"]]
        print(f"{len(br)} breaking change(s), {len(r) - len(br)} to note  [verified from the specs]")
        for x in r:
            print(f"  {'BREAKING' if x['breaking'] else 'note':8} {x['where']:40} {x['change']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
