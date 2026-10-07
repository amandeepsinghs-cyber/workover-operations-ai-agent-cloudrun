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


# ------------------------------------------------------------------------------------------------
# TC-025 query_hierarchy (Stage T, SDD §6.2) — counts come from well_master / cluster_master only.
# ------------------------------------------------------------------------------------------------
def query_hierarchy(asset: str = ASSET, field: str | None = None, cluster_id: str | None = None):
    """TC-025. ``Hierarchy{asset, fields[{field, n_wells, n_active, clusters[{cluster_id, n_wells, …}]}]}``.

    Unknown asset / field / cluster → ``UNAVAILABLE`` naming the valid values (never guessed, BDD-F05-S04).
    """
    import time

    import pandas as pd

    from .common import ToolResult, ToolStatus, build_provenance, load_table, unavailable

    t0 = time.perf_counter()
    params = {"asset": asset, "field": field, "cluster_id": cluster_id}
    if asset and str(asset).strip().upper() not in (ASSET, "ASSAM", "ALL"):
        return unavailable("TC-025", params, t0, ["asset"], f"Unknown asset '{asset}'. Only {ASSET} is in the dataset.")
    fields = list(FIELDS)
    if field:
        f = resolve_field(field)
        if f is None:
            return unavailable("TC-025", params, t0, ["field"],
                               f"'{field}' is not in the dataset. Fields: {', '.join(FIELDS)}.")
        fields = [f]
    wm = load_table("well_master")
    cm = load_table("cluster_master")
    meta = {r["cluster_id"]: r for _, r in cm.iterrows()} if len(cm) else {}
    out = []
    for f in fields:
        w = wm[wm["field"] == f]
        clusters = []
        for cid in sorted(w["cluster_id"].dropna().unique()):
            if cluster_id and cid != cluster_id:
                continue
            cw = w[w["cluster_id"] == cid]
            m = meta.get(cid)
            clusters.append({
                "cluster_id": str(cid),
                "cluster_type": str(m["cluster_type"]) if m is not None else None,
                "n_wells": int(len(cw)),
                "n_active": int((cw["status"] == "ACTIVE").sum()),
                "center_lat": float(m["center_lat"]) if m is not None and pd.notna(m["center_lat"]) else None,
                "center_lon": float(m["center_lon"]) if m is not None and pd.notna(m["center_lon"]) else None,
            })
        if cluster_id and not clusters:
            continue
        out.append({"field": f, "n_wells": int(len(w)), "n_active": int((w["status"] == "ACTIVE").sum()),
                    "clusters": clusters})
    if cluster_id and not out:
        return unavailable("TC-025", params, t0, ["cluster_id"], f"Cluster '{cluster_id}' not found.")
    val = {"asset": ASSET, "fields": out, "n_wells": int(sum(x["n_wells"] for x in out))}
    msg = "; ".join(f"{x['field']}: {x['n_wells']} wells in {len(x['clusters'])} clusters "
                    f"({', '.join(c['cluster_id'] for c in x['clusters'])})" for x in out)
    return ToolResult(ToolStatus.OK, val, [], msg + ".", build_provenance("TC-025", params, t0))
