"""Catalogue of every v0.3 ``/api`` route frozen by the Stage M golden snapshots.

Each entry is ``(name, method, path_template, body)``. ``{well}`` in the path is
substituted with each golden well. Global routes (no ``{well}``) are captured once.
The websocket ``/api/wells/{well}/live`` route is handled separately (see
``capture.py`` / ``test_api_shapes.py``) because it is not a request/response route.
"""

from __future__ import annotations

# Stage N: GLK- IDs retired; one golden well per field (Geleki, Lakwa fixture, Lakhmani).
GOLDEN_WELLS = ["GK-129", "LKW-047", "LKM-061"]

# Chat/audio requests run with Gemini disabled (local fallback engine): see conftest.py.
_CHAT_BODY = {"message": "What happened to this well and what do you recommend?", "language": "english"}
_AUDIO_BODY = {"audio_base64": "AAAA", "mime_type": "audio/webm", "language": "english"}

ROUTES: list[tuple[str, str, str, dict | None]] = [
    ("health", "GET", "/api/health", None),
    ("wells_kpis", "GET", "/api/wells/kpis", None),
    ("wells_list", "GET", "/api/wells", None),
    ("wells_list_filtered", "GET", "/api/wells?status=all&basin=Assam&search=GK", None),
    ("field_infrastructure", "GET", "/api/field/infrastructure", None),
    ("well_detail", "GET", "/api/wells/{well}", None),
    ("well_reports", "GET", "/api/wells/{well}/reports", None),
    ("well_report_completion", "GET", "/api/wells/{well}/reports/completion", None),
    ("well_report_workover", "GET", "/api/wells/{well}/reports/workover", None),
    ("well_report_bhp", "GET", "/api/wells/{well}/reports/bhp", None),
    ("well_report_lab", "GET", "/api/wells/{well}/reports/lab", None),
    ("well_history_30d", "GET", "/api/wells/{well}/history?range=30d", None),
    ("well_history_2y", "GET", "/api/wells/{well}/history?range=2y", None),
    ("well_workovers", "GET", "/api/wells/{well}/workovers", None),
    ("well_export", "GET", "/api/wells/{well}/export", None),
    ("well_recommendations", "POST", "/api/wells/{well}/recommendations", None),
    ("well_chat_fallback", "POST", "/api/wells/{well}/chat", _CHAT_BODY),
    ("well_audio_fallback", "POST", "/api/wells/{well}/audio", _AUDIO_BODY),
    ("well_not_found", "GET", "/api/wells/NOPE-000", None),
]

WS_LIVE_NAME = "well_live_ws"
WS_LIVE_PATH = "/api/wells/{well}/live"

# Expected HTTP status per route (default 200).
EXPECTED_STATUS = {"well_not_found": 404}
