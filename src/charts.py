"""Shared matplotlib styling for report figures (static PNGs, light surface).

Phases use the first three categorical slots, which stay distinguishable for
colour-blind readers; magnitudes use a single-hue blue ramp.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"
PHASE_COLORS = {"Powerplay": "#2a78d6", "Middle": "#eb6834", "Death": "#1baf7a"}
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
BLUE = "#2a78d6"
SEQUENTIAL = LinearSegmentedColormap.from_list(
    "blue_seq", ["#cde2fb", "#86b6ef", "#3987e5", "#256abf", "#184f95", "#0d366b"])


def style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID, "axes.labelcolor": TEXT_2, "axes.titlecolor": TEXT,
        "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "axes.axisbelow": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "xtick.color": TEXT_2, "ytick.color": TEXT_2, "font.size": 10,
        "legend.frameon": False, "legend.labelcolor": TEXT,
        "lines.linewidth": 2, "lines.markersize": 5,
    })


def save(fig, path) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
