"""WellPulse v0.4 data generator (Stage N; SDD §5).

    uv run python -m app.analytics.generator.generate --field all --start 2021-10-01 --end 2026-09-30

Writes parquet to ``settings.LANDING_DIR`` (or ``--out``):
    <out>/<field_lower>/<table>.parquet   well-keyed tables per field
    <out>/asset/<table>.parquet           job_catalogue, mro_inventory, rig_calendar, field_master,
                                          cluster_master, facility_master, field_targets

Geleki = frozen v0.3.0 core (2023-10-01 → 2026-09-30, rows/columns unchanged, V-N5) + 24-month prepend
(seed 4242) + append-only columns. Lakwa / Lakhmani are simulated natively. Fully deterministic: no
wall-clock reads; every random draw is seeded; two runs produce byte-identical parquet (V-N3).
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from app import settings
from app.analytics.generator.v030.production import simulate_production_history
from app.analytics.generator.v030.supporting import (
    generate_decision_log,
    generate_document_index,
    generate_draft_plan_table,
    generate_mro_inventory,
    generate_rig_calendar,
    generate_well_offsets,
    generate_well_run,
)
from app.analytics.generator.v030.wells import generate_well_master

from .catalogue import build_job_catalogue, label_geleki_workovers
from .construction import (
    generate_casing_tally,
    generate_perforation_intervals,
    generate_tubing_string,
)
from .fields import FIELD_CONFIGS, resolve_field
from .fields.base import FieldConfig
from .fields.geleki import GELEKI, PREPEND_SEED
from .formation_tops import generate_formation_tops
from .hierarchy import cluster_master, facility_master, field_master, nearest_cluster
from .native import native_tables, run_native_field
from .operations_events import assemble, derive_core_events
from .prepend import core_start_waits, prepend_frames, run_prepend
from .pressure_surveys import generate_pressure_surveys
from .targets import build_field_targets
from .telemetry import core_gap_columns

V030_START, V030_END = date(2023, 10, 1), date(2026, 9, 30)
LINEAGE_AT = "2026-09-23T16:00:00Z"
V030_BATCH = "BATCH-GELEKI-20260923-V1"
LINEAGE_COLS = ["_ingested_at", "_source_system", "_source_file", "_batch_id"]


def v030_lineage(df: pd.DataFrame, table: str) -> pd.DataFrame:
    df = df.copy()
    df["_ingested_at"] = LINEAGE_AT
    df["_source_system"] = "GENERATOR"
    df["_source_file"] = f"gs://well-workover-intervention-data/landing/generator/2026/09/23/{table}.parquet"
    df["_batch_id"] = V030_BATCH
    return df


def v04_lineage(df: pd.DataFrame, table: str, batch: str, folder: str) -> pd.DataFrame:
    df = df.copy()
    df["_ingested_at"] = LINEAGE_AT
    df["_source_system"] = "GENERATOR"
    df["_source_file"] = f"gs://well-workover-intervention-data/landing/v04/{folder}/{table}.parquet"
    df["_batch_id"] = batch
    return df


def _per_well_concat(prepend: pd.DataFrame, core: pd.DataFrame, well_order: list[str]) -> pd.DataFrame:
    """Prepend rows before core rows for each well; core rows keep their original relative order."""
    pos = {w: i for i, w in enumerate(well_order)}
    p = prepend.copy()
    c = core.copy()
    p["__k"], c["__k"] = 0, 1
    p["__o"], c["__o"] = np.arange(len(p)), np.arange(len(c))
    df = pd.concat([p, c], ignore_index=True)
    df["__w"] = df["well_id"].map(pos)
    df = df.sort_values(["__w", "__k", "__o"], kind="mergesort").drop(columns=["__w", "__k", "__o"])
    return df.reset_index(drop=True)


def construction_tables(cfg: FieldConfig, wells: pd.DataFrame, wo: pd.DataFrame, daily: pd.DataFrame,
                        start: date, end: date) -> dict[str, pd.DataFrame]:
    s = cfg.seed * 100
    done = wo[wo["outcome"] != "IN_PROGRESS"]
    wo_c = done[["workover_id", "well_id", "start_date", "end_date", "catalogue_job_code", "is_censored"]]
    d_c = daily[["well_id", "production_date", "liquid_rate_blpd", "is_producing"]]
    return dict(
        casing_tally=generate_casing_tally(wells, s + 31),
        tubing_string=generate_tubing_string(wells, wo_c, s + 32),
        perforation_intervals=generate_perforation_intervals(wells, wo_c, s + 33),
        formation_tops=generate_formation_tops(wells, s + 34),
        pressure_surveys=generate_pressure_surveys(wells, d_c, start, end, s + 35),
    )


def build_geleki(start: date, end: date) -> tuple[dict[str, pd.DataFrame], pd.Series, set]:
    wells = generate_well_master(142)
    v030_params: dict = {}
    daily, tests, status, wo = simulate_production_history(wells, V030_START, V030_END, params_out=v030_params)
    order = wells["well_id"].tolist()
    cl = dict(zip(order, nearest_cluster(GELEKI, wells)))
    wells_c = wells.copy()
    wells_c["cluster_id"] = wells_c["well_id"].map(cl)

    pre = prepend_frames(run_prepend(wells_c, v030_params, core_start_waits(status)))
    PB, FOLD = "BATCH-GELEKI-PREPEND-V04", "geleki"

    def core_tag(df, table):
        out = v030_lineage(df, table)
        out["field"] = "Geleki"
        out["cluster_id"] = out["well_id"].map(cl)
        out["is_prepend"] = False
        return out

    def pre_tag(df, table, cols):
        out = df.drop(columns=["is_prepend"], errors="ignore").copy()
        out = v04_lineage(out, table, PB, FOLD)
        out["field"] = "Geleki"
        out["cluster_id"] = out["well_id"].map(cl)
        out["is_prepend"] = True
        return out[cols]

    # daily_production
    d_core = core_tag(daily, "daily_production")
    gap = core_gap_columns(daily, wells)
    for c in gap.columns:
        d_core[c] = gap[c].to_numpy()
    d_all = _per_well_concat(pre_tag(pre["daily_production"], "daily_production", list(d_core.columns)), d_core, order)

    t_core = core_tag(tests, "well_tests")
    t_all = _per_well_concat(pre_tag(pre["well_tests"], "well_tests", list(t_core.columns)), t_core, order)

    s_core = core_tag(status, "well_status_history")
    s_all = _per_well_concat(pre_tag(pre["well_status_history"], "well_status_history", list(s_core.columns)),
                             s_core, order)

    wo_core = core_tag(label_geleki_workovers(wo), "workover_history")
    wo_all = _per_well_concat(pre_tag(pre["workover_history"], "workover_history", list(wo_core.columns)),
                              wo_core, order)

    wm = v030_lineage(wells, "well_master")
    wm["cluster_id"] = wm["well_id"].map(cl)

    docs = v030_lineage(generate_document_index(wells), "document_index")
    known = set(docs["doc_id"])
    extra = []
    for r in wo_all[wo_all["report_doc_id"].notna()].itertuples(index=False):
        if r.report_doc_id in known:
            continue
        known.add(r.report_doc_id)
        extra.append(dict(doc_id=r.report_doc_id, well_id=r.well_id, doc_type="WORKOVER_REPORT", doc_date=r.end_date,
                          gcs_uri=f"gs://well-workover-intervention-data/documents/geleki/workover/{r.report_doc_id}.pdf",
                          title=f"{r.well_id} Workover Completion Report — {r.catalogue_job_code} ({r.end_date:%b %Y})",
                          has_text_layer=True))
    docs = pd.concat([docs, v04_lineage(pd.DataFrame(extra), "document_index", "BATCH-GELEKI-DOCS-V04", FOLD)],
                     ignore_index=True)

    well_run = generate_well_run(wells, daily, run_date=date(2026, 9, 23))
    ev = assemble([derive_core_events(status, "Geleki", cl).assign(), _tag_events(pre["events"], "Geleki", True)],
                  "Geleki")

    wells_cons = wells_c.copy()
    tables = dict(
        well_master=wm, daily_production=d_all, well_tests=t_all, well_status_history=s_all,
        workover_history=wo_all, well_offsets=v030_lineage(generate_well_offsets(wells), "well_offsets"),
        document_index=docs, well_run=v030_lineage(well_run, "well_run"),
        draft_plan=v030_lineage(generate_draft_plan_table(well_run), "draft_plan"),
        decision_log=v030_lineage(generate_decision_log(), "decision_log"),
        operations_events=v04_lineage(ev, "operations_events", "BATCH-GELEKI-V04", FOLD),
    )
    for k, v in construction_tables(GELEKI, wells_cons, wo_all, d_all, start, end).items():
        tables[k] = v04_lineage(v, k, "BATCH-GELEKI-V04", FOLD)

    # potential: prepend (simulated) + core (frozen v0.3.0 Arps curves)
    idx = pd.date_range(start, end)
    pre_pot = pd.Series(0.0, index=pd.date_range(start, V030_START - pd.Timedelta(days=1)))
    res_pot = pre["potential"]
    for arr in res_pot.values():
        pre_pot += arr
    t = np.arange((V030_END - V030_START).days + 1, dtype=float)
    core_pot = np.zeros_like(t)
    for wid, p in v030_params.items():
        if p["is_idle"]:
            continue
        core_pot += p["q_i"] / (1.0 + p["b"] * p["d_i_day"] * t) ** (1.0 / p["b"])
    pot = pd.concat([pre_pot, pd.Series(core_pot, index=pd.date_range(V030_START, V030_END))]).reindex(idx)
    idle = set(wells.loc[wells["status"] == "IDLE", "well_id"])
    return tables, pot, idle


def _tag_events(ev: pd.DataFrame, field: str, is_prepend: bool) -> pd.DataFrame:
    if ev is None or not len(ev):
        return ev
    out = ev.copy()
    out["field"] = field
    out["is_prepend"] = is_prepend
    return out


def build_native(cfg: FieldConfig, start: date) -> tuple[dict[str, pd.DataFrame], pd.Series, set]:
    run = run_native_field(cfg, settings.AS_OF)
    tb = native_tables(cfg, run)
    batch, fold = f"BATCH-{cfg.field.upper()}-V04", cfg.field.lower()
    ev = assemble([pd.DataFrame(run["res"].events)], cfg.field)
    tb["operations_events"] = ev
    tb.update(construction_tables(cfg, tb["well_master"], tb["workover_history"], tb["daily_production"],
                                  cfg.start, cfg.end))
    tables = {k: v04_lineage(v, k, batch, fold) for k, v in tb.items()}
    pot = pd.Series(np.sum(list(run["res"].potential.values()), axis=0), index=pd.date_range(cfg.start, cfg.end))
    idle = set(tb["well_master"].loc[tb["well_master"]["status"] == "IDLE", "well_id"])
    return tables, pot, idle


def write_tables(out: Path, folder: str, tables: dict[str, pd.DataFrame]) -> None:
    d = out / folder
    d.mkdir(parents=True, exist_ok=True)
    for name in sorted(tables):
        tables[name].to_parquet(d / f"{name}.parquet", index=False)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--field", default="all")
    ap.add_argument("--start", default=str(settings.DATA_START))
    ap.add_argument("--end", default=str(settings.DATA_END))
    ap.add_argument("--out", default=str(settings.LANDING_DIR))
    a = ap.parse_args(argv)
    start, end = date.fromisoformat(a.start), date.fromisoformat(a.end)
    if (start, end) != (settings.DATA_START, settings.DATA_END):
        print(f"ERROR: the v0.4 window is fixed at {settings.DATA_START}..{settings.DATA_END} (D-2, V-N5)",
              file=sys.stderr)
        return 2
    if a.field.lower() == "all":
        fields = list(FIELD_CONFIGS)
    else:
        f = resolve_field(a.field)
        if f is None:
            print(f"ERROR: unknown field {a.field}", file=sys.stderr)
            return 2
        fields = [f]
    out = Path(a.out)
    wells_by_field, targets = {}, []
    for f in fields:
        cfg = FIELD_CONFIGS[f]
        tables, pot, idle = build_geleki(start, end) if f == "Geleki" else build_native(cfg, start)
        write_tables(out, f.lower(), tables)
        wells_by_field[f] = tables["well_master"]
        targets.append(build_field_targets(f, pot, tables["daily_production"], idle))
        print(f"{f}: " + ", ".join(f"{k}={len(v)}" for k, v in sorted(tables.items())))
    if a.field.lower() == "all":
        cfgs = [FIELD_CONFIGS[f] for f in fields]
        cat = build_job_catalogue()
        cat = pd.concat([v030_lineage(cat.iloc[:28], "job_catalogue"),
                         v04_lineage(cat.iloc[28:], "job_catalogue", "BATCH-ASSET-V04", "asset")], ignore_index=True)
        asset = dict(
            job_catalogue=cat,
            mro_inventory=v030_lineage(generate_mro_inventory(), "mro_inventory"),
            rig_calendar=v030_lineage(generate_rig_calendar(), "rig_calendar"),
            field_master=v04_lineage(field_master(cfgs, wells_by_field), "field_master", "BATCH-ASSET-V04", "asset"),
            cluster_master=v04_lineage(cluster_master(cfgs, wells_by_field), "cluster_master", "BATCH-ASSET-V04", "asset"),
            facility_master=v04_lineage(facility_master(cfgs), "facility_master", "BATCH-ASSET-V04", "asset"),
            field_targets=v04_lineage(pd.concat(targets, ignore_index=True), "field_targets", "BATCH-ASSET-V04", "asset"),
        )
        write_tables(out, "asset", asset)
        print("asset: " + ", ".join(f"{k}={len(v)}" for k, v in sorted(asset.items())))
    print(f"PREPEND_SEED={PREPEND_SEED} out={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
