"""Draw previews of the three report pages from the generated project and its data.

    python dashboard/preview_pages.py

Positions, titles and subtitles are read from the visual.json files, and every chart is drawn from
the project CSVs with the report's default slicer state (all seasons; batting, AT Rayudu; feature
set B, logistic regression). Also flags text that is likely to overflow its box.
Output: dashboard/previews/page_1_league.png ... page_3_model.png
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

HERE = Path(__file__).resolve().parent
PROJ = HERE / "IPL_Scorebook"
DATA = PROJ / "data"
OUTDIR = HERE / "previews"
OUTDIR.mkdir(exist_ok=True)
PAGES = PROJ / "IPL_Scorebook.Report/definition/pages"

INK, MUTED, SOFT, RULE, PAPER = "#1B1F24", "#6E6A62", "#3D3A35", "#CFC7B6", "#F4F1EA"
PP, MID, DEATH, OCHRE, GREY = "#C8553D", "#2E6F95", "#2F5D50", "#D9A23B", "#B9B2A3"
PH = {"Powerplay": PP, "Middle": MID, "Death": DEATH}
SERIF, SANS = "DejaVu Serif", "DejaVu Sans"
MS = {"baseline_majority": "Majority class", "baseline_pp_rate_above_train_median": "Rule: PP rate > median", "baseline_higher_pp_rate_wins": "Rule: higher PP rate", "logistic_regression": "Logistic regression", "decision_tree": "Decision tree", "random_forest": "Random forest"}
W, H, S = 1280, 720, 1.5  # S: preview pixels per canvas pixel
PT = 96 / 72  # Power BI font points to canvas pixels
warnings: list[str] = []

T = {f.stem: pd.read_csv(f) for f in DATA.glob("*.csv")}
season = T["Season"].set_index("season_key")["season"]
phase = T["Phase"].set_index("phase_key")["phase"]


def lit(o):
    return o["expr"]["Literal"]["Value"].strip("'").replace("''", "'")


def load(page: str) -> dict[str, dict]:
    out = {}
    for f in (PAGES / page / "visuals").glob("*/visual.json"):
        v = json.loads(f.read_text(encoding="utf-8"))
        out[v["name"]] = v
    return out


class Canvas:
    def __init__(self, page):
        self.v = load(page)
        self.fig = plt.figure(figsize=(W * S / 100, H * S / 100), dpi=100)
        self.fig.patch.set_facecolor(PAPER)
        self.ren = self.fig.canvas.get_renderer()

    def fx(self, x):
        return x / W

    def fy(self, y):
        return 1 - y / H

    def text(self, x, y, w, h, s, size, color=INK, font=SANS, weight="normal", style="normal", name=""):
        """Wrap text into the box by measuring it; record overflow."""
        fs = size * PT * S * 0.72  # matplotlib points at this dpi
        words, lines, cur = s.split(), [], ""
        for wd in words:
            trial = (cur + " " + wd).strip()
            t = self.fig.text(0, 0, trial, fontsize=fs, family=font, weight=weight, style=style)
            width = t.get_window_extent(self.ren).width / S
            t.remove()
            if width > w and cur:
                lines.append(cur)
                cur = wd
            else:
                cur = trial
        lines.append(cur)
        line_h = size * PT * 1.32
        if len(lines) * line_h > h + 2:
            warnings.append(f"{name}: {len(lines)} lines need {len(lines) * line_h:.0f}px, box is {h}px")
        for i, ln in enumerate(lines):
            self.fig.text(self.fx(x), self.fy(y + size * PT + i * line_h), ln, fontsize=fs, family=font,
                          color=color, weight=weight, style=style, va="baseline")

    def frame(self, name, title=True):
        v = self.v[name]
        p = v["position"]
        vco = v["visual"].get("visualContainerObjects", {})
        top = p["y"]
        if title:
            t = vco.get("title", [{}])[0].get("properties", {})
            st = vco.get("subTitle", [{}])[0].get("properties", {})
            if "text" in t:
                self.text(p["x"], top, p["width"], 23, lit(t["text"]), 13, INK, SERIF, name=name + " title")
                top += 20
            if "text" in st:
                self.text(p["x"], top, p["width"], 14, lit(st["text"]), 9, MUTED, name=name + " subtitle")
                top += 16
        ax = self.fig.add_axes([self.fx(p["x"]), self.fy(p["y"] + p["height"]), p["width"] / W,
                                (p["y"] + p["height"] - top - 4) / H])
        ax.set_facecolor(PAPER)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.tick_params(colors=MUTED, labelsize=7.5 * S * 0.72 * PT, length=0)
        return ax, p

    def rules(self):
        for name, v in self.v.items():
            bg = v["visual"].get("visualContainerObjects", {}).get("background", [{}])[0].get("properties", {})
            if v["visual"]["visualType"] == "textbox" and bg.get("show", {}).get("expr", {}).get("Literal", {}).get("Value") == "true":
                p = v["position"]
                c = lit(bg["color"]["solid"]["color"])
                self.fig.patches.append(Rectangle((self.fx(p["x"]), self.fy(p["y"] + p["height"])), p["width"] / W,
                                                  max(p["height"], 1) / H, transform=self.fig.transFigure, color=c))

    def textboxes(self):
        for name, v in self.v.items():
            if v["visual"]["visualType"] != "textbox":
                continue
            paras = v["visual"]["objects"]["general"][0]["properties"]["paragraphs"]
            r = paras[0]["textRuns"][0]
            if not r["value"]:
                continue
            st = r["textStyle"]
            p = v["position"]
            self.text(p["x"], p["y"], p["width"], p["height"], r["value"], float(st["fontSize"][:-2]), st["color"],
                      SERIF if st["fontFamily"] == "Georgia" else SANS, "bold" if st.get("fontWeight") else "normal",
                      name=name)

    def cards(self, values: dict[str, str]):
        for name, v in self.v.items():
            if v["visual"]["visualType"] != "card":
                continue
            p = v["position"]
            proj = v["visual"]["query"]["queryState"]["Values"]["projections"][0]
            col = lit(v["visual"]["objects"]["labels"][0]["properties"]["color"]["solid"]["color"])
            self.fig.text(self.fx(p["x"] + p["width"] / 2), self.fy(p["y"] + 38), values[name], fontsize=30 * PT * S * 0.72,
                          family=SERIF, color=col, ha="center", va="baseline")
            self.text(p["x"] + 10, p["y"] + 44, p["width"] - 20, 16, proj["displayName"], 9, MUTED, name=name)

    def nav_and_slicers(self, slicer_text: dict[str, str]):
        for name, v in self.v.items():
            vt = v["visual"]["visualType"]
            p = v["position"]
            if vt == "actionButton":
                t = v["visual"]["objects"]["text"][0]["properties"]
                cur = t["bold"]["expr"]["Literal"]["Value"] == "true"
                self.fig.text(self.fx(p["x"] + p["width"] / 2), self.fy(p["y"] + 16), lit(t["text"]),
                              fontsize=9 * PT * S * 0.72, family=SANS, ha="center", color=INK if cur else MUTED,
                              weight="bold" if cur else "normal")
                if cur:
                    self.fig.patches.append(Rectangle((self.fx(p["x"]), self.fy(p["y"] + p["height"])), p["width"] / W,
                                                      p["height"] / H, transform=self.fig.transFigure, fill=False,
                                                      ec=INK, lw=0.8))
            if vt == "slicer":
                hdr = lit(v["visual"]["objects"]["header"][0]["properties"]["text"])
                self.fig.text(self.fx(p["x"]), self.fy(p["y"] + 12), hdr, fontsize=9 * PT * S * 0.72, family=SANS,
                              color=MUTED)
                self.fig.patches.append(Rectangle((self.fx(p["x"]), self.fy(p["y"] + p["height"] - 4)), p["width"] / W,
                                                  (p["height"] - 22) / H, transform=self.fig.transFigure,
                                                  fc="#FBF8F2", ec=RULE, lw=0.8))
                self.fig.text(self.fx(p["x"] + 8), self.fy(p["y"] + 36), slicer_text[name],
                              fontsize=9.5 * PT * S * 0.72, family=SANS, color=INK, va="center", linespacing=1.6)

    def save(self, fname):
        self.fig.savefig(OUTDIR / fname, facecolor=PAPER)
        plt.close(self.fig)


def bars_h(ax, labels, values, colors, fmt, size=8):
    y = np.arange(len(labels))[::-1]
    ax.barh(y, values, color=colors, height=0.62)
    ax.set_yticks(y, labels)
    ax.set_xticks([])
    mx = max(values) if len(values) else 1
    for yy, v in zip(y, values):
        ax.text(v + mx * 0.01, yy, fmt(v), va="center", fontsize=size * PT * S * 0.72, color=INK, family=SANS)
    ax.set_xlim(0, mx * 1.18)


def cols_v(ax, labels, values, colors, fmt, size=7):
    x = np.arange(len(labels))
    ax.bar(x, values, color=colors, width=0.7)
    ax.set_xticks(x, labels)
    ax.set_yticks([])
    mx = np.nanmax(values)
    for xx, v in zip(x, values):
        ax.text(xx, v + mx * 0.02, fmt(v), ha="center", fontsize=size * PT * S * 0.72, color=INK, family=SANS)
    ax.set_ylim(0, mx * 1.2)


def legend(ax, items):
    for i, (lab, c) in enumerate(items):
        ax.text(0.0 + i * 0.2, 1.02, "● " + lab, transform=ax.transAxes, color=c, fontsize=8 * PT * S * 0.72,
                family=SANS, va="bottom")


def table(ax, header, rows, colw, cell_colors=None, size=8.5):
    ax.axis("off")
    n = len(rows)
    rh = 1 / (n + 1.4)
    x = 0
    for j, (h, w) in enumerate(zip(header, colw)):
        ax.text(x, 1 - rh * 0.6, h, fontsize=size * PT * S * 0.72 * 0.92, color=MUTED, family=SANS, va="center",
                transform=ax.transAxes)
        x += w
    ax.plot([0, 1], [1 - rh * 1.15] * 2, color=INK, lw=0.8, transform=ax.transAxes)
    for i, r in enumerate(rows):
        yy = 1 - rh * (i + 1.75)
        x = 0
        for j, (val, w) in enumerate(zip(r, colw)):
            if cell_colors and cell_colors[i][j]:
                ax.add_patch(Rectangle((x - 0.01, yy - rh * 0.45), w, rh * 0.9, color=cell_colors[i][j],
                                       transform=ax.transAxes))
                c = "#FFFFFF"
            else:
                c = INK
            ax.text(x, yy, str(val), fontsize=size * PT * S * 0.72, color=c, family=SANS, va="center",
                    transform=ax.transAxes)
            x += w
        ax.plot([0, 1], [yy - rh * 0.5] * 2, color="#DDD6C8", lw=0.5, transform=ax.transAxes)


def heat(ax, mat, rlabels, clabels, lo, hi, fmt, size=8, row_w=0.18):
    ax.axis("off")
    nr, nc = mat.shape
    vmin, vmax = np.nanmin(mat), np.nanmax(mat)
    c0, c1 = np.array(matplotlib.colors.to_rgb(lo)), np.array(matplotlib.colors.to_rgb(hi))
    cw = (1 - row_w) / nc
    rh = 1 / (nr + 1)
    for j, cl in enumerate(clabels):
        ax.text(row_w + (j + 0.5) * cw, 1 - rh * 0.5, cl, ha="center", va="center", fontsize=size * PT * S * 0.72 * 0.9,
                color=MUTED, family=SANS, transform=ax.transAxes)
    for i, rl in enumerate(rlabels):
        yy = 1 - rh * (i + 1.5)
        ax.text(0, yy, rl, va="center", fontsize=size * PT * S * 0.72, color=INK, family=SANS, transform=ax.transAxes)
        for j in range(nc):
            v = mat[i, j]
            if np.isnan(v):
                continue
            t = (v - vmin) / (vmax - vmin) if vmax > vmin else 0
            ax.add_patch(Rectangle((row_w + j * cw, yy - rh / 2), cw, rh, color=c0 + (c1 - c0) * t,
                                   transform=ax.transAxes))
            ax.text(row_w + (j + 0.5) * cw, yy, fmt(v), ha="center", va="center",
                    fontsize=size * PT * S * 0.72 * 0.9, color=INK, family=SANS, transform=ax.transAxes)


# ------------------------------------------------------------------ page 1
def page1():
    c = Canvas("p1_league")
    c.rules()
    c.textboxes()
    ip = T["InningsPhase"].assign(season=lambda d: d.season_key.map(season), phase=lambda d: d.phase_key.map(phase))
    m = T["Matches"].assign(season=lambda d: d.season_key.map(season))
    g = ip.groupby(["season", "phase"])[["runs", "legal_balls", "boundaries", "balls_faced", "dots"]].sum()
    rr = (g.runs * 6 / g.legal_balls).unstack()
    pp = g.xs("Powerplay", level="phase")
    toss = m.dropna(subset=["toss_winner_won"]).groupby("toss_decision").toss_winner_won.mean()
    n200 = m.assign(n=(m.inn1_total_runs >= 200).astype(int) + (m.inn2_total_runs >= 200).astype(int)).groupby("season").n.sum()
    c.cards({"stat_1": f"{rr.loc[2024, 'Powerplay']:.2f}",
             "stat_2": f"+{100 * (rr.loc[2024, 'Powerplay'] / rr.loc[2008, 'Powerplay'] - 1):.0f}%",
             "stat_3": f"{n200[2024]}", "stat_4": f"{100 * m.toss_winner_won.mean():.1f}%"})
    c.nav_and_slicers({"slicer_season": "2008  —  2024", "slicer_country": "☐ India\n☐ South Africa\n☐ UAE"})

    ax, _ = c.frame("main_runrate")
    for ph in ("Powerplay", "Middle", "Death"):
        ax.plot(rr.index, rr[ph], color=PH[ph], lw=2.4)
    legend(ax, [(k, v) for k, v in PH.items()])
    ax.grid(axis="y", color="#DDD6C8", lw=0.6)
    ax.set_xticks(range(2008, 2025, 2))

    ax, _ = c.frame("pp_detail")
    ax.plot(pp.index, pp.boundaries / pp.balls_faced, color=PP, lw=1.8)
    ax.plot(pp.index, pp.dots / pp.legal_balls, color=GREY, lw=1.8)
    legend(ax, [("Balls hit for 4 or 6", PP), ("Dot balls", GREY)])
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, 0))
    ax.grid(axis="y", color="#DDD6C8", lw=0.6)

    ax, _ = c.frame("toss")
    t = toss.sort_values(ascending=False)
    bars_h(ax, t.index.tolist(), t.values, [PP if i == "field" else GREY for i in t.index], lambda v: f"{100 * v:.1f}%", 9)

    ax, _ = c.frame("big_totals")
    cols_v(ax, [str(s)[2:] for s in n200.index], n200.values, [PP if s >= 2023 else GREY for s in n200.index], str)

    ax, _ = c.frame("bowl_first")
    f = m.groupby("season").toss_decision.apply(lambda s: (s == "field").mean())
    cols_v(ax, [str(s)[2:] for s in f.index], f.values, SOFT, lambda v: f"{100 * v:.0f}%")

    ax, _ = c.frame("grounds")
    comp = m[m.match_status == "completed"].merge(T["Venue"], on="venue_key")
    v = comp.groupby("venue_short").inn1_total_runs.agg(["mean", "size"])
    v = v[v["size"] >= 10].sort_values("mean", ascending=False).head(7)
    bars_h(ax, v.index.tolist(), v["mean"].values, SOFT, lambda x: f"{x:.0f}")
    c.save("page_1_league.png")


# ------------------------------------------------------------------ page 2
def page2():
    c = Canvas("p2_players")
    c.rules()
    c.textboxes()
    who, role = "AT Rayudu", "batting"
    sp, ch, psp = T["PhaseSpells"], T["PhaseChanges"], T["PlayerSeasonPhase"]
    spr = sp[sp.role_type == role]
    agg = spr.groupby("player_key").agg(q=("qualifying_seasons", "sum"), n=("profile_key", "size"))
    pool, changed = int((agg.q >= 2).sum()), int((agg.n > 1).sum())
    c.cards({"stat_1": f"{pool}", "stat_2": f"{changed}", "stat_3": f"{100 * changed / pool:.0f}%",
             "stat_4": f"{(ch.role_type == role).sum()}"})
    c.nav_and_slicers({"slicer_role": "● batting\n○ bowling", "slicer_player": f"{who}  ▾"})

    ax, _ = c.frame("balls_by_phase")
    d = psp[(psp.player == who) & (psp.role_type == role)].assign(season=lambda x: x.season_key.map(season),
                                                                   phase=lambda x: x.phase_key.map(phase))
    sh = d.pivot_table(index="season", columns="phase", values="balls", aggfunc="sum").fillna(0)
    sh = sh.div(sh.sum(axis=1), axis=0)
    bottom = np.zeros(len(sh))
    x = np.arange(len(sh))
    for ph in ("Powerplay", "Middle", "Death"):
        vals = sh.get(ph, pd.Series(0, index=sh.index)).values
        ax.bar(x, vals, bottom=bottom, color=PH[ph], width=0.72)
        for xx, b, vv in zip(x, bottom, vals):
            if vv > 0.08:
                ax.text(xx, b + vv / 2, f"{100 * vv:.0f}%", ha="center", va="center", color="white",
                        fontsize=6.5 * PT * S * 0.72, family=SANS)
        bottom += vals
    ax.set_xticks(x, [str(s)[2:] for s in sh.index])
    ax.set_yticks([])
    legend(ax, [(k, v) for k, v in PH.items()])

    ax, _ = c.frame("restless")
    top = spr.groupby("player").agg(n=("profile_key", "size"), q=("qualifying_seasons", "sum")).sort_values(
        ["n", "q"], ascending=False).head(9)
    table(ax, ["Player", "Spells", "Seasons"], [[i, r.n, r.q] for i, r in top.iterrows()], [0.6, 0.2, 0.2])

    ax, _ = c.frame("spells")
    s = spr[spr.player == who].sort_values("valid_from_season")
    rows = [[r.valid_from_season, r.last_seen_season, r.primary_phase, r.qualifying_seasons, f"{r.phase_index_value:.2f}",
             r.spell_status] for r in s.itertuples()]
    table(ax, ["From", "Last seen", "Primary phase", "Seasons", "Index", "Row"], rows[:9],
          [0.14, 0.16, 0.26, 0.14, 0.13, 0.17], [[None, None, PH[r[2]], None, None, None] for r in rows[:9]], 8)

    ax, _ = c.frame("moves")
    chr_ = ch[ch.role_type == role]
    mt = chr_.pivot_table(index="from_phase", columns="to_phase", values="player", aggfunc="count")
    order = ["Powerplay", "Middle", "Death"]
    mt = mt.reindex(index=order, columns=order)
    heat(ax, mt.values.astype(float), order, order, PAPER, "#8FB3CC", lambda v: f"{v:.0f}", 10, 0.3)

    ax, _ = c.frame("franchise_heat")
    ip = T["InningsPhase"].assign(season=lambda d: d.season_key.map(season))
    fr = T["Franchise"]
    act = fr[fr.active == 1].set_index("franchise_id")["latest_name"]
    g = ip[ip.batting_franchise.isin(act.index)].groupby(["batting_franchise", "season"])[["runs", "legal_balls"]].sum()
    r = (g.runs * 6 / g.legal_balls).unstack()
    r.index = r.index.map(act)
    r = r.sort_index()
    heat(ax, r.values, ["⊞ " + i for i in r.index], [str(s)[2:] for s in r.columns], PAPER, "#D9806B",
         lambda v: f"{v:.1f}", 7.5, 0.2)
    c.save("page_2_players.png")


# ------------------------------------------------------------------ page 3
def page3():
    c = Canvas("p3_model")
    c.rules()
    c.textboxes()
    mm, tp, fi, mo = T["ModelMetrics"], T["TestPredictions"], T["FeatureImportance"], T["MLModel"]
    B, LR = "B", "logistic_regression"
    sel = tp[(tp.feature_set == B) & (tp.model == LR)]
    hit = sel.correct.mean()
    auc = mm[(mm.feature_set == B) & (mm.model == LR)].roc_auc.iloc[0]
    base = mm[(mm.feature_set == B) & (mm.is_baseline == 1) & (mm.model != "baseline_majority")].accuracy.iloc[0]
    c.cards({"stat_1": f"{100 * hit:.1f}%", "stat_2": f"{auc:.2f}", "stat_3": f"{100 * base:.1f}%",
             "stat_4": f"+{100 * (hit - base):.1f} pts"})
    c.nav_and_slicers({"slicer_set": "○ A: after the 1st-innings Powerplay\n● B: after both Powerplays",
                       "slicer_model": "Logistic regression ▾"})

    ax, _ = c.frame("every_model")
    b = mm[mm.feature_set == B].sort_values("accuracy", ascending=False)
    colors = [INK if mdl == LR else ("#D8D2C4" if base_ == 1 else "#A9A294") for mdl, base_ in zip(b.model, b.is_baseline)]
    bars_h(ax, b.model.map(MS).tolist(), b.accuracy.values, colors, lambda v: f"{100 * v:.1f}%")

    ax, _ = c.frame("pp_gap")
    m = T["Matches"]
    e = m[m.ml_eligible == 1].groupby(["pp_diff_band_order", "pp_diff_band"]).bat_first_won.mean().reset_index()
    cols_v(ax, e.pp_diff_band.tolist(), e.bat_first_won.values, SOFT, lambda v: f"{100 * v:.0f}%", 8)
    ax.axhline(0.5, color=MUTED, ls="--", lw=0.8)

    ax, _ = c.frame("scatter")
    for lab, col_ in (("Bat first won", INK), ("Chase won", OCHRE)):
        d = sel[sel.actual_label == lab]
        ax.scatter(d.pp_run_rate_diff, d.prob_bat_first_wins, s=9, color=col_, alpha=0.75, lw=0)
    ax.axhline(0.5, color=MUTED, ls="--", lw=0.8)
    legend(ax, [("Bat first won", INK), ("Chase won", OCHRE)])
    ax.grid(color="#DDD6C8", lw=0.5)

    ax, _ = c.frame("confusion")
    cm = sel.pivot_table(index="actual_label", columns="predicted_label", values="match_key", aggfunc="count")
    heat(ax, cm.values.astype(float), cm.index.tolist(), cm.columns.tolist(), PAPER, "#8FB3CC", lambda v: f"{v:.0f}", 11,
         0.3)

    ax, _ = c.frame("chase_wickets")
    w = m[m.chase_pp_wickets_band.notna()].groupby(["chase_pp_wickets_order", "chase_pp_wickets_band"]).bat_first_won.mean()
    w = (1 - w).reset_index()
    cols_v(ax, w.chase_pp_wickets_band.tolist(), w.bat_first_won.values, OCHRE, lambda v: f"{100 * v:.0f}%", 8)
    ax.axhline(0.5, color=MUTED, ls="--", lw=0.8)

    ax, _ = c.frame("importance")
    f = fi[(fi.feature_set == B) & (fi.model == "random_forest")].sort_values("abs_value", ascending=False).head(7)
    bars_h(ax, f.feature_label.tolist(), f.abs_value.values, SOFT, lambda v: f"{v:.3f}", 7)

    ax, _ = c.frame("misses")
    ms = sel[(sel.correct == 0) & (sel.confidence >= 0.7)].sort_values("match_date")
    table(ax, ["Date", "Batted first", "Winner", "P(bat 1st)"],
          [[r.match_date, r.bat_first_team[:20], r.winner_team[:20], f"{r.prob_bat_first_wins:.2f}"] for r in ms.head(8).itertuples()],
          [0.22, 0.33, 0.33, 0.12], size=7)
    c.save("page_3_model.png")
    return len(ms)


if __name__ == "__main__":
    page1()
    page2()
    n = page3()
    print(f"previews in {OUTDIR}; confident misses for LR/B: {n}")
    for w_ in warnings:
        print("TEXT:", w_)
