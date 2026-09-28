"""E10: SCD Type 2 dimension dim_player_phase_profile (rules in section 8.4) and the drift table.

The dimension is built by replaying seasons in order through `apply_season`,
exactly as an incremental season-by-season load would maintain it.
"""
from __future__ import annotations

import pandas as pd

from .config import QUALIFY_BALLS
from .transform import fact_player_season_phase

KEY = ("player_key", "role_type")


def season_primaries(fpsp: pd.DataFrame, season_years: pd.Series) -> pd.DataFrame:
    """One row per qualifying player x season x role: its primary phase and index."""
    p = fpsp[(fpsp.qualifies == 1) & (fpsp.is_primary_phase == 1)].copy()
    p["season"] = p["season_key"].map(season_years).astype(int)
    return p[["player_key", "role_type", "season", "phase_key", "phase_index"]].rename(
        columns={"phase_key": "primary_phase_key"})


def apply_season(rows: list[dict], season: int, primaries: pd.DataFrame) -> list[dict]:
    """Apply one season's qualifying primaries to the dimension rows (mutates and returns rows).

    - No open row: open one from this season.
    - Same phase as the open row: extend it (no new row).
    - Different phase: close the open row at its last qualifying season, open a new one.
    - Players who did not qualify this season are untouched (gap rule).
    """
    open_rows = {(r["player_key"], r["role_type"]): r for r in rows if r["is_current"]}
    for p in primaries.itertuples(index=False):
        k = (p.player_key, p.role_type)
        cur = open_rows.get(k)
        if cur is not None and cur["primary_phase_key"] == p.primary_phase_key:
            cur["last_seen_season"] = season
            cur["qualifying_seasons"] += 1
            continue
        if cur is not None:
            cur["valid_to_season"] = cur["last_seen_season"]
            cur["is_current"] = 0
        new = {"player_key": p.player_key, "role_type": p.role_type,
               "primary_phase_key": p.primary_phase_key, "phase_index_value": p.phase_index,
               "valid_from_season": season, "valid_to_season": None, "last_seen_season": season,
               "qualifying_seasons": 1, "is_current": 1}
        rows.append(new)
        open_rows[k] = new
    return rows


def build_profile(primaries: pd.DataFrame, threshold: int = QUALIFY_BALLS) -> pd.DataFrame:
    rows: list[dict] = []
    for season in sorted(primaries["season"].unique()):
        batch = primaries[primaries.season == season].sort_values(list(KEY))
        apply_season(rows, int(season), batch)
    cols = ["profile_key", "player_key", "role_type", "primary_phase_key", "phase_index_value",
            "valid_from_season", "valid_to_season", "last_seen_season", "qualifying_seasons",
            "is_current", "threshold_balls"]
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=cols)
    df = df.sort_values([*KEY, "valid_from_season"]).reset_index(drop=True)
    df["profile_key"] = range(1, len(df) + 1)
    df["valid_to_season"] = df["valid_to_season"].astype("Int64")
    df["threshold_balls"] = threshold
    return df[cols]


def drift_table(profile: pd.DataFrame, fpsp: pd.DataFrame, season_years: pd.Series,
                players: pd.DataFrame, phases: pd.DataFrame) -> pd.DataFrame:
    """Each change of primary phase, with the indices of both phases in both seasons."""
    p = profile.sort_values([*KEY, "valid_from_season"])
    nxt = p.groupby(list(KEY)).shift(-1)
    t = p.assign(to_phase_key=nxt["primary_phase_key"], to_season=nxt["valid_from_season"])
    t = t[t.to_phase_key.notna()].copy()
    t["to_phase_key"] = t["to_phase_key"].astype(int)
    t["to_season"] = t["to_season"].astype(int)
    t = t.rename(columns={"primary_phase_key": "from_phase_key", "valid_to_season": "from_season"})

    idx = fpsp.assign(season=fpsp.season_key.map(season_years)).set_index(
        ["player_key", "role_type", "season", "phase_key"])["phase_index"]

    def lookup(season_col, phase_col):
        return [idx.get((a, b, int(c), int(d)), 0.0)
                for a, b, c, d in zip(t.player_key, t.role_type, t[season_col], t[phase_col])]

    t["from_phase_index_before"] = lookup("from_season", "from_phase_key")
    t["to_phase_index_before"] = lookup("from_season", "to_phase_key")
    t["from_phase_index_after"] = lookup("to_season", "from_phase_key")
    t["to_phase_index_after"] = lookup("to_season", "to_phase_key")
    t["seasons_between"] = t["to_season"] - t["from_season"]
    name = players.set_index("player_key")["canonical_name"]
    phase = phases.set_index("phase_key")["phase_name"]
    t["player"] = t["player_key"].map(name)
    t["from_phase"] = t["from_phase_key"].map(phase)
    t["to_phase"] = t["to_phase_key"].map(phase)
    cols = ["player", "player_key", "role_type", "from_phase", "to_phase", "from_season", "to_season",
            "seasons_between", "from_phase_index_before", "to_phase_index_before",
            "from_phase_index_after", "to_phase_index_after"]
    out = t[cols].copy()
    for c in cols[-4:]:
        out[c] = out[c].astype(float).round(3)
    return out.sort_values(["role_type", "player", "to_season"]).reset_index(drop=True)


def sensitivity(fact_delivery: pd.DataFrame, season_years: pd.Series, thresholds) -> pd.DataFrame:
    """Drift counts at several qualification thresholds."""
    rows = []
    for th in thresholds:
        fpsp = fact_player_season_phase(fact_delivery, th)
        prim = season_primaries(fpsp, season_years)
        prof = build_profile(prim, th)
        for role in ("batting", "bowling"):
            pr = prof[prof.role_type == role]
            spells = pr.groupby("player_key").size()
            multi = prim[prim.role_type == role].groupby("player_key").size()
            rows.append({
                "threshold_balls": th, "role_type": role,
                "qualifying_player_seasons": int((prim.role_type == role).sum()),
                "players_with_2plus_qualifying_seasons": int((multi >= 2).sum()),
                "phase_changes": int((spells - 1).sum()),
                "players_who_changed": int((spells > 1).sum()),
            })
    return pd.DataFrame(rows)
