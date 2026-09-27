# Build & Local Run Guide (`build.md`)
## WellPulse: Energy Well Operations & Voice AI Platform

**Document Version:** 1.0.0  
**Target Environment:** Local Workstation / Laptop (Linux, macOS, Windows WSL)  

---

## 1. Prerequisites

Before building and running WellPulse, verify that your local machine has the following tools installed:

| Tool | Minimum Version | Recommended Version | Verification Command |
|---|---|---|---|
| **Python** | 3.10+ | 3.11 / 3.12 | `python3 --version` |
| **Node.js** | 18.0+ | 20.x LTS | `node --version` |
| **npm** | 9.0+ | 10.x | `npm --version` |
| **Modern Web Browser** | Chrome 100+ or Edge 100+ | Latest Chrome | Tested with Web Speech API |

---

## 2. Repository Structure

```
wellpulse/
├── archive/                     # Preserved prototypes for learning & reference
│   ├── LEARNINGS.md             # Key architectural takeaways from legacy code
│   ├── drilling-dashboard/      # Legacy Streamlit prototype 1
│   └── drilling-intelligence/   # Legacy Streamlit/Vertex prototype 2
├── docs/                        # Specifications & Architecture
│   ├── BRD.md                   # Business Requirements Document
│   ├── BDD.md                   # Behavior-Driven Development (Gherkin)
│   ├── SDD.md                   # Software Design Document
│   ├── features.md              # Feature Catalog (MoSCoW prioritized)
│   ├── build.md                 # This build and local execution guide
│   └── checklist.md             # Step-by-step implementation & verification checklist
├── backend/                     # Python FastAPI Service
│   ├── app/
│   │   ├── api/                 # Endpoints (/wells, /chat, /recommendations)
│   │   ├── core/                # Configuration and LLM client setup
│   │   ├── services/            # Telemetry generator, context builder, diagnostics
│   │   └── data/                # Generated 24-month well dataset (wells_data.json)
│   ├── requirements.txt         # Python dependencies
│   └── run.py                   # Backend entrypoint (port 8000)
├── frontend/                    # React + Vite + Tailwind Client
│   ├── public/                  # Static assets & icons
│   ├── src/
│   │   ├── components/
│   │   │   ├── map/             # Leaflet GIS Map & custom markers
│   │   │   ├── telemetry/       # 24-Month Recharts (BOPD, MCFD, Pressures)
│   │   │   ├── timeline/        # Workover & Intervention history cards
│   │   │   ├── agent/           # Voice AI assistant & waveform visualizer
│   │   │   └── common/          # KPI cards, badges, search bar, filter chips
│   │   ├── context/             # Global WellContext (selected well, status filters)
│   │   ├── types/               # TypeScript interfaces
│   │   ├── App.tsx              # Split-pane layout
│   │   └── main.tsx             # Application bootstrap
│   ├── package.json             # Frontend dependencies
│   ├── tailwind.config.js       # Dark SCADA theme colors
│   └── vite.config.ts           # Vite bundler configuration & API proxy
├── scripts/                     # Helper maintenance scripts
├── run_local.sh                 # Unified one-command startup script
└── README.md                    # Project landing page
```

---

## 3. Environment Configuration

Create a `.env` file in `backend/` or the root directory if you wish to use live Google Gemini models:

```bash
# Optional: Live Gemini API Key (If omitted, system uses built-in Local Petroleum Expert Engine)
GEMINI_API_KEY="your-gemini-api-key"

# Server configuration
BACKEND_HOST="0.0.0.0"
BACKEND_PORT=8001
FRONTEND_PORT=5175
```

> [!NOTE]
> Setting `GEMINI_API_KEY` is completely **optional**. If not provided, WellPulse automatically activates its built-in Petroleum Diagnostic Engine so you can evaluate the platform 100% locally and offline without external dependencies.

---

## 4. Manual Step-by-Step Setup

### 4.1 Backend Setup (Terminal 1)
```bash
cd backend

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run backend service
python3 run.py
```
*The FastAPI backend will start at `http://localhost:8001`. You can inspect interactive OpenAPI documentation at `http://localhost:8001/docs`.*

### 4.2 Frontend Setup (Terminal 2)
```bash
cd frontend

# Install npm dependencies
npm install

# Start Vite development server
npm run dev
```
*The React frontend will start at `http://localhost:5175`.*

---

## 5. Automated Single-Command Startup (`run_local.sh`)

To launch both backend and frontend concurrently with a single command:

```bash
# Make the startup script executable
chmod +x run_local.sh

# Launch WellPulse
./run_local.sh
```

The script will:
1. Verify Python and Node environments.
2. Initialize and verify backend dependencies.
3. Generate the 50-well, 24-month synthetic telemetry dataset if not already present.
4. Install frontend npm packages if missing.
5. Launch FastAPI backend on port `8001`.
6. Launch Vite frontend on port `5175`.
7. Monitor both processes and shut down cleanly upon pressing `Ctrl+C`.

---

## 6. Verification & Health Checks

Once running, verify the following endpoints in your browser:
- **Application Dashboard**: `http://localhost:5175`
- **Backend Health Check**: `http://localhost:8001/api/health`
- **Well Telemetry API**: `http://localhost:8001/api/wells`
- **Interactive Swagger Docs**: `http://localhost:8001/docs`

---

## 7. Troubleshooting

| Issue | Cause | Solution |
|---|---|---|
| **Port 8000 already in use** | An existing process is listening on port 8000 | Run `lsof -i :8000` and kill the conflicting process or modify `BACKEND_PORT` |
| **Microphone not transcribing** | Browser permission blocked or non-HTTPS/localhost | Ensure you are accessing via `http://localhost:5173` and click "Allow" when prompted for microphone permissions |
| **Vite connection refused** | Backend is still starting up | Wait 3 seconds for Uvicorn to initialize before refreshing the frontend |
