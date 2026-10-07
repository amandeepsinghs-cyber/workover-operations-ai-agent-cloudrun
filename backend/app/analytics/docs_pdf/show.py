"""Print the facts and tables of one document (template / hero authors' helper).

    uv run python -m app.analytics.docs_pdf.show DOC-SCAN-GK-129-2019 [--json]
"""
from __future__ import annotations

import json
import sys

from app.analytics.docs_pdf.facts import FIELDS, iter_specs

PREFIX_FIELD = {"GK": "Geleki", "LKW": "Lakwa", "LKM": "Lakhmani"}


def find(doc_id: str):
    fields = [f for code, f in PREFIX_FIELD.items() if f"-{code}-" in f"-{doc_id}-" or f"-{code}" in doc_id]
    fields = fields or list(FIELDS)
    for s in iter_specs(fields=fields):
        if s.doc_id == doc_id:
            return s
    return None


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    s = find(args[0])
    if s is None:
        print(f"unknown doc_id {args[0]}")
        return 1
    if "--json" in args:
        print(json.dumps({"doc_id": s.doc_id, "doc_type": s.doc_type, "title": s.title, "facts": dict(s.facts),
                          "raw": {k: str(v) for k, v in s.raw.items()},
                          "tables": {k: {"columns": list(t.columns), "rows": [dict(r) for r in t.rows]} for k, t in s.tables.items()},
                          "meta": dict(s.meta)}, indent=1, default=str))
        return 0
    print(f"{s.doc_id}  {s.doc_type}  {s.title}  ({s.field}, {s.well_id}, {s.doc_date})")
    for k, v in s.facts.items():
        print(f"  {{{k}}} = {v!r:<40}  <- {s.sources.get(k, '')}")
    for name, t in s.tables.items():
        print(f"  table {name} ({len(t.rows)} rows) columns={list(t.columns)}")
        for r in t.rows[:5]:
            print("     ", dict(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
