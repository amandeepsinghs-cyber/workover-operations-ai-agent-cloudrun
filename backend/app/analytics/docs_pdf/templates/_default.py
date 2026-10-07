"""Generic fallback template: dumps every fact and table (used until a type template exists)."""
from __future__ import annotations

from app.analytics.docs_pdf.ir import KV, H, P, Table

SKIP = {"doc_id", "doc_type", "doc_type_name", "doc_title", "doc_date", "field", "asset", "as_of", "well_id"}


def _label(slot: str) -> str:
    # slot names may contain digits only in theory; strip them to keep the literal legal
    return "".join(ch for ch in slot.replace("_", " ") if not ch.isdigit()).strip().capitalize()


def build(spec):
    pairs = [(_label(k), "{" + k + "}") for k in spec.facts if k not in SKIP]
    blocks = [H("Summary of recorded facts"), KV(pairs, cols=2)]
    for name, data in spec.tables.items():
        if not data.columns:
            continue
        blocks.append(H(_label(name), level=2))
        blocks.append(Table(name, [(c, _label(c)) for c in data.columns]))
    blocks.append(P("Generated from the WellPulse landing tables.", style="note"))
    return blocks
