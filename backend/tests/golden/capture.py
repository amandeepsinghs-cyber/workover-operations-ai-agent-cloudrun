"""Capture golden API *shape* snapshots of the v0.3 WellPulse backend (Stage M).

Usage (from ``backend/``)::

    uv run python -m tests.golden.capture --wells GLK-101,GLK-120,GLK-150

Writes ``tests/golden/<route_name>.schema.json`` for every route in
``tests/golden/routes.py`` plus the live websocket. Per-well routes merge the
shapes observed across all golden wells. Gemini is never called: the chat and
audio routes are captured on the local fallback engine.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fastapi.testclient import TestClient

from tests.golden import routes as R
from tests.golden.shape import infer, merge

GOLDEN_DIR = Path(__file__).resolve().parent


def disable_gemini() -> None:
    """Force the local fallback engine: make every Gemini call raise."""
    from app.services import ai_agent

    def _no_gemini(*_args, **_kwargs):
        raise RuntimeError("Gemini disabled in golden/test runs")

    ai_agent.call_gemini_api = _no_gemini


def _paths(path_template: str, wells: list[str]) -> list[str]:
    if "{well}" in path_template:
        return [path_template.format(well=w) for w in wells]
    return [path_template]


def capture_http(client: TestClient, wells: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for name, method, template, body in R.ROUTES:
        expected = R.EXPECTED_STATUS.get(name, 200)
        schema: dict = {}
        for path in _paths(template, wells):
            resp = client.request(method, path, json=body)
            if resp.status_code != expected:
                raise SystemExit(f"{name}: {method} {path} -> {resp.status_code} (expected {expected})")
            schema = merge(schema, infer(resp.json()))
        out[name] = {
            "route": template,
            "method": method,
            "status": expected,
            "wells": wells if "{well}" in template else [],
            "schema": schema,
        }
    return out


def capture_ws(client: TestClient, wells: list[str]) -> dict:
    ready_schema: dict = {}
    response_schema: dict = {}
    pong_schema: dict = {}
    for w in wells:
        with client.websocket_connect(R.WS_LIVE_PATH.format(well=w)) as ws:
            ready_schema = merge(ready_schema, infer(ws.receive_json()))
            ws.send_json({"type": "ping"})
            pong_schema = merge(pong_schema, infer(ws.receive_json()))
            ws.send_json({"type": "message", "text": "What happened to this well?", "language": "english"})
            thinking = ws.receive_json()
            assert thinking.get("type") == "thinking", thinking
            response_schema = merge(response_schema, infer(ws.receive_json()))
    return {
        "route": R.WS_LIVE_PATH,
        "method": "WEBSOCKET",
        "status": 101,
        "wells": wells,
        "schema": {"ready": ready_schema, "pong": pong_schema, "response": response_schema},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wells", default=",".join(R.GOLDEN_WELLS))
    args = ap.parse_args()
    wells = [w.strip() for w in args.wells.split(",") if w.strip()]

    disable_gemini()
    from app.main import app

    with TestClient(app) as client:
        snapshots = capture_http(client, wells)
        snapshots[R.WS_LIVE_NAME] = capture_ws(client, wells)

    for name, snap in snapshots.items():
        path = GOLDEN_DIR / f"{name}.schema.json"
        path.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"[✓] {path.relative_to(GOLDEN_DIR.parent.parent)}")
    print(f"[✓] {len(snapshots)} golden shape files written for wells {wells}")


if __name__ == "__main__":
    main()
