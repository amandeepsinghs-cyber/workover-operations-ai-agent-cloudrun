"""Stage O gate on the real, fully built corpus (skipped when it has not been built).

Build: ``cd backend && uv run python -m app.analytics.docs_pdf.build``
"""
from __future__ import annotations

import json

import pandas as pd
import pytest

from app.analytics.docs_pdf.facts import DOC_TYPES
from app.analytics.docs_pdf.paths import docs_dir, index_dir

FIELDS = ("Geleki", "Lakwa", "Lakhmani")
IDX = index_dir()
ROOT = docs_dir()

pytestmark = pytest.mark.skipif(not (IDX / "document_index.parquet").exists(),
                                reason="document corpus not built (run app.analytics.docs_pdf.build)")


@pytest.fixture(scope="module")
def docs() -> pd.DataFrame:
    return pd.read_parquet(IDX / "document_index.parquet")


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads((IDX / "corpus_manifest.json").read_text())


def test_every_index_row_resolves_to_a_pdf(docs):
    missing = [r.doc_id for r in docs.itertuples() if not (ROOT / r.path).exists()]
    assert not missing, missing[:10]


def test_d1_to_d11_present_for_every_field(docs):
    for fld in FIELDS:
        have = set(docs.loc[docs["field"] == fld, "doc_type"])
        have |= set(docs.loc[docs["field"] == "ALL", "doc_type"])  # SOPs are asset-wide
        assert set(DOC_TYPES) <= have, (fld, sorted(set(DOC_TYPES) - have))


def test_sop_for_every_intervention_class(docs):
    sops = set(docs.loc[docs["doc_type"] == "D11", "doc_id"])
    assert {f"SOP-IC-{n:02d}" for n in range(1, 15)} <= sops


def test_scanned_subset_is_about_ten_percent(docs):
    sub = docs[docs["doc_type"].isin(["D01", "D05"])]
    share = (~sub["has_text_layer"].astype(bool)).mean()
    assert 0.07 <= share <= 0.13, share
    assert not bool(docs.set_index("doc_id").loc["DOC-CBL-GK129-1998", "has_text_layer"])


def test_gk129_hero_documents(docs):
    d = docs.set_index("doc_id")
    assert d.loc["DOC-CBL-GK129-1998", "doc_type"] == "D05"
    assert str(d.loc["DOC-CBL-GK129-1998", "doc_date"]).startswith("1998")
    assert d.loc["DOC-SCAN-GK-129-2019", "doc_type"] == "D02"
    assert str(d.loc["DOC-SCAN-GK-129-2019", "doc_date"]).startswith("2019")


def test_corpus_size_within_budget(manifest):
    assert manifest["corpus_mb"] <= 200, manifest["corpus_mb"]
