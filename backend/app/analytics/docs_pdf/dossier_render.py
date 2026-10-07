"""Dossier PDF renderer and vector wellbore schematic for WellPulse.

Renders multi-page executive well dossiers using ReportLab flowables.
Follows the fact-slot rule: zero digits or spelled-out numbers in code strings.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Line, Polygon, PolyLine, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    TableStyle,
)
from reportlab.platypus import (
    Spacer as RLSpacer,
)
from reportlab.platypus import (
    Table as RLTable,
)

PAGE_W, PAGE_H = A4
MARGIN = 16 * mm

TONE_COLORS = {
    "info": colors.HexColor(0xe8f1fb),
    "warning": colors.HexColor(0xfff4e0),
    "danger": colors.HexColor(0xfde8e8),
    "success": colors.HexColor(0xe7f6ea),
}

LITHO_SHADES = (0xf4ecd8, 0xe9dcc0, 0xddd0b0, 0xf0e6cc, 0xe4d6b4)


@lru_cache(maxsize=1)
def styles() -> dict[str, ParagraphStyle]:
    ss = getSampleStyleSheet()
    base = ParagraphStyle(
        "body",
        parent=ss["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        alignment=TA_LEFT,
        spaceAfter=3,
    )
    return {
        "title": ParagraphStyle(
            "title",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            spaceAfter=4,
            textColor=colors.HexColor(0x123b5c),
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=base,
            fontSize=9.5,
            leading=13,
            spaceAfter=6,
            textColor=colors.HexColor(0x555555),
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            spaceBefore=6,
            spaceAfter=2,
            textColor=colors.HexColor(0x123b5c),
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12,
            spaceBefore=4,
            spaceAfter=2,
            textColor=colors.HexColor(0x123b5c),
            keepWithNext=True,
        ),
        "body": base,
        "note": ParagraphStyle(
            "note",
            parent=base,
            fontSize=8,
            leading=10,
            textColor=colors.HexColor(0x555555),
            spaceAfter=2,
        ),
        "small": ParagraphStyle(
            "small",
            parent=base,
            fontSize=7.5,
            leading=9.5,
        ),
        "emphasis": ParagraphStyle(
            "emphasis",
            parent=base,
            fontName="Helvetica-Bold",
        ),
        "unavailable": ParagraphStyle(
            "unavailable",
            parent=base,
            fontName="Helvetica-Oblique",
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor(0x9b1c1c),
            spaceAfter=2,
        ),
        "cell": ParagraphStyle(
            "cell",
            parent=base,
            fontSize=7.5,
            leading=9,
            spaceAfter=0,
        ),
        "cellh": ParagraphStyle(
            "cellh",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9,
            spaceAfter=0,
        ),
        "label": ParagraphStyle(
            "label",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor(0x333333),
            spaceAfter=0,
        ),
        "value": ParagraphStyle(
            "value",
            parent=base,
            fontSize=8.5,
            leading=10.5,
            spaceAfter=0,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=base,
            leftIndent=10,
            firstLineIndent=-8,
            spaceAfter=2,
        ),
    }


def _p(text: str, style_name: str) -> Paragraph:
    st = styles()
    style = st.get(style_name, st["body"])
    return Paragraph(escape(str(text or "")), style)


def _col_widths(headers: list[str], rows: list[list[str]], total: float) -> list[float]:
    if not headers:
        return []
    lens = []
    for i, h in enumerate(headers):
        longest = max([len(str(h))] + [len(str(r[i])) if i < len(r) else 0 for r in rows[:50]])
        lens.append(min(max(longest, 4), 40))
    s = sum(lens)
    if s <= 0:
        return [total / len(headers)] * len(headers)
    return [total * x / s for x in lens]


def _render_p(block: dict) -> list:
    st_name = block.get("style", "body")
    text = block.get("text", "")
    return [_p(text, st_name)]


def _render_kv(block: dict, width: float) -> list:
    pairs = block.get("pairs") or []
    cols = block.get("cols", 2)
    if cols not in (2, 3):
        cols = 2
    cells = []
    row = []
    for pair in pairs:
        label = str(pair[0]) if len(pair) > 0 else ""
        val = str(pair[1]) if len(pair) > 1 else ""
        row.extend([_p(label, "label"), _p(val, "value")])
        if len(row) == 2 * cols:
            cells.append(row)
            row = []
    if row:
        row.extend([""] * (2 * cols - len(row)))
        cells.append(row)
    out = []
    if block.get("title"):
        out.append(_p(block["title"], "h2"))
    if not cells:
        return out
    lw = width * 0.18 * (2 / cols)
    vw = width * 0.32 * (2 / cols)
    col_widths = [lw, vw] * cols
    t = RLTable(cells, colWidths=col_widths)
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor(0xdddddd)),
                ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return out + [t, RLSpacer(1, 1.5 * mm)]


def _render_table(block: dict, width: float) -> list:
    headers = [str(h) for h in block.get("headers") or []]
    rows = block.get("rows") or []
    title = block.get("title")
    out = []
    if title:
        out.append(_p(title, "h2"))
    if not rows:
        empty_text = block.get("empty_text", "")
        out.append(_p(empty_text, "unavailable"))
        out.append(RLSpacer(1, 1.5 * mm))
        return out

    col_weights = block.get("col_weights")
    if col_weights and len(col_weights) == len(headers) and sum(col_weights) > 0:
        total_w = sum(col_weights)
        col_w = [width * (w / total_w) for w in col_weights]
    else:
        col_w = _col_widths(headers, rows, width)

    data = [[_p(h, "cellh") for h in headers]]
    for r in rows:
        row_cells = []
        for i in range(len(headers)):
            val = str(r[i]) if i < len(r) else ""
            row_cells.append(_p(val, "cell"))
        data.append(row_cells)

    t = RLTable(data, colWidths=col_w, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(0xdfe8f1)),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor(0xb0b8c0)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    out.append(t)
    out.append(RLSpacer(1, 1.5 * mm))
    return out


def _render_callout(block: dict, width: float) -> list:
    tone = block.get("tone", "info")
    bg = TONE_COLORS.get(tone, TONE_COLORS["info"])
    text = block.get("text", "")
    t = RLTable([[_p(text, "body")]], colWidths=[width])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), bg),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(0x999999)),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return [RLSpacer(1, 2 * mm), t, RLSpacer(1, 2 * mm)]


def _render_bullets(block: dict) -> list:
    items = block.get("items") or []
    bullet_style = styles()["bullet"]
    bullet_prefix = "\u2022 "
    out = []
    for it in items:
        out.append(Paragraph(bullet_prefix + escape(str(it or "")), bullet_style))
    return out


def _render_drawing(block: dict) -> list:
    dr = block.get("drawing")
    cap = block.get("caption")
    items = []
    if dr is not None:
        items.append(dr)
    if cap:
        items.append(_p(cap, "note"))
    if not items:
        return []
    return [KeepTogether(items), RLSpacer(1, 1.5 * mm)]


def _flatten_keep(flowables: list) -> list:
    """KeepTogether reports an unbounded height inside a Table cell; use its content instead."""
    out = []
    for f in flowables:
        if isinstance(f, KeepTogether):
            out.extend(_flatten_keep(list(getattr(f, "_content", []))))
        else:
            out.append(f)
    return out


def _render_columns(block: dict, width: float) -> list:
    widths = block.get("widths") or [0.5, 0.5]
    w_left = width * float(widths[0])
    w_right = width * float(widths[1])
    left_flowables = _flatten_keep(_render_blocks(block.get("left") or [], w_left))
    right_flowables = _flatten_keep(_render_blocks(block.get("right") or [], w_right))
    if not left_flowables:
        left_flowables = [RLSpacer(1, 1)]
    if not right_flowables:
        right_flowables = [RLSpacer(1, 1)]
    t = RLTable([[left_flowables, right_flowables]], colWidths=[w_left, w_right])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return [t, RLSpacer(1, 1.5 * mm)]


def _render_block(block: dict, width: float) -> list:
    kind = block.get("kind")
    if kind == "p":
        return _render_p(block)
    if kind == "kv":
        return _render_kv(block, width)
    if kind == "table":
        return _render_table(block, width)
    if kind == "callout":
        return _render_callout(block, width)
    if kind == "bullets":
        return _render_bullets(block)
    if kind == "drawing":
        return _render_drawing(block)
    if kind == "columns":
        return _render_columns(block, width)
    raise ValueError("Unknown block kind: " + str(kind))


def _render_blocks(blocks: list[dict], width: float) -> list:
    flowables = []
    for b in blocks:
        flowables.extend(_render_block(b, width))
    return flowables


def _numbered_canvas(footer_id: str, banner: str):
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
                self.setFillColor(colors.HexColor(0x777777))
                if footer_id:
                    self.drawString(MARGIN, 9 * mm, footer_id)
                self.drawRightString(PAGE_W - MARGIN, 9 * mm, f"Page {self._pageNumber} of {total}")
                if banner:
                    self.drawString(MARGIN, PAGE_H - 9 * mm, banner)
                super().showPage()
            super().save()

    return NumberedCanvas


def render_dossier_pdf(doc: dict, out_path: Path) -> int:
    """Render the dossier; return the page count. Creates parent dirs."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    usable_width = PAGE_W - 2 * MARGIN
    story = []

    title = doc.get("title")
    if title:
        story.append(_p(title, "title"))
    subtitle = doc.get("subtitle")
    if subtitle:
        story.append(_p(subtitle, "subtitle"))
    if title or subtitle:
        story.append(RLSpacer(1, 2 * mm))

    for sec in doc.get("sections") or []:
        sec_title = sec.get("title")
        if sec_title:
            rule = Drawing(usable_width, 1)
            rule.add(Line(0, 0.5, usable_width, 0.5, strokeColor=colors.HexColor(0x123b5c), strokeWidth=0.5))
            heading_flowables = [
                RLSpacer(1, 3 * mm),
                _p(sec_title, "h1"),
                rule,
                RLSpacer(1, 1.5 * mm),
            ]
            story.append(KeepTogether(heading_flowables))
        blocks = sec.get("blocks") or []
        story.extend(_render_blocks(blocks, usable_width))

    meta = doc.get("meta") or {}
    footer_id = doc.get("footer_id", "")
    banner = doc.get("banner", "")

    doc_template = SimpleDocTemplate(
        str(out),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=meta.get("title", doc.get("title", "")),
        author=meta.get("author", ""),
        subject=meta.get("subject", ""),
    )
    doc_template.build(story, canvasmaker=_numbered_canvas(footer_id, banner))
    return int(doc_template.page)


def wellbore_schematic(geom: dict, width: float, height: float) -> Drawing:
    """Vector wellbore schematic + lithology column (points)."""
    d = Drawing(width, height)

    fms = geom.get("formations") or []
    casings = geom.get("casing") or []
    tub = geom.get("tubing") or []
    perfs = geom.get("perfs") or []

    is_empty = not (fms or casings or tub or perfs)
    if is_empty:
        d.add(Rect(0, 0, width, height, strokeColor=colors.HexColor(0xdddddd), strokeWidth=0.5, fillColor=None))
        if geom.get("caption_label"):
            d.add(String(width * 0.5, 4, str(geom["caption_label"]), fontName="Helvetica", fontSize=6, textAnchor="middle"))
        return d

    td_val = geom.get("td_m")
    if td_val is not None and float(td_val) > 0:
        td = float(td_val)
    else:
        candidates = []
        for f in fms:
            if f.get("bottom"):
                candidates.append(float(f["bottom"]))
        for c in casings:
            if c.get("shoe"):
                candidates.append(float(c["shoe"]))
        for p in perfs:
            if p.get("bottom"):
                candidates.append(float(p["bottom"]))
        for t in tub:
            if t.get("bottom"):
                candidates.append(float(t["bottom"]))
        td = max(candidates) if candidates else 1000.0

    top_y = height - 8.0
    bot_y = 16.0 if geom.get("caption_label") else 10.0
    scale = (top_y - bot_y) / td if td > 0 else 1.0

    def y_coord(depth_m: float) -> float:
        return top_y - float(depth_m) * scale

    fx = 4.0
    fw = width * 0.22
    for i, f in enumerate(fms):
        t_m = float(f.get("top", 0.0))
        b_m = float(f.get("bottom", 0.0))
        lbl = str(f.get("label") or "")
        lbl_lower = lbl.lower()
        if "lime" in lbl_lower:
            fill_col = colors.HexColor(0xd0dce5)
        elif "coal" in lbl_lower:
            fill_col = colors.HexColor(0x666666)
        else:
            fill_col = colors.HexColor(LITHO_SHADES[i % len(LITHO_SHADES)])
        rect_y = y_coord(b_m)
        rect_h = max(y_coord(t_m) - rect_y, 0.5)
        d.add(Rect(fx, rect_y, fw, rect_h, fillColor=fill_col, strokeColor=colors.grey, strokeWidth=0.3))
        if lbl:
            text_color = colors.white if "coal" in lbl_lower else colors.black
            d.add(String(fx + 2, y_coord(t_m) - 7, lbl, fontName="Helvetica-Bold", fontSize=6, fillColor=text_color))

    cx = fx + fw + (width - (fx + fw)) * 0.25
    ods = [float(c.get("od") or 0.0) for c in casings if c.get("od")]
    max_od = max(ods) if ods else 1.0
    min_od = min(ods) if ods else 1.0

    def half(od_val: float) -> float:
        return 6.0 + 26.0 * (float(od_val) / max_od if max_od > 0 else 1.0)

    for c in sorted(casings, key=lambda item: -(float(item.get("od") or 0.0))):
        shoe_m = float(c.get("shoe", 0.0))
        top_m = float(c.get("top", 0.0))
        od_val = float(c.get("od", 1.0))
        toc = c.get("cement_top")
        hw = half(od_val)
        if toc is not None and float(toc) < shoe_m:
            toc_m = float(toc)
            cement_h = max(y_coord(toc_m) - y_coord(shoe_m), 0.5)
            for sgn in (-1, 1):
                x0 = cx + sgn * hw
                d.add(Rect(min(x0, x0 + sgn * 4), y_coord(shoe_m), 4, cement_h, fillColor=colors.HexColor(0xb9b9b9), strokeColor=None))
        for sgn in (-1, 1):
            d.add(Line(cx + sgn * hw, y_coord(top_m), cx + sgn * hw, y_coord(shoe_m), strokeColor=colors.black, strokeWidth=1))
        d.add(Polygon([cx - hw, y_coord(shoe_m), cx - hw - 4, y_coord(shoe_m), cx - hw, y_coord(shoe_m) + 5], fillColor=colors.black, strokeColor=None))
        d.add(Polygon([cx + hw, y_coord(shoe_m), cx + hw + 4, y_coord(shoe_m), cx + hw, y_coord(shoe_m) + 5], fillColor=colors.black, strokeColor=None))

    innermost_hw = half(min_od) if casings else 8.0
    for p in perfs:
        t_m = float(p.get("top", 0.0))
        b_m = float(p.get("bottom", 0.0))
        is_open = bool(p.get("open", True))
        steps = max(int((y_coord(t_m) - y_coord(b_m)) / 2.5), 1)
        tick_col = colors.red if is_open else colors.HexColor(0x888888)
        for k in range(steps + 1):
            yy = y_coord(t_m) - k * (y_coord(t_m) - y_coord(b_m)) / steps
            for sgn in (-1, 1):
                l_tick = Line(cx + sgn * innermost_hw, yy, cx + sgn * (innermost_hw + 7), yy, strokeColor=tick_col, strokeWidth=0.8)
                if not is_open:
                    l_tick.strokeDashArray = [2, 2]
                d.add(l_tick)

    for t in tub:
        top_m = float(t.get("top", 0.0))
        bot_m = float(t.get("bottom", 0.0))
        comp = str(t.get("component") or "").upper()
        if comp == "TUBING":
            for sgn in (-1, 1):
                d.add(Line(cx + sgn * 2.5, y_coord(top_m), cx + sgn * 2.5, y_coord(bot_m), strokeColor=colors.HexColor(0x1f5fa8), strokeWidth=1))
        else:
            rect_h = max(abs(y_coord(top_m) - y_coord(bot_m)), 3.0)
            rect_bot = min(y_coord(top_m), y_coord(bot_m))
            d.add(Rect(cx - 4.5, rect_bot, 9, rect_h, fillColor=colors.HexColor(0x1f5fa8), strokeColor=None))

    lx = cx + half(max_od) + 12.0
    raw_labels = []
    for c in casings:
        lbl = c.get("label")
        if lbl and c.get("shoe") is not None:
            raw_labels.append((y_coord(float(c["shoe"])), str(lbl)))
    for p in perfs:
        lbl = p.get("label")
        if lbl and p.get("top") is not None:
            raw_labels.append((y_coord(float(p["top"])), str(lbl)))
    for t in tub:
        comp = str(t.get("component") or "").upper()
        lbl = t.get("label")
        if comp != "TUBING" and lbl is not None and t.get("top") is not None:
            raw_labels.append((y_coord(float(t["top"])), str(lbl)))

    # deepest first, pushing later labels upwards so the bottom of the well stays readable
    raw_labels.sort(key=lambda item: item[0])
    ly_used: list[float] = []
    for at_y, text in raw_labels:
        yy = max(at_y, bot_y)
        while any(abs(yy - u) < 7 for u in ly_used):
            yy += 7
        ly_used.append(yy)
        d.add(String(lx, yy, text, fontName="Helvetica", fontSize=5.8))

    if geom.get("caption_label"):
        d.add(String(width * 0.5, 4, str(geom["caption_label"]), fontName="Helvetica", fontSize=6, textAnchor="middle"))

    return d


def sparkline(
    values: list[float | None],
    width: float,
    height: float,
    marker_idx: list[int] | None = None,
) -> Drawing:
    """Tiny line chart of values (None = gap), vertical red ticks at marker indices. No text at all."""
    d = Drawing(width, height)
    d.add(Rect(0, 0, width, height, strokeColor=colors.HexColor(0xdddddd), strokeWidth=0.5, fillColor=None))

    if not values:
        return d
    valid_vals = [v for v in values if v is not None]
    if not valid_vals:
        return d

    pad_x = 2.0
    pad_y = 2.0
    plot_w = max(width - 2.0 * pad_x, 1.0)
    plot_h = max(height - 2.0 * pad_y, 1.0)
    n = len(values)

    def get_x(idx: int) -> float:
        if n <= 1:
            return pad_x + plot_w * 0.5
        return pad_x + (float(idx) / float(n - 1)) * plot_w

    vmin = min(valid_vals)
    vmax = max(valid_vals)
    vrange = vmax - vmin

    def get_y(val: float) -> float:
        if vrange <= 1e-9:
            return pad_y + plot_h * 0.5
        return pad_y + ((float(val) - vmin) / vrange) * plot_h

    segments: list[list[float]] = []
    current: list[float] = []
    for i, val in enumerate(values):
        if val is not None:
            current.extend([get_x(i), get_y(val)])
        else:
            if len(current) >= 4:
                segments.append(current)
            elif len(current) == 2:
                segments.append([current[0] - 0.5, current[1], current[0] + 0.5, current[1]])
            current = []
    if len(current) >= 4:
        segments.append(current)
    elif len(current) == 2:
        segments.append([current[0] - 0.5, current[1], current[0] + 0.5, current[1]])

    for seg in segments:
        d.add(PolyLine(seg, strokeColor=colors.HexColor(0x1f5fa8), strokeWidth=0.8))

    if marker_idx:
        for idx in marker_idx:
            if 0 <= idx < n:
                mx = get_x(idx)
                d.add(Line(mx, 1.0, mx, height - 1.0, strokeColor=colors.red, strokeWidth=0.8))

    return d
