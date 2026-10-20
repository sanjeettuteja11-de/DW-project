"""Checks for the generated Power BI project.

    python dashboard/validate_pbip.py <path to a clone of github.com/microsoft/json-schemas>

1. Every JSON file that declares a $schema validates against Microsoft's published schema.
2. Every table, column and measure a visual uses exists in the semantic model.
3. Every measure's DAX only references measures and columns that exist.
4. Visuals sit inside the 1280 x 720 page and do not overlap (thin rules excepted).
5. Interactions and page-navigation buttons point at visuals and pages that exist.
6. Each table's embedded CSV decodes and matches the column list and types in the model.
"""
from __future__ import annotations

import base64
import gzip
import io
import json
import re
import sys
from pathlib import Path

import pandas as pd
from jsonschema import Draft7Validator
from referencing import Registry, Resource

HERE = Path(__file__).resolve().parent
PROJ = HERE / "IPL_Scorebook"
URL = "https://developer.microsoft.com/json-schemas/"
problems: list[str] = []


def schema_check(schemas_root: Path) -> int:
    def retrieve(uri: str) -> Resource:
        path = schemas_root / uri.removeprefix(URL)
        return Resource.from_contents(json.loads(path.read_text(encoding="utf-8")))

    registry = Registry(retrieve=retrieve)
    n = 0
    for f in sorted(PROJ.rglob("*.json")) + sorted(PROJ.rglob("*.pbi*")):
        if f.suffix not in (".json", ".pbip", ".pbir", ".pbism"):
            continue
        doc = json.loads(f.read_text(encoding="utf-8"))
        sch = doc.get("$schema") if isinstance(doc, dict) else None
        if not sch or not sch.startswith(URL):
            continue
        schema = retrieve(sch).contents
        errs = list(Draft7Validator(schema, registry=registry).iter_errors(doc))
        for e in errs[:5]:
            problems.append(f"schema {f.relative_to(PROJ)}: {'/'.join(map(str, e.absolute_path))}: {e.message[:200]}")
        n += 1
        # formatting values are free-form in the visual schema, but every {"expr": ...} inside them
        # is a semantic-query expression, so check those against the expression schema as well
        if "visualContainer" in sch:
            qver = "1.2.0"
            expr_schema = {"$ref": f"{URL}fabric/item/report/definition/semanticQuery/{qver}/schema.json"
                                   "#/definitions/QueryExpressionContainer"}
            ev = Draft7Validator(expr_schema, registry=registry)
            for node in walk(doc.get("visual", {}).get("objects", {})):
                if "expr" in node:
                    for e in list(ev.iter_errors(node["expr"]))[:2]:
                        problems.append(f"expr {f.relative_to(PROJ)}: {e.message[:200]}")
    return n


def model_objects() -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, str], dict[str, dict]]:
    cols: dict[str, set[str]] = {}
    meas: dict[str, set[str]] = {}
    dax: dict[str, str] = {}
    parts: dict[str, dict] = {}
    for f in (PROJ / "IPL_Scorebook.SemanticModel/definition/tables").glob("*.tmdl"):
        text = f.read_text(encoding="utf-8")
        t = f.stem
        cols[t] = set(re.findall(r"^\tcolumn '?([^'\n]+?)'?$", text, re.M))
        meas[t] = set()
        for name, expr in re.findall(r"^\tmeasure '?(.+?)'? = (.+)$", text, re.M):
            name = name.replace("''", "'")
            meas[t].add(name)
            dax[f"{t}[{name}]"] = expr
        b64 = re.search(r'Binary\.FromText\("([^"]+)"', text).group(1)
        types = re.findall(r'\{"([^"]+)", (Int64\.Type|type \w+)\}', text)
        parts[t] = {"b64": b64, "types": types}
    return cols, meas, dax, parts


def walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)


def report_checks(cols, meas) -> int:
    pages_dir = PROJ / "IPL_Scorebook.Report/definition/pages"
    page_names = json.loads((pages_dir / "pages.json").read_text(encoding="utf-8"))["pageOrder"]
    n = 0
    for pn in page_names:
        page = json.loads((pages_dir / pn / "page.json").read_text(encoding="utf-8"))
        vis = {}
        for vf in sorted((pages_dir / pn / "visuals").glob("*/visual.json")):
            v = json.loads(vf.read_text(encoding="utf-8"))
            vis[v["name"]] = v
            n += 1
            for node in walk(v):
                for kind, pool in (("Column", cols), ("Measure", meas)):
                    if kind in node and isinstance(node[kind], dict) and "Property" in node[kind]:
                        src = node[kind]["Expression"].get("SourceRef", {})
                        ent = src.get("Entity")
                        if ent is None:
                            continue  # filter alias (Source); resolved through From
                        if ent not in pool or node[kind]["Property"] not in pool[ent]:
                            problems.append(f"{pn}/{v['name']}: missing {kind.lower()} {ent}.{node[kind]['Property']}")
                if "From" in node and "Where" in node:
                    alias = {e["Name"]: e["Entity"] for e in node["From"]}
                    for sub in walk(node["Where"]):
                        if "Column" in sub and "Source" in sub["Column"]["Expression"].get("SourceRef", {}):
                            ent = alias[sub["Column"]["Expression"]["SourceRef"]["Source"]]
                            if sub["Column"]["Property"] not in cols.get(ent, set()):
                                problems.append(f"{pn}/{v['name']}: filter column {ent}.{sub['Column']['Property']}")
            link = v["visual"].get("visualContainerObjects", {}).get("visualLink")
            if link:
                target = link[0]["properties"]["navigationSection"]["expr"]["Literal"]["Value"].strip("'")
                if target not in page_names:
                    problems.append(f"{pn}/{v['name']}: navigation to unknown page {target}")
        for it in page.get("visualInteractions", []):
            for k in ("source", "target"):
                if it[k] not in vis:
                    problems.append(f"{pn}: interaction {k} {it[k]} is not a visual")
        boxes = []
        for name, v in vis.items():
            p = v["position"]
            if p["x"] < 0 or p["y"] < 0 or p["x"] + p["width"] > 1280 or p["y"] + p["height"] > 720:
                problems.append(f"{pn}/{name}: outside the page {p}")
            if p["height"] > 3 and p["width"] > 3:
                boxes.append((name, p["x"], p["y"], p["x"] + p["width"], p["y"] + p["height"]))
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                if a[1] < b[3] and b[1] < a[3] and a[2] < b[4] and b[2] < a[4]:
                    problems.append(f"{pn}: {a[0]} overlaps {b[0]}")
    return n


def dax_checks(cols, meas, dax) -> None:
    all_measures = {m for ms in meas.values() for m in ms}
    for key, expr in dax.items():
        for t, c in re.findall(r"(\w+)\[([^\]]+)\]", expr):
            if t not in cols or (c not in cols[t] and c not in meas.get(t, set())):
                problems.append(f"DAX {key}: unknown {t}[{c}]")
        for m in re.findall(r"(?<![\w\]])\[([^\]]+)\]", expr):
            if m not in all_measures:
                problems.append(f"DAX {key}: unknown measure [{m}]")


def data_checks(parts) -> int:
    rows = 0
    for t, p in parts.items():
        raw = gzip.decompress(base64.b64decode(p["b64"]))
        df = pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=False)
        if list(df.columns) != [c for c, _ in p["types"]]:
            problems.append(f"data {t}: CSV header differs from the typed column list")
        for c, ty in p["types"]:
            vals = df[c][df[c] != ""]
            if ty == "Int64.Type" and not vals.str.fullmatch(r"-?\d+").all():
                problems.append(f"data {t}.{c}: non-integer text in an Int64 column")
            if ty == "type number" and not vals.str.fullmatch(r"-?\d+(\.\d+)?([eE]-?\d+)?").all():
                problems.append(f"data {t}.{c}: non-numeric text in a number column")
            if ty == "type date" and not vals.str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
                problems.append(f"data {t}.{c}: bad date text")
        rows += len(df)
    return rows


def main() -> None:
    schemas_root = Path(sys.argv[1])
    n_schema = schema_check(schemas_root)
    cols, meas, dax, parts = model_objects()
    n_vis = report_checks(cols, meas)
    dax_checks(cols, meas, dax)
    n_rows = data_checks(parts)
    print(f"schema-checked files: {n_schema}; visuals: {n_vis}; measures: {len(dax)}; embedded rows: {n_rows:,}")
    if problems:
        print(f"{len(problems)} problem(s):")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("no problems found")


if __name__ == "__main__":
    main()
