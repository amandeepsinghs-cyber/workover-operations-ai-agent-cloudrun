# ==============================================================================
# Dockerfile for WellPulse Cloud Run Deployment
# Serves React+Vite Frontend and FastAPI Backend
# ==============================================================================

FROM python:3.11-slim
WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/backend/
COPY frontend/dist/ /app/frontend/dist/

WORKDIR /app/backend

EXPOSE 8080

CMD ["python", "run.py"]
