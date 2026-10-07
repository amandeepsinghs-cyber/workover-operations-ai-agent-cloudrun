"""
FastAPI Routes for Well Management, Telemetry, and Contextual AI Agent.

v0.4 (Stage N): every route reads the ``WellRepository`` (parquet landing by default, SDD §5.7).
``GLK-`` IDs are retired (404 with a pointer to ``GK-``); no currency leaves the API (D-1).
"""

import base64

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.analytics.generator.fields import FIELD_CONFIGS
from app.data_access.adapters import as_of_timestamp
from app.data_access.repository import RetiredWellId, get_repository
from app.services.ai_agent import (
    chat_with_well_agent,
    chat_with_well_agent_audio,
    generate_structured_recommendation,
)

router = APIRouter()

RETIRED_DETAIL = "GLK- IDs retired in v0.4; use GK-"
HISTORY_RANGES = ("30d", "6m", "1y", "2y", "3y", "5y")
SUMMARY_KEYS = (
    "id", "name", "coordinates", "basin", "formation", "lift_type", "status", "current_metrics",
    "telemetry_summary", "recent_workovers_count", "field", "cluster_id", "health_bucket", "health_reason",
    "status_reason", "health_rule", "as_of", "current_metrics_date",
)


class ChatRequest(BaseModel):
    message: str
    language: str | None = "english"


class AudioMessageRequest(BaseModel):
    audio_base64: str
    mime_type: str | None = "audio/webm"
    language: str | None = "english"


# ---------------------------------------------------------------------------
# Data seams (also used by app.live.voice_tools: voice == screen)
# ---------------------------------------------------------------------------
def get_all_wells() -> list[dict]:
    """All well summaries (incl. workovers) from the repository."""
    return get_repository().list_wells()


def _well_or_404(well_id: str) -> dict:
    try:
        w = get_repository().get_well(well_id)
    except RetiredWellId:
        raise HTTPException(status_code=404, detail=RETIRED_DETAIL)
    if w is None:
        raise HTTPException(status_code=404, detail=f"Well {well_id} not found")
    return w


@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "WellPulse Backend API",
        "version": "1.0.0",
    }


@router.get("/wells/kpis")
def get_fleet_kpis(field: str | None = None):
    wells = [w for w in get_all_wells() if not field or w["field"].lower() == field.lower()]
    total = len(wells)
    healthy = sum(1 for w in wells if w["status"] == "healthy")
    warning = sum(1 for w in wells if w["status"] == "warning")
    failed = sum(1 for w in wells if w["status"] == "failed")

    total_oil = sum(w["current_metrics"]["oil_bopd"] for w in wells)
    total_gas = sum(w["current_metrics"]["gas_mcfd"] for w in wells)
    avg_water_cut = round(sum(w["current_metrics"]["water_cut_pct"] for w in wells) / total, 1) if total else 0.0

    return {
        "total_wells": total,
        "healthy_count": healthy,
        "warning_count": warning,
        "failed_count": failed,
        "total_oil_bopd": round(total_oil, 1),
        "total_gas_mcfd": round(total_gas, 1),
        "avg_water_cut_pct": avg_water_cut,
    }


@router.get("/wells")
def list_wells(
    status: str | None = Query(None, description="healthy, warning, or failed"),
    basin: str | None = Query(None),
    search: str | None = Query(None),
    field: str | None = Query(None, description="Geleki, Lakwa or Lakhmani"),
):
    results = []
    for w in get_all_wells():
        if status and status.lower() != "all" and w["status"].lower() != status.lower():
            continue
        if basin and basin.lower() not in w["basin"].lower():
            continue
        if field and field.lower() not in ("all", w["field"].lower()):
            continue
        if search:
            s = search.lower()
            if s not in w["name"].lower() and s not in w["id"].lower() and s not in w["formation"].lower():
                continue
        # Lightweight summary for map & list (no workovers / history)
        results.append({k: w.get(k) for k in SUMMARY_KEYS})
    return results


@router.get("/wells/{well_id}")
def get_well_detail(well_id: str):
    w = _well_or_404(well_id)
    out = {k: w.get(k) for k in SUMMARY_KEYS if k != "recent_workovers_count"}
    out["workovers"] = w.get("workovers", [])
    out["reports"] = w.get("reports", {})
    return out


@router.get("/wells/{well_id}/reports")
def get_well_reports(well_id: str):
    return _well_or_404(well_id).get("reports", {})


@router.get("/wells/{well_id}/reports/{report_type}")
def get_well_specific_report(well_id: str, report_type: str):
    valid_keys = {
        "completion": "completion_report",
        "workover": "daily_workover_report",
        "bhp": "bottomhole_pressure_survey",
        "lab": "water_and_scale_lab_report",
    }
    reports = _well_or_404(well_id).get("reports", {})
    target_key = valid_keys.get(report_type.lower(), report_type.lower())
    if target_key in reports:
        return reports[target_key]
    raise HTTPException(
        status_code=404,
        detail=f"Report type '{report_type}' not found for well {well_id}. Available: {list(reports.keys())}",
    )


@router.get("/wells/{well_id}/history")
def get_well_history(
    well_id: str,
    range: str = Query("2y", description="Time range: 30d, 6m, 1y, 2y, 3y or 5y"),
):
    _well_or_404(well_id)
    if range not in HISTORY_RANGES:
        raise HTTPException(status_code=422, detail=f"range must be one of {list(HISTORY_RANGES)}")
    return get_repository().get_history(well_id, range)


@router.get("/wells/{well_id}/workovers")
def get_well_workovers(well_id: str):
    return _well_or_404(well_id).get("workovers", [])


@router.post("/wells/{well_id}/chat")
def chat_with_well(well_id: str, request: ChatRequest):
    target = _well_or_404(well_id)
    return chat_with_well_agent(target, request.message, language=request.language or "english")


@router.post("/wells/{well_id}/audio")
def chat_with_well_audio(well_id: str, request: AudioMessageRequest):
    target = _well_or_404(well_id)
    try:
        audio_bytes = base64.b64decode(request.audio_base64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64 audio: {e}")

    return chat_with_well_agent_audio(
        target,
        audio_bytes,
        mime_type=request.mime_type or "audio/webm",
        language=request.language or "english",
    )


@router.websocket("/wells/{well_id}/live")
async def well_live_websocket(websocket: WebSocket, well_id: str):
    await websocket.accept()
    try:
        target = get_repository().get_well(well_id)
        error = None if target else f"Well {well_id} not found"
    except RetiredWellId:
        target, error = None, RETIRED_DETAIL

    if not target:
        await websocket.send_json({"type": "error", "error": error})
        await websocket.close()
        return

    await websocket.send_json({
        "type": "ready",
        "well_id": target["id"],
        "well_name": target["name"],
        "status": "connected",
        "mode": "gemini-live-bi-directional",
    })

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "message")

            if msg_type == "message":
                user_text = data.get("text", "")
                lang = data.get("language", "hinglish")

                await websocket.send_json({"type": "thinking"})
                result = chat_with_well_agent(target, user_text, language=lang)
                await websocket.send_json({
                    "type": "response",
                    "text": result["response"],
                    "recommendation": result.get("recommendation"),
                    "engine": result.get("engine"),
                    "language": lang,
                })

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "error": str(e)})
        except Exception:
            pass


@router.post("/wells/{well_id}/recommendations")
def get_recommendation(well_id: str):
    target = _well_or_404(well_id)
    return {
        "well_id": target["id"],
        "well_name": target["name"],
        "status": target["status"],
        "recommendation": generate_structured_recommendation(target),
    }


@router.get("/field/infrastructure")
def get_field_infrastructure(field: str = Query("Geleki", description="Geleki, Lakwa or Lakhmani")):
    """Processing facilities (GGS / CTF / ETP) and serviced wells for one field, from facility_master."""
    match = next((f for f in FIELD_CONFIGS if f.lower() == field.lower()), None)
    if match is None:
        raise HTTPException(status_code=404, detail=f"Unknown field {field!r}; expected one of {list(FIELD_CONFIGS)}")
    return get_repository().field_infrastructure(match)


@router.get("/wells/{well_id}/export")
def export_well_dossier(well_id: str):
    """Exports full engineering dossier and telemetry archive for a well."""
    w = _well_or_404(well_id)
    cfg = FIELD_CONFIGS[w["field"]]
    return {
        "well_id": w["id"],
        "well_name": w["name"],
        "field": f"{cfg.field} Field, Assam ({cfg.asset} Asset)",
        "formation": w["formation"],
        "status": w["status"],
        "coordinates": w["coordinates"],
        "current_metrics": w["current_metrics"],
        "telemetry_summary": w.get("telemetry_summary", {}),
        "workovers": w.get("workovers", []),
        "reports": w.get("reports", {}),
        "export_timestamp": as_of_timestamp(),
        "as_of": w.get("as_of"),
        "health_rule": w.get("health_rule"),
    }
