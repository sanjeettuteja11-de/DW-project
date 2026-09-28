"""SCD Type 2 rules of section 8.4 on hand-made season primaries."""
import pandas as pd

from src.scd2 import build_profile

PP, MID, DEATH = 1, 2, 3


def primaries(rows):
    return pd.DataFrame(rows, columns=["player_key", "role_type", "season", "primary_phase_key", "phase_index"])


def spells(profile, player=1, role="batting"):
    p = profile[(profile.player_key == player) & (profile.role_type == role)]
    return [(r.primary_phase_key, r.valid_from_season,
             None if pd.isna(r.valid_to_season) else int(r.valid_to_season), r.is_current)
            for r in p.itertuples()]


def test_unchanged_phase_extends_the_open_row():
    prof = build_profile(primaries([(1, "batting", y, PP, 2.0) for y in (2008, 2009, 2010)]))
    assert spells(prof) == [(PP, 2008, None, 1)]
    assert prof.qualifying_seasons.iloc[0] == 3 and prof.last_seen_season.iloc[0] == 2010


def test_change_closes_old_row_at_last_season_with_old_phase():
    prof = build_profile(primaries([
        (1, "batting", 2008, PP, 2.0), (1, "batting", 2009, PP, 2.1),
        (1, "batting", 2010, DEATH, 3.0), (1, "batting", 2011, MID, 1.2),
    ]))
    assert spells(prof) == [(PP, 2008, 2009, 0), (DEATH, 2010, 2010, 0), (MID, 2011, None, 1)]
    assert prof.phase_index_value.tolist() == [2.0, 3.0, 1.2]


def test_gap_season_neither_opens_nor_closes():
    # Qualifies 2008 and 2011 only; the change is dated from the next qualifying season.
    prof = build_profile(primaries([(1, "batting", 2008, PP, 2.0), (1, "batting", 2011, DEATH, 3.0)]))
    assert spells(prof) == [(PP, 2008, 2008, 0), (DEATH, 2011, None, 1)]
    # A gap with no change keeps a single spell.
    prof = build_profile(primaries([(1, "batting", 2008, PP, 2.0), (1, "batting", 2011, PP, 2.5)]))
    assert spells(prof) == [(PP, 2008, None, 1)]


def test_roles_and_players_are_independent():
    prof = build_profile(primaries([
        (1, "batting", 2008, PP, 2.0), (1, "bowling", 2008, DEATH, 2.0),
        (1, "batting", 2009, MID, 1.5), (2, "batting", 2009, MID, 1.1),
    ]))
    assert spells(prof, 1, "bowling") == [(DEATH, 2008, None, 1)]
    assert spells(prof, 1, "batting") == [(PP, 2008, 2008, 0), (MID, 2009, None, 1)]
    assert spells(prof, 2, "batting") == [(MID, 2009, None, 1)]
    assert prof.groupby(["player_key", "role_type"]).is_current.sum().eq(1).all()
    assert prof.profile_key.is_unique


def test_empty_input():
    assert build_profile(primaries([])).empty
