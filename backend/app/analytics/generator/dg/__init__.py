"""Stage DG: synthetic data-gap tables (v0.5, F-22, D-29).

Post-processing step. It reads existing landing parquet per field and writes 6 new
tables next to them. Every row is flagged ``is_synthetic=True``. See
docs/v05_change_brief.md section 4.
"""
