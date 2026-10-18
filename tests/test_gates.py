"""Each gate must catch the corruption it is designed for."""
from src.validate import run_gates


def status(conn, gate, **ctx):
    return run_gates(conn, [gate], ctx)[0].status


def test_g1_dangling_foreign_key(db_copy):
    db_copy.execute("UPDATE fact_delivery SET batter_key = 99999 WHERE rowid = 1")
    assert status(db_copy, "G1") == "FAIL"


def test_g3_run_arithmetic(db_copy):
    db_copy.execute("UPDATE fact_delivery SET total_runs = total_runs + 1 WHERE rowid = 1")
    assert status(db_copy, "G3") == "FAIL"


def test_g4_unexplained_target(db_copy):
    db_copy.execute("""UPDATE dim_match SET target_runs = target_runs + 5
                       WHERE match_key = (SELECT MIN(match_key) FROM dim_match
                                          WHERE match_status = 'completed' AND is_dl_applied = 0)""")
    assert status(db_copy, "G4") == "FAIL"


def test_g5_too_many_legal_balls(db_copy):
    db_copy.execute("""UPDATE fact_delivery SET is_legal_for_bowler = 1
                       WHERE match_key = 1 AND inning = 1""")
    db_copy.execute("""INSERT INTO fact_delivery SELECT match_key, season_key, inning, delivery_seq + 1000,
                       batting_team_key, bowling_team_key, batter_key, bowler_key, non_striker_key,
                       player_dismissed_key, fielder_key, phase_key, over, ball, batsman_runs, extra_runs,
                       total_runs, extras_type, is_wicket, dismissal_kind, is_super_over_innings,
                       is_legal_for_bowler, is_faced_by_batter, is_boundary, is_dot
                       FROM fact_delivery WHERE match_key = 1 AND inning = 1 LIMIT 10""")
    assert status(db_copy, "G5") == "FAIL"


def test_g5_seven_ball_over_is_an_explained_exception(db_copy, tmp_path):
    # Umpire miscount: one extra legal, run-less delivery at the end of a full over (D-20).
    mk, inn, ov = db_copy.execute("""SELECT match_key, inning, over FROM fact_delivery
                                     WHERE is_super_over_innings = 0 GROUP BY 1, 2, 3
                                     HAVING SUM(is_legal_for_bowler) = 6 LIMIT 1""").fetchone()
    db_copy.execute("""INSERT INTO fact_delivery SELECT match_key, season_key, inning, delivery_seq + 1000,
                       batting_team_key, bowling_team_key, batter_key, bowler_key, non_striker_key,
                       NULL, NULL, phase_key, over, 7, 0, 0, 0, 'none', 0, 'none', 0, 1, 1, 0, 1
                       FROM fact_delivery WHERE match_key = ? AND inning = ? AND over = ? LIMIT 1""",
                    (mk, inn, ov))
    assert status(db_copy, "G5", logs=tmp_path) == "PASS"
    import pandas as pd
    assert len(pd.read_csv(tmp_path / "g5_exceptions.csv")) == 1


def test_g7_winner_not_a_participant(db_copy):
    db_copy.execute("""UPDATE fact_match_summary SET winner_key = (
                           SELECT team_key FROM dim_team WHERE team_key NOT IN (
                               SELECT team1_key FROM dim_match WHERE match_key = 1
                               UNION SELECT team2_key FROM dim_match WHERE match_key = 1) LIMIT 1)
                       WHERE match_key = 1""")
    assert status(db_copy, "G7") == "FAIL"


def test_g8_two_current_rows(db_copy):
    db_copy.execute("""INSERT INTO dim_player_phase_profile
                       SELECT profile_key + 100000, player_key, role_type, primary_phase_key,
                              phase_index_value, valid_from_season + 1, NULL, last_seen_season,
                              qualifying_seasons, 1, threshold_balls
                       FROM dim_player_phase_profile WHERE is_current = 1 LIMIT 1""")
    assert status(db_copy, "G8") == "FAIL"


def test_g9_row_count_mismatch(db_copy):
    db_copy.execute("DELETE FROM fact_delivery WHERE rowid = 1")
    assert status(db_copy, "G9") == "FAIL"


def test_g6_franchise_count(db_copy):
    assert status(db_copy, "G6", expected_franchises=4) == "PASS"
    assert status(db_copy, "G6", expected_franchises=15) == "FAIL"
