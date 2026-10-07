"""``GET /api/me/capabilities`` (SDD §13.4, §14.2, §16; Stage Y).

Returns the resolved persona (``X-Persona``, default ``ASSET_MANAGER``) and its capabilities from the single
matrix in ``app.agent.rbac``. UI hint only — enforcement is server-side in every gated route / tool.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.agent import rbac

router = APIRouter()


@router.get("/me/capabilities")
def me_capabilities(persona: str = Depends(rbac.get_persona)):
    return {"status": "OK", "data": rbac.capabilities_for(persona), "message": "", "missing_fields": [],
            "provenance": {"tool_id": "rbac", "source": "app/agent/rbac.py MATRIX (SDD §16.2)"}}
