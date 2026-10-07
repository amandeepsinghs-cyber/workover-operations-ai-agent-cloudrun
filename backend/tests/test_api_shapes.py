"""Stage M regression gate: today's ``/api`` response SHAPES must not break.

Golden files live in ``tests/golden/*.schema.json`` (regenerate with
``uv run python -m tests.golden.capture``). Additive keys are allowed; removed
keys and type changes fail.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.routing import APIRoute, APIWebSocketRoute

from tests.golden import routes as R
from tests.golden.shape import infer, merge, validate

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


def _load(name: str) -> dict:
    path = GOLDEN_DIR / f"{name}.schema.json"
    assert path.exists(), f"missing golden file {path.name}; run tests.golden.capture"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name,method,template,body", R.ROUTES, ids=[r[0] for r in R.ROUTES])
def test_http_route_shape(client, name, method, template, body):
    golden = _load(name)
    assert golden["route"] == template and golden["method"] == method
    wells = R.GOLDEN_WELLS if "{well}" in template else [None]
    for w in wells:
        path = template.format(well=w) if w else template
        resp = client.request(method, path, json=body)
        assert resp.status_code == golden["status"], f"{method} {path}: {resp.status_code} {resp.text[:200]}"
        errors = validate(resp.json(), golden["schema"])
        assert not errors, f"{method} {path} shape drift:\n" + "\n".join(errors[:20])


def test_live_websocket_shape(client):
    golden = _load(R.WS_LIVE_NAME)["schema"]
    for w in R.GOLDEN_WELLS:
        with client.websocket_connect(R.WS_LIVE_PATH.format(well=w)) as ws:
            assert not validate(ws.receive_json(), golden["ready"])
            ws.send_json({"type": "ping"})
            assert not validate(ws.receive_json(), golden["pong"])
            ws.send_json({"type": "message", "text": "What happened to this well?", "language": "english"})
            assert ws.receive_json()["type"] == "thinking"
            errors = validate(ws.receive_json(), golden["response"])
            assert not errors, "\n".join(errors)


def test_every_api_route_has_a_golden_snapshot():
    """Guard: a new or untested /api route in main.py must be added to routes.py."""
    from app.main import app

    covered = {t.split("?")[0].replace("{well}", "{well_id}") for _, _, t, _ in R.ROUTES}
    covered.add(R.WS_LIVE_PATH.replace("{well}", "{well_id}"))
    # Parametrised report route is covered by its four concrete report types.
    covered.add("/api/wells/{well_id}/reports/{report_type}")
    live = {
        r.path
        for r in app.routes
        if isinstance(r, (APIRoute, APIWebSocketRoute)) and r.path.startswith("/api")
    }
    missing = sorted(live - covered)
    assert not missing, f"/api routes without golden snapshots: {missing}"
    for name, *_ in R.ROUTES:
        assert (GOLDEN_DIR / f"{name}.schema.json").exists(), name


def test_shape_helper_semantics():
    s = merge(infer({"a": 1, "b": None}), infer({"a": 2.5, "b": "x", "c": True}))
    assert s["required"] == ["a", "b"]
    assert s["properties"]["b"]["type"] == ["null", "string"]
    assert not validate({"a": 3, "b": "y", "extra": 1}, s)  # additive keys allowed
    assert validate({"b": "y"}, s)  # removed key fails
    assert validate({"a": "3", "b": "y"}, s)  # type change fails
