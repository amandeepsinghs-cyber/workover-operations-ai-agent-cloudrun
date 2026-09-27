# ==============================================================================
# Multi-Stage Dockerfile for WellPulse Cloud Run Deployment
# Builds React+Vite Frontend and serves via FastAPI Backend in a single container
# ==============================================================================

# Stage 1: Build Frontend Assets
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# Stage 2: Python Runtime Environment
FROM python:3.11-slim AS runner
WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/backend/
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

WORKDIR /app/backend

EXPOSE 8080

CMD ["python", "run.py"]
