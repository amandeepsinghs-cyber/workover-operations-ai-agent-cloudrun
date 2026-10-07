"""Template registry: one module per document type (``dNN_*.py``) exposing ``build(spec)``.

``build(spec: DocSpec) -> list[Block]`` returns the document *body*; the framework
adds the header (title, document id, well, field, date), the footer, the hero
narrative (``hero_text.yaml``) and the sign-off.

Template rules (enforced at render time by ``ir.check_literal`` and statically by
``validate.py --type DNN``):
- No digit and no spelled-out number word in ANY string you write (headings,
  labels, prose, table headers). Numbers enter only as ``{slot}`` references to
  ``spec.facts`` or as table rows from ``spec.tables``.
- Only reference slots / table columns that exist for the type (see
  ``templates/slot_catalogue/DNN.json``).
- You may branch on ``spec.raw[...]`` / ``spec.has(...)`` / ``spec.is_(...)`` but never
  compute or format a number yourself.
"""
from __future__ import annotations

import importlib
from types import ModuleType

TEMPLATE_MODULES = {
    "D01": "d01_completion",
    "D02": "d02_workover",
    "D03": "d03_dwr",
    "D04": "d04_schematic",
    "D05": "d05_cbl",
    "D06": "d06_chemical",
    "D07": "d07_well_test",
    "D08": "d08_rca",
    "D09": "d09_field_study",
    "D10": "d10_monthly",
    "D11": "d11_sop",
}


def load_template(doc_type: str) -> ModuleType:
    """Return the type's template module, or the generic default if not written yet."""
    name = TEMPLATE_MODULES[doc_type]
    try:
        return importlib.import_module(f"{__name__}.{name}")
    except ModuleNotFoundError as e:
        if e.name != f"{__name__}.{name}":
            raise
        return importlib.import_module(f"{__name__}._default")
