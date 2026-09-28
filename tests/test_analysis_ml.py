"""Phase 5-7 modules on the synthetic fixture."""
import os

import pandas as pd
import pytest

from src import analysis, ml
from src.config import PROJECT_ROOT
from src.features import MODEL_A, MODEL_B


@pytest.fixture(scope="module")
def analysis_results(built):
    paths, _ = built
    return analysis.run(paths)


@pytest.fixture(scope="module")
def ml_results(built):
    paths, _ = built
    return ml.run(paths)


def test_analysis_answers_every_question(built, analysis_results):
    paths, _ = built
    for q in ("q1_drift_summary", "q1_worked_examples", "q2_league_phase_rates", "q3_team_phase_profile",
              "q4_venue_profile", "q5_toss_overall", "q6_powerplay_win_rate"):
        assert not analysis_results[q].empty, q
    figs = paths.export / "analysis" / "figures"
    assert {"q2_league_phase_rates.png", "q3_team_powerplay_heatmap.png", "q6_powerplay_win_rate.png"} <= {
        p.name for p in figs.iterdir()}


def test_worked_examples_include_planted_drift(analysis_results):
    assert "Drift Batter" in set(analysis_results["q1_worked_examples"].player)


def test_toss_chi_square_is_valid(analysis_results):
    t = analysis_results["q5_toss_overall"]
    assert set(t.toss_decision) == {"bat", "field"}
    assert t.p_value.between(0, 1).all()
    assert t.matches.sum() == t.total_matches.iloc[0]


def test_powerplay_bands_cover_all_eligible_matches(built, analysis_results, db):
    n = db.execute("SELECT COUNT(*) FROM fact_match_summary WHERE ml_eligible = 1").fetchone()[0]
    assert analysis_results["q6_powerplay_win_rate"].matches.sum() == n


def test_season_split_is_chronological():
    s = ml.season_split([2008, 2009, 2010, 2011, 2012, 2013])
    assert (s.train, s.val, s.test) == ([2008, 2009, 2010], [2011], [2012, 2013])
    with pytest.raises(ValueError):
        ml.season_split([2008, 2009, 2010])


def test_forward_folds_never_train_on_later_seasons():
    df = pd.DataFrame({"season": [2008, 2008, 2009, 2010, 2010]})
    for s, tr, va in ml.forward_folds(df, [2008, 2009, 2010]):
        assert (df.loc[tr, "season"] < s).all() and (df.loc[va, "season"] == s).all()


def test_ml_results(ml_results):
    m = ml_results["metrics"]
    test = m[m.split == "test"]
    for fs in ("A", "B"):
        models = set(test[test.feature_set == fs].model)
        assert {"baseline_majority", "logistic_regression", "decision_tree", "random_forest"} <= models
    assert "baseline_higher_pp_rate_wins" in set(test[test.feature_set == "B"].model)
    assert test.accuracy.between(0, 1).all()
    assert (test.tn + test.fp + test.fn + test.tp == test.n).all()
    split = ml_results["split"].set_index("part")
    assert split.loc["test", "seasons"] == "2010 2011"
    imp = ml_results["feature_importance"]
    assert set(imp[imp.feature_set == "A"].feature) == set(MODEL_A)
    assert set(imp[imp.feature_set == "B"].feature) == set(MODEL_B)


def test_model_a_never_sees_second_innings():
    assert not any(f.startswith("inn2_") for f in MODEL_A)
    for leak in ("target_runs", "result_margin", "winner_key", "player_of_match_key"):
        assert leak not in MODEL_B


def test_dashboard_pages_render(built, ml_results):
    from streamlit.testing.v1 import AppTest

    paths, _ = built
    os.environ["IPL_DW_EXPORT"] = str(paths.export)
    try:
        for page in ("1. League overview", "2. Player phase drift", "3. Powerplay and outcome"):
            at = AppTest.from_file(str(PROJECT_ROOT / "dashboard" / "app.py"), default_timeout=60).run()
            at.sidebar.radio[0].set_value(page).run()
            assert not at.exception, (page, at.exception)
            assert at.title[0].value == page.split(". ", 1)[1]
    finally:
        os.environ.pop("IPL_DW_EXPORT", None)
