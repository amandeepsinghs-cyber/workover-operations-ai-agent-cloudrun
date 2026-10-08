"""CLI: ``uv run python -m app.analytics.generator.dg --field all``."""
from __future__ import annotations

import argparse
import importlib

from .common import FIELDS, LANDING, finalize, load_field

MODULES = ("tubing_deviation", "integrity", "hazards_fishing")


def run(fields: list[str], dry_run: bool = False) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in fields:
        ctx = load_field(f)
        for m in MODULES:
            mod = importlib.import_module(f"{__package__}.{m}")
            for table, df in mod.generate(ctx).items():
                out = finalize(df, table, f)
                if not dry_run:
                    out.to_parquet(LANDING / f / f"{table}.parquet", index=False)
                counts[f"{f}.{table}"] = len(out)
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--field", default="all")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    fields = list(FIELDS) if a.field == "all" else [a.field]
    for k, v in run(fields, a.dry_run).items():
        print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
