"""Load the clean layer and the star schema into SQLite."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from .clean import CleanResult
from .config import SQL_DIR

# Insertion order respects foreign keys.
WAREHOUSE_ORDER = ["dim_date", "dim_season", "dim_phase", "dim_team", "dim_venue", "dim_player", "dim_match",
                   "dim_player_phase_profile", "fact_delivery", "fact_match_summary",
                   "fact_player_season_phase"]


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def load_clean(conn: sqlite3.Connection, clean: CleanResult) -> None:
    """Layer 3: clean tables, mapping tables and the unmapped-entity audit."""
    tables = {
        "clean_matches": clean.matches, "clean_deliveries": clean.deliveries,
        "map_team": clean.team_map, "map_venue": clean.venue_map, "map_player": clean.player_map,
        "audit_unmapped": clean.unmapped, "cleaning_log": clean.log,
    }
    for name, df in tables.items():
        df.to_sql(name, conn, if_exists="replace", index=False)
    conn.commit()


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript((SQL_DIR / "ddl.sql").read_text())
    conn.executescript((SQL_DIR / "views.sql").read_text())


def insert(conn: sqlite3.Connection, table: str, df: pd.DataFrame) -> int:
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    missing = set(cols) - set(df.columns)
    if missing:
        raise ValueError(f"{table}: frame is missing columns {sorted(missing)}")
    df[cols].to_sql(table, conn, if_exists="append", index=False, chunksize=50_000)
    return len(df)


def load_warehouse(conn: sqlite3.Connection, tables: dict[str, pd.DataFrame]) -> dict[str, int]:
    counts = {}
    for name in WAREHOUSE_ORDER:
        if name in tables:
            counts[name] = insert(conn, name, tables[name])
    conn.commit()
    return counts
