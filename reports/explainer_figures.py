"""Diagrams for the project explainer: pipeline layers with code locations, and attribute lineage.

    python reports/explainer_figures.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(exist_ok=True)
INK, MUTED, EDGE = "#1A2B4C", "#4b5563", "#1A2B4C"
FILL, FILL2, FILL3 = "#DCE6F5", "#f3f4f6", "#fde8d8"
plt.rcParams.update({"font.family": "DejaVu Sans"})


def box(ax, x, y, w, h, fill, lw=1.0):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.08",
                                fc=fill, ec=EDGE, lw=lw))


def arrow(ax, a, b, label=None, color=INK, rad=0.0, lw=1.2, label_xy=None):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=11, color=color, lw=lw,
                                 connectionstyle=f"arc3,rad={rad}", shrinkA=2, shrinkB=2))
    if label:
        lx, ly = label_xy or ((a[0] + b[0]) / 2 + 0.12, (a[1] + b[1]) / 2)
        ax.text(lx, ly, label, fontsize=7.6, color=MUTED, va="center")


# ---------------------------------------------------------------- figure 1: pipeline layers
def pipeline():
    layers = [
        ("RAW FILES", "data/raw/matches.csv (1,095 x 20)\ndata/raw/deliveries.csv (260,920 x 17)",
         "Kaggle download\n(notebook section 1)", FILL2),
        ("STAGING", "stg_matches, stg_deliveries\nall columns TEXT + source_row",
         "E1-E2  src/extract.py\nsha256(), register(), stage()", FILL),
        ("PROFILING", "logs/profiling_report.csv\nlogs/data_quality_findings.csv",
         "E3  src/profiling.py\ncolumn_profile(), quality_findings()", FILL2),
        ("CLEAN", "clean_matches, clean_deliveries\nmap_team, map_venue, map_player, cleaning_log",
         "E4-E6  src/clean.py + mappings/*.csv\nnullify(), normalise_*(), canonical_*()", FILL),
        ("WAREHOUSE", "7 dimensions, 3 fact tables\nSCD2 dim_player_phase_profile, 6 views",
         "E7-E10  src/transform.py, src/scd2.py\nsrc/load.py + sql/ddl.sql, sql/views.sql", FILL),
        ("VALIDATION", "gates G1-G9 (stop the run on failure)\nlogs/validation_report.csv",
         "E11  src/validate.py\ng1() ... g9(), run_gates()", FILL3),
        ("EXPORTS", "data/export/*.csv (dims, facts, views)\nml_features.csv, drift_table.csv",
         "E12  src/export.py, src/features.py", FILL),
        ("USES", "insights | models | Power BI workbook\nnotebook, report, deck",
         "src/analysis.py, src/ml.py, src/powerbi.py\nnotebooks/, reports/", FILL2),
    ]
    fig, ax = plt.subplots(figsize=(10.8, 11.2))
    ax.set_xlim(0, 10.8)
    ax.set_ylim(0, 11.2)
    ax.axis("off")
    h, gap, top = 1.0, 0.32, 10.6
    for i, (name, tables, code, fill) in enumerate(layers):
        y = top - i * (h + gap) - h
        box(ax, 0.3, y, 10.3, h, fill, lw=1.6 if name in ("WAREHOUSE", "VALIDATION") else 1.0)
        ax.text(0.5, y + h / 2, name, fontsize=10.5, fontweight="bold", color=INK, va="center")
        ax.text(2.15, y + h / 2, tables, fontsize=8.4, color="#111827", va="center", linespacing=1.4)
        ax.plot([6.3, 6.3], [y + 0.12, y + h - 0.12], color=EDGE, lw=0.6)
        ax.text(6.42, y + h / 2, code, fontsize=7.9, color=INK, va="center", family="DejaVu Sans Mono",
                linespacing=1.4)
        if i < len(layers) - 1:
            arrow(ax, (1.3, y), (1.3, y - gap))
    ax.text(0.3, 10.85, "Pipeline layers (left), what each holds (middle) and the code that builds it (right)",
            fontsize=10, color=INK, fontweight="bold")
    ax.text(0.3, 0.12, "Everything from STAGING to EXPORTS runs in order from src/pipeline.py run(); "
            "db/ipl_dw.sqlite holds the staging, clean and warehouse layers.", fontsize=8.4, color=MUTED)
    fig.savefig(OUT / "explainer_pipeline.png", dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------- figure 2: attribute lineage
def lineage():
    fig, ax = plt.subplots(figsize=(12, 8.6))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8.6)
    ax.axis("off")
    cols = [(0.2, 2.35, "Clean columns\n(fact_delivery, dim_match)"),
            (3.05, 2.6, "Derived per-ball / per-match\nattributes"),
            (6.25, 2.85, "Aggregated measures\n(table or view)"),
            (9.65, 2.15, "Insight")]
    for x, w, title in cols:
        ax.text(x + w / 2, 8.25, title, ha="center", va="center", fontsize=9.6, fontweight="bold", color=INK)

    def node(x, w, y, text, fill, h=0.56, fs=8.0):
        box(ax, x, y - h / 2, w, h, fill)
        ax.text(x + w / 2, y, text, ha="center", va="center", fontsize=fs, color="#111827", linespacing=1.25)
        return {"l": (x, y), "r": (x + w, y)}

    c1x, c1w = cols[0][0], cols[0][1]
    c2x, c2w = cols[1][0], cols[1][1]
    c3x, c3w = cols[2][0], cols[2][1]
    c4x, c4w = cols[3][0], cols[3][1]
    A = {
        "over": node(c1x, c1w, 7.45, "over (1-20)", FILL2),
        "extras": node(c1x, c1w, 6.65, "extras_type", FILL2),
        "bruns": node(c1x, c1w, 5.85, "batsman_runs, total_runs", FILL2),
        "wkt": node(c1x, c1w, 5.05, "is_wicket, dismissal_kind", FILL2),
        "who": node(c1x, c1w, 4.25, "batter_key, bowler_key,\nseason_key", FILL2),
        "toss": node(c1x, c1w, 2.75, "toss_winner_key,\ntoss_decision", FILL2),
        "win": node(c1x, c1w, 1.85, "winner_key", FILL2),
        "inn": node(c1x, c1w, 0.95, "inning, batting_team_key", FILL2),
    }
    B = {
        "phase": node(c2x, c2w, 7.45, "phase_key\n1-6 PP, 7-15 Mid, 16-20 Death", FILL),
        "legal": node(c2x, c2w, 6.65, "is_legal_for_bowler\nis_faced_by_batter", FILL),
        "bnd": node(c2x, c2w, 5.85, "is_boundary (4 or 6)\nis_dot (legal, 0 runs)", FILL),
        "bf": node(c2x, c2w, 1.45, "bat_first_team_key\n(batting team of innings 1)", FILL),
        "tww": node(c2x, c2w, 2.75, "toss_winner_won\n(winner = toss winner)", FILL),
        "bfw": node(c2x, c2w, 0.55, "bat_first_won\n(winner = bat-first team)", FILL),
    }
    C = {
        "rr": node(c3x, c3w, 7.15, "run_rate = runs x 6 / legal balls\nboundary %, dot %\nv_league_phase_rates",
                   FILL3, h=0.82),
        "share": node(c3x, c3w, 5.55, "phase_share -> phase_index\n-> is_primary_phase\nfact_player_season_phase",
                      FILL3, h=0.82),
        "spell": node(c3x, c3w, 4.25, "spells, valid_from / valid_to\ndim_player_phase_profile", FILL3, h=0.7),
        "pp": node(c3x, c3w, 2.05, "inn1 / inn2 pp_run_rate, pp_wickets\npp_rr_diff = inn1 - inn2\nfact_match_summary",
                   FILL3, h=0.82),
    }
    D = {
        "i1": node(c4x, c4w, 7.15, "1. Powerplay boom", "#ffffff", h=0.6, fs=8.8),
        "i4": node(c4x, c4w, 4.9, "4. Phase drift", "#ffffff", h=0.6, fs=8.8),
        "i2": node(c4x, c4w, 2.05, "2. Powerplay vs result", "#ffffff", h=0.6, fs=8.8),
        "i3": node(c4x, c4w, 3.2, "3. Toss decision", "#ffffff", h=0.6, fs=8.8),
        "ml": node(c4x, c4w, 0.85, "ML target and\nfeatures", "#ffffff", h=0.6, fs=8.8),
    }
    links = [
        (A["over"], B["phase"]), (A["extras"], B["legal"]), (A["bruns"], B["bnd"]),
        (A["toss"], B["tww"]), (A["win"], B["tww"]), (A["inn"], B["bf"]), (A["win"], B["bfw"]),
        (B["phase"], C["rr"]), (B["legal"], C["rr"]), (B["bnd"], C["rr"]),
        (B["phase"], C["share"]), (B["legal"], C["share"]), (A["who"], C["share"]),
        (B["phase"], C["pp"]), (B["legal"], C["pp"]), (A["wkt"], C["pp"]), (B["bf"], C["pp"]),
        (C["share"], C["spell"]), (B["bf"], B["bfw"]),
        (C["rr"], D["i1"]), (C["spell"], D["i4"]), (C["pp"], D["i2"]), (B["bfw"], D["i2"]),
        (B["tww"], D["i3"]), (C["pp"], D["ml"]), (B["bfw"], D["ml"]),
    ]
    for a, b in links:
        if a is C["share"] and b is C["spell"]:
            arrow(ax, (c3x + c3w / 2, 5.14), (c3x + c3w / 2, 4.6), lw=0.9)
        elif a is B["bf"] and b is B["bfw"]:
            arrow(ax, (c2x + c2w / 2, 1.17), (c2x + c2w / 2, 0.83), lw=0.9)
        else:
            arrow(ax, a["r"], b["l"], lw=0.75, color="#374151")
    ax.text(0.2, 0.05, "Boxes on the left are columns after cleaning; each arrow is a computation in "
            "src/clean.py, src/transform.py, src/scd2.py, sql/views.sql or src/analysis.py.",
            fontsize=8.2, color=MUTED)
    fig.savefig(OUT / "explainer_lineage.png", dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    pipeline()
    lineage()
    print("wrote explainer_pipeline.png, explainer_lineage.png")
