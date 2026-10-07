# WellPulse medallion lakehouse (Stage X, F-15)

Project `workover-operations-agentic-ai`, BigQuery location `asia-south1`, bucket `gs://workover-operations-agentic-ai-datalake`. Why BigQuery: [`decision_record.md`](./decision_record.md). All names live in [`config.py`](./config.py).

## Runbook (repo root; every step is idempotent and never drops anything)
```bash
uv run --project backend python lakehouse/ddl/generate_ddl.py        # DDL from landing parquet schemas
uv run --project backend python lakehouse/load/bronze_upload.py      # landing -> gs://.../bronze/<t>/dt=/landing_folder=/
uv run --project backend python lakehouse/load/apply_ddl.py --dry-run-only
uv run --project backend python lakehouse/load/apply_ddl.py          # datasets, bronze external, silver, doc_chunks, dossier_facts
uv run --project backend python lakehouse/load/bronze_to_silver.py   # MERGE + parquet/bronze/silver count + checksum reconciliation
(cd lakehouse/dataform && npx -y @dataform/cli@3.0.25 compile && npx -y @dataform/cli@3.0.25 run)   # Gold + assertions
uv run --project backend python lakehouse/load/export_silver.py      # gs://.../silver_exports/
# after Stage O has produced docs_pdf/ and data/index/:
uv run --project backend python lakehouse/load/documents_upload.py
uv run --project backend python lakehouse/load/doc_chunks.py
uv run --project backend python lakehouse/load/dossier_facts.py
# parity (skips without ADC):
cd backend && uv run pytest tests/integration/test_backend_parity.py -q
```
Run the app on BigQuery: `DATA_BACKEND=bigquery` (reads `wellpulse_silver`; parquet remains the default).
