import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.live import router as live_router  # Stage U: WS /ws/live
from app.api.wells import router as wells_router
from app.api.docs import router as docs_router  # Stage O: document corpus
from app.api.fields import router as fields_router  # Stage P: TC-019 / TC-020 routes
from app.data_access.repository import get_repository

app = FastAPI(
    title="WellPulse API",
    description="Operational Well Intelligence & Voice AI Copilot for Energy Assets",
    version="1.0.0",
)

# Enable CORS for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_utf8_charset_header(request, call_next):
    response = await call_next(request)
    ct = response.headers.get("content-type", "")
    if "application/json" in ct and "charset" not in ct:
        response.headers["content-type"] = "application/json; charset=utf-8"
    return response


# Register API routes FIRST so they take precedence over static files
app.include_router(wells_router, prefix="/api")
app.include_router(docs_router, prefix="/api")  # Stage O: /api/docs/*, /api/wells/{id}/documents
app.include_router(live_router)  # Stage U: WS /ws/live (SDD §11.4)
app.include_router(fields_router, prefix="/api")  # Stage P: /api/fields/{f}/health|attribution, /api/wells/{id}/attribution


@app.on_event("startup")
def startup_event():
    print("[*] WellPulse Backend Initializing...")
    wells = get_repository().list_wells()  # warm the parquet repository (SDD §5.7)
    print(f"[✓] WellPulse Backend Ready with {len(wells)} active well assets.")


# Mount pre-built frontend static files if available (for Cloud Run production container)
possible_dist_paths = [
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"),
    os.path.join(os.path.dirname(__file__), "..", "static"),
    "/app/frontend/dist",
]

for p in possible_dist_paths:
    abs_p = os.path.abspath(p)
    if os.path.exists(abs_p) and os.path.exists(os.path.join(abs_p, "index.html")):
        app.mount("/", StaticFiles(directory=abs_p, html=True), name="frontend")
        print(f"[✓] Mounted frontend static files from {abs_p}")
        break
