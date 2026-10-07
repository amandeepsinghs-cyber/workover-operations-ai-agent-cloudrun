"""Deterministic scripted LLM for CI and offline runs (``WELLPULSE_AGENT_LLM=fake``).

Behaviour per model call:
* the request ends with the user's text → emit ``function_call`` parts chosen by :func:`app.agent.router.route`
  (UI context is read from the system instruction's ``UI CONTEXT`` line, so the fake sees what Gemini sees);
* the request ends with ``function_response`` parts → emit a final text built ONLY from those responses
  (each tool's own ``message`` plus a few scalar fields), so the number guardrail passes by construction.

It exercises the real ADK Runner, the real tool wrappers (RBAC, redaction) and the real callbacks; only the
model is replaced. It is never used in production unless explicitly configured.
"""

from __future__ import annotations

import re
from collections.abc import AsyncGenerator
from typing import Any

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from app.agent import router

_UI_RE = re.compile(r"UI CONTEXT: field=([^;]*); selected well=([^;]*);")
_LANG_RE = re.compile(r"LANGUAGE: (\w+)")

_KEY_FIELDS = {
    "classify_well_health": ("sick_or_lost_count", "total_wells"),
    "rank_candidates": ("rig_queue_total", "rigless_queue_total"),
}


def _system_text(req: LlmRequest) -> str:
    cfg = getattr(req, "config", None)
    si = getattr(cfg, "system_instruction", None)
    if isinstance(si, str):
        return si
    if si is not None and getattr(si, "parts", None):
        return " ".join(p.text or "" for p in si.parts)
    return ""


def _ui(req: LlmRequest) -> dict[str, Any]:
    m = _UI_RE.search(_system_text(req))
    if not m:
        return {}
    f, w = m.group(1).strip(), m.group(2).strip()
    return {"field": None if f in ("", "ALL") else f, "well_id": None if w in ("", "none selected") else w}


def _user_texts(req: LlmRequest) -> list[str]:
    out = []
    for c in req.contents or []:
        if c.role == "user":
            t = " ".join(p.text for p in (c.parts or []) if getattr(p, "text", None))
            if t.strip():
                out.append(t.strip())
    return out


def _summary(name: str, resp: dict) -> str:
    status = resp.get("status")
    msg = (resp.get("message") or "").strip()
    if status not in ("OK", "LOW_CONFIDENCE"):
        return f"{name}: {status} - {msg or 'not available'}."
    data = resp.get("data")
    bits = []
    if isinstance(data, dict):
        for k in _KEY_FIELDS.get(name, ()):
            if data.get(k) is not None:
                bits.append(f"{k.replace('_', ' ')} {data[k]}")
        if name == "recommend_next_best_action":
            acts = data.get("actions") or []
            if acts:
                a = acts[0]
                bits.append(f"rank 1 {a.get('job_code')} (cost band {a.get('cost_band', 'n/a')}, rig-days "
                            f"{a.get('rig_days')})")
        if name == "compare_interventions" and data.get("verdict"):
            bits.append(f"verdict: {data.get('verdict')}")
    text = f"{name}: {msg}" if msg else f"{name}: done"
    if bits:
        text += " (" + "; ".join(bits) + ")"
    return text.rstrip(".") + "."


class FakeLlm(BaseLlm):
    """Scripted model; see module docstring."""

    model: str = "fake-wellpulse"

    @classmethod
    def supported_models(cls) -> list[str]:
        return [r"fake-.*"]

    async def generate_content_async(self, llm_request: LlmRequest, stream: bool = False) \
            -> AsyncGenerator[LlmResponse, None]:
        contents = list(llm_request.contents or [])
        last = contents[-1] if contents else None
        last_parts = list(getattr(last, "parts", None) or [])
        responses = [p.function_response for p in last_parts if getattr(p, "function_response", None)]
        lang = (_LANG_RE.search(_system_text(llm_request)) or [None, "English"])[1].lower()
        if responses:
            lines = [_summary(fr.name, fr.response or {}) for fr in responses]
            lead = {"hinglish": "Tool results ke hisaab se: ", "hindi": "टूल परिणाम: "}.get(lang, "From the tools: ")
            yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text=lead + " ".join(lines))]))
            return
        texts = _user_texts(llm_request)
        text = texts[-1] if texts else ""
        calls = router.route(text, _ui(llm_request), texts[:-1])
        if not calls:
            yield LlmResponse(content=types.Content(role="model", parts=[types.Part(
                text="WellPulse runs on synthetic, representative data for Geleki, Lakwa and Lakhmani. "
                     "Ask about field production, sick wells, the priority list, a well, or the next best action.")]))
            return
        parts = [types.Part(function_call=types.FunctionCall(name=n, args={k: v for k, v in a.items() if v not in (None, "")}))
                 for n, a in calls]
        yield LlmResponse(content=types.Content(role="model", parts=parts))
