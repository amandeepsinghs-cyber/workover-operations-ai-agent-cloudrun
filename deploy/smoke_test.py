"""WellPulse post-deploy smoke test (Stage W.4, SDD §17).

    cd backend && uv run --frozen --no-dev python ../deploy/smoke_test.py https://wellpulse-app-bowxi5445q-uc.a.run.app
    cd backend && uv run --frozen python ../deploy/smoke_test.py http://localhost:8002 --ws-timeout 30

Checks (each prints PASS/FAIL with latency; exit code = number of failures):
  1. GET /api/healthz (falls back to /api/health)       -> 200, JSON
  2. GET /api/wells/kpis                                 -> 200, total_wells > 0
  3. GET /api/fields                                     -> 200, >= 1 field
  4. GET /api/docs/search?q=SOP                          -> 200, status OK and >= 1 hit (index baked in)
  5. WS  /ws/live handshake                              -> first frame {"type":"status"}; then
                                                            "connected" (Gemini Live) or "fallback"
                                                            (text mode) within --ws-timeout
  6. GET /  (SPA index)                                  -> 200, text/html with a root div
Stdlib HTTP; the WS check uses `websockets` (in the backend lock via uvicorn[standard]).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Callable

RESULTS: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str) -> None:
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}", flush=True)


def http_get(url: str, headers: dict[str, str] | None = None, timeout: float = 30.0) -> tuple[int, str, str, float]:
    req = urllib.request.Request(url, headers={"User-Agent": "wellpulse-smoke/0.4", **(headers or {})})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
            body = r.read().decode("utf-8", "replace")
            return r.status, r.headers.get("content-type", ""), body, time.perf_counter() - t0
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace") if e.fp else ""
        return e.code, e.headers.get("content-type", "") if e.headers else "", body, time.perf_counter() - t0


def check_json(name: str, url: str, predicate: Callable[[Any], tuple[bool, str]],
               headers: dict[str, str] | None = None) -> int:
    try:
        status, ctype, body, dt = http_get(url, headers)
    except Exception as e:  # network / TLS / timeout
        record(name, False, f"{type(e).__name__}: {e}")
        return 0
    if status != 200:
        record(name, False, f"HTTP {status} in {dt*1000:.0f} ms: {body[:200]}")
        return status
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        record(name, False, f"non-JSON ({ctype}) in {dt*1000:.0f} ms: {body[:120]}")
        return status
    ok, detail = predicate(data)
    record(name, ok, f"HTTP 200 in {dt*1000:.0f} ms; {detail}")
    return status


def _health(d: Any) -> tuple[bool, str]:
    return isinstance(d, dict), f"status={d.get('status') if isinstance(d, dict) else d!r}"


def _kpis(d: Any) -> tuple[bool, str]:
    n = d.get("total_wells", 0) if isinstance(d, dict) else 0
    return bool(n and n > 0), f"total_wells={n}"


def _fields(d: Any) -> tuple[bool, str]:
    # Accept {fields:[...]}, an envelope {data:{fields:[...]}} or a bare list.
    fields = d
    if isinstance(d, dict):
        inner = d.get("data")
        fields = d.get("fields") or (inner.get("fields") if isinstance(inner, dict) else inner)
    names = [f.get("field") or f.get("name") for f in fields if isinstance(f, dict)] if isinstance(fields, list) else []
    return len(names) >= 1, f"fields={names}"


def _docs(d: Any) -> tuple[bool, str]:
    if not isinstance(d, dict):
        return False, f"unexpected {type(d).__name__}"
    hits = d.get("data") or []
    return d.get("status") == "OK" and len(hits) >= 1, f"status={d.get('status')} hits={len(hits)} msg={d.get('message')!r}"


async def ws_handshake(base: str, timeout: float) -> None:
    name = "WS /ws/live handshake"
    try:
        import websockets
    except ImportError:
        record(name, False, "python package `websockets` not available (run via `uv run` in backend/)")
        return
    ws_url = base.replace("https://", "wss://", 1).replace("http://", "ws://", 1) + "/ws/live?language=english&screen=smoke"
    t0 = time.perf_counter()
    statuses: list[str] = []
    try:
        async with websockets.connect(ws_url, open_timeout=timeout, max_size=None) as ws:
            deadline = t0 + timeout
            while time.perf_counter() < deadline:
                raw = await asyncio.wait_for(ws.recv(), timeout=max(0.1, deadline - time.perf_counter()))
                if isinstance(raw, bytes):
                    continue  # audio frames
                msg = json.loads(raw)
                if msg.get("type") == "status":
                    statuses.append(str(msg.get("status")))
                    if msg.get("status") in ("connected", "fallback"):
                        break
            dt = time.perf_counter() - t0
            final = statuses[-1] if statuses else None
            ok = bool(statuses) and statuses[0] in ("connecting", "fallback") and final in ("connected", "fallback")
            note = "" if final == "connected" else " (text fallback: Gemini Live not connected)" if final == "fallback" else ""
            record(name, ok, f"statuses={statuses} in {dt*1000:.0f} ms{note}")
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}; statuses={statuses}")


def check_spa(base: str) -> None:
    name = "GET / (SPA index)"
    try:
        status, ctype, body, dt = http_get(base + "/")
    except Exception as e:
        record(name, False, f"{type(e).__name__}: {e}")
        return
    ok = status == 200 and "text/html" in ctype and ('id="root"' in body or "<script" in body)
    record(name, ok, f"HTTP {status} {ctype} in {dt*1000:.0f} ms, {len(body)} bytes")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("base_url", help="e.g. https://wellpulse-app-bowxi5445q-uc.a.run.app")
    ap.add_argument("--ws-timeout", type=float, default=25.0)
    ap.add_argument("--skip-ws", action="store_true")
    a = ap.parse_args(argv)
    base = a.base_url.rstrip("/")
    print(f"WellPulse smoke test -> {base}")

    # 1. health: /api/healthz is the SDD name; the app currently serves /api/health.
    try:
        status, *_ = http_get(base + "/api/healthz")
    except Exception:
        status = 0
    if status == 200:
        check_json("GET /api/healthz", base + "/api/healthz", _health)
    else:
        check_json("GET /api/health (no /api/healthz)", base + "/api/health", _health)

    check_json("GET /api/wells/kpis", base + "/api/wells/kpis", _kpis)
    check_json("GET /api/fields", base + "/api/fields", _fields)
    st = check_json("GET /api/docs/search?q=SOP", base + "/api/docs/search?q=SOP", _docs)
    if st == 403:  # default persona lacks the capability: retry as the field engineer
        RESULTS.pop()
        check_json("GET /api/docs/search?q=SOP [X-Persona: FIELD_ENGINEER]", base + "/api/docs/search?q=SOP",
                   _docs, headers={"X-Persona": "FIELD_ENGINEER"})
    if not a.skip_ws:
        asyncio.run(ws_handshake(base, a.ws_timeout))
    check_spa(base)

    failures = sum(1 for _, ok, _ in RESULTS if not ok)
    print(f"\n{len(RESULTS) - failures}/{len(RESULTS)} checks passed")
    return failures


if __name__ == "__main__":
    sys.exit(main())
