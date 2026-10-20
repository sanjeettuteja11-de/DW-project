"""E12: write CSV exports for the dashboard and the ML notebook to data/export/."""
from __future__ import annotations

import sqlite3

import pandas as pd

from . import features
from .config import Paths

VIEWS = ["v_league_phase_rates", "v_team_phase_profile", "v_venue_profile", "v_player_phase_profile",
         "v_match_phase"]
TABLES = ["dim_date", "dim_team", "dim_venue", "dim_player", "dim_season", "dim_phase", "dim_match",
          "fact_match_summary", "fact_player_season_phase", "dim_player_phase_profile"]


def read_table(conn: sqlite3.Connection, name: str) -> pd.DataFrame:
    """Read a table or view; INTEGER columns containing NULLs stay integers (not 2009.0)."""
    df = pd.read_sql(f"SELECT * FROM {name}", conn)
    types = {r[1]: r[2] for r in conn.execute(f"PRAGMA table_info({name})")}
    for col in df.columns:
        if types.get(col) == "INTEGER" and df[col].dtype.kind == "f":
            df[col] = df[col].astype("Int64")
    return df


def run(paths: Paths, conn: sqlite3.Connection, extra: dict[str, pd.DataFrame]) -> list[str]:
    written = []
    for name in TABLES + VIEWS:
        read_table(conn, name).to_csv(paths.export / f"{name}.csv", index=False)
        written.append(name)
    features.build(conn).to_csv(paths.export / "ml_features.csv", index=False)
    written.append("ml_features")
    for name, df in extra.items():
        df.to_csv(paths.export / f"{name}.csv", index=False)
        written.append(name)
    return written
