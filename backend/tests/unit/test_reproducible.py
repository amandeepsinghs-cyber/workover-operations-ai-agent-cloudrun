"""Reproducibility tests (V-N3) for deterministic data generation across runs."""

from __future__ import annotations

from pathlib import Path

import pytest

from app import settings
from app.analytics.generator import generate


@pytest.fixture(scope="module")
def landing() -> Path:
    """Return landing path if data is generated, else skip."""
    landing_dir = settings.LANDING_DIR
    if not (landing_dir / "asset" / "field_targets.parquet").exists():
        pytest.skip("landing data not generated; run app.analytics.generator.generate")
    return landing_dir


def test_two_runs_byte_identical(tmp_path: Path) -> None:
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"

    ret_a = generate.main([
        "--field", "Lakhmani",
        "--start", "2021-10-01",
        "--end", "2026-09-30",
        "--out", str(out_a),
    ])
    ret_b = generate.main([
        "--field", "Lakhmani",
        "--start", "2021-10-01",
        "--end", "2026-09-30",
        "--out", str(out_b),
    ])

    assert ret_a == 0, f"Run a exited with code {ret_a}"
    assert ret_b == 0, f"Run b exited with code {ret_b}"

    files_a = {p.relative_to(out_a) for p in out_a.rglob("*.parquet")}
    files_b = {p.relative_to(out_b) for p in out_b.rglob("*.parquet")}

    assert len(files_a) > 0, "No parquet files generated in run a"
    assert files_a == files_b, f"File set mismatch: {files_a ^ files_b}"

    for rel_path in sorted(files_a):
        bytes_a = (out_a / rel_path).read_bytes()
        bytes_b = (out_b / rel_path).read_bytes()
        assert bytes_a == bytes_b, f"File {rel_path} differs between run a and run b"


def test_geleki_run_matches_committed_landing(tmp_path: Path, landing: Path) -> None:
    out_g = tmp_path / "g"
    ret = generate.main([
        "--field", "Geleki",
        "--start", "2021-10-01",
        "--end", "2026-09-30",
        "--out", str(out_g),
    ])
    assert ret == 0, f"Geleki generation failed with exit code {ret}"

    generated_files = sorted((out_g / "geleki").glob("*.parquet"))
    assert len(generated_files) > 0, "No Geleki parquet files generated"

    for gen_path in generated_files:
        committed_path = landing / "geleki" / gen_path.name
        assert committed_path.exists(), f"Committed file missing: {committed_path}"
        assert gen_path.read_bytes() == committed_path.read_bytes(), (
            f"Generated file {gen_path.name} does not match committed landing file {committed_path}"
        )
