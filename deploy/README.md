# WellPulse v0.4 — deploy packaging (Stage W)

One multi-stage image, deployed as a new revision of the existing Cloud Run service
`wellpulse-app` (`workover-operations-agentic-ai` / `us-central1`). See SDD §17, D-14, D-16, D-18.

| File | Purpose |
|---|---|
| [`../Dockerfile`](../Dockerfile) | 3 stages: `node:20-slim` builds `frontend/dist` → `python:3.11-slim` + uv (`uv sync --frozen --no-dev`), landing parquet if missing, PDF corpus + index (`python -m app.analytics.docs_pdf.build`), self-check → slim non-root runtime on `$PORT` |
| [`selfcheck.py`](./selfcheck.py) | Build-time gate: data/model artefacts present and `app.main` imports |
| [`env.cloudrun.yaml`](./env.cloudrun.yaml) | Service env (`--env-vars-file` replaces every var, so `GEMINI_API_KEY` is dropped) |
| [`deploy.sh`](./deploy.sh) | `plan` (dry run, default) · `iam` · `build` · `deploy` · `smoke` · `all` |
| [`smoke_test.py`](./smoke_test.py) | health, `/api/wells/kpis`, `/api/fields`, `/api/docs/search?q=SOP`, `WS /ws/live`, SPA |
| [`../.dockerignore`](../.dockerignore), [`../.gcloudignore`](../.gcloudignore) | Keep secrets (`.env`), venvs, `node_modules`, host `frontend/dist`, the local corpus/index and tests out of the upload and the image |

## Run

```bash
deploy/deploy.sh plan              # print every command; changes nothing
deploy/deploy.sh iam               # create wellpulse-run SA if missing + additive role bindings
deploy/deploy.sh build             # Cloud Build -> AR image :v04-<sha>[-dirty] (e2-highcpu-8)
deploy/deploy.sh deploy            # new revision from that image, SDD §17.2 flags
deploy/deploy.sh smoke             # smoke test against the service URL
# or: deploy/deploy.sh all
```

Overrides: `IMAGE_TAG=…`, `RUN_SA=806277846965-compute@developer.gserviceaccount.com` (reuse the
current default compute SA instead of the dedicated one), `DEPLOY_MODE=source`
(`gcloud run deploy --source .` instead of build + `--image`), `SMOKE_URL=…`, `DRY_RUN=1`.

## Cloud Run flags (SDD §17.2)

`--memory 4Gi --cpu 2 --concurrency 20 --min-instances 1 --max-instances 1 --timeout 3600
--session-affinity --no-cpu-throttling --cpu-boost --execution-environment gen2 --port 8080
--env-vars-file deploy/env.cloudrun.yaml --labels app=wellpulse,stage=v04`.
`--max-instances 1` + session affinity is D-16 (in-memory ADK / Live sessions). The service IAM
policy is not touched (public `allUsers` invoker stays for the demo).

## Runtime service account (SDD §17.3)

`wellpulse-run@workover-operations-agentic-ai.iam.gserviceaccount.com`, additive bindings only:
`roles/aiplatform.user`, `roles/bigquery.jobUser`, `roles/logging.logWriter`,
`roles/cloudtrace.agent` (project); `roles/bigquery.dataViewer` on `wellpulse_bronze|silver|gold`;
`roles/storage.objectViewer` on `gs://workover-operations-agentic-ai-datalake`.
The deployer needs `roles/iam.serviceAccountUser` on that SA (project owners have it).

## Rollback

```bash
gcloud run services update-traffic wellpulse-app --project workover-operations-agentic-ai \
  --region us-central1 --to-revisions=<previous-revision>=100
```
`deploy.sh deploy` prints the previous ready revision before it deploys. Nothing is ever deleted.
