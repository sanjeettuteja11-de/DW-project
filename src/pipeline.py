"""Run the full ETL (E1-E12).

    python -m src.pipeline --source-url <kaggle url> --dataset-version <version>

Exits with code 1 if any validation gate fails; exports are written only
when every gate passes.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import clean, export, extract, profiling, scd2, transform, validate
from .config import EXPECTED_FRANCHISES, PROJECT_ROOT, QUALIFY_BALLS, SENSITIVITY_THRESHOLDS, Paths
from .load import connect, create_schema, load_clean, load_warehouse


def _say(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def run(
    paths: Paths = Paths(),
    source_url: str = "",
    dataset_version: str = "",
    download_date: str = "",
    threshold: int = QUALIFY_BALLS,
    expected_franchises: int | None = EXPECTED_FRANCHISES,
    sensitivity_thresholds=SENSITIVITY_THRESHOLDS,
) -> int:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    paths.ensure()
    if paths.db.exists():
        paths.db.unlink()
    conn = connect(paths.db)
    report_path = paths.logs / "validation_report.csv"
    results: list[validate.GateResult] = []
    ctx = {"logs": paths.logs, "expected_franchises": expected_franchises}

    def gate(*names) -> bool:
        new = validate.run_gates(conn, names, ctx)
        results.extend(new)
        for r in new:
            _say(f"  {r.gate} {r.status}: {r.detail}")
        validate.write_report(results, report_path, run_id)
        return all(r.passed for r in new)

    try:
        _say("E1 register raw files")
        frames, log = extract.register(paths, run_id, source_url, dataset_version, download_date)
        ctx["raw_counts"] = dict(zip(extract.RAW_FILES, log["rows"]))
        _say("E2 stage")
        extract.stage(conn, frames)
        staged = extract.read_staging(conn)
        _say("E3 profile")
        findings = profiling.run(paths, staged)
        _say(f"  {int((findings.status == 'CONFIRMED').sum())}/{len(findings)} expected issues confirmed")

        _say("E4-E6 canonicalise, normalise, flag")
        cleaned = clean.run(paths, staged)
        load_clean(conn, cleaned)
        _say(f"  {len(cleaned.log)} cleaning rules applied; {len(cleaned.fuzzy_candidates)} player pairs "
             "for manual review (logs/player_fuzzy_candidates.csv)")
        if not gate("G6"):
            _say("STOP: unmapped entities; add them to mappings/*.csv (see logs/unmapped_entities.csv)")
            return 1

        _say("E7-E9 dimensions and facts")
        tables = transform.build(cleaned, threshold)
        season_years = tables["dim_season"].set_index("season_key")["year"]
        _say("E10 SCD2 player phase profile")
        primaries = scd2.season_primaries(tables["fact_player_season_phase"], season_years)
        profile = scd2.build_profile(primaries, threshold)
        tables["dim_player_phase_profile"] = scd2.describe(profile, tables["dim_player"], tables["dim_phase"])
        tables["fact_player_season_phase"] = scd2.link_fact(tables["fact_player_season_phase"], profile,
                                                            season_years)
        create_schema(conn)
        counts = load_warehouse(conn, tables)
        for name, n in counts.items():
            _say(f"  {name}: {n} rows")

        _say("E11 validate")
        ok = gate("G1", "G2", "G3", "G4", "G5", "G7", "G8", "G9")
        if not ok:
            _say("STOP: validation failed; see logs/validation_report.csv")
            return 1

        _say("E12 export")
        drift = scd2.drift_table(tables["dim_player_phase_profile"], tables["fact_player_season_phase"],
                                 season_years, tables["dim_player"], tables["dim_phase"])
        sens = scd2.sensitivity(tables["fact_delivery"], season_years, sensitivity_thresholds)
        export.run(paths, conn, {"drift_table": drift, "drift_sensitivity": sens})
        _say(f"  {len(drift)} phase changes in the drift table; exports in {paths.export}")
        _say("DONE: all gates passed")
        return 0
    finally:
        conn.close()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", type=Path, default=PROJECT_ROOT, help="project root (data/, db/, logs/)")
    p.add_argument("--source-url", default="", help="dataset URL, recorded in the extraction log")
    p.add_argument("--dataset-version", default="", help="dataset version, recorded in the extraction log")
    p.add_argument("--download-date", default="", help="YYYY-MM-DD; defaults to the file modification date")
    p.add_argument("--threshold", type=int, default=QUALIFY_BALLS, help="qualification threshold in balls")
    p.add_argument("--expected-franchises", type=int, default=EXPECTED_FRANCHISES)
    a = p.parse_args(argv)
    if not all((a.root / "data" / "raw" / f).exists() for f in extract.RAW_FILES.values()):
        print(f"Put matches.csv and deliveries.csv in {a.root / 'data' / 'raw'} first (see README).")
        return 2
    return run(Paths(root=a.root), a.source_url, a.dataset_version, a.download_date, a.threshold,
               a.expected_franchises)


if __name__ == "__main__":
    sys.exit(main())
