"""End-to-end run on the synthetic fixture."""
import numpy as np
import pandas as pd

from tests.conftest import build_project, read
from tests.synthetic import generate


def test_pipeline_passes_all_gates(built):
    paths, code = built
    assert code == 0
    report = pd.read_csv(paths.logs / "validation_report.csv")
    assert set(report.gate) == {f"G{i}" for i in range(1, 10)}
    assert report.status.isin(["PASS", "SKIP"]).all(), report[report.status == "FAIL"]


def test_extraction_log_records_provenance(built):
    paths, _ = built
    log = pd.read_csv(paths.logs / "extraction_log.csv")
    assert set(log.file) == {"matches.csv", "deliveries.csv"}
    assert log.sha256.str.len().eq(64).all()
    assert (log.source_url == "synthetic-test").all()


def test_all_expected_quality_issues_confirmed(built):
    paths, _ = built
    findings = pd.read_csv(paths.logs / "data_quality_findings.csv")
    assert (findings.status == "CONFIRMED").all(), findings


def test_team_renames_are_type2_spells(db):
    t = pd.read_sql("SELECT * FROM dim_team ORDER BY team_key", db)
    delhi = t[t.franchise_id == "DEL"].sort_values("valid_from_season")
    assert list(delhi.canonical_name) == ["Delhi Daredevils", "Delhi Capitals"]
    assert list(delhi.is_current) == [0, 1]
    assert delhi.valid_to_season.iloc[0] == 2009 and pd.isna(delhi.valid_to_season.iloc[1])
    # Spelling variants collapse to one name.
    assert (t.franchise_id == "RPS").sum() == 1
    assert t.groupby("franchise_id").is_current.sum().eq(1).all()


def test_venue_and_player_variants_resolved(db):
    venues = pd.read_sql("SELECT * FROM dim_venue", db)
    assert len(venues) == 4 and venues.city.notna().all()
    assert "Feroz Shah Kotla" not in set(venues.canonical_name)
    players = set(pd.read_sql("SELECT canonical_name FROM dim_player", db).canonical_name)
    assert "MS Dhoni" in players and "M.S. Dhoni" not in players
    assert not any("(sub)" in p for p in players)


def test_seasons_and_overs_normalised(db):
    years = pd.read_sql("SELECT year FROM dim_season ORDER BY year", db).year.tolist()
    assert years == [2008, 2009, 2010, 2011]
    lo, hi = db.execute("SELECT MIN(over), MAX(over) FROM fact_delivery").fetchone()
    assert (lo, hi) == (1, 20)


def test_super_over_and_special_matches(db):
    s = pd.read_sql("""SELECT m.source_match_id, m.match_status, m.is_super_over, m.is_dl_applied,
                              f.winner_key, f.ml_eligible
                       FROM dim_match m JOIN fact_match_summary f USING (match_key)""", db)
    assert (s.match_status == "no_result").sum() == 1
    assert s.is_super_over.sum() == 1 and s.is_dl_applied.sum() == 1
    special = s[(s.match_status != "completed") | (s.is_super_over == 1) | (s.is_dl_applied == 1)]
    assert (special.ml_eligible == 0).all()
    phases = db.execute("SELECT COUNT(*) FROM fact_delivery WHERE is_super_over_innings = 1 "
                        "AND phase_key IS NOT NULL").fetchone()[0]
    assert phases == 0


def test_player_season_phase_reconciles_with_deliveries(db):
    faced = db.execute("""SELECT SUM(is_faced_by_batter), SUM(is_legal_for_bowler) FROM fact_delivery
                          WHERE is_super_over_innings = 0""").fetchone()
    agg = dict(db.execute("SELECT role_type, SUM(balls) FROM fact_player_season_phase GROUP BY role_type"))
    assert agg["batting"] == faced[0] and agg["bowling"] == faced[1]
    shares = pd.read_sql("""SELECT player_key, season_key, role_type, SUM(phase_share) s
                            FROM fact_player_season_phase GROUP BY 1, 2, 3""", db)
    assert np.allclose(shares.s, 1.0)
    primaries = pd.read_sql("""SELECT player_key, season_key, role_type, SUM(is_primary_phase) n, MAX(qualifies) q
                               FROM fact_player_season_phase GROUP BY 1, 2, 3""", db)
    assert (primaries.n == primaries.q).all()


def test_planted_drifts_detected(built):
    paths, _ = built
    drift = read(paths, "drift_table")
    got = {(r.player, r.role_type, r.from_phase, r.to_phase, r.from_season, r.to_season)
           for r in drift.itertuples()}
    assert ("Drift Batter", "batting", "Powerplay", "Death", 2009, 2010) in got
    assert ("Drift Bowler", "bowling", "Powerplay", "Death", 2009, 2010) in got
    sens = read(paths, "drift_sensitivity")
    assert set(sens.threshold_balls) == {60, 120}


def test_g4_lists_dl_exception(built):
    paths, _ = built
    exc = pd.read_csv(paths.logs / "g4_exceptions.csv")
    assert len(exc) == 1 and exc.is_dl_applied.iloc[0] == 1


def test_ml_features_use_only_earlier_matches(built, db):
    paths, _ = built
    f = read(paths, "ml_features")
    assert {"inn1_pp_run_rate", "bat_first_won"} <= set(f.columns)
    for leak in ("target_runs", "result_margin", "winner_key", "player_of_match_key"):
        assert leak not in f.columns
    first_season = f.season.min()
    assert f.loc[f.season == first_season, "bat_first_prev_season_win_pct"].isna().all()

    ms = pd.read_sql("""SELECT s.match_key, s.venue_key, s.inn1_total_runs, s.match_status, m.match_date,
                               m.source_match_id
                        FROM fact_match_summary s JOIN dim_match m USING (match_key)
                        ORDER BY m.match_date, m.source_match_id""", db).reset_index(drop=True)
    for row in f.itertuples():
        pos = ms.index[ms.match_key == row.match_key][0]
        venue = ms.venue_key[pos]
        earlier = ms.iloc[:pos]
        earlier = earlier[(earlier.match_status == "completed") & earlier.inn1_total_runs.notna()]
        at_venue = earlier[earlier.venue_key == venue].inn1_total_runs
        expected = at_venue.mean() if len(at_venue) else earlier.inn1_total_runs.mean()
        assert np.isclose(row.venue_avg_first_innings_prior, expected, equal_nan=True)


def test_rerun_is_deterministic(built, tmp_path):
    paths, _ = built
    other, code = build_project(tmp_path)
    assert code == 0
    for name in ("fact_match_summary", "fact_player_season_phase", "dim_player_phase_profile"):
        pd.testing.assert_frame_equal(read(paths, name), read(other, name))


def test_unmapped_team_stops_the_run(tmp_path):
    raw = tmp_path / "data" / "raw"
    m, d = generate(raw)
    m.loc[0, "team1"] = "Mystery XI"
    m.to_csv(raw / "matches.csv", index=False)
    paths, code = build_project(tmp_path)
    assert code == 1
    report = pd.read_csv(paths.logs / "validation_report.csv")
    assert report.set_index("gate").status["G6"] == "FAIL"
    unmapped = pd.read_csv(paths.logs / "unmapped_entities.csv")
    assert "Mystery XI" in set(unmapped.raw_value)


def test_star_schema_has_no_snowflaking():
    """Every foreign key runs from a fact table to a dimension; no dimension references another table."""
    import re
    from src.config import SQL_DIR
    ddl = (SQL_DIR / "ddl.sql").read_text()
    for name, body in re.findall(r"CREATE TABLE (\w+) \((.*?)\n\);", ddl, re.S):
        if name.startswith("dim_"):
            assert "REFERENCES" not in body, f"{name} references another table"
        else:
            assert re.findall(r"REFERENCES (\w+)\(", body), f"{name} has no dimensions"
            assert all(t.startswith("dim_") for t in re.findall(r"REFERENCES (\w+)\(", body))


def test_scd2_spell_is_linked_to_the_fact(db):
    f = pd.read_sql("""SELECT f.qualifies, f.is_primary_phase, f.phase_key, p.primary_phase_key, f.profile_key
                       FROM fact_player_season_phase f
                       LEFT JOIN dim_player_phase_profile p USING (profile_key)""", db)
    q = f[f.qualifies == 1]
    assert q.profile_key.notna().all()
    prim = q[q.is_primary_phase == 1]
    assert (prim.phase_key == prim.primary_phase_key).all()
