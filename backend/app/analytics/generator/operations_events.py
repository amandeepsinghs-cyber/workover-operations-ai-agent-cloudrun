"""operations_events assembly (SDD §5.3/§5.4; V-N2).

Native / prepend events are emitted by ``WellSim`` from the same state arrays as the daily rows.
For the frozen Geleki core, events are *derived* from the v0.3.0 status episodes: every
``WAITING_ON_RIG`` episode becomes a ``WAIT_ON_RIG`` event whose ``trigger_ref`` is the workover the
well was waiting for (the next ``UNDER_WORKOVER`` episode of that well).
"""

from __future__ import annotations

import pandas as pd

from .simulate import FACTOR

COLUMNS = ["event_id", "well_id", "field", "cluster_id", "start_date", "end_date", "event_type", "factor_class",
           "controllable", "responsible_function", "trigger_ref", "is_prepend"]


def derive_core_events(status: pd.DataFrame, field: str, cluster_of: dict) -> pd.DataFrame:
    rows = []
    for wid, g in status.groupby("well_id", sort=False):
        g = g.reset_index(drop=True)
        for i, r in g.iterrows():
            if r["status"] != "WAITING_ON_RIG":
                continue
            if r["end_date"] is not None and r["end_date"] < r["start_date"]:
                continue    # v0.3.0 emits zero-length episodes (end < start); nothing happened
            nxt = g.iloc[i + 1:]
            wo = nxt[nxt["status"] == "UNDER_WORKOVER"]["workover_id"]
            fc, ctrl, fn = FACTOR["WAIT_ON_RIG"]
            rows.append(dict(well_id=wid, field=field, cluster_id=cluster_of.get(wid), start_date=r["start_date"],
                             end_date=r["end_date"], event_type="WAIT_ON_RIG", factor_class=fc, controllable=ctrl,
                             responsible_function=fn, trigger_ref=wo.iloc[0] if len(wo) else None, is_prepend=False))
    return pd.DataFrame(rows)


def assemble(frames: list[pd.DataFrame], field: str) -> pd.DataFrame:
    df = pd.concat([f for f in frames if f is not None and len(f)], ignore_index=True)
    df = df.sort_values(["start_date", "well_id", "event_type", "end_date"], kind="mergesort").reset_index(drop=True)
    df.insert(0, "event_id", [f"OE-{field.upper()}-{i + 1:05d}" for i in range(len(df))])
    return df[COLUMNS]
