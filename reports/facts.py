"""Collect every number quoted in the report, cleaning log, deck and build guide.

    python reports/facts.py        # after src.pipeline, src.analysis, src.ml, src.powerbi

Writes reports/facts.json, which the document builders read, so no figure in the
written deliverables is typed by hand.
"""
import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.config import Paths  # noqa: E402

P = Paths(root=ROOT)
EX, LOGS = P.export, P.logs


def r(x, n=1):
    return None if pd.isna(x) else round(float(x), n)


def main():
    con = sqlite3.connect(P.db)
    q = lambda s: pd.read_sql(s, con)  # noqa: E731
    f = {}

    raw_m = pd.read_csv(P.raw / "matches.csv", dtype=str, keep_default_na=False)
    raw_d = pd.read_csv(P.raw / "deliveries.csv", dtype=str, keep_default_na=False)
    ext = pd.read_csv(LOGS / "extraction_log.csv").drop_duplicates("file", keep="last").set_index("file")
    f["raw"] = {
        "matches_rows": len(raw_m), "matches_cols": raw_m.shape[1],
        "deliveries_rows": len(raw_d), "deliveries_cols": raw_d.shape[1],
        "matches_mb": r((P.raw / "matches.csv").stat().st_size / 1e6, 2),
        "deliveries_mb": r((P.raw / "deliveries.csv").stat().st_size / 1e6, 1),
        "sha_matches": ext.loc["matches.csv", "sha256"], "sha_deliveries": ext.loc["deliveries.csv", "sha256"],
        "team_strings": len(set(raw_m.team1) | set(raw_m.team2)), "venue_strings": raw_m.venue.nunique(),
        "season_text_rows": int((~raw_m.season.str.isdigit()).sum()),
        "na_method": int((raw_m.method == "NA").sum()), "na_city": int((raw_m.city == "NA").sum()),
        "wides": int((raw_d.extras_type == "wides").sum()), "noballs": int((raw_d.extras_type == "noballs").sum()),
        "blank_extras": int((raw_d.extras_type == "").sum()),
        "first_date": raw_m.date.min(), "last_date": raw_m.date.max(),
    }
    f["source"] = {
        "url": "https://www.kaggle.com/datasets/patrickb1912/ipl-complete-dataset-20082020",
        "title": "IPL Complete Dataset (2008-2024)", "owner": "Prateek Bhardwaj", "version": "3",
        "updated": "8 June 2024", "download_date": "18 October 2026",
        "licence": "Open Database License (database) / Database Contents License (contents)",
        "origin": "Cricsheet (cricsheet.org), Open Data Commons Attribution License",
    }

    counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in (
        "dim_season", "dim_phase", "dim_team", "dim_venue", "dim_player", "dim_match", "fact_delivery",
        "fact_match_summary", "fact_player_season_phase", "dim_player_phase_profile")}
    f["warehouse"] = counts
    f["warehouse"]["franchises"] = con.execute("SELECT COUNT(DISTINCT franchise_id) FROM dim_team").fetchone()[0]
    st = q("SELECT match_status, COUNT(*) n FROM dim_match GROUP BY 1").set_index("match_status").n
    f["matches"] = {"completed": int(st.get("completed", 0)), "tie": int(st.get("tie", 0)),
                    "no_result": int(st.get("no_result", 0)),
                    "super_over": con.execute("SELECT SUM(is_super_over) FROM dim_match").fetchone()[0],
                    "dl": con.execute("SELECT SUM(is_dl_applied) FROM dim_match").fetchone()[0],
                    "ml_eligible": con.execute("SELECT SUM(ml_eligible) FROM fact_match_summary").fetchone()[0]}
    f["matches"]["excluded_ml"] = counts["dim_match"] - f["matches"]["ml_eligible"]

    log = pd.read_csv(LOGS / "cleaning_log.csv")
    f["cleaning"] = {"rules": len(log), "cells": int(log.rows_affected.sum()),
                     "by_rule": log.groupby("rule").rows_affected.sum().astype(int).to_dict(),
                     "fuzzy_pairs": len(pd.read_csv(LOGS / "player_fuzzy_candidates.csv")),
                     "seven_ball_overs": len(pd.read_csv(LOGS / "g5_exceptions.csv")),
                     "g4_exceptions": len(pd.read_csv(LOGS / "g4_exceptions.csv"))}
    gates = pd.read_csv(LOGS / "validation_report.csv")
    f["gates"] = [{"gate": g.gate, "description": g.description, "status": g.status, "detail": g.detail}
                  for g in gates.sort_values("gate").itertuples()]

    # Insight 1: phase run rates
    rates = pd.read_csv(EX / "analysis" / "q2_league_phase_rates.csv")
    w = rates.pivot(index="season", columns="phase_name", values="run_rate")
    pp = rates[rates.phase_name == "Powerplay"].set_index("season")
    inn1 = q("SELECT s.year, AVG(inn1_total_runs) a FROM fact_match_summary f JOIN dim_season s USING (season_key) "
             "WHERE match_status = 'completed' GROUP BY 1").set_index("year").a
    f["i1"] = {ph: {"y2008": r(w.loc[2008, ph], 2), "y2022": r(w.loc[2022, ph], 2), "y2024": r(w.loc[2024, ph], 2),
                    "chg_08_24": r(100 * (w.loc[2024, ph] / w.loc[2008, ph] - 1)),
                    "chg_22_24": r(100 * (w.loc[2024, ph] / w.loc[2022, ph] - 1))}
               for ph in ("Powerplay", "Middle", "Death")}
    f["i1"]["pp_boundary"] = {"y2008": r(pp.boundary_pct[2008]), "y2024": r(pp.boundary_pct[2024])}
    f["i1"]["pp_dot"] = {"y2008": r(pp.dot_pct[2008]), "y2024": r(pp.dot_pct[2024])}
    f["i1"]["avg_inn1"] = {str(y): r(inn1[y]) for y in (2008, 2022, 2023, 2024)}

    # Insight 2: Powerplay vs result
    corr = pd.read_csv(EX / "analysis" / "q6_powerplay_correlation.csv").set_index("measure")
    bands = pd.read_csv(EX / "analysis" / "q6_powerplay_win_rate.csv")
    f["i2"] = {"matches": int(corr.loc["pp_rr_diff", "matches"]), "r": r(corr.loc["pp_rr_diff", "point_biserial_r"], 2),
               "higher_wins": r(corr.loc["pp_rr_diff", "higher_pp_rate_wins_pct"]),
               "bands": bands[["pp_rr_diff_band", "matches", "bat_first_win_pct"]].to_dict("records")}

    # Insight 3: toss
    toss = pd.read_csv(EX / "analysis" / "q5_toss_overall.csv").set_index("toss_decision")
    fs = q("SELECT s.year, 100.0 * AVG(toss_decision = 'field') p FROM fact_match_summary f "
           "JOIN dim_season s USING (season_key) GROUP BY 1").set_index("year").p
    venues = pd.read_csv(EX / "analysis" / "q5_toss_by_venue.csv")
    f["i3"] = {"overall": r(toss.overall_toss_winner_win_pct.iloc[0]),
               "field_pct": r(toss.loc["field", "win_pct"]), "field_won": int(toss.loc["field", "toss_winner_won"]),
               "field_n": int(toss.loc["field", "matches"]), "bat_pct": r(toss.loc["bat", "win_pct"]),
               "bat_won": int(toss.loc["bat", "toss_winner_won"]), "bat_n": int(toss.loc["bat", "matches"]),
               "chi2": r(toss.chi2.iloc[0], 2), "p": r(toss.p_value.iloc[0], 3),
               "field_share_pre2014_min": r(fs.loc[2008:2013].min(), 0), "field_share_pre2014_max": r(fs.loc[2008:2013].max(), 0),
               "field_share_2016_2019_min": r(fs.loc[2016:2019].min(), 0), "field_share_2024": r(fs.loc[2024], 0),
               "venues_tested": len(venues), "venue_min_p": r(venues.p_value.min(), 3),
               "venue_min_n": int(venues.matches.min()), "venue_max_n": int(venues.matches.max())}

    # Insight 4: drift
    ds = pd.read_csv(EX / "analysis" / "q1_drift_summary.csv")
    mv = pd.read_csv(EX / "analysis" / "q1_drift_moves.csv")
    d = {}
    for t in (60, 120):
        for role in ("batting", "bowling"):
            row = ds[(ds.threshold_balls == t) & (ds.role_type == role)].iloc[0]
            d[f"{role}_{t}"] = {"pool": int(row.players_with_2plus_qualifying_seasons),
                                "changed": int(row.players_who_changed), "changes": int(row.phase_changes),
                                "pct": r(100 * row.players_who_changed / row.players_with_2plus_qualifying_seasons, 0)}
    bat = mv[mv.role_type == "batting"]
    bowl = mv[mv.role_type == "bowling"]
    mid = bat[(bat.from_phase == "Middle") | (bat.to_phase == "Middle")].n.sum()
    ppd = bowl[bowl.from_phase.isin(["Powerplay", "Death"]) & bowl.to_phase.isin(["Powerplay", "Death"])].n.sum()
    d["bat_middle_moves"], d["bat_moves"] = int(mid), int(bat.n.sum())
    d["bowl_ppdeath_moves"], d["bowl_moves"] = int(ppd), int(bowl.n.sum())
    d["bat_middle_pct"] = r(100 * mid / bat.n.sum(), 0)
    d["bowl_ppdeath_pct"] = r(100 * ppd / bowl.n.sum(), 0)
    d["moves"] = mv.to_dict("records")
    f["i4"] = d

    vp = pd.read_csv(EX / "analysis" / "q4_venue_profile.csv")
    f["venues"] = vp.head(8)[["venue", "city", "matches", "avg_first_innings", "bat_first_win_rate"]].to_dict("records")

    # ML
    m = pd.read_csv(EX / "ml" / "metrics.csv")
    t = m[m.split == "test"]
    f["ml"] = {"split": pd.read_csv(EX / "ml" / "split.csv").to_dict("records"),
               "test": [{k: (r(v, 3) if isinstance(v, float) else v) for k, v in row.items()}
                        for row in t[["feature_set", "model", "params", "accuracy", "precision", "recall", "f1",
                                      "roc_auc", "tn", "fp", "fn", "tp"]].fillna("").to_dict("records")]}
    cv = pd.read_csv(EX / "ml" / "cv_results.csv")
    best = cv.loc[cv.groupby(["feature_set", "model"]).cv_roc_auc.idxmax()]
    f["ml"]["cv_best"] = [{"feature_set": b.feature_set, "model": b.model, "cv_auc": r(b.cv_roc_auc, 3),
                           "folds": int(b.folds)} for b in best.itertuples()]
    preds = pd.read_csv(EX / "ml" / "test_predictions.csv")
    lr = preds[(preds.feature_set == "B") & (preds.model == "logistic_regression")]
    f["ml"]["lr_b_by_season"] = {str(k): r(100 * v) for k, v in lr.groupby("season").correct.mean().items()}
    feats = pd.read_csv(EX / "ml_features.csv")
    f["ml"]["bat_first_win_train"] = r(100 * feats[feats.season <= 2021].bat_first_won.mean())
    f["ml"]["bat_first_win_test"] = r(100 * feats[feats.season >= 2023].bat_first_won.mean())
    imp = pd.read_csv(EX / "ml" / "feature_importance.csv")
    f["ml"]["rf_b_top"] = imp[(imp.feature_set == "B") & (imp.model == "random_forest")] \
        .nlargest(5, "value")[["feature", "value"]].round(3).to_dict("records")
    dev = feats[feats.season <= 2022]
    lo = dev[dev.inn2_pp_wickets <= 1]
    hi = dev[dev.inn2_pp_wickets >= 2]
    f["ml"]["chase_win_le1_wkt"] = r(100 * (1 - lo.bat_first_won.mean()))
    f["ml"]["chase_win_ge2_wkt"] = r(100 * (1 - hi.bat_first_won.mean()))
    f["ml"]["upsets"] = pd.read_csv(EX / "ml" / "upsets.csv").groupby(["feature_set", "model"]).size() \
        .reset_index(name="n").to_dict("records")

    tm = pd.read_csv(EX / "powerbi" / "csv" / "TeamMatches.csv")
    f["teams_win_pct"] = (100 * tm.groupby("franchise_id").won.mean()).round(1).sort_values(ascending=False).to_dict()
    f["pbi_tables"] = {p.stem: int(sum(1 for _ in open(p)) - 1) for p in sorted((EX / "powerbi" / "csv").glob("*.csv"))}
    con.close()
    out = ROOT / "reports" / "facts.json"
    out.write_text(json.dumps(f, indent=1, default=str))
    print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
