"""Project-wide constants and filesystem layout."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = PROJECT_ROOT / "sql"

# phase_key, phase_name, start_over, end_over (section 8.2)
PHASES = (
    (1, "Powerplay", 1, 6),
    (2, "Middle", 7, 15),
    (3, "Death", 16, 20),
)

# Minimum balls in a season for a player-season to be classified (section 8.3).
QUALIFY_BALLS = 60
# Results are reported at both thresholds as a sensitivity check.
SENSITIVITY_THRESHOLDS = (60, 120)

# G6: CSK, MI, KKR, RR, Delhi, Punjab, RCB, Deccan Chargers, SRH, Pune Warriors,
# Kochi Tuskers, Rising Pune Supergiant, Gujarat Lions, Gujarat Titans, LSG.
# Update this if the downloaded dataset version covers fewer seasons.
EXPECTED_FRANCHISES = 15

# Raw strings treated as missing values when cleaning.
NULL_TOKENS = frozenset({"", "NA", "N/A", "NaN", "nan", "None", "none", "null", "NULL"})

# Dismissal kinds credited to the bowler.
BOWLER_WICKET_KINDS = frozenset(
    {"bowled", "caught", "lbw", "stumped", "caught and bowled", "hit wicket"}
)
# Dismissal kinds that are not a dismissal of the batter.
NOT_OUT_KINDS = frozenset({"retired hurt", "retired not out"})


@dataclass(frozen=True)
class Paths:
    root: Path = PROJECT_ROOT
    mappings: Path = field(default=PROJECT_ROOT / "mappings")

    @property
    def raw(self) -> Path:
        return self.root / "data" / "raw"

    @property
    def staging(self) -> Path:
        return self.root / "data" / "staging"

    @property
    def clean(self) -> Path:
        return self.root / "data" / "clean"

    @property
    def export(self) -> Path:
        return self.root / "data" / "export"

    @property
    def db(self) -> Path:
        return self.root / "db" / "ipl_dw.sqlite"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    def ensure(self) -> None:
        for p in (self.raw, self.staging, self.clean, self.export, self.db.parent, self.logs):
            p.mkdir(parents=True, exist_ok=True)
