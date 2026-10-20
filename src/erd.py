"""ER diagram of the star schema (deliverable D6), drawn from docs/data_dictionary.csv.

    python -m src.dictionary && python -m src.erd

Writes docs/er_diagram_keys.png/.svg/.pdf. The three fact tables sit in the middle row with
their keys and measures; the eight dimensions sit around them with all their columns. There is
one line per fact-dimension pair: a crow's foot at the fact (many side) and a bar at the
dimension's primary key (one side). Role-playing dimensions (team, player) carry one line,
labelled with the roles, so the diagram shows every foreign key without a line per column.
"""
from __future__ import annotations

import textwrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from .config import PROJECT_ROOT  # noqa: E402

DOCS = PROJECT_ROOT / "docs"
FONT = "DejaVu Sans"
W, ROW, HEAD = 4.1, 0.31, 0.62
INK, GREY, LINE = "#111111", "#555555", "#2b2b2b"

# (x centre, top y) of every table
POS = {
    "dim_player_phase_profile": (2.6, 16.2),
    "fact_player_season_phase": (2.6, 10.6),
    "dim_player": (13.6, 16.2),
    "fact_delivery": (13.6, 13.0),
    "dim_season": (13.6, 4.6),
    "dim_phase": (8.1, 3.2),
    "dim_date": (19.9, 16.2),
    "dim_match": (19.9, 12.6),
    "dim_venue": (19.9, 8.1),
    "dim_team": (19.9, 6.0),
    "fact_match_summary": (26.0, 12.0),
}

# (fact, dimension): (fact side, dimension side, optional waypoints). Sides: L, R, T, B.
EDGES = {
    ("fact_player_season_phase", "dim_player_phase_profile"): ("L", "L", [(0.25, None), (0.25, "dst")]),
    ("fact_player_season_phase", "dim_player"): ("R", "L", [(6.4, None), (6.4, "dst")]),
    ("fact_player_season_phase", "dim_phase"): ("R", "L", [(5.3, None), (5.3, "dst")]),
    ("fact_player_season_phase", "dim_season"): ("R", "L", [(7.3, None), (7.3, "dst")]),
    ("fact_delivery", "dim_player"): ("L", "B", [(10.9, None), (10.9, 15.25), ("dst", 15.25)]),
    ("fact_delivery", "dim_phase"): ("L", "R", [(10.6, None), (10.6, "dst")]),
    ("fact_delivery", "dim_season"): ("L", "T", [(10.3, None), (10.3, 5.3), ("dst", 5.3)]),
    ("fact_delivery", "dim_match"): ("R", "L", [(16.4, None), (16.4, "dst")]),
    ("fact_delivery", "dim_date"): ("R", "L", [(16.1, None), (16.1, "dst")]),
    ("fact_delivery", "dim_venue"): ("R", "L", [(16.7, None), (16.7, "dst")]),
    ("fact_delivery", "dim_team"): ("R", "L", [(17.0, None), (17.0, "dst")]),
    ("fact_match_summary", "dim_match"): ("L", "R", [(23.3, None), (23.3, "dst")]),
    ("fact_match_summary", "dim_date"): ("L", "R", [(23.0, None), (23.0, "dst")]),
    ("fact_match_summary", "dim_venue"): ("L", "R", [(22.7, None), (22.7, "dst")]),
    ("fact_match_summary", "dim_team"): ("L", "R", [(22.4, None), (22.4, "dst")]),
    ("fact_match_summary", "dim_player"): ("R", "T", [(28.6, None), (28.6, 17.0), ("dst", 17.0)]),
    ("fact_match_summary", "dim_season"): ("R", "B", [(28.9, None), (28.9, 2.6), ("dst", 2.6)]),
}


class Box:
    def __init__(self, table: str, cols: pd.DataFrame):
        self.table = table
        self.fact = table.startswith("fact_")
        self.x, self.top = POS[table]
        self.desc = cols.table_description.iloc[0]
        self.keys, self.measures = [], []
        for c in cols.itertuples():
            key = str(c.key) if pd.notna(c.key) else ""
            ref = str(c.references) if pd.notna(c.references) else ""
            tag = ", ".join(t for t, on in (("PK", "PK" in key), ("FK", bool(ref))) if on)
            if self.fact and not tag:
                self.measures.append(c.column)
            else:
                self.keys.append((c.column, str(c.type), tag, ref))
        self.mlines = textwrap.wrap(", ".join(self.measures), 58) if self.fact else []
        extra = (len(self.mlines) + 1) * 0.25 + 0.15 if self.fact else 0
        self.height = HEAD + ROW * len(self.keys) + extra

    left = property(lambda s: s.x - W / 2)
    right = property(lambda s: s.x + W / 2)
    bottom = property(lambda s: s.top - s.height)

    def row_y(self, column: str) -> float:
        return self.top - HEAD - ROW * ([k[0] for k in self.keys].index(column) + 0.5)

    def pk_y(self) -> float:
        return self.row_y(next(k[0] for k in self.keys if "PK" in k[2]))

    def draw(self, ax):
        lw = 1.8 if self.fact else 1.1
        ax.add_patch(plt.Rectangle((self.left, self.bottom), W, self.height, fc="white", ec=INK, lw=lw,
                                   zorder=3))
        ax.add_patch(plt.Rectangle((self.left, self.top - HEAD), W, HEAD, fc="#2f2f2f" if self.fact else "#e6e6e6",
                                   ec=INK, lw=lw, zorder=3))
        fg = "white" if self.fact else INK
        ax.text(self.x, self.top - HEAD * 0.4, self.table, ha="center", va="center", fontsize=9.6,
                fontweight="bold", family=FONT, color=fg, zorder=4)
        ax.text(self.x, self.top - HEAD * 0.8, "FACT" if self.fact else "DIMENSION", ha="center", va="center",
                fontsize=6, family=FONT, color=fg, zorder=4)
        for i, (col, typ, tag, ref) in enumerate(self.keys):
            y = self.top - HEAD - ROW * (i + 0.5)
            if i:
                ax.plot([self.left, self.right], [y + ROW / 2] * 2, color="#cccccc", lw=0.5, zorder=4)
            t = ax.text(self.left + 0.1, y, col, va="center", fontsize=7.7, family=FONT, zorder=4, color=INK)
            if "PK" in tag:
                t.set_fontweight("bold")
            right = (ref.split(".")[0].removeprefix("dim_") if ref else typ.lower())
            ax.text(self.right - 0.62, y, right, va="center", ha="right", fontsize=6.3, family=FONT,
                    color=GREY, zorder=4, style="italic" if ref else "normal")
            ax.text(self.right - 0.08, y, tag, va="center", ha="right", fontsize=6.4, family=FONT, zorder=4,
                    fontweight="bold" if "PK" in tag else "normal")
        if self.fact:
            y = self.top - HEAD - ROW * len(self.keys)
            ax.plot([self.left, self.right], [y, y], color=INK, lw=0.8, zorder=4)
            ax.text(self.left + 0.1, y - 0.2, "measures", fontsize=6.4, family=FONT, fontweight="bold",
                    va="center", zorder=4)
            for j, ln in enumerate(self.mlines):
                ax.text(self.left + 0.1, y - 0.2 - 0.25 * (j + 1), ln, fontsize=6.1, family=FONT, color=GREY,
                        va="center", zorder=4)


def _end(ax, x, y, side, many):
    """Crow's foot (many) or bar (one) where a line meets a box side."""
    d = {"L": (-1, 0), "R": (1, 0), "T": (0, 1), "B": (0, -1)}[side]
    if many:
        for o in (-0.13, 0, 0.13):
            if d[1] == 0:
                ax.plot([x + 0.32 * d[0], x], [y, y + o], color=LINE, lw=0.9, zorder=5)
            else:
                ax.plot([x, x + o], [y + 0.32 * d[1], y], color=LINE, lw=0.9, zorder=5)
    else:
        if d[1] == 0:
            xb = x + 0.16 * d[0]
            ax.plot([xb, xb], [y - 0.13, y + 0.13], color=LINE, lw=1.3, zorder=5)
        else:
            yb = y + 0.16 * d[1]
            ax.plot([x - 0.13, x + 0.13], [yb, yb], color=LINE, lw=1.3, zorder=5)


STARS = [  # (fact, [(dimension, label)]) drawn as one star each; shared dimensions repeat (conformed)
    ("fact_delivery", [("dim_date", ""), ("dim_season", ""), ("dim_venue", ""), ("dim_match", ""),
                       ("dim_team", "batting, bowling"), ("dim_player", "batter, bowler, non-striker,\ndismissed, fielder"),
                       ("dim_phase", "")]),
    ("fact_match_summary", [("dim_date", ""), ("dim_season", ""), ("dim_venue", ""), ("dim_match", ""),
                            ("dim_team", "batting first, chasing,\ntoss winner, winner"),
                            ("dim_player", "player of the match")]),
    ("fact_player_season_phase", [("dim_player", ""), ("dim_season", ""), ("dim_phase", ""),
                                  ("dim_player_phase_profile", "SCD2 spell in force")]),
]


def _box(ax, cx, cy, title, lines, fact, w=3.3):
    h = 0.55 + 0.27 * len(lines)
    ax.add_patch(plt.Rectangle((cx - w / 2, cy - h / 2), w, h, fc="white", ec=INK, lw=1.8 if fact else 1.0, zorder=3))
    ax.add_patch(plt.Rectangle((cx - w / 2, cy + h / 2 - 0.5), w, 0.5, fc="#2f2f2f" if fact else "#e6e6e6",
                               ec=INK, lw=1.8 if fact else 1.0, zorder=3))
    ax.text(cx, cy + h / 2 - 0.25, title, ha="center", va="center", fontsize=8.6, fontweight="bold",
            family=FONT, color="white" if fact else INK, zorder=4)
    for i, (txt, bold) in enumerate(lines):
        ax.text(cx - w / 2 + 0.1, cy + h / 2 - 0.68 - 0.27 * i, txt, va="center", fontsize=6.9, family=FONT,
                fontweight="bold" if bold else "normal", color=INK if bold or not fact else GREY, zorder=4)


def draw(dd: pd.DataFrame, path_stem) -> int:
    import math
    cols = {t: g for t, g in dd.groupby("table")}
    fig, ax = plt.subplots(figsize=(24, 11))
    n_fk = int(dd.references.notna().sum())
    for k, (fact, dims) in enumerate(STARS):
        cx, cy, R = 6.6 + k * 14.2, 5.6, 4.4
        f = cols[fact]
        keys = [(f"{r.column}  " + ", ".join(t for t, on in (("PK", "PK" in str(r.key)), ("FK", pd.notna(r.references))) if on), True)
                for r in f.itertuples() if "PK" in str(r.key) or pd.notna(r.references)]
        n_meas = len(f) - len(keys)
        for i, (dim, label) in enumerate(dims):
            a = math.pi / 2 - 2 * math.pi * i / len(dims)
            dx, dy = cx + R * math.cos(a) * 1.35, cy + R * math.sin(a)
            ax.plot([cx, dx], [cy, dy], color=LINE, lw=1.1, zorder=1)
            ax.text(cx + (dx - cx) * 0.36, cy + (dy - cy) * 0.36, "N", fontsize=7.5, family=FONT, ha="center",
                    va="center", zorder=2, bbox=dict(fc="white", ec="none", pad=0.4))
            ax.text(cx + (dx - cx) * 0.74, cy + (dy - cy) * 0.74, "1", fontsize=7.5, family=FONT, ha="center",
                    va="center", zorder=2, bbox=dict(fc="white", ec="none", pad=0.4))
            if label:
                ax.text(cx + (dx - cx) * 0.55, cy + (dy - cy) * 0.55 - 0.05, label, fontsize=6.3, family=FONT,
                        ha="center", va="top", style="italic", color=GREY, zorder=2,
                        bbox=dict(fc="white", ec="none", pad=0.5))
            d = cols[dim]
            pk = d[d.key.astype(str).str.contains("PK")].column.tolist()
            attrs = d[~d.key.astype(str).str.contains("PK")].column.tolist()
            lines = [(c + "  PK", True) for c in pk] + [(c, False) for c in attrs[:4]]
            if len(attrs) > 4:
                lines.append((f"+ {len(attrs) - 4} more", False))
            _box(ax, dx, dy, dim, lines, False, w=2.75)
        _box(ax, cx, cy, fact, keys + [(f"+ {n_meas} measures", False)], True, w=3.3)
        grain = {"fact_delivery": "grain: one ball", "fact_match_summary": "grain: one match",
                 "fact_player_season_phase": "grain: player x season x role x phase"}[fact]
        ax.text(cx, cy - R - 1.7, grain, ha="center", fontsize=8.5, family=FONT, fontweight="bold", color=INK)
    ax.text(0.0, 12.25, "IPL Phase-Performance Data Warehouse: star schema", fontsize=15, fontweight="bold",
            family=FONT, color=INK)
    ax.text(0.0, 11.8, f"Three stars, one per fact table, sharing 8 conformed dimensions (the same dim_date, dim_season, "
            f"dim_venue, dim_match, dim_team, dim_player and dim_phase tables appear in more than one star). "
            f"{n_fk} foreign keys, all fact to dimension (N to 1); no dimension references another.",
            fontsize=8.4, family=FONT, color=INK)
    ax.text(0.0, 11.45, "Italic labels name the roles of a role-playing dimension. dim_player_phase_profile is SCD Type 2: "
            "one row per spell, linked to the season fact by profile_key.", fontsize=8.0, family=FONT, color=GREY)
    ax.set_xlim(-0.5, 43.0)
    ax.set_ylim(-1.2, 12.6)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()
    for ext in ("png", "svg", "pdf"):
        fig.savefig(f"{path_stem}.{ext}", dpi=200, facecolor="white", bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    return n_fk


def run() -> int:
    dd = pd.read_csv(DOCS / "data_dictionary.csv")
    for old in DOCS.glob("er_diagram.*"):
        old.unlink()
    return draw(dd, DOCS / "er_diagram_keys")


if __name__ == "__main__":
    n = run()
    print(f"wrote docs/er_diagram_keys.png/.svg/.pdf ({n} foreign keys)")
