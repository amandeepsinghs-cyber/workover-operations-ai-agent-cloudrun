# ==============================================================================
# WellPulse v0.4 — multi-stage image for Cloud Run (SDD §17.1, D-14, D-18)
#
#   stage 1  web      node:20-slim      npm ci && npm run build      -> /web/dist
#   stage 2  build    python:3.11-slim  uv sync --frozen --no-dev    -> /app/backend/.venv
#                                       landing parquet (only if missing), PDF corpus + index,
#                                       artefact self-check (fails the build if anything is missing)
#   stage 3  runtime  python:3.11-slim  venv + app + data + frontend dist, non-root, $PORT
#
# frontend/dist is NOT taken from the build context (excluded in .dockerignore/.gcloudignore);
# it is always rebuilt in stage 1. The PDF corpus + index are git-ignored and always rebuilt in
# stage 2. No BuildKit-only syntax (heredocs, cache mounts): Cloud Build may use the legacy builder.
# Build:  deploy/deploy.sh  (gcloud builds submit --machine-type e2-highcpu-8 ...)
# ==============================================================================

# ---------------------------------------------------------------- stage 1: web
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
# The committed lockfile pins "resolved" URLs to the Google-internal npm airlock proxy, which is
# unreachable from Cloud Build (npm then dies with "Exit handler never called" and installs
# nothing). Point them at the public registry for this build only; `integrity` hashes in the
# lockfile are still verified, so the exact same tarballs are installed. Host lockfile untouched.
RUN sed -i -E 's#"resolved": "https?://airlock-proxy\.uplink\.goog(:[0-9]+)?/npm/[^/]+/[^/]+/#"resolved": "https://registry.npmjs.org/#' package-lock.json \
 && npm config set registry https://registry.npmjs.org/ \
 && npm ci --no-audit --no-fund \
 && test -x node_modules/.bin/tsc && test -x node_modules/.bin/vite
COPY frontend/ ./
RUN npm run build && test -f dist/index.html

# -------------------------------------------------------------- stage 2: build
FROM python:3.11-slim AS build
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/backend/.venv
# uv pinned to the lockfile toolchain minor (D-14); pip only bootstraps uv.
RUN pip install --no-cache-dir "uv>=0.12.7,<0.13"
WORKDIR /app/backend

# Locked runtime deps only (no dev group). Layer cached until pyproject/uv.lock change.
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --frozen --no-dev --no-install-project

ENV PATH="/app/backend/.venv/bin:${PATH}"
COPY backend/ ./

# D-18: landing parquet is committed; regenerate only if it is missing from the context.
RUN if [ ! -f app/data/landing/asset/field_targets.parquet ]; then \
        echo "[build] landing parquet missing -> generating"; \
        python -m app.analytics.generator.generate --field all --start 2021-10-01 --end 2026-09-30; \
    else echo "[build] landing parquet present (committed)"; fi

# D-18: synthetic PDF corpus (D1..D11 + SOPs) + retrieval index are always built here
# (seeded, deterministic): render -> scanify -> validate -> index.
RUN python -m app.analytics.docs_pdf.build

# Artefact self-check (SDD §17.1 `selfcheck`): fails the build if data/model artefacts are
# missing or app.main cannot import with the baked-in data.
COPY deploy/selfcheck.py /tmp/selfcheck.py
RUN python /tmp/selfcheck.py && rm -f /tmp/selfcheck.py

# Defence in depth: never ship tests or a local .env (both are also in .dockerignore).
RUN rm -rf /app/backend/tests /app/backend/.env

# ------------------------------------------------------------ stage 3: runtime
FROM python:3.11-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PORT=8080 \
    PATH="/app/backend/.venv/bin:${PATH}"

RUN groupadd --system --gid 10001 wellpulse \
 && useradd --system --uid 10001 --gid wellpulse --home-dir /home/wellpulse --create-home wellpulse

WORKDIR /app/backend
# The venv path is identical in build and runtime (/app/backend/.venv) and both stages use the
# same python:3.11-slim interpreter in /usr/local/bin, so the venv's symlinks stay valid.
# Files stay root-owned (read-only for the app user): the runtime writes nothing to disk.
COPY --from=build /app/backend /app/backend
COPY --from=web /web/dist /app/frontend/dist

USER wellpulse
EXPOSE 8080
# `sh -c` so Cloud Run's $PORT is honoured; `exec` keeps uvicorn as PID 1 (clean SIGTERM).
# --ws-ping-interval 20 keeps /ws/live alive behind the Cloud Run front end (SDD §17.1).
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --ws-ping-interval 20 --proxy-headers --forwarded-allow-ips '*'"]
