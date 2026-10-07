"""``WellRepository`` protocol and the process-wide repository accessor (SDD §5.7).

``DATA_BACKEND`` selects the implementation: ``parquet`` (default, D-11 local) reads the Stage N
landing files; ``bigquery`` (Stage X) reads the same frames from ``wellpulse_silver`` (``bigquery_repo.py``).
"""

from __future__ import annotations

import os
import threading
from typing import Protocol

from .parquet_repo import ParquetRepository, RetiredWellId

__all__ = ["RetiredWellId", "WellRepository", "get_repository", "reset_repository"]


class WellRepository(Protocol):
    def list_wells(self) -> list[dict]: ...
    def get_well(self, well_id: str) -> dict | None: ...
    def get_history(self, well_id: str, range_: str) -> list[dict] | None: ...
    def field_infrastructure(self, field: str) -> dict: ...
    def catalogue_job(self, job_code: str) -> dict | None: ...


_repo: WellRepository | None = None
_lock = threading.Lock()


def get_repository() -> WellRepository:
    global _repo
    with _lock:
        if _repo is None:
            backend = os.environ.get("DATA_BACKEND", "parquet").strip().lower()
            if backend == "bigquery":
                from .bigquery_repo import (
                    BigQueryRepository,  # Stage X; lazy so parquet needs no GCP libs
                )

                _repo = BigQueryRepository()
                return _repo
            if backend != "parquet":
                raise ValueError(f"unknown DATA_BACKEND {backend!r} (expected 'parquet' or 'bigquery')")
            _repo = ParquetRepository()
        return _repo


def reset_repository() -> None:
    """Drop the cached repository (tests)."""
    global _repo
    with _lock:
        _repo = None
