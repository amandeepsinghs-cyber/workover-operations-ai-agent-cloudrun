"""Parquet vs. BigQuery backend parity + lakehouse gate checks (Stage X, BDD F-15 S01/S03, SDD §15.3).

Runs against the live lakehouse in ``workover-operations-agentic-ai`` / ``asia-south1``. Skips
cleanly when Application Default Credentials are unavailable or the Silver layer has not been
loaded (CI without GCP); on a developer box with ADC it must pass.

What it proves:
- raw frames served by ``BigQueryRepository`` are identical to ``ParquetRepository`` (values,
  dtypes, column order, row order);
- repository outputs and REST responses for the fixture wells are identical on both backends;
- every BigQuery read carries the pruning predicates (field / folder, production_date <= AS_OF);
- Silver row counts == landing parquet row counts; Silver daily_production partitioning/clustering;
- Gold ``field_kpi_monthly`` reconciles to the repository's monthly field sums within 0.1 %.
"""

from __future__ import annotations

import json
import math
import os
from datetime import date

import pandas as pd
import pyarrow.parquet as pq
import pytest

from app import settings
from app.data_access import repository as r
from app.data_access.parquet_repo import ParquetRepository

PROJECT = os.getenv("WELLPULSE_BQ_PROJECT", "workover-operations-agentic-ai")
LOCATION = os.getenv("WELLPULSE_BQ_LOCATION", "asia-south1")
FIXTURE_WELLS = ["GK-129", "GK-101", "LKW-047", "LKW-112", "LKW-088", "LKM-023", "LKM-061", "LKM-090"]
FIELDS = ["Geleki", "Lakwa", "Lakhmani"]


def _bq_client_or_skip():
    try:
        import google.auth
        from google.cloud import bigquery

        google.auth.default()
        client = bigquery.Client(project=PROJECT, location=LOCATION)
        client.get_table(f"{PROJECT}.wellpulse_silver.daily_production")
        return client
    except Exception as exc:  # noqa: BLE001 - any auth/NotFound/import problem means "no lakehouse here"
        pytest.skip(f"BigQuery lakehouse unavailable ({type(exc).__name__}: {str(exc)[:120]})")


@pytest.fixture(scope="module")
def bq_client():
    return _bq_client_or_skip()


@pytest.fixture(scope="module")
def pq_repo():
    return ParquetRepository()


@pytest.fixture(scope="module")
def bq_repo(bq_client):
    from app.data_access.bigquery_repo import BigQueryRepository

    return BigQueryRepository(client=bq_client)


def _norm(obj):
    """JSON-normalise so NaN == NaN and dates/numpy scalars compare by value."""
    def default(o):
        if hasattr(o, "item"):
            return o.item()
        return str(o)

    def fix(o):
        if isinstance(o, float) and math.isnan(o):
            return "NaN"
        if isinstance(o, dict):
            return {k: fix(v) for k, v in o.items()}
        if isinstance(o, list):
            return [fix(v) for v in o]
        return o

    return json.loads(json.dumps(fix(json.loads(json.dumps(obj, default=default))), sort_keys=True))


# -- raw frame parity ----------------------------------------------------------------------------------
@pytest.mark.parametrize("attr", ["wells", "daily", "catalogue", "facilities", "field_master"])
def test_frames_identical(pq_repo, bq_repo, attr):
    pd.testing.assert_frame_equal(getattr(pq_repo, attr), getattr(bq_repo, attr), check_exact=True)


def test_per_well_tables_identical(pq_repo, bq_repo):
    assert set(pq_repo.per_well) == set(bq_repo.per_well)
    for wid in FIXTURE_WELLS:
        a, b = pq_repo.per_well[wid], bq_repo.per_well[wid]
        assert set(a) == set(b), wid
        for t in a:
            pd.testing.assert_frame_equal(a[t], b[t], check_exact=True, obj=f"{wid}.{t}")


# -- repository / REST parity (BDD F-15 S03) ------------------------------------------------------------
def test_list_wells_identical(pq_repo, bq_repo):
    assert _norm(pq_repo.list_wells()) == _norm(bq_repo.list_wells())


@pytest.mark.parametrize("wid", FIXTURE_WELLS)
def test_well_detail_and_history_identical(pq_repo, bq_repo, wid):
    assert _norm(pq_repo.get_well(wid)) == _norm(bq_repo.get_well(wid))
    for rng in ["30d", "1y", "5y"]:
        assert _norm(pq_repo.get_history(wid, rng)) == _norm(bq_repo.get_history(wid, rng)), rng


@pytest.mark.parametrize("field", FIELDS)
def test_field_infrastructure_identical(pq_repo, bq_repo, field):
    assert _norm(pq_repo.field_infrastructure(field)) == _norm(bq_repo.field_infrastructure(field))


def test_rest_routes_identical_with_bigquery_backend(pq_repo, bq_repo):
    """The API itself, served once from each backend (DATA_BACKEND=bigquery path)."""
    from fastapi.testclient import TestClient

    from app.main import app

    routes = ["/api/wells", "/api/wells/kpis", "/api/wells?field=Lakwa"]
    for wid in ["GK-129", "LKW-047", "LKM-061"]:
        routes += [f"/api/wells/{wid}", f"/api/wells/{wid}/history?range=1y", f"/api/wells/{wid}/workovers"]
    old = r._repo
    try:
        out = {}
        for name, repo in (("parquet", pq_repo), ("bigquery", bq_repo)):
            r._repo = repo
            with TestClient(app) as c:
                out[name] = {u: (c.get(u).status_code, c.get(u).json()) for u in routes}
    finally:
        r._repo = old
    for u in routes:
        assert out["parquet"][u][0] == out["bigquery"][u][0], u
        assert _norm(out["parquet"][u][1]) == _norm(out["bigquery"][u][1]), u


def test_queries_carry_pruning_predicates(bq_repo):
    assert len(bq_repo.daily) > 0  # ensure loaded
    daily = [q for q in bq_repo.queries if "daily_production" in q and "INFORMATION_SCHEMA" not in q]
    assert len(daily) == 3
    for q in daily:
        assert "production_date <= @as_of" in q and "field = @field" in q, q
    for q in bq_repo.queries:
        if "INFORMATION_SCHEMA" not in q:
            assert "_landing_folder = @folder" in q, q


# -- lakehouse gate checks (BDD F-15 S01) ---------------------------------------------------------------
def test_silver_row_counts_equal_parquet(bq_client):
    landing = settings.LANDING_DIR
    counts: dict[str, int] = {}
    for p in landing.glob("*/*.parquet"):
        counts[p.stem] = counts.get(p.stem, 0) + pq.read_metadata(p).num_rows
    sql = " UNION ALL ".join(
        f"SELECT '{t}' AS t, COUNT(*) AS n FROM `{PROJECT}.wellpulse_silver.{t}`" for t in sorted(counts))
    got = {row["t"]: row["n"] for row in bq_client.query(sql, location=LOCATION).result()}
    assert got == counts


def test_silver_daily_production_physical_design(bq_client):
    t = bq_client.get_table(f"{PROJECT}.wellpulse_silver.daily_production")
    assert t.time_partitioning is not None and t.time_partitioning.field == "production_date"
    assert t.clustering_fields == ["field", "well_id"]
    assert t.location == LOCATION
    for ds in ("wellpulse_bronze", "wellpulse_silver", "wellpulse_gold"):
        assert bq_client.get_dataset(f"{PROJECT}.{ds}").location == LOCATION


def test_gold_field_kpi_monthly_reconciles_to_repository(pq_repo, bq_client):
    d = pq_repo.daily.merge(pq_repo.wells[["well_id", "field"]], on="well_id")
    d["month"] = pd.to_datetime(d["production_date"]).dt.to_period("M").dt.to_timestamp().dt.date
    repo = d.groupby(["field", "month"]).agg(
        oil_bbl=("oil_rate_bopd", "sum"), water_bbl=("water_rate_bwpd", "sum"),
        gas_mscf=("gas_rate_mscfd", "sum"), days=("production_date", "nunique")).reset_index()
    repo["oil_bopd"] = repo["oil_bbl"] / repo["days"]
    gold = bq_client.query(
        f"SELECT field, month, oil_bbl, water_bbl, gas_mscf, days_in_period AS days, oil_bopd "
        f"FROM `{PROJECT}.wellpulse_gold.field_kpi_monthly`", location=LOCATION).result().to_arrow().to_pandas()
    m = repo.merge(gold, on=["field", "month"], how="outer", suffixes=("_repo", "_gold"), indicator=True)
    assert (m["_merge"] == "both").all(), m[m["_merge"] != "both"][["field", "month", "_merge"]]
    assert len(m) == 3 * 60  # 3 fields x 60 months (2021-10 .. 2026-09, Sept partial to AS_OF)
    for col in ["oil_bbl", "water_bbl", "gas_mscf", "oil_bopd"]:
        rel = (m[f"{col}_gold"] - m[f"{col}_repo"]).abs() / m[f"{col}_repo"].abs().clip(lower=1e-9)
        assert rel.max() <= 1e-3, (col, m.loc[rel.idxmax(), ["field", "month"]].to_dict(), rel.max())
    assert (m["days_repo"] == m["days_gold"]).all()
    assert gold["month"].max() == date(settings.AS_OF.year, settings.AS_OF.month, 1)
