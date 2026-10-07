"""TC-025 query_hierarchy (BDD-F05-S01 / S04) and TC-016 v2 multi-field map with cluster polygons (Gate T)."""

from __future__ import annotations

from app.analytics.tools.common import ToolStatus, currency_keys
from app.analytics.tools.geodata import build_field_geojson, cluster_polygons, load_field_geojson
from app.analytics.tools.hierarchy import query_hierarchy
from app.analytics.tools.render_well_map import render_well_map


def test_fields_and_clusters():
    r = query_hierarchy()
    assert r.status == ToolStatus.OK
    f = {x["field"]: x for x in r.value["fields"]}
    assert (f["Geleki"]["n_wells"], len(f["Geleki"]["clusters"])) == (142, 3)
    assert (f["Lakwa"]["n_wells"], len(f["Lakwa"]["clusters"])) == (160, 3)
    assert (f["Lakhmani"]["n_wells"], len(f["Lakhmani"]["clusters"])) == (110, 2)
    for x in f.values():
        assert sum(c["n_wells"] for c in x["clusters"]) == x["n_wells"]
    assert r.value["n_wells"] == 412
    assert currency_keys(r.value) == []


def test_filters_and_refusals():
    r = query_hierarchy(field="lakwa")
    assert [x["field"] for x in r.value["fields"]] == ["Lakwa"]
    r = query_hierarchy(cluster_id="LKW-GGS-II")
    assert [c["cluster_id"] for c in r.value["fields"][0]["clusters"]] == ["LKW-GGS-II"]
    bad = query_hierarchy(field="Rudrasagar")
    assert bad.status == ToolStatus.UNAVAILABLE and "Lakhmani" in bad.message  # lists the 3 fields
    assert query_hierarchy(cluster_id="NOPE").status == ToolStatus.UNAVAILABLE


def test_geojson_files_three_ggs_for_lakwa():
    gj = load_field_geojson("Lakwa")
    kinds = [f["properties"]["kind"] for f in gj["features"]]
    assert kinds.count("FIELD_BOUNDARY") == 1 and kinds.count("CLUSTER_POLYGON") == 3
    assert all(f["properties"]["is_synthetic_geometry"] for f in gj["features"])
    assert {p["properties"]["cluster_id"] for p in cluster_polygons("Lakwa")} == {"LKW-GGS-I", "LKW-GGS-II", "LKW-GGS-III"}
    assert len(cluster_polygons("Lakhmani")) == 2
    # committed file == deterministic rebuild from data
    assert build_field_geojson("Lakwa")["features"] == gj["features"]


def _inside(lon, lat, ring):
    c = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            c = not c
    return c


def test_lakwa_map_only_lkw_wells_and_3_ggs_polygons():
    r = render_well_map(field="Lakwa")
    v = r.value
    assert len(v.points) == 160 and all(p["well_id"].startswith("LKW-") for p in v.points)
    assert len(v.cluster_polygons) == 3
    rings = {p["properties"]["cluster_id"]: p["geometry"]["coordinates"][0] for p in v.cluster_polygons}
    for p in v.points:  # every well sits inside its own GGS polygon
        assert _inside(p["lng"], p["lat"], rings[p["cluster_id"]]), p["well_id"]
    assert any(p["oil_bopd"] is not None for p in v.points)


def test_multi_field_map():
    r = render_well_map(field="Lakwa,Lakhmani")
    assert r.value.fields == ["Lakwa", "Lakhmani"] and len(r.value.points) == 270
    assert len(r.value.cluster_polygons) == 5
    assert len(render_well_map(field="ALL").value.points) == 412
