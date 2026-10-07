"""Unit tests for extended ADK tool wrappers (SDD §12.3, Stage V)."""

from __future__ import annotations

import json
import types
from typing import Any

import pytest

from app.agent.adk_tools import ALL
from app.agent.adk_tools_ext import EXT_TOOLS, classify_intervention, query_wells

ALLOWED_STATUSES = {
    "OK",
    "UNAVAILABLE",
    "INSUFFICIENT_HISTORY",
    "LOW_CONFIDENCE",
    "DISCRIMINATOR_UNAVAILABLE",
}

FORBIDDEN_KEY_PATTERNS = ("usd", "inr", "payback", "npv")


def assert_no_currency_keys(obj: Any, path: str = "") -> None:
    """Recursively verify no dictionary key contains forbidden currency patterns."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            for pat in FORBIDDEN_KEY_PATTERNS:
                assert pat not in kl, f"Forbidden currency pattern '{pat}' found in key '{path}.{k}'"
            assert_no_currency_keys(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            assert_no_currency_keys(item, f"{path}[{idx}]")


@pytest.fixture
def fake_context() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        state={
            "persona": "ASSET_MANAGER",
            "ui_field": "Geleki",
            "ui_well_id": "GK-129",
        }
    )


def _get_minimal_args(fn: Any, context: types.SimpleNamespace) -> dict[str, Any]:
    name = fn.__name__
    if name == "route_intervention":
        return {"mechanism": "WAX", "tool_context": context}
    if name in ("estimate_uplift", "check_mro"):
        return {"job_code": "WAX_REMOVAL", "tool_context": context}
    if name == "get_document":
        return {"doc_id": "SOP-IC-01", "tool_context": context}
    return {"tool_context": context}


@pytest.mark.parametrize("wrapper", EXT_TOOLS, ids=lambda fn: fn.__name__)
def test_all_ext_tools_call(wrapper: Any, fake_context: types.SimpleNamespace) -> None:
    args = _get_minimal_args(wrapper, fake_context)
    result = wrapper(**args)

    assert isinstance(result, dict), f"{wrapper.__name__} did not return a dict"
    for expected_key in ("status", "message", "tool_id"):
        assert expected_key in result, f"Key '{expected_key}' missing from {wrapper.__name__} result"

    assert (
        result["status"] in ALLOWED_STATUSES
    ), f"{wrapper.__name__} returned unexpected status '{result['status']}'"

    # Verify JSON serializability
    dumped = json.dumps(result)
    assert dumped is not None

    # Verify recursive currency absence
    assert_no_currency_keys(result, wrapper.__name__)


def test_field_engineer_own_cluster_query_wells() -> None:
    """FIELD_ENGINEER with no ui_well_id and no cluster gets status UNAVAILABLE for query_wells."""
    fe_ctx = types.SimpleNamespace(state={"persona": "FIELD_ENGINEER", "ui_field": "Geleki"})
    result = query_wells(tool_context=fe_ctx)

    assert isinstance(result, dict)
    assert result.get("status") == "UNAVAILABLE"
    assert "limited to own cluster" in result.get("message", "") or "not permitted" in result.get("message", "")


def test_ed_classify_intervention() -> None:
    """ED persona calling classify_intervention works (redacted to summary / allowed status)."""
    ed_ctx = types.SimpleNamespace(
        state={
            "persona": "ED",
            "ui_field": "Geleki",
            "ui_well_id": "GK-129",
        }
    )
    result = classify_intervention(tool_context=ed_ctx)

    assert isinstance(result, dict)
    assert result.get("status") in ALLOWED_STATUSES
    assert result.get("tool_id") == "TC-021"
    json.dumps(result)
    assert_no_currency_keys(result, "classify_intervention_ed")


def test_all_tools_count_and_unique_names() -> None:
    """from app.agent.adk_tools import ALL has len 30 and unique __name__s."""
    assert len(ALL) == 30, f"Expected 30 tools in ALL, found {len(ALL)}"
    names = [t.__name__ for t in ALL]
    assert len(set(names)) == 30, f"Duplicate tool names in ALL: {names}"
    assert len(EXT_TOOLS) == 19, f"Expected 19 tools in EXT_TOOLS, found {len(EXT_TOOLS)}"
