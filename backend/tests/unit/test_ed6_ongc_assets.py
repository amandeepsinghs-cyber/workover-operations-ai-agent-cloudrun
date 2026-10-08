"""Stage ED-6 (v0.6): India view — 13 ONGC assets, position-only tags outside Assam (F-32, D-34)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.analytics.tools.ongc_assets import ongc_assets


def test_thirteen_assets_only_assam_live():
    d = ongc_assets()
    assert d["n_assets"] == 13 == len(d["assets"])
    live = [a for a in d["assets"] if a["live"]]
    assert [a["asset_id"] for a in live] == ["ASSAM"]
    assert live[0]["fields"] == ["Lakwa", "Lakhmani", "Geleki"] and live[0]["well_tags"] == []


def test_tags_are_position_only_and_near_centre():
    for a in ongc_assets()["assets"]:
        if a["live"]:
            continue
        assert 8 <= len(a["well_tags"]) <= 30
        names = [t["name"] for t in a["well_tags"]]
        assert len(names) == len(set(names))
        for t in a["well_tags"]:
            assert set(t) == {"name", "lat", "lng"}  # D-34: no data behind a tag
            assert abs(t["lat"] - a["lat"]) < 0.5 and abs(t["lng"] - a["lng"]) < 0.5


def test_deterministic_and_route():
    from app.main import app

    r = TestClient(app).get("/api/geo/ongc-assets")
    assert r.status_code == 200 and r.json() == ongc_assets()
