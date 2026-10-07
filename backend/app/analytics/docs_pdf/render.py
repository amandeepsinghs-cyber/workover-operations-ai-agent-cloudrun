"""Render DocSpecs to PDFs (reportlab) + ``<doc_id>.facts.json``.

    uv run python -m app.analytics.docs_pdf.render --field all [--types D1,D2] [--wells GK-129] [--workers 16]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import traceback
from collections import Counter
from functools import lru_cache
from multiprocessing import get_context
from pathlib import Path
from xml.sax.saxutils import escape

import yaml
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    KeepTogether,
    PageBreak as RLPageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer as RLSpacer,
    Table as RLTable,
    TableStyle,
)

from app.analytics.docs_pdf import ir
from app.analytics.docs_pdf.facts import DOC_TYPES, FIELDS, TYPE_DIRS, iter_specs, norm_type
from app.analytics.docs_pdf.provenance import compact_sources
from app.analytics.docs_pdf.paths import docs_dir, facts_path, pdf_path
from app.analytics.docs_pdf.templates import load_template

HERO_FILE = Path(__file__).parent / "templates" / "hero_text.yaml"
FOOTER_PREFIX = "WellPulse synthetic document corpus"
BANNER = "SYNTHETIC DATA - generated from WellPulse landing tables - not for operational use"
PAGE_W, PAGE_H = A4
MARGIN = 16 * mm


# --------------------------------------------------------------------------- styles
@lru_cache(maxsize=1)
def styles() -> dict[str, ParagraphStyle]:
    ss = getSampleStyleSheet()
    base = ParagraphStyle("body", parent=ss["BodyText"], fontName="Helvetica", fontSize=9, leading=12, alignment=TA_LEFT)
    return {
        "title": ParagraphStyle("title", parent=base, fontName="Helvetica-Bold", fontSize=14, leading=18, spaceAfter=4),
        "h1": ParagraphStyle("h1", parent=base, fontName="Helvetica-Bold", fontSize=11, leading=14, spaceBefore=8, spaceAfter=3,
                             textColor=colors.HexColor("#123b5c")),
        "h2": ParagraphStyle("h2", parent=base, fontName="Helvetica-Bold", fontSize=9.5, leading=12, spaceBefore=6, spaceAfter=2),
        "body": base,
        "note": ParagraphStyle("note", parent=base, fontSize=8, leading=10, textColor=colors.HexColor("#555555")),
        "small": ParagraphStyle("small", parent=base, fontSize=7.5, leading=9.5),
        "emphasis": ParagraphStyle("emphasis", parent=base, fontName="Helvetica-Bold"),
        "cell": ParagraphStyle("cell", parent=base, fontSize=7.5, leading=9),
        "cellh": ParagraphStyle("cellh", parent=base, fontName="Helvetica-Bold", fontSize=7.5, leading=9),
        "label": ParagraphStyle("label", parent=base, fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=colors.HexColor("#333333")),
        "value": ParagraphStyle("value", parent=base, fontSize=8.5, leading=10.5),
    }


TONES = {"info": "#e8f1fb", "warning": "#fff4e0", "danger": "#fde8e8", "success": "#e7f6ea"}


def _p(text: str, style: str) -> Paragraph:
    return Paragraph(escape(text), styles()[style])


# --------------------------------------------------------------------------- hero narratives
@lru_cache(maxsize=1)
def hero_narratives() -> dict[str, list[dict]]:
    if not HERO_FILE.exists():
        return {}
    data = yaml.safe_load(HERO_FILE.read_text()) or {}
    out: dict[str, list[dict]] = {}
    for item in data.get("narratives", []):
        out.setdefault(item["doc_id"], []).append(item)
    return out


def hero_blocks(spec: ir.DocSpec) -> list[ir.Block]:
    blocks: list[ir.Block] = []
    for item in hero_narratives().get(spec.doc_id, []):
        blocks.append(ir.H(item.get("heading", "Engineering narrative")))
        for para in item.get("paragraphs", []):
            blocks.append(ir.P(para))
        for b in item.get("bullets", []) and [ir.Bullets(item["bullets"])]:
            blocks.append(b)
        if item.get("callout"):
            blocks.append(ir.Callout(item["callout"], tone=item.get("tone", "warning")))
    return blocks


def compose(spec: ir.DocSpec) -> tuple[list[ir.Block], str]:
    """Template body + hero narrative + sign-off. Raises FactSlotError on rule breaks."""
    mod = load_template(spec.doc_type)
    body = list(mod.build(spec))
    for b in body:
        if not isinstance(b, ir.Block):
            raise ir.FactSlotError(f"{spec.doc_type}: template returned non-Block {type(b).__name__}")
    signoff = [b for b in body if isinstance(b, ir.Signoff)]
    body = [b for b in body if not isinstance(b, ir.Signoff)]
    return body + hero_blocks(spec) + (signoff or [ir.Signoff()]), mod.__name__.rsplit(".", 1)[-1]


# --------------------------------------------------------------------------- schematic
def _num(s: str) -> float | None:
    try:
        return float(str(s).replace(",", ""))
    except (TypeError, ValueError):
        return None


def schematic_drawing(spec: ir.DocSpec, filler: ir.SlotFiller, width: float, height: float) -> Drawing:
    d = Drawing(width, height)
    cas = list(spec.table("casing").rows)
    tub = list(spec.table("tubing").rows)
    perfs = list(spec.table("perfs").rows)
    fms = list(spec.table("formations").rows)
    depths = [_num(r.get("shoe_m")) for r in cas] + [_num(r.get("bottom_md_m")) for r in fms] + [_num(r.get("bottom_m")) for r in perfs]
    td = max([x for x in depths if x] or [1000.0])
    top_y, bot_y = height - 8, 14
    scale = (top_y - bot_y) / td
    y = lambda m: top_y - m * scale  # noqa: E731
    labels: list[list[str]] = []
    # formation column
    fx, fw = 4, 70
    shades = ["#f4ecd8", "#e9dcc0", "#ddd0b0", "#f0e6cc", "#e4d6b4"]
    for i, r in enumerate(fms):
        t, b = _num(r.get("top_md_m")), _num(r.get("bottom_md_m"))
        if t is None or b is None:
            continue
        d.add(Rect(fx, y(b), fw, max(y(t) - y(b), 0.5), fillColor=colors.HexColor(shades[i % len(shades)]), strokeColor=colors.grey, strokeWidth=0.3))
        d.add(String(fx + 2, y(t) - 7, r.get("formation", ""), fontName="Helvetica-Bold", fontSize=6))
        d.add(String(fx + 2, y(t) - 13, f"{r.get('top_md_m')} m", fontName="Helvetica", fontSize=5.5))
        labels.append([r.get("formation", ""), r.get("top_md_m", "")])
    # wellbore
    cx = fx + fw + 70
    ods = [_num(r.get("od_in")) or 0 for r in cas] or [1]
    max_od = max(ods)
    half = lambda od: 6 + 30 * (od / max_od)  # noqa: E731
    lx = cx + 50
    ly_used: list[float] = []

    def label(text: str, at_y: float):
        yy = at_y
        while any(abs(yy - u) < 7 for u in ly_used):
            yy -= 7
        ly_used.append(yy)
        d.add(String(lx, yy, text, fontName="Helvetica", fontSize=5.8))

    for r in sorted(cas, key=lambda r: -(_num(r.get("od_in")) or 0)):
        od, top, shoe, toc = _num(r.get("od_in")) or 0, _num(r.get("top_m")) or 0, _num(r.get("shoe_m")), _num(r.get("cement_top_m"))
        if shoe is None:
            continue
        hw = half(od)
        if toc is not None and toc < shoe:
            for sgn in (-1, 1):
                x0 = cx + sgn * hw
                d.add(Rect(min(x0, x0 + sgn * 4), y(shoe), 4, y(toc) - y(shoe), fillColor=colors.HexColor("#b9b9b9"), strokeColor=None))
        for sgn in (-1, 1):
            d.add(Line(cx + sgn * hw, y(top), cx + sgn * hw, y(shoe), strokeColor=colors.black, strokeWidth=1))
        d.add(Polygon([cx - hw, y(shoe), cx - hw - 4, y(shoe), cx - hw, y(shoe) + 5], fillColor=colors.black, strokeColor=None))
        d.add(Polygon([cx + hw, y(shoe), cx + hw + 4, y(shoe), cx + hw, y(shoe) + 5], fillColor=colors.black, strokeColor=None))
        txt = f"{r.get('string_type')} {r.get('od_in')} in, shoe {r.get('shoe_m')} m, cement top {r.get('cement_top_m')} m"
        label(txt, y(shoe))
        labels.append([r.get("string_type", ""), r.get("od_in", ""), r.get("shoe_m", ""), r.get("cement_top_m", "")])
    for r in perfs:
        t, b = _num(r.get("top_m")), _num(r.get("bottom_m"))
        if t is None or b is None:
            continue
        hw = half(min(ods)) if ods else 10
        steps = max(int((y(t) - y(b)) / 2.5), 1)
        for k in range(steps + 1):
            yy = y(t) - k * (y(t) - y(b)) / steps
            for sgn in (-1, 1):
                d.add(Line(cx + sgn * hw, yy, cx + sgn * (hw + 9), yy, strokeColor=colors.red, strokeWidth=0.8))
        label(f"Perforations {r.get('zone')} {r.get('top_m')} to {r.get('bottom_m')} m ({r.get('status')})", y(t))
        labels.append([r.get("zone", ""), r.get("top_m", ""), r.get("bottom_m", ""), r.get("status", "")])
    for r in tub:
        top, ln = _num(r.get("top_m")), _num(r.get("length_m"))
        if top is None or ln is None:
            continue
        comp = r.get("component", "")
        if comp == "TUBING":
            for sgn in (-1, 1):
                d.add(Line(cx + sgn * 3, y(top), cx + sgn * 3, y(top + ln), strokeColor=colors.HexColor("#1f5fa8"), strokeWidth=1))
        else:
            d.add(Rect(cx - 4.5, y(top + ln) - 1, 9, max(y(top) - y(top + ln), 3), fillColor=colors.HexColor("#1f5fa8"), strokeColor=None))
            label(f"{comp} at {r.get('top_m')} m", y(top))
            labels.append([comp, r.get("top_m", "")])
    d.add(String(cx - 20, 2, f"Total depth reference {spec.facts.get('total_depth_md_m', ir.MISSING)} m MD", fontName="Helvetica", fontSize=5.8))
    filler.used["total_depth_md_m"] = spec.facts.get("total_depth_md_m", ir.MISSING)
    rec = filler.used_tables.setdefault("schematic_labels", {"columns": [["label_values"]], "rows": [], "source": "casing_tally, tubing_string, perforation_intervals, formation_tops"})
    rec["rows"].extend(labels)
    return d


# --------------------------------------------------------------------------- flowables
def _col_widths(headers: list[str], rows: list[list[str]], total: float) -> list[float]:
    lens = []
    for i, h in enumerate(headers):
        longest = max([len(h)] + [len(r[i]) for r in rows[:50]])
        lens.append(min(max(longest, 4), 40))
    s = sum(lens)
    return [total * x / s for x in lens]


def to_flowables(block: ir.Block, spec: ir.DocSpec, filler: ir.SlotFiller) -> list:
    st = styles()
    width = PAGE_W - 2 * MARGIN
    if isinstance(block, ir.H):
        return [_p(filler.fill(block.text), "h1" if block.level <= 1 else "h2")]
    if isinstance(block, ir.P):
        return [_p(filler.fill(block.text), block.style if block.style in st else "body")]
    if isinstance(block, ir.Callout):
        t = RLTable([[_p(filler.fill(block.text), "body")]], colWidths=[width])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(TONES.get(block.tone, TONES["info"]))),
                               ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
                               ("LEFTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 4),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        return [RLSpacer(1, 2 * mm), t, RLSpacer(1, 2 * mm)]
    if isinstance(block, ir.KV):
        cells, row = [], []
        for label, value in block.pairs:
            row += [_p(filler.fill(label), "label"), _p(filler.fill(value), "value")]
            if len(row) == 2 * block.cols:
                cells.append(row)
                row = []
        if row:
            row += [""] * (2 * block.cols - len(row))
            cells.append(row)
        out = [_p(filler.fill(block.title), "h2")] if block.title else []
        if not cells:
            return out
        lw, vw = width * 0.18 * (2 / block.cols), width * 0.32 * (2 / block.cols)
        t = RLTable(cells, colWidths=[lw, vw] * block.cols)
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#dddddd")),
                               ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]))
        return out + [t]
    if isinstance(block, ir.Table):
        headers, rows = filler.table_rows(block)
        out = [_p(filler.fill(block.title), "h2")] if block.title else []
        if not rows:
            return out + [_p(filler.fill(block.empty_text), "note")]
        data = [[_p(h, "cellh") for h in headers]] + [[_p(c, "cell") for c in r] for r in rows]
        t = RLTable(data, colWidths=_col_widths(headers, rows, width), repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dfe8f1")),
                               ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#b0b8c0")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]))
        return out + [t, RLSpacer(1, 1.5 * mm)]
    if isinstance(block, ir.Bullets):
        out = []
        for i, it in enumerate(block.items, start=1):
            prefix = f"Step {i}. " if block.numbered else "\u2022 "
            out.append(Paragraph(("<b>" + escape(prefix) + "</b>" if block.numbered else escape(prefix)) + escape(filler.fill(it)),
                                 ParagraphStyle("li", parent=st["body"], leftIndent=10, firstLineIndent=-8 if not block.numbered else 0)))
        return out
    if isinstance(block, ir.Schematic):
        dr = schematic_drawing(spec, filler, width, 150 * mm)
        return [KeepTogether([dr, _p(filler.fill(block.caption), "note")])]
    if isinstance(block, ir.Signoff):
        cells = [[_p(filler.fill(r), "label"), _p("Name / signature / date", "note")] for r in block.roles]
        t = RLTable(cells, colWidths=[width * 0.3, width * 0.7])
        t.setStyle(TableStyle([("LINEBELOW", (1, 0), (1, -1), 0.4, colors.grey), ("TOPPADDING", (0, 0), (-1, -1), 6)]))
        return [RLSpacer(1, 4 * mm), t]
    if isinstance(block, ir.PageBreak):
        return [RLPageBreak()]
    if isinstance(block, ir.Spacer):
        return [RLSpacer(1, float(block.height_mm) * mm)]
    raise ir.FactSlotError(f"unknown block {type(block).__name__}")


def header_flowables(spec: ir.DocSpec, filler: ir.SlotFiller) -> list:
    pairs = [("Document", "{doc_id}"), ("Type", "{doc_type_name}"), ("Field", "{field}"), ("Date", "{doc_date}")]
    if spec.well_id:
        pairs.insert(3, ("Well", "{well_id}"))
    if "cluster_id" in spec.facts:
        pairs.append(("Cluster", "{cluster_id}"))
    return [_p(filler.fill("{doc_title}"), "title")] + to_flowables(ir.KV(pairs, cols=3), spec, filler) + [RLSpacer(1, 2 * mm)]


def _numbered_canvas(footer_id: str):
    class NumberedCanvas(rl_canvas.Canvas):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self._saved = []

        def showPage(self):
            self._saved.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._saved)
            for state in self._saved:
                self.__dict__.update(state)
                self.setFont("Helvetica", 6.5)
                self.setFillColor(colors.HexColor("#777777"))
                self.drawString(MARGIN, 9 * mm, f"{FOOTER_PREFIX} | {footer_id}")
                self.drawRightString(PAGE_W - MARGIN, 9 * mm, f"Page {self._pageNumber} of {total}")
                self.drawString(MARGIN, PAGE_H - 9 * mm, BANNER)
                super().showPage()
            super().save()

    return NumberedCanvas


def render_spec(spec: ir.DocSpec, root: Path | None = None) -> dict:
    """Render one document; returns its facts record (also written next to the PDF)."""
    blocks, template = compose(spec)
    filler = ir.SlotFiller(spec)
    story = header_flowables(spec, filler)
    for b in blocks:
        story += to_flowables(b, spec, filler)
    out = pdf_path(spec.field, spec.doc_type, spec.doc_id, root)
    out.parent.mkdir(parents=True, exist_ok=True)
    footer_id = filler.fill("{doc_id}")
    doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=14 * mm,
                            bottomMargin=14 * mm, title=spec.title, author="WellPulse corpus generator",
                            subject=DOC_TYPES[spec.doc_type])
    doc.build(story, canvasmaker=_numbered_canvas(footer_id))
    rec = {
        "doc_id": spec.doc_id, "doc_type": spec.doc_type, "doc_type_dir": TYPE_DIRS[spec.doc_type],
        "doc_type_name": DOC_TYPES[spec.doc_type], "field": spec.field, "well_id": spec.well_id,
        "doc_date": spec.doc_date, "title": spec.title, "template": template, "pages": doc.page,
        "has_text_layer": True, "bytes": out.stat().st_size,
        "facts": filler.used,
        "sources_ref": f"slot_catalogue/{spec.doc_type}.json",
        "sources": compact_sources(spec.doc_type, {k: spec.sources.get(k, "") for k in filler.used}),
        "tables": filler.used_tables,
        "meta": dict(spec.meta),
        "hero": spec.doc_id in hero_narratives(),
    }
    facts_path(spec.field, spec.doc_type, spec.doc_id, root).write_text(json.dumps(rec, separators=(",", ":"), default=str))
    return rec


# --------------------------------------------------------------------------- CLI
def _render_one(args) -> tuple[str, str, str | None, int]:
    spec, root = args
    try:
        rec = render_spec(spec, root)
        return spec.doc_type, spec.doc_id, None, rec["bytes"]
    except Exception as e:  # noqa: BLE001 - reported per document
        return spec.doc_type, spec.doc_id, f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}", 0


def parse_fields(s: str) -> list[str]:
    if s.lower() == "all":
        return list(FIELDS)
    m = {k.lower(): k for k in FIELDS}
    return [m[x.strip().lower()] for x in s.split(",") if x.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--field", default="all")
    ap.add_argument("--types", default=",".join(DOC_TYPES))
    ap.add_argument("--wells", default="")
    ap.add_argument("--workers", type=int, default=min(32, os.cpu_count() or 4))
    ap.add_argument("--out", default="")
    ap.add_argument("--clean", action="store_true", help="delete existing outputs of the selected types first")
    ap.add_argument("--limit", type=int, default=0, help="render at most N docs per type (smoke runs)")
    a = ap.parse_args(argv)
    root = Path(a.out) if a.out else docs_dir()
    fields = parse_fields(a.field)
    types = [norm_type(t) for t in a.types.split(",") if t.strip()]
    wells = [w.strip() for w in a.wells.split(",") if w.strip()] or None
    if a.clean:
        for fld in fields + (["ALL"] if "D11" in types else []):
            for t in types:
                p = pdf_path(fld, t, "x", root).parent
                if p.exists():
                    shutil.rmtree(p)
    t0 = time.time()
    specs = list(iter_specs(fields, types, wells))
    if a.limit:
        per: Counter = Counter()
        keep = []
        for s in specs:
            if per[s.doc_type] < a.limit or s.well_id in ("GK-129",):
                keep.append(s)
                per[s.doc_type] += 1
        specs = keep
    print(f"[render] {len(specs)} documents from facts in {time.time() - t0:.1f}s; rendering with {a.workers} workers")
    ok: Counter = Counter()
    nbytes: Counter = Counter()
    failures: list[tuple[str, str, str]] = []
    jobs = [(s, root) for s in specs]
    if a.workers <= 1:
        results = map(_render_one, jobs)
    else:
        pool = get_context("fork").Pool(a.workers)
        results = pool.imap_unordered(_render_one, jobs, chunksize=16)
    for t, doc_id, err, size in results:
        if err:
            failures.append((t, doc_id, err))
        else:
            ok[t] += 1
            nbytes[t] += size
    if a.workers > 1:
        pool.close()
        pool.join()
    for t in sorted(set(ok) | {f[0] for f in failures}):
        print(f"  {t} {DOC_TYPES[t]:<46} ok={ok[t]:>6}  failed={sum(1 for f in failures if f[0] == t):>4}  {nbytes[t] / 1e6:7.1f} MB")
    print(f"[render] done in {time.time() - t0:.1f}s; {sum(ok.values())} ok, {len(failures)} failed, {sum(nbytes.values()) / 1e6:.1f} MB")
    for t, doc_id, err in failures[:10]:
        print(f"  FAIL {t} {doc_id}: {err}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
