"""Fact-slot validator (the gate that lets Flash write templates).

    uv run python -m app.analytics.docs_pdf.validate                # whole rendered corpus + static checks
    uv run python -m app.analytics.docs_pdf.validate --type D06     # Flash worker gate for one type

Checks
1. Static: every string literal in the type's template module (and, for D11 /
   heroes, every YAML string) is digit-free outside ``{slots}`` and contains no
   spelled-out number words. Identifier-like strings (slot / column keys) are skipped.
2. Compose: the template builds for a stratified sample (``--type``) or every spec
   (``--full``) without FactSlotError (unknown slot, literal digit, bad column).
3. PDF: for each rendered document (pypdf extraction) every ``facts.json`` value and
   table cell appears in the text, and after removing them (and framework layout
   tokens "Page N of M", "Step N") no digit remains. Scanned documents
   (``has_text_layer=false``) must have no extractable text and must carry
   ``scanned_text`` for the index.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
import tempfile
import time
from collections import Counter, defaultdict
from multiprocessing import get_context
from pathlib import Path

import yaml

from app.analytics.docs_pdf import ir
from app.analytics.docs_pdf.ir import DIGIT_RE
from app.analytics.docs_pdf.facts import DOC_TYPES, FIELDS, TYPE_DIRS, iter_specs, norm_type, stable_hash
from app.analytics.docs_pdf.paths import docs_dir
from app.analytics.docs_pdf.templates import TEMPLATE_MODULES

TEMPLATES_DIR = Path(__file__).parent / "templates"
SOP_DIR = TEMPLATES_DIR / "sop"
HERO_FILE = TEMPLATES_DIR / "hero_text.yaml"
IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
LAYOUT_RE = re.compile(r"Page\s?\d+\s?of\s?\d+|Step\s?\d+\.")
WS_RE = re.compile(r"\s+")


# --------------------------------------------------------------------------- static checks
def _docstring_nodes(tree: ast.AST) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant):
                ids.add(id(body[0].value))
    return ids


def static_check_module(path: Path) -> list[str]:
    problems = []
    src = path.read_text()
    tree = ast.parse(src)
    skip = _docstring_nodes(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
            s = node.value
            if IDENT_RE.match(s):
                continue  # slot / table / column key
            for p in ir.literal_violations(s):
                problems.append(f"{path.name}:{node.lineno}: {p}")
        if isinstance(node, ast.JoinedStr):
            problems.append(f"{path.name}:{node.lineno}: f-strings are not allowed in templates (use {{slot}} literals)")
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") in ("format", "__mod__"):
            problems.append(f"{path.name}:{node.lineno}: str.format() is not allowed in templates")
    for bad in ("import random", "datetime", "numpy", "pandas"):
        if bad in src:
            problems.append(f"{path.name}: templates may not use {bad!r} (numbers come from facts.py only)")
    return problems


def _yaml_strings(obj, where: str):
    if isinstance(obj, str):
        yield where, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _yaml_strings(v, f"{where}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _yaml_strings(v, f"{where}[{i}]")
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        yield where, str(obj)


# keys in YAML whose values are identifiers / references, not printed prose
YAML_ID_KEYS = {"doc_id", "well_id", "intervention_class", "doc_type", "tone", "job_codes", "sop_id"}


def static_check_yaml(path: Path) -> list[str]:
    problems = []
    data = yaml.safe_load(path.read_text())
    for where, s in _yaml_strings(data, path.name):
        last = re.split(r"[.\[]", where)[-1].rstrip("]")
        parent_key = where.rsplit(".", 1)[-1].split("[")[0]
        if parent_key in YAML_ID_KEYS or last in YAML_ID_KEYS:
            continue
        for p in ir.literal_violations(s):
            problems.append(f"{where}: {p}")
    return problems


def static_check(doc_type: str) -> list[str]:
    mod = TEMPLATES_DIR / f"{TEMPLATE_MODULES[doc_type]}.py"
    problems = []
    if not mod.exists():
        problems.append(f"{doc_type}: template {mod.name} not written yet (default template in use)")
    else:
        problems += static_check_module(mod)
    if doc_type == "D11":
        if not SOP_DIR.exists():
            problems.append("D11: templates/sop/ missing")
        else:
            for y in sorted(SOP_DIR.glob("*.yaml")):
                problems += static_check_yaml(y)
    return problems


def sop_problems() -> list[str]:
    from app.analytics.docs_pdf.facts import IC_SOP_CLASSES, asset_data
    from app.analytics.docs_pdf.sop import SOP_DIR as SD, load_sop, schema_problems

    load_sop.cache_clear()
    jc = asset_data().job_catalogue
    probs = []
    for ic in IC_SOP_CLASSES:
        codes = list(jc[jc.intervention_class == ic]["job_code"])
        data = load_sop(ic)
        probs += schema_problems(ic, data, codes)
        if data is not None:
            sid = jc[jc.intervention_class == ic]["sop_doc_id"].dropna()
            if len(sid) and data.get("sop_id") != sid.iloc[0]:
                probs.append(f"{ic}: sop_id {data.get('sop_id')} != job_catalogue.sop_doc_id {sid.iloc[0]}")
            probs += static_check_yaml(SD / f"{ic}.yaml")
    return probs


def hero_doc_ids() -> list[str]:
    if not HERO_FILE.exists():
        return []
    data = yaml.safe_load(HERO_FILE.read_text()) or {}
    return [n["doc_id"] for n in data.get("narratives", [])]


# --------------------------------------------------------------------------- PDF checks
def norm(s: str) -> str:
    return WS_RE.sub("", s or "")


def value_regex(v: str) -> re.Pattern:
    """Match a fact value as a whole number token, tolerating line breaks inside it."""
    body = r"\s?".join(re.escape(c) for c in v if not c.isspace())
    return re.compile(r"(?<![0-9])(?<![0-9][.,])" + body + r"(?![.,]?[0-9])")


def extract_text(pdf: Path) -> list[str]:
    from pypdf import PdfReader

    r = PdfReader(str(pdf))
    return [p.extract_text() or "" for p in r.pages]


def check_record(rec: dict, pdf: Path) -> list[str]:
    """Validate one rendered document against its facts.json record."""
    problems = []
    if not pdf.exists():
        return [f"{rec['doc_id']}: PDF missing"]
    try:
        pages = extract_text(pdf)
    except Exception as e:  # noqa: BLE001
        return [f"{rec['doc_id']}: unreadable PDF ({e})"]
    text = norm("".join(pages))
    if not rec.get("has_text_layer", True):
        if len(text) > 40:
            problems.append(f"{rec['doc_id']}: flagged scanned but {len(text)} chars extractable")
        if not rec.get("scanned_text"):
            problems.append(f"{rec['doc_id']}: scanned document lacks scanned_text for the index")
            return problems
        stext = norm("".join(rec["scanned_text"]))
        vals = {norm(str(v)) for v in rec.get("facts", {}).values() if norm(str(v))}
        miss = [v for v in vals if v not in stext]
        if miss:
            problems.append(f"{rec['doc_id']}: scanned_text lacks fact value(s) {miss[:3]}")
        return problems
    values = [str(v) for v in rec.get("facts", {}).values()]
    for t in rec.get("tables", {}).values():
        for row in t.get("rows", []):
            values.extend(str(c) for c in row)
    uniq = sorted({v for v in values if v.strip()}, key=lambda v: len(norm(v)), reverse=True)
    missing = [v for v in uniq if norm(v) not in text]
    if missing:
        problems.append(f"{rec['doc_id']}: {len(missing)} fact value(s) not found in PDF text, e.g. {missing[:3]}")
    residue = LAYOUT_RE.sub(" ", WS_RE.sub(" ", "\n".join(pages)))
    for v in uniq:
        if DIGIT_RE.search(v):
            residue = value_regex(v).sub(" ", residue)
    stray = re.findall(r".{0,25}\d.{0,25}", residue)
    if stray:
        problems.append(f"{rec['doc_id']}: {len(stray)} stray digit context(s) outside fact slots, e.g. {stray[:2]}")
    return problems


def _check_path(fp: str) -> tuple[str, str, list[str], bool]:
    p = Path(fp)
    rec = json.loads(p.read_text())
    pdf = p.with_name(p.name.replace(".facts.json", ".pdf"))
    return rec["doc_type"], rec["doc_id"], check_record(rec, pdf), rec.get("has_text_layer", True)


def facts_files(root: Path, doc_type: str | None = None) -> list[Path]:
    out = []
    for fk in list(FIELDS.values()) + ["asset"]:
        for t in ([doc_type] if doc_type else DOC_TYPES):
            d = root / fk / TYPE_DIRS[t]
            if d.exists():
                out.extend(sorted(d.glob("*.facts.json")))
    return out


def check_corpus(root: Path, doc_type: str | None, workers: int) -> tuple[Counter, Counter, list[str]]:
    files = [str(p) for p in facts_files(root, doc_type)]
    ok, bad, problems = Counter(), Counter(), []
    if not files:
        return ok, bad, [f"no rendered documents under {root}" + (f" for {doc_type}" if doc_type else "")]
    pool = get_context("fork").Pool(workers) if workers > 1 else None
    it = pool.imap_unordered(_check_path, files, chunksize=32) if pool else map(_check_path, files)
    for t, _doc, probs, _txt in it:
        if probs:
            bad[t] += 1
            problems.extend(probs)
        else:
            ok[t] += 1
    if pool:
        pool.close()
        pool.join()
    return ok, bad, problems


# --------------------------------------------------------------------------- sampling + compose
def sample_specs(doc_type: str, per_group: int = 1, extra: int = 12) -> list:
    specs = list(iter_specs(types=[doc_type]))
    groups: dict = defaultdict(list)
    for s in specs:
        key = (s.field, s.meta.get("intervention_class"), s.meta.get("outcome"), s.raw.get("phase_code"),
               s.meta.get("variant"), s.raw.get("isolation_assessment"))
        groups[key].append(s)
    chosen = {}
    for key, ss in groups.items():
        for s in sorted(ss, key=lambda x: stable_hash(x.doc_id))[:per_group]:
            chosen[s.doc_id] = s
    for s in sorted(specs, key=lambda x: stable_hash("x" + x.doc_id))[:extra]:
        chosen[s.doc_id] = s
    for s in specs:  # hero documents always included
        if s.well_id in ("GK-129", "LKW-047", "LKW-112", "LKM-090") and (len(chosen) < 400):
            chosen[s.doc_id] = s
    return list(chosen.values()), specs


def hero_gate(workers: int, t0: float) -> int:
    """Gate for hero narratives: YAML literal check + render every targeted document."""
    from app.analytics.docs_pdf.render import hero_narratives, render_spec

    failed = False
    if not HERO_FILE.exists():
        print("[validate HERO] templates/hero_text.yaml missing")
        return 1
    probs = static_check_yaml(HERO_FILE)
    print(f"[validate HERO] static literal check: {'PASS' if not probs else 'FAIL'} ({len(probs)})")
    for p in probs[:40]:
        print("   ", p)
    failed |= bool(probs)
    hero_narratives.cache_clear()
    ids = set(hero_doc_ids())
    specs = [s for s in iter_specs(wells=["GK-129", "LKW-047", "LKW-112", "LKM-090"]) if s.doc_id in ids]
    unknown = ids - {s.doc_id for s in specs}
    if unknown:
        print(f"[validate HERO] FAIL: doc_id(s) not in corpus: {sorted(unknown)}")
        failed = True
    with tempfile.TemporaryDirectory(prefix="docs_hero_") as tmp:
        root = Path(tmp)
        errs = []
        for s in specs:
            try:
                render_spec(s, root)
            except Exception as e:  # noqa: BLE001
                errs.append(f"{s.doc_id}: {type(e).__name__}: {e}")
        print(f"[validate HERO] render {len(specs)} hero documents: {'PASS' if not errs else 'FAIL'}")
        for e in errs:
            print("   ", e)
        failed |= bool(errs)
        bad = 0
        for fp in facts_files(root):
            probs = _check_path(str(fp))[2]
            if probs:
                bad += 1
                for p in probs:
                    print("   ", p)
        failed |= bool(bad)
        print(f"[validate HERO] PDF fact check: {len(specs) - bad} pass, {bad} fail")
    print(f"[validate HERO] {'PASS' if not failed else 'FAIL'} in {time.time() - t0:.1f}s")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--type", default="", help="DNN: Flash gate for one type (static + compose + render sample + PDF checks)")
    ap.add_argument("--full", action="store_true", help="with --type: compose every spec, not a sample")
    ap.add_argument("--root", default="", help="rendered corpus root (default data/docs_pdf)")
    ap.add_argument("--workers", type=int, default=min(32, os.cpu_count() or 4))
    a = ap.parse_args(argv)
    t0 = time.time()
    failed = False
    if a.type.upper() == "HERO":
        return hero_gate(a.workers, t0)
    if a.type.upper() == "SOP":
        probs = sop_problems()
        print(f"[validate SOP] schema + literal check of IC-01..IC-14: {'PASS' if not probs else 'FAIL'} ({len(probs)})")
        for p in probs[:60]:
            print("   ", p)
        rc = main(["--type", "D11", "--workers", str(a.workers)])
        return 1 if (probs or rc) else 0
    if a.type:
        t = norm_type(a.type)
        probs = static_check(t)
        print(f"[validate {t}] static literal check: {'PASS' if not probs else 'FAIL'} ({len(probs)} problem(s))")
        for p in probs[:40]:
            print("   ", p)
        failed |= bool(probs)
        sample, allspecs = sample_specs(t)
        if a.full:
            sample = allspecs
        from app.analytics.docs_pdf.render import render_spec

        with tempfile.TemporaryDirectory(prefix=f"docs_{t}_") as tmp:
            root = Path(tmp)
            errs = []
            for s in sample:
                try:
                    render_spec(s, root)
                except Exception as e:  # noqa: BLE001
                    errs.append(f"{s.doc_id}: {type(e).__name__}: {e}")
            print(f"[validate {t}] compose+render {len(sample)} of {len(allspecs)} docs: "
                  f"{'PASS' if not errs else 'FAIL'} ({len(errs)} error(s))")
            for e in errs[:20]:
                print("   ", e)
            failed |= bool(errs)
            ok, bad, problems = check_corpus(root, t, a.workers)
            print(f"[validate {t}] PDF fact check: {sum(ok.values())} pass, {sum(bad.values())} fail")
            for p in problems[:20]:
                print("   ", p)
            failed |= bool(problems)
            pages = Counter()
            for fp in facts_files(root, t):
                pages[json.loads(fp.read_text())["pages"]] += 1
            print(f"[validate {t}] page-count distribution: {dict(sorted(pages.items()))}")
        print(f"[validate {t}] {'PASS' if not failed else 'FAIL'} in {time.time() - t0:.1f}s")
        return 1 if failed else 0

    root = Path(a.root) if a.root else docs_dir()
    if HERO_FILE.exists() and static_check_yaml(HERO_FILE):
        failed = True
        print("[validate] static hero_text.yaml: FAIL", static_check_yaml(HERO_FILE)[:5])
    for t in DOC_TYPES:
        probs = static_check(t)
        if probs:
            failed = True
            print(f"[validate] static {t}: FAIL ({len(probs)})")
            for p in probs[:10]:
                print("   ", p)
    sp = sop_problems()
    if sp:
        failed = True
        print(f"[validate] SOP library: FAIL ({len(sp)})", sp[:5])
    ok, bad, problems = check_corpus(root, None, a.workers)
    total = sum(ok.values()) + sum(bad.values())
    for t in DOC_TYPES:
        print(f"  {t} {DOC_TYPES[t]:<46} pass={ok[t]:>6} fail={bad[t]:>4}")
    rate = 100.0 * sum(ok.values()) / total if total else 0.0
    print(f"[validate] fact validation {sum(ok.values())}/{total} = {rate:.2f}% ; stray-digit/missing problems: {len(problems)}")
    for p in problems[:20]:
        print("   ", p)
    failed |= bool(problems) or total == 0
    print(f"[validate] {'PASS' if not failed else 'FAIL'} in {time.time() - t0:.1f}s")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
