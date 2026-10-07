"""Asset hierarchy helpers (SDD §5.1): ASSAM_ASSET → field → cluster → well.

``field_of(well_id)`` resolves the field from the well-ID prefix (``GK-`` / ``LKW-`` / ``LKM-``);
an unknown prefix (incl. retired ``GLK-``) returns ``None`` and callers answer ``UNAVAILABLE``.
There is no default field and no hero well (K-6).
"""

from __future__ import annotations

from app.analytics.generator.fields import FIELD_CONFIGS, field_of, resolve_field

ASSET = "ASSAM_ASSET"
FIELDS: tuple[str, ...] = tuple(FIELD_CONFIGS)

__all__ = ["ASSET", "FIELDS", "field_of", "resolve_field", "cluster_ids"]


def cluster_ids(field: str) -> list[str]:
    """Cluster IDs configured for a field (GGS for Lakwa/Lakhmani, fault blocks for Geleki)."""
    cfg = FIELD_CONFIGS.get(field)
    return [c.cluster_id for c in cfg.clusters] if cfg else []
