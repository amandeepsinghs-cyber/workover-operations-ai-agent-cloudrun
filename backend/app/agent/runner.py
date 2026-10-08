"""In-process ADK Runner for WellPulse text chat (SDD §12.1–§12.4).

``run_turn_async(session_id, user_id, persona, field, well_id, language, text, screen)`` → ``ChatReply`` dict.

* Model: ``gemini-3.8-flash`` on Vertex AI with ADC, project/location from ``app.settings`` passed explicitly to
  the genai client (the shell's GOOGLE_CLOUD_PROJECT may be wrong). ``WELLPULSE_AGENT_LLM=fake`` swaps in the
  scripted :class:`app.agent.fake_llm.FakeLlm` (CI). No API key anywhere (D-13).
* Sessions: ``InMemorySessionService`` (D-16, demo); key ``wellpulse:{persona}:{session_id}``.
* Persona / UI context go into session state via ``state_delta`` each turn; tool wrappers read them from
  ``tool_context.state`` and gate with RBAC (SDD §16).
* Artifacts / actions / tool trace are built **only** from this invocation's events (K-4 fix).
* Vertex failure → explicit ``status: "degraded"`` reply from the deterministic router + real tools (SDD §12.6).
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid
from functools import lru_cache
from types import SimpleNamespace
from typing import Any

from app import settings
from app.agent import adk_tools, callbacks, prompt, rbac

logger = logging.getLogger("wellpulse.agent.runner")

APP_NAME = "wellpulse"
DEGRADED_TEXT = "Model unavailable; showing tool output."
LANGUAGES = ("english", "hinglish", "hindi")

# tool name → artifact kind (SDD §12.4; + classifier / map)
ARTIFACT_KIND = {
    "field_production_history": "field_history_chart",
    "compare_fields": "field_comparison",
    "classify_well_health": "health_buckets",
    "attribute_decline": "attribution_waterfall",
    "rank_candidates": "priority_queue",
    "query_wells": "priority_queue",
    "plot_production": "well_production_chart",
    "well_profile": "well_profile",
    "recommend_next_best_action": "nba",
    "compare_interventions": "counterfactual",
    "build_well_dossier": "dossier",
    "search_documents": "citations",
    "classify_intervention": "intervention_classification",
    "render_well_map": "well_map",
    # v0.6 Stage ED-7
    "compare_offset_decline": "offset_decline",
    "well_anomalies": "well_anomalies",
    "wax_sand_behaviour": "wax_sand",
}
# tool name → screen the UI should drill to (T2 "drill down … different screens")
ACTION_SCREEN = {
    "field_production_history": "field_history",
    "compare_fields": "field_compare",
    "classify_well_health": "field_health",
    "rank_candidates": "priority",
    "query_wells": "priority",
    "render_well_map": "map",
    "well_profile": "well",
    "plot_production": "well",
    "recommend_next_best_action": "well",
    "compare_interventions": "well",
    "build_well_dossier": "well",
    "compare_offset_decline": "well",
    "well_anomalies": "well",
    "wax_sand_behaviour": "well",
}
_PLOT_WORDS = ("plot", "chart", "graph", "dikhao")


# --------------------------------------------------------------------------------------------------
# construction
# --------------------------------------------------------------------------------------------------
def build_model(mode: str | None = None) -> Any:
    mode = (mode or settings.AGENT_LLM).lower()
    if mode == "fake":
        from app.agent.fake_llm import FakeLlm

        return FakeLlm()
    from google.adk.models.google_llm import Gemini

    return Gemini(model=settings.TEXT_MODEL,
                  client_kwargs={"vertexai": True, "project": settings.PROJECT_ID, "location": settings.TEXT_LOCATION})


def build_agent(model: Any = None, tools: list | None = None, name: str = "wellpulse") -> Any:
    from google.adk.agents import Agent
    from google.genai import types

    return Agent(
        name=name,
        model=model if model is not None else build_model(),
        description="Urvi AI Agent for ONGC Assam Asset (Geleki, Lakwa, Lakhmani).",
        instruction=prompt.build,
        tools=list(tools if tools is not None else adk_tools.ALL),
        before_model_callback=callbacks.sanitize_history,
        after_model_callback=callbacks.check_numbers,
        generate_content_config=types.GenerateContentConfig(temperature=0.1),
    )


class _Bundle(SimpleNamespace):
    runner: Any
    session_service: Any
    mode: str


@lru_cache(maxsize=4)
def get_bundle(mode: str | None = None) -> _Bundle:
    """One Runner per LLM mode, built lazily (FastAPI lifespan or first request). Not request state."""
    from google.adk.apps import App
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    m = (mode or settings.AGENT_LLM).lower()
    svc = InMemorySessionService()
    app = App(name=APP_NAME, root_agent=build_agent(build_model(m)))
    return _Bundle(runner=Runner(app=app, session_service=svc), session_service=svc, mode=m)


def reset_runner() -> None:
    get_bundle.cache_clear()


def engine_label(mode: str) -> str:
    return "adk:fake-llm" if mode == "fake" else f"adk:{settings.TEXT_MODEL}@vertex/{settings.TEXT_LOCATION}"


# --------------------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------------------
def _ui_state(persona: str, field: str | None, well_id: str | None, language: str, screen: str | None,
              cluster_id: str | None = None) -> dict[str, Any]:
    wid = adk_tools.norm_well_id(well_id)
    fld = adk_tools.norm_field(field)
    if wid and not fld:
        try:
            from app.analytics.tools.common import well_master_row

            fld = (well_master_row(wid) or {}).get("field") or ""
        except Exception:  # noqa: BLE001
            fld = ""
    if wid and not cluster_id:
        cluster_id = rbac._cluster_of_well(wid)  # own-cluster scoping for FE (SDD §16.2)
    return {"persona": persona, "ui_field": fld or "ALL", "ui_well_id": wid, "ui_cluster_id": cluster_id or "",
            "ui_screen": screen or "", "language": language}


def _norm_language(language: str | None) -> str:
    lang = (language or settings.DEFAULT_LANGUAGE).strip().lower()
    return lang if lang in LANGUAGES else settings.DEFAULT_LANGUAGE


def build_artifacts(calls: list[dict], user_text: str) -> tuple[list[dict], list[dict]]:
    """Artifacts + navigation actions from this turn's tool calls (K-4: nothing global)."""
    artifacts, actions, seen = [], [], set()
    wants_plot = any(w in (user_text or "").lower() for w in _PLOT_WORDS)
    for c in calls:
        name, resp, args = c["name"], c.get("response") or {}, c.get("args") or {}
        status = resp.get("status")
        if status not in ("OK", "LOW_CONFIDENCE"):
            continue
        if name == "ui_control":  # v0.6 ED-11: the browser executes the allow-listed command
            cmd = (resp.get("data") or {}).get("command") if isinstance(resp.get("data"), dict) else None
            if isinstance(cmd, dict) and cmd.get("action"):
                actions.append({"kind": "ui", "command": cmd, "source_tool": name})
            continue
        kind = ARTIFACT_KIND.get(name)
        if name == "field_production_history" and not (args.get("plot") or wants_plot):
            kind = None  # BDD-F11-S01 "no chart is shown yet" (tell first)
        if kind and (kind, name, str(args)) not in seen:
            seen.add((kind, name, str(args)))
            artifacts.append({"kind": kind, "tool": name, "tool_id": resp.get("tool_id") or "",
                              "data": resp.get("data"), "message": resp.get("message", ""),
                              "provenance": resp.get("provenance") or {}})
        screen = ACTION_SCREEN.get(name)
        if name == "field_production_history" and kind is None:
            screen = None
        if screen:
            data = resp.get("data") if isinstance(resp.get("data"), dict) else {}
            well = args.get("well_id") or data.get("well_id") or (data.get("identity") or {}).get("well_id")
            field = args.get("field") or data.get("field")
            act = {"kind": "navigate", "screen": screen, "field": field or None,
                   "well_id": adk_tools.norm_well_id(well) or None if screen == "well" else None, "source_tool": name}
            if not any((a.get("screen"), a.get("field"), a.get("well_id")) == (act["screen"], act["field"], act["well_id"])
                       for a in actions):
                actions.append(act)
    # ED-14 (D-41): when the agent already drove the screen this turn (e.g. health_filter), do not also open the
    # Health & priority screen just because a health / ranking tool was consulted.
    if any(a.get("kind") == "ui" for a in actions):
        actions = [a for a in actions if not (a.get("kind") == "navigate" and a.get("screen") in ("field_health", "priority"))]
    return artifacts, actions


def _recommendation(calls: list[dict], persona: str) -> dict | None:
    for c in calls:
        if c["name"] == "recommend_next_best_action" and (c.get("response") or {}).get("status") == "OK":
            wid = adk_tools.norm_well_id((c.get("args") or {}).get("well_id")) or \
                adk_tools.norm_well_id((c["response"].get("data") or {}).get("well_id"))
            if not wid:
                return None
            try:
                from app.analytics.tools.nba import (
                    recommend_next_best_action,
                    recommendation_from_nba,
                )

                rec = recommendation_from_nba(recommend_next_best_action(wid))
                return rbac.redact(persona, "well.nba", rec) if rec else None
            except Exception:  # noqa: BLE001
                return None
    return None


# --------------------------------------------------------------------------------------------------
# the turn
# --------------------------------------------------------------------------------------------------
async def run_turn_async(session_id: str | None, user_id: str | None, persona: str | None, field: str | None,
                         well_id: str | None, language: str | None, text: str, screen: str | None = None,
                         mode: str | None = None, debug: bool = False) -> dict[str, Any]:
    from google.genai import types

    t0 = time.perf_counter()
    p = rbac.resolve_persona(persona)
    lang = _norm_language(language)
    sid_client = session_id or uuid.uuid4().hex
    sid = f"wellpulse:{p}:{sid_client}"
    uid = user_id or "web"
    b = get_bundle(mode)
    state = _ui_state(p, field, well_id, lang, screen)

    sess = await b.session_service.get_session(app_name=APP_NAME, user_id=uid, session_id=sid)
    if sess is None:
        await b.session_service.create_session(app_name=APP_NAME, user_id=uid, session_id=sid, state=dict(state))

    calls: dict[str, dict] = {}
    order: list[str] = []
    final_parts: list[str] = []
    try:
        with rbac.persona_scope(p):
            async for ev in b.runner.run_async(user_id=uid, session_id=sid,
                                               new_message=types.Content(role="user", parts=[types.Part(text=text)]),
                                               state_delta=dict(state)):
                ts = getattr(ev, "timestamp", None) or time.time()
                for fc in ev.get_function_calls() or []:
                    cid = fc.id or f"{fc.name}:{len(order)}"
                    calls[cid] = {"name": fc.name, "args": dict(fc.args or {}), "t_call": ts, "response": None}
                    order.append(cid)
                for fr in ev.get_function_responses() or []:
                    cid = fr.id if fr.id in calls else next((k for k in reversed(order) if calls[k]["name"] == fr.name
                                                             and calls[k]["response"] is None), None)
                    if cid is None:
                        cid = f"{fr.name}:{len(order)}"
                        calls[cid] = {"name": fr.name, "args": {}, "t_call": ts}
                        order.append(cid)
                    calls[cid]["response"] = fr.response or {}
                    calls[cid]["t_resp"] = ts
                if (ev.content and ev.content.parts and getattr(ev, "author", "") != "user" and not ev.partial
                        and not ev.get_function_calls() and not ev.get_function_responses()):
                    final_parts += [pt.text for pt in ev.content.parts if pt.text and not getattr(pt, "thought", False)]
    except Exception as e:  # noqa: BLE001 - Vertex / network failure → explicit degraded reply (SDD §12.6)
        logger.warning("agent turn failed (%s: %s); degraded reply", type(e).__name__, e)
        return degraded_reply(sid_client, p, state, text, lang, b.mode, error=f"{type(e).__name__}: {e}")

    ordered = [calls[k] for k in order]
    artifacts, actions = build_artifacts(ordered, text)
    sess = await b.session_service.get_session(app_name=APP_NAME, user_id=uid, session_id=sid)
    ncheck = dict((sess.state or {}).get("last_number_check") or {}) if sess else {}
    # the check is recorded per model turn; only trust it if this turn produced the final text
    if not final_parts:
        ncheck = {"ok": True, "unmatched": []}
    reply = {
        "session_id": sid_client,
        "response": "\n".join(x.strip() for x in final_parts if x.strip()) or "",
        "artifacts": artifacts,
        "actions": actions,
        "tool_calls": [{"name": c["name"], "args": c["args"],
                        "status": (c.get("response") or {}).get("status", "PENDING"),
                        "duration_ms": round(max(0.0, (c.get("t_resp") or c["t_call"]) - c["t_call"]) * 1000)}
                       for c in ordered],
        "recommendation": _recommendation(ordered, p),
        "status": "ok",
        "engine": engine_label(b.mode),
        "language": lang,
        "persona": p,
        "number_check": {"ok": bool(ncheck.get("ok", True)), "unmatched": list(ncheck.get("unmatched") or [])},
        "duration_ms": round((time.perf_counter() - t0) * 1000),
    }
    if debug:
        reply["trace"] = {"tool_returns": [{"name": c["name"], "response": c.get("response")} for c in ordered],
                          "ui_state": state}
    return reply


def degraded_reply(session_id: str, persona: str, state: dict, text: str, language: str, mode: str,
                   error: str = "") -> dict[str, Any]:
    """Deterministic route + real tools; explicit status 'degraded' (W-12: never a silent keyword answer)."""
    from app.agent import router

    ctx = SimpleNamespace(state=dict(state))
    calls = []
    for name, args in router.route(text, {"field": state.get("ui_field"), "well_id": state.get("ui_well_id")}):
        fn = adk_tools.TOOLS_BY_NAME.get(name)
        if fn is None:
            continue
        with rbac.persona_scope(persona):
            resp = fn(**{k: v for k, v in args.items() if v not in (None, "")}, tool_context=ctx)
        calls.append({"name": name, "args": args, "response": resp, "t_call": 0.0, "t_resp": 0.0})
    artifacts, actions = build_artifacts(calls, text)
    msgs = [f"{c['name']}: {(c['response'] or {}).get('message', '')}".strip() for c in calls]
    return {
        "session_id": session_id, "response": " ".join([DEGRADED_TEXT] + msgs).strip(), "artifacts": artifacts,
        "actions": actions, "tool_calls": [{"name": c["name"], "args": c["args"],
                                            "status": (c["response"] or {}).get("status", ""), "duration_ms": 0}
                                           for c in calls],
        "recommendation": _recommendation(calls, persona), "status": "degraded",
        "engine": engine_label(mode) + ":degraded", "language": language, "persona": persona,
        "number_check": {"ok": True, "unmatched": []}, "error": error[:300],
    }


def run_turn(session_id: str | None = None, user_id: str | None = None, persona: str | None = None,
             field: str | None = None, well_id: str | None = None, language: str | None = None, text: str = "",
             screen: str | None = None, mode: str | None = None) -> dict[str, Any]:
    """Sync wrapper (Live text fallback runs in a worker thread). Safe inside or outside an event loop."""
    coro_args = {"session_id": session_id, "user_id": user_id, "persona": persona, "field": field, "well_id": well_id,
                     "language": language, "text": text, "screen": screen, "mode": mode}
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(run_turn_async(**coro_args))
    box: dict[str, Any] = {}

    def _worker() -> None:
        box["r"] = asyncio.run(run_turn_async(**coro_args))

    th = threading.Thread(target=_worker, daemon=True)
    th.start()
    th.join()
    return box["r"]
