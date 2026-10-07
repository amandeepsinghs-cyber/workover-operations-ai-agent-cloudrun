"""Stage O: fact-slot discipline of the synthetic PDF corpus (F-10, BDD-F10 'no invented numbers').

Covers the literal checker, the read-only DocSpec, the static template scan and the
PDF-level fact / stray-digit validator on hand-crafted PDFs.
"""
from __future__ import annotations

import pickle

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.analytics.docs_pdf import ir
from app.analytics.docs_pdf.validate import check_record, static_check_module


# --------------------------------------------------------------------------- literal checker
@pytest.mark.parametrize("text", [
    "Top of cement at {cement_top_m} m above {perf_top_m} m.",
    "Step by step: rig up, kill the well, nipple up the BOP.",
    "Dual barriers verified to the approved test pressure.",
])
def test_literal_accepts_digit_free_text(text):
    assert ir.literal_violations(text) == []
    assert ir.check_literal(text) == text


@pytest.mark.parametrize("text", [
    "Cement top at 2435 m.",
    "Hold for 15 minutes.",
    "Use two barriers.",
    "Uplift of twenty BOPD.",
    "Water cut rose by ten percent.",
])
def test_literal_rejects_digits_and_number_words(text):
    assert ir.literal_violations(text)
    with pytest.raises(ir.FactSlotError):
        ir.check_literal(text, "unit-test")


def test_digits_inside_slot_names_are_allowed():
    # slot names are identifiers, not printed numbers
    assert ir.literal_violations("{d02_doc_id} and {pre_wc_avg}") == []


# --------------------------------------------------------------------------- DocSpec
def _spec(**over):
    kw = dict(doc_id="T-1", doc_type="D02", field="Geleki", well_id="GK-129", doc_date="2019-05-14",
              title="t", facts={"uplift_bopd": "1.5"}, raw={"uplift_bopd": 1.5}, sources={}, tables={}, meta={})
    kw.update(over)
    return ir.freeze_spec(**kw)


def test_docspec_is_read_only_and_picklable():
    s = _spec()
    with pytest.raises(Exception):
        s.facts["uplift_bopd"] = "999"
    with pytest.raises(Exception):
        s.doc_id = "X"  # type: ignore[misc]
    s2 = pickle.loads(pickle.dumps(s))
    assert s2.facts["uplift_bopd"] == "1.5"


# --------------------------------------------------------------------------- static template scan
def test_static_scan_flags_numeric_literals(tmp_path):
    bad = tmp_path / "dxx_bad.py"
    bad.write_text(
        'from app.analytics.docs_pdf.ir import P\n'
        'def build(spec):\n'
        '    return [P("Pump set at 1200 m."), P(f"{spec.doc_id}")]\n'
    )
    probs = static_check_module(bad)
    assert any("1200" in p for p in probs)
    assert any("f-string" in p.lower() or "joinedstr" in p.lower() for p in probs)


def test_static_scan_passes_clean_template(tmp_path):
    good = tmp_path / "dxx_good.py"
    good.write_text(
        '"""Docstring with 2024 is fine."""\n'
        'from app.analytics.docs_pdf.ir import P\n'
        'def build(spec):\n'
        '    return [P("Pump set at {pump_setting_depth_m} m.")]\n'
    )
    assert static_check_module(good) == []


# --------------------------------------------------------------------------- PDF validator
def _pdf(path, lines):
    c = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    for ln in lines:
        c.drawString(60, y, ln)
        y -= 18
    c.showPage()
    c.save()


def _rec(**facts):
    return {"doc_id": "T-1", "doc_type": "D02", "has_text_layer": True, "facts": facts, "tables": {}}


def test_pdf_check_passes_when_every_number_is_a_fact(tmp_path):
    p = tmp_path / "ok.pdf"
    _pdf(p, ["Pre-job oil 38.0 BOPD, post-job 39.5 BOPD.", "Uplift 1.5 BOPD."])
    assert check_record(_rec(pre="38.0", post="39.5", up="1.5"), p) == []


def test_pdf_check_flags_stray_digit(tmp_path):
    p = tmp_path / "stray.pdf"
    _pdf(p, ["Pre-job oil 38.0 BOPD, post-job 39.5 BOPD.", "Hold for 15 minutes."])
    probs = check_record(_rec(pre="38.0", post="39.5"), p)
    assert probs and "stray digit" in probs[0]


def test_pdf_check_flags_missing_fact(tmp_path):
    p = tmp_path / "miss.pdf"
    _pdf(p, ["Pre-job oil 38.0 BOPD."])
    probs = check_record(_rec(pre="38.0", post="39.5"), p)
    assert any("not found" in x for x in probs)


def test_pdf_check_does_not_merge_adjacent_numbers(tmp_path):
    # '3.0' must not be accepted as covering the '3' inside '3.05' and vice versa
    p = tmp_path / "adj.pdf"
    _pdf(p, ["Rig days 3.05 recorded."])
    probs = check_record(_rec(rd="3.0"), p)
    assert probs
