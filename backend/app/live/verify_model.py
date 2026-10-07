"""python -m app.live.verify_model — Live / text model verification (SDD §11.7, D-12: list, never guess).

1. ``models.list()`` on Vertex (ADC) in each location; print names containing ``live`` / ``native-audio``.
2. Smoke-test the configured Live model: open a session, send "Say OK.", assert audio + turn_complete.
3. Ping the text model (generate_content) in us-central1 and global.
Exit code 0 only if the configured Live model connects and returns audio.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from app.live.session import live_settings

TEXT_MODEL = os.getenv("WELLPULSE_TEXT_MODEL", "gemini-3.8-flash")


def list_models(project: str, location: str) -> list[str]:
    from google import genai

    c = genai.Client(vertexai=True, project=project, location=location)
    return [m.name for m in c.models.list(config={"page_size": 300})]


async def live_smoke(project: str, location: str, model: str) -> tuple[bool, str]:
    from google import genai
    from google.genai import types

    c = genai.Client(vertexai=True, project=project, location=location)
    cfg = types.LiveConnectConfig(response_modalities=[types.Modality.AUDIO],
                                  output_audio_transcription=types.AudioTranscriptionConfig())
    t0 = time.perf_counter()
    try:
        async with c.aio.live.connect(model=model, config=cfg) as s:
            t_conn = time.perf_counter() - t0
            t1 = time.perf_counter()
            await s.send_client_content(
                turns=[types.Content(role="user", parts=[types.Part.from_text(text="Say OK.")])], turn_complete=True)
            nbytes, first = 0, None

            async def rx() -> None:
                nonlocal nbytes, first
                async for r in s.receive():
                    sc = r.server_content
                    if sc and sc.model_turn:
                        for p in sc.model_turn.parts or []:
                            if p.inline_data and p.inline_data.data:
                                first = first if first is not None else time.perf_counter() - t1
                                nbytes += len(p.inline_data.data)
                    if sc and sc.turn_complete:
                        return

            await asyncio.wait_for(rx(), 10)
            ok = nbytes > 0
            return ok, f"connect={t_conn:.2f}s first_audio={first if first is None else round(first, 2)}s bytes={nbytes}"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:200]}"


def text_ping(project: str, location: str, model: str) -> str:
    from google import genai

    try:
        c = genai.Client(vertexai=True, project=project, location=location)
        r = c.models.generate_content(model=model, contents="Reply with the single word OK.")
        return f"OK ({(r.text or '').strip()!r})"
    except Exception as e:
        return f"FAIL {type(e).__name__}: {str(e)[:160]}"


def main() -> int:
    s = live_settings()
    print(f"project={s['project']} configured live model={s['model']} location={s['location']}")
    for loc in dict.fromkeys([s["location"], "us-central1", "global"]):
        try:
            names = list_models(s["project"], loc)
            live = [n for n in names if "live" in n.lower() or "native-audio" in n.lower()]
            print(f"[{loc}] LIVE: {live}")
            print(f"[{loc}] TEXT {TEXT_MODEL} listed: {any(n.endswith('/' + TEXT_MODEL) for n in names)}")
        except Exception as e:
            print(f"[{loc}] list failed: {type(e).__name__}: {e}")
    ok, info = asyncio.run(live_smoke(s["project"], s["location"], s["model"]))
    print(f"LIVE SMOKE {s['model']}@{s['location']}: {'OK' if ok else 'FAIL'} {info}")
    for loc in ("us-central1", "global"):
        print(f"TEXT PING {TEXT_MODEL}@{loc}: {text_ping(s['project'], loc, TEXT_MODEL)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
