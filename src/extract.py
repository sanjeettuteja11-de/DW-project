"""E1 (download and register) and E2 (stage).

The raw files are never modified: they are read as text, checksummed and
copied unchanged into the staging tables.
"""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import Paths

RAW_FILES = {"matches": "matches.csv", "deliveries": "deliveries.csv"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_raw(path: Path) -> pd.DataFrame:
    """Read a raw CSV with every value as text and no NA inference."""
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_filter=False)


def raw_paths(paths: Paths) -> dict[str, Path]:
    out = {name: paths.raw / fname for name, fname in RAW_FILES.items()}
    missing = [str(p) for p in out.values() if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "Raw files not found: " + ", ".join(missing)
            + ". Download matches.csv and deliveries.csv into data/raw/ (see README)."
        )
    return out


def register(
    paths: Paths,
    run_id: str,
    source_url: str = "",
    dataset_version: str = "",
    download_date: str = "",
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """E1: checksum and profile the raw files; append to logs/extraction_log.csv."""
    frames, rows = {}, []
    log_path = paths.logs / "extraction_log.csv"
    previous = pd.read_csv(log_path, dtype=str) if log_path.exists() else pd.DataFrame()
    for name, path in raw_paths(paths).items():
        df = read_raw(path)
        frames[name] = df
        digest = sha256(path)
        prev = previous[previous["file"] == path.name] if len(previous) else previous
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        rows.append({
            "run_id": run_id,
            "file": path.name,
            "source_url": source_url,
            "dataset_version": dataset_version,
            "download_date": download_date or mtime.date().isoformat(),
            "sha256": digest,
            "checksum_changed": bool(len(prev)) and prev["sha256"].iloc[-1] != digest,
            "bytes": path.stat().st_size,
            "rows": len(df),
            "columns": len(df.columns),
            "column_names": "|".join(df.columns),
        })
    log = pd.DataFrame(rows)
    log.to_csv(log_path, mode="a", header=not log_path.exists(), index=False)
    return frames, log


def stage(conn: sqlite3.Connection, frames: dict[str, pd.DataFrame]) -> dict[str, int]:
    """E2: load raw frames unchanged into stg_* tables (all TEXT, plus source_row)."""
    counts = {}
    for name, df in frames.items():
        table = f"stg_{name}"
        staged = df.copy()
        staged.insert(0, "source_row", range(1, len(df) + 1))
        staged.to_sql(table, conn, if_exists="replace", index=False)
        (n,) = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        if n != len(df):
            raise RuntimeError(f"{table}: staged {n} rows but raw file has {len(df)}")
        counts[table] = n
    conn.commit()
    return counts


def read_staging(conn: sqlite3.Connection) -> dict[str, pd.DataFrame]:
    out = {}
    for name in RAW_FILES:
        df = pd.read_sql(f"SELECT * FROM stg_{name} ORDER BY source_row", conn)
        out[name] = df
    return out
