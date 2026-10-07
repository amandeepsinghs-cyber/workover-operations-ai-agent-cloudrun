"""Fact builders: one ``DocSpec`` per document, every value read from the landing tables.

This module is the ONLY place numbers for the corpus are produced. Templates
see formatted strings (``spec.facts`` / ``spec.tables``) and may not compute or
type numbers themselves (see ``ir.py``).

Conventions for formatted values (documented in the slot catalogue):
- rates / depths / pressures: one decimal with thousands separator ("2,435.7");
- counts and day numbers: integers ("41");
- percentages: one decimal with a percent sign ("17.6%");
- dates: ISO ``YYYY-MM-DD``; booleans: "Yes"/"No";
- missing values: ``ir.MISSING`` ("not recorded").
"""
from __future__ import annotations

import hashlib
import math
import warnings
from dataclasses import dataclass
from datetime import date, timedelta
from functools import cached_property, lru_cache
from pathlib import Path
from typing import Any, Iterable, Iterator

import numpy as np
import pandas as pd

from app.analytics.docs_pdf.ir import MISSING, DocSpec, TableData, freeze_spec
from app.settings import AS_OF, LANDING_DIR

warnings.filterwarnings("ignore", category=RuntimeWarning, message="Mean of empty slice")

FIELDS = {"Geleki": "geleki", "Lakwa": "lakwa", "Lakhmani": "lakhmani"}
FIELD_CODES = {"Geleki": "GK", "Lakwa": "LKW", "Lakhmani": "LKM"}
DOC_TYPES = {
    "D01": "Well completion report",
    "D02": "Workover / intervention report",
    "D03": "Daily workover report",
    "D04": "Wellbore schematic and casing / tubing tally",
    "D05": "Cement bond log summary",
    "D06": "Chemical treatment log",
    "D07": "Well test and pressure survey report",
    "D08": "Failure root-cause analysis note",
    "D09": "Field study / annual review",
    "D10": "Monthly field production report",
    "D11": "Standard operating procedure",
}
TYPE_DIRS = {t: t.replace("D0", "D") for t in DOC_TYPES}  # D01 -> D1 (folder / API alias)
HERO_WELLS = ("GK-129", "LKW-047", "LKW-112", "LKM-090")
AVG_WINDOW_DAYS = 30  # pre/post production averaging window (methodology parameter, printed as a fact)
DECLINE_WINDOW_DAYS = 180  # trailing window for decline comparisons in D7 and wait-day counts in D2
REPORTED_OUTCOMES = ("SUCCESS", "PARTIAL", "FAILED")
IC_SOP_CLASSES = tuple(f"IC-{i:02d}" for i in range(1, 15))
WAX_SCALE_CLASSES = ("IC-04", "IC-05")
WATER_INTEGRITY_CODES = ("CEMENT_SQUEEZE", "POLYMER_GEL", "STRADDLE_PACKER", "ZONE_TRANSFER", "CASING_REPAIR")


def norm_type(t: str) -> str:
    """'D1' / 'd01' / 'D01' -> 'D01'."""
    t = t.strip().upper()
    if not t.startswith("D"):
        raise ValueError(t)
    return f"D{int(t[1:]):02d}"


# --------------------------------------------------------------------------- formatting
def _isnan(v: Any) -> bool:
    if v is None:
        return True
    try:
        return bool(pd.isna(v))
    except (TypeError, ValueError):
        return False


def f_num(v: Any, nd: int = 1) -> str:
    if _isnan(v):
        return MISSING
    return f"{float(v):,.{nd}f}"


def f_int(v: Any) -> str:
    if _isnan(v):
        return MISSING
    return f"{int(round(float(v))):,d}"


def f_pct(v: Any, nd: int = 1) -> str:
    if _isnan(v):
        return MISSING
    return f"{float(v):,.{nd}f}%"


def f_signed_pct(v: Any, nd: int = 1) -> str:
    if _isnan(v):
        return MISSING
    return f"{float(v):+,.{nd}f}%"


def f_signed(v: Any, nd: int = 1) -> str:
    if _isnan(v):
        return MISSING
    return f"{float(v):+,.{nd}f}"


def f_pp(v: Any, nd: int = 1) -> str:
    if _isnan(v):
        return MISSING
    return f"{float(v):+,.{nd}f} pp"


def f_date(v: Any) -> str:
    if _isnan(v):
        return MISSING
    if isinstance(v, (date, pd.Timestamp)):
        return pd.Timestamp(v).date().isoformat()
    return str(v)[:10]


def f_bool(v: Any) -> str:
    if _isnan(v):
        return MISSING
    return "Yes" if bool(v) else "No"


def f_text(v: Any) -> str:
    if _isnan(v) or str(v).strip() == "":
        return MISSING
    return str(v)


def to_date(v: Any) -> date | None:
    if _isnan(v):
        return None
    return pd.Timestamp(v).date()


def pct_change(new: float, old: float) -> float:
    if _isnan(new) or _isnan(old) or old == 0:
        return float("nan")
    return (new - old) / old * 100.0


class Facts:
    """Accumulates (formatted, raw, source) triples for one document."""

    def __init__(self):
        self.facts: dict[str, str] = {}
        self.raw: dict[str, Any] = {}
        self.sources: dict[str, str] = {}
        self.tables: dict[str, TableData] = {}

    def add(self, name: str, raw: Any, fmt=f_text, source: str = "") -> None:
        self.facts[name] = fmt(raw)
        self.raw[name] = None if _isnan(raw) else (raw.item() if isinstance(raw, np.generic) else raw)
        if source:
            self.sources[name] = source

    def missing(self, *names: str) -> None:
        """Declare optional slots that have no data for this document (prints MISSING)."""
        for n in names:
            if n not in self.facts:
                self.add(n, None, source="no matching row")

    def table(self, name: str, df: pd.DataFrame, fmts: dict[str, Any], source: str) -> None:
        rows = []
        for rec in df.to_dict("records"):
            rows.append({k: fn(rec.get(k)) for k, fn in fmts.items()})
        self.tables[name] = TableData(columns=tuple(fmts), rows=tuple(rows), source=source)
        self.sources[f"table:{name}"] = source

    def spec(self, **kw) -> DocSpec:
        return freeze_spec(facts=self.facts, raw=self.raw, sources=self.sources, tables=self.tables, **kw)


# --------------------------------------------------------------------------- data access
def _read(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    return df.drop(columns=[c for c in df.columns if c.startswith("_")])


@lru_cache(maxsize=1)
def asset_data() -> "AssetData":
    return AssetData(LANDING_DIR / "asset")


class AssetData:
    def __init__(self, root: Path):
        self.root = root
        self.job_catalogue = _read(root / "job_catalogue.parquet")
        self.field_targets = _read(root / "field_targets.parquet")
        self.facility_master = _read(root / "facility_master.parquet")
        self.cluster_master = _read(root / "cluster_master.parquet")
        self.field_master = _read(root / "field_master.parquet")
        self.jobs = self.job_catalogue.set_index("job_code")

    def job(self, code: str | None) -> dict:
        if code is None or code not in self.jobs.index:
            return {}
        return self.jobs.loc[code].to_dict()

    @cached_property
    def ic_labels(self) -> dict[str, str]:
        import yaml

        cfg = Path(__file__).resolve().parents[1] / "config" / "ic_map.yaml"
        data = yaml.safe_load(cfg.read_text())
        return {k: v["label"] for k, v in data["classes"].items()}


@lru_cache(maxsize=3)
def field_data(field: str) -> "FieldData":
    return FieldData(field)


class FieldData:
    def __init__(self, field: str):
        self.field = field
        root = LANDING_DIR / FIELDS[field]
        self.wm = _read(root / "well_master.parquet").set_index("well_id", drop=False)
        self.wo = _read(root / "workover_history.parquet")
        self.wo["ts"] = pd.to_datetime(self.wo["start_date"])
        self.wo["te"] = pd.to_datetime(self.wo["end_date"])
        self.wo = self.wo.sort_values(["well_id", "ts", "workover_id"]).reset_index(drop=True)
        self.cas = _read(root / "casing_tally.parquet")
        self.tub = _read(root / "tubing_string.parquet")
        self.perf = _read(root / "perforation_intervals.parquet")
        self.ftops = _read(root / "formation_tops.parquet")
        self.ps = _read(root / "pressure_surveys.parquet")
        self.wt = _read(root / "well_tests.parquet")
        self.wt["td"] = pd.to_datetime(self.wt["test_date"])
        self.wsh = _read(root / "well_status_history.parquet")
        self.wsh["ts"] = pd.to_datetime(self.wsh["start_date"])
        self.wsh["te"] = pd.to_datetime(self.wsh["end_date"]).fillna(pd.Timestamp(AS_OF))
        self.ev = _read(root / "operations_events.parquet")
        self.ev["ts"] = pd.to_datetime(self.ev["start_date"])
        self.ev["te"] = pd.to_datetime(self.ev["end_date"]).fillna(self.ev["ts"])
        self.docidx = _read(root / "document_index.parquet")
        self.offsets = _read(root / "well_offsets.parquet")

    @cached_property
    def dp(self) -> pd.DataFrame:
        root = LANDING_DIR / FIELDS[self.field]
        cols = ["well_id", "production_date", "oil_rate_bopd", "water_rate_bwpd", "gas_rate_mscfd",
                "liquid_rate_blpd", "water_cut_pct", "gor_scf_bbl", "thp_kgcm2", "chp_kgcm2", "wht_degc",
                "runtime_hours", "is_producing", "downtime_reason", "gl_inj_rate_mscfd", "spm"]
        df = pd.read_parquet(root / "daily_production.parquet", columns=cols)
        df["production_date"] = pd.to_datetime(df["production_date"])
        return df.sort_values(["well_id", "production_date"])

    @cached_property
    def dp_by_well(self) -> dict[str, pd.DataFrame]:
        return {w: g.set_index("production_date") for w, g in self.dp.groupby("well_id", sort=False)}

    def window_mean(self, well: str, start: pd.Timestamp, end: pd.Timestamp, col: str, producing_only=True) -> float:
        g = self.dp_by_well.get(well)
        if g is None:
            return float("nan")
        s = g.loc[start:end]
        if producing_only:
            s = s[s["is_producing"].astype(bool)]
        v = s[col].dropna()
        return float(v.mean()) if len(v) else float("nan")

    def window_means(self, well: str, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, float]:
        """Means of every numeric column over producing days in [start, end] (one slice)."""
        g = self.dp_by_well.get(well)
        if g is None or end < start:
            return {}
        s = g.loc[start:end]
        s = s[s["is_producing"].astype(bool)]
        if not len(s):
            return {}
        return s.mean(numeric_only=True).to_dict()

    def producing_days(self, well: str, start: pd.Timestamp, end: pd.Timestamp) -> int:
        g = self.dp_by_well.get(well)
        if g is None:
            return 0
        return int(g.loc[start:end]["is_producing"].astype(bool).sum())

    @cached_property
    def wo_by_well(self) -> dict[str, pd.DataFrame]:
        return {w: g for w, g in self.wo.groupby("well_id", sort=False)}

    @cached_property
    def wsh_by_well(self) -> dict[str, pd.DataFrame]:
        return {w: g for w, g in self.wsh.groupby("well_id", sort=False)}

    @cached_property
    def tub_by_well(self) -> dict[str, pd.DataFrame]:
        return {w: g for w, g in self.tub.groupby("well_id", sort=False)}

    @cached_property
    def ev_by_well(self) -> dict[str, pd.DataFrame]:
        return {w: g for w, g in self.ev.groupby("well_id", sort=False)}

    @cached_property
    def docidx_by_id(self) -> dict[str, dict]:
        return {r["doc_id"]: r for r in self.docidx.to_dict("records")}

    def facility_for_cluster(self, cluster: str) -> dict:
        fm = asset_data().facility_master
        for r in fm[fm["field"] == self.field].to_dict("records"):
            if cluster in str(r.get("serviced_cluster_ids") or "").split(","):
                return r
        return {}


# --------------------------------------------------------------------------- shared fact groups
CASING_FMT = {"string_type": f_text, "od_in": lambda v: f_num(v, 3), "weight_ppf": f_num, "grade": f_text,
              "top_m": f_num, "shoe_m": f_num, "cement_top_m": f_num, "install_date": f_date}
TUBING_FMT = {"seq": f_int, "component": f_text, "od_in": lambda v: f_num(v, 3), "length_m": f_num,
              "top_m": f_num, "install_date": f_date, "workover_id": f_text}
PERF_FMT = {"zone": f_text, "top_m": f_num, "bottom_m": f_num, "spf": f_int, "perf_date": f_date, "status": f_text}
FTOPS_FMT = {"formation": f_text, "top_md_m": f_num, "bottom_md_m": f_num, "lithology": f_text}
JOBHIST_FMT = {"workover_id": f_text, "start_date": f_date, "end_date": f_date, "catalogue_job_code": f_text,
               "intervention_class": f_text, "failure_code": f_text, "rig_days": f_num, "pre_job_oil_bopd": f_num,
               "post_job_oil_bopd": f_num, "outcome": f_text, "run_life_days": f_int}


def _base(f: Facts, doc_id: str, doc_type: str, field: str, well: str | None, doc_date: str, title: str,
          cluster: str | None = None) -> None:
    f.add("doc_id", doc_id, source="corpus")
    f.add("doc_type", doc_type, source="corpus")
    f.add("doc_type_name", DOC_TYPES[doc_type], source="corpus")
    f.add("doc_title", title, source="corpus")
    f.add("doc_date", doc_date, f_date, source="corpus")
    f.add("field", field, source="field_master.field")
    f.add("asset", "Assam", source="field_master.asset")
    f.add("as_of", AS_OF, f_date, source="settings.AS_OF")
    if well:
        f.add("well_id", well, source="well_master.well_id")
    if cluster:
        f.add("cluster_id", cluster, source="well_master.cluster_id")


def _well_facts(f: Facts, fd: FieldData, well: str) -> dict:
    w = fd.wm.loc[well].to_dict()
    src = "well_master"
    for col, fmt in [("spud_date", f_date), ("completion_date", f_date), ("current_zone", f_text),
                     ("perf_top_m", f_num), ("perf_bottom_m", f_num), ("total_depth_md_m", f_num),
                     ("total_depth_tvd_m", f_num), ("lift_type", f_text), ("plunger_diameter_in", lambda v: f_num(v, 2)),
                     ("stroke_length_in", f_num), ("pump_setting_depth_m", f_num), ("rod_string_grade", f_text),
                     ("pump_type", f_text), ("casing_vented", f_bool), ("tubing_size_in", lambda v: f_num(v, 3)),
                     ("casing_size_in", lambda v: f_num(v, 3)), ("latitude", lambda v: f_num(v, 5)),
                     ("longitude", lambda v: f_num(v, 5))]:
        f.add(col, w.get(col), fmt, f"{src}.{col}")
    f.add("well_status", w.get("status"), f_text, f"{src}.status")
    f.add("perf_interval_m", (w.get("perf_bottom_m") or np.nan) - (w.get("perf_top_m") or np.nan), f_num,
          "well_master.perf_bottom_m - perf_top_m")
    fac = fd.facility_for_cluster(w.get("cluster_id"))
    f.add("facility_id", fac.get("facility_id"), f_text, "facility_master.facility_id")
    f.add("facility_name", fac.get("name"), f_text, "facility_master.name")
    return w


def _construction(f: Facts, fd: FieldData, well: str, w: dict, as_of: str | None = None) -> None:
    """Construction facts; ``as_of`` (ISO date) drops rows installed after the document date."""
    cas = fd.cas[fd.cas.well_id == well].sort_values("od_in", ascending=False)
    if as_of:
        cas = cas[cas.install_date.astype(str) <= as_of]
    f.table("casing", cas, CASING_FMT, "casing_tally")
    prod = cas[cas.string_type == "PRODUCTION"]
    p = prod.iloc[0].to_dict() if len(prod) else {}
    f.add("prod_casing_od_in", p.get("od_in"), lambda v: f_num(v, 3), "casing_tally.od_in[PRODUCTION]")
    f.add("prod_casing_weight_ppf", p.get("weight_ppf"), f_num, "casing_tally.weight_ppf[PRODUCTION]")
    f.add("prod_casing_grade", p.get("grade"), f_text, "casing_tally.grade[PRODUCTION]")
    f.add("prod_casing_shoe_m", p.get("shoe_m"), f_num, "casing_tally.shoe_m[PRODUCTION]")
    f.add("cement_top_m", p.get("cement_top_m"), f_num, "casing_tally.cement_top_m[PRODUCTION]")
    f.add("casing_install_date", p.get("install_date"), f_date, "casing_tally.install_date[PRODUCTION]")
    f.add("n_casing_strings", len(cas), f_int, "count(casing_tally)")
    cover = (w.get("perf_top_m") or np.nan) - (p.get("cement_top_m") if p else np.nan)
    f.add("cement_above_perf_m", cover, f_num, "well_master.perf_top_m - casing_tally.cement_top_m")
    cemented = (p.get("shoe_m") or np.nan) - (p.get("cement_top_m") if p else np.nan) if p else np.nan
    f.add("cemented_length_m", cemented, f_num, "casing_tally.shoe_m - cement_top_m")
    sc = cas[cas.string_type == "SURFACE"]
    f.add("surface_casing_shoe_m", sc.iloc[0]["shoe_m"] if len(sc) else np.nan, f_num, "casing_tally.shoe_m[SURFACE]")

    tub = fd.tub[fd.tub.well_id == well].sort_values("seq")
    if as_of:  # historical documents (D1 as-completed, D5 log) must not show a later string
        tub = tub[tub.install_date.astype(str) <= as_of]
    f.table("tubing", tub, TUBING_FMT, "tubing_string")
    f.add("tubing_install_date", tub["install_date"].max() if len(tub) else None, f_date, "tubing_string.install_date")
    f.add("tubing_workover_id", tub["workover_id"].dropna().iloc[0] if tub["workover_id"].notna().any() else None,
          f_text, "tubing_string.workover_id")
    pump = tub[tub.component == "PUMP"]
    f.add("pump_top_m", pump.iloc[0]["top_m"] if len(pump) else np.nan, f_num, "tubing_string.top_m[PUMP]")
    anchor = tub[tub.component.str.contains("ANCHOR", na=False)]
    f.add("anchor_top_m", anchor.iloc[0]["top_m"] if len(anchor) else np.nan, f_num, "tubing_string.top_m[ANCHOR]")
    f.add("n_tubing_components", len(tub), f_int, "count(tubing_string)")

    perf = fd.perf[fd.perf.well_id == well].sort_values("top_m")
    if as_of:
        perf = perf[perf.perf_date.astype(str) <= as_of]
    f.table("perfs", perf, PERF_FMT, "perforation_intervals")
    f.add("n_perf_intervals", len(perf), f_int, "count(perforation_intervals)")
    f.add("n_open_perfs", int((perf.status == "OPEN").sum()), f_int, "count(perforation_intervals[OPEN])")
    ft = fd.ftops[fd.ftops.well_id == well].sort_values("top_md_m")
    f.table("formations", ft, FTOPS_FMT, "formation_tops")
    f.add("n_formations", len(ft), f_int, "count(formation_tops)")
    zone = ft[ft.formation == w.get("current_zone")]
    f.add("zone_top_md_m", zone.iloc[0]["top_md_m"] if len(zone) else np.nan, f_num, "formation_tops.top_md_m[current_zone]")
    f.add("zone_lithology", zone.iloc[0]["lithology"] if len(zone) else None, f_text, "formation_tops.lithology[current_zone]")


def _job_facts(f: Facts, fd: FieldData, r: dict) -> None:
    a = asset_data()
    src = "workover_history"
    for col, fmt in [("workover_id", f_text), ("start_date", f_date), ("end_date", f_date), ("job_code", f_text),
                     ("catalogue_job_code", f_text), ("intervention_class", f_text), ("failure_code", f_text),
                     ("is_rigless", f_bool), ("rig_id", f_text), ("rig_days", f_num), ("pre_job_oil_bopd", f_num),
                     ("post_job_oil_bopd", f_num), ("uplift_bopd", f_num), ("outcome", f_text),
                     ("run_life_days", f_int), ("is_censored", f_bool), ("damage_reset_frac", lambda v: f_num(v, 2))]:
        f.add(col, r.get(col), fmt, f"{src}.{col}")
    job = a.job(r.get("catalogue_job_code"))
    f.add("job_name", job.get("job_name"), f_text, "job_catalogue.job_name")
    f.add("job_category", job.get("category"), f_text, "job_catalogue.category")
    f.add("mechanism_code", job.get("mechanism_code"), f_text, "job_catalogue.mechanism_code")
    f.add("selection_evidence", job.get("selection_evidence"), f_text, "job_catalogue.selection_evidence")
    f.add("requires_rig", job.get("requires_rig"), f_bool, "job_catalogue.requires_rig")
    f.add("equipment", job.get("equipment"), f_text, "job_catalogue.equipment")
    f.add("est_days", job.get("est_days"), f_num, "job_catalogue.est_days")
    f.add("cost_band", job.get("cost_band"), f_text, "job_catalogue.cost_band")
    f.add("sop_doc_id", job.get("sop_doc_id"), f_text, "job_catalogue.sop_doc_id")
    f.add("ic_label", a.ic_labels.get(r.get("intervention_class")), f_text, "ic_map.yaml label")
    rd, ed = r.get("rig_days"), job.get("est_days")
    f.add("rig_days_over_plan", (rd - ed) if not (_isnan(rd) or _isnan(ed)) else np.nan, f_num,
          "workover_history.rig_days - job_catalogue.est_days")
    duration = (r["te"] - r["ts"]).days + 1 if not _isnan(r.get("te")) else np.nan
    f.add("calendar_days", duration, f_int, "workover_history.end_date - start_date + 1")


def _prod_context(f: Facts, fd: FieldData, well: str, start: pd.Timestamp, end: pd.Timestamp | None) -> None:
    """Pre/post averages from daily_production around a job (window AVG_WINDOW_DAYS)."""
    n = AVG_WINDOW_DAYS
    f.add("window_days", n, f_int, "facts.AVG_WINDOW_DAYS (averaging window parameter)")
    pre_s, pre_e = start - pd.Timedelta(days=n), start - pd.Timedelta(days=1)
    pre_m = fd.window_means(well, pre_s, pre_e)
    post_m: dict[str, float] = {}
    if end is not None and not _isnan(end) and end + pd.Timedelta(days=1) <= pd.Timestamp(AS_OF):
        post_m = fd.window_means(well, end + pd.Timedelta(days=1), min(end + pd.Timedelta(days=n), pd.Timestamp(AS_OF)))
    for col, nm, fmt in [("oil_rate_bopd", "oil", f_num), ("water_cut_pct", "wc", f_pct), ("gor_scf_bbl", "gor", f_int),
                         ("thp_kgcm2", "thp", f_num), ("chp_kgcm2", "chp", f_num), ("wht_degc", "wht", f_num),
                         ("liquid_rate_blpd", "liquid", f_num), ("gas_rate_mscfd", "gas", f_num)]:
        pre = pre_m.get(col, float("nan"))
        post = post_m.get(col, float("nan"))
        f.add(f"pre_{nm}_avg", pre, fmt, f"daily_production.{col} mean [start-{n}d, start-1d] producing days")
        f.add(f"post_{nm}_avg", post, fmt, f"daily_production.{col} mean [end+1d, end+{n}d] producing days")
        if nm in ("oil", "wc", "thp", "wht"):
            delta = post - pre if not (_isnan(post) or _isnan(pre)) else float("nan")
            f.add(f"delta_{nm}", delta, f_pp if nm == "wc" else f_signed, f"post_{nm}_avg - pre_{nm}_avg")
    f.add("pre_producing_days", fd.producing_days(well, pre_s, pre_e), f_int, "count(daily_production.is_producing) pre window")


def _status_days(fd: FieldData, well: str, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, int]:
    w = fd.wsh_by_well.get(well, fd.wsh.iloc[0:0])
    s = w[(w.te >= start) & (w.ts <= end)]
    out: dict[str, int] = {}
    for r in s.itertuples():
        a, b = max(r.ts, start), min(r.te, end)
        days = (b - a).days + 1
        if days > 0:
            out[r.status] = out.get(r.status, 0) + days
    return out


def _history(f: Facts, fd: FieldData, well: str, before: pd.Timestamp | None = None, name="job_history", limit=8) -> pd.DataFrame:
    h = fd.wo_by_well.get(well, fd.wo.iloc[0:0])
    h = h[h.outcome.isin(REPORTED_OUTCOMES + ("NO_ACTION", "IN_PROGRESS"))]
    if before is not None:
        h = h[h.ts < before]
    h = h.sort_values("ts").tail(limit)
    f.table(name, h, JOBHIST_FMT, "workover_history")
    return h


# --------------------------------------------------------------------------- per-type builders
def build_d01(fd: FieldData) -> Iterator[DocSpec]:
    for well in fd.wm.index:
        doc_id = f"DOC-COMP-{well}"
        land = fd.docidx_by_id.get(doc_id, {})
        title = land.get("title") or f"Well Completion & CBL Report {well}"
        w = fd.wm.loc[well].to_dict()
        f = Facts()
        _base(f, doc_id, "D01", fd.field, well, w["completion_date"], title, w["cluster_id"])
        _well_facts(f, fd, well)
        _construction(f, fd, well, w, as_of=f_date(w["completion_date"]))
        f.add("drilling_days", (to_date(w["completion_date"]) - to_date(w["spud_date"])).days, f_int,
              "well_master.completion_date - spud_date")
        perf = fd.perf[(fd.perf.well_id == well)]
        first = perf.sort_values("perf_date").head(1)
        f.add("initial_perf_date", first.iloc[0]["perf_date"] if len(first) else None, f_date, "perforation_intervals.perf_date")
        f.add("initial_spf", first.iloc[0]["spf"] if len(first) else np.nan, f_int, "perforation_intervals.spf")
        yield f.spec(doc_id=doc_id, doc_type="D01", field=fd.field, well_id=well, doc_date=f_date(w["completion_date"]),
                     title=title, meta={"legacy_doc_type": land.get("doc_type")})


def _wo_rows(fd: FieldData) -> list[dict]:
    rows = fd.wo[fd.wo.outcome.isin(REPORTED_OUTCOMES)]
    return rows.to_dict("records")


def _d2_doc_id(r: dict) -> str:
    return r.get("report_doc_id") or f"DOC-WO-{r['workover_id'][3:]}"


def build_d02(fd: FieldData) -> Iterator[DocSpec]:
    for r in _wo_rows(fd):
        well = r["well_id"]
        doc_id = _d2_doc_id(r)
        land = fd.docidx_by_id.get(doc_id, {})
        ddate = land.get("doc_date") or f_date(r["end_date"])
        title = land.get("title") or f"{well} Workover Completion Report — {r['catalogue_job_code']}"
        f = Facts()
        _base(f, doc_id, "D02", fd.field, well, ddate, title, r["cluster_id"])
        w = _well_facts(f, fd, well)
        _job_facts(f, fd, r)
        _prod_context(f, fd, well, r["ts"], r["te"])
        win0 = r["ts"] - pd.Timedelta(days=DECLINE_WINDOW_DAYS)
        sd = _status_days(fd, well, win0, r["ts"] - pd.Timedelta(days=1))
        f.add("lookback_days", DECLINE_WINDOW_DAYS, f_int, "facts.DECLINE_WINDOW_DAYS (look-back parameter)")
        f.add("wait_on_rig_days", sd.get("WAITING_ON_RIG", 0), f_int, "well_status_history WAITING_ON_RIG days in look-back")
        f.add("wait_on_material_days", sd.get("WAITING_ON_MATERIAL", 0), f_int, "well_status_history WAITING_ON_MATERIAL days in look-back")
        f.add("shut_in_days", sd.get("SHUT_IN", 0), f_int, "well_status_history SHUT_IN days in look-back")
        wsh = fd.wsh_by_well.get(well, fd.wsh.iloc[0:0])
        wsh = wsh[wsh.workover_id == r["workover_id"]]
        f.add("deferred_bbl", wsh["deferred_bbl"].sum() if len(wsh) else np.nan, f_int, "sum(well_status_history.deferred_bbl[workover_id])")
        h = fd.wo_by_well[well]
        prev = h[(h.ts < r["ts"]) & h.outcome.isin(REPORTED_OUTCOMES)].tail(1)
        if len(prev):
            p = prev.iloc[0]
            f.add("prev_workover_id", p["workover_id"], f_text, "workover_history.workover_id[previous]")
            f.add("prev_job_code", p["catalogue_job_code"], f_text, "workover_history.catalogue_job_code[previous]")
            f.add("prev_end_date", p["end_date"], f_date, "workover_history.end_date[previous]")
            f.add("prev_outcome", p["outcome"], f_text, "workover_history.outcome[previous]")
            f.add("days_since_prev", (r["ts"] - p["te"]).days, f_int, "start_date - previous end_date")
        nxt = h[(h.ts > r["ts"]) & h.outcome.isin(REPORTED_OUTCOMES)].head(1)
        if len(nxt):
            n = nxt.iloc[0]
            f.add("next_workover_id", n["workover_id"], f_text, "workover_history.workover_id[next]")
            f.add("next_job_code", n["catalogue_job_code"], f_text, "workover_history.catalogue_job_code[next]")
            f.add("next_start_date", n["start_date"], f_date, "workover_history.start_date[next]")
        f.missing("prev_workover_id", "prev_job_code", "prev_end_date", "prev_outcome", "days_since_prev",
                  "next_workover_id", "next_job_code", "next_start_date")
        n_prior = int((h[h.ts < r["ts"]].outcome.isin(REPORTED_OUTCOMES)).sum())
        f.add("n_prior_jobs", n_prior, f_int, "count(workover_history) before this job")
        tub = fd.tub_by_well.get(well, fd.tub.iloc[0:0])
        tub = tub[tub.workover_id == r["workover_id"]].sort_values("seq")
        f.table("tubing_installed", tub, TUBING_FMT, "tubing_string[workover_id]")
        _history(f, fd, well, before=r["ts"])
        f.add("n_rig_days_reported", math.ceil(r["rig_days"]) if not r["is_rigless"] and r["rig_days"] > 0 else 0, f_int,
              "ceil(workover_history.rig_days) = number of D3 daily reports")
        yield f.spec(doc_id=doc_id, doc_type="D02", field=fd.field, well_id=well, doc_date=f_date(ddate), title=title,
                     meta={"workover_id": r["workover_id"], "intervention_class": r.get("intervention_class"),
                           "job_code": r.get("catalogue_job_code"), "legacy_doc_type": land.get("doc_type"),
                           "outcome": r.get("outcome")})


def _phase(day: int, total: int) -> str:
    if total <= 1:
        return "SINGLE_DAY"
    if day == 1:
        return "RIG_UP"
    if day == total:
        return "RIG_DOWN"
    return "MAIN"


def build_d03(fd: FieldData) -> Iterator[DocSpec]:
    ev = fd.ev
    for r in _wo_rows(fd):
        if r["is_rigless"] or _isnan(r["rig_days"]) or r["rig_days"] <= 0:
            continue
        well = r["well_id"]
        total = int(math.ceil(r["rig_days"]))
        job = asset_data().job(r.get("catalogue_job_code"))
        wev = fd.ev_by_well.get(well, ev.iloc[0:0])
        wsh_w = fd.wsh_by_well.get(well, fd.wsh.iloc[0:0])
        for day in range(1, total + 1):
            d = r["ts"] + pd.Timedelta(days=day - 1)
            if d.date() > AS_OF:
                break
            doc_id = f"DWR-{r['workover_id'][3:]}-D{day:02d}"
            title = f"{well} Daily Workover Report — {r['catalogue_job_code']} day {day} of {total}"
            f = Facts()
            _base(f, doc_id, "D03", fd.field, well, d.date(), title, r["cluster_id"])
            for col, fmt in [("workover_id", f_text), ("start_date", f_date), ("catalogue_job_code", f_text),
                             ("intervention_class", f_text), ("failure_code", f_text), ("rig_id", f_text),
                             ("rig_days", f_num), ("pre_job_oil_bopd", f_num)]:
                f.add(col, r.get(col), fmt, f"workover_history.{col}")
            f.add("job_name", job.get("job_name"), f_text, "job_catalogue.job_name")
            f.add("job_category", job.get("category"), f_text, "job_catalogue.category")
            f.add("equipment", job.get("equipment"), f_text, "job_catalogue.equipment")
            f.add("est_days", job.get("est_days"), f_num, "job_catalogue.est_days")
            f.add("sop_doc_id", job.get("sop_doc_id"), f_text, "job_catalogue.sop_doc_id")
            f.add("report_date", d.date(), f_date, "workover_history.start_date + day - 1")
            f.add("day_no", day, f_int, "day index within workover_history.rig_days")
            f.add("total_days", total, f_int, "ceil(workover_history.rig_days)")
            f.add("days_remaining", total - day, f_int, "total_days - day_no")
            f.add("phase_code", _phase(day, total), f_text, "facts._phase(day_no, total_days)")
            f.add("over_plan", "Yes" if day > (job.get("est_days") or 0) else "No", f_text,
                  "day_no > job_catalogue.est_days")
            f.add("pump_setting_depth_m", fd.wm.loc[well, "pump_setting_depth_m"], f_num, "well_master.pump_setting_depth_m")
            f.add("perf_top_m", fd.wm.loc[well, "perf_top_m"], f_num, "well_master.perf_top_m")
            f.add("lift_type", fd.wm.loc[well, "lift_type"], f_text, "well_master.lift_type")
            st = wsh_w[(wsh_w.ts <= d) & (wsh_w.te >= d)]
            f.add("well_status_today", st.iloc[0]["status"] if len(st) else None, f_text, "well_status_history.status")
            today = wev[(wev.ts <= d) & (wev.te >= d)]
            f.table("events_today", today.assign(start_date=today["start_date"], end_date=today["end_date"]),
                    {"event_type": f_text, "factor_class": f_text, "responsible_function": f_text,
                     "start_date": f_date, "end_date": f_date}, "operations_events")
            f.add("n_events_today", len(today), f_int, "count(operations_events) on report_date")
            yield f.spec(doc_id=doc_id, doc_type="D03", field=fd.field, well_id=well, doc_date=f_date(d), title=title,
                         meta={"workover_id": r["workover_id"], "intervention_class": r.get("intervention_class"),
                               "job_code": r.get("catalogue_job_code")})


def build_d04(fd: FieldData) -> Iterator[DocSpec]:
    for well in fd.wm.index:
        w = fd.wm.loc[well].to_dict()
        tub = fd.tub[fd.tub.well_id == well]
        ddate = max([d for d in [w["completion_date"], tub["install_date"].max() if len(tub) else None] if d])
        ddate = min(f_date(ddate), AS_OF.isoformat())
        doc_id = f"SCH-{well}"
        title = f"Wellbore Schematic & Casing/Tubing Tally {well}"
        f = Facts()
        _base(f, doc_id, "D04", fd.field, well, ddate, title, w["cluster_id"])
        _well_facts(f, fd, well)
        _construction(f, fd, well, w)
        yield f.spec(doc_id=doc_id, doc_type="D04", field=fd.field, well_id=well, doc_date=ddate, title=title, meta={})


def build_d05(fd: FieldData) -> Iterator[DocSpec]:
    """CBL summary for the subset of wells with water-control / integrity jobs + hero wells.

    The log is dated at the start of the well's most recent water-control / integrity workover (a
    pre-remedial diagnostic log); hero wells without such jobs use the completion date; a legacy
    CBL in the landing document_index (GK-129, 1998) replaces the generated one. Only history
    before the log date is shown, so no document refers to a later event.
    """
    wo = fd.wo
    wi = wo[wo.catalogue_job_code.isin(WATER_INTEGRITY_CODES) & wo.outcome.isin(REPORTED_OUTCOMES)]
    flagged = set(wi.well_id) | {w for w in HERO_WELLS if w in fd.wm.index}
    for well in sorted(flagged):
        w = fd.wm.loc[well].to_dict()
        legacy = [d for d in fd.docidx_by_id.values() if d["well_id"] == well and str(d["doc_id"]).startswith("DOC-CBL-")]
        cas = fd.cas[(fd.cas.well_id == well) & (fd.cas.string_type == "PRODUCTION")]
        jobs = wi[wi.well_id == well].sort_values("ts")
        trigger = None
        if legacy:
            land = legacy[0]
            doc_id, ddate, title = land["doc_id"], land["doc_date"], land["title"]
            date_src = "document_index.doc_date"
        else:
            land = {}
            if len(jobs):
                trigger = jobs.iloc[-1]
                ddate = trigger["start_date"]
                date_src = "workover_history.start_date[latest water-control / integrity job]"
            else:
                ddate = cas.iloc[0]["install_date"] if len(cas) else w["completion_date"]
                date_src = "casing_tally.install_date[PRODUCTION]"
            doc_id = f"CBL-{well}-{str(ddate)[:4]}"
            title = f"Cement Bond Log Summary {well} ({str(ddate)[:4]})"
        f = Facts()
        _base(f, doc_id, "D05", fd.field, well, ddate, title, w["cluster_id"])
        _well_facts(f, fd, well)
        _construction(f, fd, well, w, as_of=f_date(ddate))
        f.add("log_date", ddate, f_date, date_src)
        f.add("log_bottom_m", cas.iloc[0]["shoe_m"] if len(cas) else np.nan, f_num, "casing_tally.shoe_m[PRODUCTION]")
        f.add("trigger_workover_id", trigger["workover_id"] if trigger is not None else None, f_text,
              "workover_history.workover_id[job the log was run for]")
        f.add("trigger_job_code", trigger["catalogue_job_code"] if trigger is not None else None, f_text,
              "workover_history.catalogue_job_code[job the log was run for]")
        h = jobs[jobs.ts < pd.Timestamp(ddate)]
        f.table("water_jobs", h, JOBHIST_FMT, "workover_history[water-control / integrity jobs before log_date]")
        f.add("n_water_jobs", len(h), f_int, "count(water-control / integrity jobs before log_date)")
        n_failed = int((h.outcome == "FAILED").sum())
        f.add("n_water_jobs_failed", n_failed, f_int, "count(... outcome = FAILED)")
        cover = f.raw.get("cement_above_perf_m")
        remark = "micro-annulus" in str(land.get("title", "")).lower()
        # Categorical interpretation derived from data (no invented amplitude numbers):
        if cover is None or cover <= 0:
            assess, basis = "POOR", "CEMENT_TOP_BELOW_TOP_PERFORATION"
        elif n_failed > 0:
            assess, basis = "QUESTIONABLE", "PRIOR_FAILED_WATER_CONTROL_JOB"
        elif remark:
            assess, basis = "QUESTIONABLE", "LOG_REMARK_MICRO_ANNULUS"
        else:
            assess, basis = "ADEQUATE", "CEMENT_ABOVE_PERFORATIONS_NO_PRIOR_FAILURE"
        f.add("isolation_assessment", assess, f_text,
              "rule: cement_above_perf_m <= 0 -> POOR; prior failed water/integrity job or logged micro-annulus "
              "remark (document_index.title) -> QUESTIONABLE; else ADEQUATE")
        f.add("assessment_basis", basis, f_text, "which branch of the isolation_assessment rule applied")
        yield f.spec(doc_id=doc_id, doc_type="D05", field=fd.field, well_id=well, doc_date=f_date(ddate), title=title,
                     meta={"legacy_doc_type": land.get("doc_type"),
                           "workover_id": trigger["workover_id"] if trigger is not None else None})


def build_d06(fd: FieldData) -> Iterator[DocSpec]:
    for r in _wo_rows(fd):
        if r.get("intervention_class") not in WAX_SCALE_CLASSES:
            continue
        well = r["well_id"]
        doc_id = f"CHEM-{r['workover_id'][3:]}"
        title = f"{well} Chemical Treatment Log — {r['catalogue_job_code']}"
        f = Facts()
        _base(f, doc_id, "D06", fd.field, well, r["end_date"], title, r["cluster_id"])
        _well_facts(f, fd, well)
        _job_facts(f, fd, r)
        _prod_context(f, fd, well, r["ts"], r["te"])
        h = fd.wo_by_well[well]
        prior = h[(h.ts < r["ts"]) & (h.intervention_class == r["intervention_class"]) & h.outcome.isin(REPORTED_OUTCOMES)]
        f.table("prior_treatments", prior.tail(8), JOBHIST_FMT, "workover_history[same intervention_class, earlier]")
        f.add("n_prior_treatments", len(prior), f_int, "count(prior treatments of same class)")
        f.add("days_since_last_treatment", (r["ts"] - prior.iloc[-1]["te"]).days if len(prior) else np.nan, f_int,
              "start_date - last prior treatment end_date")
        yield f.spec(doc_id=doc_id, doc_type="D06", field=fd.field, well_id=well, doc_date=f_date(r["end_date"]), title=title,
                     meta={"workover_id": r["workover_id"], "intervention_class": r.get("intervention_class"),
                           "job_code": r.get("catalogue_job_code")})


def _decline(fd: FieldData, well: str, end: pd.Timestamp) -> float:
    n = AVG_WINDOW_DAYS
    a = fd.window_mean(well, end - pd.Timedelta(days=DECLINE_WINDOW_DAYS), end - pd.Timedelta(days=DECLINE_WINDOW_DAYS - n), "oil_rate_bopd")
    b = fd.window_mean(well, end - pd.Timedelta(days=n), end, "oil_rate_bopd")
    return pct_change(b, a)


def build_d07(fd: FieldData) -> Iterator[DocSpec]:
    ps = fd.ps.sort_values(["well_id", "survey_date"])
    for well, g in ps.groupby("well_id"):
        prev = None
        wt = fd.wt[fd.wt.well_id == well].sort_values("td")
        offs = fd.offsets[fd.offsets.well_id == well].sort_values("rank")
        for r in g.to_dict("records"):
            sd = pd.Timestamp(r["survey_date"])
            doc_id = f"WT-{r['survey_id'][3:]}"
            title = f"{well} Well Test & Pressure Survey Report ({f_date(sd)})"
            f = Facts()
            _base(f, doc_id, "D07", fd.field, well, sd.date(), title, r["cluster_id"])
            _well_facts(f, fd, well)
            for col, fmt in [("survey_id", f_text), ("survey_date", f_date), ("sbhp_kgcm2", f_num), ("fbhp_kgcm2", f_num),
                             ("pi_bpd_per_kgcm2", lambda v: f_num(v, 3)), ("fluid_level_m", f_num), ("datum_tvd_m", f_num)]:
                f.add(col, r.get(col), fmt, f"pressure_surveys.{col}")
            f.add("drawdown_kgcm2", r["sbhp_kgcm2"] - r["fbhp_kgcm2"], f_num, "pressure_surveys.sbhp - fbhp")
            if prev is not None:
                f.add("prev_survey_date", prev["survey_date"], f_date, "pressure_surveys.survey_date[previous]")
                f.add("prev_sbhp_kgcm2", prev["sbhp_kgcm2"], f_num, "pressure_surveys.sbhp_kgcm2[previous]")
                f.add("sbhp_change_kgcm2", r["sbhp_kgcm2"] - prev["sbhp_kgcm2"], lambda v: f"{v:+,.1f}" if not _isnan(v) else MISSING,
                      "sbhp - previous sbhp")
            f.missing("prev_survey_date", "prev_sbhp_kgcm2", "sbhp_change_kgcm2")
            prev = r
            near = wt[(wt.td <= sd + pd.Timedelta(days=AVG_WINDOW_DAYS))]
            near = near.iloc[(near.td - sd).abs().argsort()[:1]] if len(near) else near
            if len(near):
                t = near.iloc[0].to_dict()
                for col, fmt in [("test_id", f_text), ("test_date", f_date), ("test_duration_hr", f_num),
                                 ("oil_rate_bopd", f_num), ("water_rate_bwpd", f_num), ("gas_rate_mscfd", f_num),
                                 ("thp_kgcm2", f_num), ("chp_kgcm2", f_num), ("fluid_level_m", f_num),
                                 ("pump_intake_p_kgcm2", f_num), ("test_quality", f_text)]:
                    f.add(f"test_{col}" if not col.startswith("test_") else col, t.get(col), fmt, f"well_tests.{col}")
                liq = (t.get("oil_rate_bopd") or 0) + (t.get("water_rate_bwpd") or 0)
                f.add("test_water_cut_pct", (t.get("water_rate_bwpd") or 0) / liq * 100 if liq else np.nan, f_pct,
                      "well_tests.water_rate / (oil + water)")
                f.add("test_gor_scf_bbl", (t.get("gas_rate_mscfd") or 0) * 1000 / t["oil_rate_bopd"] if t.get("oil_rate_bopd") else np.nan,
                      f_int, "well_tests.gas_rate_mscfd * 1000 / oil_rate_bopd")
            f.missing("test_id", "test_date", "test_duration_hr", "test_oil_rate_bopd", "test_water_rate_bwpd",
                      "test_gas_rate_mscfd", "test_thp_kgcm2", "test_chp_kgcm2", "test_fluid_level_m",
                      "test_pump_intake_p_kgcm2", "test_quality", "test_water_cut_pct", "test_gor_scf_bbl")
            recent = wt[wt.td <= sd].tail(4)
            f.table("recent_tests", recent, {"test_date": f_date, "oil_rate_bopd": f_num, "water_rate_bwpd": f_num,
                                             "gas_rate_mscfd": f_num, "thp_kgcm2": f_num, "chp_kgcm2": f_num,
                                             "fluid_level_m": f_num, "test_quality": f_text}, "well_tests")
            f.add("decline_window_days", DECLINE_WINDOW_DAYS, f_int, "facts.DECLINE_WINDOW_DAYS")
            f.add("well_decline_pct", _decline(fd, well, sd), f_signed_pct,
                  "daily_production oil: mean(last window) vs mean(window starting decline_window_days earlier)")
            orows = []
            for o in offs.to_dict("records"):
                orows.append({"offset_well_id": o["offset_well_id"], "distance_m": o["distance_m"], "same_zone": o["same_zone"],
                              "decline_pct": _decline(fd, o["offset_well_id"], sd) if o["offset_well_id"] in fd.dp_by_well else np.nan})
            odf = pd.DataFrame(orows)
            f.table("offsets", odf, {"offset_well_id": f_text, "distance_m": f_num, "same_zone": f_bool,
                                     "decline_pct": f_signed_pct}, "well_offsets + daily_production")
            if len(odf):
                f.add("offset_median_decline_pct", odf["decline_pct"].median(), f_signed_pct, "median(offsets.decline_pct)")
                resid = (odf["decline_pct"] - f.raw.get("well_decline_pct", np.nan)).abs().max() if f.raw.get("well_decline_pct") is not None else np.nan
                f.add("offset_max_residual_pp", resid, lambda v: MISSING if _isnan(v) else f"{v:.1f} pp",
                      "max |offset decline - well decline|")
            f.missing("offset_median_decline_pct", "offset_max_residual_pp")
            yield f.spec(doc_id=doc_id, doc_type="D07", field=fd.field, well_id=well, doc_date=f_date(sd), title=title,
                         meta={"survey_id": r["survey_id"]})


def build_d08(fd: FieldData) -> Iterator[DocSpec]:
    wo = fd.wo
    for r in _wo_rows(fd):
        if r["outcome"] != "FAILED":
            continue
        well = r["well_id"]
        doc_id = f"RCA-{r['workover_id'][3:]}"
        title = f"{well} Failure Root-Cause Analysis — {r['catalogue_job_code']} ({f_date(r['end_date'])[:7]})"
        f = Facts()
        _base(f, doc_id, "D08", fd.field, well, r["end_date"], title, r["cluster_id"])
        _well_facts(f, fd, well)
        _job_facts(f, fd, r)
        _prod_context(f, fd, well, r["ts"], r["te"])
        f.add("d02_doc_id", _d2_doc_id(r), f_text, "workover_history.report_doc_id")
        h = fd.wo_by_well[well]
        same = h[(h.ts < r["ts"]) & (h.failure_code == r["failure_code"]) & h.outcome.isin(REPORTED_OUTCOMES)]
        f.add("n_prior_same_failure", len(same), f_int, "count(prior jobs with same failure_code)")
        nxt = h[(h.ts > r["ts"]) & h.outcome.isin(REPORTED_OUTCOMES)].head(1)
        if len(nxt):
            n = nxt.iloc[0]
            f.add("next_workover_id", n["workover_id"], f_text, "workover_history.workover_id[next]")
            f.add("next_job_code", n["catalogue_job_code"], f_text, "workover_history.catalogue_job_code[next]")
            f.add("next_start_date", n["start_date"], f_date, "workover_history.start_date[next]")
            f.add("next_outcome", n["outcome"], f_text, "workover_history.outcome[next]")
            f.add("days_to_next_job", (n["ts"] - r["te"]).days, f_int, "next start_date - end_date")
        f.missing("next_workover_id", "next_job_code", "next_start_date", "next_outcome", "days_to_next_job")
        fj = wo[(wo.catalogue_job_code == r["catalogue_job_code"]) & wo.outcome.isin(REPORTED_OUTCOMES)]
        f.add("field_jobs_same_code", len(fj), f_int, "count(field workover_history same catalogue_job_code)")
        f.add("field_fail_rate_same_code", (fj.outcome == "FAILED").mean() * 100 if len(fj) else np.nan, f_pct,
              "share FAILED among field jobs with same catalogue_job_code")
        _history(f, fd, well, before=None, limit=10)
        yield f.spec(doc_id=doc_id, doc_type="D08", field=fd.field, well_id=well, doc_date=f_date(r["end_date"]), title=title,
                     meta={"workover_id": r["workover_id"], "intervention_class": r.get("intervention_class"),
                           "job_code": r.get("catalogue_job_code")})


def _period_facts(f: Facts, fd: FieldData, start: pd.Timestamp, end: pd.Timestamp) -> None:
    a = asset_data()
    dp = fd.dp[(fd.dp.production_date >= start) & (fd.dp.production_date <= end)]
    days = (end - start).days + 1
    f.add("period_start", start.date(), f_date, "period")
    f.add("period_end", end.date(), f_date, "period")
    f.add("period_days", days, f_int, "period_end - period_start + 1")
    oil = dp["oil_rate_bopd"].fillna(0).sum()
    water = dp["water_rate_bwpd"].fillna(0).sum()
    gas = dp["gas_rate_mscfd"].fillna(0).sum()
    f.add("oil_bbl", oil, f_int, "sum(daily_production.oil_rate_bopd) over period")
    f.add("water_bbl", water, f_int, "sum(daily_production.water_rate_bwpd)")
    f.add("gas_mscf", gas, f_int, "sum(daily_production.gas_rate_mscfd)")
    f.add("avg_oil_bopd", oil / days, f_num, "oil_bbl / period_days")
    f.add("avg_water_cut_pct", water / (oil + water) * 100 if oil + water else np.nan, f_pct, "water_bbl / (oil_bbl + water_bbl)")
    f.add("avg_gor_scf_bbl", gas * 1000 / oil if oil else np.nan, f_int, "gas_mscf * 1000 / oil_bbl")
    prod = dp[dp.is_producing.astype(bool)]
    f.add("active_wells", prod.well_id.nunique(), f_int, "count distinct producing wells")
    f.add("wells_total", len(fd.wm), f_int, "count(well_master)")
    f.add("uptime_pct", len(prod) / len(dp) * 100 if len(dp) else np.nan, f_pct, "producing well-days / well-days")
    ft = a.field_targets
    ft = ft[(ft.field == fd.field) & (pd.to_datetime(ft.month) >= start.replace(day=1)) & (pd.to_datetime(ft.month) <= end)]
    tgt = ft["target_oil_bopd"].mean() if len(ft) else np.nan
    f.add("target_oil_bopd", tgt, f_num, "mean(field_targets.target_oil_bopd)")
    f.add("potential_oil_bopd", ft["potential_oil_bopd"].mean() if len(ft) else np.nan, f_num, "mean(field_targets.potential_oil_bopd)")
    f.add("target_uptime_pct", ft["target_uptime_pct"].mean() if len(ft) else np.nan, f_pct, "mean(field_targets.target_uptime_pct)")
    f.add("gap_vs_target_pct", pct_change(oil / days, tgt), f_signed_pct, "(avg_oil_bopd - target_oil_bopd) / target_oil_bopd")
    wo = fd.wo[(fd.wo.ts >= start) & (fd.wo.ts <= end) & fd.wo.outcome.isin(REPORTED_OUTCOMES)]
    f.add("n_jobs", len(wo), f_int, "count(workover_history started in period)")
    f.add("n_jobs_failed", int((wo.outcome == "FAILED").sum()), f_int, "count(... FAILED)")
    f.add("job_success_pct", (wo.outcome == "SUCCESS").mean() * 100 if len(wo) else np.nan, f_pct, "share SUCCESS")
    f.add("rig_days_used", wo["rig_days"].sum(), f_num, "sum(workover_history.rig_days)")
    f.add("uplift_bopd_total", wo["uplift_bopd"].sum(), f_num, "sum(workover_history.uplift_bopd)")
    by_ic = (wo.groupby("intervention_class")
               .agg(n_jobs=("workover_id", "count"), n_success=("outcome", lambda s: int((s == "SUCCESS").sum())),
                    n_failed=("outcome", lambda s: int((s == "FAILED").sum())), rig_days=("rig_days", "sum"),
                    uplift_bopd=("uplift_bopd", "sum")).reset_index())
    by_ic["ic_label"] = by_ic["intervention_class"].map(a.ic_labels)
    f.table("jobs_by_class", by_ic, {"intervention_class": f_text, "ic_label": f_text, "n_jobs": f_int, "n_success": f_int,
                                     "n_failed": f_int, "rig_days": f_num, "uplift_bopd": f_num}, "workover_history")
    # downtime by reason (status history, days in period)
    s = fd.wsh[(fd.wsh.te >= start) & (fd.wsh.ts <= end) & (fd.wsh.status != "PRODUCING")].copy()
    if len(s):
        s["days"] = (s["te"].clip(upper=end) - s["ts"].clip(lower=start)).dt.days + 1
        dt = (s.groupby(["status", "reason_code"]).agg(episodes=("episode_id", "count"), days=("days", "sum"),
                                                        deferred_bbl=("deferred_bbl", "sum"))
              .reset_index().sort_values("days", ascending=False).head(10))
        f.add("deferred_bbl", s["deferred_bbl"].sum(), f_int, "sum(well_status_history.deferred_bbl) non-producing episodes")
    else:
        dt = pd.DataFrame(columns=["status", "reason_code", "episodes", "days", "deferred_bbl"])
        f.add("deferred_bbl", 0, f_int, "sum(well_status_history.deferred_bbl)")
    f.table("downtime", dt, {"status": f_text, "reason_code": f_text, "episodes": f_int, "days": f_int,
                             "deferred_bbl": f_int}, "well_status_history")
    e = fd.ev[(fd.ev.ts >= start) & (fd.ev.ts <= end)]
    evt = (e.groupby(["event_type", "factor_class"]).agg(events=("event_id", "count"),
                                                          controllable=("controllable", lambda s: int(s.sum())))
           .reset_index().sort_values("events", ascending=False))
    f.table("events", evt, {"event_type": f_text, "factor_class": f_text, "events": f_int, "controllable": f_int},
            "operations_events")
    # per-cluster production
    cl = fd.wm[["well_id", "cluster_id"]].reset_index(drop=True)
    pc = dp.merge(cl, on="well_id").groupby("cluster_id").agg(oil=("oil_rate_bopd", "sum"), wells=("well_id", "nunique")).reset_index()
    pc["avg_oil_bopd"] = pc["oil"] / days
    f.table("clusters", pc, {"cluster_id": f_text, "wells": f_int, "oil": f_int, "avg_oil_bopd": f_num},
            "daily_production + well_master.cluster_id")


def build_d09(fd: FieldData) -> Iterator[DocSpec]:
    code = FIELD_CODES[fd.field]
    start_all, end_all = fd.dp.production_date.min(), pd.Timestamp(AS_OF)
    for year in range(start_all.year, end_all.year + 1):
        start = max(pd.Timestamp(year, 1, 1), start_all)
        end = min(pd.Timestamp(year, 12, 31), end_all)
        doc_id = f"FS-{code}-{year}"
        partial = start != pd.Timestamp(year, 1, 1) or end != pd.Timestamp(year, 12, 31)
        title = f"{fd.field} Field Annual Review {year}" + (" (part year)" if partial else "")
        f = Facts()
        _base(f, doc_id, "D09", fd.field, None, end.date(), title)
        f.add("year", year, lambda v: str(v), "calendar year")
        f.add("is_partial_year", partial, f_bool, "period shorter than calendar year")
        _period_facts(f, fd, start, end)
        prev_s, prev_e = pd.Timestamp(year - 1, 1, 1), pd.Timestamp(year - 1, 12, 31)
        if prev_e >= start_all:
            pdp = fd.dp[(fd.dp.production_date >= max(prev_s, start_all)) & (fd.dp.production_date <= prev_e)]
            pdays = (prev_e - max(prev_s, start_all)).days + 1
            prev_avg = pdp["oil_rate_bopd"].fillna(0).sum() / pdays
            f.add("prev_avg_oil_bopd", prev_avg, f_num, "previous-year avg oil")
            f.add("yoy_change_pct", pct_change(f.raw["avg_oil_bopd"], prev_avg), f_signed_pct, "avg_oil_bopd vs previous year")
        f.missing("prev_avg_oil_bopd", "yoy_change_pct")
        _field_static(f, fd)
        yield f.spec(doc_id=doc_id, doc_type="D09", field=fd.field, well_id=None, doc_date=f_date(end), title=title,
                     meta={"year": year})
    # legacy field documents from the landing index (frozen v0.3 set): render as D9 field studies
    for d in fd.docidx.to_dict("records"):
        if not str(d["doc_id"]).startswith("DOC-FIELD-"):
            continue
        f = Facts()
        _base(f, d["doc_id"], "D09", fd.field, None, d["doc_date"], d["title"])
        f.add("study_topic", d["title"], f_text, "document_index.title")
        _field_static(f, fd)
        yield f.spec(doc_id=d["doc_id"], doc_type="D09", field=fd.field, well_id=None, doc_date=f_date(d["doc_date"]),
                     title=d["title"], meta={"legacy_doc_type": d["doc_type"], "variant": "legacy_study"})


def _field_static(f: Facts, fd: FieldData) -> None:
    a = asset_data()
    fm = a.field_master[a.field_master.field == fd.field].iloc[0].to_dict()
    f.add("n_wells", fm["n_wells"], f_int, "field_master.n_wells")
    f.add("primary_reservoirs", fm["primary_reservoirs"], f_text, "field_master.primary_reservoirs")
    f.add("centroid_lat", fm["centroid_lat"], lambda v: f_num(v, 3), "field_master.centroid_lat")
    f.add("centroid_lon", fm["centroid_lon"], lambda v: f_num(v, 3), "field_master.centroid_lon")
    f.add("data_start", fm["data_start"], f_date, "field_master.data_start")
    f.add("data_end", fm["data_end"], f_date, "field_master.data_end")
    cm = a.cluster_master[a.cluster_master.field == fd.field]
    f.add("n_clusters", len(cm), f_int, "count(cluster_master)")
    f.table("cluster_list", cm, {"cluster_id": f_text, "cluster_type": f_text, "n_wells": f_int,
                                 "center_lat": lambda v: f_num(v, 3), "center_lon": lambda v: f_num(v, 3)}, "cluster_master")
    fac = a.facility_master[a.facility_master.field == fd.field]
    f.table("facilities", fac, {"facility_id": f_text, "type": f_text, "name": f_text, "capacity_bopd": f_int,
                                "serviced_cluster_ids": f_text}, "facility_master")
    lift = fd.wm["lift_type"].value_counts().rename_axis("lift_type").reset_index(name="wells")
    f.table("lift_mix", lift, {"lift_type": f_text, "wells": f_int}, "well_master.lift_type")
    ft = fd.ftops.groupby("formation").agg(median_top_md_m=("top_md_m", "median"), wells=("well_id", "nunique"),
                                           lithology=("lithology", "first")).reset_index().sort_values("median_top_md_m")
    f.table("formation_summary", ft, {"formation": f_text, "median_top_md_m": f_num, "wells": f_int, "lithology": f_text},
            "formation_tops")


def build_d10(fd: FieldData) -> Iterator[DocSpec]:
    code = FIELD_CODES[fd.field]
    start_all = fd.dp.production_date.min()
    m = pd.Timestamp(start_all.year, start_all.month, 1)
    while True:
        end = (m + pd.offsets.MonthEnd(0)).normalize()
        if end.date() > AS_OF:
            break
        doc_id = f"MPR-{code}-{m:%Y-%m}"
        title = f"{fd.field} Monthly Production Report {m:%B %Y}"
        f = Facts()
        _base(f, doc_id, "D10", fd.field, None, end.date(), title)
        f.add("month_label", f"{m:%B %Y}", f_text, "calendar month")
        _period_facts(f, fd, m, end)
        pm = m - pd.offsets.MonthBegin(1)
        if pm >= pd.Timestamp(start_all.year, start_all.month, 1):
            pend = (pm + pd.offsets.MonthEnd(0)).normalize()
            pdp = fd.dp[(fd.dp.production_date >= pm) & (fd.dp.production_date <= pend)]
            prev_avg = pdp["oil_rate_bopd"].fillna(0).sum() / ((pend - pm).days + 1)
            f.add("prev_avg_oil_bopd", prev_avg, f_num, "previous-month avg oil")
            f.add("mom_change_pct", pct_change(f.raw["avg_oil_bopd"], prev_avg), f_signed_pct, "avg_oil_bopd vs previous month")
        f.missing("prev_avg_oil_bopd", "mom_change_pct")
        # top / bottom wells by monthly oil
        dp = fd.dp[(fd.dp.production_date >= m) & (fd.dp.production_date <= end)]
        wsum = dp.groupby("well_id").agg(oil=("oil_rate_bopd", "sum"), days_on=("is_producing", "sum")).reset_index()
        wsum["avg_oil_bopd"] = wsum["oil"] / ((end - m).days + 1)
        f.table("top_wells", wsum.sort_values("oil", ascending=False).head(10),
                {"well_id": f_text, "oil": f_int, "avg_oil_bopd": f_num, "days_on": f_int}, "daily_production")
        jobs = fd.wo[(fd.wo.ts >= m) & (fd.wo.ts <= end) & fd.wo.outcome.isin(REPORTED_OUTCOMES)]
        f.table("jobs_started", jobs.head(25), {"well_id": f_text, "workover_id": f_text, "catalogue_job_code": f_text,
                                                "intervention_class": f_text, "start_date": f_date, "rig_days": f_num,
                                                "outcome": f_text}, "workover_history")
        yield f.spec(doc_id=doc_id, doc_type="D10", field=fd.field, well_id=None, doc_date=f_date(end), title=title,
                     meta={"month": f"{m:%Y-%m}"})
        m = m + pd.offsets.MonthBegin(1)


def build_d11() -> Iterator[DocSpec]:
    """One SOP per intervention class IC-01..IC-14 (doc_id = job_catalogue.sop_doc_id), asset-wide."""
    a = asset_data()
    jc = a.job_catalogue
    for ic in IC_SOP_CLASSES:
        jobs = jc[jc.intervention_class == ic]
        sop_ids = jobs["sop_doc_id"].dropna().unique()
        doc_id = sop_ids[0] if len(sop_ids) else f"SOP-{ic}"
        label = a.ic_labels.get(ic, ic)
        title = f"SOP {ic} — {label}"
        f = Facts()
        _base(f, doc_id, "D11", "ALL", None, AS_OF, title)
        f.add("intervention_class", ic, f_text, "ic_map.yaml")
        f.add("ic_label", label, f_text, "ic_map.yaml label")
        f.add("n_job_codes", len(jobs), f_int, "count(job_catalogue[intervention_class])")
        f.table("job_codes", jobs, {"job_code": f_text, "job_name": f_text, "category": f_text, "equipment": f_text,
                                    "requires_rig": f_bool, "est_days": f_num, "cost_band": f_text,
                                    "selection_evidence": f_text}, "job_catalogue")
        f.add("equipment_list", ", ".join(sorted(jobs["equipment"].dropna().unique())), f_text, "job_catalogue.equipment")
        f.add("requires_rig_any", bool(jobs["requires_rig"].any()), f_bool, "any(job_catalogue.requires_rig)")
        f.add("est_days_min", jobs["est_days"].min(), f_num, "min(job_catalogue.est_days)")
        f.add("est_days_max", jobs["est_days"].max(), f_num, "max(job_catalogue.est_days)")
        rows, alljobs = [], []
        for fld in FIELDS:
            wo = field_data(fld).wo
            j = wo[(wo.intervention_class == ic) & wo.outcome.isin(REPORTED_OUTCOMES)]
            alljobs.append(j)
            rows.append({"field": fld, "jobs": len(j),
                         "success_pct": (j.outcome == "SUCCESS").mean() * 100 if len(j) else np.nan,
                         "failed": int((j.outcome == "FAILED").sum()),
                         "median_rig_days": j["rig_days"].median() if len(j) else np.nan,
                         "median_uplift_bopd": j["uplift_bopd"].median() if len(j) else np.nan,
                         "median_run_life_days": j["run_life_days"].median() if len(j) else np.nan})
        f.table("field_stats", pd.DataFrame(rows), {"field": f_text, "jobs": f_int, "success_pct": f_pct, "failed": f_int,
                                                   "median_rig_days": f_num, "median_uplift_bopd": f_num,
                                                   "median_run_life_days": f_int}, "workover_history (all fields)")
        j = pd.concat(alljobs)
        f.add("jobs_all_fields", len(j), f_int, "count(workover_history[intervention_class])")
        f.add("success_pct_all", (j.outcome == "SUCCESS").mean() * 100 if len(j) else np.nan, f_pct, "share SUCCESS all fields")
        f.add("median_rig_days_all", j["rig_days"].median() if len(j) else np.nan, f_num, "median rig_days all fields")
        f.add("median_uplift_all", j["uplift_bopd"].median() if len(j) else np.nan, f_num, "median uplift_bopd all fields")
        fails = j[j.outcome == "FAILED"]["failure_code"].value_counts().head(5).rename_axis("failure_code").reset_index(name="failed_jobs")
        f.table("failure_modes", fails, {"failure_code": f_text, "failed_jobs": f_int}, "workover_history[FAILED]")
        yield f.spec(doc_id=doc_id, doc_type="D11", field="ALL", well_id=None, doc_date=AS_OF.isoformat(), title=title,
                     meta={"intervention_class": ic, "job_codes": list(jobs["job_code"])})


BUILDERS = {"D01": build_d01, "D02": build_d02, "D03": build_d03, "D04": build_d04, "D05": build_d05, "D06": build_d06,
            "D07": build_d07, "D08": build_d08, "D09": build_d09, "D10": build_d10}


def iter_specs(fields: Iterable[str] | None = None, types: Iterable[str] | None = None,
               wells: Iterable[str] | None = None) -> Iterator[DocSpec]:
    """Yield specs for the requested fields/types (D11 is asset-wide and yielded once)."""
    fields = list(fields or FIELDS)
    types = [norm_type(t) for t in (types or DOC_TYPES)]
    wells = set(wells) if wells else None
    for fld in fields:
        fd = field_data(fld)
        for t in types:
            if t == "D11":
                continue
            for spec in BUILDERS[t](fd):
                if wells is None or spec.well_id in wells or (spec.well_id is None and t in ("D09", "D10")):
                    yield spec
    if "D11" in types:
        yield from build_d11()


def stable_hash(text: str) -> int:
    return int(hashlib.sha1(text.encode()).hexdigest()[:12], 16)
