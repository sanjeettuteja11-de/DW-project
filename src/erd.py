"""ER diagram of the star schema (deliverable D6), drawn from docs/data_dictionary.csv.

    python -m src.dictionary && python -m src.erd

Writes docs/er_diagram_keys.png/.svg/.pdf: every table with its primary and
foreign keys. Each relationship line starts at the foreign-key row (crow's
foot = many side) and ends at the primary-key row it references (bar = one
side), so every foreign key in the DDL appears as exactly one line.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from .config import PROJECT_ROOT  # noqa: E402

DOCS = PROJECT_ROOT / "docs"
W, ROW, HEAD = 3.6, 0.34, 0.62
FONT = "DejaVu Sans"

# Column x-centre and the tables stacked in it (top to bottom).
LAYOUT = {
    2.0: ["dim_player_phase_profile"],
    6.6: ["dim_player", "dim_phase"],
    12.0: ["fact_player_season_phase", "fact_delivery", "dim_match", "fact_match_summary"],
    17.8: ["dim_season", "dim_team", "dim_venue"],
}
TOPS = {"dim_player_phase_profile": 8.3, "dim_player": 11.9, "dim_phase": 5.0,
        "dim_season": 13.4, "dim_team": 8.9, "dim_venue": 3.6}


class Box:
    def __init__(self, table: str, cols: pd.DataFrame, x: float, top: float):
        self.table, self.x, self.top = table, x, top
        self.rows = []
        hidden = 0
        for c in cols.itertuples():
            key = str(c.key) if pd.notna(c.key) else ""
            fk = pd.notna(c.references) and str(c.references) != ""
            tag = ", ".join(t for t, on in (("PK", "PK" in key), ("FK", fk)) if on)
            if tag:
                self.rows.append((c.column, str(c.type), tag, str(c.references) if fk else ""))
            else:
                hidden += 1
        self.hidden = hidden
        self.height = HEAD + ROW * (len(self.rows) + 1)

    @property
    def left(self):
        return self.x - W / 2

    @property
    def right(self):
        return self.x + W / 2

    def row_y(self, column: str) -> float:
        names = [r[0] for r in self.rows]
        return self.top - HEAD - ROW * (names.index(column) + 0.5)

    def draw(self, ax):
        fact = self.table.startswith("fact_")
        ax.add_patch(plt.Rectangle((self.left, self.top - self.height), W, self.height, fc="white",
                                   lw=1.6 if fact else 1.1, ec="black", zorder=3))
        ax.add_patch(plt.Rectangle((self.left, self.top - HEAD), W, HEAD, fc="#d4d4d4" if fact else "#f0f0f0",
                                   ec="black", lw=1.1, zorder=3))
        ax.text(self.x, self.top - HEAD * 0.38, self.table, ha="center", va="center", fontsize=9.2,
                fontweight="bold", family=FONT, zorder=4)
        ax.text(self.x, self.top - HEAD * 0.78, "FACT" if fact else "DIMENSION", ha="center", va="center",
                fontsize=6.3, family=FONT, zorder=4)
        for i, (col, typ, tag, _) in enumerate(self.rows):
            y = self.top - HEAD - ROW * (i + 0.5)
            ax.plot([self.left, self.right], [y - ROW / 2, y - ROW / 2], color="#999999", lw=0.5, zorder=4)
            t = ax.text(self.left + 0.1, y, col, va="center", fontsize=7.8, family=FONT, zorder=4)
            if "PK" in tag:
                t.set_fontweight("bold")
            ax.text(self.right - 1.45, y, typ, va="center", fontsize=6.4, family=FONT, color="#333333", zorder=4)
            ax.text(self.right - 0.1, y, tag, va="center", ha="right", fontsize=6.6, family=FONT, zorder=4)
        y = self.top - HEAD - ROW * (len(self.rows) + 0.5)
        ax.text(self.left + 0.1, y, f"+ {self.hidden} attribute / measure columns", va="center",
                fontsize=6.6, style="italic", family=FONT, color="#333333", zorder=4)


def _crow(ax, x, y, direction):
    """Crow's foot at the table edge (x, y); the line arrives from `direction` (+1 right, -1 left)."""
    for dy in (-0.12, 0, 0.12):
        ax.plot([x + 0.34 * direction, x], [y, y + dy], color="black", lw=0.9, zorder=5)


def _bar(ax, x, y, direction):
    xb = x + 0.17 * direction
    ax.plot([xb, xb], [y - 0.12, y + 0.12], color="black", lw=1.2, zorder=5)


def layout(dd: pd.DataFrame) -> dict[str, Box]:
    boxes = {}
    for x, tables in LAYOUT.items():
        top = 15.2
        for t in tables:
            b = Box(t, dd[dd.table == t], x, TOPS.get(t, top))
            boxes[t] = b
            top = b.top - b.height - 0.55
    return boxes


def draw(dd: pd.DataFrame, path_stem) -> int:
    boxes = layout(dd)
    fig, ax = plt.subplots(figsize=(15.5, 12.4))
    refs = [(b.table, col, ref) for b in boxes.values() for col, _, _, ref in b.rows if ref]
    lane: dict = {}
    for src, col, ref in refs:
        ref_table, ref_col = ref.split(".")
        s, t = boxes[src], boxes[ref_table]
        y0, y1 = s.row_y(col), t.row_y(ref_col)
        if abs(s.x - t.x) < 0.1:          # same column: bracket on the right-hand side
            k = lane.setdefault(("same", s.x), 0)
            lane[("same", s.x)] += 1
            xo = s.right + 0.4 + 0.22 * k
            pts = [(s.right, y0), (xo, y0), (xo, y1), (t.right, y1)]
            d0 = d1 = 1
        else:
            d = 1 if t.x > s.x else -1
            x0 = s.right if d > 0 else s.left
            x1 = t.left if d > 0 else t.right
            k = lane.setdefault((s.table, d), 0)
            lane[(s.table, d)] += 1
            xm = x0 + d * (0.45 + 0.13 * k)
            pts = [(x0, y0), (xm, y0), (x1 - d * 0.5, y1), (x1, y1)]
            d0, d1 = d, -d
        xs, ys = zip(*pts)
        ax.plot(xs, ys, color="#222222", lw=0.85, zorder=1)
        _crow(ax, pts[0][0], pts[0][1], d0)
        _bar(ax, pts[-1][0], pts[-1][1], d1)
    for b in boxes.values():
        b.draw(ax)
    ax.text(0.2, 15.95, "IPL Phase-Performance Data Warehouse: star schema", fontsize=14, fontweight="bold",
            family=FONT)
    ax.text(0.2, 15.5, "Bold = primary-key column. Each line runs from a foreign key (crow's foot, many side) "
            "to the primary key it references (bar, one side). 3 fact tables, 7 dimension tables, "
            f"{len(refs)} foreign keys.", fontsize=8.5, family=FONT)
    ax.set_xlim(0, 19.8)
    ax.set_ylim(-2.3, 16.3)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()
    for ext in ("png", "svg", "pdf"):
        fig.savefig(f"{path_stem}.{ext}", dpi=200, facecolor="white", bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    return len(refs)


def run() -> int:
    dd = pd.read_csv(DOCS / "data_dictionary.csv")
    for old in DOCS.glob("er_diagram.*"):
        old.unlink()
    return draw(dd, DOCS / "er_diagram_keys")


if __name__ == "__main__":
    n = run()
    print(f"wrote docs/er_diagram_keys.png/.svg/.pdf ({n} foreign keys)")
