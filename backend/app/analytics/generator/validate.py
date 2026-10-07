"""Stage N data-contract validator (SDD §5.5 V-N1..V-N7, DC-010/DC-014, Gate N).

    uv run python -m app.analytics.generator.validate --field all
    uv run python -m app.analytics.generator.validate --compare-baseline tests/baseline/landing_v030

Exit code 0 = no violations, 1 = violations, 2 = missing data.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from app import settings

from .fields import FIELD_CONFIGS, resolve_field
from .geometry import point_in_polygon
from .native import lkm090_offsets

EXPECTED_WELLS = {"Geleki": 142, "Lakwa": 160, "Lakhmani": 110}
EXPECTED_CLUSTERS = {"Geleki": 3, "Lakwa": 3, "Lakhmani": 2}
GAP_TARGET = {"Lakwa": (-0.18, 0.03), "Lakhmani": (-0.06, 0.03), "Geleki": (0.0, 0.03)}
QTD = (date(2026, 7, 1), settings.AS_OF)
T12M = (settings.AS_OF - timedelta(days=364), settings.AS_OF)
FIELD_TABLES = ["well_master", "daily_production", "well_tests", "well_status_history", "workover_history",
                "well_offsets", "document_index", "operations_events", "casing_tally", "tubing_string",
                "perforation_intervals", "pressure_surveys", "formation_tops"]
ASSET_TABLES = ["job_catalogue", "mro_inventory", "rig_calendar", "field_master", "cluster_master",
                "facility_master", "field_targets"]
GELEKI_FROZEN = ["well_run", "draft_plan", "decision_log"]
BASELINE_FIELD_TABLES = ["well_master", "daily_production", "well_tests", "well_status_history", "workover_history",
                         "well_offsets", "document_index", "well_run", "draft_plan", "decision_log"]
BASELINE_ASSET_TABLES = ["job_catalogue", "mro_inventory", "rig_calendar"]
IC_MIN_ROWS = 30
CURRENCY_TOKENS = ("cost_usd", "_usd", "currency", "payback")


def load(landing: Path, folder: str, table: str) -> pd.DataFrame:
    return pd.read_parquet(landing / folder / f"{table}.parquet")


# ------------------------------------------------------------------------------------------------
# metrics shared with pin_targets
# ------------------------------------------------------------------------------------------------
def gap(landing: Path, field: str, window: tuple[date, date]) -> float:
    from .targets import gap_vs_target
    t = load(landing, "asset", "field_targets")
    d = load(landing, field.lower(), "daily_production")[["production_date", "oil_rate_bopd"]]
    return gap_vs_target(t[t.field == field], d, *window)


def status_days(status: pd.DataFrame, well: str, st: str, lo: date, hi: date) -> int:
    s = status[(status.well_id == well) & (status.status == st)]
    n = 0
    for r in s.itertuples(index=False):
        a = max(r.start_date, lo)
        b = min(r.end_date or hi, hi)
        n += max(0, (b - a).days + 1)
    return n


def lkw047_waits(landing: Path) -> dict:
    st = load(landing, "lakwa", "well_status_history")
    wo = load(landing, "lakwa", "workover_history")
    pump = wo[(wo.well_id == "LKW-047") & (wo.catalogue_job_code == "PUMP_OVERHAUL")].sort_values("start_date")
    job = pump.iloc[-1]
    lo = settings.AS_OF - timedelta(days=179)
    hi = job.start_date - timedelta(days=1)
    ev = load(landing, "lakwa", "operations_events")
    ev = ev[(ev.well_id == "LKW-047") & (ev.trigger_ref == job.workover_id)]
    ev_days = {t: int(((g.end_date - g.start_date).apply(lambda x: x.days) + 1).sum()) for t, g in ev.groupby("event_type")}
    return dict(workover_id=job.workover_id, job_start=job.start_date,
                wait_on_rig_days=status_days(st, "LKW-047", "WAITING_ON_RIG", lo, hi),
                wait_on_material_days=status_days(st, "LKW-047", "WAITING_ON_MATERIAL", lo, hi),
                events=ev_days)


def decline_pct(daily: pd.DataFrame, well: str, a: date, b: date, k: int = 14) -> float:
    d = daily[(daily.well_id == well) & daily.is_producing]
    pre = d[(d.production_date >= a - timedelta(days=k)) & (d.production_date < a)].oil_rate_bopd.mean()
    post = d[(d.production_date > b - timedelta(days=k)) & (d.production_date <= b)].oil_rate_bopd.mean()
    return float(post / pre - 1.0)


def lkm090_residuals(landing: Path) -> dict:
    cfg = FIELD_CONFIGS["Lakhmani"]
    wells = load(landing, "lakhmani", "well_master")
    daily = load(landing, "lakhmani", "daily_production")[["well_id", "production_date", "oil_rate_bopd", "is_producing"]]
    days = int(cfg.fixtures["LKM-090"].params["signature_days"])
    a, b = settings.AS_OF - timedelta(days=days - 1), settings.AS_OF
    me = decline_pct(daily, "LKM-090", a, b)
    offs = {w: decline_pct(daily, w, a, b) for w in lkm090_offsets(wells, cfg)}
    return dict(lkm090_decline=me, offsets=offs, max_abs_residual_pp=max(abs(v - me) for v in offs.values()) * 100)


def join_continuity(landing: Path) -> dict:
    d = load(landing, "geleki", "daily_production")[["well_id", "production_date", "oil_rate_bopd", "is_producing"]]
    j = date(2023, 10, 1)
    pre = d[(d.production_date >= j - timedelta(days=7)) & (d.production_date < j)]
    core = d[(d.production_date >= j) & (d.production_date < j + timedelta(days=7))]
    tot_pre = pre.groupby("production_date").oil_rate_bopd.sum().mean()
    tot_core = core.groupby("production_date").oil_rate_bopd.sum().mean()
    pw_pre = pre[pre.is_producing].oil_rate_bopd.mean()
    pw_core = core[core.is_producing].oil_rate_bopd.mean()
    return dict(field_total_ratio=float(tot_pre / tot_core - 1), per_producing_well_ratio=float(pw_pre / pw_core - 1))


def ic_counts(landing: Path) -> dict[str, int]:
    frames = [load(landing, f.lower(), "workover_history") for f in FIELD_CONFIGS]
    wo = pd.concat([f[["intervention_class", "is_censored"]] for f in frames])
    return wo[~wo.is_censored.astype(bool)].intervention_class.value_counts().sort_index().to_dict()


# ------------------------------------------------------------------------------------------------
# checks
# ------------------------------------------------------------------------------------------------
def check_field(landing: Path, field: str) -> list[str]:
    v: list[str] = []
    cfg = FIELD_CONFIGS[field]
    fl = field.lower()
    missing = [t for t in FIELD_TABLES + (GELEKI_FROZEN if field == "Geleki" else [])
               if not (landing / fl / f"{t}.parquet").exists()]
    if missing:
        return [f"{field}: missing tables {missing}"]
    wells = load(landing, fl, "well_master")
    daily = load(landing, fl, "daily_production")
    status = load(landing, fl, "well_status_history")
    wo = load(landing, fl, "workover_history")
    ev = load(landing, fl, "operations_events")
    fm = load(landing, "asset", "field_master").set_index("field")

    # V-N1 well counts, prefixes, clusters, boundary
    if len(wells) != EXPECTED_WELLS[field]:
        v.append(f"V-N1 {field}: {len(wells)} wells, expected {EXPECTED_WELLS[field]}")
    if not wells.well_id.str.startswith(cfg.prefix).all():
        v.append(f"V-N1 {field}: well ids without prefix {cfg.prefix}")
    if wells.cluster_id.nunique() != EXPECTED_CLUSTERS[field]:
        v.append(f"V-N1 {field}: {wells.cluster_id.nunique()} clusters, expected {EXPECTED_CLUSTERS[field]}")
    poly = [(lat, lon) for lon, lat in json.loads(fm.loc[field, "boundary_geojson"])["coordinates"][0]]
    outside = [w for w, la, lo in zip(wells.well_id, wells.latitude, wells.longitude) if not point_in_polygon(la, lo, poly)]
    if outside:
        v.append(f"V-N1 {field}: {len(outside)} wells outside boundary polygon")

    # DC-010 coverage: one row per well-day across the full window
    n_days = (settings.DATA_END - settings.DATA_START).days + 1
    cnt = daily.groupby("well_id").size()
    if not (cnt == n_days).all() or len(cnt) != len(wells):
        v.append(f"DC-010 {field}: well-day coverage not {n_days} for every well")
    if daily.production_date.min() != settings.DATA_START or daily.production_date.max() != settings.DATA_END:
        v.append(f"DC-010 {field}: window {daily.production_date.min()}..{daily.production_date.max()}")
    if daily.duplicated(["well_id", "production_date"]).any():
        v.append(f"DC-010 {field}: duplicate well-days")
    prod = daily[daily.is_producing]
    bal = (prod.liquid_rate_blpd - (prod.oil_rate_bopd + prod.water_rate_bwpd)).abs()
    if (bal > 0.15).any():
        v.append(f"DC-010 {field}: liquid != oil + water on {(bal > 0.15).sum()} rows")

    # DC-014 null-not-zero
    rate_cols = ["oil_rate_bopd", "water_rate_bwpd", "gas_rate_mscfd", "liquid_rate_blpd"]
    down = daily[~daily.is_producing]
    if down[rate_cols].notna().any().any():
        v.append(f"DC-014 {field}: {int(down[rate_cols].notna().any(axis=1).sum())} shut-in days with non-NULL rates")
    if prod[rate_cols].isna().any().any():
        v.append(f"DC-014 {field}: producing days with NULL rates")

    # V-N7 gap columns
    lift = dict(zip(wells.well_id, wells.lift_type))
    is_gl = daily.well_id.map(lift) == "GAS_LIFT"
    if daily.loc[~is_gl, ["gl_inj_rate_mscfd", "gl_inj_pressure_kgcm2"]].notna().any().any():
        v.append(f"V-N7 {field}: gl_inj_* non-NULL on non-gas-lift wells")
    if daily.loc[~daily.is_producing, ["wht_degc", "gl_inj_rate_mscfd", "gl_inj_pressure_kgcm2"]].notna().any().any():
        v.append(f"V-N7 {field}: gap columns non-NULL on non-producing days")
    if daily.loc[daily.is_producing & is_gl, ["gl_inj_rate_mscfd", "gl_inj_pressure_kgcm2"]].isna().any().any():
        v.append(f"V-N7 {field}: gl_inj_* NULL on producing gas-lift days")
    if daily.loc[daily.is_producing, "wht_degc"].isna().any():
        v.append(f"V-N7 {field}: wht_degc NULL on producing days")
    if "gor_scf_bbl" not in daily.columns:
        v.append(f"V-N7 {field}: gor_scf_bbl missing")
    ps = load(landing, fl, "pressure_surveys").sort_values(["well_id", "survey_date"])
    gaps = ps.groupby("well_id").survey_date.apply(lambda s: s.diff().dropna().apply(lambda x: x.days)).astype(int)
    if len(gaps) and ((gaps < 365) | (gaps > 731)).any():
        v.append(f"V-N7 {field}: pressure survey interval outside [12, 24] months")
    ft = load(landing, fl, "formation_tops")
    if ft.well_id.nunique() != len(wells):
        v.append(f"V-N7 {field}: formation_tops missing wells")

    # V-N2 every event overlaps >= 1 down/degraded day
    degraded = daily[(~daily.is_producing) | (daily.runtime_fraction < 0.999)][["well_id", "production_date"]]
    deg_by_well = {w: set(g.production_date) for w, g in degraded.groupby("well_id")}
    bad = 0
    for r in ev.itertuples(index=False):
        days = deg_by_well.get(r.well_id, set())
        d, ok = r.start_date, False
        end = r.end_date if r.end_date is not None else settings.DATA_END
        while d <= end:
            if d in days:
                ok = True
                break
            d += timedelta(days=1)
        bad += not ok
    if bad:
        v.append(f"V-N2 {field}: {bad} operations_events without a down/degraded day")
    if not ev.event_id.is_unique:
        v.append(f"V-N2 {field}: duplicate event_id")
    if (ev.responsible_function.str.contains(r"\b(?:Mr|Ms|Shri)\b", regex=True)).any():
        v.append(f"V-N2 {field}: responsible_function names a person")

    # status episodes contiguous, non-overlapping (frozen v0.3.0 core exempt: it has known gaps / zero-length
    # episodes that V-N5 forbids us to change; the prepend → core join is checked)
    for w, g in status.groupby("well_id"):
        if field == "Geleki":
            core = g[~g.is_prepend.astype(bool)]
            g = g[g.is_prepend.astype(bool)]
            if len(g) and len(core) and core.start_date.min() != g.end_date.max() + timedelta(days=1):
                v.append(f"DC-030 Geleki: {w} prepend does not join the core")
        g = g.sort_values("start_date")
        ends = g.end_date.tolist()
        starts = g.start_date.tolist()
        for i in range(1, len(g)):
            if ends[i - 1] is None or starts[i] != ends[i - 1] + timedelta(days=1):
                v.append(f"DC-030 {field}: {w} status episodes not contiguous")
                break

    # K-1 labels
    nc = wo[~wo.is_censored.astype(bool)]
    if nc.catalogue_job_code.isna().any() or nc.intervention_class.isna().any():
        v.append(f"K-1 {field}: non-censored workovers without catalogue_job_code / intervention_class")
    if "job_code" not in wo.columns:
        v.append(f"K-1 {field}: job_code dropped")
    if not wo.workover_id.is_unique:
        v.append(f"DC-040 {field}: duplicate workover_id")

    # currency (D-1): no currency columns in well-keyed tables
    for t in FIELD_TABLES:
        cols = [c for c in load(landing, fl, t).columns if any(tok in c.lower() for tok in CURRENCY_TOKENS)]
        if cols:
            v.append(f"D-1 {field}.{t}: currency columns {cols}")

    # gap vs target
    tgt, tol = GAP_TARGET[field]
    g = gap(landing, field, QTD)
    if abs(g - tgt) > tol + 1e-9:
        v.append(f"F-09 {field}: QTD gap {g:+.1%} outside {tgt:+.0%} ± {tol * 100:.0f} pp")

    # V-N4 fixtures / V-N6 continuity
    if field == "Lakwa":
        w = lkw047_waits(landing)
        if (w["wait_on_rig_days"], w["wait_on_material_days"]) != (41, 12):
            v.append(f"V-N4 LKW-047: waits {w['wait_on_rig_days']}/{w['wait_on_material_days']} != 41/12")
        st88 = status[(status.well_id == "LKW-088") & (status.start_date >= settings.AS_OF - timedelta(days=179))]
        if not ((st88.status == "SHUT_IN") & (st88.reason_code == "POWER_OUTAGE")).any():
            v.append("V-N4 LKW-088: no GGS-II power outages in the 180-day window")
        if (st88.status.isin(["WAITING_ON_RIG", "UNDER_WORKOVER", "WAITING_ON_MATERIAL"])).any():
            v.append("V-N4 LKW-088: mechanical downtime inside the 180-day window")
    if field == "Lakhmani":
        r = lkm090_residuals(landing)
        if r["max_abs_residual_pp"] > 5.0:
            v.append(f"V-N4 LKM-090: offset residual {r['max_abs_residual_pp']:.1f} pp > 5 pp")
        d61 = daily[(daily.well_id == "LKM-061") & daily.is_producing]
        a = settings.AS_OF - timedelta(days=74)
        pre = d61[(d61.production_date < a) & (d61.production_date >= a - timedelta(days=30))]
        post = d61[(d61.production_date > settings.AS_OF - timedelta(days=14)) & (d61.production_date <= settings.AS_OF)]
        if not (post.gl_inj_rate_mscfd.mean() > pre.gl_inj_rate_mscfd.mean() * 1.15
                and post.gl_inj_pressure_kgcm2.mean() < pre.gl_inj_pressure_kgcm2.mean() - 2.0):
            v.append("V-N4 LKM-061: no GLV failure signature (inj rate up, inj pressure down)")
    if field == "Geleki":
        jc = join_continuity(landing)
        for k, x in jc.items():
            if abs(x) > 0.03:
                v.append(f"V-N6 Geleki: join discontinuity {x:+.1%} ({k})")
        pre = daily[daily.is_prepend]
        if pre.production_date.min() != date(2021, 10, 1) or pre.production_date.max() != date(2023, 9, 30):
            v.append("V-N6 Geleki: prepend window wrong")
        core = daily[~daily.is_prepend]
        act = wells[wells.status == "ACTIVE"].well_id
        frac = 100 * (~core[core.well_id.isin(act)].is_producing).mean()
        if abs(frac - 16.3) > 1.5:      # AT-092 applies to the frozen core only
            v.append(f"AT-092 Geleki core: FRACTION_DOWN_ACTIVE {frac:.2f}%")
    return v


def check_asset(landing: Path) -> list[str]:
    v: list[str] = []
    missing = [t for t in ASSET_TABLES if not (landing / "asset" / f"{t}.parquet").exists()]
    if missing:
        return [f"asset: missing tables {missing}"]
    cat = load(landing, "asset", "job_catalogue")
    if "GLV_REPLACE" not in set(cat.job_code):
        v.append("K-2: GLV_REPLACE missing from job_catalogue")
    if "cost_band" not in cat.columns or not set(cat.cost_band) <= {"LOW", "MED", "HIGH"}:
        v.append("D-1: job_catalogue.cost_band missing / invalid")
    counts = ic_counts(landing)
    for i in range(1, 16):
        ic = f"IC-{i:02d}"
        if counts.get(ic, 0) < IC_MIN_ROWS:
            v.append(f"IC: {ic} has {counts.get(ic, 0)} non-censored rows < {IC_MIN_ROWS}")
    ft = load(landing, "asset", "field_targets")
    if ft.duplicated(["field", "month"]).any():
        v.append("field_targets: duplicate (field, month)")
    fac = load(landing, "asset", "facility_master")
    if set(fac.field) != set(FIELD_CONFIGS):
        v.append("facility_master: not every field has facilities")
    return v


def check_no_wall_clock() -> list[str]:
    """V-N3 (static part): no wall-clock reads in the generator package."""
    v = []
    root = Path(__file__).parent
    for p in sorted(root.rglob("*.py")):
        tree = ast.parse(p.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in ("now", "today", "utcnow", "time_ns"):
                v.append(f"V-N3: wall-clock call .{node.attr}() in {p.relative_to(root)}:{node.lineno}")
    return v


def compare_baseline(landing: Path, baseline: Path) -> list[str]:
    """V-N5: every v0.3.0 column and row of Geleki is identical to the frozen baseline."""
    v = []
    for t in BASELINE_FIELD_TABLES + BASELINE_ASSET_TABLES:
        folder = "asset" if t in BASELINE_ASSET_TABLES else "geleki"
        base = pd.read_parquet(baseline / f"{t}.parquet")
        new = load(landing, folder, t)
        miss = [c for c in base.columns if c not in new.columns]
        if miss:
            v.append(f"V-N5 {t}: missing baseline columns {miss}")
            continue
        if "is_prepend" in new.columns:
            new = new[~new.is_prepend.astype(bool)]
        sub = new[list(base.columns)].iloc[: len(base)].reset_index(drop=True)
        if len(new) < len(base) or not sub.equals(base):
            v.append(f"V-N5 {t}: v0.3.0 rows/columns differ from baseline")
        else:
            print(f"  V-N5 {t}: {len(base)} rows x {len(base.columns)} cols identical")
    return v


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--field", default=None)
    ap.add_argument("--compare-baseline", default=None)
    ap.add_argument("--landing", default=str(settings.LANDING_DIR))
    a = ap.parse_args(argv)
    landing = Path(a.landing)
    if not landing.exists():
        print(f"no landing data at {landing}; run generate first", file=sys.stderr)
        return 2
    v: list[str] = []
    if a.compare_baseline:
        v += compare_baseline(landing, Path(a.compare_baseline))
    if a.field or not a.compare_baseline:
        fields = list(FIELD_CONFIGS) if (a.field or "all").lower() == "all" else [resolve_field(a.field)]
        if None in fields:
            print(f"unknown field {a.field}", file=sys.stderr)
            return 2
        v += check_no_wall_clock()
        v += check_asset(landing)
        for f in fields:
            v += check_field(landing, f)
            print(f"  {f}: QTD gap {gap(landing, f, QTD):+.1%}, trailing-12m gap {gap(landing, f, T12M):+.1%}")
        if "Lakwa" in fields:
            print(f"  LKW-047: {lkw047_waits(landing)}")
        if "Lakhmani" in fields:
            r = lkm090_residuals(landing)
            print(f"  LKM-090 decline {r['lkm090_decline']:+.1%}, max offset residual {r['max_abs_residual_pp']:.1f} pp")
        if "Geleki" in fields:
            print(f"  Geleki join: {join_continuity(landing)}")
        print(f"  IC counts: {ic_counts(landing)}")
    print(f"{len(v)} violations")
    for x in v:
        print(f"  [X] {x}")
    return 1 if v else 0


if __name__ == "__main__":
    raise SystemExit(main())
