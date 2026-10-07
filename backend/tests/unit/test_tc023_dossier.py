"""TC-023 field-engineer dossier (Stage S, F-06; BDD-F06-S01, S03, S04, S05; Gate S).

Gate S: 2–4 pages, ≤ 10 s, all 9 sections (incl. lithology from formation_tops and casing/tubing tallies), every
number traced (fact-slot validator 100 %), GK-129 cites the 1998 CBL and the 2019 failed WSO, LKW-047 carries the
HUMAN_PROCESS attribution and the PUMP_OVERHAUL NBA + SOP-IC-01 (as-of per pinned_values R-D1), no currency, JSON
export kept.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import json
import re
import time
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.analytics.tools import dossier as D
from app.analytics.tools.common import ToolStatus

LKW_DISPATCH = date(2026, 7, 6)   # day before WO-LKW-047-007 (pump job); pinned_values R-D1 lists it as PUMP_OVERHAUL
LKW_RD1 = date(2026, 5, 14)       # R-D1 gate as-of: last producing day before EP-LKW-047-040
CURRENCY_RE = re.compile(r"₹|\bINR\b|\bUSD\b|US\$|\$\s?\d|\blakh|\bcrore|\brupee|payback|\bNPV\b", re.IGNORECASE)


def _text(pdf: Path) -> str:
    return "\n".join(p.extract_text() or "" for p in PdfReader(str(pdf)).pages)


def _pdf(r) -> Path:
    return D.dossier_dir() / r.value.file_name


@pytest.fixture(scope="module")
def lkw_fe():
    t0 = time.perf_counter()
    r = D.build_well_dossier("LKW-047", persona="FIELD_ENGINEER", as_of=LKW_DISPATCH)
    return r, time.perf_counter() - t0


@pytest.fixture(scope="module")
def gk129():
    t0 = time.perf_counter()
    r = D.build_well_dossier("GK-129")
    return r, time.perf_counter() - t0


# ------------------------------------------------------------------------------------------------ BDD-F06-S01
def test_f06_s01_lkw047_pages_time_sections(lkw_fe):
    r, dt = lkw_fe
    assert r.value is not None, r.message
    v = r.value
    assert 2 <= v.pages <= 4, v.pages
    assert dt <= 10.0, f"dossier took {dt:.1f} s"
    assert v.sections == list(D.SECTION_TITLES) and len(v.sections) == 9
    text = _text(_pdf(r))
    flat = re.sub(r"\s+", " ", text)
    for title in D.SECTION_TITLES:
        assert title in flat, title
    # Construction & Lithology: casing tally + lithology column from formation_tops (WS-4, D-19)
    assert "Casing tally" in flat and "Lithology column (formation tops)" in flat
    for formation in ("Alluvium", "Namsang", "Tipam"):
        assert formation in flat
    assert "Tubing string / BHA tally" in flat
    assert len(v.highlights) == 3


def test_lkw047_attribution_nba_sop_as_of_dispatch(lkw_fe):
    r, _ = lkw_fe
    flat = re.sub(r"\s+", " ", _text(_pdf(r)))
    assert "largest class HUMAN_PROCESS" in flat
    assert "WAIT_ON_RIG" in flat and "WAIT_ON_MATERIAL" in flat
    assert "PUMP_OVERHAUL" in flat and "SOP-IC-01" in flat
    assert any("PUMP_OVERHAUL" in h for h in r.value.highlights)
    assert any("HUMAN_PROCESS" in h for h in r.value.highlights)
    assert "SOP-IC-01" in {s["doc_id"] for s in r.value.sources}


def test_lkw047_rd1_as_of_pump_overhaul_and_human_process():
    r = D.build_well_dossier("LKW-047", as_of=LKW_RD1)
    flat = re.sub(r"\s+", " ", _text(_pdf(r)))
    assert r.value.validation["ok"], r.value.validation
    assert "PUMP_OVERHAUL" in flat and "SOP-IC-01" in flat
    assert "HUMAN_PROCESS" in flat  # WAIT_ON_RIG / WAIT_ON_MATERIAL components inside the 180-day window


def test_field_engineer_sees_no_cost_band(lkw_fe):
    r, _ = lkw_fe
    flat = re.sub(r"\s+", " ", _text(_pdf(r)))
    assert "Cost band" not in flat and "cost band" not in flat


# ------------------------------------------------------------------------------------------------ BDD-F06-S03
@pytest.mark.parametrize("which", ["lkw_fe", "gk129"])
def test_f06_s03_every_number_traced(which, request):
    r, _ = request.getfixturevalue(which)
    val = r.value.validation
    assert val["ok"] and val["traced_pct"] == 100.0, val
    assert not val["missing_values"] and not val["stray_digits"]
    rec = json.loads((D.dossier_dir() / r.value.file_name.replace(".pdf", ".facts.json")).read_text())
    assert set(rec["facts"]) == set(rec["fact_sources"]) and all(rec["fact_sources"].values())
    # independent re-validation of the file on disk
    again = D.validate_pdf(_pdf(r), rec["facts"])
    assert again["ok"], again
    assert hashlib.sha256(_pdf(r).read_bytes()).hexdigest() == rec["pdf_sha256"]
    assert re.fullmatch(r"[0-9a-f]{64}", rec["data_sha256"])


def test_validator_catches_unslotted_digit(gk129, tmp_path):
    r, _ = gk129
    rec = json.loads((D.dossier_dir() / r.value.file_name.replace(".pdf", ".facts.json")).read_text())
    facts = dict(rec["facts"])
    facts.pop(next(k for k, v in facts.items() if k.startswith("casing[") and k.endswith(".shoe_m")))
    bad = D.validate_pdf(_pdf(r), facts)
    assert not bad["ok"] and bad["stray_digits"]


def test_static_no_digits_in_printed_literals():
    """Template rule (SDD §10.2) applied to dossier.py: string literals that can reach the PDF carry no digit.

    Exempt: docstrings, module-level constants, fact-slot sources (``put``/``text`` args ≥ 3 and ``source=``),
    dict keys / subscripts / comparisons, provenance / ``unavailable`` messages, and plumbing functions
    (paths, regexes, validation, result packing) whose strings never enter the PDF.
    """
    src = Path(D.__file__).read_text()
    tree = ast.parse(src)
    plumbing = {"_safe", "_fmt", "_clean", "dossier_dir", "dossier_name", "dossier_doc_id", "dossier_path", "validate_pdf",
                "_assemble", "build_well_dossier", "_dossier_from_rec", "data_hash", "_docs_for_well", "_doc_facts", "_norm"}
    exempt: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                exempt.add(id(body[0].value))
        if isinstance(node, ast.FunctionDef) and node.name in plumbing:
            exempt.update(id(n) for n in ast.walk(node))
        if isinstance(node, ast.Call):
            fn = getattr(node.func, "attr", getattr(node.func, "id", ""))
            if fn in ("put", "text"):
                for a in node.args[:1] + node.args[2:]:  # fact key (never printed) and source descriptor
                    exempt.update(id(n) for n in ast.walk(a))
                for kw in node.keywords:
                    if kw.arg in ("source",):
                        exempt.update(id(n) for n in ast.walk(kw.value))
            if fn == "_tool_ref":  # the id itself is put into a fact slot by _tool_ref
                exempt.update(id(n) for n in ast.walk(node))
            if fn in ("build_provenance", "unavailable", "denied", "fullmatch", "finditer", "sub", "compile", "encode"):
                exempt.update(id(n) for n in ast.walk(node))
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if k is not None:
                    exempt.update(id(n) for n in ast.walk(k))
                if isinstance(k, ast.Constant) and k.value in ("doc_type",):
                    exempt.update(id(n) for n in ast.walk(v))
        if isinstance(node, (ast.Subscript, ast.Compare)):
            exempt.update(id(n) for n in ast.walk(node.slice if isinstance(node, ast.Subscript) else node))
    for stmt in tree.body:  # module-level constants
        if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            exempt.update(id(n) for n in ast.walk(stmt))
    bad = [f"line {n.lineno}: {n.value!r}" for n in ast.walk(tree)
           if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in exempt and re.search(r"\d", n.value)
           and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", n.value)]  # identifier-like = column key (as validate.py)
    assert not bad, bad


# ------------------------------------------------------------------------------------------------ BDD-F06-S04
def test_f06_s04_gk129_cites_1998_cbl_and_2019_failed_wso(gk129):
    r, dt = gk129
    assert r.status == ToolStatus.OK, r.message
    assert 2 <= r.value.pages <= 4 and dt <= 10.0
    flat = re.sub(r"\s+", " ", _text(_pdf(r)))
    hz = flat.split("Hazards & Lessons", 2)[-1].split("Logistics")[0]
    # 1998 cement bond log: title + date
    assert "DOC-CBL-GK129-1998" in hz and "Cement Bond Log & Micro-Annulus Report GK-129 (1998)" in hz and "1998-04-15" in hz
    # 2019 failed straddle-packer water shut-off: report + RCA, title + date
    assert "DOC-SCAN-GK-129-2019" in hz and "Straddle Packer WSO (May 2019)" in hz and "2019-05-14" in hz
    assert "RCA-GK-129-2019" in hz
    assert "STRADDLE_PACKER on 2019-05-10 failed" in hz
    ids = {s["doc_id"] for s in r.value.sources}
    assert {"DOC-CBL-GK129-1998", "DOC-SCAN-GK-129-2019", "RCA-GK-129-2019"} <= ids


@pytest.mark.parametrize("which", ["lkw_fe", "gk129"])
def test_no_currency(which, request):
    r, _ = request.getfixturevalue(which)
    text = _text(_pdf(r))
    assert not CURRENCY_RE.search(text), CURRENCY_RE.search(text).group(0)
    assert not CURRENCY_RE.search(json.dumps(r.value.highlights))


# ------------------------------------------------------------------------------------------------ BDD-F06-S05
def test_f06_s05_missing_casing_declared(monkeypatch):
    real = D.well_profile

    def no_casing(well_id, k_neighbours=3, as_of=None):
        res = real(well_id, k_neighbours=k_neighbours, as_of=as_of)
        prof = res.value
        con = {**prof.construction, "casing": []}
        return dataclasses.replace(res, value=dataclasses.replace(prof, construction=con))

    monkeypatch.setattr(D, "well_profile", no_casing)
    r = D.build_well_dossier("LKM-061")
    flat = re.sub(r"\s+", " ", _text(_pdf(r)))
    cl = flat.split("Construction & Lithology", 1)[1].split("Production Snapshot")[0]
    assert "UNAVAILABLE — casing_tally" in cl
    assert "CONDUCTOR" not in cl and "PRODUCTION" not in cl.split("UNAVAILABLE — casing_tally")[0].split("Casing tally")[-1]
    assert "casing_tally" in r.missing_fields and r.status == ToolStatus.LOW_CONFIDENCE
    assert r.value.validation["ok"], r.value.validation


def test_ed_gets_construction_summary_only():
    r = D.build_well_dossier("GK-129", persona="ED")
    flat = re.sub(r"\s+", " ", _text(_pdf(r)))
    cl = flat.split("Construction & Lithology", 1)[1].split("Production Snapshot")[0]
    assert "Construction summary only" in cl and "Casing tally" not in cl
    assert "Lithology column (formation tops)" in cl
    assert r.value.validation["ok"]


def test_unknown_and_retired_wells():
    assert D.build_well_dossier("GK-999").status == ToolStatus.UNAVAILABLE
    assert D.build_well_dossier("GLK-129").status == ToolStatus.UNAVAILABLE


# ------------------------------------------------------------------------------------------------ API
@pytest.fixture(scope="module")
def client():
    from app.main import app

    return TestClient(app)


def test_api_post_dossier_and_file(client, gk129):
    resp = client.post("/api/wells/GK-129/dossier?refresh=false")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("OK", "LOW_CONFIDENCE") and body["data"]["pages"] in (2, 3, 4)
    assert body["data"]["pdf_url"].startswith("/api/files/dossiers/GK-129_")
    f = client.get(body["data"]["pdf_url"])
    assert f.status_code == 200 and f.headers["content-type"] == "application/pdf" and f.content[:4] == b"%PDF"
    assert client.get(body["data"]["facts_url"]).json()["data_sha256"] == body["data"]["data_sha256"]
    assert client.get("/api/files/dossiers/..%2F..%2Fsettings.py").status_code == 404
    assert client.get("/api/files/dossiers/GK-129_2020-01-01_AM.pdf").status_code == 404


def test_api_export_json_kept_and_pdf(client):
    j = client.get("/api/wells/GK-129/export")
    assert j.status_code == 200
    body = j.json()
    for k in ("well_id", "well_name", "field", "formation", "status", "coordinates", "current_metrics", "workovers",
              "reports", "export_timestamp", "as_of"):
        assert k in body, k
    assert body["pdf_url"] == "/api/wells/GK-129/export?format=pdf" and body["doc_id"].startswith("DOSSIER-GK-129-")
    assert "usd" not in json.dumps(body).lower()
    t0 = time.perf_counter()
    p = client.get("/api/wells/GK-129/export?format=pdf")
    assert p.status_code == 200 and p.headers["content-type"] == "application/pdf" and p.content[:4] == b"%PDF"
    assert time.perf_counter() - t0 <= 10.0
    assert client.get("/api/wells/GK-999/export?format=pdf").status_code == 404
    assert client.get("/api/wells/GLK-129/dossier").status_code in (404, 405)
    assert client.post("/api/wells/GLK-129/dossier").status_code == 404


def test_api_as_of_override_gated(client, monkeypatch):
    from app import settings

    monkeypatch.setattr(settings, "ALLOW_AS_OF_OVERRIDE", False, raising=False)
    assert client.post("/api/wells/LKW-047/dossier?as_of=2026-07-06").status_code == 422
