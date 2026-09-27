"""
FastAPI Routes for Well Management, Telemetry, and Contextual AI Agent.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from app.services.data_generator import get_all_wells
from app.services.ai_agent import chat_with_well_agent, generate_structured_recommendation

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    language: Optional[str] = "hinglish"


@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "WellPulse Backend API",
        "version": "1.0.0",
    }


@router.get("/wells/kpis")
def get_fleet_kpis():
    wells = get_all_wells()
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
    status: Optional[str] = Query(None, description="healthy, warning, or failed"),
    basin: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    wells = get_all_wells()
    results = []

    for w in wells:
        if status and status.lower() != "all" and w["status"].lower() != status.lower():
            continue
        if basin and basin.lower() not in w["basin"].lower():
            continue
        if search:
            s = search.lower()
            if s not in w["name"].lower() and s not in w["id"].lower() and s not in w["formation"].lower():
                continue

        # Return lightweight summary for map & list (exclude large 730d history)
        results.append({
            "id": w["id"],
            "name": w["name"],
            "coordinates": w["coordinates"],
            "basin": w["basin"],
            "formation": w["formation"],
            "lift_type": w["lift_type"],
            "status": w["status"],
            "current_metrics": w["current_metrics"],
            "telemetry_summary": w.get("telemetry_summary", {}),
            "recent_workovers_count": len(w.get("workovers", [])),
        })

    return results


@router.get("/wells/{well_id}")
def get_well_detail(well_id: str):
    wells = get_all_wells()
    for w in wells:
        if w["id"].upper() == well_id.upper():
            return {
                "id": w["id"],
                "name": w["name"],
                "coordinates": w["coordinates"],
                "basin": w["basin"],
                "formation": w["formation"],
                "lift_type": w["lift_type"],
                "status": w["status"],
                "current_metrics": w["current_metrics"],
                "telemetry_summary": w.get("telemetry_summary", {}),
                "workovers": w.get("workovers", []),
                "reports": w.get("reports", {}),
            }
    raise HTTPException(status_code=404, detail=f"Well {well_id} not found")


@router.get("/wells/{well_id}/reports")
def get_well_reports(well_id: str):
    wells = get_all_wells()
    for w in wells:
        if w["id"].upper() == well_id.upper():
            return w.get("reports", {})
    raise HTTPException(status_code=404, detail=f"Well {well_id} not found")


@router.get("/wells/{well_id}/reports/{report_type}")
def get_well_specific_report(well_id: str, report_type: str):
    wells = get_all_wells()
    valid_keys = {
        "completion": "completion_report",
        "workover": "daily_workover_report",
        "bhp": "bottomhole_pressure_survey",
        "lab": "water_and_scale_lab_report",
    }
    for w in wells:
        if w["id"].upper() == well_id.upper():
            reports = w.get("reports", {})
            target_key = valid_keys.get(report_type.lower(), report_type.lower())
            if target_key in reports:
                return reports[target_key]
            raise HTTPException(
                status_code=404,
                detail=f"Report type '{report_type}' not found for well {well_id}. Available: {list(reports.keys())}",
            )
    raise HTTPException(status_code=404, detail=f"Well {well_id} not found")


@router.get("/wells/{well_id}/history")
def get_well_history(
    well_id: str,
    range: str = Query("2y", description="Time range: 30d, 6m, 1y, or 2y"),
):
    wells = get_all_wells()
    target = None
    for w in wells:
        if w["id"].upper() == well_id.upper():
            target = w
            break

    if not target:
        raise HTTPException(status_code=404, detail=f"Well {well_id} not found")

    full_history = target.get("history_730d", [])
    if range == "30d":
        return full_history[-30:]
    elif range == "6m":
        return full_history[-180:]
    elif range == "1y":
        return full_history[-365:]
    return full_history


@router.get("/wells/{well_id}/workovers")
def get_well_workovers(well_id: str):
    wells = get_all_wells()
    for w in wells:
        if w["id"].upper() == well_id.upper():
            return w.get("workovers", [])
    raise HTTPException(status_code=404, detail=f"Well {well_id} not found")


@router.post("/wells/{well_id}/chat")
def chat_with_well(well_id: str, request: ChatRequest):
    wells = get_all_wells()
    target = None
    for w in wells:
        if w["id"].upper() == well_id.upper():
            target = w
            break

    if not target:
        raise HTTPException(status_code=404, detail=f"Well {well_id} not found")

    result = chat_with_well_agent(
        target, request.message, language=request.language or "hinglish"
    )
    return result


@router.websocket("/wells/{well_id}/live")
async def well_live_websocket(websocket: WebSocket, well_id: str):
    await websocket.accept()
    wells = get_all_wells()
    target = None
    for w in wells:
        if w["id"].upper() == well_id.upper():
            target = w
            break

    if not target:
        await websocket.send_json({"type": "error", "error": f"Well {well_id} not found"})
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
    wells = get_all_wells()
    target = None
    for w in wells:
        if w["id"].upper() == well_id.upper():
            target = w
            break

    if not target:
        raise HTTPException(status_code=404, detail=f"Well {well_id} not found")

    rec = generate_structured_recommendation(target)
    return {
        "well_id": target["id"],
        "well_name": target["name"],
        "status": target["status"],
        "recommendation": rec,
    }
