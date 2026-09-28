"""Phase 5: answers to the analysis questions of section 10.

    python -m src.analysis      # after the pipeline; writes data/export/analysis/

Each function returns a DataFrame computed from the warehouse; `run` also
draws the figures used in the report and the dashboard.
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from . import charts
from .config import PROJECT_ROOT, Paths
from .export import read_table
from .load import connect

PP_DIFF_BINS = [-np.inf, -3, -1.5, -0.5, 0.5, 1.5, 3, np.inf]
PP_DIFF_LABELS = ["< -3", "-3 to -1.5", "-1.5 to -0.5", "-0.5 to 0.5", "0.5 to 1.5", "1.5 to 3", "> 3"]


# ---------------------------------------------------------------- Q1 drift

def drift_summary(drift: pd.DataFrame, sensitivity: pd.DataFrame) -> pd.DataFrame:
    """Q1: how many players changed primary phase, by role and threshold."""
    counts = drift.groupby("role_type").agg(phase_changes=("player", "size"),
                                            players_who_changed=("player", "nunique"))
    moves = drift.groupby(["role_type", "from_phase", "to_phase"]).size().rename("n").reset_index()
    out = sensitivity.merge(counts.reset_index(), on="role_type", how="left", suffixes=("", "_table"))
    return out.drop(columns=[c for c in out.columns if c.endswith("_table")]), moves


def worked_examples(drift: pd.DataFrame, n: int = 3) -> pd.DataFrame:
    """Q1: the clearest changes - largest rise of the new phase's index across the change."""
    d = drift.assign(index_shift=drift.to_phase_index_after - drift.to_phase_index_before)
    return d.sort_values("index_shift", ascending=False).head(n).reset_index(drop=True)


# ---------------------------------------------------------------- Q2-Q4

def league_phase_rates(conn) -> pd.DataFrame:
    """Q2: league run rate by season and phase."""
    return read_table(conn, "v_league_phase_rates").sort_values(["season", "phase_key"])


def team_phase_profile(conn) -> pd.DataFrame:
    """Q3: team x season x phase run rate and wickets (by franchise)."""
    return read_table(conn, "v_team_phase_profile")


def venue_profile(conn, min_matches: int = 10) -> pd.DataFrame:
    """Q4: venues ranked by average first-innings score (venues with enough matches)."""
    v = read_table(conn, "v_venue_profile")
    return v[v.matches >= min_matches].sort_values("avg_first_innings", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------- Q5 toss

def _chi2(table: pd.DataFrame) -> tuple[float, float, int]:
    if table.shape != (2, 2) or (table.values.sum(axis=0) == 0).any() or (table.values.sum(axis=1) == 0).any():
        return np.nan, np.nan, 0
    chi2, p, dof, _ = stats.chi2_contingency(table.values)
    return float(chi2), float(p), int(dof)


def toss_matches(conn) -> pd.DataFrame:
    return pd.read_sql("""
        SELECT s.match_key, v.canonical_name AS venue, s.toss_decision,
               CASE WHEN s.winner_key = s.toss_winner_key THEN 1 ELSE 0 END AS toss_winner_won
        FROM fact_match_summary s JOIN dim_venue v USING (venue_key)
        WHERE s.winner_key IS NOT NULL""", conn)


def toss_effect(conn, min_matches: int = 20) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Q5: does the toss decision relate to the toss winner winning? Overall and by venue.

    Chi-square test of independence on the 2x2 table decision (bat/field) x toss winner won (yes/no).
    """
    m = toss_matches(conn)
    overall = m.groupby("toss_decision").toss_winner_won.agg(matches="size", toss_winner_won="sum")
    overall["win_pct"] = (100 * overall.toss_winner_won / overall.matches).round(1)
    table = pd.crosstab(m.toss_decision, m.toss_winner_won)
    chi2, p, dof = _chi2(table)
    overall = overall.reset_index().assign(chi2=round(chi2, 3), p_value=round(p, 4), dof=dof,
                                           total_matches=len(m),
                                           overall_toss_winner_win_pct=round(100 * m.toss_winner_won.mean(), 1))
    rows = []
    for venue, g in m.groupby("venue"):
        if len(g) < min_matches:
            continue
        chi2, p, _ = _chi2(pd.crosstab(g.toss_decision, g.toss_winner_won))
        rows.append({"venue": venue, "matches": len(g),
                     "pct_chose_field": round(100 * (g.toss_decision == "field").mean(), 1),
                     "toss_winner_win_pct": round(100 * g.toss_winner_won.mean(), 1),
                     "chi2": round(chi2, 3), "p_value": round(p, 4)})
    by_venue = pd.DataFrame(rows, columns=["venue", "matches", "pct_chose_field", "toss_winner_win_pct",
                                           "chi2", "p_value"])
    return overall, by_venue.sort_values("matches", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------- Q6 Powerplay

def powerplay_matches(conn) -> pd.DataFrame:
    df = pd.read_sql("""SELECT match_key, inn1_pp_run_rate, inn2_pp_run_rate, inn1_pp_wickets,
                               inn2_pp_wickets, bat_first_won
                        FROM fact_match_summary WHERE ml_eligible = 1""", conn)
    df["pp_rr_diff"] = df.inn1_pp_run_rate - df.inn2_pp_run_rate
    return df


def powerplay_vs_result(conn) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Q6: correlation of Powerplay measures with the result, and win rate by PP run-rate difference."""
    df = powerplay_matches(conn)
    rows = []
    for col in ("inn1_pp_run_rate", "inn1_pp_wickets", "pp_rr_diff"):
        ok = df[[col, "bat_first_won"]].dropna()
        if len(ok) > 2 and ok[col].std() > 0:
            r, p = stats.pointbiserialr(ok.bat_first_won, ok[col])
        else:
            r, p = np.nan, np.nan
        rows.append({"measure": col, "matches": len(ok), "point_biserial_r": round(r, 3),
                     "p_value": round(p, 4)})
    corr = pd.DataFrame(rows)
    df["pp_rr_diff_band"] = pd.cut(df.pp_rr_diff, PP_DIFF_BINS, labels=PP_DIFF_LABELS)
    grouped = df.groupby("pp_rr_diff_band", observed=False).bat_first_won.agg(matches="size", wins="sum")
    grouped["bat_first_win_pct"] = (100 * grouped.wins / grouped.matches.replace(0, np.nan)).round(1)
    higher = df[df.pp_rr_diff != 0]
    rule_acc = ((higher.pp_rr_diff > 0).astype(int) == higher.bat_first_won).mean() if len(higher) else np.nan
    corr["higher_pp_rate_wins_pct"] = round(100 * rule_acc, 1)
    return corr, grouped.reset_index()


# ---------------------------------------------------------------- figures

def fig_league_rates(rates: pd.DataFrame, path: Path) -> None:
    fig, ax = charts.plt.subplots(figsize=(8, 4.2))
    for phase, g in rates.groupby("phase_name", sort=False):
        c = charts.PHASE_COLORS.get(phase, charts.BLUE)
        ax.plot(g.season, g.run_rate, color=c, marker="o", label=phase)
        ax.annotate(phase, (g.season.iloc[-1], g.run_rate.iloc[-1]), xytext=(6, 0),
                    textcoords="offset points", va="center", color=charts.TEXT, fontsize=9)
    ax.set_title("League run rate by phase and season")
    ax.set_xlabel("Season")
    ax.set_ylabel("Runs per over")
    ax.xaxis.get_major_locator().set_params(integer=True)
    ax.margins(x=0.08)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncols=3)
    charts.save(fig, path)


def fig_team_heatmap(profile: pd.DataFrame, phase: str, path: Path) -> None:
    p = profile[profile.phase_name == phase].pivot(index="franchise_id", columns="season",
                                                   values="batting_run_rate")
    fig, ax = charts.plt.subplots(figsize=(max(6, 0.55 * p.shape[1] + 2), 0.4 * p.shape[0] + 1.6))
    ax.grid(False)
    im = ax.imshow(p.values, cmap=charts.SEQUENTIAL, aspect="auto")
    ax.set_xticks(range(p.shape[1]), p.columns, rotation=45 if p.shape[1] > 8 else 0)
    ax.set_yticks(range(p.shape[0]), p.index)
    ax.set_title(f"{phase} batting run rate by franchise and season")
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cb.set_label("Runs per over", color=charts.TEXT_2)
    cb.outline.set_visible(False)
    charts.save(fig, path)


def fig_venues(venues: pd.DataFrame, path: Path, top: int = 15) -> None:
    v = venues.head(top).iloc[::-1]
    fig, ax = charts.plt.subplots(figsize=(8, 0.35 * len(v) + 1.4))
    ax.barh(v.venue, v.avg_first_innings, color=charts.BLUE, height=0.7)
    ax.grid(axis="y", visible=False)
    for y, (val, n) in enumerate(zip(v.avg_first_innings, v.matches)):
        ax.text(val, y, f" {val:.0f} ({n})", va="center", color=charts.TEXT_2, fontsize=8)
    ax.set_title("Average first-innings score by venue (matches)")
    ax.set_xlabel("Runs")
    charts.save(fig, path)


def fig_powerplay(grouped: pd.DataFrame, path: Path) -> None:
    fig, ax = charts.plt.subplots(figsize=(8, 4.2))
    x = np.arange(len(grouped))
    ax.bar(x, grouped.bat_first_win_pct.fillna(0), color=charts.BLUE, width=0.7)
    ax.axhline(50, color=charts.TEXT_2, linewidth=1, linestyle="--")
    for i, (pct, n) in enumerate(zip(grouped.bat_first_win_pct, grouped.matches)):
        if n:
            ax.text(i, pct, f"{pct:.0f}%\nn={n}", ha="center", va="bottom", color=charts.TEXT_2, fontsize=8)
    ax.set_xticks(x, grouped.pp_rr_diff_band.astype(str))
    ax.set_ylim(0, 110)
    ax.grid(axis="x", visible=False)
    ax.set_title("Batting-first win rate by Powerplay run-rate difference")
    ax.set_xlabel("Batting-first PP run rate minus chasing PP run rate")
    ax.set_ylabel("Batting-first team won (%)")
    charts.save(fig, path)


# ---------------------------------------------------------------- run

def run(paths: Paths) -> dict[str, pd.DataFrame]:
    out = paths.export / "analysis"
    figs = out / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    charts.style()
    conn = connect(paths.db)
    try:
        drift = pd.read_csv(paths.export / "drift_table.csv")
        sens = pd.read_csv(paths.export / "drift_sensitivity.csv")
        summary, moves = drift_summary(drift, sens)
        rates = league_phase_rates(conn)
        teams = team_phase_profile(conn)
        venues = venue_profile(conn)
        toss_overall, toss_venue = toss_effect(conn)
        pp_corr, pp_grouped = powerplay_vs_result(conn)
    finally:
        conn.close()
    results = {
        "q1_drift_summary": summary, "q1_drift_moves": moves, "q1_worked_examples": worked_examples(drift),
        "q2_league_phase_rates": rates, "q3_team_phase_profile": teams, "q4_venue_profile": venues,
        "q5_toss_overall": toss_overall, "q5_toss_by_venue": toss_venue,
        "q6_powerplay_correlation": pp_corr, "q6_powerplay_win_rate": pp_grouped,
    }
    for name, df in results.items():
        df.to_csv(out / f"{name}.csv", index=False)
    fig_league_rates(rates, figs / "q2_league_phase_rates.png")
    for phase in ("Powerplay", "Death"):
        fig_team_heatmap(teams, phase, figs / f"q3_team_{phase.lower()}_heatmap.png")
    if len(venues):
        fig_venues(venues, figs / "q4_venues.png")
    fig_powerplay(pp_grouped, figs / "q6_powerplay_win_rate.png")
    return results


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=PROJECT_ROOT)
    a = p.parse_args(argv)
    results = run(Paths(root=a.root))
    print(f"{len(results)} analysis tables written to {a.root / 'data' / 'export' / 'analysis'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
