"""ML feature table (section 11) built from the warehouse with leakage guardrails.

- Only information available at the prediction point is used.
- "Previous season" and "earlier matches" features use strictly earlier data.
- result_margin, player_of_match, winner and target_runs are never features.
"""
from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

PP_FEATURES = ["pp_runs", "pp_wickets", "pp_run_rate", "pp_boundaries", "pp_dot_pct"]
MODEL_A = [f"inn1_{c}" for c in PP_FEATURES] + [
    "toss_decision_bat", "toss_winner_bat_first", "venue_avg_first_innings_prior",
    "bat_first_prev_season_win_pct", "chase_prev_season_win_pct"]
MODEL_B = MODEL_A + [f"inn2_{c}" for c in PP_FEATURES]
TARGET = "bat_first_won"


def build(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql("""
        SELECT s.*, m.source_match_id, m.match_date, se.year AS season,
               tb.franchise_id AS bat_first_franchise, tc.franchise_id AS chase_franchise
        FROM fact_match_summary s
        JOIN dim_match m USING (match_key)
        JOIN dim_season se ON se.season_key = s.season_key
        JOIN dim_team tb ON tb.team_key = s.bat_first_team_key
        JOIN dim_team tc ON tc.team_key = s.chase_team_key
        ORDER BY m.match_date, m.source_match_id""", conn)

    # Franchise win percentage per season (all matches with a result); used for the next season.
    teams = pd.concat([
        df[["season", "bat_first_franchise", "bat_first_won"]].set_axis(["season", "franchise", "won"], axis=1),
        df[["season", "chase_franchise", "bat_first_won"]].set_axis(["season", "franchise", "won"], axis=1)
        .assign(won=lambda x: 1 - x["won"]),
    ]).dropna(subset=["won"])
    win_pct = teams.groupby(["franchise", "season"])["won"].mean()
    seasons = sorted(df["season"].unique())
    prev = {s: seasons[i - 1] for i, s in enumerate(seasons) if i > 0}
    for side in ("bat_first", "chase"):
        df[f"{side}_prev_season_win_pct"] = [
            win_pct.get((f, prev.get(s)), np.nan) for f, s in zip(df[f"{side}_franchise"], df["season"])]

    # Venue average first-innings score from earlier matches only (expanding mean, shifted).
    valid = (df.match_status == "completed") & df.inn1_total_runs.notna()
    score = df.inn1_total_runs.where(valid)
    by_venue = score.groupby(df.venue_key)
    prior_sum = by_venue.transform(lambda s: s.shift().fillna(0).cumsum())
    prior_n = by_venue.transform(lambda s: s.shift().notna().cumsum())
    league = score.shift().expanding().mean()
    df["venue_avg_first_innings_prior"] = (prior_sum / prior_n.replace(0, np.nan)).fillna(league)

    df["toss_decision_bat"] = (df.toss_decision == "bat").astype(int)
    keep = ["match_key", "source_match_id", "match_date", "season", TARGET] + MODEL_B
    out = df.loc[df.ml_eligible == 1, keep].reset_index(drop=True)
    counts = [TARGET] + [f"inn{i}_{c}" for i in (1, 2) for c in ("pp_runs", "pp_wickets", "pp_boundaries")]
    return out.astype({c: int for c in counts})
