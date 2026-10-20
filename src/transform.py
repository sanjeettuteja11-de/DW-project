"""E7 (dimensions), E8 (fact_delivery) and E9 (aggregate facts).

Surrogate keys are assigned in a deterministic sort order so reruns on the
same input produce identical keys.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .clean import CleanResult
from .config import BOWLER_WICKET_KINDS, NOT_OUT_KINDS, PHASES, QUALIFY_BALLS


def _keys(values, name: str) -> pd.DataFrame:
    vals = sorted(pd.Series(values).dropna().unique())
    return pd.DataFrame({name: range(1, len(vals) + 1), "value": vals})


def _rate(num, den, mult):
    num, den = np.asarray(num, dtype=float), np.asarray(den, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(den > 0, num * mult / den, np.nan)


# ------------------------------------------------------------------ E7 dimensions

def date_key(dates: pd.Series) -> pd.Series:
    """Smart date key yyyymmdd from ISO date strings."""
    return dates.str.replace("-", "", regex=False).astype(int)


def dim_date(matches) -> pd.DataFrame:
    d = pd.to_datetime(pd.Series(sorted(matches["match_date"].dropna().unique())))
    return pd.DataFrame({
        "date_key": d.dt.strftime("%Y%m%d").astype(int),
        "full_date": d.dt.strftime("%Y-%m-%d"),
        "year": d.dt.year,
        "month": d.dt.month,
        "month_name": d.dt.strftime("%B"),
        "day_of_month": d.dt.day,
        "day_name": d.dt.strftime("%A"),
        "is_weekend": (d.dt.dayofweek >= 5).astype(int),
    })


def dim_season(matches) -> pd.DataFrame:
    return _keys(matches["season_year"], "season_key").rename(columns={"value": "year"})


def dim_phase() -> pd.DataFrame:
    return pd.DataFrame(PHASES, columns=["phase_key", "phase_name", "start_over", "end_over"])


def dim_team(matches, deliveries, team_map) -> pd.DataFrame:
    """SCD Type 2 on name: one row per (franchise, canonical name) spell, ordered by first season."""
    season_of = matches.set_index("match_id")["season_year"]
    usage = pd.concat([
        matches[["season_year", "team1"]].rename(columns={"team1": "name"}),
        matches[["season_year", "team2"]].rename(columns={"team2": "name"}),
        pd.DataFrame({"season_year": deliveries["match_id"].map(season_of),
                      "name": deliveries["batting_team"]}),
    ]).dropna()
    spells = usage.groupby("name")["season_year"].agg(["min", "max"]).reset_index()
    franchise = team_map.drop_duplicates("canonical_name").set_index("canonical_name")["franchise_id"]
    spells["franchise_id"] = spells["name"].map(franchise)
    spells = spells.sort_values(["franchise_id", "min", "name"]).reset_index(drop=True)
    latest_season = matches["season_year"].max()
    last_of_franchise = ~spells.duplicated("franchise_id", keep="last")
    is_current = last_of_franchise & (spells["max"] == latest_season)
    return pd.DataFrame({
        "team_key": range(1, len(spells) + 1),
        "franchise_id": spells["franchise_id"],
        "canonical_name": spells["name"],
        "valid_from_season": spells["min"].astype(int),
        "valid_to_season": spells["max"].astype("Int64").where(~is_current),
        "is_current": is_current.astype(int),
    })


def dim_venue(matches, venue_map) -> pd.DataFrame:
    city = venue_map.drop_duplicates("canonical_name").set_index("canonical_name")["city"]
    k = _keys(matches["venue"], "venue_key").rename(columns={"value": "canonical_name"})
    k["city"] = k["canonical_name"].map(city)
    return k


def dim_player(matches, deliveries) -> pd.DataFrame:
    cols = [deliveries[c] for c in ("batter", "bowler", "non_striker", "player_dismissed", "fielder")]
    return _keys(pd.concat(cols + [matches["player_of_match"]]), "player_key").rename(
        columns={"value": "canonical_name"})


# Columns of the dim_match table; the other columns of the match lookup become foreign keys in the facts.
DIM_MATCH_COLUMNS = ["match_key", "source_match_id", "match_date", "toss_decision", "match_status",
                     "result_type", "result_margin", "target_runs", "target_overs", "is_super_over",
                     "is_dl_applied"]


def match_lookup(matches, dims) -> pd.DataFrame:
    """Every match with its surrogate key and the keys of its season, venue, teams and players."""
    team = dims["team"].set_index("canonical_name")["team_key"]
    m = matches.sort_values(["match_date", "match_id"]).reset_index(drop=True)
    return pd.DataFrame({
        "match_key": range(1, len(m) + 1),
        "source_match_id": m["match_id"].astype(int),
        "season_key": m["season_year"].map(dims["season"].set_index("year")["season_key"]),
        "match_date": m["match_date"],
        "venue_key": m["venue"].map(dims["venue"].set_index("canonical_name")["venue_key"]),
        "team1_key": m["team1"].map(team),
        "team2_key": m["team2"].map(team),
        "toss_winner_key": m["toss_winner"].map(team),
        "toss_decision": m["toss_decision"],
        "match_status": m["match_status"],
        "result_type": m["result_type"],
        "result_margin": m["result_margin"],
        "target_runs": m["target_runs"],
        "target_overs": m["target_overs"],
        "is_super_over": m["is_super_over"],
        "is_dl_applied": m["is_dl_applied"],
        "player_of_match_key": m["player_of_match"].map(
            dims["player"].set_index("canonical_name")["player_key"]),
    })


# ------------------------------------------------------------------ E8 fact_delivery

def phase_of(over: pd.Series) -> pd.Series:
    out = pd.Series(pd.NA, index=over.index, dtype="Int64")
    for key, _, start, end in PHASES:
        out[(over >= start) & (over <= end)] = key
    return out


def fact_delivery(deliveries, dims) -> pd.DataFrame:
    team = dims["team"].set_index("canonical_name")["team_key"]
    player = dims["player"].set_index("canonical_name")["player_key"]
    match = dims["match"].set_index("source_match_id")[["match_key", "season_key", "venue_key", "match_date"]]
    d = deliveries
    f = pd.DataFrame({
        "match_key": d["match_id"].map(match["match_key"]),
        "date_key": date_key(d["match_id"].map(match["match_date"])),
        "season_key": d["match_id"].map(match["season_key"]),
        "venue_key": d["match_id"].map(match["venue_key"]),
        "inning": d["inning"],
        "delivery_seq": d["delivery_seq"],
        "batting_team_key": d["batting_team"].map(team),
        "bowling_team_key": d["bowling_team"].map(team),
        "batter_key": d["batter"].map(player),
        "bowler_key": d["bowler"].map(player),
        "non_striker_key": d["non_striker"].map(player),
        "player_dismissed_key": d["player_dismissed"].map(player),
        "fielder_key": d["fielder"].map(player),
        "phase_key": phase_of(d["over"]).where(d["is_super_over_innings"] == 0),
    })
    for col in ("over", "ball", "batsman_runs", "extra_runs", "total_runs", "extras_type", "is_wicket",
                "dismissal_kind", "is_super_over_innings", "is_legal_for_bowler", "is_faced_by_batter",
                "is_boundary", "is_dot"):
        f[col] = d[col]
    return f.sort_values(["match_key", "inning", "delivery_seq"]).reset_index(drop=True)


# ------------------------------------------------------------------ E9 aggregates

def _innings_stats(fd: pd.DataFrame) -> pd.DataFrame:
    reg = fd[fd.is_super_over_innings == 0]
    pp = reg.phase_key == 1
    g = reg.assign(
        pp_runs=reg.total_runs.where(pp, 0), pp_wickets=reg.is_wicket.where(pp, 0),
        pp_legal=reg.is_legal_for_bowler.where(pp, 0), pp_boundaries=reg.is_boundary.where(pp, 0),
        pp_dots=reg.is_dot.where(pp, 0),
    ).groupby(["match_key", "inning"]).agg(
        pp_runs=("pp_runs", "sum"), pp_wickets=("pp_wickets", "sum"),
        pp_legal_balls=("pp_legal", "sum"), pp_boundaries=("pp_boundaries", "sum"),
        pp_dots=("pp_dots", "sum"), total_runs=("total_runs", "sum"), wickets=("is_wicket", "sum"),
        legal_balls=("is_legal_for_bowler", "sum"), batting_team_key=("batting_team_key", "first"),
    ).reset_index()
    g["pp_dot_pct"] = _rate(g.pp_dots, g.pp_legal_balls, 100)
    g["pp_run_rate"] = _rate(g.pp_runs, g.pp_legal_balls, 6)
    return g.drop(columns="pp_dots")


def fact_match_summary(matches, dims, fd) -> pd.DataFrame:
    dm = dims["match"]
    team = dims["team"].set_index("canonical_name")["team_key"]
    src = matches.set_index("match_id")
    winner = dm["source_match_id"].map(src["winner"]).map(team)
    inn = _innings_stats(fd)
    out = dm[["match_key", "season_key", "venue_key", "toss_winner_key", "toss_decision",
              "match_status", "result_type", "is_super_over", "is_dl_applied",
              "team1_key", "team2_key", "player_of_match_key"]].copy()
    out["date_key"] = date_key(dm["match_date"])
    out["winner_key"] = winner.astype("Int64")

    stat_cols = ["pp_runs", "pp_wickets", "pp_legal_balls", "pp_boundaries", "pp_dot_pct",
                 "pp_run_rate", "total_runs", "wickets", "legal_balls"]
    for i in (1, 2):
        part = inn[inn.inning == i].set_index("match_key")
        for c in stat_cols:
            out[f"inn{i}_{c}"] = out["match_key"].map(part[c])
        out[f"inn{i}_team"] = out["match_key"].map(part["batting_team_key"])

    # Batting-first team from innings 1; without deliveries, infer from the toss.
    other = np.where(out.toss_winner_key == out.team1_key, out.team2_key, out.team1_key)
    from_toss = np.where(out.toss_decision == "bat", out.toss_winner_key, other)
    out["bat_first_team_key"] = out["inn1_team"].fillna(pd.Series(from_toss, index=out.index)).astype(int)
    out["chase_team_key"] = np.where(out.bat_first_team_key == out.team1_key, out.team2_key, out.team1_key)
    out["toss_winner_bat_first"] = (out.toss_winner_key == out.bat_first_team_key).astype(int)
    out["bat_first_won"] = (out.winner_key == out.bat_first_team_key).astype("Int64").where(
        out.winner_key.notna())
    out["ml_eligible"] = (
        (out.match_status == "completed") & (out.is_super_over == 0) & (out.is_dl_applied == 0)
        & out.winner_key.notna() & out.inn1_legal_balls.notna() & out.inn2_legal_balls.notna()
    ).astype(int)
    cols = ["match_key", "date_key", "season_key", "venue_key", "bat_first_team_key", "chase_team_key",
            "toss_winner_key", "toss_decision", "toss_winner_bat_first"]
    cols += [f"inn{i}_{c}" for i in (1, 2) for c in
             ("pp_runs", "pp_wickets", "pp_legal_balls", "pp_boundaries", "pp_dot_pct", "pp_run_rate",
              "total_runs", "wickets", "legal_balls")]
    cols += ["winner_key", "player_of_match_key", "result_type", "match_status", "bat_first_won", "ml_eligible"]
    return out[cols]


def fact_player_season_phase(fd: pd.DataFrame, threshold: int = QUALIFY_BALLS) -> pd.DataFrame:
    reg = fd[fd.is_super_over_innings == 0].copy()
    keys = ["season_key", "phase_key"]

    reg["runs_conceded"] = reg.batsman_runs + reg.extra_runs.where(
        reg.extras_type.isin(["wides", "noballs"]), 0)
    reg["bowler_wicket"] = reg.dismissal_kind.isin(BOWLER_WICKET_KINDS).astype(int)
    reg["batter_dot"] = ((reg.is_faced_by_batter == 1) & (reg.batsman_runs == 0)).astype(int)

    bat = reg.groupby(["batter_key", *keys]).agg(
        balls=("is_faced_by_batter", "sum"), runs=("batsman_runs", "sum"),
        boundaries=("is_boundary", "sum"), dots=("batter_dot", "sum"),
    ).reset_index().rename(columns={"batter_key": "player_key"})
    outs = reg[reg.player_dismissed_key.notna() & ~reg.dismissal_kind.isin(NOT_OUT_KINDS)]
    outs = outs.groupby(["player_dismissed_key", *keys]).size().rename("wickets").reset_index()
    outs = outs.rename(columns={"player_dismissed_key": "player_key"}).astype({"player_key": int})
    bat = bat.merge(outs, on=["player_key", *keys], how="outer")
    bat["role_type"] = "batting"

    bowl = reg.groupby(["bowler_key", *keys]).agg(
        balls=("is_legal_for_bowler", "sum"), runs=("runs_conceded", "sum"),
        wickets=("bowler_wicket", "sum"), boundaries=("is_boundary", "sum"), dots=("is_dot", "sum"),
    ).reset_index().rename(columns={"bowler_key": "player_key"})
    bowl["role_type"] = "bowling"

    f = pd.concat([bat, bowl], ignore_index=True)
    f["player_key"] = f["player_key"].astype(int)

    # Complete grid: every phase for every player-season-role that has any balls.
    grid = f[["player_key", "season_key", "role_type"]].drop_duplicates().merge(
        pd.DataFrame({"phase_key": [p[0] for p in PHASES]}), how="cross")
    f = grid.merge(f, on=["player_key", "season_key", "role_type", "phase_key"], how="left")
    for c in ("balls", "runs", "wickets", "boundaries", "dots"):
        f[c] = f[c].fillna(0).astype(int)

    grp = ["player_key", "season_key", "role_type"]
    f["season_balls"] = f.groupby(grp)["balls"].transform("sum")
    f = f[f.season_balls > 0].copy()
    league = f.groupby(["season_key", "role_type", "phase_key"])["balls"].sum()
    league_share = league / league.groupby(level=["season_key", "role_type"]).transform("sum")
    f["phase_share"] = f.balls / f.season_balls
    f["league_phase_share"] = [league_share.get((s, r, p), np.nan) for s, r, p in
                               zip(f.season_key, f.role_type, f.phase_key)]
    f["phase_index"] = _rate(f.phase_share, f.league_phase_share, 1)
    f["phase_index"] = f["phase_index"].fillna(0.0)
    f["strike_rate"] = np.where(f.role_type == "batting", _rate(f.runs, f.balls, 100), np.nan)
    f["economy"] = np.where(f.role_type == "bowling", _rate(f.runs, f.balls, 6), np.nan)
    f["qualifies"] = (f.season_balls >= threshold).astype(int)

    # Primary phase: highest phase_index; ties broken by more balls, then earlier phase.
    ranked = f[f.qualifies == 1].sort_values(grp + ["phase_index", "balls", "phase_key"],
                                             ascending=[True, True, True, False, False, True])
    primary = ranked.drop_duplicates(grp).set_index(grp + ["phase_key"]).index
    f["is_primary_phase"] = f.set_index(grp + ["phase_key"]).index.isin(primary).astype(int)
    cols = ["player_key", "season_key", "role_type", "phase_key", "balls", "runs", "wickets",
            "boundaries", "dots", "strike_rate", "economy", "season_balls", "phase_share",
            "league_phase_share", "phase_index", "qualifies", "is_primary_phase"]
    return f[cols].sort_values(grp + ["phase_key"]).reset_index(drop=True)


def build(clean: CleanResult, threshold: int = QUALIFY_BALLS) -> dict[str, pd.DataFrame]:
    m, d = clean.matches, clean.deliveries
    dims = {
        "season": dim_season(m),
        "phase": dim_phase(),
        "team": dim_team(m, d, clean.team_map),
        "venue": dim_venue(m, clean.venue_map),
        "player": dim_player(m, d),
    }
    dims["match"] = match_lookup(m, dims)
    fd = fact_delivery(d, dims)
    return {
        "dim_date": dim_date(m),
        "dim_season": dims["season"],
        "dim_phase": dims["phase"],
        "dim_team": dims["team"],
        "dim_venue": dims["venue"],
        "dim_player": dims["player"],
        "dim_match": dims["match"][DIM_MATCH_COLUMNS],
        "fact_delivery": fd,
        "fact_match_summary": fact_match_summary(m, dims, fd),
        "fact_player_season_phase": fact_player_season_phase(fd, threshold),
    }
