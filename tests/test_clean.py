"""Row-level cleaning rules."""
import pandas as pd

from src.clean import CleaningLog, normalise_deliveries, nullify


def deliveries(rows, columns=None):
    cols = columns or ["match_id", "inning", "batting_team", "bowling_team", "over", "ball", "batter",
                       "bowler", "non_striker", "batsman_runs", "extra_runs", "total_runs", "extras_type",
                       "is_wicket", "player_dismissed", "dismissal_kind", "fielder"]
    df = pd.DataFrame(rows, columns=cols).astype(str)
    df.insert(0, "source_row", range(1, len(df) + 1))
    log = CleaningLog()
    return normalise_deliveries(nullify(df, "deliveries", log), log), log.frame()


def test_legal_ball_flags_and_over_shift():
    d, log = deliveries([
        (1, 1, "A", "B", 0, 1, "x", "y", "z", 0, 1, 1, "wides", 0, "NA", "NA", "NA"),
        (1, 1, "A", "B", 0, 1, "x", "y", "z", 4, 1, 5, "noballs", 0, "NA", "NA", "NA"),
        (1, 1, "A", "B", 0, 1, "x", "y", "z", 0, 0, 0, "NA", 0, "NA", "NA", "NA"),
        (1, 1, "A", "B", 0, 2, "x", "y", "z", 0, 1, 1, "legbyes", 0, "NA", "NA", "NA"),
    ])
    assert d.over.tolist() == [1, 1, 1, 1]
    assert d.delivery_seq.tolist() == [1, 2, 3, 4]
    assert d.is_legal_for_bowler.tolist() == [0, 0, 1, 1]
    assert d.is_faced_by_batter.tolist() == [0, 1, 1, 1]
    assert d.is_boundary.tolist() == [0, 1, 0, 0]
    assert d.is_dot.tolist() == [0, 0, 1, 0]
    assert d.extras_type.tolist() == ["wides", "noballs", "none", "legbyes"]
    assert "shift 0-based overs to 1-20" in set(log.rule)


def test_older_dataset_version_columns():
    cols = ["match_id", "inning", "batting_team", "bowling_team", "over", "ball", "batsman", "non_striker",
            "bowler", "is_super_over", "wide_runs", "bye_runs", "legbye_runs", "noball_runs",
            "penalty_runs", "batsman_runs", "extra_runs", "total_runs", "player_dismissed",
            "dismissal_kind", "fielder"]
    d, _ = deliveries([
        (1, 1, "A", "B", 1, 1, "x", "z", "y", 0, 1, 0, 0, 0, 0, 0, 1, 1, "", "", ""),
        (1, 1, "A", "B", 1, 1, "x", "z", "y", 0, 0, 0, 0, 0, 0, 0, 0, 0, "x", "bowled", ""),
        (1, 3, "A", "B", 1, 1, "x", "z", "y", 1, 0, 0, 0, 0, 0, 6, 0, 6, "", "", ""),
    ], cols)
    assert d.batter.tolist() == ["x", "x", "x"]
    assert d.extras_type.tolist() == ["wides", "none", "none"]
    assert d.is_wicket.tolist() == [0, 1, 0]
    assert d.is_super_over_innings.tolist() == [0, 0, 1]
    assert d.over.tolist() == [1, 1, 1]  # already 1-based: no shift
