"""Build-time artefact self-check for the WellPulse image (SDD §17.1 `selfcheck`).

Run inside the Docker build stage from ``/app/backend``:
    python /tmp/selfcheck.py
Fails (exit != 0) if any data / model artefact the runtime needs is missing, or if the ASGI app
cannot be imported with the baked-in data. Lives in deploy/ because the Stage W packet owns only
packaging files (an ``app.analytics.tools.selfcheck`` module can replace it later).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path("app")
REQUIRED = [
    "data/landing/asset/field_targets.parquet",
    "data/index/corpus_manifest.json",
    "data/index/document_index.parquet",
    "data/index/doc_chunks.parquet",
    "data/index/tfidf.pkl",
    "analytics/model/coxph_srp_v1.pkl",
    "analytics/model/intervention_classifier_v1.pkl",
    "analytics/config/triggers.yaml",
    "data/geodata/geleki_boundary.geojson",
    "data/geodata/lakwa_boundary.geojson",
    "data/geodata/lakhmani_boundary.geojson",
]


def main() -> int:
    missing = [p for p in REQUIRED if not (ROOT / p).is_file()]
    n_parquet = len(list((ROOT / "data/landing").rglob("*.parquet")))
    n_pdf = len(list((ROOT / "data/docs_pdf").rglob("*.pdf")))
    print(f"[selfcheck] landing parquet={n_parquet} pdfs={n_pdf} missing={missing}")
    if missing or n_parquet == 0 or n_pdf == 0:
        print("[selfcheck] FAILED: data/model artefacts missing", file=sys.stderr)
        return 1
    sys.path.insert(0, ".")
    import app.main  # noqa: F401  (import smoke; no network: data is local parquet)

    print("[selfcheck] app.main imports OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
