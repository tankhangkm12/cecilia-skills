#!/usr/bin/env python3
"""UI measurement helpers for Cecilia frontend roles — numbers, not eyeballing (v18.1).

  uikit.py contrast "#1d4ed8" "#ffffff"                  WCAG 2.x contrast ratio and AA/AAA verdicts
  uikit.py palette shot.png [--top 8] [--tokens tensura/docs/.../design-tokens.json]
                                                         dominant colours, share of pixels, nearest design
                                                         token (CIE76 delta-E) and contrast vs the dominant one
  uikit.py diff ref.png shot.png [--threshold 24] [--max-percent 2] [--out diff.png]
                                                         pixel difference between a design export / reference
                                                         image and a screenshot of the build

Works on PNG files (what Playwright, Penpot and Figma export). Standard library only; Python 3.9+.
Add --json for machine-readable output. `diff --max-percent N` exits 1 when the difference is above N.
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import zlib
from pathlib import Path


class UikitError(Exception):
    pass


# ------------------------------------------------------------------------------------------ colours

def parse_color(text: str):
    t = text.strip().lower()
    m = re.fullmatch(r"#?([0-9a-f]{3}|[0-9a-f]{4}|[0-9a-f]{6}|[0-9a-f]{8})", t)
    if m:
        h = m.group(1)
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    m = re.fullmatch(r"rgba?\(\s*(\d{1,3})\s*[, ]\s*(\d{1,3})\s*[, ]\s*(\d{1,3})\s*(?:[,/]\s*[\d.%]+\s*)?\)", t)
    if m:
        rgb = tuple(int(x) for x in m.groups())
        if all(0 <= x <= 255 for x in rgb):
            return rgb
    raise UikitError(f"cannot read colour {text!r} — use #rrggbb, #rgb or rgb(r, g, b)")


def hexcolor(rgb) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _lin(c: float) -> float:
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb) -> float:
    r, g, b = (_lin(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a, b) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def verdicts(ratio: float) -> dict:
    return {"AA text": ratio >= 4.5, "AA large text": ratio >= 3.0, "AAA text": ratio >= 7.0,
            "AAA large text": ratio >= 4.5, "non-text UI (1.4.11)": ratio >= 3.0}


def to_lab(rgb):
    r, g, b = (_lin(x) for x in rgb)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e(a, b) -> float:
    la, lb = to_lab(a), to_lab(b)
    return sum((p - q) ** 2 for p, q in zip(la, lb)) ** 0.5


# ------------------------------------------------------------------------------------------ PNG I/O

PNG_SIG = b"\x89PNG\r\n\x1a\n"
CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def read_png(path):
    """Return (width, height, pixels) with pixels a bytearray of RGBA, 4 bytes per pixel."""
    try:
        data = Path(path).read_bytes()
    except OSError as e:
        raise UikitError(f"cannot read {path}: {e}")
    if data[:8] != PNG_SIG:
        raise UikitError(f"{path} is not a PNG — export or screenshot as PNG")
    pos, idat, plte, trns, ihdr = 8, [], None, None, None
    while pos + 8 <= len(data):
        length = int.from_bytes(data[pos:pos + 4], "big")
        ctype = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if ctype == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", chunk)
        elif ctype == b"PLTE":
            plte = chunk
        elif ctype == b"tRNS":
            trns = chunk
        elif ctype == b"IDAT":
            idat.append(chunk)
        elif ctype == b"IEND":
            break
    if ihdr is None:
        raise UikitError(f"{path}: missing IHDR — damaged PNG")
    w, h, depth, ctype_, _comp, _filt, interlace = ihdr
    if interlace:
        raise UikitError(f"{path}: interlaced PNG is not supported — re-export without interlacing")
    allowed = {0: (1, 2, 4, 8, 16), 3: (1, 2, 4, 8)}.get(ctype_, (8, 16))
    if ctype_ not in CHANNELS or depth not in allowed:
        raise UikitError(f"{path}: unsupported PNG (colour type {ctype_}, bit depth {depth})")
    if ctype_ == 3 and plte is None:
        raise UikitError(f"{path}: palette PNG without PLTE — damaged PNG")
    try:
        raw = zlib.decompress(b"".join(idat))
    except zlib.error as e:
        raise UikitError(f"{path}: cannot decompress image data ({e})")
    ch = CHANNELS[ctype_]
    bits = ch * depth
    bpp = max(1, bits // 8)
    stride = (w * bits + 7) // 8
    if len(raw) < h * (stride + 1):
        raise UikitError(f"{path}: truncated image data")
    out = bytearray(w * h * 4)
    prev = bytearray(stride)
    o = 0
    for y in range(h):
        base = y * (stride + 1)
        ftype = raw[base]
        line = bytearray(raw[base + 1:base + 1 + stride])
        if ftype == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif ftype == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                upleft = prev[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + _paeth(left, prev[i], upleft)) & 0xFF
        elif ftype != 0:
            raise UikitError(f"{path}: bad filter type {ftype} on row {y}")
        prev = line
        if depth == 16:
            line = line[0::2]  # keep the high byte of each sample
        elif depth < 8:
            per = 8 // depth
            mask = (1 << depth) - 1
            samples = bytearray()
            for byte in line:
                for k in range(per):
                    samples.append((byte >> (8 - depth * (k + 1))) & mask)
            line = samples[:w]
            if ctype_ == 0:
                scale = 255 // mask
                line = bytearray(v * scale for v in line)
        for x in range(w):
            if ctype_ == 6:
                out[o:o + 4] = line[x * 4:x * 4 + 4]
            elif ctype_ == 2:
                out[o:o + 3] = line[x * 3:x * 3 + 3]
                out[o + 3] = 255
            elif ctype_ == 0:
                v = line[x]
                out[o:o + 4] = bytes((v, v, v, 255))
            elif ctype_ == 4:
                v, a = line[x * 2], line[x * 2 + 1]
                out[o:o + 4] = bytes((v, v, v, a))
            else:
                idx = line[x]
                out[o:o + 3] = plte[idx * 3:idx * 3 + 3]
                out[o + 3] = trns[idx] if trns is not None and idx < len(trns) else 255
            o += 4
    return w, h, out


def write_png(path, w, h, rgb: bytes):
    rows = b"".join(b"\x00" + rgb[y * w * 3:(y + 1) * w * 3] for y in range(h))

    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(PNG_SIG + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                           + chunk(b"IDAT", zlib.compress(rows, 6)) + chunk(b"IEND", b""))


# ------------------------------------------------------------------------------------------ tokens

def load_tokens(path):
    """Colour tokens from a design-tokens JSON (DTCG `$value`, `value` or plain strings; `{a.b}` aliases)."""
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise UikitError(f"cannot read tokens {path}: {e}")
    flat = {}

    def walk(node, prefix):
        if isinstance(node, dict):
            val = node.get("$value", node.get("value"))
            if isinstance(val, str):
                flat[prefix] = val
                return
            for k, v in node.items():
                if not k.startswith("$"):
                    walk(v, f"{prefix}.{k}" if prefix else k)
        elif isinstance(node, str):
            flat[prefix] = node

    walk(doc, "")
    colors = {}
    for name in flat:
        val, seen = flat[name], set()
        while isinstance(val, str) and val.startswith("{") and val.endswith("}") and val not in seen:
            seen.add(val)
            val = flat.get(val[1:-1], "")
        try:
            colors[name] = parse_color(val)
        except UikitError:
            continue
    if not colors:
        raise UikitError(f"{path}: no colour tokens found")
    return colors


def nearest_token(rgb, tokens):
    name = min(tokens, key=lambda n: delta_e(rgb, tokens[n]))
    return name, delta_e(rgb, tokens[name])


# ------------------------------------------------------------------------------------------ commands

def cmd_contrast(a):
    fg, bg = parse_color(a.fg), parse_color(a.bg)
    ratio = contrast_ratio(fg, bg)
    res = {"fg": hexcolor(fg), "bg": hexcolor(bg), "ratio": round(ratio, 2), "pass": verdicts(ratio)}
    if a.json:
        print(json.dumps(res, indent=2))
        return 0
    print(f"contrast {res['fg']} on {res['bg']} = {ratio:.2f}:1   (WCAG 2.x relative luminance)")
    for k, ok in res["pass"].items():
        print(f"  {'PASS' if ok else 'FAIL'}  {k}")
    return 0


def cmd_palette(a):
    w, h, px = read_png(a.image)
    step = max(1, a.step)
    buckets = {}
    total = 0
    for y in range(0, h, step):
        row = y * w * 4
        for x in range(0, w, step):
            i = row + x * 4
            if px[i + 3] < 128:
                continue
            key = (px[i] >> 3, px[i + 1] >> 3, px[i + 2] >> 3)
            b = buckets.get(key)
            if b is None:
                buckets[key] = [1, px[i], px[i + 1], px[i + 2]]
            else:
                b[0] += 1
                b[1] += px[i]
                b[2] += px[i + 1]
                b[3] += px[i + 2]
            total += 1
    if not total:
        raise UikitError(f"{a.image}: no opaque pixels")
    ranked = sorted(buckets.values(), key=lambda b: -b[0])
    merged = []  # merge buckets that are visually the same colour (delta-E < 2.3, one JND)
    for n, r, g, b in ranked:
        rgb = (round(r / n), round(g / n), round(b / n))
        for m in merged:
            if delta_e(rgb, m["rgb"]) < 2.3:
                m["count"] += n
                break
        else:
            merged.append({"rgb": rgb, "count": n})
        if len(merged) >= a.top * 4:
            break
    merged.sort(key=lambda m: -m["count"])
    merged = merged[:a.top]
    tokens = load_tokens(a.tokens) if a.tokens else None
    base = merged[0]["rgb"]
    rows = []
    for m in merged:
        row = {"hex": hexcolor(m["rgb"]), "share_pct": round(100.0 * m["count"] / total, 2),
               "contrast_vs_dominant": round(contrast_ratio(m["rgb"], base), 2)}
        if tokens:
            name, de = nearest_token(m["rgb"], tokens)
            row.update({"nearest_token": name, "token_hex": hexcolor(tokens[name]), "delta_e": round(de, 1)})
        rows.append(row)
    res = {"image": str(a.image), "size": [w, h], "sampled_pixels": total, "step": step, "colors": rows}
    if a.json:
        print(json.dumps(res, indent=2))
        return 0
    print(f"{a.image}: {w}x{h}, {total:,} opaque pixels sampled (every {step}px)")
    head = "| colour | share | contrast vs dominant |" + (" nearest token | ΔE |" if tokens else "")
    print(head)
    print("|---|---|---|" + ("---|---|" if tokens else ""))
    for r in rows:
        line = f"| {r['hex']} | {r['share_pct']:.2f}% | {r['contrast_vs_dominant']:.2f}:1 |"
        if tokens:
            line += f" {r['nearest_token']} ({r['token_hex']}) | {r['delta_e']:.1f} |"
        print(line)
    if tokens:
        print("ΔE < 2.3 ≈ same colour · 2.3–5 close (likely the token, check) · > 5 not a token → ask or add one")
    print("Sampled colours include anti-aliasing and photos; confirm text/background pairs with `contrast`.")
    return 0


def cmd_diff(a):
    wa, ha, pa = read_png(a.ref)
    wb, hb, pb = read_png(a.shot)
    w, h = min(wa, wb), min(ha, hb)
    thr = a.threshold
    diff = 0
    minx, miny, maxx, maxy = w, h, -1, -1
    out = bytearray(w * h * 3) if a.out else None
    for y in range(h):
        ra, rb = y * wa * 4, y * wb * 4
        for x in range(w):
            i, j = ra + x * 4, rb + x * 4
            d = max(abs(pa[i] - pb[j]), abs(pa[i + 1] - pb[j + 1]), abs(pa[i + 2] - pb[j + 2]))
            if d > thr:
                diff += 1
                if x < minx:
                    minx = x
                if x > maxx:
                    maxx = x
                if y < miny:
                    miny = y
                if y > maxy:
                    maxy = y
                if out is not None:
                    k = (y * w + x) * 3
                    out[k:k + 3] = b"\xff\x00\x3c"
            elif out is not None:
                k = (y * w + x) * 3
                g = 170 + (pa[i] * 30 + pa[i + 1] * 59 + pa[i + 2] * 11) // 100 // 3
                out[k:k + 3] = bytes((g, g, g))
    area = w * h
    pct = 100.0 * diff / area if area else 0.0
    res = {"ref": str(a.ref), "shot": str(a.shot), "ref_size": [wa, ha], "shot_size": [wb, hb],
           "compared": [w, h], "threshold": thr, "different_pixels": diff, "different_pct": round(pct, 3),
           "bbox": [minx, miny, maxx, maxy] if diff else None, "size_mismatch": (wa, ha) != (wb, hb)}
    if a.out:
        write_png(a.out, w, h, bytes(out))
        res["diff_image"] = str(a.out)
    failed = a.max_percent is not None and pct > a.max_percent
    res["verdict"] = None if a.max_percent is None else ("FAIL" if failed else "PASS")
    if a.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"ref  {a.ref}: {wa}x{ha}\nshot {a.shot}: {wb}x{hb}")
        if res["size_mismatch"]:
            print(f"WARNING: sizes differ — compared the top-left {w}x{h}. Screenshot at the reference size "
                  f"(playwright-cli resize {wa} {ha}) for a fair number.")
        print(f"different pixels: {diff:,} of {area:,} = {pct:.3f}%  (a channel differs by > {thr})")
        if diff:
            print(f"difference box: x {minx}–{maxx}, y {miny}–{maxy}")
        if a.out:
            print(f"diff image: {a.out} (red = different)")
        if res["verdict"]:
            print(f"verdict vs --max-percent {a.max_percent}: {res['verdict']}")
        print("Fonts, anti-aliasing and live data move pixels; use the box and the diff image to judge, "
              "the percentage to track progress.")
    return 1 if failed else 0


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("contrast", help="WCAG contrast ratio of two colours")
    c.add_argument("fg")
    c.add_argument("bg")
    p = sub.add_parser("palette", help="dominant colours of a PNG")
    p.add_argument("image")
    p.add_argument("--top", type=int, default=8)
    p.add_argument("--step", type=int, default=2, help="sample every Nth pixel (default 2)")
    p.add_argument("--tokens", help="design-tokens JSON to map colours to")
    d = sub.add_parser("diff", help="pixel difference of two PNGs")
    d.add_argument("ref")
    d.add_argument("shot")
    d.add_argument("--threshold", type=int, default=24, help="max per-channel difference counted as equal")
    d.add_argument("--max-percent", type=float, help="exit 1 when the difference is above this")
    d.add_argument("--out", help="write a diff image (PNG)")
    for s in (c, p, d):
        s.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        return {"contrast": cmd_contrast, "palette": cmd_palette, "diff": cmd_diff}[a.cmd](a)
    except UikitError as e:
        print(f"uikit: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
