"""app/live/session.py — Gemini Live proxy behind ``WS /ws/live`` (SDD §11.3-11.4, BDD F-07).

Port of the ADK repo's ``agent/live/live_session.py`` (itself a port of Drilling Intelligence 2.0
``backend/app/agent/live_session.py``, ADR-003)::

    browser WS --(one reader task)--> inbound queue --> current Gemini Live session
                                                   \\--> text fallback (after 3 failures)

* The Gemini session can be replaced (GoAway / drop) without dropping the browser socket.
* Reconnects reuse the latest ``SessionResumptionConfig`` handle, keep sliding-window context
  compression on, and send a **recap** of past turns so memory survives (BDD-F07-S03).
* After 2 consecutive failures the handle is dropped (a stale handle can be the cause); after 3 the
  client gets ``status: fallback`` and prompts are answered by ``app.live.fallback`` (BDD-F07-S04).
* Tool calls run the registered ``voice_tools`` in a worker thread with a 10 s timeout.
* The language toggle (english / hinglish / hindi) is a LANGUAGE block in the system instruction at
  connect time and a context line on change (SDD §11.6). Voice never speaks ₹ / USD (D-1).

All per-connection state lives in a local ``state`` dict (no module-level mutable state, SDD §12.4).

Configuration (env; ``WELLPULSE_*`` wins, ``WORKOVER_*`` accepted as alias):
  WELLPULSE_LIVE_MODEL     verified via ``python -m app.live.verify_model`` (Stage U: gemini-3.8-live)
  WELLPULSE_LIVE_LOCATION  default us-central1 (gemini-3.8-live is not served from ``global``)
  WELLPULSE_LIVE_PROJECT   default GOOGLE_CLOUD_PROJECT, then workover-operations-agentic-ai
  WELLPULSE_LIVE_VOICE     default Aoede (DI 2.0; D-42 kept the female voice)
  WELLPULSE_LIVE_OFFLINE   1 => skip Gemini, go straight to text fallback
  WELLPULSE_DEBUG_RECONNECT 1 => accept {"type":"debug_reconnect"} to force a resume (tests / demo)
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from app.live import voice_tools

logger = logging.getLogger("wellpulse.live.session")

DEFAULT_LIVE_MODEL = "gemini-3.8-live"  # verified 2026-10-07 by models.list + live.connect (us-central1)
DEFAULT_LIVE_LOCATION = "us-central1"
DEFAULT_PROJECT = "workover-operations-agentic-ai"
MAX_CONSECUTIVE_FAILURES = 3
DROP_HANDLE_AFTER = 2
RECAP_KEEP_FIRST = 4
RECAP_KEEP_LAST = 16
RECAP_MAX_CHARS = 320
LANGUAGES = ("english", "hinglish", "hindi")
PROMPT_PATH = Path(__file__).with_name("live_prompt.md")
LANGUAGE_MARKER = "## LANGUAGE BLOCKS"

_CLOSED = object()  # sentinel pushed on the inbound queue when the browser disconnects

# connect_factory(model, config) -> async context manager yielding a Live session
ConnectFactory = Callable[[str, Any], Any]


# ---------------------------------------------------------------------------
# Settings + prompt
# ---------------------------------------------------------------------------
def _env(name: str, default: str | None = None) -> str | None:
    return os.getenv(f"WELLPULSE_{name}") or os.getenv(f"WORKOVER_{name}") or default


def live_settings() -> dict[str, Any]:
    return {
        "model": _env("LIVE_MODEL", DEFAULT_LIVE_MODEL),
        "location": _env("LIVE_LOCATION", DEFAULT_LIVE_LOCATION),
        "project": _env("LIVE_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT") or DEFAULT_PROJECT,
        "voice": _env("LIVE_VOICE", "Aoede"),
        "offline": _env("LIVE_OFFLINE", "0") == "1",
        "debug_reconnect": _env("DEBUG_RECONNECT", "0") == "1",
        "backoff_s": float(_env("LIVE_BACKOFF_S", "0.5") or 0.5),
        "tool_timeout_s": float(_env("LIVE_TOOL_TIMEOUT_S", str(voice_tools.TOOL_TIMEOUT_S)) or 10),
    }


def norm_language(lang: str | None) -> str:
    lang = (lang or "english").strip().lower()
    return lang if lang in LANGUAGES else "english"


def _read_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        return (
            "You are Urvi AI Agent (voice) for ONGC Assam Asset. Every number you speak must come "
            "from a tool result in the same turn. Never speak rupee or dollar figures. 1-3 short sentences."
        )


def language_block(lang: str) -> str:
    """The ``### <lang>`` subsection under ``## LANGUAGE BLOCKS`` in live_prompt.md."""
    text = _read_prompt()
    _, _, blocks = text.partition(LANGUAGE_MARKER)
    lang = norm_language(lang)
    for chunk in blocks.split("### ")[1:]:
        head, _, body = chunk.partition("\n")
        if head.strip().lower() == lang:
            return body.strip()
    return f"Reply in {lang}."


def build_system_prompt(ui: dict[str, Any] | None) -> str:
    ui = ui or {}
    base = _read_prompt().partition(LANGUAGE_MARKER)[0].strip()
    lang = norm_language(ui.get("language"))
    parts = [base, f"## LANGUAGE ({lang})\n{language_block(lang)}"]
    ctx = _context_line(ui)
    if ctx:
        parts.append(f"## SESSION CONTEXT\n{ctx}")
    return "\n\n".join(parts)


def build_live_config(types: Any, system_prompt: str, tools: list[Any], handle: str | None, voice: str) -> Any:
    """LiveConnectConfig with session resumption + sliding-window compression (SDD §11.3)."""
    return types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        output_audio_transcription=types.AudioTranscriptionConfig(),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        system_instruction=types.Content(parts=[types.Part.from_text(text=system_prompt)]),
        tools=tools,
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice))
        ),
        session_resumption=types.SessionResumptionConfig(handle=handle),
        context_window_compression=types.ContextWindowCompressionConfig(sliding_window=types.SlidingWindow()),
    )


def _default_connect_factory(settings: dict[str, Any]) -> ConnectFactory:
    from google import genai

    client = genai.Client(vertexai=True, project=settings["project"], location=settings["location"])

    def factory(model: str, config: Any) -> Any:
        return client.aio.live.connect(model=model, config=config)

    return factory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _send(ws: WebSocket, payload: dict[str, Any]) -> bool:
    try:
        await ws.send_json(payload)
        return True
    except Exception:
        return False


def _log_turn(state: dict[str, Any], role: str, text: str) -> None:
    text = " ".join((text or "").split())
    if text:
        state.setdefault("log", []).append((role, text[:RECAP_MAX_CHARS]))


def recap_turns(state: dict[str, Any], types: Any) -> list[Any] | None:
    """Past turns re-sent after reconnect as alternating user/model history (not one blob)."""
    log = state.get("log") or []
    if not log:
        return None
    if len(log) > RECAP_KEEP_FIRST + RECAP_KEEP_LAST:
        lines = log[:RECAP_KEEP_FIRST] + log[-RECAP_KEEP_LAST:]
    else:
        lines = list(log)
    turns: list[Any] = []
    for role, text in lines:
        r = "model" if role == "Agent" else "user"
        if turns and turns[-1].role == r:
            turns[-1].parts.append(types.Part.from_text(text=text))
        else:
            turns.append(types.Content(role=r, parts=[types.Part.from_text(text=text)]))
    if turns and turns[0].role == "user":
        turns[0].parts.insert(0, types.Part.from_text(text="[Earlier in this conversation — history only]"))
    return turns


def _context_line(ui: dict[str, Any] | None) -> str:
    if not ui:
        return ""
    bits = []
    for key in ("field", "well_id", "persona", "screen"):
        if ui.get(key):
            bits.append(f"{key}={ui[key]}")
    if ui.get("language"):
        bits.append(f"language={norm_language(ui['language'])}")
    return f"[UI context] {', '.join(bits)}" if bits else ""


def _summarize(result: dict[str, Any]) -> str:
    s = json.dumps(result, default=str, ensure_ascii=False)
    return s if len(s) <= 400 else s[:397] + "..."


def _merge_ui(state: dict[str, Any], ui_state: Any) -> bool:
    """Merge a ui_state dict; returns True if the language changed."""
    if not isinstance(ui_state, dict):
        return False
    before = norm_language(state["ui"].get("language"))
    state["ui"] = {**state["ui"], **{k: v for k, v in ui_state.items() if v is not None}}
    return norm_language(state["ui"].get("language")) != before


async def _run_tool(ws: WebSocket, name: str, args: dict[str, Any], state: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    """Execute a voice tool off the event loop (10 s timeout) and emit tool_call/action events."""
    persona = state["ui"].get("persona")
    await _send(ws, {"type": "tool_call", "name": name, "status": "running", "args": args})
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(voice_tools.execute_voice_tool, name, args, persona), timeout=timeout_s
        )
    except TimeoutError:
        result = {"status": "UNAVAILABLE", "message": "timeout", "duration_ms": round(timeout_s * 1000)}
    await _send(
        ws,
        {
            "type": "tool_call",
            "name": name,
            "status": "done",
            "args": args,
            "duration_ms": result.get("duration_ms"),
            "result_summary": _summarize(result),
            "result": result,
        },
    )
    tool = voice_tools.VOICE_TOOLS.get(name)
    if tool and tool.action_kind and result.get("status") == "OK":
        await _send(ws, {"type": "action", "kind": tool.action_kind, "payload": result})
    return result


def initial_ui_from_query(websocket: WebSocket) -> dict[str, Any]:
    q = websocket.query_params
    ui = {k: q.get(k) for k in ("field", "well_id", "persona", "screen", "language") if q.get(k)}
    ui["language"] = norm_language(ui.get("language"))
    return ui


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
async def handle_live_websocket(websocket: WebSocket, connect_factory: ConnectFactory | None = None) -> None:
    """Entry point for /ws/live. ``connect_factory`` is injectable for tests (fake sessions)."""
    await websocket.accept()
    settings = live_settings()
    inbound: asyncio.Queue = asyncio.Queue()
    state: dict[str, Any] = {"handle": None, "resumable": False, "ui": initial_ui_from_query(websocket), "log": []}

    async def browser_reader() -> None:
        try:
            while True:
                msg = await websocket.receive()
                if msg.get("type") == "websocket.disconnect":
                    break
                await inbound.put(msg)
        except (WebSocketDisconnect, RuntimeError):
            pass
        except Exception as e:  # pragma: no cover - defensive
            logger.error("browser_reader error: %s", e)
        finally:
            await inbound.put(_CLOSED)

    reader_task = asyncio.create_task(browser_reader())
    try:
        if settings["offline"] and connect_factory is None:
            await _send(websocket, {"type": "status", "status": "fallback", "model": "text", "memory": False,
                                    "message": "WELLPULSE_LIVE_OFFLINE=1 — text mode."})
            await run_fallback_session(websocket, inbound, state)
            return
        await run_resilient_live(websocket, inbound, settings, state, connect_factory)
    finally:
        reader_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await reader_task


async def run_resilient_live(
    websocket: WebSocket,
    inbound: asyncio.Queue,
    settings: dict[str, Any],
    state: dict[str, Any],
    connect_factory: ConnectFactory | None = None,
) -> None:
    try:
        from google.genai import types

        tools = voice_tools.build_genai_tools(state["ui"].get("persona"))
        if connect_factory is None:
            connect_factory = _default_connect_factory(settings)
    except Exception as e:  # broken setup must degrade, not kill the socket
        logger.error("Live setup failed: %s: %s", type(e).__name__, e)
        await _send(websocket, {"type": "status", "status": "fallback", "model": "text", "memory": False,
                                "message": f"Gemini Live setup error ({type(e).__name__}) — switched to text."})
        await run_fallback_session(websocket, inbound, state)
        return

    model = settings["model"]
    failures = 0
    ever_connected = False
    while True:
        handle = state["handle"] if state["resumable"] else None
        resuming = ever_connected
        await _send(websocket, {"type": "status", "status": "reconnecting" if resuming else "connecting", "model": model})
        try:
            # Rebuilt each connect so a language/persona change is honoured on resume.
            config = build_live_config(types, build_system_prompt(state["ui"]), tools, handle, settings["voice"])
            logger.info("Gemini Live connect model=%s resume=%s", model, bool(handle))
            async with connect_factory(model, config) as session:
                failures = 0
                recap = recap_turns(state, types) if resuming else None
                await _send(websocket, {"type": "status", "status": "resumed" if resuming else "connected",
                                        "model": model, "memory": bool(handle) or bool(recap)})
                ever_connected = True
                if recap:
                    try:
                        await session.send_client_content(turns=recap, turn_complete=False)
                    except Exception as e:  # recap is best-effort
                        logger.warning("Recap send failed: %s", e)
                reason = await _run_bidi_stream(websocket, session, inbound, state, settings)
            logger.info("Gemini Live session ended: %s", reason)
            if reason == "browser_closed":
                return
            continue  # go_away / server_closed -> resume with latest handle
        except Exception as e:
            failures += 1
            logger.warning("Gemini Live failure %d/%d: %s: %s", failures, MAX_CONSECUTIVE_FAILURES, type(e).__name__, e)
            if failures >= MAX_CONSECUTIVE_FAILURES:
                await _send(websocket, {"type": "status", "status": "fallback", "model": "text", "memory": bool(state["log"]),
                                        "message": f"Gemini Live unavailable ({type(e).__name__}) — switched to text."})
                await run_fallback_session(websocket, inbound, state)
                return
            if failures >= DROP_HANDLE_AFTER:
                state["resumable"] = False
            await asyncio.sleep(settings["backoff_s"] * failures)


async def _run_bidi_stream(
    websocket: WebSocket, session: Any, inbound: asyncio.Queue, state: dict[str, Any], settings: dict[str, Any]
) -> str:
    """Pump one Gemini session. Returns 'browser_closed' | 'go_away' | 'server_closed'.

    Raises on unexpected upstream errors so the caller can count failures.
    """
    from google.genai import types

    async def send_context(prefix: str = "") -> None:
        line = _context_line(state["ui"])
        if not line:
            return
        lang = norm_language(state["ui"].get("language"))
        text = f"{line}\n{prefix}" if prefix else line
        if prefix:
            text += f"\nLANGUAGE ({lang}): {language_block(lang)}"
        await session.send_client_content(
            turns=[types.Content(role="user", parts=[types.Part.from_text(text=text)])], turn_complete=False
        )

    async def client_to_gemini() -> str:
        while True:
            message = await inbound.get()
            if message is _CLOSED:
                return "browser_closed"
            if message.get("bytes"):
                await session.send_realtime_input(audio=types.Blob(data=message["bytes"], mime_type="audio/pcm;rate=16000"))
                continue
            if not message.get("text"):
                continue
            try:
                data = json.loads(message["text"])
            except json.JSONDecodeError:
                continue
            mtype = data.get("type")
            lang_changed = _merge_ui(state, data.get("ui_state"))
            if mtype == "context":
                await send_context("[Language switched — use the new language from now on.]" if lang_changed else "")
            elif mtype in ("prompt", "text"):
                text = str(data.get("text", ""))
                _log_turn(state, "User", text)
                await _send(websocket, {"type": "voice_state", "state": "thinking"})
                line = _context_line(state["ui"])
                full = f"{line}\n{text}" if line else text
                await session.send_client_content(
                    turns=[types.Content(role="user", parts=[types.Part.from_text(text=full)])], turn_complete=True
                )
            elif mtype == "audio_end":
                await session.send_realtime_input(audio_stream_end=True)
            elif mtype == "interrupt":
                # Client already stopped playback (barge-in); Gemini VAD interrupts on new speech.
                await _send(websocket, {"type": "interrupted"})
                await _send(websocket, {"type": "voice_state", "state": "listening"})
            elif mtype == "debug_reconnect" and settings.get("debug_reconnect"):
                return "go_away"

    async def gemini_to_client() -> str:
        caption: list[str] = []
        turn_output = False
        tool_since_output = False
        while True:
            got_any = False
            async for response in session.receive():
                got_any = True
                sru = getattr(response, "session_resumption_update", None)
                if sru is not None and getattr(sru, "resumable", False) and getattr(sru, "new_handle", None):
                    state["handle"] = sru.new_handle
                    state["resumable"] = True
                if getattr(response, "go_away", None) is not None:
                    logger.info("Gemini Live GoAway (time_left=%s)", getattr(response.go_away, "time_left", None))
                    return "go_away"

                tc = getattr(response, "tool_call", None)
                if tc is not None:
                    tool_since_output = True
                    await _send(websocket, {"type": "voice_state", "state": "thinking"})
                    responses = []
                    for fc in tc.function_calls or []:
                        args = dict(fc.args or {})
                        result = await _run_tool(websocket, fc.name, args, state, settings["tool_timeout_s"])
                        _log_turn(state, "Tool", f"{fc.name} -> {_summarize(result)}")
                        responses.append(types.FunctionResponse(name=fc.name, response={"result": result}, id=fc.id))
                    await session.send_tool_response(function_responses=responses)

                sc = getattr(response, "server_content", None)
                if sc is None:
                    continue
                if getattr(sc, "interrupted", False):
                    state["speaking"] = False
                    await _send(websocket, {"type": "interrupted"})
                it = getattr(sc, "input_transcription", None)
                if it is not None and getattr(it, "text", None):
                    state.setdefault("heard", []).append(it.text)
                    await _send(websocket, {"type": "input_transcript", "text": it.text})
                ot = getattr(sc, "output_transcription", None)
                if ot is not None and getattr(ot, "text", None):
                    turn_output = True
                    caption.append(ot.text)
                    await _send(websocket, {"type": "caption_delta", "text": ot.text, "role": "agent"})
                mt = getattr(sc, "model_turn", None)
                if mt is not None:
                    for part in mt.parts or []:
                        inline = getattr(part, "inline_data", None)
                        if inline is not None and inline.data:
                            if not state.get("speaking"):
                                state["speaking"] = True
                                await _send(websocket, {"type": "voice_state", "state": "speaking"})
                            turn_output = True
                            await websocket.send_bytes(inline.data)
                if getattr(sc, "turn_complete", False):
                    if not turn_output and tool_since_output:
                        continue  # swallow the empty turn_complete Gemini emits right after a tool call
                    turn_output = False
                    tool_since_output = False
                    state["speaking"] = False
                    full_text = "".join(caption).strip()
                    caption = []
                    heard = "".join(state.pop("heard", [])).strip()
                    if heard:
                        _log_turn(state, "User", heard)
                    _log_turn(state, "Agent", full_text)
                    await _send(websocket, {"type": "turn_complete", "full_text": full_text})
                    await _send(websocket, {"type": "voice_state", "state": "idle"})
            if not got_any:
                return "server_closed"

    async def guarded() -> str:
        try:
            return await gemini_to_client()
        except Exception as e:
            with contextlib.suppress(Exception):
                from websockets.exceptions import ConnectionClosedOK

                if isinstance(e, ConnectionClosedOK):
                    return "server_closed"
            if " 1000 " in f" {e} " or " 1001 " in f" {e} ":
                return "server_closed"
            raise

    t1 = asyncio.create_task(client_to_gemini())
    t2 = asyncio.create_task(guarded())
    done, pending = await asyncio.wait([t1, t2], return_when=asyncio.FIRST_COMPLETED)
    for p in pending:
        p.cancel()
    for p in pending:
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await p
    return done.pop().result()


# ---------------------------------------------------------------------------
# Fallback: text turns via app.live.fallback (Stage V swaps in the ADK Runner)
# ---------------------------------------------------------------------------
async def run_fallback_session(websocket: WebSocket, inbound: asyncio.Queue, state: dict[str, Any]) -> None:
    from app.live import fallback

    await _send(websocket, {"type": "voice_state", "state": "idle"})
    warned_audio = False
    while True:
        msg = await inbound.get()
        if msg is _CLOSED:
            return
        if msg.get("bytes"):
            if not warned_audio:
                warned_audio = True
                await _send(websocket, {"type": "error", "message": "Gemini Live unavailable — text mode: type your question."})
            continue
        if not msg.get("text"):
            continue
        try:
            data = json.loads(msg["text"])
        except json.JSONDecodeError:
            continue
        _merge_ui(state, data.get("ui_state"))
        if data.get("type") not in ("prompt", "text"):
            continue
        text = str(data.get("text", ""))
        _log_turn(state, "User", text)
        await _send(websocket, {"type": "voice_state", "state": "thinking"})
        reply = await fallback.answer_text_async(text, dict(state["ui"]), list(state["log"]))
        reply_text = voice_tools.strip_money(str(reply.get("text", "")))
        _log_turn(state, "Agent", reply_text)
        await _send(websocket, {"type": "fallback_reply", "text": reply_text,
                                "recommendation": voice_tools.strip_money(reply.get("recommendation")),
                                "artifacts": voice_tools.to_json_safe(voice_tools.strip_money(reply.get("artifacts") or [])),
                                "actions": voice_tools.to_json_safe(reply.get("actions") or []),
                                "engine": reply.get("engine", "text-fallback")})
        await _send(websocket, {"type": "caption_delta", "text": reply_text, "role": "agent"})
        await _send(websocket, {"type": "turn_complete", "full_text": reply_text})
        await _send(websocket, {"type": "voice_state", "state": "idle"})
