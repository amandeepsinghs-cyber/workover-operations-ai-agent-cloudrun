"""One-shot corpus build: render -> scanify -> index (D-18: outputs are git-ignored and regenerated).

    cd backend && uv run python -m app.analytics.docs_pdf.build [--workers 32] [--skip-validate]

Steps
  1. render   all D1..D11 PDFs + ``.facts.json`` into ``data/docs_pdf`` (``--clean``)
  2. scanify  ~10% of D1/D5 (plus DOC-CBL-GK129-1998) into image-only PDFs
  3. validate full-corpus fact / stray-digit / scanned gate (skippable)
  4. index    ``data/index`` (document_index.parquet, doc_chunks.parquet, tfidf.pkl, corpus_manifest.json)
"""
from __future__ import annotations

import argparse
import os
import sys
import time


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=min(32, os.cpu_count() or 4))
    ap.add_argument("--field", default="all")
    ap.add_argument("--scan-fraction", type=float, default=0.10)
    ap.add_argument("--skip-validate", action="store_true")
    a = ap.parse_args(argv)

    from app.analytics.docs_pdf import index, render, scanify, validate

    w = str(a.workers)
    steps = [
        ("render", lambda: render.main(["--field", a.field, "--clean", "--workers", w])),
        ("scanify", lambda: scanify.main(["--fraction", str(a.scan_fraction), "--types", "D1,D5",
                                          "--field", a.field, "--workers", w])),
    ]
    if not a.skip_validate:
        steps.append(("validate", lambda: validate.main(["--workers", w])))
    steps.append(("index", lambda: index.main(["--workers", w])))

    for name, fn in steps:
        t0 = time.time()
        print(f"[build] {name} ...", flush=True)
        rc = fn() or 0
        print(f"[build] {name} rc={rc} in {time.time() - t0:.1f}s", flush=True)
        if rc:
            return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
