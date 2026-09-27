#!/usr/bin/env bash
# ==============================================================================
# WellPulse: Local Platform Launcher
# Boots FastAPI Backend (port 8000) and React+Vite Frontend (port 5173)
# ==============================================================================

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/backend"
FRONTEND_DIR="${PROJECT_ROOT}/frontend"

echo "======================================================================"
echo "           WellPulse - Energy Well Operations & Voice AI              "
echo "======================================================================"

# 1. Check prerequisites
command -v python3 >/dev/null 2>&1 || { echo "[!] Error: python3 is required."; exit 1; }
command -v node >/dev/null 2>&1 || { echo "[!] Error: node is required."; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "[!] Error: npm is required."; exit 1; }

# 2. Setup Backend Virtualenv
if [ ! -d "${BACKEND_DIR}/.venv" ]; then
    echo "[*] Initializing backend virtual environment..."
    python3 -m venv "${BACKEND_DIR}/.venv"
    "${BACKEND_DIR}/.venv/bin/pip" install -r "${BACKEND_DIR}/requirements.txt"
fi

# 3. Ensure synthetic dataset is generated
if [ ! -f "${BACKEND_DIR}/app/data/wells_data.json" ]; then
    echo "[*] Generating synthetic 24-month well telemetry..."
    "${BACKEND_DIR}/.venv/bin/python" "${BACKEND_DIR}/app/services/data_generator.py"
fi

# 4. Check Frontend dependencies
if [ ! -d "${FRONTEND_DIR}/node_modules" ]; then
    echo "[*] Installing frontend npm dependencies..."
    (cd "${FRONTEND_DIR}" && npm install)
fi

# 5. Clean up any existing background tasks on exit
cleanup() {
    echo ""
    echo "[*] Shutting down WellPulse services..."
    if [ -n "${BACKEND_PID}" ]; then
        kill "${BACKEND_PID}" 2>/dev/null || true
    fi
    if [ -n "${FRONTEND_PID}" ]; then
        kill "${FRONTEND_PID}" 2>/dev/null || true
    fi
    echo "[✓] All WellPulse services terminated."
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# 6. Launch Backend
echo "[*] Starting FastAPI Backend on http://localhost:8002..."
(cd "${BACKEND_DIR}" && "${BACKEND_DIR}/.venv/bin/python" run.py) &
BACKEND_PID=$!

# Wait for backend health check
echo "[*] Waiting for backend to become ready..."
for i in {1..30}; do
    if curl -s http://localhost:8002/api/health >/dev/null 2>&1; then
        echo "[✓] Backend is healthy!"
        break
    fi
    sleep 0.5
done

# 7. Launch Frontend
echo "[*] Starting React + Vite Frontend on http://localhost:5180..."
(cd "${FRONTEND_DIR}" && npm run dev -- --host 0.0.0.0 --port 5180) &
FRONTEND_PID=$!

echo "======================================================================"
echo "[✓] WellPulse is live and running!"
echo "    • Operations Dashboard: http://localhost:5180"
echo "    • Backend API / Docs:   http://localhost:8002/docs"
echo "======================================================================"
echo "Press Ctrl+C to stop all services."

wait
