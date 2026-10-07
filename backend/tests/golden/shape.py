"""JSON *shape* inference and validation for golden API snapshots (Stage M).

WellPulse v0.3 data is relative to ``datetime.now()``, so golden files freeze
the response SHAPE (types and keys), never the values. ``int`` and ``float``
are both recorded as ``number`` so that a rounded value never breaks a test.

Schema dialect (a small JSON-Schema subset):
    {"type": ["object"], "properties": {...}, "required": [...]}
    {"type": ["array"], "items": {...}}
    {"type": ["string"]} / ["number"] / ["boolean"] / ["null"]
``type`` is always a sorted list so that merged samples can be unions.
"""

from __future__ import annotations

from typing import Any


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    raise TypeError(f"Unsupported JSON value type: {type(value)!r}")


def infer(value: Any) -> dict:
    """Infer a shape schema from a single JSON value."""
    t = _type_name(value)
    schema: dict = {"type": [t]}
    if t == "object":
        schema["properties"] = {k: infer(v) for k, v in value.items()}
        schema["required"] = sorted(value.keys())
    elif t == "array":
        items: dict | None = None
        for item in value:
            items = infer(item) if items is None else merge(items, infer(item))
        schema["items"] = items if items is not None else {}
    return schema


def merge(a: dict, b: dict) -> dict:
    """Merge two shape schemas (union of types; required = intersection)."""
    if not a:
        return b
    if not b:
        return a
    out: dict = {"type": sorted(set(a.get("type", [])) | set(b.get("type", [])))}
    if "properties" in a or "properties" in b:
        pa, pb = a.get("properties", {}), b.get("properties", {})
        out["properties"] = {
            k: merge(pa.get(k, {}), pb.get(k, {})) for k in sorted(set(pa) | set(pb))
        }
        ra = set(a["required"]) if "required" in a else set(pa)
        rb = set(b["required"]) if "required" in b else set(pb)
        # If one side was never an object, its required set must not shrink the other.
        if "object" not in a.get("type", []):
            ra = rb
        if "object" not in b.get("type", []):
            rb = ra
        out["required"] = sorted(ra & rb)
    if "items" in a or "items" in b:
        out["items"] = merge(a.get("items", {}), b.get("items", {}))
    return out


def validate(value: Any, schema: dict, path: str = "$") -> list[str]:
    """Return a list of shape violations of ``value`` against ``schema``.

    Additive changes (new keys) are allowed; removed required keys and type
    changes are violations. An empty schema ``{}`` accepts anything.
    """
    if not schema:
        return []
    errors: list[str] = []
    t = _type_name(value)
    allowed = schema.get("type", [])
    if allowed and t not in allowed:
        return [f"{path}: expected {allowed}, got {t!r}"]
    if t == "object":
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: missing required key {key!r}")
        for key, sub in props.items():
            if key in value:
                errors.extend(validate(value[key], sub, f"{path}.{key}"))
    elif t == "array":
        items = schema.get("items", {})
        for i, item in enumerate(value):
            errors.extend(validate(item, items, f"{path}[{i}]"))
            if len(errors) > 20:
                break
    return errors
