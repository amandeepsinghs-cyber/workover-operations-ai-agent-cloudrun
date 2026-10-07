#!/usr/bin/env bash
# ==============================================================================
# WellPulse v0.4 — Cloud Run packaging + deploy (Stage W, SDD §17, D-14, D-16, D-18)
#
#   deploy/deploy.sh plan      print every command, change nothing (default)
#   deploy/deploy.sh iam       ensure runtime SA + additive role bindings (never removes any)
#   deploy/deploy.sh build     Cloud Build the multi-stage image -> Artifact Registry (no deploy)
#   deploy/deploy.sh deploy    new revision of wellpulse-app from $IMAGE (or --source, see below)
#   deploy/deploy.sh smoke     deploy/smoke_test.py against the service URL
#   deploy/deploy.sh all       iam -> build -> deploy -> smoke
#
# Env overrides:
#   IMAGE_TAG=v04-<sha>      image tag (default: v04-<git short sha>[-dirty])
#   RUN_SA=<email>           runtime SA (default dedicated wellpulse-run@…; SDD §17.3)
#   DEPLOY_MODE=image|source image (default): build with gcloud builds submit on e2-highcpu-8,
#                            then `run deploy --image`. source: `gcloud run deploy --source .`
#                            (Cloud Run's default build machine; corpus build is slower there).
#   DRY_RUN=1                print commands instead of running them (implied by `plan`)
#
# Never deletes services, revisions, images or IAM bindings. Rollback:
#   gcloud run services update-traffic wellpulse-app --region us-central1 \
#     --project workover-operations-agentic-ai --to-revisions=<previous>=100
# ==============================================================================
set -euo pipefail

PROJECT="workover-operations-agentic-ai"
REGION="us-central1"
SERVICE="wellpulse-app"
AR_REPO="cloud-run-source-deploy"
BUCKET="workover-operations-agentic-ai-datalake"
BQ_DATASETS=(wellpulse_bronze wellpulse_silver wellpulse_gold)
SA_NAME="wellpulse-run"
RUN_SA="${RUN_SA:-${SA_NAME}@${PROJECT}.iam.gserviceaccount.com}"
DEPLOY_MODE="${DEPLOY_MODE:-image}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

# The shell may export the WRONG project (og-agentic-ecosystem): every gcloud call below passes
# --project explicitly, and we unset it so nothing inherits it by accident.
unset GOOGLE_CLOUD_PROJECT CLOUDSDK_CORE_PROJECT || true

if [ -z "${IMAGE_TAG:-}" ]; then
    sha="$(git rev-parse --short HEAD 2>/dev/null || echo nogit)"
    dirty="$(git status --porcelain 2>/dev/null | grep -q . && echo -dirty || true)"
    IMAGE_TAG="v04-${sha}${dirty}"
fi
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${AR_REPO}/${SERVICE}:${IMAGE_TAG}"

# Cloud Run flags (SDD §17.2). D-16: one instance + session affinity (in-memory ADK/Live sessions).
RUN_FLAGS=(
    --project "${PROJECT}" --region "${REGION}"
    --service-account "${RUN_SA}"
    --memory 4Gi --cpu 2 --concurrency 20
    --min-instances 1 --max-instances 1
    --timeout 3600 --session-affinity --no-cpu-throttling --cpu-boost
    --execution-environment gen2
    --port 8080
    --env-vars-file deploy/env.cloudrun.yaml
    --labels app=wellpulse,stage=v04
    --quiet
)
# --env-vars-file REPLACES all env vars on the service => the legacy GEMINI_API_KEY is removed.
# Public access is unchanged: we do not touch the service IAM policy (allUsers invoker stays).

# Print every command; execute unless DRY_RUN=1. Failures stop the script (set -e).
x() {
    printf '+'; printf ' %q' "$@"; printf '\n'
    if [ "${DRY_RUN:-0}" = "1" ]; then return 0; fi
    "$@"
}
# Additive binding that must not abort the whole run (e.g. bq CLI without dataset IAM support).
x_soft() {
    x "$@" || echo "[!] WARN: command failed (non-fatal, grant manually if needed): $*" >&2
}

step_iam() {
    echo "== iam: runtime service account ${RUN_SA} (additive only)"
    if [ "${RUN_SA}" = "${SA_NAME}@${PROJECT}.iam.gserviceaccount.com" ]; then
        if [ "${DRY_RUN:-0}" = "1" ] || ! gcloud iam service-accounts describe "${RUN_SA}" --project "${PROJECT}" >/dev/null 2>&1; then
            x gcloud iam service-accounts create "${SA_NAME}" --project "${PROJECT}" \
                --display-name "WellPulse Cloud Run runtime (v0.4)" \
                --description "Least-privilege runtime SA for wellpulse-app (SDD 17.3)"
        else
            echo "   SA exists"
        fi
    fi
    local member="serviceAccount:${RUN_SA}"
    # Project-level roles (SDD §17.3). add-iam-policy-binding is additive and idempotent.
    for role in roles/aiplatform.user roles/bigquery.jobUser roles/logging.logWriter roles/cloudtrace.agent; do
        x gcloud projects add-iam-policy-binding "${PROJECT}" --member "${member}" --role "${role}" \
            --condition None --quiet --format none
    done
    # BigQuery read on the wellpulse_* datasets only (DATA_BACKEND=bigquery).
    for ds in "${BQ_DATASETS[@]}"; do
        x_soft bq add-iam-policy-binding --member "${member}" --role roles/bigquery.dataViewer \
            "${PROJECT}:${ds}"
    done
    # Optional: read PDFs from the datalake bucket instead of the image.
    x gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" --project "${PROJECT}" \
        --member "${member}" --role roles/storage.objectViewer --format none
}

step_build() {
    echo "== build: ${IMAGE}"
    # e2-highcpu-8: the corpus build (≈21k PDFs render -> scanify -> validate -> index) is CPU bound.
    x gcloud builds submit . --project "${PROJECT}" --region "${REGION}" \
        --tag "${IMAGE}" --machine-type e2-highcpu-8 --timeout 3600s
}

step_deploy() {
    echo "== deploy: ${SERVICE} (${DEPLOY_MODE})"
    if [ "${DRY_RUN:-0}" != "1" ]; then
        prev="$(gcloud run services describe "${SERVICE}" --project "${PROJECT}" --region "${REGION}" \
            --format 'value(status.latestReadyRevisionName)' 2>/dev/null || true)"
        echo "   previous ready revision (rollback target): ${prev:-<none>}"
    fi
    if [ "${DEPLOY_MODE}" = "source" ]; then
        x gcloud run deploy "${SERVICE}" --source . "${RUN_FLAGS[@]}"
    else
        x gcloud run deploy "${SERVICE}" --image "${IMAGE}" "${RUN_FLAGS[@]}"
    fi
}

service_url() {
    gcloud run services describe "${SERVICE}" --project "${PROJECT}" --region "${REGION}" \
        --format 'value(status.url)'
}

step_smoke() {
    local url="${SMOKE_URL:-}"
    if [ -z "${url}" ]; then
        if [ "${DRY_RUN:-0}" = "1" ]; then url="https://wellpulse-app-bowxi5445q-uc.a.run.app"; else url="$(service_url)"; fi
    fi
    echo "== smoke: ${url}"
    # websockets ships with uvicorn[standard] in the backend lock, so reuse that environment.
    x bash -c "cd backend && uv run --frozen --no-dev python ../deploy/smoke_test.py '${url}'"
}

cmd="${1:-plan}"
case "${cmd}" in
    plan)   DRY_RUN=1; step_iam; step_build; step_deploy; step_smoke ;;
    iam)    step_iam ;;
    build)  step_build ;;
    deploy) step_deploy ;;
    smoke)  step_smoke ;;
    all)    step_iam; [ "${DEPLOY_MODE}" = "image" ] && step_build; step_deploy; step_smoke ;;
    *) echo "usage: $0 {plan|iam|build|deploy|smoke|all}" >&2; exit 2 ;;
esac
