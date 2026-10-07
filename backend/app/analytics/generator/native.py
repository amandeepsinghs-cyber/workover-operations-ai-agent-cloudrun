"""Native field run (Lakwa, Lakhmani): well_master → renewal simulation → fixtures → tables.

Streams (all ``np.random.default_rng([cfg.seed, stream, ...])``):
  1 well_master · 2 per-well params · 3 external events · 10+i well i simulation · 20 documents
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from app.analytics.generator.v030.supporting import generate_well_offsets

from .fields.base import FieldConfig
from .fixtures import (
    FIXTURE_WINDOW_DAYS,
    FORCED_HISTORY,
    script_fixture,
    scripted_cluster_events,
)
from .simulate import (
    DAILY_COLS,
    SimResult,
    WellSim,
    draw_external_events,
    draw_native_params,
)
from .wells_native import generate_native_well_master

GAP_COLS = ["wht_degc", "gl_inj_rate_mscfd", "gl_inj_pressure_kgcm2"]


def lkm090_offsets(wells: pd.DataFrame, cfg: FieldConfig) -> list[str]:
    fx = cfg.fixtures.get("LKM-090")
    if fx is None:
        return []
    me = wells[wells.well_id == fx.well_id].iloc[0]
    cand = wells[(wells.current_zone == me.current_zone) & (wells.well_id != fx.well_id)
                 & (wells.status == "ACTIVE") & (~wells.well_id.isin(list(cfg.fixtures)))].copy()
    cand["dist"] = np.hypot(cand.latitude - me.latitude, (cand.longitude - me.longitude) * 0.89)
    return cand.sort_values(["dist", "well_id"]).head(int(fx.params["n_offsets"]))["well_id"].tolist()


def run_native_field(cfg: FieldConfig, as_of: date) -> dict:
    start, end = cfg.start, cfg.end
    n = (end - start).days + 1
    as_idx = (as_of - start).days
    fw0 = as_idx - FIXTURE_WINDOW_DAYS
    wells = generate_native_well_master(cfg)
    params = draw_native_params(cfg, wells, np.random.default_rng([cfg.seed, 2]))
    ext = draw_external_events(cfg, n, start, np.random.default_rng([cfg.seed, 3]))
    ext = ext + scripted_cluster_events(cfg.field, start)
    offsets = lkm090_offsets(wells, cfg)
    res = SimResult()
    sims = {}
    for i, row in enumerate(wells.itertuples(index=False)):
        wid = row.well_id
        fx = cfg.fixtures.get(wid)
        special = fx is not None or wid in offsets
        sim = WellSim(cfg, row, params[wid], start, n, 0, np.random.default_rng([cfg.seed, 10, i]),
                      job_mode="native", ext_events=ext,
                      fixture_window_start=fw0 if special else None,
                      exempt_external_from=fw0 if special else None,
                      forced_jobs=FORCED_HISTORY.get(wid), allow_terminal=not special)
        sim.build()
        sim.overlay_setpoints()
        if fx is not None:
            script_fixture(sim, fx.kind, fx.params, as_idx)
        elif wid in offsets:
            script_fixture(sim, "RESERVOIR_DECLINE_OFFSET", cfg.fixtures["LKM-090"].params, as_idx)
        sim.overlay_external()
        sim.render(res)
        sims[wid] = sim
    return dict(wells=wells, res=res, sims=sims, offsets=offsets, n_days=n)


def native_tables(cfg: FieldConfig, run: dict) -> dict[str, pd.DataFrame]:
    wells, res = run["wells"], run["res"]
    cl = dict(zip(wells.well_id, wells.cluster_id))
    daily = pd.DataFrame(res.daily, columns=DAILY_COLS + GAP_COLS)
    daily["is_prepend"] = False
    tests = pd.DataFrame(res.tests)
    status = pd.DataFrame(res.status)
    wo = pd.DataFrame(res.workovers)
    for df in (daily, tests, status, wo):
        df.insert(1, "field", cfg.field)
        df.insert(2, "cluster_id", df["well_id"].map(cl))
    offsets = generate_well_offsets(wells)
    docs = native_document_index(cfg, wells, wo)
    return dict(well_master=wells, daily_production=daily, well_tests=tests, well_status_history=status,
                workover_history=wo, well_offsets=offsets, document_index=docs)


def native_document_index(cfg: FieldConfig, wells: pd.DataFrame, wo: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng([cfg.seed, 20])
    fl = cfg.field.lower()
    rows = []
    for r in wells.itertuples(index=False):
        rows.append(dict(doc_id=f"DOC-COMP-{r.well_id}", well_id=r.well_id, doc_type="COMPLETION_REPORT",
                         doc_date=r.completion_date,
                         gcs_uri=f"gs://well-workover-intervention-data/documents/{fl}/completion/{r.well_id}_completion.pdf",
                         title=f"Well Completion & CBL Report {r.well_id}",
                         has_text_layer=bool(r.completion_date.year > 2005)))
    for r in wo[wo.report_doc_id.notna()].itertuples(index=False):
        rows.append(dict(doc_id=r.report_doc_id, well_id=r.well_id, doc_type="WORKOVER_REPORT", doc_date=r.end_date,
                         gcs_uri=f"gs://well-workover-intervention-data/documents/{fl}/workover/{r.report_doc_id}.pdf",
                         title=f"{r.well_id} Workover Completion Report — {r.catalogue_job_code} ({r.end_date:%b %Y})",
                         has_text_layer=bool(rng.random() < 0.7)))
    return pd.DataFrame(rows)


def daterange(start: date, n: int) -> list[date]:
    return [start + timedelta(days=d) for d in range(n)]
