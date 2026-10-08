"""v0.6 ED-11 (F-41, D-39, D-40): `ui_control` — hands-off screen control."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.agent import ui_control as ui

FRONT = Path(__file__).resolve().parents[3] / "frontend" / "src" / "agent" / "uiCommands.ts"


@pytest.mark.parametrize(
    ("args", "expect"),
    [
        (("fullscreen", "on"), {"action": "fullscreen", "value": "on", "label": "Full screen on"}),
        (("FULLSCREEN", "exit"), {"action": "fullscreen", "value": "off"}),
        (("basemap", "dark"), {"action": "basemap", "value": "scada"}),
        (("map_view", "India"), {"action": "map_view", "value": "india"}),
        (("focus_field", "lakmani"), {"action": "focus_field", "value": "Lakhmani"}),
        (("open_screen", "compare"), {"action": "open_screen", "value": "field_compare"}),
        (("panel", "close"), {"action": "panel", "value": "close"}),
        (("language", "Hindi"), {"action": "language", "value": "hindi"}),
        (("agent", "dock"), {"action": "agent", "value": "dock"}),
    ],
)
def test_validate_allowed(args, expect):
    cmd, err = ui.validate(*args)
    assert err == "" and cmd is not None
    for k, v in expect.items():
        assert cmd[k] == v


def test_well_commands_normalise_id_and_view():
    cmd, _ = ui.validate("open_well", well_id="gk 129", view="completion")
    assert cmd == {"action": "open_well", "well_id": "GK-129", "view": "wellbore", "label": "GK-129 · wellbore"}
    cmd, _ = ui.validate("focus_well", "lkw-019")
    assert cmd["well_id"] == "LKW-019" and cmd["label"] == "LKW-019 on map"


@pytest.mark.parametrize(
    "args",
    [("delete_everything", ""), ("fullscreen", "maybe"), ("focus_well", ""), ("open_well", "", "GK-129", "secret"),
     ("focus_field", "Mumbai High")],
)
def test_validate_rejects_outside_allow_list(args):
    cmd, err = ui.validate(*args)
    assert cmd is None and err
    env = ui.run(*args)
    assert env["status"] == "INVALID" and env["data"] is None


def test_ed13_focus_cluster_and_report_print():
    cmd, err = ui.validate("focus_cluster", "ggs 03")
    assert err == "" and cmd == {"action": "focus_cluster", "value": "GGS-03", "label": "GGS-03 wells"}
    cmd, _ = ui.validate("focus_cluster", "LKW-GGS-II")
    assert cmd["value"] == "LKW-GGS-II"
    for bad in ("", "x", "GGS-01; drop table", "A" * 25):
        cmd, err = ui.validate("focus_cluster", bad)
        assert cmd is None and err
    cmd, _ = ui.validate("report", "print")
    assert cmd["value"] == "print" and cmd["label"] == "Field report printing"


@pytest.mark.parametrize(
    ("raw", "expect"),
    [("non producing", "not_producing"), ("red", "not_producing"), ("band", "not_producing"), ("Healthy", "healthy"),
     ("needs attention", "attention"), ("amber", "attention"), ("clear", "all"), ("all", "all")],
)
def test_ed14_health_filter(raw, expect):
    cmd, err = ui.validate("health_filter", raw)
    assert err == "" and cmd["value"] == expect
    assert ui.validate("health_filter", "purple")[0] is None


@pytest.mark.parametrize(
    ("text", "expect"),
    [("GK one two nine", "GK 129"), ("GGS three", "GGS 3"), ("one twenty nine", "129"), ("gk 129", "gk 129"),
     ("एक दो नौ", "129"), ("GGS 03", "GGS 03")],
)
def test_ed14_spoken_digits(text, expect):
    assert ui.spoken_digits(text) == expect


def test_ed14_spoken_ids_normalise():
    assert ui.validate("focus_cluster", "ggs three")[0]["value"] == "GGS-03"
    assert ui.validate("open_well", well_id="GK one two nine", view="wellbore")[0]["well_id"] == "GK-129"
    assert ui.validate("focus_well", "lkw nineteen")[0]["well_id"] == "LKW-019"


def test_ed14_runner_drops_health_screen_when_ui_ran():
    from app.agent.runner import build_artifacts

    ok = {"status": "OK", "data": {"field": "Lakwa"}, "tool_id": "TC-020"}
    calls = [
        {"name": "classify_well_health", "args": {"field": "Lakwa"}, "response": ok},
        {"name": "ui_control", "args": {}, "response": ui.run("health_filter", "not_producing")},
    ]
    _arts, actions = build_artifacts(calls, "only show non producing wells")
    assert [a["kind"] for a in actions] == ["ui"]
    assert actions[0]["command"]["action"] == "health_filter"
    # Without a ui command the health question still opens the Health & priority screen.
    _arts, actions = build_artifacts(calls[:1], "which wells need attention in Lakwa?")
    assert any(a.get("screen") == "field_health" for a in actions)


def test_adk_tool_and_runner_action():
    from app.agent.adk_tools import TOOLS_BY_NAME
    from app.agent.runner import build_artifacts
    from app.api.chat import AgentAction

    env = TOOLS_BY_NAME["ui_control"]("fullscreen", "on")
    assert env["status"] == "OK" and env["data"]["command"]["action"] == "fullscreen"
    calls = [
        {"name": "ui_control", "args": {"action": "fullscreen", "value": "on"}, "response": env},
        {"name": "ui_control", "args": {"action": "nope"}, "response": ui.run("nope")},
    ]
    artifacts, actions = build_artifacts(calls, "make it full screen")
    assert artifacts == []
    assert actions == [{"kind": "ui", "command": env["data"]["command"], "source_tool": "ui_control"}]
    AgentAction(**actions[0])  # the chat reply schema accepts ui actions


def test_voice_tool_registered_and_runs():
    from app.live import voice_tools

    assert "ui_control" in voice_tools.VOICE_TOOLS
    assert voice_tools.VOICE_TOOLS["ui_control"].action_kind == "ui_control"
    names = {d["name"] for d in voice_tools.declarations_data()}
    assert "ui_control" in names and len(names) <= 13  # D-39
    res = voice_tools.execute_voice_tool("ui_control", {"action": "basemap", "value": "satellite"})
    assert res["status"] == "OK" and res["data"]["command"]["label"] == "Satellite map"


def test_front_and_back_allow_lists_match():
    src = FRONT.read_text(encoding="utf-8")
    block = src[src.index("export const UI_ACTIONS") : src.index("} as const;")]
    front: dict[str, tuple[str, ...] | None] = {}
    for m in re.finditer(r"^\s{2}(\w+):\s*(null|\[([^\]]*)\])", block, re.M):
        front[m.group(1)] = None if m.group(2) == "null" else tuple(re.findall(r"'([^']+)'", m.group(3)))
    assert front == ui.UI_ACTIONS
