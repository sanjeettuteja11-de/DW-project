"""Generate notebooks 01-04 (run once; the .ipynb files are committed without outputs).

    python notebooks/build_notebooks.py

Each notebook reads the project root from IPL_DW_ROOT (default: the repository),
so the same notebooks run on the real data or on a test fixture.
"""
from pathlib import Path

import nbformat as nbf

HERE = Path(__file__).resolve().parent

SETUP = """import os, sys
from pathlib import Path
import pandas as pd
from IPython.display import Image, display

REPO = Path.cwd().resolve().parent if Path.cwd().name == "notebooks" else Path.cwd().resolve()
sys.path.insert(0, str(REPO))
ROOT = Path(os.environ.get("IPL_DW_ROOT", REPO))
LOGS, EXPORT = ROOT / "logs", ROOT / "data" / "export"
pd.set_option("display.max_columns", 50, "display.width", 200)
print("Project root:", ROOT)"""


def md(text):
    return nbf.v4.new_markdown_cell(text.strip())


def code(text):
    return nbf.v4.new_code_cell(text.strip())


NOTEBOOKS = {
    "01_profiling.ipynb": [
        md("""# 01 Extraction and profiling (Phase 1, deliverables D1-D2)
Run `python -m src.pipeline` first. This notebook reads the logs written by steps E1-E3."""),
        code(SETUP),
        md("## E1 Extraction log: provenance, checksum and row counts"),
        code('pd.read_csv(LOGS / "extraction_log.csv")'),
        md("## E3 Column profile"),
        code('profile = pd.read_csv(LOGS / "profiling_report.csv")\nprofile'),
        md("## Section 6: expected data-quality issues, confirmed or not"),
        code('pd.read_csv(LOGS / "data_quality_findings.csv")'),
        md("""**Findings (write after running on the downloaded data):** for each issue, state whether it
was confirmed, the evidence count, and any issue not anticipated in section 6."""),
    ],
    "02_cleaning.ipynb": [
        md("""# 02 Cleaning and warehouse load (Phases 2-3, deliverables D3, D7, D9)"""),
        code(SETUP),
        md("## Cleaning log: every rule and the rows it changed"),
        code('log = pd.read_csv(LOGS / "cleaning_log.csv")\n'
             'log.groupby(["step", "rule"]).rows_affected.sum().sort_values(ascending=False)'),
        md("## Canonical mapping tables"),
        code('for name in ("map_team", "map_venue"):\n'
             '    display(pd.read_csv(ROOT / "data" / "clean" / f"{name}.csv"))'),
        code('players = pd.read_csv(ROOT / "data" / "clean" / "map_player.csv")\n'
             'players[players.raw_name != players.canonical_name]'),
        md("""## Player pairs for manual review
Approve a merge by adding `raw_name,canonical_name,merge,<reason>` to `mappings/players.csv`;
record a rejected pair with decision `keep_separate`. Then re-run the pipeline."""),
        code('pd.read_csv(LOGS / "player_fuzzy_candidates.csv").head(30)'),
        md("## Team dimension: SCD Type 2 on name"),
        code('pd.read_csv(EXPORT / "dim_team.csv")'),
        md("## Validation gates G1-G9"),
        code('pd.read_csv(LOGS / "validation_report.csv")[["gate", "status", "failures", "detail"]]'),
        code('pd.read_csv(LOGS / "g4_exceptions.csv")'),
    ],
    "03_insights.ipynb": [
        md("""# 03 Insights (Phase 5, deliverable D11)
Answers the six questions of section 10. Charts are also saved to `data/export/analysis/figures/`."""),
        code(SETUP),
        code('from src import analysis\nfrom src.config import Paths\n'
             'res = analysis.run(Paths(root=ROOT))\nFIGS = EXPORT / "analysis" / "figures"'),
        md("## Q1 Which players changed primary phase?"),
        code('res["q1_drift_summary"]'),
        code('res["q1_drift_moves"]'),
        md("Three worked examples (largest rise of the new phase's index):"),
        code('res["q1_worked_examples"]'),
        md("**Finding:** _write after running on the real data._"),
        md("## Q2 How do league phase run rates change by season?"),
        code('display(Image(FIGS / "q2_league_phase_rates.png"))\nres["q2_league_phase_rates"]'),
        md("**Finding:**"),
        md("## Q3 Team Powerplay and Death profiles"),
        code('display(Image(FIGS / "q3_team_powerplay_heatmap.png"))\n'
             'display(Image(FIGS / "q3_team_death_heatmap.png"))'),
        md("**Finding:**"),
        md("## Q4 Which venues favour which phase and innings?"),
        code('if (FIGS / "q4_venues.png").exists():\n    display(Image(FIGS / "q4_venues.png"))\n'
             'res["q4_venue_profile"]'),
        md("**Finding:**"),
        md("""## Q5 Does the toss decision relate to winning?
Chi-square test of independence, decision (bat/field) x toss winner won (yes/no). A p-value below
0.05 would indicate an association; it does not show that the decision causes the result."""),
        code('display(res["q5_toss_overall"])\nres["q5_toss_by_venue"]'),
        md("**Finding:**"),
        md("## Q6 How strongly does Powerplay performance relate to the result?"),
        code('display(Image(FIGS / "q6_powerplay_win_rate.png"))\n'
             'display(res["q6_powerplay_correlation"])\nres["q6_powerplay_win_rate"]'),
        md("**Finding:**"),
    ],
    "04_ml.ipynb": [
        md("""# 04 Machine learning (Phase 6, deliverable D12)
Target: the team batting first wins. Model A: after the first-innings Powerplay. Model B: after both
Powerplays. Chronological split by season; the test seasons are scored once."""),
        code(SETUP),
        code('from src import ml\nfrom src.config import Paths\n'
             'res = ml.run(Paths(root=ROOT))\nFIGS = EXPORT / "ml" / "figures"'),
        md("## Split"),
        code('res["split"]'),
        md("## Season-ordered cross-validation (train + validation seasons only)"),
        code('res["cv_results"].sort_values(["feature_set", "model", "cv_roc_auc"], ascending=[True, True, False])'),
        md("## Validation and test metrics, with both baselines"),
        code('m = res["metrics"]\nm.pivot_table(index=["feature_set", "model"], columns="split",\n'
             '               values=["accuracy", "f1", "roc_auc"]).round(3)'),
        code('display(Image(FIGS / "model_comparison.png"))'),
        md("## Interpretation"),
        code('display(Image(FIGS / "decision_tree_model_A.png"))'),
        code('imp = res["feature_importance"]\n'
             'imp.pivot_table(index="feature", columns=["feature_set", "model"], values="value").round(3)'),
        md("## Error analysis: confident wrong predictions (upsets)"),
        code('res["upsets"]'),
        md("""**Findings:** compare each model with both baselines. T20 results are high-variance, so a
modest margin over the baselines is an expected, legitimate result; report it as obtained."""),
    ],
}

for name, cells in NOTEBOOKS.items():
    nb = nbf.v4.new_notebook()
    nb.cells = cells
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    nbf.write(nb, HERE / name)
    print("wrote", name)
