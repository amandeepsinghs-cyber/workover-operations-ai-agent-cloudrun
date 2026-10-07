"""FIELD_CONFIGS registry and well-ID prefix resolution (SDD §5.1, §5.2)."""

from __future__ import annotations

from .base import (
    ClusterConfig,
    DowntimeModel,
    FacilityConfig,
    FieldConfig,
    FixtureSpec,
    ReservoirRanges,
)
from .geleki import GELEKI
from .lakhmani import LAKHMANI
from .lakwa import LAKWA

FIELD_CONFIGS: dict[str, FieldConfig] = {"Geleki": GELEKI, "Lakwa": LAKWA, "Lakhmani": LAKHMANI}

# Longest prefix first so "LKW-" / "LKM-" never shadow each other.
_PREFIXES = sorted(((c.prefix, c.field) for c in FIELD_CONFIGS.values()), key=lambda t: -len(t[0]))


def field_of(well_id: str) -> str | None:
    """Return the field for a well ID by prefix, or None if the prefix is unknown (incl. retired GLK-)."""
    wid = (well_id or "").upper()
    for prefix, field in _PREFIXES:
        if wid.startswith(prefix):
            return field
    return None


def resolve_field(name: str) -> str | None:
    """Case-insensitive field-name lookup."""
    for f in FIELD_CONFIGS:
        if f.lower() == (name or "").lower():
            return f
    return None


__all__ = [
    "FIELD_CONFIGS",
    "ClusterConfig",
    "DowntimeModel",
    "FacilityConfig",
    "FieldConfig",
    "FixtureSpec",
    "ReservoirRanges",
    "field_of",
    "resolve_field",
]
