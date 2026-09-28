"""IPL phase dashboard (deliverable D13). Reads only data/export/.

    streamlit run dashboard/app.py
    IPL_DW_EXPORT=/other/export streamlit run dashboard/app.py   # another export folder

Pages: 1 League overview, 2 Player phase drift, 3 Powerplay and outcome.
"""
from __future__ import annotations

import os
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
EXPORT = Path(os.environ.get("IPL_DW_EXPORT", ROOT / "data" / "export"))

PHASES = ["Powerplay", "Middle", "Death"]
PHASE_SCALE = alt.Scale(domain=PHASES, range=["#2a78d6", "#eb6834", "#1baf7a"])
BLUE = "#2a78d6"
PP_BANDS = [-np.inf, -3, -1.5, -0.5, 0.5, 1.5, 3, np.inf]
PP_LABELS = ["< -3", "-3 to -1.5", "-1.5 to -0.5", "-0.5 to 0.5", "0.5 to 1.5", "1.5 to 3", "> 3"]

st.set_page_config(page_title="IPL Phase Warehouse", layout="wide")


@st.cache_data
def load(name: str) -> pd.DataFrame:
    path = EXPORT / f"{name}.csv"
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def need(*names: str) -> bool:
    missing = [n for n in names if load(n).empty]
    if missing:
        st.error(f"Missing exports: {', '.join(missing)}. Run `python -m src.pipeline` "
                 "(and `python -m src.ml` for model results) first.")
    return not missing


def matches() -> pd.DataFrame:
    s, m, t, v, se = (load(n) for n in ("fact_match_summary", "dim_match", "dim_team", "dim_venue",
                                         "dim_season"))
    team = t.set_index("team_key")
    df = s.merge(m[["match_key", "source_match_id", "match_date"]], on="match_key")
    df["season"] = df.season_key.map(se.set_index("season_key").year)
    df["venue"] = df.venue_key.map(v.set_index("venue_key").canonical_name)
    for side, col in (("bat_first", "bat_first_team_key"), ("chase", "chase_team_key"),
                      ("winner", "winner_key")):
        df[f"{side}_franchise"] = df[col].map(team.franchise_id)
    df["toss_winner_won"] = (df.winner_key == df.toss_winner_key).astype(int).where(df.winner_key.notna())
    return df


def season_filter(df: pd.DataFrame, key: str) -> tuple[int, int]:
    lo, hi = int(df.season.min()), int(df.season.max())
    if lo == hi:
        return lo, hi
    return st.slider("Seasons", lo, hi, (lo, hi), key=key)


# ---------------------------------------------------------------- page 1

def page_league() -> None:
    if not need("fact_match_summary", "v_match_phase"):
        return
    mp, ms = load("v_match_phase"), matches()
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        lo, hi = season_filter(ms, "p1_season")
    with c2:
        team = st.selectbox("Team (franchise)", ["All"] + sorted(mp.franchise_id.unique()))
    with c3:
        venue = st.selectbox("Venue", ["All"] + sorted(mp.venue.unique()))
    mp = mp[mp.season.between(lo, hi)]
    ms = ms[ms.season.between(lo, hi)]
    if team != "All":
        mp = mp[mp.franchise_id == team]
        ms = ms[(ms.bat_first_franchise == team) | (ms.chase_franchise == team)]
    if venue != "All":
        mp, ms = mp[mp.venue == venue], ms[ms.venue == venue]
    if ms.empty:
        st.info("No matches for this selection.")
        return

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Matches", f"{len(ms):,}")
    k2.metric("Seasons", ms.season.nunique())
    k3.metric("Avg first-innings score", f"{ms.inn1_total_runs.mean():.0f}")
    k4.metric("Batting-first win rate", f"{100 * ms.bat_first_won.mean():.0f}%")

    rates = mp.groupby(["season", "phase_name"], as_index=False)[["runs", "legal_balls", "wickets"]].sum()
    rates["run_rate"] = (rates.runs * 6 / rates.legal_balls).round(2)
    hover = alt.selection_point(fields=["season"], nearest=True, on="pointerover", empty=False)
    base = alt.Chart(rates).encode(
        x=alt.X("season:O", title="Season", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("run_rate:Q", title="Runs per over", scale=alt.Scale(zero=False)),
        color=alt.Color("phase_name:N", scale=PHASE_SCALE, title="Phase", legend=alt.Legend(orient="top")))
    line = base.mark_line(strokeWidth=2) + base.mark_point(size=60, filled=True).encode(
        tooltip=["season", "phase_name", "run_rate", "wickets", "legal_balls"]).add_params(hover)
    rule = alt.Chart(rates).mark_rule(color="#8a8984").encode(x="season:O").transform_filter(hover)
    st.subheader("Runs per over by phase")
    st.altair_chart((line + rule).properties(height=320), use_container_width=True)

    left, right = st.columns(2)
    long = pd.concat([ms[["season", "bat_first_franchise", "winner_franchise"]]
                      .rename(columns={"bat_first_franchise": "franchise"}),
                      ms[["season", "chase_franchise", "winner_franchise"]]
                      .rename(columns={"chase_franchise": "franchise"})])
    long = long[long.winner_franchise.notna()]
    wins = long.assign(won=long.franchise == long.winner_franchise).groupby("franchise", as_index=False).agg(
        matches=("won", "size"), wins=("won", "sum"))
    wins["win_pct"] = (100 * wins.wins / wins.matches).round(1)
    if team != "All":
        wins = wins[wins.franchise == team]
    with left:
        st.subheader("Team win percentage")
        st.altair_chart(alt.Chart(wins).mark_bar(color=BLUE, cornerRadiusEnd=4).encode(
            y=alt.Y("franchise:N", sort="-x", title=None), x=alt.X("win_pct:Q", title="Win %"),
            tooltip=["franchise", "matches", "wins", "win_pct"]), use_container_width=True)
    with right:
        per = ms.groupby("season", as_index=False).size().rename(columns={"size": "matches"})
        st.subheader("Matches per season")
        st.altair_chart(alt.Chart(per).mark_bar(color=BLUE, cornerRadiusEnd=4).encode(
            x=alt.X("season:O", title="Season", axis=alt.Axis(labelAngle=0)), y=alt.Y("matches:Q", title="Matches"),
            tooltip=["season", "matches"]), use_container_width=True)


# ---------------------------------------------------------------- page 2

def page_drift() -> None:
    if not need("v_player_phase_profile", "fact_player_season_phase", "dim_player", "drift_table"):
        return
    prof, fp, players, drift = (load(n) for n in ("v_player_phase_profile", "fact_player_season_phase",
                                                   "dim_player", "drift_table"))
    seasons, phases = load("dim_season"), load("dim_phase")
    fp = fp.assign(season=fp.season_key.map(seasons.set_index("season_key").year),
                   phase_name=fp.phase_key.map(phases.set_index("phase_key").phase_name),
                   player=fp.player_key.map(players.set_index("player_key").canonical_name))

    c1, c2, c3 = st.columns([1, 2, 2])
    with c1:
        role = st.radio("Role", ["batting", "bowling"], horizontal=True)
    changed = sorted(drift[drift.role_type == role].player.unique())
    options = changed + sorted(set(prof[prof.role_type == role].player) - set(changed))
    with c2:
        player = st.selectbox("Player (players who changed phase first)", options) if options else None
    with c3:
        lo, hi = season_filter(fp, "p2_season")
    if player is None:
        st.info("No qualifying players for this role.")
        return

    spells = prof[(prof.player == player) & (prof.role_type == role)].copy()
    last = int(fp.season.max())
    spells["end"] = spells.valid_to_season.fillna(spells.last_seen_season).astype(int) + 1
    st.subheader(f"{player}: primary-phase spells ({role})")
    spells["mid"] = (spells.valid_from_season + spells.end) / 2
    spells["label"] = spells.primary_phase + " " + spells.valid_from_season.astype(str) + "–" + (
        spells.end - 1).astype(str)
    x_scale = alt.Scale(domain=[min(lo, int(spells.valid_from_season.min())), max(hi, last) + 1])
    base = alt.Chart(spells)
    bars = base.mark_bar(cornerRadius=4, height=34).encode(
        x=alt.X("valid_from_season:Q", title="Season", scale=x_scale, axis=alt.Axis(format="d", tickMinStep=1)),
        x2="end:Q",
        color=alt.Color("primary_phase:N", scale=PHASE_SCALE, legend=None),
        tooltip=["primary_phase", "valid_from_season", "valid_to_season", "qualifying_seasons",
                 alt.Tooltip("phase_index_value:Q", format=".2f"), "is_current"])
    text = base.mark_text(color="white", fontWeight="bold").encode(x="mid:Q", text="label:N")
    st.altair_chart((bars + text).properties(height=60), use_container_width=True)

    idx = fp[(fp.player == player) & (fp.role_type == role) & fp.season.between(lo, hi)]
    st.subheader("Phase index by season (1.0 = league average share)")
    chart = alt.Chart(idx).encode(
        x=alt.X("season:O", title="Season", axis=alt.Axis(labelAngle=0)), y=alt.Y("phase_index:Q", title="Phase index"),
        color=alt.Color("phase_name:N", scale=PHASE_SCALE, title="Phase", legend=alt.Legend(orient="top")),
        tooltip=["season", "phase_name", alt.Tooltip("phase_index:Q", format=".2f"), "balls",
                 "season_balls", "qualifies"])
    one = alt.Chart(pd.DataFrame({"y": [1.0]})).mark_rule(strokeDash=[4, 4], color="#8a8984").encode(y="y:Q")
    st.altair_chart((chart.mark_line(strokeWidth=2) + chart.mark_point(size=60, filled=True) + one)
                    .properties(height=300), use_container_width=True)

    st.subheader("Players who changed primary phase")
    d = drift[(drift.role_type == role) & drift.to_season.between(lo, hi)]
    st.dataframe(d.drop(columns=["player_key", "role_type"]), use_container_width=True, hide_index=True)


# ---------------------------------------------------------------- page 3

def page_powerplay() -> None:
    if not need("fact_match_summary"):
        return
    ms = matches()
    ms = ms[ms.ml_eligible == 1].copy()
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        lo, hi = season_filter(ms, "p3_season")
    with c2:
        venue = st.selectbox("Venue", ["All"] + sorted(ms.venue.unique()), key="p3_venue")
    with c3:
        toss = st.selectbox("Toss decision", ["All", "bat", "field"])
    ms = ms[ms.season.between(lo, hi)]
    if venue != "All":
        ms = ms[ms.venue == venue]
    if toss != "All":
        ms = ms[ms.toss_decision == toss]
    if ms.empty:
        st.info("No matches for this selection.")
        return

    ms["pp_rr_diff"] = ms.inn1_pp_run_rate - ms.inn2_pp_run_rate
    ms["band"] = pd.cut(ms.pp_rr_diff, PP_BANDS, labels=PP_LABELS).astype(str)
    g = ms.groupby("band", as_index=False).agg(matches=("bat_first_won", "size"), wins=("bat_first_won", "sum"))
    g["win_pct"] = (100 * g.wins / g.matches).round(1)
    left, right = st.columns(2)
    with left:
        st.subheader("Batting-first win rate by Powerplay run-rate difference")
        bars = alt.Chart(g).mark_bar(color=BLUE, cornerRadiusEnd=4).encode(
            x=alt.X("band:N", sort=PP_LABELS, title="Batting-first PP rate minus chasing PP rate",
                    axis=alt.Axis(labelAngle=0)),
            y=alt.Y("win_pct:Q", title="Batting-first won (%)", scale=alt.Scale(domain=[0, 100])),
            tooltip=["band", "matches", "wins", "win_pct"])
        half = alt.Chart(pd.DataFrame({"y": [50]})).mark_rule(strokeDash=[4, 4], color="#8a8984").encode(y="y:Q")
        st.altair_chart((bars + half).properties(height=320), use_container_width=True)
    with right:
        st.subheader("First-innings Powerplay run rate vs first-innings total")
        st.altair_chart(alt.Chart(ms).mark_circle(size=60, opacity=0.6, color=BLUE).encode(
            x=alt.X("inn1_pp_run_rate:Q", title="Powerplay run rate", scale=alt.Scale(zero=False)),
            y=alt.Y("inn1_total_runs:Q", title="First-innings total", scale=alt.Scale(zero=False)),
            tooltip=["source_match_id", "season", "venue", "inn1_pp_run_rate", "inn1_total_runs",
                     "bat_first_won"]).properties(height=320), use_container_width=True)

    st.subheader("Venues")
    v = ms.groupby("venue", as_index=False).agg(
        matches=("match_key", "size"), avg_first_innings=("inn1_total_runs", "mean"),
        avg_pp_run_rate=("inn1_pp_run_rate", "mean"), bat_first_win_pct=("bat_first_won", "mean"))
    v["bat_first_win_pct"] = (100 * v.bat_first_win_pct).round(1)
    st.dataframe(v.round(2).sort_values("matches", ascending=False), use_container_width=True, hide_index=True)

    metrics = load("ml/metrics")
    st.subheader("Model comparison (test seasons)")
    if metrics.empty:
        st.info("Run `python -m src.ml` to add model results.")
        return
    test = metrics[metrics.split == "test"]
    st.dataframe(test[["feature_set", "model", "params", "n", "accuracy", "precision", "recall", "f1",
                       "roc_auc"]].round(3), use_container_width=True, hide_index=True)
    choice = st.selectbox("Confusion matrix for", [f"{r.feature_set} | {r.model}" for r in test.itertuples()])
    fs, model = choice.split(" | ")
    r = test[(test.feature_set == fs) & (test.model == model)].iloc[0]
    cm = pd.DataFrame({"actual": ["chase won", "chase won", "bat first won", "bat first won"],
                       "predicted": ["chase won", "bat first won", "chase won", "bat first won"],
                       "matches": [r.tn, r.fp, r.fn, r.tp]})
    heat = alt.Chart(cm).encode(x=alt.X("predicted:N", title="Predicted"), y=alt.Y("actual:N", title="Actual"))
    st.altair_chart((heat.mark_rect(stroke="white", strokeWidth=2).encode(
        color=alt.Color("matches:Q", scale=alt.Scale(range=["#cde2fb", "#184f95"]), legend=None),
        tooltip=["actual", "predicted", "matches"])
        + heat.mark_text(fontSize=16).encode(
            text="matches:Q",
            color=alt.condition(alt.datum.matches > cm.matches.max() / 2, alt.value("white"), alt.value("black"))))
        .properties(width=320, height=220))


PAGES = {"1. League overview": page_league, "2. Player phase drift": page_drift,
         "3. Powerplay and outcome": page_powerplay}
st.sidebar.title("IPL Phase Warehouse")
page = st.sidebar.radio("Page", list(PAGES))
st.sidebar.caption(f"Data: {EXPORT}")
st.title(page.split(". ", 1)[1])
PAGES[page]()
