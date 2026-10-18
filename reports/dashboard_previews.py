"""Layout previews of the three Power BI report pages, drawn from the Power BI workbook's CSVs.

    python reports/dashboard_previews.py

These are the visual specification used in docs/PowerBI_Build_Guide.docx: every visual
on them is listed there with its fields and measures. Replace them with screenshots of the
built .pbix once it exists.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "data" / "export" / "powerbi" / "csv"
OUT = ROOT / "reports" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

BG, CARD, EDGE, INK, MUTED = "#f3f2f1", "#ffffff", "#e1dfdd", "#252423", "#605e5c"
BLUE, DARK, ORANGE, PURPLE, PINK = "#118dff", "#12239e", "#e66c37", "#6b007b", "#e044a7"
PHASE = {"Powerplay": BLUE, "Middle": ORANGE, "Death": DARK}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.edgecolor": EDGE,
                     "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False})

T = {n: pd.read_csv(CSV / f"{n}.csv") for n in (
    "Season", "Phase", "Venue", "Matches", "TeamMatches", "InningsPhase", "PlayerSeasonPhase",
    "PhaseSpells", "PhaseChanges", "ModelMetrics", "TestPredictions", "FeatureImportance")}


def page(title, subtitle):
    fig = plt.figure(figsize=(16, 9), dpi=110)
    fig.patch.set_facecolor(BG)
    fig.text(0.015, 0.955, title, fontsize=19, fontweight="bold", color=INK, va="center")
    fig.text(0.015, 0.918, subtitle, fontsize=10, color=MUTED, va="center")
    fig.text(0.985, 0.012, "Layout preview drawn from IPL_PowerBI_Data.xlsx", fontsize=7, color=MUTED, ha="right")
    return fig


def card(fig, x, y, w, h, title=None):
    fig.patches.append(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.004",
                                      transform=fig.transFigure, fc=CARD, ec=EDGE, lw=0.8, zorder=-5))
    if title:
        fig.text(x + 0.008, y + h - 0.022, title, fontsize=9.5, fontweight="bold", color=INK, va="center")


def kpi(fig, x, y, w, h, label, value, note=""):
    card(fig, x, y, w, h)
    fig.text(x + w / 2, y + h * 0.58, value, fontsize=22, fontweight="bold", color=INK, ha="center", va="center")
    fig.text(x + w / 2, y + h * 0.24, label, fontsize=8.5, color=MUTED, ha="center", va="center")
    if note:
        fig.text(x + w / 2, y + h * 0.09, note, fontsize=7, color=MUTED, ha="center", va="center")


def axes(fig, x, y, w, h, title, left=0.035):
    card(fig, x, y, w, h, title)
    ax = fig.add_axes([x + left, y + 0.05, w - left - 0.015, h - 0.105])
    ax.set_zorder(5)
    ax.set_facecolor(CARD)
    ax.grid(axis="y", color="#edebe9", lw=0.6)
    ax.set_axisbelow(True)
    return ax


def slicer_panel(fig, items, x=0.012, y=0.06, w=0.135, h=0.83):
    card(fig, x, y, w, h)
    fig.text(x + 0.01, y + h - 0.025, "Filters", fontsize=10, fontweight="bold", color=INK)
    yy = y + h - 0.075
    for label, value, kind in items:
        fig.text(x + 0.01, yy, label, fontsize=8.5, fontweight="bold", color=INK)
        if kind == "slider":
            fig.lines.append(plt.Line2D([x + 0.015, x + w - 0.015], [yy - 0.035, yy - 0.035],
                                        transform=fig.transFigure, color=BLUE, lw=3))
            for xx in (x + 0.015, x + w - 0.015):
                fig.patches.append(plt.Circle((xx, yy - 0.035), 0.005, transform=fig.transFigure, color=DARK))
            fig.text(x + 0.01, yy - 0.06, value, fontsize=7.5, color=MUTED)
            yy -= 0.11
        elif kind.startswith("buttons"):
            bx = x + 0.01
            for i, v in enumerate(value):
                bw = (w - 0.02) / len(value)
                fig.patches.append(FancyBboxPatch((bx + i * bw, yy - 0.05), bw - 0.003, 0.032,
                                                  boxstyle="round,pad=0,rounding_size=0.003",
                                                  transform=fig.transFigure,
                                                  fc=BLUE if (i == 0 and kind == "buttons") else CARD,
                                                  ec=BLUE, lw=0.8))
                fig.text(bx + i * bw + (bw - 0.003) / 2, yy - 0.034, v, fontsize=7, ha="center", va="center",
                         color="white" if (i == 0 and kind == "buttons") else BLUE)
            yy -= 0.1
        else:
            fig.patches.append(FancyBboxPatch((x + 0.01, yy - 0.05), w - 0.02, 0.032,
                                              boxstyle="round,pad=0,rounding_size=0.003",
                                              transform=fig.transFigure, fc=CARD, ec=EDGE, lw=0.8))
            fig.text(x + 0.016, yy - 0.034, value, fontsize=7.5, va="center", color=INK)
            fig.text(x + w - 0.018, yy - 0.034, "▾", fontsize=8, va="center", color=MUTED)
            yy -= 0.1
    return yy


def narrative(fig, x, y, w, h, text):
    card(fig, x, y, w, h, "What this page shows")
    fig.text(x + 0.008, y + h - 0.045, text, fontsize=8.3, color=INK, va="top", wrap=True)


# ---------------------------------------------------------------- page 1
def page1():
    S, M, IP, Ph, V = T["Season"], T["Matches"], T["InningsPhase"], T["Phase"], T["Venue"]
    fig = page("How the IPL changed, 2008–2024",
               "League overview · 1,095 matches · 260,920 balls · 17 seasons")
    slicer_panel(fig, [("Season", "2008 – 2024", "slider"),
                       ("Country", ["India", "UAE", "S. Africa"], "buttons-none"), ("Venue", "All", "drop")])
    ip = IP.merge(S, on="season_key").merge(Ph, on="phase_key")
    comp = M[M.match_status == "completed"]
    pp = ip[ip.phase == "Powerplay"].groupby("season")[["runs", "legal_balls"]].sum()
    pprr = pp.runs * 6 / pp.legal_balls
    x0, w = 0.158, 0.205
    kpi(fig, x0, 0.76, 0.19, 0.13, "Matches", f"{len(M):,}")
    kpi(fig, x0 + w, 0.76, 0.19, 0.13, "Avg first-innings score", f"{comp.inn1_total_runs.mean():.0f}",
        "completed matches")
    kpi(fig, x0 + 2 * w, 0.76, 0.19, 0.13, "Powerplay run rate, 2024", f"{pprr[2024]:.2f}",
        f"{pprr[2008]:.2f} in 2008 (+{100 * (pprr[2024] / pprr[2008] - 1):.0f}%)")
    kpi(fig, x0 + 3 * w, 0.76, 0.19, 0.13, "Toss winner win %", f"{100 * M.toss_winner_won.mean():.1f}%",
        "a coin flip")

    ax = axes(fig, 0.158, 0.36, 0.5, 0.385, "Run rate by phase and season")
    g = ip.groupby(["season", "phase"])[["runs", "legal_balls"]].sum()
    rr = (g.runs * 6 / g.legal_balls).unstack()
    for ph in ("Powerplay", "Middle", "Death"):
        ax.plot(rr.index, rr[ph], marker="o", ms=3, lw=2, color=PHASE[ph], label=ph)
    ax.axvspan(2022.5, 2024.5, color="#f3f2f1", zorder=0)
    ax.text(2023.5, 6.85, "Impact\nPlayer era", ha="center", fontsize=7, color=MUTED)
    ax.set_ylim(6.6, 11.6)
    ax.set_xticks(range(2008, 2025, 2))
    ax.set_ylabel("Runs per over")
    ax.legend(ncol=3, frameon=False, loc="upper left", fontsize=8)

    ax = axes(fig, 0.668, 0.36, 0.32, 0.385, "Toss winner win % by decision")
    t = M.dropna(subset=["toss_winner_won"]).groupby("toss_decision").toss_winner_won.agg(["mean", "size"])
    bars = ax.bar(["Chose to bat", "Chose to field"], 100 * t["mean"], color=[ORANGE, BLUE], width=0.55)
    for b, (_, r) in zip(bars, t.iterrows()):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() - 2, f"{100 * r['mean']:.1f}%\n{int(r['size'])} matches",
                ha="center", va="top", fontsize=8.5, color="white", fontweight="bold")
    ax.axhline(50, ls="--", color=MUTED, lw=0.8)
    ax.set_ylim(0, 70)
    ax.set_ylabel("Toss winner won (%)")

    ax = axes(fig, 0.158, 0.06, 0.5, 0.285, "Average first-innings score by venue (10+ matches)", left=0.15)
    vv = comp.merge(V, on="venue_key").groupby("venue_short").inn1_total_runs.agg(["mean", "size"])
    vv = vv[vv["size"] >= 10].sort_values("mean").tail(8)
    ax.barh(vv.index, vv["mean"], color=BLUE, height=0.6)
    for i, (m, n) in enumerate(zip(vv["mean"], vv["size"])):
        ax.text(m + 1, i, f"{m:.0f}  ({n})", va="center", fontsize=7.5, color=INK)
    ax.set_xlim(0, 215)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color="#edebe9", lw=0.6)
    ax.tick_params(axis="y", labelsize=7.5)

    narrative(fig, 0.668, 0.06, 0.32, 0.285,
              "Scoring has risen in every phase, but the Powerplay\nchanged most: +23% since 2008 and +21% in the\n"
              "two Impact Player seasons alone.\n\nWinning the toss does not win matches (50.8%), but\n"
              "toss winners who chose to field won 53.9% against\n45.4% for those who batted (chi-square p = 0.009).\n\n"
              "Use the season slider and the country or venue\nfilters to compare eras and grounds; team and\nplayer detail is on the next page.")
    fig.savefig(OUT / "dashboard_page1_overview.png", facecolor=BG)
    plt.close(fig)


# ---------------------------------------------------------------- page 2
def page2():
    S, IP, Ph = T["Season"], T["InningsPhase"], T["Phase"]
    psp, spells, ch = T["PlayerSeasonPhase"], T["PhaseSpells"], T["PhaseChanges"]
    who, role = "HH Pandya", "batting"
    fig = page("Teams and players: detail and drill-down",
               "Drill from franchise to phase · pick a player to see how his phase changed")
    slicer_panel(fig, [("Franchise", "All", "drop"), ("Role", ["Batting", "Bowling"], "buttons"),
                       ("Player", who, "drop"), ("Season", "2008 – 2024", "slider")])

    ax = axes(fig, 0.158, 0.47, 0.5, 0.42, "Batting run rate by franchise and season (\u229e drills a franchise into phases)",
              left=0.06)
    ip = IP.merge(S, on="season_key").merge(Ph, on="phase_key")
    active = ["CSK", "DEL", "GT", "KKR", "LSG", "MI"]
    seasons = list(range(2014, 2025))
    rows, labels = [], []
    for fr in active:
        d = ip[ip.batting_franchise == fr]
        g = d.groupby("season")[["runs", "legal_balls"]].sum()
        rows.append((g.runs * 6 / g.legal_balls).reindex(seasons))
        labels.append(("\u229f " if fr == "KKR" else "\u229e ") + fr)
        if fr == "KKR":   # one franchise shown expanded to its phases
            for ph in ("Powerplay", "Middle", "Death"):
                g = d[d.phase == ph].groupby("season")[["runs", "legal_balls"]].sum()
                rows.append((g.runs * 6 / g.legal_balls).reindex(seasons))
                labels.append("      " + ph)
    mat = np.vstack([r.values for r in rows])
    ax.imshow(mat, aspect="auto", cmap="Blues", vmin=6.5, vmax=12.5)
    for (i, j), v in np.ndenumerate(mat):
        if not np.isnan(v):
            ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=6.8, color="white" if v > 10.3 else INK)
    ax.set_xticks(range(len(seasons)), seasons, fontsize=7)
    ax.set_yticks(range(len(labels)), labels, fontsize=7.5)
    ax.grid(False)
    for s_ in ax.spines.values():
        s_.set_visible(False)

    ax = axes(fig, 0.668, 0.47, 0.32, 0.42, f"{who}: phase index by season ({role})")
    pp = psp[(psp.player == who) & (psp.role_type == role)].merge(S, on="season_key").merge(Ph, on="phase_key")
    for ph in ("Powerplay", "Middle", "Death"):
        d = pp[pp.phase == ph].sort_values("season")
        ax.plot(d.season, d.phase_index, marker="o", ms=3, color=PHASE[ph], label=ph)
    ax.axhline(1, ls="--", color=MUTED, lw=0.8)
    ax.text(pp.season.min(), 1.05, "league average = 1.0", fontsize=7, color=MUTED)
    ax.legend(frameon=False, fontsize=7.5, ncol=3, loc="lower right", bbox_to_anchor=(1.0, 1.0))
    ax.set_xticks(range(2015, 2025))
    ax.tick_params(axis="x", labelsize=7)
    ax.set_ylabel("Phase index")

    card(fig, 0.158, 0.06, 0.5, 0.39, f"Primary-phase spells (SCD Type 2): {who}, {role}")
    sp = spells[(spells.player == who) & (spells.role_type == role)].sort_values("valid_from_season")
    rows = [["Primary phase", "From", "To", "Qualifying seasons", "Current"]] + [
        [r.primary_phase, str(r.valid_from_season), "" if pd.isna(r.valid_to_season) else str(int(r.valid_to_season)),
         str(r.qualifying_seasons), "Yes" if r.is_current else ""] for r in sp.itertuples()]
    xs = [0.168, 0.29, 0.36, 0.43, 0.56]
    for i, row in enumerate(rows):
        y = 0.38 - i * 0.04
        for x, v in zip(xs, row):
            fig.text(x, y, v, fontsize=8.5, fontweight="bold" if i == 0 else "normal", color=INK)
        fig.lines.append(plt.Line2D([0.165, 0.65], [y - 0.012, y - 0.012], transform=fig.transFigure,
                                    color=EDGE, lw=0.6))
    fig.text(0.168, 0.09, "The Player slicer filters this table and the phase-index chart; clicking a heatmap cell cross-filters the page.", fontsize=7.5, color=MUTED)

    ax = axes(fig, 0.668, 0.06, 0.32, 0.39, f"Phase changes, all players ({role})", left=0.075)
    c = ch[ch.role_type == role].groupby(["from_phase", "to_phase"]).size().unstack(fill_value=0)
    order = ["Powerplay", "Middle", "Death"]
    c = c.reindex(index=order, columns=order, fill_value=0)
    ax.imshow(c.values, cmap="Oranges", vmin=0, vmax=c.values.max() * 1.4)
    for (i, j), v in np.ndenumerate(c.values):
        ax.text(j, i, "–" if i == j else str(v), ha="center", va="center", fontsize=10, color=INK)
    ax.set_xticks(range(3), [f"to {o}" for o in order], fontsize=7.5)
    ax.set_yticks(range(3), [f"from {o}" for o in order], fontsize=7.5)
    ax.grid(False)
    fig.savefig(OUT / "dashboard_page2_detail.png", facecolor=BG)
    plt.close(fig)


# ---------------------------------------------------------------- page 3
def page3():
    mm, pr, fi = T["ModelMetrics"], T["TestPredictions"], T["FeatureImportance"]
    fs, model = "B", "logistic_regression"
    fig = page("Can the Powerplay predict the winner?",
               "Model insights · test seasons 2023–2024 · models trained on 2008–2022 only")
    slicer_panel(fig, [("Prediction point", ["B: both PPs", "A: 1st PP"], "buttons"),
                       ("Model", "Logistic regression", "drop"), ("Season", "2023 – 2024", "slider")])
    b = mm[mm.feature_set == fs].set_index("model")
    p = pr[(pr.feature_set == fs) & (pr.model == model)]
    x0, w = 0.158, 0.205
    kpi(fig, x0, 0.76, 0.19, 0.13, "Test accuracy", f"{100 * b.loc[model, 'accuracy']:.1f}%")
    kpi(fig, x0 + w, 0.76, 0.19, 0.13, "ROC-AUC", f"{b.loc[model, 'roc_auc']:.2f}")
    kpi(fig, x0 + 2 * w, 0.76, 0.19, 0.13, "Rule: higher PP rate wins",
        f"{100 * b.loc['baseline_higher_pp_rate_wins', 'accuracy']:.1f}%", "baseline to beat")
    kpi(fig, x0 + 3 * w, 0.76, 0.19, 0.13, "Test matches", f"{p.match_key.nunique()}")

    ax = axes(fig, 0.158, 0.41, 0.36, 0.335, "Accuracy and ROC-AUC by model (Model B)", left=0.075)
    order = ["baseline_majority", "baseline_higher_pp_rate_wins", "decision_tree", "random_forest",
             "logistic_regression"]
    labels = ["Majority class", "Rule: higher PP", "Decision tree", "Random forest", "Logistic regr."]
    y = np.arange(len(order))
    ax.barh(y + 0.19, b.loc[order, "accuracy"], height=0.36, color=BLUE, label="Accuracy")
    ax.barh(y - 0.19, b.loc[order, "roc_auc"], height=0.36, color=DARK, label="ROC-AUC")
    for yi, a, r in zip(y, b.loc[order, "accuracy"], b.loc[order, "roc_auc"]):
        ax.text(a + 0.01, yi + 0.19, f"{a:.2f}", va="center", fontsize=7)
        ax.text(r + 0.01, yi - 0.19, f"{r:.2f}", va="center", fontsize=7)
    ax.set_yticks(y, labels, fontsize=7.5)
    ax.set_xlim(0, 0.95)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color="#edebe9", lw=0.6)
    ax.legend(frameon=False, fontsize=7.5, loc="lower right")

    card(fig, 0.524, 0.41, 0.2, 0.335, "Predicted vs actual")
    cm = pd.crosstab(p.actual_label, p.predicted_label).reindex(index=["Bat first won", "Chase won"],
                                                               columns=["Bat first wins", "Chase wins"])
    fig.text(0.62, 0.68, "Predicted", fontsize=8, color=MUTED, ha="center")
    for j, c in enumerate(cm.columns):
        fig.text(0.6 + j * 0.06, 0.65, c.replace(" wins", "\nwins"), fontsize=7.5, ha="center", va="center", color=INK)
    for i, r in enumerate(cm.index):
        fig.text(0.53, 0.58 - i * 0.09, r.replace(" won", "\nwon"), fontsize=7.5, va="center", color=INK)
        for j, c in enumerate(cm.columns):
            v = cm.loc[r, c]
            good = (i == j)
            fig.patches.append(FancyBboxPatch((0.575 + j * 0.06, 0.545 - i * 0.09), 0.052, 0.07,
                                              boxstyle="round,pad=0,rounding_size=0.003", transform=fig.transFigure,
                                              fc=BLUE if good else "#deecf9", ec="none"))
            fig.text(0.601 + j * 0.06, 0.58 - i * 0.09, str(v), fontsize=13, fontweight="bold", ha="center",
                     va="center", color="white" if good else INK)
    fig.text(0.53, 0.43, "Actual (rows) × predicted (columns)", fontsize=7, color=MUTED)

    ax = axes(fig, 0.734, 0.41, 0.254, 0.335, "Feature importance (random forest, B)", left=0.1)
    f = fi[(fi.feature_set == fs) & (fi.model == "random_forest")].nlargest(7, "value").iloc[::-1]
    ax.barh(f.feature.str.replace("_", " "), f.value, color=PURPLE, height=0.6)
    ax.tick_params(axis="y", labelsize=6.8)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color="#edebe9", lw=0.6)

    ax = axes(fig, 0.158, 0.06, 0.36, 0.335, "Predicted probability vs Powerplay run-rate difference")
    for ok, col, lab in ((1, BLUE, "Correct"), (0, PINK, "Wrong")):
        d = p[p.correct == ok]
        ax.scatter(d.pp_run_rate_diff, d.prob_bat_first_wins, s=12, color=col, alpha=0.75, label=lab)
    ax.axhline(0.5, ls="--", color=MUTED, lw=0.8)
    ax.axvline(0, ls=":", color=MUTED, lw=0.8)
    ax.set_xlabel("Batting-first PP run rate minus chasing PP run rate")
    ax.set_ylabel("P(batting first wins)")
    ax.legend(frameon=False, fontsize=7.5, loc="upper left")

    card(fig, 0.524, 0.06, 0.464, 0.335, "Confident wrong predictions (upsets, probability ≥ 0.70)")
    up = p[(p.correct == 0) & (p.confidence >= 0.7)].sort_values("confidence", ascending=False).head(6)
    cols = [("Date", 0.532), ("Batting first", 0.6), ("Chasing", 0.73), ("Winner", 0.84), ("P(bat 1st)", 0.94)]
    for k, (c, x) in enumerate(cols):
        fig.text(x, 0.335, c, fontsize=8, fontweight="bold", color=INK)
    for i, r in enumerate(up.itertuples()):
        y = 0.3 - i * 0.034
        vals = [r.match_date, r.bat_first_team, r.chase_team, r.winner_team, f"{r.prob_bat_first_wins:.2f}"]
        for (c, x), v in zip(cols, vals):
            fig.text(x, y, str(v)[:27], fontsize=7.4, color=INK)
    fig.text(0.532, 0.075, "Most of the signal is captured by one subtraction: the model beats the rule by "
             "about 1.4 points.\nThe chasing side's Powerplay wickets matter more than any run rate.",
             fontsize=7.8, color=MUTED)
    fig.savefig(OUT / "dashboard_page3_model.png", facecolor=BG)
    plt.close(fig)


if __name__ == "__main__":
    page1()
    page2()
    page3()
    print("wrote", ", ".join(p.name for p in sorted(OUT.glob("dashboard_page*.png"))))
