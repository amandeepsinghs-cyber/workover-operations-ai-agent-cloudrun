"""Formation tops generator for subsurface stratigraphic layering.

Stage N / WellPulse v0.4 synthetic data generation.
"""

import numpy as np
import pandas as pd

LITHOLOGY_MAP = {
    "Alluvium": "Unconsolidated sand and clay",
    "Namsang": "Sandstone with clay and pebble beds",
    "Girujan": "Mottled clay",
    "Tipam": "Massive sandstone, minor shale",
    "Barail": "Sand-shale-coal alternation",
    "Kopili": "Shale with thin sandstone",
    "Lakadong": "Limestone and sandstone (Sylhet)",
}


def generate_formation_tops(wells: pd.DataFrame, seed: int) -> pd.DataFrame:
    """Generate formation tops table for given wells.

    Columns:
        well_id, field, cluster_id, formation, top_md_m, bottom_md_m, lithology
    """
    rng = np.random.default_rng(seed)
    columns = [
        "well_id",
        "field",
        "cluster_id",
        "formation",
        "top_md_m",
        "bottom_md_m",
        "lithology",
    ]
    if wells.empty:
        return pd.DataFrame(columns=columns)

    records = []
    for _, row in wells.iterrows():
        wid = row["well_id"]
        fld = row["field"]
        cid = row["cluster_id"]
        current_zone = str(row["current_zone"])
        perf_top_m = float(row["perf_top_m"])
        perf_bottom_m = float(row["perf_bottom_m"])
        td_md_m = float(row["total_depth_md_m"])

        # Per well, draw ALL six thicknesses first in that order, plus offset
        t_all = float(rng.uniform(300.0, 500.0))
        t_nam = float(rng.uniform(400.0, 700.0))
        t_tip = float(rng.uniform(450.0, 650.0))
        t_bar = float(rng.uniform(600.0, 900.0))
        t_kop = float(rng.uniform(150.0, 300.0))
        t_lak = float(rng.uniform(80.0, 200.0))
        offset = float(rng.uniform(40.0, 150.0))

        top_z = perf_top_m - offset

        if current_zone == "Tipam":
            thick_tip = max(t_tip, (perf_bottom_m - top_z) + 20.0)
            top_tip = top_z
            bot_tip = top_tip + thick_tip
            top_bar = bot_tip
            bot_bar = top_bar + t_bar
            top_kop = bot_bar
            bot_kop = top_kop + t_kop
            top_lak = bot_kop
            bot_lak = top_lak + t_lak
            upper_deep_top = top_tip

        elif current_zone == "Barail":
            thick_bar = max(t_bar, (perf_bottom_m - top_z) + 20.0)
            top_bar = top_z
            bot_bar = top_bar + thick_bar
            bot_tip = top_bar
            top_tip = bot_tip - t_tip
            top_kop = bot_bar
            bot_kop = top_kop + t_kop
            top_lak = bot_kop
            bot_lak = top_lak + t_lak
            upper_deep_top = top_tip

        elif current_zone == "Lakadong":
            thick_lak = max(t_lak, (perf_bottom_m - top_z) + 20.0)
            top_lak = top_z
            bot_lak = top_lak + thick_lak
            bot_kop = top_lak
            top_kop = bot_kop - t_kop
            bot_bar = top_kop
            top_bar = bot_bar - t_bar
            bot_tip = top_bar
            top_tip = bot_tip - t_tip
            upper_deep_top = top_tip

        else:
            raise ValueError(f"Unknown current_zone: {current_zone}")

        # Alluvium, Namsang, Girujan
        gir_thick = upper_deep_top - (t_all + t_nam)
        if gir_thick < 100.0:
            target_nam_bottom = upper_deep_top - 100.0
            if target_nam_bottom - t_all >= 50.0:
                all_bottom = t_all
                nam_bottom = target_nam_bottom
            else:
                nam_bottom = target_nam_bottom
                target_all_bottom = nam_bottom - 50.0
                all_bottom = max(50.0, target_all_bottom)
        else:
            all_bottom = t_all
            nam_bottom = t_all + t_nam

        b0 = 0.0
        b1 = round(all_bottom, 1)
        b2 = round(nam_bottom, 1)
        b3 = round(upper_deep_top, 1)
        b4 = round(bot_tip, 1)
        b5 = round(bot_bar, 1)
        b6 = round(bot_kop, 1)
        b7 = round(bot_lak, 1)

        candidates = [
            ("Alluvium", b0, b1),
            ("Namsang", b1, b2),
            ("Girujan", b2, b3),
            ("Tipam", b3, b4),
            ("Barail", b4, b5),
            ("Kopili", b5, b6),
            ("Lakadong", b6, b7),
        ]

        td_rounded = round(td_md_m, 1)
        kept = []
        for form_name, top_m, bot_m in candidates:
            if top_m < td_rounded:
                kept.append([form_name, top_m, bot_m])

        if kept:
            kept[-1][2] = td_rounded

        for form_name, top_m, bot_m in kept:
            records.append({
                "well_id": wid,
                "field": fld,
                "cluster_id": cid,
                "formation": form_name,
                "top_md_m": top_m,
                "bottom_md_m": bot_m,
                "lithology": LITHOLOGY_MAP[form_name],
            })

    return pd.DataFrame(records, columns=columns)
