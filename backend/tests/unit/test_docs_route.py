"""Stage O: document routes + retrieval on a small hermetic corpus (SDD §13.4, F-10 / F-14).

A module fixture renders GK-129's documents (D1, D2, D5, D8), the Geleki field studies (D9)
and the asset-wide SOP library (D11) into a temp dir, scans the 1998 CBL (image-only PDF),
builds the TF-IDF index and points the store at it through the env-var overrides.
"""
from __future__ import annotations

import json
import os

import pytest

from app.analytics.docs_pdf import store
from app.analytics.docs_pdf.facts import iter_specs
from app.analytics.docs_pdf.index import build as build_index
from app.analytics.docs_pdf.render import render_spec
from app.analytics.docs_pdf.scanify import scan_one

HERO_CBL = "DOC-CBL-GK129-1998"
HERO_WSO = "DOC-SCAN-GK-129-2019"


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    root = tmp_path_factory.mktemp("docs_pdf")
    idx = tmp_path_factory.mktemp("index")
    specs = list(iter_specs(["Geleki"], ["D01", "D02", "D05", "D08", "D09"], wells=["GK-129"]))
    specs += list(iter_specs(["Geleki"], ["D11"]))
    for s in specs:
        render_spec(s, root)
    cbl = next(s for s in specs if s.doc_id == HERO_CBL)
    _, err, _ = scan_one((cbl, root))
    assert err is None
    manifest = build_index(root, idx, 1)
    mp = pytest.MonkeyPatch()
    mp.setenv("WELLPULSE_DOCS_DIR", str(root))
    mp.setenv("WELLPULSE_DOCS_INDEX_DIR", str(idx))
    store.reload()
    yield {"root": root, "idx": idx, "specs": specs, "manifest": manifest}
    mp.undo()
    store.reload()


def test_hero_documents_exist(corpus):
    ids = {s.doc_id for s in corpus["specs"]}
    assert HERO_CBL in ids and HERO_WSO in ids and "RCA-GK-129-2019" in ids


def test_pdf_route_serves_pdf(client, corpus):
    r = client.get(f"/api/docs/{HERO_WSO}.pdf")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content[:4] == b"%PDF"


def test_scanned_pdf_has_no_text_layer_but_is_served(client, corpus):
    from pypdf import PdfReader
    import io

    r = client.get(f"/api/docs/{HERO_CBL}.pdf")
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    text = "".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(r.content)).pages)
    assert len(text.strip()) < 40
    meta = client.get(f"/api/docs/{HERO_CBL}/meta").json()
    assert meta["status"] == "OK"
    assert meta["data"]["has_text_layer"] in (False, 0)


def test_unknown_document_is_404(client, corpus):
    assert client.get("/api/docs/DOC-NOPE-0000.pdf").status_code == 404
    assert client.get("/api/docs/DOC-NOPE-0000/meta").status_code == 404


def test_well_documents_lists_real_docs(client, corpus):
    body = client.get("/api/wells/GK-129/documents").json()
    assert body["status"] == "OK"
    ids = {d["doc_id"] for d in body["data"]}
    assert {HERO_CBL, HERO_WSO, "DOC-COMP-GK-129"} <= ids
    for d in body["data"]:
        assert d["pdf_url"] == f"/api/docs/{d['doc_id']}.pdf"
        assert d["uri"].startswith(d["pdf_url"] + "#page=")


def test_well_documents_type_filter(client, corpus):
    body = client.get("/api/wells/GK-129/documents", params={"doc_types": "D5"}).json()
    assert body["data"] and {d["doc_type"] for d in body["data"]} == {"D5"}
    dated = {d["doc_id"]: d["doc_date"] for d in body["data"]}
    assert dated[HERO_CBL].startswith("1998")


def test_bad_doc_type_is_422(client, corpus):
    assert client.get("/api/wells/GK-129/documents", params={"doc_types": "D99"}).status_code == 422
    assert client.get("/api/docs/search", params={"q": "cement", "doc_types": "X1"}).status_code == 422


def test_unknown_and_retired_well_ids_are_404(client, corpus):
    assert client.get("/api/wells/GK-99999/documents").status_code == 404
    assert client.get("/api/wells/GLK-129/documents").status_code == 404


def test_search_finds_scanned_cbl(client, corpus):
    body = client.get("/api/docs/search", params={"q": "micro-annulus cement bond", "well_id": "GK-129"}).json()
    assert body["status"] == "OK"
    top = {h["doc_id"]: h for h in body["data"]}
    assert HERO_CBL in top
    hit = top[HERO_CBL]
    assert hit["scanned"] is True and "SCANNED" in hit["flags"]
    assert hit["uri"].startswith(f"/api/docs/{HERO_CBL}.pdf#page=")


def test_search_failed_wso_by_type(client, corpus):
    body = client.get("/api/docs/search", params={"q": "straddle packer water shut-off", "doc_types": "D2,D8",
                                                  "well_id": "GK-129"}).json()
    ids = [h["doc_id"] for h in body["data"]]
    assert HERO_WSO in ids or "RCA-GK-129-2019" in ids
    assert all(h["doc_type"] in ("D2", "D8") for h in body["data"])


def test_sop_library_covers_ic01_to_ic14(client, corpus):
    from app.analytics.docs_pdf.sop import load_sop

    for n in range(1, 15):
        ic = f"IC-{n:02d}"
        assert load_sop(ic) is not None, ic
        r = client.get(f"/api/docs/SOP-{ic}.pdf")
        assert r.status_code == 200 and r.content[:4] == b"%PDF", ic
    body = client.get("/api/docs/search", params={"q": "gas lift valve slickline", "doc_types": "D11"}).json()
    assert body["data"] and body["data"][0]["doc_id"].startswith("SOP-IC-")


def test_every_index_row_resolves(corpus):
    s = store.get_store()
    assert s is not None
    for doc_id in s.docs["doc_id"]:
        assert s.pdf_path(doc_id) is not None, doc_id


def test_facts_json_records_provenance(corpus):
    s = store.get_store()
    p = s.pdf_path(HERO_WSO)
    rec = json.loads(p.with_name(f"{HERO_WSO}.facts.json").read_text())
    assert rec["facts"]["uplift_bopd"] == "1.5"
    assert rec["facts"]["outcome"] == "FAILED"
    assert os.path.getsize(p) > 1000
