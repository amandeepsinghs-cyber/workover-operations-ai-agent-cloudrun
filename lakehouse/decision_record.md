# Decision record: where WellPulse production data should live (Stage X, F-15)

**Decision: production time series live in BigQuery (Silver/Gold, `asia-south1`); raw files and PDFs live in GCS (Bronze). The demo app still reads parquet by default and switches to BigQuery with `DATA_BACKEND=bigquery`. A parity test shows both backends return the same results.**

> Verbatim anchor (T2 / §3): *"showcase that in the Medallion architecture, and then we can … create a let's say Lakehouse"*; *"production data … whether it should go ultimately into BigQuery or if there is a better database"*.
> This record backs SDD §15.2 and gives the agent its answer to BDD F-15 S02 ("Where does this data live, and why BigQuery?").

## 1. Context (measured, 2026-10-07)
| Fact | Value | Source |
|---|---|---|
| Wells | 412 (Geleki 142, Lakwa 160, Lakhmani 110) | `well_master` |
| Window | 2021-10-01 → 2026-09-30 (60 months), AS_OF 2026-09-23 | D-2, D-15 |
| `daily_production` rows | 752,312 | landing parquet = Bronze = Silver (reconciled) |
| All 23 landing tables | 839,938 rows, 12 MB parquet | `lakehouse/load/bronze_upload.py` |
| Dominant query shapes | field × month roll-ups over 5 years; one well's history; field comparisons; screening at AS_OF | TC-028, TC-017, TC-024, TC-020 |
| Write pattern | daily batch (generator / future SCADA allocation), append-mostly | SDD §5.5 |

## 2. Options considered
| Option | Fit for this workload | Verdict |
|---|---|---|
| **BigQuery** (Silver/Gold) | Columnar storage with partitioning and clustering. Five-year roll-ups over all wells finish in seconds. Native to Dataform (Gold), Looker and Gemini. Supports streaming ingest. 0.75 M daily rows is tiny. Even 1-minute SCADA for 412 wells (~216 M rows/yr) is routine. Pay per byte scanned: partition pruning on `production_date` and clustering on `field, well_id` keep app queries small. | ✅ **Chosen** for Silver/Gold and analytics |
| Bigtable | High-QPS millisecond point reads/writes on wide time series keyed by `well#timestamp` | ❌ Not now. Use it only if a live per-second SCADA tile is added. It cannot do field × month aggregation without another engine. |
| AlloyDB / Cloud SQL (Postgres) | OLTP: approvals, `decision_log`, the draft-plan workflow, ADK sessions (D-16) | ❌ Not for time series: row-store scans over multi-year roll-ups, and capacity to manage. ✅ Optional later for workflow and sessions. |
| Spanner | Global, strongly consistent OLTP | ❌ Overkill for a single-region analytics workload |
| Parquet in the container image | Zero latency, zero cost, works offline | ✅ Default runtime for the demo (`DATA_BACKEND=parquet`) |
| GCS + external tables only (no Silver) | Cheap, but no partition/cluster pruning on parquet external tables, no DML, no clustering | ❌ This is Bronze only (immutable raw) |

## 3. Why BigQuery wins on this workload
1. **The query shape is analytical.** Every headline question (L1–L3: *"5-year field-wise production"*, *"which field is not performing"*, *"how many wells are sick"*) is an aggregation over many wells and many days. Column stores do this cheaply; OLTP row stores and Bigtable do not.
2. **Physical design matches the access path.** Silver `daily_production` is `PARTITION BY production_date CLUSTER BY field, well_id` (V§5). App reads always carry `field`, `_landing_folder` and `production_date <= AS_OF` predicates, so blocks outside the requested field and period are pruned.
3. **One platform from raw data to KPI.** GCS Bronze → BigQuery Silver (`MERGE`, idempotent) → Dataform Gold (`field_kpi_monthly`, `sick_well_screen`, `intervention_features`, `nba_lookup`, `dossier_facts`), with assertions for uniqueness and Silver↔Gold reconciliation (±0.1%).
4. **Scale headroom without re-platforming.** Moving from daily to 1-minute data (~290× the rows) stays inside BigQuery's normal operating range. Only a sub-second live view would justify adding Bigtable next to it.
5. **Cost controls built in.** Every job carries `maximum_bytes_billed` and labels (`app=wellpulse`, `stage=x` / `component=api`, `datacloud=jetski`).

## 4. Consequences
- **Two runtime backends, one code path.** `BigQueryRepository` subclasses `ParquetRepository` and overrides only the raw read (`_read`). All adapters and routes run unchanged on both backends. `tests/integration/test_backend_parity.py` asserts identical frames, identical repository outputs and identical REST responses for the fixture wells.
- **The demo stays offline-safe.** Cloud Run keeps parquet as the default. BigQuery is an opt-in that proves the Lakehouse story.
- **Documents.** PDFs and `facts.json` are mirrored to `gs://…/documents/`. `wellpulse_silver.doc_chunks` mirrors the TF-IDF index (D-17). `wellpulse_gold.dossier_facts` holds the grounding facts (the V§5 "grounding cache", derived interpretation). Vertex AI Search remains a drop-in behind TC-026.
- **Revisit triggers:**
  - a live per-second SCADA view → add Bigtable for the hot path;
  - approval/workflow writes → add AlloyDB/Cloud SQL for OLTP;
  - multi-region operations → re-evaluate.

## 5. Layout (as built)
```
gs://workover-operations-agentic-ai-datalake/
  bronze/<table>/dt=2026-09-23/landing_folder=<asset|geleki|lakwa|lakhmani>/part-000.parquet
  documents/<field>/<Dxx>/<doc_id>.pdf (+ .facts.json)        # when Stage O corpus exists
  silver_exports/<table>/dt=2026-09-23/<table>-*.parquet
BigQuery (asia-south1):
  wellpulse_bronze.*   23 external tables (hive keys dt, landing_folder)
  wellpulse_silver.*   23 contract tables + doc_chunks
  wellpulse_gold.*     field_kpi_monthly, sick_well_screen (view), intervention_features, nba_lookup, dossier_facts (+ assertions)
```
