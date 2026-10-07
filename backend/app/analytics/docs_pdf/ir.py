"""Intermediate representation for corpus documents + the fact-slot rule.

Templates (``templates/dNN_*.py``) return a list of blocks built from this module.
Every piece of template text is a *literal* that may reference fact slots as
``{slot_name}``.  Literals are checked when the block is created: a digit (or a
spelled-out number word) outside a ``{slot}`` raises :class:`FactSlotError`.
Numbers therefore only ever enter a document through ``DocSpec.facts`` (scalar
slots) or ``DocSpec.tables`` (row data), both filled by ``facts.py`` from the
landing tables.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

DIGIT_RE = re.compile(r"\d")
SLOT_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
# Spelled-out quantities are numbers too: a template may not smuggle them in.
NUMBER_WORDS = {
    "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
    "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty",
    "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety", "hundred", "thousand",
    "million", "billion", "dozen", "dozens", "lakh", "lakhs", "crore", "crores", "percent",
}
WORD_RE = re.compile(r"[A-Za-z]+")
MISSING = "not recorded"


class FactSlotError(ValueError):
    """A template literal broke the fact-slot rule or referenced an unknown slot."""


def literal_violations(text: str) -> list[str]:
    """Return the reasons ``text`` is not a legal template literal (empty = legal)."""
    if text is None:
        return []
    stripped = SLOT_RE.sub(" ", str(text))
    problems = []
    if DIGIT_RE.search(stripped):
        problems.append(f"digit outside a fact slot: {text!r}")
    words = {w.lower() for w in WORD_RE.findall(stripped)}
    bad = sorted(words & NUMBER_WORDS)
    if bad:
        problems.append(f"number word(s) {bad} in literal: {text!r}")
    if "{" in stripped or "}" in stripped:
        problems.append(f"malformed slot braces: {text!r}")
    return problems


def check_literal(text: str, where: str = "") -> str:
    problems = literal_violations(text)
    if problems:
        raise FactSlotError(f"{where}: " + "; ".join(problems))
    return text


def slots_in(text: str) -> list[str]:
    return SLOT_RE.findall(text or "")


# --------------------------------------------------------------------------- spec
@dataclass(frozen=True)
class TableData:
    """Row data for one table: ``rows`` hold pre-formatted strings keyed by column."""

    columns: tuple[str, ...]
    rows: tuple[Mapping[str, str], ...]
    source: str = ""

    def __len__(self) -> int:
        return len(self.rows)


@dataclass(frozen=True)
class DocSpec:
    doc_id: str
    doc_type: str  # "D01".."D11"
    field: str  # Geleki | Lakwa | Lakhmani | ALL
    well_id: str | None
    doc_date: str
    title: str
    facts: Mapping[str, str]  # slot -> formatted string (what is printed)
    raw: Mapping[str, Any]  # slot -> raw value (for template branching only)
    tables: Mapping[str, TableData]
    sources: Mapping[str, str]  # slot/table -> provenance "table.column"
    meta: Mapping[str, Any] = field(default_factory=dict)

    def has(self, slot: str) -> bool:
        v = self.facts.get(slot)
        return v is not None and v != MISSING and v != ""

    def table(self, name: str) -> TableData:
        return self.tables.get(name) or TableData(columns=(), rows=())

    def is_(self, slot: str, value: Any) -> bool:
        return self.raw.get(slot) == value


class FrozenDict(dict):
    """Read-only, picklable mapping (templates cannot add or change facts)."""

    def _ro(self, *a, **k):
        raise TypeError("DocSpec mappings are read-only: facts come from facts.py only")

    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = _ro  # type: ignore[assignment]

    def __reduce__(self):
        return (FrozenDict, (dict(self),))


def freeze_spec(**kw) -> DocSpec:
    for k in ("facts", "raw", "sources", "tables", "meta"):
        kw[k] = FrozenDict(kw.get(k) or {})
    return DocSpec(**kw)


# --------------------------------------------------------------------------- blocks
class Block:
    """Base class. ``literals()`` yields every template string for validation."""

    def literals(self) -> list[str]:
        return []


@dataclass
class H(Block):
    text: str
    level: int = 1

    def __post_init__(self):
        check_literal(self.text, "H")

    def literals(self):
        return [self.text]


@dataclass
class P(Block):
    text: str
    style: str = "body"  # body | note | small | emphasis

    def __post_init__(self):
        check_literal(self.text, "P")

    def literals(self):
        return [self.text]


@dataclass
class KV(Block):
    """Label/value grid. Values are templates, normally a single ``{slot}``."""

    pairs: Sequence[tuple[str, str]]
    cols: int = 2
    title: str | None = None

    def __post_init__(self):
        for label, value in self.pairs:
            check_literal(label, "KV label")
            check_literal(value, "KV value")
        if self.title:
            check_literal(self.title, "KV title")

    def literals(self):
        out = [x for pair in self.pairs for x in pair]
        return out + ([self.title] if self.title else [])


@dataclass
class Table(Block):
    """A table whose rows come from ``spec.tables[name]``. Headers are literals."""

    name: str
    columns: Sequence[tuple[str, str]]  # (column key, header literal)
    title: str | None = None
    max_rows: int | None = None
    empty_text: str = "No records in the source tables for this section."

    def __post_init__(self):
        for _, header in self.columns:
            check_literal(header, "Table header")
        if self.title:
            check_literal(self.title, "Table title")
        check_literal(self.empty_text, "Table empty_text")

    def literals(self):
        return [h for _, h in self.columns] + ([self.title] if self.title else []) + [self.empty_text]


@dataclass
class Bullets(Block):
    items: Sequence[str]
    numbered: bool = False  # numbered items render as "Step N" (layout numbering)

    def __post_init__(self):
        for it in self.items:
            check_literal(it, "Bullets item")

    def literals(self):
        return list(self.items)


@dataclass
class Callout(Block):
    text: str
    tone: str = "info"  # info | warning | danger | success

    def __post_init__(self):
        check_literal(self.text, "Callout")

    def literals(self):
        return [self.text]


@dataclass
class Schematic(Block):
    """Wellbore schematic drawn by the framework from tables casing/tubing/perfs/formations."""

    caption: str = "Wellbore schematic (not to scale)"

    def __post_init__(self):
        check_literal(self.caption, "Schematic caption")

    def literals(self):
        return [self.caption]


@dataclass
class Signoff(Block):
    roles: Sequence[str] = ("Prepared by", "Reviewed by", "Approved by")

    def __post_init__(self):
        for r in self.roles:
            check_literal(r, "Signoff role")

    def literals(self):
        return list(self.roles)


@dataclass
class PageBreak(Block):
    pass


@dataclass
class Spacer(Block):
    height_mm: float = 4.0  # layout dimension, not document content


# --------------------------------------------------------------------------- filling
class SlotFiller:
    """Resolves ``{slot}`` references against a spec and records which facts were used."""

    def __init__(self, spec: DocSpec):
        self.spec = spec
        self.used: dict[str, str] = {}
        self.used_tables: dict[str, dict] = {}

    def fill(self, text: str) -> str:
        def sub(m: re.Match) -> str:
            name = m.group(1)
            if name not in self.spec.facts:
                raise FactSlotError(f"{self.spec.doc_type}/{self.spec.doc_id}: unknown slot {{{name}}}")
            val = self.spec.facts[name]
            val = MISSING if val is None or val == "" else str(val)
            self.used[name] = val
            return val

        return SLOT_RE.sub(sub, text)

    def table_rows(self, block: Table) -> tuple[list[str], list[list[str]]]:
        data = self.spec.table(block.name)
        keys = [k for k, _ in block.columns]
        for k in keys:
            if data.rows and k not in data.columns:
                raise FactSlotError(f"{self.spec.doc_type}/{self.spec.doc_id}: table {block.name!r} has no column {k!r}")
        rows = list(data.rows[: block.max_rows] if block.max_rows else data.rows)
        out = [[str(r.get(k, MISSING) if r.get(k) not in (None, "") else MISSING) for k in keys] for r in rows]
        rec = self.used_tables.setdefault(block.name, {"columns": [], "rows": [], "source": data.source})
        rec["columns"].append(keys)
        rec["rows"].extend(out)
        return [h for _, h in block.columns], out
