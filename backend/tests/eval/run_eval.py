"""Stage V agent eval: tool-selection accuracy + number grounding on ``datasets/v04-dataset.json``.

Runs every case through the real ADK Runner (``app.agent.runner.run_turn_async``) — ``--mode vertex`` uses
``gemini-3.8-flash`` on Vertex AI (ADC, project/location from ``app.settings``); ``--mode fake`` uses the
deterministic FakeLlm (sanity check of the harness and the dataset).

A case PASSES tool selection when, in the evaluated turn (history prompts run first in the same session):
  * every ``expected_tools`` name was called,
  * at least one tool of every ``expected_any_of`` group was called,
  * no ``forbidden_tools`` name was called,
  * for ``expected_tools == []`` and no any_of: no data tool was needed — any call is allowed only if the answer
    still contains no ungrounded number (disclosure / architecture questions).
Number grounding (BDD-X-S01): ``callbacks.check_text(response, tool_returns, prompt)`` finds no unmatched number.

We use this script instead of ``agents-cli eval`` because that CLI needs a scaffolded agents-cli project and the
Vertex Gen AI evaluation service; the dataset file keeps the agents-cli case shape so it can be reused there.

Usage (from backend/):
  uv run python -m tests.eval.run_eval --mode vertex --concurrency 4
  uv run python -m tests.eval.run_eval --mode fake
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DATASET = HERE / "datasets" / "v04-dataset.json"
RESULTS = HERE / "results"


def score_case(case: dict, reply: dict) -> dict[str, Any]:
    from app.agent.callbacks import check_text, prompt_facts

    called = [c["name"] for c in reply.get("tool_calls", [])]
    cset = set(called)
    exp = set(case.get("expected_tools") or [])
    any_of = [set(g) for g in (case.get("expected_any_of") or [])]
    forb = set(case.get("forbidden_tools") or [])
    missing = sorted(exp - cset)
    any_missing = [sorted(g) for g in any_of if not (g & cset)]
    forbidden_hit = sorted(forb & cset)
    tool_ok = not missing and not any_missing and not forbidden_hit
    prompt = case["prompt"]["parts"][0]["text"]
    trace = reply.get("trace") or {}
    returns = trace.get("tool_returns") or []
    _, bad = check_text(reply.get("response", ""), [prompt_facts(trace.get("ui_state")), *returns], prompt)
    statuses = {c["name"]: c["status"] for c in reply.get("tool_calls", [])}
    refusal_ok = None
    if case.get("expect_refusal"):
        text = reply.get("response", "").lower()
        denied = any(s == "UNAVAILABLE" for s in statuses.values()) or "no_job_justified" in json.dumps(returns).lower()
        words = ("not available", "unavailable", "access", "permission", "not permitted", "can't", "cannot",
                 "no job", "nahi", "allowed", "role", "denied")
        refusal_ok = denied or any(w in text for w in words)
    nc = reply.get("number_check") or {}
    # Grounding is judged on the model's raw text: the callback's pre-mask verdict AND the final text.
    raw_unmatched = list(nc.get("unmatched") or [])
    bad = sorted(set(bad) | set(raw_unmatched))
    return {"tool_ok": tool_ok, "called": called, "missing": missing, "any_of_missing": any_missing,
            "forbidden_called": forbidden_hit, "statuses": statuses, "numbers_ok": not bad, "unmatched": bad,
            "refusal_ok": refusal_ok, "status": reply.get("status"), "engine": reply.get("engine")}


async def run_case(case: dict, mode: str, sem: asyncio.Semaphore) -> dict[str, Any]:
    from app.agent.runner import run_turn_async

    ctx = case.get("context") or {}
    field = ctx.get("field")
    field = None if field in (None, "", "ALL") else field
    kw = {"user_id": "eval", "persona": case["persona"], "field": field, "well_id": ctx.get("well_id"),
          "language": case.get("language") or "english", "screen": ctx.get("screen"), "mode": mode}
    sid = f"eval-{case['eval_case_id']}-{uuid.uuid4().hex[:6]}"
    async with sem:
        t0 = time.perf_counter()
        try:
            for h in case.get("history") or []:
                await run_turn_async(session_id=sid, text=h, **kw)
            reply = await run_turn_async(session_id=sid, text=case["prompt"]["parts"][0]["text"], debug=True, **kw)
            err = None
        except Exception as e:  # noqa: BLE001 - recorded as a failed case
            reply, err = {"response": "", "tool_calls": [], "status": "error"}, f"{type(e).__name__}: {e}"
        dt = time.perf_counter() - t0
    s = score_case(case, reply)
    if err:
        s["tool_ok"] = False
        s["error"] = err
    return {"eval_case_id": case["eval_case_id"], "persona": case["persona"], "language": case.get("language"),
            "tags": case.get("tags", []), "prompt": case["prompt"]["parts"][0]["text"],
            "expected_tools": case.get("expected_tools"), "expected_any_of": case.get("expected_any_of"),
            "expect_refusal": case.get("expect_refusal", False), "latency_s": round(dt, 2),
            "response": reply.get("response", "")[:600], **s}


def summarize(rows: list[dict]) -> dict[str, Any]:
    def acc(sub: list[dict], key: str = "tool_ok") -> dict:
        n = len(sub)
        k = sum(1 for r in sub if r.get(key))
        return {"n": n, "pass": k, "rate": round(k / n, 4) if n else None}

    hold = [r for r in rows if "holdout" in r["tags"]]
    dev = [r for r in rows if "holdout" not in r["tags"]]
    demo = [r for r in rows if r["eval_case_id"].startswith("f18_l")]
    refusals = [r for r in rows if r["expect_refusal"]]
    lat = sorted(r["latency_s"] for r in rows)
    return {"tool_selection": acc(rows), "tool_selection_dev": acc(dev), "tool_selection_holdout": acc(hold),
            "tool_selection_f18_demo": acc(demo), "number_grounding": acc(rows, "numbers_ok"),
            "refusal_behaviour": acc(refusals, "refusal_ok"),
            "degraded_or_error": sum(1 for r in rows if r["status"] != "ok"),
            "latency_p50_s": lat[len(lat) // 2] if lat else None,
            "latency_p95_s": lat[min(len(lat) - 1, int(len(lat) * 0.95))] if lat else None,
            "failed_cases": [r["eval_case_id"] for r in rows if not r["tool_ok"]]}


async def main_async(args: argparse.Namespace) -> dict:
    from app import settings

    data = json.loads(Path(args.dataset).read_text("utf-8"))
    cases = data["eval_cases"]
    if args.only:
        keep = set(args.only.split(","))
        cases = [c for c in cases if c["eval_case_id"] in keep]
    sem = asyncio.Semaphore(args.concurrency)
    rows = await asyncio.gather(*(run_case(c, args.mode, sem) for c in cases))
    out = {"dataset": data.get("name"), "mode": args.mode,
           "model": settings.TEXT_MODEL if args.mode == "vertex" else "fake",
           "location": settings.TEXT_LOCATION, "project": settings.PROJECT_ID, "label": args.label,
           "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
           "summary": summarize(list(rows)), "cases": list(rows)}
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"{args.mode}-{args.label or 'run'}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out["path"] = str(path)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=("vertex", "fake"), default="vertex")
    ap.add_argument("--dataset", default=str(DATASET))
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--only", default="", help="comma-separated eval_case_ids")
    ap.add_argument("--label", default="")
    args = ap.parse_args()
    out = asyncio.run(main_async(args))
    print(json.dumps(out["summary"], indent=2))
    for r in out["cases"]:
        if not r["tool_ok"] or not r["numbers_ok"]:
            print(f"FAIL {r['eval_case_id']}: called={r['called']} missing={r['missing']} any={r['any_of_missing']} "
                  f"forbidden={r['forbidden_called']} unmatched={r['unmatched']} {r.get('error') or ''}")
    print("results:", out["path"])


if __name__ == "__main__":
    main()
