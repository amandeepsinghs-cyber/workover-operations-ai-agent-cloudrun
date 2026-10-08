"""Stage ED-2 (v0.6): F-28 completion diagram in the dashboard (GET /api/wells/{id}/schematic.svg)."""
from __future__ import annotations

import random
import xml.etree.ElementTree as ET

import pytest
from fastapi.testclient import TestClient

from app.analytics.tools.common import load_table, well_rows
from app.analytics.tools.field_report import render_well_schematic_svg

CORE = ["GK-129", "LKW-019", "LKM-061"]


def _sample(n: int = 10, seed: int = 28) -> list[str]:
    ids = sorted(set(load_table("well_master")["well_id"].astype(str)) - set(CORE))
    return random.Random(seed).sample(ids, n)


@pytest.mark.parametrize("well", CORE + _sample())
def test_diagram_draws_every_perforation(well):
    svg = render_well_schematic_svg(well)
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    assert 'height="auto"' not in svg and "<br/>" not in svg
    assert "TD (Total Depth)" in svg
    ET.fromstring(svg)  # must be well-formed XML, or browsers will not render it as an image (ED-8)
    perfs = well_rows("perforation_intervals", well)
    assert svg.count("Perforations:") == len(perfs)


def test_route_svg_and_404():
    from app.main import app

    c = TestClient(app)
    r = c.get("/api/wells/GK-129/schematic.svg")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml")
    assert c.get("/api/wells/ZZ-999/schematic.svg").status_code == 404
