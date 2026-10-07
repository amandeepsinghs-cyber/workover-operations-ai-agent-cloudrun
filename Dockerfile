# ==============================================================================
# Dockerfile for WellPulse Cloud Run Deployment
# Serves React+Vite Frontend and FastAPI Backend
# Python deps: uv + backend/uv.lock (Stage M, D-14). requirements.txt is gone.
# ==============================================================================

FROM python:3.11-slim
WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=never

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install locked runtime deps only (no dev group) into /app/backend/.venv
RUN pip install --no-cache-dir "uv>=0.12.7,<0.13"
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --frozen --no-dev --no-install-project
ENV PATH="/app/backend/.venv/bin:${PATH}"

COPY backend/ /app/backend/
COPY frontend/dist/ /app/frontend/dist/

EXPOSE 8080

CMD ["python", "run.py"]
