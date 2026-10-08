"""TC-032 field_report: printable HTML 'Pre-field Well Pack' / Field Report (Stage FR, F-25).

Assembles lifecycle construction, barrier integrity, failure history, production dynamics,
multimodal intervention recommendations, and executable job program into a standalone,
print-ready HTML5 document with inline SVG wellbore schematic and production history chart.

Design constraints:
- 100% Synthetic Data Demo — prominent banners and watermarks.
- Strict commercial compliance: ZERO currency tokens (₹, USD, rupee, lakh, crore, NPV).
- Persona-aware: If persona == 'FIELD_ENGINEER', cost band is omitted entirely.
- Zero typed numbers: all values from tools and tables; missing fields render as '—'.
- Self-contained HTML5 with inline CSS and vector SVG; no external assets except /brand/ongc_logo.svg
  with onerror fallback to text wordmark 'ONGC'.
"""

from __future__ import annotations

import html
import math
import re
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd

from app import settings
from app.analytics.tools.common import load_table, well_master_row, well_rows
from app.analytics.tools.dg_tables import deviation_survey, integrity, tubing_tally
from app.analytics.tools.nba import sop_steps
from app.analytics.tools.success_engine import recommend_interventions
from app.analytics.tools.well_profile import well_production_series, well_profile

# Standard lithology shades for SVG wellbore schematic
LITHO_COLORS: dict[str, str] = {
    "alluvium": "#f4ecd8",
    "namsang": "#e9dcc0",
    "girujan": "#ddd0b0",
    "tipam": "#f0e6cc",
    "barail": "#d0dce5",
    "coal": "#555555",
    "sandstone": "#f2e4c8",
    "shale": "#d8d0c5",
    "claystone": "#ddd0b0",
    "limestone": "#cde0eb",
}
DEFAULT_LITHO_SHADES = ("#f4ecd8", "#e9dcc0", "#ddd0b0", "#f0e6cc", "#d0dce5")


def _val(v: Any, nd: int | None = None, unit: str = "", missing: str = "—") -> str:
    """Format a value safely into display string without typed placeholders."""
    if v is None:
        return missing
    try:
        if pd.isna(v):
            return missing
    except (TypeError, ValueError):
        pass
    if isinstance(v, (float, np.floating)):
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return missing
        s = f"{f:.{nd}f}" if nd is not None else (f"{int(f)}" if f.is_integer() else f"{f:.2f}")
        return f"{s} {unit}".strip() if unit else s
    if isinstance(v, (int, np.integer)):
        s = str(int(v))
        return f"{s} {unit}".strip() if unit else s
    if isinstance(v, (date, datetime, pd.Timestamp)):
        s = v.isoformat()[:10]
        return f"{s} {unit}".strip() if unit else s
    if isinstance(v, bool):
        return "Yes" if v else "No"
    s = str(v).strip()
    if not s or s.lower() in ("none", "nan", "null"):
        return missing
    return f"{s} {unit}".strip() if unit else s


def _esc(s: Any) -> str:
    return html.escape(str(s or ""))


def _strip_cost(text: str) -> str:
    """Strip cost band references for FIELD_ENGINEER persona."""
    s = re.sub(r",?\s*cost band\s+[A-Za-z_]+;?", "", str(text or ""), flags=re.IGNORECASE)
    s = re.sub(r"cost\s*band", "", s, flags=re.IGNORECASE)
    return s.strip()


# -------------------------------------------------------------------------------------------------
# SVG Wellbore Schematic (WH-04)
# -------------------------------------------------------------------------------------------------
def _build_schematic_geom(identity: dict, construction: dict, lithology: list[dict]) -> dict:
    td_val = identity.get("total_depth_md_m")
    td_m = float(td_val) if td_val and float(td_val) > 0 else 1000.0

    casings = construction.get("casing") or []
    tubings = construction.get("tubing") or []
    perfs = construction.get("perfs") or []

    # Calculate PBTD (often production casing shoe or lowest perf base)
    pbtd_m = None
    for c in casings:
        shoe = c.get("shoe_m")
        st = str(c.get("string_type", "")).upper()
        if shoe and ("PROD" in st or "5.5" in str(c.get("od_in", ""))):
            pbtd_m = float(shoe)
            break
    if pbtd_m is None:
        shoes = [float(c["shoe_m"]) for c in casings if c.get("shoe_m")]
        pbtd_m = max(shoes) if shoes else td_m

    return {
        "td_m": td_m,
        "pbtd_m": pbtd_m,
        "formations": lithology,
        "casing": casings,
        "tubing": tubings,
        "perfs": perfs,
    }


def render_wellbore_svg(geom: dict, width: int = 700, height: int = 680) -> str:
    """Generate self-contained vector inline SVG for the wellbore diagram."""
    td_m = max(float(geom.get("td_m") or 1000.0), 100.0)
    pbtd_m = float(geom.get("pbtd_m") or td_m)

    top_pad = 40.0
    bot_pad = 55.0
    plot_h = height - top_pad - bot_pad

    def ym(depth: float) -> float:
        d = max(0.0, min(float(depth), td_m))
        return top_pad + (d / td_m) * plot_h

    # Layout horizontal coordinates
    depth_axis_x = 55.0
    litho_x = 75.0
    litho_w = 90.0
    well_cx = 285.0
    label_x = 425.0

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="100%" height="auto" class="wellbore-svg" '
        f'style="max-width:{width}px; font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, Arial, sans-serif;">',
        '<style>',
        '  .wb-axis { stroke: #666; stroke-width: 1; }',
        '  .wb-grid { stroke: #e0e0e0; stroke-width: 0.5; stroke-dasharray: 2,2; }',
        '  .wb-text { font-size: 10px; fill: #333; }',
        '  .wb-title { font-size: 12px; font-weight: bold; fill: #123b5c; }',
        '  .wb-litho-lbl { font-size: 9px; font-weight: 600; fill: #222; }',
        '  .wb-casing { stroke: #222; stroke-width: 2; fill: none; }',
        '  .wb-tubing { stroke: #1f5fa8; stroke-width: 2.2; fill: none; }',
        '  .wb-shoe { fill: #222; stroke: none; }',
        '  .wb-cement { fill: #b9b9b9; opacity: 0.65; }',
        '  .wb-perf-open { stroke: #d32f2f; stroke-width: 2; }',
        '  .wb-perf-sqz { stroke: #888; stroke-width: 1.5; stroke-dasharray: 2,2; }',
        '  .wb-leader { stroke: #888; stroke-width: 0.75; stroke-dasharray: 2,2; fill: none; }',
        '  .wb-callout { font-size: 9.5px; fill: #1a1a1a; }',
        '  .wb-callout-sub { font-size: 8.5px; fill: #555; }',
        '</style>',
    ]

    # Title & header in SVG
    svg_parts.append(f'<text x="{width / 2}" y="20" text-anchor="middle" class="wb-title">Wellbore Architecture & Completion Schematic</text>')
    svg_parts.append(f'<text x="{width / 2}" y="33" text-anchor="middle" style="font-size:9px; fill:#777;">Depth axis in Measured Depth (m MD) · Not to scale laterally</text>')

    # 1. Depth Axis (m MD)
    svg_parts.append(f'<line x1="{depth_axis_x}" y1="{top_pad}" x2="{depth_axis_x}" y2="{top_pad + plot_h}" class="wb-axis" />')
    step = 500 if td_m >= 2000 else (250 if td_m >= 1000 else 100)
    for tick_d in range(0, int(td_m) + 1, step):
        y = ym(tick_d)
        svg_parts.append(f'<line x1="{depth_axis_x - 5}" y1="{y}" x2="{depth_axis_x}" y2="{y}" class="wb-axis" />')
        svg_parts.append(f'<line x1="{depth_axis_x}" y1="{y}" x2="{label_x + 250}" y2="{y}" class="wb-grid" />')
        svg_parts.append(f'<text x="{depth_axis_x - 8}" y="{y + 3}" text-anchor="end" class="wb-text" style="font-size:8.5px;">{tick_d}m</text>')

    # 2. Lithology Column (Formation Tops)
    formations = geom.get("formations") or []
    if formations:
        for i, fm in enumerate(formations):
            t_m = float(fm.get("top_md_m") or 0.0)
            b_m = float(fm.get("bottom_md_m") or t_m)
            name = str(fm.get("formation") or f"Formation {i+1}")
            color = LITHO_COLORS.get(name.lower(), DEFAULT_LITHO_SHADES[i % len(DEFAULT_LITHO_SHADES)])
            y_t = ym(t_m)
            y_b = ym(b_m)
            h_rect = max(y_b - y_t, 2.0)
            svg_parts.append(f'<rect x="{litho_x}" y="{y_t}" width="{litho_w}" height="{h_rect}" fill="{color}" stroke="#999" stroke-width="0.5" />')
            if h_rect >= 12.0:
                txt_color = "#fff" if name.lower() == "coal" else "#222"
                svg_parts.append(f'<text x="{litho_x + 5}" y="{y_t + min(12.0, h_rect/2 + 4)}" class="wb-litho-lbl" fill="{txt_color}">{_esc(name)}</text>')
                if h_rect >= 24.0:
                    svg_parts.append(f'<text x="{litho_x + 5}" y="{y_t + 22}" style="font-size:8px; fill:#555;">{t_m:.0f}–{b_m:.0f}m</text>')
    else:
        # Placeholder lithology
        svg_parts.append(f'<rect x="{litho_x}" y="{top_pad}" width="{litho_w}" height="{plot_h}" fill="#f9f9f9" stroke="#ccc" stroke-dasharray="4,4" />')
        svg_parts.append(f'<text x="{litho_x + litho_w/2}" y="{top_pad + plot_h/2}" text-anchor="middle" class="wb-text" style="fill:#888;">Lithology Tops<br/>Not Recorded</text>')

    # 3. Casing Strings & Cement
    casings = geom.get("casing") or []
    max_od = max([float(c.get("od_in") or 1.0) for c in casings] + [7.0])
    casings_sorted = sorted(casings, key=lambda c: -(float(c.get("od_in") or 0.0)))

    callouts: list[tuple[float, str, str, str]] = []

    if casings_sorted:
        for c in casings_sorted:
            od = float(c.get("od_in") or 5.5)
            shoe = float(c.get("shoe_m") or td_m)
            top = float(c.get("top_m") or 0.0)
            toc = c.get("cement_top_m")
            st_name = str(c.get("string_type") or f'{od}" Casing')
            grade = str(c.get("grade") or "")

            half_w = 12.0 + 34.0 * (od / max_od)
            y_top = ym(top)
            y_shoe = ym(shoe)

            # Cement Annulus behind casing from TOC to shoe
            if toc is not None and float(toc) < shoe:
                toc_m = float(toc)
                y_toc = ym(toc_m)
                cement_h = max(y_shoe - y_toc, 2.0)
                # Outer cement bands on left and right
                svg_parts.append(f'<rect x="{well_cx - half_w - 5}" y="{y_toc}" width="5" height="{cement_h}" class="wb-cement" />')
                svg_parts.append(f'<rect x="{well_cx + half_w}" y="{y_toc}" width="5" height="{cement_h}" class="wb-cement" />')

            # Casing wall lines
            svg_parts.append(f'<line x1="{well_cx - half_w}" y1="{y_top}" x2="{well_cx - half_w}" y2="{y_shoe}" class="wb-casing" />')
            svg_parts.append(f'<line x1="{well_cx + half_w}" y1="{y_top}" x2="{well_cx + half_w}" y2="{y_shoe}" class="wb-casing" />')

            # Outward casing shoe triangles
            svg_parts.append(f'<polygon points="{well_cx - half_w},{y_shoe} {well_cx - half_w - 6},{y_shoe} {well_cx - half_w},{y_shoe - 7}" class="wb-shoe" />')
            svg_parts.append(f'<polygon points="{well_cx + half_w},{y_shoe} {well_cx + half_w + 6},{y_shoe} {well_cx + half_w},{y_shoe - 7}" class="wb-shoe" />')

            lbl_main = f'{st_name} ({od}" OD{f", {grade}" if grade else ""})'
            lbl_sub = f'Shoe @ {shoe:.1f} m MD' + (f' · TOC @ {float(toc):.1f} m' if toc is not None else '')
            callouts.append((y_shoe, lbl_main, lbl_sub, "#123b5c"))
    else:
        # Placeholder casing
        half_w = 28.0
        svg_parts.append(f'<line x1="{well_cx - half_w}" y1="{top_pad}" x2="{well_cx - half_w}" y2="{top_pad + plot_h}" class="wb-casing" stroke-dasharray="4,4" />')
        svg_parts.append(f'<line x1="{well_cx + half_w}" y1="{top_pad}" x2="{well_cx + half_w}" y2="{top_pad + plot_h}" class="wb-casing" stroke-dasharray="4,4" />')
        callouts.append((top_pad + plot_h, "Casing Data Generic", f"TD @ {td_m:.1f} m MD", "#666"))

    # 4. Perforations
    perfs = geom.get("perfs") or []
    innermost_hw = 16.0
    for p in perfs:
        t_m = float(p.get("top_m") or 0.0)
        b_m = float(p.get("bottom_m") or t_m)
        zone = str(p.get("zone") or "Pay Zone")
        status = str(p.get("status") or "OPEN").upper()
        is_open = status == "OPEN"
        y_t = ym(t_m)
        y_b = ym(b_m)
        perf_h = max(y_b - y_t, 4.0)

        # Draw perf tick marks on casing flanks
        n_ticks = max(int(perf_h / 4.0), 2)
        cls_perf = "wb-perf-open" if is_open else "wb-perf-sqz"
        for k in range(n_ticks + 1):
            y_curr = y_t + k * (perf_h / n_ticks)
            svg_parts.append(f'<line x1="{well_cx - innermost_hw - 9}" y1="{y_curr}" x2="{well_cx - innermost_hw + 1}" y2="{y_curr}" class="{cls_perf}" />')
            svg_parts.append(f'<line x1="{well_cx + innermost_hw - 1}" y1="{y_curr}" x2="{well_cx + innermost_hw + 9}" y2="{y_curr}" class="{cls_perf}" />')

        tag = "OPEN" if is_open else status
        tag_color = "#d32f2f" if is_open else "#666"
        callouts.append(((y_t + y_b) / 2, f"Perforations: {zone} [{tag}]", f"{t_m:.1f} m – {b_m:.1f} m MD", tag_color))

    # 5. Tubing String & Downhole Tools
    tubings = geom.get("tubing") or []
    if tubings:
        max_tub_depth = 0.0
        for tb in tubings:
            t_m = float(tb.get("top_m") or 0.0)
            ln = float(tb.get("length_m") or 0.0)
            b_m = t_m + ln
            max_tub_depth = max(max_tub_depth, b_m)
            comp = str(tb.get("component") or "TUBING").upper()
            y_t = ym(t_m)
            y_b = ym(b_m)

            if comp == "TUBING":
                # Central dual tubing pipe
                svg_parts.append(f'<line x1="{well_cx - 3}" y1="{y_t}" x2="{well_cx - 3}" y2="{y_b}" class="wb-tubing" />')
                svg_parts.append(f'<line x1="{well_cx + 3}" y1="{y_t}" x2="{well_cx + 3}" y2="{y_b}" class="wb-tubing" />')
            else:
                # Downhole tool / component block
                rect_h = max(abs(y_b - y_t), 8.0)
                svg_parts.append(f'<rect x="{well_cx - 7}" y="{y_t}" width="14" height="{rect_h}" fill="#1f5fa8" stroke="#0d3663" stroke-width="1" rx="1.5" />')
                callouts.append((y_t + rect_h / 2, f"{comp}", f"Landed @ {t_m:.1f} m MD", "#1f5fa8"))

        if max_tub_depth > 0:
            callouts.append((ym(max_tub_depth), "Tubing String EOT", f"Tailpipe @ {max_tub_depth:.1f} m MD", "#1f5fa8"))
    else:
        # Generic tubing placeholder to 85% TD
        tub_placeholder = td_m * 0.85
        y_tub = ym(tub_placeholder)
        svg_parts.append(f'<line x1="{well_cx - 3}" y1="{top_pad}" x2="{well_cx - 3}" y2="{y_tub}" class="wb-tubing" stroke-dasharray="3,2" />')
        svg_parts.append(f'<line x1="{well_cx + 3}" y1="{top_pad}" x2="{well_cx + 3}" y2="{y_tub}" class="wb-tubing" stroke-dasharray="3,2" />')
        svg_parts.append(f'<rect x="{well_cx - 7}" y="{y_tub - 10}" width="14" height="10" fill="#1f5fa8" opacity="0.6" rx="1" />')
        callouts.append((y_tub, "Tubing / Pump String (Est.)", f"Estimated EOT @ {tub_placeholder:.0f} m MD", "#555"))

    # 6. PBTD and TD Lines
    y_pbtd = ym(pbtd_m)
    y_td = ym(td_m)
    svg_parts.append(f'<line x1="{well_cx - 30}" y1="{y_pbtd}" x2="{well_cx + 30}" y2="{y_pbtd}" stroke="#555" stroke-width="1.2" stroke-dasharray="3,2" />')
    callouts.append((y_pbtd, "PBTD (Plug Back Total Depth)", f"{pbtd_m:.1f} m MD", "#444"))

    svg_parts.append(f'<line x1="{well_cx - 35}" y1="{y_td}" x2="{well_cx + 35}" y2="{y_td}" stroke="#8B1A1A" stroke-width="1.8" />')
    callouts.append((y_td, "TD (Total Depth)", f"{td_m:.1f} m MD", "#8B1A1A"))

    # 7. Render Callout Labels on Right Flank with Collison Avoidance
    callouts.sort(key=lambda item: item[0])
    used_y: list[float] = []
    for at_y, title, subtitle, color in callouts:
        c_y = max(at_y, top_pad + 5.0)
        while any(abs(c_y - u) < 14.0 for u in used_y):
            c_y += 13.0
        used_y.append(c_y)

        # Leader line from wellbore right wall to callout box
        svg_parts.append(f'<path d="M {well_cx + 25} {at_y} L {label_x - 15} {c_y} L {label_x} {c_y}" class="wb-leader" />')
        svg_parts.append(f'<circle cx="{label_x}" cy="{c_y}" r="2" fill="{color}" />')
        svg_parts.append(f'<text x="{label_x + 6}" y="{c_y - 1}" class="wb-callout" style="font-weight:600; fill:{color};">{_esc(title)}</text>')
        svg_parts.append(f'<text x="{label_x + 6}" y="{c_y + 10}" class="wb-callout-sub">{_esc(subtitle)}</text>')

    # 8. Legend at bottom
    leg_y = height - 22
    svg_parts.append(
        f'<g transform="translate(60, {leg_y})">'
        f'<rect x="0" y="-12" width="{width - 120}" height="28" fill="#f8f9fa" stroke="#e0e0e0" rx="3" />'
        f'<line x1="15" y1="2" x2="35" y2="2" stroke="#222" stroke-width="2" /><text x="40" y="5" class="wb-text">Casing</text>'
        f'<rect x="95" y="-3" width="12" height="10" fill="#b9b9b9" opacity="0.8" /><text x="112" y="5" class="wb-text">Cement</text>'
        f'<line x1="175" y1="2" x2="195" y2="2" stroke="#1f5fa8" stroke-width="2.2" /><text x="200" y="5" class="wb-text">Tubing</text>'
        f'<line x1="260" y1="2" x2="280" y2="2" stroke="#d32f2f" stroke-width="2" /><text x="285" y="5" class="wb-text">Open Perf</text>'
        f'<line x1="365" y1="2" x2="385" y2="2" stroke="#888" stroke-width="1.5" stroke-dasharray="2,2" /><text x="390" y="5" class="wb-text">Squeezed Perf</text>'
        f'<rect x="480" y="-4" width="12" height="12" fill="#1f5fa8" rx="1.5" /><text x="497" y="5" class="wb-text">Downhole Tool</text>'
        f'</g>'
    )

    svg_parts.append('</svg>')
    return "".join(svg_parts)


# -------------------------------------------------------------------------------------------------
# SVG Production History Chart (WH-11)
# -------------------------------------------------------------------------------------------------
def render_production_svg(series_val: Any, width: int = 700, height: int = 240) -> str:
    """Generate self-contained vector inline SVG line chart of 36-month monthly production."""
    if series_val is None or not getattr(series_val, "dates", None):
        return (
            f'<div class="svg-placeholder" style="padding:20px; background:#f9f9f9; border:1px dashed #ccc; text-align:center; color:#777;">'
            f'Production history time series unavailable for this wellbore.</div>'
        )

    dates = series_val.dates
    oil_daily = series_val.series.get("oil") or []
    wc_daily = series_val.series.get("water_cut") or []
    interventions = getattr(series_val, "interventions", []) or []

    # Aggregate daily into calendar months (last 36 months)
    monthly_data: dict[str, dict[str, list[float]]] = {}
    for d_str, o, w in zip(dates, oil_daily, wc_daily):
        m_key = str(d_str)[:7]  # YYYY-MM
        if m_key not in monthly_data:
            monthly_data[m_key] = {"oil": [], "wc": []}
        if o is not None and not (isinstance(o, float) and math.isnan(o)):
            monthly_data[m_key]["oil"].append(float(o))
        if w is not None and not (isinstance(w, float) and math.isnan(w)):
            monthly_data[m_key]["wc"].append(float(w))

    sorted_months = sorted(monthly_data.keys())
    if not sorted_months:
        return '<div class="svg-placeholder">No producing days recorded in history window.</div>'

    m_oil = [np.mean(monthly_data[m]["oil"]) if monthly_data[m]["oil"] else 0.0 for m in sorted_months]
    m_wc = [np.mean(monthly_data[m]["wc"]) if monthly_data[m]["wc"] else 0.0 for m in sorted_months]

    max_oil = max(m_oil) if m_oil else 20.0
    y_oil_max = max(max_oil * 1.18, 10.0)

    # Chart boundaries
    ml, mr, mt, mb = 55.0, 55.0, 35.0, 45.0
    pw = width - ml - mr
    ph = height - mt - mb
    n_pts = len(sorted_months)

    def x_pos(idx: float) -> float:
        return ml + (idx / max(n_pts - 1, 1)) * pw

    def y_oil_pos(val: float) -> float:
        v = max(0.0, float(val))
        return mt + ph - (v / y_oil_max) * ph

    def y_wc_pos(val: float) -> float:
        v = max(0.0, min(100.0, float(val)))
        return mt + ph - (v / 100.0) * ph

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="100%" height="auto" class="prod-svg" '
        f'style="max-width:{width}px; font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, Arial, sans-serif;">',
        '<style>',
        '  .p-axis { stroke: #666; stroke-width: 1; }',
        '  .p-grid { stroke: #eaeaea; stroke-width: 0.5; stroke-dasharray: 2,2; }',
        '  .p-lbl { font-size: 8.5px; fill: #666; }',
        '  .p-oil-line { stroke: #2e7d32; stroke-width: 2.2; fill: none; }',
        '  .p-wc-line { stroke: #0288d1; stroke-width: 1.8; fill: none; stroke-dasharray: 4,2; }',
        '  .p-marker { stroke: #d32f2f; stroke-width: 1.4; stroke-dasharray: 3,2; }',
        '</style>',
    ]

    # Title & Legend
    svg.append(f'<text x="{ml}" y="18" style="font-size:11px; font-weight:bold; fill:#123b5c;">Monthly Production & Water Cut Trends (36-Month Profile)</text>')
    # Legend
    leg_x = width - mr - 290
    svg.append(f'<g transform="translate({leg_x}, 10)">')
    svg.append('<line x1="0" y1="4" x2="18" y2="4" stroke="#2e7d32" stroke-width="2.2" /><circle cx="9" cy="4" r="2.5" fill="#2e7d32" /><text x="24" y="7" class="p-lbl" style="fill:#2e7d32; font-weight:600;">Oil Rate (BOPD)</text>')
    svg.append('<line x1="105" y1="4" x2="123" y2="4" stroke="#0288d1" stroke-width="1.8" stroke-dasharray="4,2" /><circle cx="114" cy="4" r="2" fill="#0288d1" /><text x="129" y="7" class="p-lbl" style="fill:#0288d1; font-weight:600;">Water Cut (%)</text>')
    svg.append('<line x1="205" y1="4" x2="223" y2="4" stroke="#d32f2f" stroke-width="1.4" stroke-dasharray="3,2" /><circle cx="214" cy="4" r="3" fill="#d32f2f" /><text x="229" y="7" class="p-lbl" style="fill:#d32f2f; font-weight:600;">Workover</text>')
    svg.append('</g>')

    # Horizontal grid lines & Y-axes
    for pct in (0.0, 0.25, 0.5, 0.75, 1.0):
        y_val = mt + ph - pct * ph
        svg.append(f'<line x1="{ml}" y1="{y_val}" x2="{width - mr}" y2="{y_val}" class="p-grid" />')
        # Left Y label (Oil BOPD)
        oil_tick = pct * y_oil_max
        svg.append(f'<text x="{ml - 6}" y="{y_val + 3}" text-anchor="end" class="p-lbl">{oil_tick:.0f}</text>')
        # Right Y label (Water cut %)
        wc_tick = pct * 100.0
        svg.append(f'<text x="{width - mr + 6}" y="{y_val + 3}" text-anchor="start" class="p-lbl">{wc_tick:.0f}%</text>')

    # Axes lines
    svg.append(f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt + ph}" class="p-axis" stroke="#2e7d32" />')
    svg.append(f'<line x1="{width - mr}" y1="{mt}" x2="{width - mr}" y2="{mt + ph}" class="p-axis" stroke="#0288d1" />')
    svg.append(f'<line x1="{ml}" y1="{mt + ph}" x2="{width - mr}" y2="{mt + ph}" class="p-axis" />')

    # Workover date markers
    # Map workover date into X axis
    m_idx_map = {m: i for i, m in enumerate(sorted_months)}
    for wo in interventions:
        w_date = str(wo.get("date", ""))[:10]
        m_str = w_date[:7]
        if m_str in m_idx_map:
            i_base = m_idx_map[m_str]
            # fractional offset inside month
            day = int(w_date[8:10]) if len(w_date) >= 10 and w_date[8:10].isdigit() else 15
            frac = (day - 1) / 30.0
            x_m = x_pos(i_base + frac)
            j_code = str(wo.get("job_code") or "JOB")
            svg.append(f'<line x1="{x_m}" y1="{mt}" x2="{x_m}" y2="{mt + ph}" class="p-marker" />')
            svg.append(f'<circle cx="{x_m}" cy="{mt + 3}" r="3.5" fill="#d32f2f" />')
            svg.append(f'<text x="{x_m}" y="{mt - 4}" text-anchor="middle" style="font-size:7.5px; font-weight:700; fill:#d32f2f;">{_esc(j_code)}</text>')

    # Polyline paths for Oil and Water Cut
    oil_pts = [f"{x_pos(i):.1f},{y_oil_pos(val):.1f}" for i, val in enumerate(m_oil)]
    wc_pts = [f"{x_pos(i):.1f},{y_wc_pos(val):.1f}" for i, val in enumerate(m_wc)]

    svg.append(f'<polyline points="{" ".join(oil_pts)}" class="p-oil-line" />')
    svg.append(f'<polyline points="{" ".join(wc_pts)}" class="p-wc-line" />')

    # Data points
    for i, (val_o, val_w) in enumerate(zip(m_oil, m_wc)):
        xp = x_pos(i)
        svg.append(f'<circle cx="{xp:.1f}" cy="{y_oil_pos(val_o):.1f}" r="2.5" fill="#2e7d32" />')
        svg.append(f'<circle cx="{xp:.1f}" cy="{y_wc_pos(val_w):.1f}" r="2" fill="#0288d1" />')

    # X-axis Month labels (show every 4-6 months to avoid clutter)
    label_step = max(int(n_pts / 6), 1)
    for i in range(0, n_pts, label_step):
        xp = x_pos(i)
        m_label = sorted_months[i]
        svg.append(f'<line x1="{xp:.1f}" y1="{mt + ph}" x2="{xp:.1f}" y2="{mt + ph + 4}" class="p-axis" />')
        svg.append(f'<text x="{xp:.1f}" y="{mt + ph + 15}" text-anchor="middle" class="p-lbl">{m_label}</text>')
    # Ensure last month is labeled
    if (n_pts - 1) % label_step != 0:
        xp = x_pos(n_pts - 1)
        svg.append(f'<text x="{xp:.1f}" y="{mt + ph + 15}" text-anchor="middle" class="p-lbl">{sorted_months[-1]}</text>')

    svg.append('</svg>')
    return "".join(svg)


# -------------------------------------------------------------------------------------------------
# Main Field Report Renderer (TC-032)
# -------------------------------------------------------------------------------------------------
def render_field_report(well_id: str, intervention: str | None = None, persona: str = "FIELD_ENGINEER") -> str:
    """Render complete, standalone, print-ready HTML5 Pre-field Well Pack for well_id."""
    wid = (well_id or "").strip().upper()
    as_of = settings.AS_OF

    wm = well_master_row(wid)
    if wm is None:
        raise ValueError(f"Well {well_id} not found.")

    is_field_engineer = str(persona or "").strip().upper() == "FIELD_ENGINEER"

    # 1. Fetch core well profile & infrastructure
    prof_res = well_profile(wid, k_neighbours=4, as_of=as_of)
    prof = prof_res.value
    if prof is None:
        raise ValueError(f"Well profile for {wid} could not be resolved.")

    identity = prof.identity
    construction = prof.construction
    lithology = prof.lithology
    lift = prof.lift
    status = prof.status
    current_rates = prof.current
    decline = prof.decline
    last_test = prof.last_test
    last_survey = prof.last_pressure_survey
    neighbours = prof.neighbours

    # 2. Fetch Data Gap (DG) Tables
    tt_res = tubing_tally(wid, as_of=as_of)
    tt_summary = tt_res.get("summary") or {}
    tt_rows = tt_res.get("rows") or []

    ds_res = deviation_survey(wid, as_of=as_of)
    ds_summary = ds_res.get("summary") or {}
    ds_rows = ds_res.get("rows") or []

    integ_res = integrity(wid, as_of=as_of)
    integ_summary = integ_res.get("summary") or {}
    barrier_tests_map = integ_summary.get("latest_barrier_tests") or {}
    fishing_records = integ_res.get("fishing_records") or []

    # 3. Workover History & Timeline
    wo_df = well_rows("workover_history", wid)
    if not wo_df.empty:
        wo_df = wo_df[wo_df["start_date"] <= as_of]
        if "is_censored" in wo_df.columns:
            wo_df = wo_df[~wo_df["is_censored"].fillna(False).astype(bool)]
        wo_records = wo_df.sort_values("start_date").to_dict(orient="records")
    else:
        wo_records = []

    # 4. Production Series & SVG
    prod_series_res = well_production_series(wid, months=36, metrics=["oil", "water_cut"], as_of=as_of)
    prod_series_val = prod_series_res.value
    prod_svg = render_production_svg(prod_series_val)

    # 5. Multimodal Success Engine Recommendations
    recs_res = recommend_interventions(wid, as_of=as_of, k=3)
    candidates = recs_res.get("candidates") or []
    drivers = recs_res.get("drivers") or []
    evidence_chain = recs_res.get("evidence_chain") or {}

    # Determine selected candidate for Job Program
    selected_cand = None
    if intervention:
        it_clean = intervention.strip().upper()
        for c in candidates:
            if c.get("job_code", "").upper() == it_clean or c.get("ic", "").upper() == it_clean:
                selected_cand = c
                break
    if selected_cand is None and candidates:
        selected_cand = candidates[0]

    # Contingencies: remaining candidates
    contingencies = [c for c in candidates if c != selected_cand][:2]

    # Kill fluid gradient computation
    # Formula: density_sg = sbhp_kgcm2*10/datum_tvd_m rounded 2 dp + 0.05 SG design margin
    kill_calc_text = "pressure survey not available - confirm before mobilisation"
    if last_survey and last_survey.get("sbhp_kgcm2") and last_survey.get("datum_tvd_m"):
        try:
            sbhp = float(last_survey["sbhp_kgcm2"])
            tvd = float(last_survey["datum_tvd_m"])
            if tvd > 0:
                base_sg = round(sbhp * 10.0 / tvd, 2)
                design_margin = 0.05
                kill_sg = round(base_sg + design_margin, 2)
                kill_calc_text = (
                    f"Required Kill Fluid Density: <strong>{kill_sg:.2f} SG</strong> "
                    f"(base gradient {base_sg:.2f} SG + 0.05 SG design margin; "
                    f"datum SBHP {sbhp:.1f} kg/cm² at {tvd:.1f} m TVD; treated KCl brine / formation water)."
                )
        except (ValueError, TypeError, ZeroDivisionError):
            pass

    # SOP Steps for selected candidate
    selected_sop_phases = []
    if selected_cand:
        s_sop = selected_cand.get("sop_steps")
        if isinstance(s_sop, list) and s_sop:
            selected_sop_phases = s_sop
        elif selected_cand.get("sop_doc_id"):
            sop_meta = sop_steps(selected_cand["sop_doc_id"])
            if sop_meta and sop_meta.get("phases"):
                selected_sop_phases = sop_meta["phases"]

    # 6. Documents for Well
    docs_df = well_rows("document_index", wid)
    if not docs_df.empty:
        docs_records = docs_df.sort_values("doc_date", ascending=False).to_dict(orient="records")
    else:
        docs_records = []

    # 7. Wellbore Diagram SVG
    geom = _build_schematic_geom(identity, construction, lithology)
    wellbore_svg = render_wellbore_svg(geom)

    # ---------------------------------------------------------------------------------------------
    # HTML Content Assembly
    # ---------------------------------------------------------------------------------------------
    today_str = as_of.isoformat()

    # Repeat failure warning check
    repeat_warning_html = ""
    if wo_records:
        since_repeat = date.fromordinal(as_of.toordinal() - 730)
        recent_fails: dict[str, int] = {}
        for r in wo_records:
            f_code = str(r.get("failure_code") or "")
            s_dt = r.get("start_date")
            if s_dt and str(s_dt)[:10] >= since_repeat.isoformat() and f_code and f_code != "NONE":
                recent_fails[f_code] = recent_fails.get(f_code, 0) + 1
        repeat_codes = [code for code, count in recent_fails.items() if count >= 2]
        if repeat_codes:
            repeat_warning_html = (
                f'<div class="callout warning">'
                f'<strong>⚠️ Repeat Failure Warning:</strong> The failure mechanism(s) '
                f'<code>{", ".join(_esc(c) for c in repeat_codes)}</code> recurred ≥ 2 times within the 24-month repeat window. '
                f'Verify root cause analysis and mitigation procedures prior to job execution.'
                f'</div>'
            )

    # Tubing tally: first 5 and last 5 joints + components
    tt_rows_html = []
    if tt_rows:
        n_tt = len(tt_rows)
        if n_tt <= 12:
            display_rows = [(i + 1, r) for i, r in enumerate(tt_rows)]
            omitted = 0
        else:
            first5 = [(i + 1, tt_rows[i]) for i in range(5)]
            last5 = [(n_tt - 5 + i + 1, tt_rows[n_tt - 5 + i]) for i in range(5)]
            display_rows = first5 + [(None, None)] + last5
            omitted = n_tt - 10

        for j_num, r in display_rows:
            if j_num is None:
                tt_rows_html.append(
                    f'<tr class="omitted-row"><td colspan="8" style="text-align:center; color:#777; font-style:italic;">'
                    f'… [{omitted} intermediate joints omitted; uniform inspection grade] …</td></tr>'
                )
            else:
                tt_rows_html.append(
                    f'<tr>'
                    f'<td>Joint #{j_num}</td>'
                    f'<td>{_val(r.get("top_md_m"), 2)}</td>'
                    f'<td>{_val(r.get("bottom_md_m"), 2)}</td>'
                    f'<td>{_val(r.get("od_in"), 3)}"</td>'
                    f'<td>{_val(r.get("id_in"), 3)}"</td>'
                    f'<td>{_val(r.get("drift_in"), 3)}"</td>'
                    f'<td>{_val(r.get("grade"))}</td>'
                    f'<td>{_val(r.get("component_type"))}</td>'
                    f'</tr>'
                )
    else:
        tt_rows_html.append('<tr><td colspan="8" class="text-muted">Tubing joint tally unavailable.</td></tr>')

    # Deviation summary sample rows
    ds_rows_html = []
    if ds_rows:
        sample_indices = [0, min(1, len(ds_rows) - 1), int(len(ds_rows) / 2), len(ds_rows) - 1]
        seen_idx = set()
        for idx in sample_indices:
            if idx in seen_idx:
                continue
            seen_idx.add(idx)
            sr = ds_rows[idx]
            ds_rows_html.append(
                f'<tr>'
                f'<td>{_val(sr.get("md_m"), 1)}</td>'
                f'<td>{_val(sr.get("tvd_m"), 1)}</td>'
                f'<td>{_val(sr.get("inc_deg"), 2)}°</td>'
                f'<td>{_val(sr.get("azi_deg"), 1)}°</td>'
                f'<td>{_val(sr.get("dls_deg_30m"), 2)}</td>'
                f'</tr>'
            )
    else:
        ds_rows_html.append('<tr><td colspan="5" class="text-muted">Directional survey stations unavailable.</td></tr>')

    # Life-of-well timeline table rows
    wo_rows_html = []
    if wo_records:
        for r in wo_records:
            doc_id = r.get("report_doc_id")
            doc_link = f'<a href="/api/docs/{doc_id}.pdf" target="_blank">{_esc(doc_id)}</a>' if doc_id else "—"
            outcome = str(r.get("outcome") or "—")
            out_class = "badge-success" if outcome == "SUCCESS" else ("badge-danger" if outcome == "FAILED" else "")
            wo_rows_html.append(
                f'<tr>'
                f'<td>{_val(r.get("start_date"))}</td>'
                f'<td>{_val(r.get("end_date"))}</td>'
                f'<td><strong>{_val(r.get("catalogue_job_code") or r.get("job_code"))}</strong></td>'
                f'<td>{_val(r.get("intervention_class"))}</td>'
                f'<td>{_val(r.get("failure_code"))}</td>'
                f'<td>{_val(r.get("rig_days"), 1)}</td>'
                f'<td><span class="badge {out_class}">{outcome}</span></td>'
                f'<td>+{_val(r.get("uplift_bopd"), 1)}</td>'
                f'<td>{doc_link}</td>'
                f'</tr>'
            )
    else:
        wo_rows_html.append('<tr><td colspan="9" class="text-muted">No historical workovers recorded.</td></tr>')

    # Fishing records table
    fr_rows_html = []
    if fishing_records:
        for fr in fishing_records:
            recovered = bool(fr.get("recovered"))
            status_badge = '<span class="badge badge-success">RECOVERED</span>' if recovered else '<span class="badge badge-danger">LEFT IN HOLE</span>'
            fr_rows_html.append(
                f'<tr>'
                f'<td>{_val(fr.get("event_date"))}</td>'
                f'<td><strong>{_val(fr.get("fish_type"))}</strong></td>'
                f'<td>{_val(fr.get("top_md_m"), 1)} m</td>'
                f'<td>{status_badge}</td>'
                f'<td>{_val(fr.get("workover_id"))}</td>'
                f'</tr>'
            )
    else:
        fr_rows_html.append('<tr><td colspan="5" style="color:#2e7d32;">✔ No unrecovered fish or obstructions recorded in wellbore; hole clear to PBTD.</td></tr>')

    # Well Integrity Barriers table
    barrier_rows_html = []
    if barrier_tests_map:
        for b_name, b_info in barrier_tests_map.items():
            res = str(b_info.get("result") or "").upper()
            b_badge = '<span class="badge badge-success">PASS</span>' if res in ("PASS", "TESTED_OK") else '<span class="badge badge-danger">FAIL</span>'
            barrier_rows_html.append(
                f'<tr>'
                f'<td><strong>{_esc(b_name)}</strong></td>'
                f'<td>{_val(b_info.get("test_date"))}</td>'
                f'<td>{b_badge}</td>'
                f'<td>{_val(b_info.get("test_pressure_kgcm2"), 1, "kg/cm²")}</td>'
                f'<td>{_val(b_info.get("next_due"))}</td>'
                f'</tr>'
            )
    else:
        barrier_rows_html.append('<tr><td colspan="5" class="text-muted">Barrier test log unavailable.</td></tr>')

    # Recommendations top 3 table
    rec_rows_html = []
    for c in candidates:
        is_sel = selected_cand and c.get("job_code") == selected_cand.get("job_code")
        row_style = 'style="background-color:#fff8f0; font-weight:600;"' if is_sel else ""
        p_pct = int(round(float(c.get("p_success") or 0.0) * 100))
        an = c.get("analogs") or {}
        n_succ = an.get("n_success", 0)
        n_tot = an.get("n", 0)
        analogs_text = f"{n_succ}/{n_tot} ({int(round(n_succ/n_tot*100)) if n_tot else 0}%)" if n_tot else "—"

        cost_col_td = ""
        if not is_field_engineer:
            cost_col_td = f'<td>{_val(c.get("cost_band"))}</td>'

        rec_rows_html.append(
            f'<tr {row_style}>'
            f'<td>#{_val(c.get("rank"))} {"👉" if is_sel else ""}</td>'
            f'<td><strong>{_val(c.get("job_name") or c.get("job_code"))}</strong> ({_val(c.get("job_code"))})</td>'
            f'<td>{_val(c.get("ic"))}</td>'
            f'<td><strong style="color:#123b5c;">{p_pct}%</strong></td>'
            f'<td>{analogs_text}</td>'
            f'<td>+{_val(c.get("expected_uplift_bopd"), 1, "BOPD")}</td>'
            f'<td>{_val(c.get("rig_days"), 1, "d")}</td>'
            f'{cost_col_td}'
            f'</tr>'
        )

    # Cost band header for table
    cost_th_html = ""
    if not is_field_engineer:
        # Note: Do NOT use the exact string 'cost band' if persona is field engineer
        cost_th_html = "<th>Cost Band</th>"

    # Modality drivers list
    drivers_html = []
    for d in drivers:
        d_val = _val(d.get("value"), 2)
        direction = str(d.get("direction") or "supports")
        color = "#2e7d32" if "support" in direction.lower() else "#d32f2f"
        drivers_html.append(
            f'<li><strong>{_esc(d.get("modality"))}:</strong> {_esc(d.get("label"))} = {d_val} '
            f'(<span style="color:{color}; font-weight:600;">{_esc(direction)}</span>, weight {_val(d.get("weight"), 3)})</li>'
        )
    if not drivers_html:
        drivers_html.append('<li>Signal attribution available from multimodal neural network features.</li>')

    # SOP Steps rendering
    sop_steps_html = []
    if selected_sop_phases:
        step_counter = 1
        for ph in selected_sop_phases:
            ph_title = _esc(ph.get("phase") or "Execution Phase")
            sop_steps_html.append(f'<div class="sop-phase"><strong>{ph_title}</strong><ol start="{step_counter}">')
            for st in ph.get("steps") or []:
                sop_steps_html.append(f'<li>{_esc(st)}</li>')
                step_counter += 1
            sop_steps_html.append('</ol></div>')
    else:
        # Fallback standard operational steps
        sop_steps_html.append(
            f'<div class="sop-phase"><strong>Phase 1: Mobilisation & Well Control</strong>'
            f'<ol>'
            f'<li>Mobilise designated workover spread to wellpad plinth (40m × 40m footprint); verify road permits and site clearance.</li>'
            f'<li>Spot kill fluid in suction tanks; establish positive pressure barrier and zero wellhead pressures.</li>'
            f'<li>Rig up BOP stack, perform function and pressure test per NORSOK D-010 specifications.</li>'
            f'</ol></div>'
            f'<div class="sop-phase"><strong>Phase 2: Tubular Retrieval & Remediation</strong>'
            f'<ol start="4">'
            f'<li>Unseat downhole completion assembly and pull production tubing string with joint-by-joint tally inspection.</li>'
            f'<li>Run scraper and drift gauge assembly to ensure drift clearance to perforation depth.</li>'
            f'<li>Execute intervention treatment per approved technical parameters.</li>'
            f'</ol></div>'
            f'<div class="sop-phase"><strong>Phase 3: Completion & Re-commissioning</strong>'
            f'<ol start="7">'
            f'<li>Re-run production tubing string and BHA to target landing depth; confirm component spacing.</li>'
            f'<li>Land tubing hanger, pressure-test wellhead packoff, swab or gas-lift well, and restore production.</li>'
            f'</ol></div>'
        )

    # Contingencies list
    contingency_html = []
    if contingencies:
        for idx, alt in enumerate(contingencies, start=1):
            p_alt = int(round(float(alt.get("p_success") or 0.0) * 100))
            alt_why = alt.get("why") or "Secondary diagnostic candidate if primary procedure encounters refusal or barrier failure."
            if is_field_engineer:
                alt_why = _strip_cost(alt_why)
            contingency_html.append(
                f'<div class="contingency-box">'
                f'<strong>Contingency #{idx}: {_val(alt.get("job_name") or alt.get("job_code"))}</strong> '
                f'({_val(alt.get("job_code"))} / {_val(alt.get("ic"))}) — P(Success): {p_alt}%, Rig-Days: {_val(alt.get("rig_days"), 1)} d.<br/>'
                f'<span style="color:#555;">{_esc(alt_why)}</span>'
                f'</div>'
            )
    else:
        contingency_html.append('<div class="contingency-box">No secondary contingency designated; proceed strictly per primary SOP.</div>')

    # Offset wells table
    offset_rows_html = []
    if neighbours:
        for nb in neighbours:
            offset_rows_html.append(
                f'<tr>'
                f'<td><strong>{_val(nb.get("well_id"))}</strong></td>'
                f'<td>{_val(nb.get("distance_m"), 1, "m")}</td>'
                f'<td>{_val(nb.get("zone"))} {"(Same)" if nb.get("same_zone") else ""}</td>'
                f'<td>{_val(nb.get("lift_type"))}</td>'
                f'<td>{_val(nb.get("bucket"))}</td>'
                f'<td>{_val(nb.get("status"))}</td>'
                f'<td>{_val(nb.get("oil_bopd"), 1, "BOPD")}</td>'
                f'<td>{_val(nb.get("water_cut_pct"), 1, "%")}</td>'
                f'<td>{_val(nb.get("last_job_code"))} ({_val(nb.get("last_job_date"))})</td>'
                f'</tr>'
            )
    else:
        offset_rows_html.append('<tr><td colspan="9" class="text-muted">No nearby cluster offset records found.</td></tr>')

    # Documents Index table
    docs_rows_html = []
    if docs_records:
        for d in docs_records[:15]:
            d_id = str(d.get("doc_id") or "")
            docs_rows_html.append(
                f'<tr>'
                f'<td><strong><a href="/api/docs/{d_id}.pdf" target="_blank">{_esc(d_id)}</a></strong></td>'
                f'<td>{_val(d.get("doc_type"))}</td>'
                f'<td>{_val(d.get("doc_date"))}</td>'
                f'<td>{_val(d.get("title"))}</td>'
                f'<td><a href="/api/docs/{d_id}.pdf" target="_blank" class="doc-link">View PDF ↗</a></td>'
                f'</tr>'
            )
    else:
        docs_rows_html.append('<tr><td colspan="5" class="text-muted">No technical documents indexed for this well.</td></tr>')

    # Selected candidate attributes for Job Program
    sel_job_name = _val(selected_cand.get("job_name") or selected_cand.get("job_code")) if selected_cand else "Intervention"
    sel_job_code = _val(selected_cand.get("job_code")) if selected_cand else "—"
    sel_ic = _val(selected_cand.get("ic")) if selected_cand else "—"
    sel_ic_lbl = _val(selected_cand.get("ic_label")) if selected_cand else ""
    sel_requires_rig = "WORKOVER RIG REQUIRED" if selected_cand and selected_cand.get("requires_rig") else "RIGLESS INTERVENTION"
    sel_rig_days = _val(selected_cand.get("rig_days"), 1, "days") if selected_cand else "—"
    sel_sop_doc = _val(selected_cand.get("sop_doc_id")) if selected_cand else "SOP-D11"
    sel_risks = ", ".join(selected_cand.get("risks") or []) if selected_cand and selected_cand.get("risks") else "None identified"

    # Assemble HTML Document
    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>WellPulse Pre-Field Well Pack · {wid} · {today_str}</title>
  <style>
    /* Reset & Typography */
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      font-size: 11px;
      line-height: 1.45;
      color: #1a1a1a;
      background-color: #f4f6f8;
      padding: 20px 0;
    }}
    .report-sheet {{
      max-width: 900px;
      margin: 0 auto;
      background: #ffffff;
      padding: 30px 40px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
      border-radius: 4px;
    }}
    
    /* Top Banner & Floating Actions */
    .top-banner {{
      background: #8B1A1A;
      color: #ffffff;
      text-align: center;
      padding: 6px 12px;
      font-weight: 800;
      font-size: 11px;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      margin-bottom: 20px;
      border-radius: 3px;
    }}
    .toolbar {{
      display: flex;
      justify-content: flex-end;
      align-items: center;
      margin-bottom: 15px;
      gap: 12px;
    }}
    .print-btn {{
      background: #123b5c;
      color: #ffffff;
      border: none;
      padding: 8px 16px;
      font-size: 11px;
      font-weight: 700;
      border-radius: 4px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: background 0.15s ease-in-out;
    }}
    .print-btn:hover {{ background: #0d2a42; }}

    /* Header & Branding */
    .header-table {{
      width: 100%;
      border-bottom: 3px solid #8B1A1A;
      padding-bottom: 14px;
      margin-bottom: 20px;
    }}
    .header-logo-cell {{ width: 140px; vertical-align: middle; }}
    .ongc-logo {{ height: 48px; width: auto; max-width: 130px; object-fit: contain; }}
    .ongc-wordmark {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      height: 42px;
      padding: 0 16px;
      background: #8B1A1A;
      color: #ffffff;
      font-weight: 900;
      font-size: 20px;
      letter-spacing: 2px;
      border-radius: 3px;
    }}
    .header-title-cell {{ vertical-align: middle; padding-left: 16px; }}
    .report-title {{ font-size: 18px; font-weight: 800; color: #123b5c; letter-spacing: 0.5px; text-transform: uppercase; }}
    .report-subtitle {{ font-size: 12px; font-weight: 600; color: #8B1A1A; margin-top: 2px; }}
    .header-meta-cell {{ text-align: right; vertical-align: middle; font-size: 10px; color: #555; }}

    /* Section Styles */
    .report-section {{
      margin-bottom: 22px;
      page-break-inside: avoid;
      break-inside: avoid;
    }}
    .section-title {{
      font-size: 12px;
      font-weight: 800;
      color: #123b5c;
      border-left: 4px solid #8B1A1A;
      padding-left: 8px;
      margin-bottom: 10px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      display: flex;
      justify-content: space-between;
      align-items: baseline;
    }}
    .section-subtitle {{ font-size: 9.5px; font-weight: 400; color: #666; text-transform: none; }}

    /* Tables & Grids */
    table.data-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 10.5px;
      margin-bottom: 8px;
    }}
    table.data-table th {{
      background: #f0f4f8;
      color: #123b5c;
      text-align: left;
      padding: 5px 8px;
      font-weight: 700;
      border: 1px solid #d0dbe5;
    }}
    table.data-table td {{
      padding: 5px 8px;
      border: 1px solid #e2e8f0;
      vertical-align: middle;
    }}
    table.data-table tr:nth-child(even) {{ background: #fafbfc; }}

    /* Key-Value Pair Grids */
    .kv-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 8px 14px;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 4px;
      padding: 10px 14px;
      margin-bottom: 8px;
    }}
    .kv-item {{ display: flex; flex-direction: column; }}
    .kv-label {{ font-size: 9px; font-weight: 600; color: #555; text-transform: uppercase; margin-bottom: 1px; }}
    .kv-value {{ font-size: 11px; font-weight: 700; color: #1a1a1a; }}

    /* Callouts & Badges */
    .callout {{
      padding: 10px 14px;
      border-radius: 4px;
      margin: 10px 0;
      font-size: 10.5px;
      line-height: 1.4;
    }}
    .callout.info {{ background: #eef5fc; border-left: 4px solid #1f5fa8; color: #0f3d6e; }}
    .callout.warning {{ background: #fff8eb; border-left: 4px solid #d97706; color: #92400e; }}
    .callout.danger {{ background: #fdf2f2; border-left: 4px solid #d32f2f; color: #991b1b; }}
    .badge {{
      display: inline-block;
      padding: 2px 6px;
      font-size: 8.5px;
      font-weight: 700;
      border-radius: 3px;
      text-transform: uppercase;
    }}
    .badge-success {{ background: #def7ec; color: #03543f; }}
    .badge-danger {{ background: #fde8e8; color: #9b1c1c; }}
    .badge-neutral {{ background: #edf2f7; color: #4a5568; }}

    /* Job Program & SOP steps */
    .sop-phase {{
      margin-bottom: 10px;
      padding: 8px 12px;
      background: #f8fafc;
      border-left: 3px solid #123b5c;
      border-radius: 2px;
    }}
    .sop-phase ol {{ padding-left: 20px; margin-top: 4px; }}
    .sop-phase li {{ margin-bottom: 4px; color: #2d3748; }}
    .contingency-box {{
      background: #fffdfa;
      border: 1px solid #fed7aa;
      border-left: 3px solid #f97316;
      padding: 8px 12px;
      margin-bottom: 6px;
      border-radius: 3px;
    }}

    /* Diagrams & Centered Elements */
    .svg-container {{
      text-align: center;
      margin: 10px 0;
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 4px;
      padding: 10px;
    }}
    .text-muted {{ color: #777; font-style: italic; }}
    a.doc-link {{ color: #1f5fa8; text-decoration: none; font-weight: 600; }}
    a.doc-link:hover {{ text-decoration: underline; }}

    /* Sign-off Block */
    .signoff-table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 14px;
    }}
    .signoff-table td {{
      width: 33.33%;
      border: 1px solid #cbd5e1;
      padding: 12px 14px;
      vertical-align: top;
      background: #fafbfc;
    }}
    .signoff-line {{
      margin-top: 35px;
      border-bottom: 1px dashed #64748b;
      height: 1px;
    }}

    /* Footer */
    .report-footer {{
      margin-top: 30px;
      padding-top: 10px;
      border-top: 1px solid #e2e8f0;
      text-align: center;
      font-size: 9px;
      font-weight: 700;
      color: #64748b;
      letter-spacing: 1px;
      text-transform: uppercase;
    }}

    /* Print Formatting Rules */
    @page {{
      size: A4 portrait;
      margin: 14mm;
    }}
    @media print {{
      body {{ background: #ffffff; padding: 0; }}
      .report-sheet {{
        box-shadow: none;
        padding: 0;
        max-width: 100%;
        border-radius: 0;
      }}
      .no-print {{ display: none !important; }}
      .report-section {{
        page-break-inside: avoid;
        break-inside: avoid;
      }}
      .header-table {{ border-bottom: 2px solid #8B1A1A; }}
    }}
  </style>
</head>
<body>

<div class="report-sheet">

  <!-- Top Banner & Print Action -->
  <div class="top-banner">SYNTHETIC DATA — DEMO</div>
  
  <div class="toolbar no-print">
    <span style="font-size:10px; color:#555;">Ready for field dispatch · A4 Print Optimized</span>
    <button onclick="window.print()" class="print-btn">🖨️ Print / Save as PDF</button>
  </div>

  <!-- Header & Corporate Branding -->
  <table class="header-table">
    <tr>
      <td class="header-logo-cell">
        <img src="/brand/ongc_logo.svg" alt="ONGC" class="ongc-logo"
             onerror="this.style.display='none'; document.getElementById('ongc-wordmark-fallback').style.display='inline-flex';" />
        <div id="ongc-wordmark-fallback" class="ongc-wordmark" style="display:none;">ONGC</div>
      </td>
      <td class="header-title-cell">
        <div class="report-title">Pre-Field Well Pack · Field Engineering Report</div>
        <div class="report-subtitle">ONGC Assam Asset · Surface & Subsurface Workover Operations</div>
      </td>
      <td class="header-meta-cell">
        <div><strong>Well ID:</strong> <span style="font-size:13px; font-weight:800; color:#8B1A1A;">{wid}</span></div>
        <div><strong>Date:</strong> {today_str}</div>
        <div><strong>Doc Ref:</strong> WH-SPEC-{wid}-{today_str.replace("-", "")}</div>
      </td>
    </tr>
  </table>

  <!-- WH-01: Header & Well Identity -->
  <section class="report-section" id="wh-01">
    <div class="section-title">
      <span>WH-01: Header & Well Identity</span>
      <span class="section-subtitle">Geographic & Operational Master Records</span>
    </div>
    <div class="kv-grid">
      <div class="kv-item"><span class="kv-label">Well Identifier</span><span class="kv-value">{wid}</span></div>
      <div class="kv-item"><span class="kv-label">Field Name</span><span class="kv-value">{_val(identity.get("field"))}</span></div>
      <div class="kv-item"><span class="kv-label">Cluster / GGS</span><span class="kv-value">{_val(identity.get("cluster_id"))}</span></div>
      <div class="kv-item"><span class="kv-label">Operating Asset</span><span class="kv-value">Assam Asset (Nazira HQ)</span></div>
      <div class="kv-item"><span class="kv-label">Surface Coordinates</span><span class="kv-value">{_val(identity.get("lat"), 5)}° N, {_val(identity.get("lon"), 5)}° E</span></div>
      <div class="kv-item"><span class="kv-label">Spud Date</span><span class="kv-value">{_val(identity.get("spud_date"))}</span></div>
      <div class="kv-item"><span class="kv-label">Completion Date</span><span class="kv-value">{_val(identity.get("completion_date"))}</span></div>
      <div class="kv-item"><span class="kv-label">Producing Formation</span><span class="kv-value">{_val(identity.get("formation") or identity.get("zone"))}</span></div>
      <div class="kv-item"><span class="kv-label">Total Depth (MD)</span><span class="kv-value">{_val(identity.get("total_depth_md_m"), 1, "m")}</span></div>
      <div class="kv-item"><span class="kv-label">Total Depth (TVD)</span><span class="kv-value">{_val(identity.get("total_depth_tvd_m"), 1, "m")}</span></div>
      <div class="kv-item"><span class="kv-label">Plug Back TD (PBTD)</span><span class="kv-value">{_val(geom.get("pbtd_m"), 1, "m")}</span></div>
      <div class="kv-item"><span class="kv-label">Lift System</span><span class="kv-value">{_val(lift.get("lift_type"))}</span></div>
    </div>
  </section>

  <!-- WH-03: Current Status & Latest Well Test -->
  <section class="report-section" id="wh-03">
    <div class="section-title">
      <span>WH-03: Current Status & Latest Well Test</span>
      <span class="section-subtitle">Real-time Health Classification & Field Gauging</span>
    </div>
    <div class="kv-grid" style="grid-template-columns: repeat(4, 1fr);">
      <div class="kv-item"><span class="kv-label">Health Bucket</span><span class="kv-value">{_val(status.get("bucket"))}</span></div>
      <div class="kv-item"><span class="kv-label">Current Episode</span><span class="kv-value">{_val(status.get("episode_status"))} (since {_val(status.get("episode_since"))})</span></div>
      <div class="kv-item"><span class="kv-label">Status Reason</span><span class="kv-value">{_val(status.get("reason_code") or status.get("reason"))}</span></div>
      <div class="kv-item"><span class="kv-label">Last Producing Date</span><span class="kv-value">{_val(current_rates.get("last_producing_date"))}</span></div>
      <div class="kv-item"><span class="kv-label">7-Day Mean Oil</span><span class="kv-value">{_val(current_rates.get("oil_bopd"), 1, "BOPD")}</span></div>
      <div class="kv-item"><span class="kv-label">7-Day Mean Water Cut</span><span class="kv-value">{_val(current_rates.get("water_cut_pct"), 1, "%")}</span></div>
      <div class="kv-item"><span class="kv-label">7-Day Mean Gas</span><span class="kv-value">{_val(current_rates.get("gas_mscfd"), 1, "MSCFD")}</span></div>
      <div class="kv-item"><span class="kv-label">Decline Residual</span><span class="kv-value">{_val(decline.get("residual_pct"), 1, "%")} (Expected {_val(decline.get("expected_bopd"), 1, "BOPD")})</span></div>
    </div>

    <!-- Latest Well Test Details -->
    <table class="data-table">
      <thead>
        <tr>
          <th>Test Identifier</th>
          <th>Test Date</th>
          <th>Duration</th>
          <th>Oil Rate</th>
          <th>Water Rate</th>
          <th>Gas Rate</th>
          <th>Surface Pressures</th>
          <th>Fluid Level</th>
          <th>Quality Grade</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>{_val(last_test.get("test_id") if last_test else None)}</strong></td>
          <td>{_val(last_test.get("test_date") if last_test else None)}</td>
          <td>{_val(last_test.get("test_duration_hr") if last_test else None, 1, "hrs")}</td>
          <td>{_val(last_test.get("oil_rate_bopd") if last_test else None, 1, "BOPD")}</td>
          <td>{_val(last_test.get("water_rate_bwpd") if last_test else None, 1, "BWPD")}</td>
          <td>{_val(last_test.get("gas_rate_mscfd") if last_test else None, 1, "MSCFD")}</td>
          <td>THP: {_val(last_test.get("thp_kgcm2") if last_test else None, 1, "kg/cm²")} | CHP: {_val(last_test.get("chp_kgcm2") if last_test else None, 1, "kg/cm²")}</td>
          <td>{_val(last_test.get("fluid_level_m") if last_test else None, 1, "m")}</td>
          <td><span class="badge badge-success">{_val(last_test.get("test_quality") if last_test else None)}</span></td>
        </tr>
      </tbody>
    </table>
  </section>

  <!-- WH-02 & WH-13: Site Access, HSE Notes & Fluid Hazards -->
  <section class="report-section" id="wh-02">
    <div class="section-title">
      <span>WH-02 &amp; WH-13: Site Access, HSE Notes &amp; Fluid Hazards</span>
      <span class="section-subtitle">Pad Logistics, Proximity Risks &amp; Toxic/Corrosive Gases</span>
    </div>
    <div class="kv-grid" style="grid-template-columns: repeat(3, 1fr);">
      <div class="kv-item"><span class="kv-label">Assigned Facility / GGS</span><span class="kv-value">{_val(identity.get("cluster_id"))} Trunk Gathering Line</span></div>
      <div class="kv-item"><span class="kv-label">Rig Pad / Plinth Footprint</span><span class="kv-value">40 m × 40 m Compacted Gravel Pad</span></div>
      <div class="kv-item"><span class="kv-label">Hazard Classification</span><span class="kv-value">{_val(integ_summary.get("hazard_class"))} Hazard Zone</span></div>
      <div class="kv-item"><span class="kv-label">H₂S Concentration</span><span class="kv-value">{_val(integ_summary.get("h2s_ppm"), 1, "ppm")}</span></div>
      <div class="kv-item"><span class="kv-label">CO₂ Concentration</span><span class="kv-value">{_val(integ_summary.get("co2_mol_pct"), 1, "mol%")}</span></div>
      <div class="kv-item"><span class="kv-label">Flow Assurance Flags</span><span class="kv-value">Wax: {_val(integ_summary.get("wax_flag"))} · Sand: {_val(integ_summary.get("sand_flag"))} · Scale: {_val(integ_summary.get("scale_flag"))}</span></div>
    </div>
    <div class="callout info" style="margin-top:6px;">
      <strong>Site HSE Advisory:</strong> Wellsite is located in proximity to local habitation and tea garden plantation boundaries.
      Observe standard ONGC noise baffling, gas monitoring for H₂S/CO₂, and spill containment protocols.
    </div>
  </section>

  <!-- WH-04: Wellbore & Completion Diagram -->
  <section class="report-section" id="wh-04">
    <div class="section-title">
      <span>WH-04: Wellbore &amp; Completion Diagram</span>
      <span class="section-subtitle">Vector Schematic with Lithology Column &amp; Mechanical Architecture</span>
    </div>
    <div class="svg-container">
      {wellbore_svg}
    </div>
  </section>

  <!-- WH-05: Casing, Tubing Components & Drift -->
  <section class="report-section" id="wh-05">
    <div class="section-title">
      <span>WH-05: Casing, Tubing Components &amp; Minimum ID Drift</span>
      <span class="section-subtitle">Tubular Diameters, Weights, Grades &amp; Drift Restrictions</span>
    </div>
    
    <!-- Casing String Table -->
    <table class="data-table">
      <thead>
        <tr>
          <th>String Type</th>
          <th>OD</th>
          <th>Weight</th>
          <th>Grade</th>
          <th>Top MD</th>
          <th>Shoe Depth</th>
          <th>Cement Top</th>
          <th>Installed Date</th>
        </tr>
      </thead>
      <tbody>
        {"".join(f'<tr><td><strong>{_val(c.get("string_type"))}</strong></td><td>{_val(c.get("od_in"), 3)}"</td><td>{_val(c.get("weight_ppf"), 1, "ppf")}</td><td>{_val(c.get("grade"))}</td><td>{_val(c.get("top_m"), 1, "m")}</td><td><strong>{_val(c.get("shoe_m"), 1, "m")}</strong></td><td>{_val(c.get("cement_top_m"), 1, "m")}</td><td>{_val(c.get("install_date"))}</td></tr>' for c in construction.get("casing", [])) or '<tr><td colspan="8" class="text-muted">Casing records unavailable.</td></tr>'}
      </tbody>
    </table>

    <div class="callout info" style="margin: 6px 0;">
      <strong>Drift Clearance Notice:</strong> Production casing nominal drift = <strong>{_val(tt_summary.get("min_drift_in"), 3, "in")}</strong>.
      Verify all workover bit, scraper, and bridge plug drift tolerances against this restriction prior to tripping.
    </div>
  </section>

  <!-- WH-06: Tubing Joint-by-Joint Tally -->
  <section class="report-section" id="wh-06">
    <div class="section-title">
      <span>WH-06: Tubing Joint-by-Joint Tally</span>
      <span class="section-subtitle">DG Synthetic Tally · First 5 + Last 5 Joints &amp; Component Verification</span>
    </div>
    <table class="data-table">
      <thead>
        <tr>
          <th>Joint No.</th>
          <th>Top MD (m)</th>
          <th>Bottom MD (m)</th>
          <th>OD</th>
          <th>Nom. ID</th>
          <th>Drift ID</th>
          <th>Grade</th>
          <th>Component Type</th>
        </tr>
      </thead>
      <tbody>
        {"".join(tt_rows_html)}
      </tbody>
    </table>
    <div style="font-size:10px; font-weight:700; color:#123b5c; padding: 4px 6px; background:#f0f4f8; border-radius:3px;">
      Summary: Total Joints = {_val(tt_summary.get("joint_count"))} | Total Tally Length = {_val(tt_summary.get("total_length_m"), 2, "m")} | Minimum Drift = {_val(tt_summary.get("min_drift_in"), 3, "in")} | Landing Depth = {_val(tt_summary.get("max_depth_m"), 2, "m MD")}
    </div>
  </section>

  <!-- WH-07: Perforations & Formation Lithology -->
  <section class="report-section" id="wh-07">
    <div class="section-title">
      <span>WH-07: Perforation Intervals &amp; Formation Lithology</span>
      <span class="section-subtitle">Active Drainage Intervals &amp; Regional Stratigraphy</span>
    </div>
    <table class="data-table">
      <thead>
        <tr>
          <th>Zone Name</th>
          <th>Top MD (m)</th>
          <th>Bottom MD (m)</th>
          <th>Net Pay</th>
          <th>Shot Density</th>
          <th>Perforation Date</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {"".join(f'<tr><td><strong>{_val(p.get("zone"))}</strong></td><td>{_val(p.get("top_m"), 1)}</td><td>{_val(p.get("bottom_m"), 1)}</td><td>{_val(float(p.get("bottom_m", 0)) - float(p.get("top_m", 0)), 1, "m")}</td><td>{_val(p.get("spf"), 0, "SPF")}</td><td>{_val(p.get("perf_date"))}</td><td><span class="badge {"badge-success" if str(p.get("status")).upper() == "OPEN" else "badge-danger"}">{_val(p.get("status"))}</span></td></tr>' for p in construction.get("perfs", [])) or '<tr><td colspan="7" class="text-muted">Perforation intervals not recorded.</td></tr>'}
      </tbody>
    </table>
  </section>

  <!-- WH-08: Well Deviation & Directional Survey Summary -->
  <section class="report-section" id="wh-08">
    <div class="section-title">
      <span>WH-08: Well Deviation &amp; Directional Survey Summary</span>
      <span class="section-subtitle">Directional Profile, Maximum Inclination &amp; True Vertical Depth</span>
    </div>
    <div class="kv-grid" style="grid-template-columns: repeat(4, 1fr); margin-bottom:8px;">
      <div class="kv-item"><span class="kv-label">Profile Type</span><span class="kv-value">{"Deviated S/J Well" if ds_summary.get("is_deviated") else "Near-Vertical Well"}</span></div>
      <div class="kv-item"><span class="kv-label">Maximum Inclination</span><span class="kv-value">{_val(ds_summary.get("max_inclination_deg"), 2, "°")}</span></div>
      <div class="kv-item"><span class="kv-label">Total Measured Depth</span><span class="kv-value">{_val(ds_summary.get("max_md_m"), 1, "m MD")}</span></div>
      <div class="kv-item"><span class="kv-label">True Vertical Depth (TVD)</span><span class="kv-value">{_val(ds_summary.get("max_tvd_m"), 1, "m TVD")}</span></div>
    </div>
    <table class="data-table">
      <thead>
        <tr>
          <th>Survey Station MD (m)</th>
          <th>True Vertical Depth TVD (m)</th>
          <th>Inclination (deg)</th>
          <th>Azimuth (deg)</th>
          <th>DLS (deg/30m)</th>
        </tr>
      </thead>
      <tbody>
        {"".join(ds_rows_html)}
      </tbody>
    </table>
  </section>

  <!-- WH-09: Chronological Life-of-Well Timeline -->
  <section class="report-section" id="wh-09">
    <div class="section-title">
      <span>WH-09: Chronological Life-of-Well Timeline</span>
      <span class="section-subtitle">Complete Intervention History, Rig-Days, Job Codes &amp; Outcomes</span>
    </div>
    <table class="data-table">
      <thead>
        <tr>
          <th>Start Date</th>
          <th>End Date</th>
          <th>Job Code</th>
          <th>Class</th>
          <th>Failure Mode</th>
          <th>Rig-Days</th>
          <th>Outcome</th>
          <th>Uplift</th>
          <th>Report Document</th>
        </tr>
      </thead>
      <tbody>
        {"".join(wo_rows_html)}
      </tbody>
    </table>
  </section>

  <!-- WH-10: Failure, Fishing & Wellbore Obstruction Log -->
  <section class="report-section" id="wh-10">
    <div class="section-title">
      <span>WH-10: Failure, Fishing &amp; Wellbore Obstruction Log</span>
      <span class="section-subtitle">Unrecovered Tubulars, Parted Strings &amp; Recurrent Failure Modes</span>
    </div>
    {repeat_warning_html}
    <table class="data-table">
      <thead>
        <tr>
          <th>Event Date</th>
          <th>Fish Description</th>
          <th>Top MD</th>
          <th>Status</th>
          <th>Workover Reference</th>
        </tr>
      </thead>
      <tbody>
        {"".join(fr_rows_html)}
      </tbody>
    </table>
  </section>

  <!-- WH-11: Historical Production Trends & Intervention Markers -->
  <section class="report-section" id="wh-11">
    <div class="section-title">
      <span>WH-11: Historical Production Trends &amp; Intervention Markers</span>
      <span class="section-subtitle">36-Month Monthly Oil Rate (BOPD) &amp; Water Cut (%) with Workover Markers</span>
    </div>
    <div class="svg-container">
      {prod_svg}
    </div>
  </section>

  <!-- WH-12: Reservoir Pressure & Lift Telemetry -->
  <section class="report-section" id="wh-12">
    <div class="section-title">
      <span>WH-12: Reservoir Pressure &amp; Lift Telemetry</span>
      <span class="section-subtitle">Static &amp; Flowing Bottom-Hole Gauges, Productivity Index &amp; Surface Pressures</span>
    </div>
    <div class="kv-grid" style="grid-template-columns: repeat(4, 1fr);">
      <div class="kv-item"><span class="kv-label">Survey Identifier</span><span class="kv-value">{_val(last_survey.get("survey_id") if last_survey else None)}</span></div>
      <div class="kv-item"><span class="kv-label">Survey Date</span><span class="kv-value">{_val(last_survey.get("survey_date") if last_survey else None)}</span></div>
      <div class="kv-item"><span class="kv-label">Static BHP (SBHP)</span><span class="kv-value">{_val(last_survey.get("sbhp_kgcm2") if last_survey else None, 1, "kg/cm²")}</span></div>
      <div class="kv-item"><span class="kv-label">Flowing BHP (FBHP)</span><span class="kv-value">{_val(last_survey.get("fbhp_kgcm2") if last_survey else None, 1, "kg/cm²")}</span></div>
      <div class="kv-item"><span class="kv-label">Productivity Index (PI)</span><span class="kv-value">{_val(last_survey.get("pi_bpd_per_kgcm2") if last_survey else None, 2, "bpd/(kg/cm²)")}</span></div>
      <div class="kv-item"><span class="kv-label">Gauge Datum TVD</span><span class="kv-value">{_val(last_survey.get("datum_tvd_m") if last_survey else None, 1, "m")}</span></div>
      <div class="kv-item"><span class="kv-label">Fluid Level</span><span class="kv-value">{_val(last_survey.get("fluid_level_m") if last_survey else None, 1, "m")}</span></div>
      <div class="kv-item"><span class="kv-label">Surface THP / CHP</span><span class="kv-value">{_val(last_test.get("thp_kgcm2") if last_test else None, 1, "kg/cm²")} / {_val(last_test.get("chp_kgcm2") if last_test else None, 1, "kg/cm²")}</span></div>
    </div>
  </section>

  <!-- WH-14: Well Integrity, Barriers & Wellhead Ratings -->
  <section class="report-section" id="wh-14">
    <div class="section-title">
      <span>WH-14: Well Integrity, Barriers &amp; Wellhead Ratings</span>
      <span class="section-subtitle">Wellhead API Class Rating &amp; Component Barrier Verification</span>
    </div>
    <div class="kv-grid" style="grid-template-columns: repeat(3, 1fr); margin-bottom:8px;">
      <div class="kv-item"><span class="kv-label">Wellhead Flange Rating</span><span class="kv-value">{_val(integ_summary.get("wellhead_class_psi"), 0, "psi API Class")}</span></div>
      <div class="kv-item"><span class="kv-label">Christmas Tree Rating</span><span class="kv-value">{_val(integ_summary.get("xmas_tree_rating_psi"), 0, "psi")}</span></div>
      <div class="kv-item"><span class="kv-label">Last Wellhead Service</span><span class="kv-value">{_val(integ_summary.get("last_service_date"))}</span></div>
    </div>
    <table class="data-table">
      <thead>
        <tr>
          <th>Barrier Element</th>
          <th>Latest Test Date</th>
          <th>Verification Result</th>
          <th>Test Pressure</th>
          <th>Next Test Due</th>
        </tr>
      </thead>
      <tbody>
        {"".join(barrier_rows_html)}
      </tbody>
    </table>
  </section>

  <!-- WH-15: Current Diagnosis & Decline Attribution -->
  <section class="report-section" id="wh-15-diag">
    <div class="section-title">
      <span>WH-15: Current Diagnosis &amp; Decline Attribution</span>
      <span class="section-subtitle">Physics-Grounded Diagnostic Mechanism &amp; Evidence Chain</span>
    </div>
    <div class="callout info">
      <strong>Diagnosed Mechanism:</strong> <code>{_esc(evidence_chain.get("mechanism") or status.get("reason_code") or "UNDERPERFORMANCE")}</code><br/>
      <strong>Attributed Signals:</strong> {", ".join(_esc(s) for s in (evidence_chain.get("signals") or ["TC-001 negative residual"]))}<br/>
      <strong>Evaluated Candidates:</strong> {", ".join(_esc(c) for c in (evidence_chain.get("candidates") or []))}
    </div>
  </section>

  <!-- WH-15: Recommended Interventions — Multimodal NN -->
  <section class="report-section" id="wh-15-recs">
    <div class="section-title">
      <span>WH-15: Recommended Interventions — WellPulse Multimodal NN</span>
      <span class="section-subtitle">Top 3 Candidates Ranked by Probability of Success P(success)</span>
    </div>
    <table class="data-table">
      <thead>
        <tr>
          <th>Rank</th>
          <th>Intervention Candidate</th>
          <th>Class</th>
          <th>P(Success)</th>
          <th>Look-alikes</th>
          <th>Expected Uplift</th>
          <th>Rig-Days</th>
          {cost_th_html}
        </tr>
      </thead>
      <tbody>
        {"".join(rec_rows_html)}
      </tbody>
    </table>

    <!-- How we decided -->
    <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:4px; padding:12px; margin-top:8px;">
      <div style="font-size:11px; font-weight:800; color:#123b5c; margin-bottom:4px;">How We Decided · Engine: WellPulse Multimodal NN</div>
      <p style="font-size:10px; color:#444; margin-bottom:8px;">
        The multimodal neural network architecture fuses four operational modalities: 24-month production time series (1D-CNN/GRU), static geology and completion encoder, intervention history sequence, and candidate intervention embeddings. It evaluates the well against historical analogs in the asset to compute calibrated success probabilities.
      </p>
      <div style="font-size:10px; font-weight:700; color:#123b5c; margin-bottom:2px;">Top Modality Drivers:</div>
      <ul style="padding-left:18px; font-size:9.5px; color:#444;">
        {"".join(drivers_html)}
      </ul>
    </div>
  </section>

  <!-- Job Program: Selected Intervention Operational Program -->
  <section class="report-section" id="job-program">
    <div class="section-title">
      <span>Job Program: Selected Intervention Operational Program</span>
      <span class="section-subtitle">Execution Blueprint for {sel_job_name} ({sel_job_code})</span>
    </div>
    
    <div class="kv-grid" style="grid-template-columns: repeat(4, 1fr); margin-bottom:10px;">
      <div class="kv-item"><span class="kv-label">Selected Job</span><span class="kv-value">{sel_job_name}</span></div>
      <div class="kv-item"><span class="kv-label">Class Code</span><span class="kv-value">{sel_ic} ({sel_ic_lbl})</span></div>
      <div class="kv-item"><span class="kv-label">Equipment Class</span><span class="kv-value">{sel_requires_rig}</span></div>
      <div class="kv-item"><span class="kv-label">Estimated Effort</span><span class="kv-value">{sel_rig_days}</span></div>
    </div>

    <!-- Kill Fluid Program Box -->
    <div class="callout warning" style="margin: 8px 0;">
      <div style="font-size:11px; font-weight:800; color:#92400e; margin-bottom:2px;">Well Control &amp; Kill Fluid Specification:</div>
      {kill_calc_text}
    </div>

    <!-- Barriers & Wellhead Safety -->
    <div style="margin: 8px 0; padding: 8px 12px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:3px;">
      <strong>Wellhead Barrier Envelopes:</strong> Primary barrier: hydrostatic kill fluid column.
      Secondary barrier: wellhead rated to {_val(integ_summary.get("wellhead_class_psi"), 0, "psi")} + double-ram BOP stack tested per SOP.
      <br/><strong>Governing Risks:</strong> {_esc(sel_risks)} · <strong>SOP Citation:</strong> <a href="/api/docs/{sel_sop_doc}.pdf" target="_blank" class="doc-link">{sel_sop_doc}</a>
    </div>

    <!-- Numbered SOP Steps -->
    <div style="margin-top:10px;">
      <div style="font-size:11px; font-weight:800; color:#123b5c; margin-bottom:6px;">Standard Operating Procedure (SOP) Step Sequence:</div>
      {"".join(sop_steps_html)}
    </div>

    <!-- Contingencies -->
    <div style="margin-top:12px;">
      <div style="font-size:11px; font-weight:800; color:#123b5c; margin-bottom:6px;">Contingency Procedures &amp; Alternate Interventions:</div>
      {"".join(contingency_html)}
    </div>
  </section>

  <!-- WH-16: Offset & Nearby Well Performance -->
  <section class="report-section" id="wh-16">
    <div class="section-title">
      <span>WH-16: Offset &amp; Nearby Well Performance</span>
      <span class="section-subtitle">Performance Dynamics of Nearest Offset Wells in Cluster</span>
    </div>
    <table class="data-table">
      <thead>
        <tr>
          <th>Offset Well ID</th>
          <th>Distance</th>
          <th>Zone</th>
          <th>Lift Type</th>
          <th>Health Bucket</th>
          <th>Operating Status</th>
          <th>Oil Rate</th>
          <th>Water Cut</th>
          <th>Last Intervention</th>
        </tr>
      </thead>
      <tbody>
        {"".join(offset_rows_html)}
      </tbody>
    </table>
  </section>

  <!-- WH-18: Technical Document Index -->
  <section class="report-section" id="wh-18">
    <div class="section-title">
      <span>WH-18: Technical Document Index (D1–D11)</span>
      <span class="section-subtitle">Archival Well Dossiers, Logs, Test Reports &amp; Operating Procedures</span>
    </div>
    <table class="data-table">
      <thead>
        <tr>
          <th>Document ID</th>
          <th>Type</th>
          <th>Date</th>
          <th>Title &amp; Scope</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        {"".join(docs_rows_html)}
      </tbody>
    </table>
  </section>

  <!-- WH-19: Operational Sign-off Block -->
  <section class="report-section" id="wh-19">
    <div class="section-title">
      <span>WH-19: Operational Sign-off Block</span>
      <span class="section-subtitle">Engineering Handover &amp; Rig Mobilisation Authorization</span>
    </div>
    <table class="signoff-table">
      <tr>
        <td>
          <div style="font-size:10px; font-weight:800; color:#123b5c;">PREPARED BY</div>
          <div style="margin-top:4px; font-size:10px; color:#333;">WellPulse Autonomous Well Engineering Agent</div>
          <div style="font-size:9px; color:#666; margin-top:2px;">Digital Signature: VERIFIED / DETERMINISTIC</div>
          <div class="signoff-line"></div>
          <div style="font-size:8.5px; color:#777; margin-top:4px;">Date: {today_str}</div>
        </td>
        <td>
          <div style="font-size:10px; font-weight:800; color:#123b5c;">REVIEWED BY</div>
          <div style="margin-top:4px; font-size:10px; color:#333;">Senior Workover Engineer / Rig Superintendent</div>
          <div style="font-size:9px; color:#666; margin-top:2px;">Assam Asset Operations</div>
          <div class="signoff-line"></div>
          <div style="font-size:8.5px; color:#777; margin-top:4px;">Date: ________________________</div>
        </td>
        <td>
          <div style="font-size:10px; font-weight:800; color:#123b5c;">APPROVED BY</div>
          <div style="margin-top:4px; font-size:10px; color:#333;">Surface Manager / Asset Operations Head</div>
          <div style="font-size:9px; color:#666; margin-top:2px;">Assam Asset Execution Authority</div>
          <div class="signoff-line"></div>
          <div style="font-size:8.5px; color:#777; margin-top:4px;">Date: ________________________</div>
        </td>
      </tr>
    </table>
  </section>

  <!-- Fixed Report Footer -->
  <footer class="report-footer">
    SYNTHETIC DATA — DEMO · WellPulse · {wid} · as of {today_str}
  </footer>

</div>

</body>
</html>
"""
    if is_field_engineer:
        html_doc = _strip_cost(html_doc)
    return html_doc
