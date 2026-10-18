"""Power BI data pack: the warehouse and model outputs as Power BI-ready tables.

    python -m src.powerbi        # after src.pipeline and src.ml

Writes data/export/powerbi/IPL_PowerBI_Data.xlsx (one Excel table per sheet, so
Power BI Desktop and the Power BI service both import it in one step) and the
same tables as CSV files. Team, venue and season names are denormalised onto
the fact tables so the report needs only a few relationships (see
docs/PowerBI_Build_Guide.docx).
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import pandas as pd

from .config import PROJECT_ROOT, Paths

IMPACT_PLAYER_FIRST_SEASON = 2023

COUNTRY_BY_CITY = {
    "Dubai": "UAE", "Abu Dhabi": "UAE", "Sharjah": "UAE",
    "Durban": "South Africa", "Centurion": "South Africa", "Johannesburg": "South Africa",
    "Cape Town": "South Africa", "Port Elizabeth": "South Africa", "East London": "South Africa",
    "Kimberley": "South Africa", "Bloemfontein": "South Africa",
}

SHORT_VENUE = {
    "Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium": "Ekana Cricket Stadium",
    "Dr. Y.S. Rajasekhara Reddy ACA-VDCA Cricket Stadium": "ACA-VDCA Stadium",
    "Himachal Pradesh Cricket Association Stadium": "HPCA Stadium",
    "Punjab Cricket Association IS Bindra Stadium": "PCA IS Bindra Stadium",
    "Maharashtra Cricket Association Stadium": "MCA Stadium",
    "Maharaja Yadavindra Singh International Cricket Stadium, Mullanpur": "Mullanpur Stadium",
    "Shaheed Veer Narayan Singh International Stadium": "SVNS Stadium, Raipur",
    "Vidarbha Cricket Association Stadium, Jamtha": "VCA Stadium, Nagpur",
    "JSCA International Stadium Complex": "JSCA Stadium",
}

MODEL_LABELS = {
    "baseline_majority": "Baseline: majority class",
    "baseline_pp_rate_above_train_median": "Baseline: PP rate above median",
    "baseline_higher_pp_rate_wins": "Baseline: higher PP rate wins",
    "logistic_regression": "Logistic regression",
    "decision_tree": "Decision tree",
    "random_forest": "Random forest",
}


def _q(conn, sql: str) -> pd.DataFrame:
    return pd.read_sql(sql, conn)


def build(paths: Paths) -> dict[str, pd.DataFrame]:
    conn = sqlite3.connect(paths.db)
    try:
        season = _q(conn, "SELECT season_key, year AS season FROM dim_season ORDER BY year")
        season["era"] = season.season.map(
            lambda y: "Impact Player era (2023-)" if y >= IMPACT_PLAYER_FIRST_SEASON else "Before 2023")

        phase = _q(conn, "SELECT phase_key, phase_name AS phase, start_over, end_over FROM dim_phase")
        phase["overs"] = phase.start_over.astype(str) + "-" + phase.end_over.astype(str)

        venue = _q(conn, "SELECT venue_key, canonical_name AS venue, city FROM dim_venue")
        venue["venue_short"] = venue.venue.map(lambda v: SHORT_VENUE.get(v, v))
        venue["country"] = venue.city.map(lambda c: COUNTRY_BY_CITY.get(c, "India"))

        franchise = _q(conn, """
            SELECT franchise_id, canonical_name AS latest_name, valid_to_season IS NULL AS active
            FROM dim_team t WHERE valid_from_season = (
                SELECT MAX(valid_from_season) FROM dim_team u WHERE u.franchise_id = t.franchise_id)""")
        franchise["active"] = franchise.active.astype(int)

        team = _q(conn, """SELECT team_key, franchise_id, canonical_name AS team_name, valid_from_season,
                                  valid_to_season, is_current FROM dim_team""")

        matches = _q(conn, """
            SELECT s.match_key, m.source_match_id, m.match_date, s.season_key, s.venue_key,
                   tb.franchise_id AS bat_first_franchise, tb.canonical_name AS bat_first_team,
                   tc.franchise_id AS chase_franchise, tc.canonical_name AS chase_team,
                   tt.franchise_id AS toss_winner_franchise, s.toss_decision, s.toss_winner_bat_first,
                   tw.franchise_id AS winner_franchise, tw.canonical_name AS winner_team,
                   s.match_status, s.result_type, m.result_margin, m.is_super_over, m.is_dl_applied,
                   s.inn1_pp_runs, s.inn1_pp_wickets, s.inn1_pp_run_rate, s.inn1_pp_dot_pct,
                   s.inn1_total_runs, s.inn1_wickets,
                   s.inn2_pp_runs, s.inn2_pp_wickets, s.inn2_pp_run_rate, s.inn2_pp_dot_pct,
                   s.inn2_total_runs, s.inn2_wickets,
                   ROUND(s.inn1_pp_run_rate - s.inn2_pp_run_rate, 3) AS pp_run_rate_diff,
                   s.bat_first_won, s.ml_eligible,
                   CASE WHEN s.winner_key IS NULL THEN NULL
                        WHEN s.winner_key = s.toss_winner_key THEN 1 ELSE 0 END AS toss_winner_won,
                   pl.canonical_name AS player_of_match
            FROM fact_match_summary s
            JOIN dim_match m USING (match_key)
            JOIN dim_team tb ON tb.team_key = s.bat_first_team_key
            JOIN dim_team tc ON tc.team_key = s.chase_team_key
            JOIN dim_team tt ON tt.team_key = s.toss_winner_key
            LEFT JOIN dim_team tw ON tw.team_key = s.winner_key
            LEFT JOIN dim_player pl ON pl.player_key = m.player_of_match_key
            ORDER BY m.match_date, m.source_match_id""")
        bins = [-99, -3, -1.5, -0.5, 0.5, 1.5, 3, 99]
        labels = ["< -3", "-3 to -1.5", "-1.5 to -0.5", "-0.5 to 0.5", "0.5 to 1.5", "1.5 to 3", "> 3"]
        matches["pp_diff_band"] = pd.cut(matches.pp_run_rate_diff, bins, labels=labels).astype(str)
        matches.loc[matches.pp_run_rate_diff.isna(), "pp_diff_band"] = None
        matches["pp_diff_band_order"] = matches.pp_diff_band.map({b: i for i, b in enumerate(labels)})

        # One row per team per match: the table behind team win % and team slicers.
        tm = []
        for role, fr, tn, pp, tot, won in (
                ("Batting first", "bat_first_franchise", "bat_first_team", "inn1_pp_run_rate",
                 "inn1_total_runs", lambda d: d.bat_first_won),
                ("Chasing", "chase_franchise", "chase_team", "inn2_pp_run_rate",
                 "inn2_total_runs", lambda d: 1 - d.bat_first_won)):
            tm.append(pd.DataFrame({
                "match_key": matches.match_key, "season_key": matches.season_key,
                "venue_key": matches.venue_key, "franchise_id": matches[fr], "team_name": matches[tn],
                "role": role, "won": won(matches), "pp_run_rate": matches[pp], "total_runs": matches[tot]}))
        team_matches = pd.concat(tm, ignore_index=True)

        innings_phase = _q(conn, """
            SELECT f.match_key, f.season_key, m.venue_key, f.inning, f.phase_key,
                   tb.franchise_id AS batting_franchise, tw.franchise_id AS bowling_franchise,
                   SUM(f.total_runs) AS runs, SUM(f.is_legal_for_bowler) AS legal_balls,
                   SUM(f.is_wicket) AS wickets, SUM(f.is_boundary) AS boundaries,
                   SUM(f.is_dot) AS dots, SUM(f.is_faced_by_batter) AS balls_faced
            FROM fact_delivery f
            JOIN dim_match m USING (match_key)
            JOIN dim_team tb ON tb.team_key = f.batting_team_key
            JOIN dim_team tw ON tw.team_key = f.bowling_team_key
            WHERE f.phase_key IS NOT NULL
            GROUP BY f.match_key, f.inning, f.phase_key""")

        player_season_phase = _q(conn, """
            SELECT f.player_key, p.canonical_name AS player, f.season_key, f.role_type, f.phase_key,
                   f.balls, f.runs, f.wickets, f.boundaries, f.dots, f.strike_rate, f.economy,
                   f.season_balls, f.phase_share, f.league_phase_share, f.phase_index,
                   f.qualifies, f.is_primary_phase
            FROM fact_player_season_phase f JOIN dim_player p USING (player_key)""")

        spells = _q(conn, """
            SELECT pr.profile_key, pr.player_key, pl.canonical_name AS player, pr.role_type,
                   ph.phase_name AS primary_phase, pr.phase_index_value, pr.valid_from_season,
                   pr.valid_to_season, pr.last_seen_season, pr.qualifying_seasons, pr.is_current
            FROM dim_player_phase_profile pr
            JOIN dim_player pl USING (player_key)
            JOIN dim_phase ph ON ph.phase_key = pr.primary_phase_key""")
    finally:
        conn.close()

    drift = pd.read_csv(paths.export / "drift_table.csv")
    drift["index_shift"] = (drift.to_phase_index_after - drift.to_phase_index_before).round(3)

    ml_dir = paths.export / "ml"
    metrics = pd.read_csv(ml_dir / "metrics.csv")
    metrics = metrics[metrics.split == "test"].copy()
    metrics["model_label"] = metrics.model.map(MODEL_LABELS)
    metrics["is_baseline"] = metrics.model.str.startswith("baseline").astype(int)
    preds = pd.read_csv(ml_dir / "test_predictions.csv")
    preds["model_label"] = preds.model.map(MODEL_LABELS)
    preds = preds.merge(matches[["match_key", "bat_first_team", "chase_team", "winner_team", "venue_key",
                                 "pp_run_rate_diff", "pp_diff_band", "pp_diff_band_order"]],
                        on="match_key", how="left")
    preds["confidence"] = preds.prob_bat_first_wins.map(lambda p: max(p, 1 - p) if pd.notna(p) else None)
    preds["predicted_label"] = preds.predicted_bat_first_won.map({1: "Bat first wins", 0: "Chase wins"})
    preds["actual_label"] = preds.actual_bat_first_won.map({1: "Bat first won", 0: "Chase won"})
    importance = pd.read_csv(ml_dir / "feature_importance.csv")
    importance["model_label"] = importance.model.map(MODEL_LABELS)
    importance["abs_value"] = importance.value.abs()

    return {
        "Season": season, "Phase": phase, "Venue": venue, "Franchise": franchise, "Team": team,
        "Matches": matches, "TeamMatches": team_matches, "InningsPhase": innings_phase,
        "PlayerSeasonPhase": player_season_phase, "PhaseSpells": spells, "PhaseChanges": drift,
        "ModelMetrics": metrics, "TestPredictions": preds, "FeatureImportance": importance,
    }


def write(tables: dict[str, pd.DataFrame], out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    csv_dir = out / "csv"
    csv_dir.mkdir(exist_ok=True)
    xlsx = out / "IPL_PowerBI_Data.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        for name, df in tables.items():
            df.to_excel(xw, sheet_name=name, index=False)
            ws = xw.sheets[name]
            from openpyxl.utils import get_column_letter
            from openpyxl.worksheet.table import Table, TableStyleInfo
            ref = f"A1:{get_column_letter(len(df.columns))}{len(df) + 1}"
            t = Table(displayName=f"tbl{name}", ref=ref)
            t.tableStyleInfo = TableStyleInfo(name="TableStyleLight1", showRowStripes=True)
            ws.add_table(t)
            for i, col in enumerate(df.columns, start=1):
                ws.column_dimensions[get_column_letter(i)].width = min(max(len(col) + 2, 10), 40)
        for name, df in tables.items():
            df.to_csv(csv_dir / f"{name}.csv", index=False)
    return xlsx


def run(paths: Paths) -> dict[str, pd.DataFrame]:
    tables = build(paths)
    write(tables, paths.export / "powerbi")
    return tables


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", type=Path, default=PROJECT_ROOT)
    a = p.parse_args(argv)
    tables = run(Paths(root=a.root))
    for name, df in tables.items():
        print(f"{name:18s} {len(df):>7,d} rows  {len(df.columns):>2d} columns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
