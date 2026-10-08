"""``POST /api/chat`` — the text agent (SDD §13.4/§13.5). Persona from ``X-Persona``; UI context in the body.

Response = ``ChatReply``: ``{session_id, response, artifacts[], actions[], tool_calls[], recommendation, status,
engine, language, persona, number_check}``. ``X-Debug-Trace: 1`` adds ``trace.tool_returns`` so tests can check
that every number in ``response`` appears in that turn's tool returns (BDD-X-S01).
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from app import settings
from app.agent import rbac

router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str | None = None
    language: Literal["english", "hinglish", "hindi"] = settings.DEFAULT_LANGUAGE  # type: ignore[assignment]
    field: str | None = None
    well_id: str | None = None
    screen: str | None = None


class Artifact(BaseModel):
    kind: str
    tool: str
    tool_id: str
    data: Any = None
    message: str = ""
    provenance: dict = {}


class ToolCallTrace(BaseModel):
    name: str
    args: dict
    status: str
    duration_ms: int


class AgentAction(BaseModel):
    kind: str  # "navigate" | "ui" (v0.6 ED-11)
    screen: str | None = None
    field: str | None = None
    well_id: str | None = None
    command: dict | None = None  # kind == "ui": allow-listed ui_control command
    source_tool: str


class ChatReply(BaseModel):
    session_id: str
    response: str
    artifacts: list[Artifact] = []
    actions: list[AgentAction] = []
    tool_calls: list[ToolCallTrace] = []
    recommendation: dict | None = None
    status: Literal["ok", "degraded"] = "ok"
    engine: str
    language: str
    persona: str
    number_check: dict = {}
    trace: dict | None = None


async def chat_turn(req: ChatRequest, persona: str, debug: bool = False) -> dict[str, Any]:
    from app.agent.runner import run_turn_async

    return await run_turn_async(session_id=req.session_id, user_id="web", persona=persona, field=req.field,
                                well_id=req.well_id, language=req.language, text=req.message, screen=req.screen,
                                debug=debug)


@router.post("/chat", response_model=ChatReply, response_model_exclude_none=True)
async def post_chat(req: ChatRequest, persona: str = Depends(rbac.get_persona),
                    x_debug_trace: str | None = Header(None, alias="X-Debug-Trace")) -> dict[str, Any]:
    return await chat_turn(req, persona, debug=(x_debug_trace or "").strip() in ("1", "true", "yes"))
