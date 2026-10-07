"""Agent callbacks (SDD §12.6): number-trace guardrail + history sanitiser.

* :func:`check_numbers` (after-model): every numeral in a final text reply must match — within the rounding the
  reply uses — a number present in THIS invocation's tool returns (``function_response`` payloads, including
  numbers inside their strings and list lengths) or the user's message. Unmatched numerals are masked as
  ``«see table»`` and recorded in session state ``last_number_check`` (read by the runner → ``ChatReply``).
  This makes BDD-X-S01 "The agent never computes its own numbers" executable.
  *Deviation from SDD §12.6 (documented):* no regeneration round-trip — masking is deterministic and keeps
  latency flat; the masked count is reported per turn and measured by the live eval.
* :func:`sanitize_history` (before-model): replaces oversized tool payloads in the **request copy** (never the
  stored session events) with compact forms: long time series → count + first/last point; long lists →
  first ``MAX_LIST`` items + ``_truncated_from``. The full payload still reaches the UI as an artifact.

The numeric matcher is pure (:func:`unmatched_numbers`) so tests and the Live fallback can reuse it.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from typing import Any

MASK = "«see table»"
MAX_LIST = 30
SMALL_INT_MAX = 10  # cardinals/ordinals ("top 3", "two wells") are language, not data

# Identifiers that contain digits but are not quantities: GK-129, LKW-047, IC-08, TC-022, D11, SOP-IC-04, L1..L5, Q3
_IDENT_RE = re.compile(r"\b(?:[A-Za-z]{1,8}[-_]?)+\d+(?:[-_][A-Za-z0-9]+)*\b")
_DATE_RE = re.compile(r"\b\d{4}-\d{2}(?:-\d{2})?\b")
_NUM_RE = re.compile(r"(?<![\w.])[-+−]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?![\w])")
_ANY_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


# --------------------------------------------------------------------------------------------------
# allowed-number harvesting
# --------------------------------------------------------------------------------------------------
def harvest_numbers(obj: Any, out: set[float] | None = None, strings: list[str] | None = None) -> set[float]:
    """All numbers in a JSON-like payload: numeric leaves, numbers inside string leaves, list lengths."""
    out = set() if out is None else out
    if isinstance(obj, bool) or obj is None:
        return out
    if isinstance(obj, (int, float)):
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return out
        out.add(float(obj))
        return out
    if isinstance(obj, str):
        if strings is not None:
            strings.append(obj)
        for m in _ANY_NUM_RE.findall(obj.replace(",", "")):
            try:
                out.add(float(m))
            except ValueError:
                pass
        return out
    if isinstance(obj, dict):
        for v in obj.values():
            harvest_numbers(v, out, strings)
        return out
    if isinstance(obj, (list, tuple)):
        out.add(float(len(obj)))
        for v in obj:
            harvest_numbers(v, out, strings)
        return out
    return out


def _decimals(tok: str) -> int:
    return len(tok.split(".", 1)[1]) if "." in tok else 0


def _matches(x: float, d: int, allowed: Iterable[float], pct: bool) -> bool:
    tol = 0.5 * 10 ** (-d) + 1e-9
    for y in allowed:
        for cand in (y, -y) + ((y * 100.0, -y * 100.0) if pct or abs(y) <= 1.0 else ()):
            if abs(x - cand) <= tol:
                return True
            # integer rounding of large values the model shortens ("1,235" for 1234.6 handled above);
            # also accept the value rounded to 1 significant decimal less when d == 0 and |y| >= 100
    return False


def extract_numbers(text: str) -> list[tuple[str, float, int, bool, int, int]]:
    """Numerals that look like quantities: (token, value, decimals, is_pct, start, end). Identifiers/dates skipped."""
    spans: list[tuple[int, int]] = [(m.start(), m.end()) for m in _IDENT_RE.finditer(text)]
    spans += [(m.start(), m.end()) for m in _DATE_RE.finditer(text)]

    def inside(a: int, b: int) -> bool:
        return any(s <= a and b <= e for s, e in spans)

    out = []
    for m in _NUM_RE.finditer(text):
        a, b = m.start(), m.end()
        if inside(a, b):
            continue
        tok = m.group(0).replace("−", "-")
        try:
            val = float(tok.replace(",", "").replace("+", ""))
        except ValueError:
            continue
        rest = text[b:b + 2]
        is_pct = rest.startswith(("%", " %")) or text[b:b + 4].lower().startswith(" pct")
        out.append((tok, val, _decimals(tok), is_pct, a, b))
    return out


def unmatched_numbers(text: str, allowed: set[float], date_strings: Iterable[str] = ()) -> list[tuple[str, int, int]]:
    """Numerals in ``text`` with no match in ``allowed``. Dates are checked as whole strings."""
    bad: list[tuple[str, int, int]] = []
    known_dates = set(date_strings)
    for m in _DATE_RE.finditer(text):
        if known_dates and not any(m.group(0) in s for s in known_dates):
            bad.append((m.group(0), m.start(), m.end()))
    for tok, val, d, pct, a, b in extract_numbers(text):
        if float(val).is_integer() and 0 <= abs(val) <= SMALL_INT_MAX and d == 0:
            continue
        if not _matches(val, d, allowed, pct):
            bad.append((tok, a, b))
    return bad


def mask(text: str, bad: list[tuple[str, int, int]]) -> str:
    for tok, a, b in sorted(bad, key=lambda t: -t[1]):
        text = text[:a] + MASK + text[b:]
    return text


def check_text(text: str, tool_payloads: list[Any], user_text: str = "", extra_allowed: Iterable[float] = ()) \
        -> tuple[str, list[str]]:
    """Pure guardrail: returns (masked_text, unmatched_tokens)."""
    allowed: set[float] = {float(v) for v in extra_allowed}
    strings: list[str] = []
    for p in tool_payloads:
        harvest_numbers(p, allowed, strings)
    harvest_numbers(user_text, allowed, strings)
    bad = unmatched_numbers(text, allowed, strings)
    return (mask(text, bad) if bad else text), [t for t, _, _ in bad]


def prompt_facts(state: Any = None) -> dict[str, Any]:
    """Facts the system prompt itself states (as_of, data window, plot-month options): grounded like tool data."""
    from app import settings

    facts: dict[str, Any] = {"as_of": settings.AS_OF.isoformat(), "data_start": settings.DATA_START.isoformat(),
                             "data_end": settings.DATA_END.isoformat()}
    try:
        from app.agent import prompt

        facts["system_prompt"] = prompt.render(state or {})
    except Exception:  # noqa: BLE001, S110 - the static facts above still apply
        pass
    return facts


# --------------------------------------------------------------------------------------------------
# ADK callbacks
# --------------------------------------------------------------------------------------------------
def _invocation_payloads(callback_context: Any) -> tuple[list[Any], str]:
    """Tool returns + user text of the current invocation, from the session's own events (no globals)."""
    inv = getattr(callback_context, "invocation_id", None)
    session = getattr(callback_context, "session", None)
    payloads: list[Any] = []
    user_text = ""
    for ev in list(getattr(session, "events", []) or []):
        if inv is not None and getattr(ev, "invocation_id", None) != inv:
            continue
        content = getattr(ev, "content", None)
        for part in (getattr(content, "parts", None) or []):
            fr = getattr(part, "function_response", None)
            if fr is not None and fr.response is not None:
                payloads.append(fr.response)
            elif getattr(ev, "author", "") == "user" and getattr(part, "text", None):
                user_text += " " + part.text
    uc = getattr(callback_context, "user_content", None)
    if uc is not None and not user_text:
        user_text = " ".join(p.text for p in (uc.parts or []) if getattr(p, "text", None))
    return payloads, user_text


def check_numbers(callback_context: Any, llm_response: Any) -> Any:
    """after_model_callback: mask numerals that no tool returned in this turn; record the result."""
    content = getattr(llm_response, "content", None)
    parts = list(getattr(content, "parts", None) or [])
    if not parts or any(getattr(p, "function_call", None) for p in parts):
        return None
    if getattr(llm_response, "partial", False):
        return None
    texts = [p for p in parts if getattr(p, "text", None) and not getattr(p, "thought", False)]
    if not texts:
        return None
    payloads, user_text = _invocation_payloads(callback_context)
    facts = prompt_facts(callback_context.state)
    all_bad: list[str] = []
    for p in texts:
        new, bad = check_text(p.text, [facts, *payloads], user_text)
        if bad:
            p.text = new
            all_bad += bad
    try:
        callback_context.state["last_number_check"] = {"ok": not all_bad, "unmatched": all_bad,
                                                       "n_tool_returns": len(payloads)}
    except Exception:  # noqa: BLE001, S110 - read-only state in some contexts; the masking already happened
        pass
    return llm_response if all_bad else None


def _is_series(lst: list) -> bool:
    return bool(lst) and isinstance(lst[0], dict) and bool({"date", "period", "month"} & set(lst[0]))


def compact_for_model(obj: Any, depth: int = 0) -> Any:
    if isinstance(obj, dict):
        return {k: compact_for_model(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, list):
        if len(obj) > MAX_LIST:
            if _is_series(obj):
                return {"_series_points": len(obj), "first": obj[0], "last": obj[-1]}
            return [compact_for_model(v, depth + 1) for v in obj[:MAX_LIST]] + [{"_truncated_from": len(obj)}]
        return [compact_for_model(v, depth + 1) for v in obj]
    return obj


def sanitize_history(callback_context: Any, llm_request: Any) -> None:
    """before_model_callback: compact oversized function_response payloads in the request copy only."""
    from google.genai import types

    contents = list(getattr(llm_request, "contents", None) or [])
    new_contents = []
    changed = False
    for c in contents:
        parts = list(c.parts or [])
        new_parts = []
        for p in parts:
            fr = getattr(p, "function_response", None)
            if fr is not None and isinstance(fr.response, dict):
                compact = compact_for_model(fr.response)
                if compact != fr.response:
                    changed = True
                    p = types.Part(function_response=types.FunctionResponse(id=fr.id, name=fr.name, response=compact))
            new_parts.append(p)
        new_contents.append(types.Content(role=c.role, parts=new_parts) if changed else c)
    if changed:
        llm_request.contents = new_contents
