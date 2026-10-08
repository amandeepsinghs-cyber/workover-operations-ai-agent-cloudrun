"""v0.6 ED-11 (D-40): the browser parser routes plain screen commands locally and questions to the agent.

Runs frontend/src/agent/uiCommands.ts through esbuild + node (skipped when node / esbuild are unavailable).
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
FRONT = ROOT / "frontend"
ESBUILD = FRONT / "node_modules" / ".bin" / "esbuild"

# (text, current well, expected labels or None = goes to the agent)
CASES: list[tuple[str, str | None, list[str] | None]] = [
    ("full screen", None, ["Full screen on"]),
    ("exit full screen", None, ["Full screen off"]),
    ("satellite dikhao", None, ["Satellite map"]),
    ("switch to SCADA map", None, ["SCADA map"]),
    ("India view", None, ["India view"]),
    ("go to Geleki", None, ["Geleki field"]),
    ("show me Lakwa on the map", None, ["Lakwa field"]),
    ("open GK-129 wellbore", None, ["GK-129 · wellbore"]),
    ("GK-129 on the map", None, ["GK-129 on map"]),
    ("show the completion diagram", "GK-129", ["GK-129 · wellbore"]),
    ("field history", None, ["Field history"]),
    ("health and priority", None, ["Health & priority"]),
    ("close panel", None, ["Panel closed"]),
    ("hide flowlines", None, ["Flowlines off"]),
    ("Hindi mein baat karo", None, ["Language: Hindi"]),
    ("full screen and satellite", None, ["Full screen on", "Satellite map"]),
    ("go to Geleki, then open GK-129 wellbore", None, ["Geleki field", "GK-129 · wellbore"]),
    ("पूरी स्क्रीन", None, ["Full screen on"]),
    ("show GGS-03", None, ["GGS-03 wells"]),
    ("print the report", "GK-129", ["Field report printing"]),
    ("only show non producing wells", None, ["Showing: Not producing"]),
    ("sirf band wells dikhao", None, ["Showing: Not producing"]),
    ("केवल बंद कुएँ दिखाओ", None, ["Showing: Not producing"]),
    ("show only healthy wells", None, ["Showing: Healthy"]),
    ("needs attention wells", None, ["Showing: Needs attention"]),
    ("show all wells", None, ["Showing all wells"]),
    ("clear filter", None, ["Showing all wells"]),
    ("show GGS three", None, ["GGS-03 wells"]),
    ("open GK one two nine wellbore", None, ["GK-129 · wellbore"]),
    ("Geleki and only non producing wells", None, ["Geleki field", "Showing: Not producing"]),
    ("which wells are not producing", None, None),
    ("why are Lakwa wells not producing", None, None),
    ("what is wrong with GK-129", None, None),
    ("why is Lakwa declining", None, None),
    ("tell me about GK-129", None, None),
    ("GK-129 water cut kitna hai", None, None),
    ("compare decline with nearby wells", "GK-129", None),
    ("show me the worst well in Lakwa", None, None),
]

HARNESS = """
import { parseUiCommands } from '%s';
const cases = JSON.parse(process.argv[2]);
const out = cases.map(([t, w]) => { const r = parseUiCommands(t, w); return r ? r.map((c) => c.label) : null; });
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(not (shutil.which("node") and ESBUILD.exists()), reason="node / esbuild not available")
def test_browser_parser_routes_commands_and_questions(tmp_path: Path):
    entry = tmp_path / "harness.ts"
    entry.write_text(HARNESS % (FRONT / "src" / "agent" / "uiCommands.ts").as_posix(), encoding="utf-8")
    bundle = tmp_path / "harness.cjs"
    subprocess.run([str(ESBUILD), str(entry), "--bundle", "--platform=node", f"--outfile={bundle}",
                    "--log-level=error"], check=True, cwd=FRONT, timeout=60)
    payload = json.dumps([[t, w] for t, w, _ in CASES])
    res = subprocess.run(["node", str(bundle), payload], check=True, capture_output=True, text=True, timeout=30)
    got = json.loads(res.stdout)
    for (text, _w, expected), labels in zip(CASES, got, strict=True):
        assert labels == expected, f"{text!r}: expected {expected}, got {labels}"
