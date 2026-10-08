"""Parquet-backed repository (SDD §5.7; D-11 local default).

Loads the Stage N landing parquet once per process (lazy, thread-safe) and serves REST-shaped
dicts through ``adapters``. BigQuery (Stage X) will implement the same ``WellRepository`` protocol.
"""

from __future__ import annotations

import threading
from functools import cached_property
from pathlib import Path

import pandas as pd

from app import settings
from app.analytics.generator.fields import FIELD_CONFIGS, field_of

from . import adapters

DAILY_COLS = ["well_id", "production_date", "oil_rate_bopd", "water_rate_bwpd", "gas_rate_mscfd", "liquid_rate_blpd",
              "water_cut_pct", "gor_scf_bbl", "thp_kgcm2", "chp_kgcm2", "choke_size_64th", "spm", "runtime_fraction",
              "is_producing", "downtime_reason", "wht_degc", "gl_inj_rate_mscfd", "gl_inj_pressure_kgcm2"]
PER_WELL_TABLES = [
    "workover_history", "well_status_history", "casing_tally", "tubing_string", "perforation_intervals",
    "pressure_surveys", "formation_tops", "well_tests", "operations_events", "document_index",
    "tubing_tally", "deviation_survey", "barrier_tests", "wellhead_rating", "fluid_hazards", "fishing_records",
]


class RetiredWellId(LookupError):
    """GLK- IDs were the v0.3 demo layout; v0.4 uses GK- / LKW- / LKM- (SDD §5.1)."""


class ParquetRepository:
    def __init__(self, landing: Path | None = None):
        self.landing = Path(landing or settings.LANDING_DIR)
        self._lock = threading.Lock()
        self._summaries: list[dict] | None = None
        self._summary_by_id: dict[str, dict] = {}
        self._detail_cache: dict[str, dict] = {}

    # -- raw frames -------------------------------------------------------------------------------
    def _read(self, folder: str, table: str, columns: list[str] | None = None) -> pd.DataFrame:
        path = self.landing / folder / f"{table}.parquet"
        if not path.exists():
            return pd.DataFrame()
        return pd.read_parquet(path, columns=columns)

    @cached_property
    def wells(self) -> pd.DataFrame:
        return pd.concat([self._read(f.lower(), "well_master") for f in FIELD_CONFIGS], ignore_index=True)

    @cached_property
    def daily(self) -> pd.DataFrame:
        frames = [self._read(f.lower(), "daily_production", DAILY_COLS) for f in FIELD_CONFIGS]
        d = pd.concat(frames, ignore_index=True)
        return d[d["production_date"] <= settings.AS_OF].reset_index(drop=True)

    @cached_property
    def daily_index(self) -> dict[str, list[int]]:
        return {k: list(v) for k, v in self.daily.groupby("well_id", sort=False).indices.items()}

    @cached_property
    def per_well(self) -> dict[str, dict[str, pd.DataFrame]]:
        out: dict[str, dict[str, pd.DataFrame]] = {}
        for t in PER_WELL_TABLES:
            frames = []
            for f in FIELD_CONFIGS:
                path = self.landing / f.lower() / f"{t}.parquet"
                if path.exists():
                    df_f = self._read(f.lower(), t)
                    if not df_f.empty:
                        frames.append(df_f)
            if not frames:
                continue
            df = pd.concat(frames, ignore_index=True)
            if "well_id" in df.columns:
                df = df[df["well_id"].notna()]
                for wid, g in df.groupby("well_id", sort=False):
                    out.setdefault(wid, {})[t] = g.reset_index(drop=True)
        return out

    @cached_property
    def catalogue(self) -> pd.DataFrame:
        return self._read("asset", "job_catalogue").set_index("job_code")

    @cached_property
    def facilities(self) -> pd.DataFrame:
        return self._read("asset", "facility_master")

    @cached_property
    def field_master(self) -> pd.DataFrame:
        return self._read("asset", "field_master").set_index("field")

    @cached_property
    def well_rows(self) -> dict[str, dict]:
        return {r["well_id"]: r for r in self.wells.to_dict("records")}

    # -- lookups ----------------------------------------------------------------------------------
    def resolve_id(self, well_id: str) -> str | None:
        """Canonical well ID, or None if unknown. Raises ``RetiredWellId`` for GLK- IDs."""
        wid = (well_id or "").strip().upper()
        if wid.startswith("GLK-"):
            raise RetiredWellId(wid)
        if field_of(wid) is None:
            return None
        return wid if wid in self.well_rows else None

    def _well_daily(self, wid: str) -> pd.DataFrame:
        return self.daily.iloc[self.daily_index.get(wid, [])]

    def _tables(self, wid: str) -> dict[str, pd.DataFrame]:
        return self.per_well.get(wid, {})

    def _summaries_locked(self) -> list[dict]:
        if self._summaries is None:
            self._summaries = [
                adapters.well_summary(row, self._well_daily(wid), self._tables(wid), self.catalogue)
                for wid, row in self.well_rows.items()
            ]
            self._summary_by_id = {s["id"]: s for s in self._summaries}
        return self._summaries

    # -- public API (WellRepository) ----------------------------------------------------------------
    def list_wells(self) -> list[dict]:
        with self._lock:
            return self._summaries_locked()

    def get_well(self, well_id: str) -> dict | None:
        wid = self.resolve_id(well_id)
        if wid is None:
            return None
        with self._lock:
            if wid not in self._detail_cache:
                self._summaries_locked()
                row = self.well_rows[wid]
                cfg = FIELD_CONFIGS[row["field"]]
                self._detail_cache[wid] = adapters.well_detail(
                    self._summary_by_id[wid], row, self._well_daily(wid), self._tables(wid), self.catalogue, cfg)
            return self._detail_cache[wid]

    def get_history(self, well_id: str, range_: str) -> list[dict] | None:
        wid = self.resolve_id(well_id)
        if wid is None:
            return None
        return adapters.history_points(self._well_daily(wid), range_)

    def field_infrastructure(self, field: str) -> dict:
        cfg = FIELD_CONFIGS[field]
        fac = self.facilities[self.facilities["field"] == field]
        wells = self.wells[self.wells["field"] == field]
        return adapters.field_infrastructure(cfg, fac, wells, self.field_master.loc[field])

    def catalogue_job(self, job_code: str) -> dict | None:
        """One ``job_catalogue`` row (used by the recommendation fallback for cost band / rig-days)."""
        return self.catalogue.loc[job_code].to_dict() if job_code in self.catalogue.index else None
