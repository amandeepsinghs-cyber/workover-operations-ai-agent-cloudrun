"""tests/integration/test_ws_live.py — WS /ws/live with a FakeLiveSession (Stage U, BDD F-07). No network.

Covers: handshake + audio/caption/turn events (F07-S01 shape), transparent reconnect keeps memory
(F07-S03), 3 failures -> text fallback (F07-S04), tool call round-trip with the same backend
functions (F07-S05), currency stripping (D-1), language toggle via context, tool timeout.
"""

from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace as NS
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.live import session as live_session
from app.live import voice_tools


# ---------------------------------------------------------------------------
# Fake google-genai Live session
# ---------------------------------------------------------------------------
def _resp(**kw: Any) -> NS:
    base = dict(session_resumption_update=None, go_away=None, tool_call=None, server_content=None)
    base.update(kw)
    return NS(**base)


def _sc(text: str | None = None, turn_complete: bool = False, audio: bytes | None = None, heard: str | None = None) -> NS:
    parts = [NS(inline_data=NS(data=audio), text=None)] if audio else []
    return NS(
        interrupted=False,
        input_transcription=NS(text=heard) if heard else None,
        output_transcription=NS(text=text) if text else None,
        model_turn=NS(parts=parts) if parts else None,
        turn_complete=turn_complete,
    )


def _texts(turns: list[Any]) -> str:
    return " ".join(p.text for t in turns for p in t.parts if getattr(p, "text", None))


class FakeLiveSession:
    def __init__(self, script: FakeLive, idx: int, config: Any):
        self.script, self.idx, self.config = script, idx, config
        self.out: asyncio.Queue = asyncio.Queue()
        self.client_content: list[tuple[list[Any], bool]] = []
        self.tool_responses: list[Any] = []
        self.audio_chunks = 0
        self.audio_end = False

    async def __aenter__(self) -> FakeLiveSession:
        for r in self.script.on_connect(self):
            self.out.put_nowait(r)
        return self

    async def __aexit__(self, *a: object) -> None:
        return None

    async def send_realtime_input(self, audio: Any = None, audio_stream_end: bool | None = None, **kw: Any) -> None:
        if audio is not None:
            self.audio_chunks += 1
        if audio_stream_end:
            self.audio_end = True
            for r in self.script.on_audio_end(self):
                self.out.put_nowait(r)

    async def send_client_content(self, turns: list[Any], turn_complete: bool = True) -> None:
        self.client_content.append((turns, turn_complete))
        if turn_complete:
            for r in self.script.on_prompt(self, turns):
                self.out.put_nowait(r)

    async def send_tool_response(self, function_responses: list[Any]) -> None:
        self.tool_responses.extend(function_responses)
        self.out.put_nowait(_resp(server_content=_sc("Answer from tool.", audio=b"\x00\x01" * 8)))
        self.out.put_nowait(_resp(server_content=_sc(turn_complete=True)))

    async def receive(self):
        while True:
            item = await self.out.get()
            if item is None:
                return
            yield item


class FakeLive:
    """Scriptable connect_factory: ``(model, config) -> async context manager``."""

    def __init__(self, fail_times: int = 0):
        self.fail_times = fail_times
        self.attempts = 0
        self.sessions: list[FakeLiveSession] = []
        self.models: list[str] = []

    def __call__(self, model: str, config: Any) -> FakeLiveSession:
        self.attempts += 1
        self.models.append(model)
        if self.attempts <= self.fail_times:
            raise ConnectionError(f"simulated failure {self.attempts}")
        s = FakeLiveSession(self, len(self.sessions), config)
        self.sessions.append(s)
        return s

    def on_connect(self, s: FakeLiveSession) -> list[Any]:
        return [_resp(session_resumption_update=NS(resumable=True, new_handle=f"h{s.idx + 1}"))]

    def on_prompt(self, s: FakeLiveSession, turns: list[Any]) -> list[Any]:
        n = sum(1 for _, tc in s.client_content if tc)
        return [
            _resp(server_content=_sc(f"Answer {n}.", audio=b"\x01\x00" * 480)),
            _resp(server_content=_sc(turn_complete=True)),
        ]

    def on_audio_end(self, s: FakeLiveSession) -> list[Any]:
        return [
            _resp(server_content=_sc(heard="Which field is underperforming?")),
            _resp(server_content=_sc("Spoken answer.", audio=b"\x02\x00" * 480)),
            _resp(server_content=_sc(turn_complete=True)),
        ]


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
@pytest.fixture
def well_id() -> str:
    return voice_tools._wells()[0]["id"]


@pytest.fixture
def live_app(monkeypatch):
    from app.main import app

    monkeypatch.setenv("WELLPULSE_LIVE_BACKOFF_S", "0")
    monkeypatch.delenv("WELLPULSE_LIVE_OFFLINE", raising=False)

    def install(factory: Any) -> TestClient:
        app.state.live_connect_factory = factory
        return TestClient(app)

    yield install
    if hasattr(app.state, "live_connect_factory"):
        del app.state.live_connect_factory


def recv_until(ws: Any, pred, limit: int = 80) -> list[dict]:
    seen: list[dict] = []
    for _ in range(limit):
        msg = ws.receive()
        if msg.get("text") is None:
            seen.append({"type": "_audio", "n": len(msg.get("bytes") or b"")})
            continue
        data = json.loads(msg["text"])
        seen.append(data)
        if pred(data):
            return seen
    raise AssertionError(f"predicate not met; saw {seen}")


def is_status(s: str):
    return lambda d: d.get("type") == "status" and d.get("status") == s


def is_turn_complete(d: dict) -> bool:
    return d.get("type") == "turn_complete"


def prompt(ws: Any, text: str) -> list[dict]:
    ws.send_text(json.dumps({"type": "prompt", "text": text}))
    return recv_until(ws, is_turn_complete)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_handshake_text_turn_streams_audio_and_captions(live_app, well_id):
    fake = FakeLive()
    client = live_app(fake)
    with client.websocket_connect(f"/ws/live?language=hinglish&well_id={well_id}") as ws:
        seen = recv_until(ws, is_status("connected"))
        assert seen[0] == {"type": "status", "status": "connecting", "model": fake.models[0]}
        assert seen[-1]["model"] == live_session.live_settings()["model"]
        events = prompt(ws, "What happened to this well?")
    types_ = [e["type"] for e in events]
    assert "_audio" in types_ and "caption_delta" in types_
    assert events[-1]["full_text"] == "Answer 1."
    assert {"type": "voice_state", "state": "speaking"} in events
    # The language toggle + UI context reach the live system instruction (SDD §11.6).
    sys_text = fake.sessions[0].config.system_instruction.parts[0].text
    assert "## LANGUAGE (hinglish)" in sys_text and "Roman script" in sys_text
    assert f"well_id={well_id}" in sys_text
    assert "### english" not in sys_text  # only the selected block is appended
    # The prompt is prefixed with the UI context line.
    sent = [t for t, tc in fake.sessions[0].client_content if tc]
    assert f"well_id={well_id}" in _texts(sent[0]) and "What happened" in _texts(sent[0])
    cfg = fake.sessions[0].config
    assert cfg.context_window_compression.sliding_window is not None
    assert cfg.input_audio_transcription is not None and cfg.output_audio_transcription is not None


def test_push_to_talk_audio_turn(live_app):
    fake = FakeLive()
    client = live_app(fake)
    with client.websocket_connect("/ws/live") as ws:
        recv_until(ws, is_status("connected"))
        for _ in range(3):
            ws.send_bytes(b"\x00\x00" * 480)  # 30 ms of 16 kHz PCM16
        ws.send_text(json.dumps({"type": "audio_end"}))
        events = recv_until(ws, is_turn_complete)
    assert fake.sessions[0].audio_chunks == 3 and fake.sessions[0].audio_end
    assert {"type": "input_transcript", "text": "Which field is underperforming?"} in events
    assert events[-1]["full_text"] == "Spoken answer."


def test_reconnect_keeps_memory_with_handle_and_recap(live_app):
    class GoAwayAfterTwo(FakeLive):
        def on_prompt(self, s, turns):
            out = super().on_prompt(s, turns)
            if s.idx == 0 and sum(1 for _, tc in s.client_content if tc) == 2:
                out.append(_resp(go_away=NS(time_left="1s")))
            return out

    fake = GoAwayAfterTwo()
    client = live_app(fake)
    with client.websocket_connect("/ws/live") as ws:
        recv_until(ws, is_status("connected"))
        prompt(ws, "Which wells are down?")
        prompt(ws, "Tell me about the first one.")
        seen = recv_until(ws, is_status("resumed"))
        assert any(d.get("status") == "reconnecting" for d in seen)
        assert seen[-1]["memory"] is True
        events = prompt(ws, "And what about the second one?")
    assert events[-1]["full_text"] == "Answer 1."
    assert len(fake.sessions) == 2
    # Resumed with the latest handle, and the recap carries the earlier turns as history.
    assert fake.sessions[1].config.session_resumption.handle == "h1"
    recap_turns, recap_tc = fake.sessions[1].client_content[0]
    assert recap_tc is False
    recap = _texts(recap_turns)
    assert "Which wells are down?" in recap and "Answer 2." in recap
    assert {t.role for t in recap_turns} == {"user", "model"}


def test_three_failures_fall_back_to_text(live_app, well_id):
    fake = FakeLive(fail_times=99)
    client = live_app(fake)
    with client.websocket_connect(f"/ws/live?well_id={well_id}&language=english") as ws:
        seen = recv_until(ws, is_status("fallback"))
        assert fake.attempts == live_session.MAX_CONSECUTIVE_FAILURES
        assert "switched to text" in seen[-1]["message"]
        ws.send_bytes(b"\x00\x00" * 10)
        err = recv_until(ws, lambda d: d.get("type") == "error")
        assert "text mode" in err[-1]["message"]
        events = prompt(ws, "What happened to this well?")
    reply = next(e for e in events if e["type"] == "fallback_reply")
    assert reply["text"] and reply["engine"].startswith("text-fallback")
    assert events[-1]["full_text"] == reply["text"]


def test_two_failures_then_connect_drops_stale_handle(live_app):
    fake = FakeLive(fail_times=2)
    client = live_app(fake)
    with client.websocket_connect("/ws/live") as ws:
        recv_until(ws, is_status("connected"))
        prompt(ws, "hello")
    assert fake.attempts == 3 and len(fake.sessions) == 1
    assert fake.sessions[0].config.session_resumption.handle is None


def test_tool_call_round_trip_uses_backend_functions(live_app, well_id):
    class ToolScript(FakeLive):
        def on_prompt(self, s, turns):
            fc = NS(name="well_summary", args={"well_id": well_id.lower()}, id="call-1")
            return [_resp(tool_call=NS(function_calls=[fc])), _resp(server_content=_sc(turn_complete=True))]

    fake = ToolScript()
    client = live_app(fake)
    with client.websocket_connect("/ws/live") as ws:
        recv_until(ws, is_status("connected"))
        events = prompt(ws, "Tell me about this well")
    running = [e for e in events if e["type"] == "tool_call" and e["status"] == "running"]
    done = [e for e in events if e["type"] == "tool_call" and e["status"] == "done"]
    assert running and done and done[0]["name"] == "well_summary"
    assert done[0]["result"]["id"] == well_id and done[0]["result"]["status"] == "OK"
    assert any(e["type"] == "action" and e["kind"] == "well_profile" for e in events)
    # The same numbers go to the model as to the UI (BDD-F07-S05).
    fr = fake.sessions[0].tool_responses[0]
    assert fr.id == "call-1" and fr.response["result"]["current_metrics"] == done[0]["result"]["current_metrics"]
    from app.services.data_generator import get_all_wells

    truth = next(w for w in get_all_wells() if w["id"] == well_id)
    assert fr.response["result"]["current_metrics"]["oil_bopd"] == truth["current_metrics"]["oil_bopd"]
    # The empty turn_complete right after the tool call is swallowed; the spoken answer completes the turn.
    assert events[-1]["full_text"] == "Answer from tool."


def test_currency_is_stripped_from_voice_tool_results(live_app, monkeypatch):
    def _pricey() -> dict:
        return {
            "status": "OK",
            "estimated_cost_usd": 45000,
            "cost_inr_lakh": 12.5,
            "estimated_payback_days": 30,
            "cost_band": "MED",
            "rig_days": 7.0,
            "note": "Job costs $45,000 (₹ 37 lakh); USD 3.2M program.",
            "nested": [{"total_workover_spend_usd": 1, "oil_bopd": 120.5}],
        }

    monkeypatch.setitem(voice_tools.VOICE_TOOLS, "pricey", voice_tools.VoiceTool(name="pricey", fn=_pricey, description="test"))

    class ToolScript(FakeLive):
        def on_prompt(self, s, turns):
            return [_resp(tool_call=NS(function_calls=[NS(name="pricey", args={}, id="c")]))]

    fake = ToolScript()
    client = live_app(fake)
    with client.websocket_connect("/ws/live") as ws:
        recv_until(ws, is_status("connected"))
        events = prompt(ws, "what will it cost?")
    result = next(e for e in events if e["type"] == "tool_call" and e["status"] == "done")["result"]
    sent_to_model = fake.sessions[0].tool_responses[0].response["result"]
    for r in (result, sent_to_model):
        blob = json.dumps(r, ensure_ascii=False)
        assert "usd" not in blob.lower() and "inr" not in blob.lower() and "payback" not in blob
        assert "$" not in blob and "₹" not in blob and "lakh" not in blob
        assert r["cost_band"] == "MED" and r["rig_days"] == 7.0 and r["nested"] == [{"oil_bopd": 120.5}]


def test_language_switch_via_context_without_reconnect(live_app):
    fake = FakeLive()
    client = live_app(fake)
    with client.websocket_connect("/ws/live?language=english") as ws:
        recv_until(ws, is_status("connected"))
        ws.send_text(json.dumps({"type": "context", "ui_state": {"language": "hindi", "well_id": "X-1"}}))
        prompt(ws, "status?")
    ctx = [t for t, tc in fake.sessions[0].client_content if not tc]
    assert ctx and "language=hindi" in _texts(ctx[0]) and "Devanagari" in _texts(ctx[0])
    assert len(fake.sessions) == 1


def test_tool_timeout_returns_unavailable(live_app, monkeypatch):
    def _slow() -> dict:
        time.sleep(1.0)
        return {"status": "OK"}

    monkeypatch.setenv("WELLPULSE_LIVE_TOOL_TIMEOUT_S", "0.1")
    monkeypatch.setitem(voice_tools.VOICE_TOOLS, "slow", voice_tools.VoiceTool(name="slow", fn=_slow, description="t"))

    class ToolScript(FakeLive):
        def on_prompt(self, s, turns):
            return [_resp(tool_call=NS(function_calls=[NS(name="slow", args={}, id="c")]))]

    client = live_app(ToolScript())
    with client.websocket_connect("/ws/live") as ws:
        recv_until(ws, is_status("connected"))
        events = prompt(ws, "slow one")
    done = next(e for e in events if e["type"] == "tool_call" and e["status"] == "done")
    assert done["result"] == {"status": "UNAVAILABLE", "message": "timeout", "duration_ms": 100}


def test_interrupt_is_acknowledged(live_app):
    client = live_app(FakeLive())
    with client.websocket_connect("/ws/live") as ws:
        recv_until(ws, is_status("connected"))
        ws.send_text(json.dumps({"type": "interrupt"}))
        seen = recv_until(ws, lambda d: d.get("type") == "interrupted")
    assert seen[-1] == {"type": "interrupted"}


def test_registry_declarations_and_seams():
    names = {d["name"] for d in voice_tools.declarations_data()}
    assert {"fleet_kpis", "well_summary", "well_workovers", "well_recommendation", "compare_fields"} <= names
    ws = next(d for d in voice_tools.declarations_data() if d["name"] == "well_summary")
    assert ws["parameters"]["required"] == ["well_id"]
    assert len(names) <= 12  # SDD §11.3 voice subset
    assert voice_tools.execute_voice_tool("nope", {})["status"] == "ERROR"
    assert voice_tools.execute_voice_tool("well_summary", {"well_id": "ZZ-999"})["status"] == "NOT_FOUND"
    kpis = voice_tools.execute_voice_tool("fleet_kpis", {})
    assert kpis["status"] == "OK" and kpis["total_wells"] > 0


def test_no_api_key_read_in_live_package():
    import pathlib

    root = pathlib.Path(live_session.__file__).parent
    for p in list(root.glob("*.py")) + [root.parent / "api" / "live.py"]:
        assert "GEMINI_API_KEY" not in p.read_text(encoding="utf-8"), p
