"""Upload generated documents (PDFs, facts.json, SOPs) to GCS (SDD §15.1, D-17).

Layout: ``gs://<bucket>/documents/<relative_path>``

Uploads all files under ``backend/app/data/docs_pdf`` to the lakehouse documents
prefix. Idempotent: skips objects whose size and MD5 hash match. Never deletes objects.

    uv run --project backend python lakehouse/load/documents_upload.py [--dry-run]
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import mimetypes
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lakehouse import config as C


def get_content_type(p: Path) -> str:
    """Determine MIME content type by suffix."""
    if p.name.endswith(".facts.json") or p.suffix == ".json":
        return "application/json"
    if p.suffix == ".pdf":
        return "application/pdf"
    ctype, _ = mimetypes.guess_type(p.name)
    return ctype or "application/octet-stream"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="Print plan without uploading")
    args = ap.parse_args(argv)

    docs_dir = C.DATA_DIR / "docs_pdf"
    if not docs_dir.exists():
        print(f"SKIP: documents directory {docs_dir} does not exist (Stage O output pending)")
        return 0

    files = sorted(p for p in docs_dir.rglob("*") if p.is_file())
    if not files:
        print(f"SKIP: no files found in {docs_dir} (Stage O output pending)")
        return 0

    if args.dry_run:
        print(f"plan: upload {len(files)} files from {docs_dir} to gs://{C.BUCKET}/{C.DOCUMENTS_PREFIX}/")
        for f in files[:5]:
            rel = f.relative_to(docs_dir).as_posix()
            print(f"  plan gs://{C.BUCKET}/{C.DOCUMENTS_PREFIX}/{rel}")
        if len(files) > 5:
            print(f"  ... and {len(files) - 5} more")
        return 0

    from google.cloud import storage

    client = storage.Client(project=C.PROJECT_ID)
    bucket = client.bucket(C.BUCKET)

    def upload_one(file_path: Path) -> tuple[str, str, int]:
        rel = file_path.relative_to(docs_dir).as_posix()
        object_name = f"{C.DOCUMENTS_PREFIX}/{rel}"
        data = file_path.read_bytes()
        size = len(data)
        md5_b64 = base64.b64encode(hashlib.md5(data).digest()).decode()

        blob = bucket.get_blob(object_name)
        if blob is not None and blob.size == size and blob.md5_hash == md5_b64:
            return object_name, "skip", size

        content_type = get_content_type(file_path)
        blob_to_upload = bucket.blob(object_name)
        blob_to_upload.upload_from_string(data, content_type=content_type)
        return object_name, "upload", size

    with ThreadPoolExecutor(16) as executor:
        results = list(executor.map(upload_one, files))

    uploaded = sum(1 for _, action, _ in results if action == "upload")
    skipped = sum(1 for _, action, _ in results if action == "skip")
    total_bytes = sum(size for _, _, size in results)

    print(f"Completed: {uploaded} uploaded, {skipped} skipped, total {len(results)} files ({total_bytes} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
