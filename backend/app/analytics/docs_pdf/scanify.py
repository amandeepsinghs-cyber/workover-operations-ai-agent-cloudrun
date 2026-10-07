"""Scanify: replace a deterministic subset of D1 / D5 PDFs with image-only "scans".

    uv run python -m app.analytics.docs_pdf.scanify --fraction 0.10 --types D1,D5

The scan is drawn from the same composed blocks and fact slots as the text PDF
(so it shows exactly the same numbers), rasterised with skew + speckle and saved
as a JPEG-in-PDF with no text layer. ``facts.json`` is updated with
``has_text_layer = false`` and ``scanned_text`` (per-page plain text) so the TF-IDF
index can still retrieve the document (flagged ``scanned = true``).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
import time
from functools import lru_cache
from multiprocessing import get_context
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import reportlab
from app.analytics.docs_pdf import ir
from app.analytics.docs_pdf.facts import FIELDS, iter_specs, norm_type, stable_hash
from app.analytics.docs_pdf.paths import docs_dir, facts_path, pdf_path
from app.analytics.docs_pdf.render import BANNER, FOOTER_PREFIX, compose

FORCED_SCANS = {"DOC-CBL-GK129-1998"}  # landing document_index flags this 1998 log as scanned (no text layer)
DPI = 110
PAGE_PX = (int(8.27 * DPI), int(11.69 * DPI))
MARGIN_PX = int(0.6 * DPI)
FONT_DIR = Path(reportlab.__file__).parent / "fonts"


@lru_cache(maxsize=8)
def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / ("VeraBd.ttf" if bold else "Vera.ttf")), size)


def text_lines(spec: ir.DocSpec) -> list[tuple[str, str]]:
    """Compose the document and flatten it to (style, text) lines using the same slot filler."""
    blocks, _ = compose(spec)
    f = ir.SlotFiller(spec)
    out: list[tuple[str, str]] = [("title", f.fill("{doc_title}"))]
    hdr = [("Document", "{doc_id}"), ("Type", "{doc_type_name}"), ("Field", "{field}"), ("Date", "{doc_date}")]
    if spec.well_id:
        hdr.insert(3, ("Well", "{well_id}"))
    if "cluster_id" in spec.facts:  # mirror render.header_flowables
        hdr.append(("Cluster", "{cluster_id}"))
    out.append(("body", "   ".join(f"{lbl}: {f.fill(v)}" for lbl, v in hdr)))
    out.append(("rule", ""))
    for b in blocks:
        if isinstance(b, ir.H):
            out.append(("h1" if b.level <= 1 else "h2", f.fill(b.text)))
        elif isinstance(b, (ir.P, ir.Callout)):
            out.append(("body", f.fill(b.text)))
        elif isinstance(b, ir.KV):
            if b.title:
                out.append(("h2", f.fill(b.title)))
            for label, value in b.pairs:
                out.append(("kv", f"{f.fill(label)}: {f.fill(value)}"))
        elif isinstance(b, ir.Table):
            headers, rows = f.table_rows(b)
            if b.title:
                out.append(("h2", f.fill(b.title)))
            if not rows:
                out.append(("body", f.fill(b.empty_text)))
                continue
            out.append(("th", " | ".join(headers)))
            for r in rows:
                out.append(("td", " | ".join(r)))
        elif isinstance(b, ir.Bullets):
            for i, it in enumerate(b.items, start=1):
                out.append(("body", (f"Step {i}. " if b.numbered else "- ") + f.fill(it)))
        elif isinstance(b, ir.Signoff):
            for r in b.roles:
                out.append(("body", f"{f.fill(r)}: ______________________"))
        elif isinstance(b, ir.Schematic):
            out.append(("body", "[wellbore schematic sheet attached in original]"))
    return out


def paginate(lines: list[tuple[str, str]]) -> list[list[tuple[str, str]]]:
    widths = {"title": 62, "h1": 78, "h2": 84, "body": 96, "kv": 96, "th": 110, "td": 110}
    heights = {"title": 30, "h1": 24, "h2": 20, "body": 17, "kv": 17, "th": 15, "td": 15, "rule": 10}
    usable = PAGE_PX[1] - 2 * MARGIN_PX - 40
    pages, cur, used = [], [], 0
    for style, text in lines:
        wrapped = textwrap.wrap(text, widths.get(style, 96)) or [""] if style != "rule" else [""]
        for w in wrapped:
            h = heights.get(style, 17)
            if used + h > usable:
                pages.append(cur)
                cur, used = [], 0
            cur.append((style, w))
            used += h
    if cur:
        pages.append(cur)
    return pages


def draw_pages(spec: ir.DocSpec, pages: list[list[tuple[str, str]]]) -> list[Image.Image]:
    rng = np.random.default_rng(stable_hash(spec.doc_id) % (2**32))
    sizes = {"title": (20, True), "h1": (15, True), "h2": (13, True), "body": (12, False), "kv": (12, False),
             "th": (10, True), "td": (10, False)}
    heights = {"title": 30, "h1": 24, "h2": 20, "body": 17, "kv": 17, "th": 15, "td": 15, "rule": 10}
    imgs = []
    for n, page in enumerate(pages, start=1):
        img = Image.new("L", PAGE_PX, color=int(rng.integers(232, 246)))
        d = ImageDraw.Draw(img)
        y = MARGIN_PX
        d.text((MARGIN_PX, 18), BANNER, fill=90, font=font(9))
        for style, text in page:
            if style == "rule":
                d.line([(MARGIN_PX, y + 4), (PAGE_PX[0] - MARGIN_PX, y + 4)], fill=60, width=1)
            else:
                sz, bold = sizes.get(style, (12, False))
                d.text((MARGIN_PX, y), text, fill=int(rng.integers(15, 45)), font=font(sz, bold))
            y += heights.get(style, 17)
        d.text((MARGIN_PX, PAGE_PX[1] - 40), f"{FOOTER_PREFIX} | {spec.doc_id}", fill=80, font=font(9))
        d.text((PAGE_PX[0] - MARGIN_PX - 90, PAGE_PX[1] - 40), f"Page {n} of {len(pages)}", fill=80, font=font(9))
        arr = np.asarray(img, dtype=np.int16)
        noise = rng.normal(0, 9, arr.shape)
        speck = rng.random(arr.shape) < 0.0015
        arr = np.clip(arr + noise, 0, 255)
        arr[speck] = rng.integers(0, 80)
        img = Image.fromarray(arr.astype(np.uint8), "L").rotate(float(rng.uniform(-0.8, 0.8)), resample=Image.BICUBIC,
                                                                  fillcolor=235)
        imgs.append(img)
    return imgs


def scan_one(args) -> tuple[str, str | None, int]:
    spec, root = args
    try:
        lines = text_lines(spec)
        pages = paginate(lines)
        imgs = draw_pages(spec, pages)
        out = pdf_path(spec.field, spec.doc_type, spec.doc_id, root)
        out.parent.mkdir(parents=True, exist_ok=True)
        imgs[0].save(str(out), "PDF", resolution=DPI, save_all=True, append_images=imgs[1:], quality=45)
        fp = facts_path(spec.field, spec.doc_type, spec.doc_id, root)
        rec = json.loads(fp.read_text()) if fp.exists() else {"doc_id": spec.doc_id}
        rec.update({"has_text_layer": False, "pages": len(imgs), "bytes": out.stat().st_size,
                    "scanned_text": ["\n".join(t for _, t in p) for p in pages], "scan_dpi": DPI})
        fp.write_text(json.dumps(rec, separators=(",", ":"), default=str))
        return spec.doc_id, None, out.stat().st_size
    except Exception as e:  # noqa: BLE001
        return spec.doc_id, f"{type(e).__name__}: {e}", 0


def select(specs: list[ir.DocSpec], fraction: float) -> list[ir.DocSpec]:
    """Deterministic ~fraction per (field, type) by stable hash, plus the forced historic scans."""
    groups: dict = {}
    for s in specs:
        groups.setdefault((s.field, s.doc_type), []).append(s)
    chosen = {}
    for _, ss in groups.items():
        k = max(1, round(len(ss) * fraction))
        for s in sorted(ss, key=lambda x: stable_hash("scan:" + x.doc_id))[:k]:
            chosen[s.doc_id] = s
    for s in specs:
        if s.doc_id in FORCED_SCANS:
            chosen[s.doc_id] = s
    return list(chosen.values())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fraction", type=float, default=0.10)
    ap.add_argument("--types", default="D1,D5")
    ap.add_argument("--field", default="all")
    ap.add_argument("--out", default="")
    ap.add_argument("--workers", type=int, default=min(16, os.cpu_count() or 4))
    a = ap.parse_args(argv)
    from app.analytics.docs_pdf.render import parse_fields

    root = Path(a.out) if a.out else docs_dir()
    types = [norm_type(t) for t in a.types.split(",")]
    t0 = time.time()
    specs = list(iter_specs(parse_fields(a.field), types))
    chosen = select(specs, a.fraction)
    jobs = [(s, root) for s in chosen]
    pool = get_context("fork").Pool(a.workers)
    res = list(pool.imap_unordered(scan_one, jobs, chunksize=4))
    pool.close()
    pool.join()
    bad = [r for r in res if r[1]]
    by = {}
    for s in chosen:
        by[(s.field, s.doc_type)] = by.get((s.field, s.doc_type), 0) + 1
    tot = {}
    for s in specs:
        tot[(s.field, s.doc_type)] = tot.get((s.field, s.doc_type), 0) + 1
    for k in sorted(by):
        print(f"  {k[0]:<9} {k[1]} scanned {by[k]:>3} of {tot[k]:>4}")
    print(f"[scanify] {len(res) - len(bad)} scanned, {len(bad)} failed, {sum(r[2] for r in res) / 1e6:.1f} MB, {time.time() - t0:.1f}s")
    for r in bad[:10]:
        print("  FAIL", r)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
