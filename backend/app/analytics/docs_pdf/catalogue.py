"""Slot catalogue: what each document type's templates may reference.

    uv run python -m app.analytics.docs_pdf.catalogue      # writes templates/slot_catalogue/DNN.json

For every slot: source, up to 3 example values, how often it is missing, and (for
categorical slots) the full set of values seen, so templates can branch safely.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from app.analytics.docs_pdf.facts import DOC_TYPES, iter_specs, stable_hash
from app.analytics.docs_pdf.ir import DIGIT_RE, MISSING

OUT = Path(__file__).parent / "templates" / "slot_catalogue"
MAX_ENUM = 40


def build(doc_type: str, max_specs: int = 2000) -> dict:
    specs = list(iter_specs(types=[doc_type]))
    n_all = len(specs)
    specs = sorted(specs, key=lambda s: stable_hash(s.doc_id))[:max_specs]
    slots: dict = defaultdict(lambda: {"examples": [], "missing": 0, "values": Counter(), "source": ""})
    tables: dict = {}
    for s in specs:
        for k, v in s.facts.items():
            e = slots[k]
            e["source"] = s.sources.get(k, e["source"])
            if v == MISSING:
                e["missing"] += 1
            elif len(e["examples"]) < 3 and v not in e["examples"]:
                e["examples"].append(v)
            if not DIGIT_RE.search(str(v)):
                e["values"][v] += 1
        for name, t in s.tables.items():
            cur = tables.setdefault(name, {"columns": list(t.columns), "source": t.source, "example_rows": [], "max_rows_seen": 0})
            cur["max_rows_seen"] = max(cur["max_rows_seen"], len(t.rows))
            if len(cur["example_rows"]) < 2 and t.rows:
                cur["example_rows"].append(dict(t.rows[0]))
    out_slots = {}
    for k, e in slots.items():
        d = {"source": e["source"], "examples": e["examples"], "missing_share": round(e["missing"] / len(specs), 3)}
        if e["values"] and len(e["values"]) <= MAX_ENUM and sum(e["values"].values()) >= len(specs) * 0.5:
            d["categorical_values"] = sorted(e["values"])
        out_slots[k] = d
    return {"doc_type": doc_type, "doc_type_name": DOC_TYPES[doc_type], "n_documents": n_all,
            "missing_text": MISSING, "slots": out_slots, "tables": tables,
            "meta_keys": sorted({k for s in specs for k in s.meta}), "sample_doc_ids": [s.doc_id for s in specs[:5]]}


def main(argv=None) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    types = (argv or sys.argv[1:]) or list(DOC_TYPES)
    for t in types:
        cat = build(t)
        (OUT / f"{t}.json").write_text(json.dumps(cat, indent=1, default=str))
        print(f"{t}: {cat['n_documents']} docs, {len(cat['slots'])} slots, {len(cat['tables'])} tables")
    return 0


if __name__ == "__main__":
    sys.exit(main())
