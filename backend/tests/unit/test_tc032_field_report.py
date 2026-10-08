"""Stage FR (v0.5): TC-032 printable field report (Pre-field Well Pack)."""
from __future__ import annotations

import random
import re
import time

import pytest
from fastapi.testclient import TestClient

from app.analytics.tools.common import load_table
from app.analytics.tools.field_report import render_field_report

CORE_WELLS = ["GK-129", "LKW-019", "LKM-061"]
# Whole words only: the Lakhmani field name must not count as "lakh".
CURRENCY = re.compile(r"₹|\busd\b|rupee|\blakhs?\b|\bcrores?\b|\bnpv\b", re.IGNORECASE)


def _sample_wells(n: int = 10, seed: int = 32) -> list[str]:
    ids = sorted(set(load_table("well_master")["well_id"].astype(str)) - set(CORE_WELLS))
    return random.Random(seed).sample(ids, min(n, len(ids)))


def _assert_report_shape(html: str) -> None:
    low = html.lower()
    assert "synthetic data" in low
    assert "<svg" in low
    assert "job program" in low
    m = CURRENCY.search(html)
    assert m is None, f"currency token in report: {m.group(0)!r}"


@pytest.mark.parametrize("well", CORE_WELLS + _sample_wells())
def test_renders_for_core_and_random_wells(well):
    _assert_report_shape(render_field_report(well))


@pytest.mark.parametrize("well", CORE_WELLS)
def test_field_engineer_has_no_cost_band(well):
    fe = render_field_report(well, persona="FIELD_ENGINEER")
    assert "cost band" not in fe.lower()
    am = render_field_report(well, persona="ASSET_MANAGER")
    assert "cost band" in am.lower(), "non-FE persona keeps the cost band column"
    _assert_report_shape(am)


def test_route_html_and_404():
    from app.main import app

    c = TestClient(app)
    r = c.get("/api/wells/GK-129/report", headers={"X-Persona": "FIELD_ENGINEER"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "cost band" not in r.text.lower()
    assert c.get("/api/wells/ZZ-999/report").status_code == 404


def test_render_latency_after_warmup():
    render_field_report("GK-129")
    t0 = time.perf_counter()
    render_field_report("GK-129")
    assert time.perf_counter() - t0 < 3.0
