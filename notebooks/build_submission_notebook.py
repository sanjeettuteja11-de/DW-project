"""Build the single end-to-end submission notebook (deliverable 1 of the course guidelines).

    python notebooks/build_submission_notebook.py
    jupyter nbconvert --to notebook --execute --inplace notebooks/IPL_DW_Project.ipynb \
        --ExecutePreprocessor.timeout=1800

The notebook runs the whole project from the raw Kaggle files: extraction, profiling,
cleaning, transformation, SQLite load, validation, insights, machine learning and the
Power BI export. Narrative findings were written from the outputs of this run.
"""
from pathlib import Path

import nbformat as nbf

HERE = Path(__file__).resolve().parent
OUT = HERE / "IPL_DW_Project.ipynb"


def md(text):
    return nbf.v4.new_markdown_cell(text.strip("\n"))


def code(text):
    return nbf.v4.new_code_cell(text.strip("\n"))


REPO = HERE.parent

# Every file of the project's code, in the order the pipeline uses it: (path, step, what it does).
CODE_FILES = [
    ("requirements.txt", "setup", "Python packages and the versions the project was run with."),
    ("src/__init__.py", "setup", "Marks `src/` as a Python package."),
    ("src/config.py", "setup", "Constants (the three phases, the 60-ball qualification threshold, null tokens) "
                               "and the folder layout."),
    ("src/extract.py", "E1–E2", "Registers the raw files (SHA-256, row and column counts) and stages every "
                                "column as text with its source row number."),
    ("src/profiling.py", "E3", "Profiles every column and tests the ten expected data-quality issues."),
    ("mappings/teams.csv", "E4–E6", "Canonical team and franchise names for every raw team string."),
    ("mappings/venues.csv", "E4–E6", "Manual venue merges that the normalised-name key cannot find."),
    ("mappings/cities.csv", "E4–E6", "Canonical city names."),
    ("mappings/players.csv", "E4–E6", "Reviewed player merges (empty: every fuzzy match was a different person)."),
    ("src/clean.py", "E4–E6", "Cleaning rules: null tokens, season labels, 0-based overs, team / venue / city / "
                              "player canonicalisation, fuzzy-match review list, cleaning log."),
    ("src/transform.py", "E7–E9", "Builds the dimensions and facts: phase of every ball, legal-ball and "
                                  "faced-ball flags, match summary, player-season-phase shares and index."),
    ("src/scd2.py", "E10", "SCD Type 2 dimension of each player's primary phase, the drift table and the "
                           "threshold sensitivity check."),
    ("sql/ddl.sql", "E7–E10", "Warehouse schema: staging, clean, dimension and fact tables with keys."),
    ("sql/views.sql", "E7–E10", "Analysis views on top of the star schema."),
    ("src/load.py", "E7–E10", "SQLite connection, schema creation and table loading."),
    ("src/validate.py", "E11", "Validation gates G1–G9; the pipeline stops if any gate fails."),
    ("src/features.py", "E12", "Match-level feature table for the models."),
    ("src/dictionary.py", "E12", "Writes the data dictionary for every exported column."),
    ("src/export.py", "E12", "Exports dimensions, facts and views to CSV."),
    ("src/pipeline.py", "E1–E12", "Runs every step in order, with the gates between steps."),
    ("src/charts.py", "insights", "Shared chart style."),
    ("src/analysis.py", "insights", "The six insight questions: tables and charts."),
    ("src/ml.py", "ML", "Time-based split, baselines, logistic regression, decision tree, random forest, "
                        "cross-validation, test metrics, feature importance."),
    ("src/powerbi.py", "Power BI", "Writes the Power BI workbook (18 tables)."),
    ("src/erd.py", "docs", "Draws the ER diagram of the warehouse."),
    ("dashboard/app.py", "prototype", "First version of the dashboard in Streamlit, made before the Power BI one; "
                                      "kept because the tests in Appendix A check that its pages render."),
]
TEST_FILES = ["pytest.ini", "tests/__init__.py", "tests/conftest.py", "tests/synthetic.py", "tests/test_clean.py",
              "tests/test_scd2.py", "tests/test_gates.py", "tests/test_pipeline.py", "tests/test_analysis_ml.py"]


def file_cell(rel):
    """A cell that holds one project file and writes it to disk when run."""
    text = (REPO / rel).read_text(encoding="utf-8")
    if not text:  # %%writefile needs a body; empty files (package markers) are created directly
        return nbf.v4.new_code_cell(f'from pathlib import Path\nPath("{rel}").write_text("")  # empty file')
    return nbf.v4.new_code_cell(f"%%writefile {rel}\n" + text)


def lines_of(rel):
    return len((REPO / rel).read_text(encoding="utf-8").splitlines())


def code_section():
    total = sum(lines_of(f) for f, _, _ in CODE_FILES if f.endswith((".py", ".sql")))
    rows = "\n".join(f"| {step} | `{f}` | {lines_of(f)} | {what} |" for f, step, what in CODE_FILES)
    out = [md(f"""
## 0. The project code

This section is the complete code of the project ({total:,} lines of Python and SQL, plus four small mapping
tables), one cell per file, in the order the pipeline uses it. Each cell starts with `%%writefile`, so running it
writes that file to disk; the import cell after this section then loads the package. To run the project on
another machine, install the packages in `requirements.txt` (Python 3.11 or newer), put this notebook in an empty
folder and run all cells: section 0 writes the code, section 1 downloads the data, and the rest runs it.

| Step | File | Lines | What it does |
|---|---|---|---|
{rows}
"""),
           code(r'''
import os
from pathlib import Path

REPO = Path.cwd().resolve().parent if Path.cwd().name == "notebooks" else Path.cwd().resolve()
os.chdir(REPO)
for folder in ("src", "sql", "mappings", "tests", "dashboard"):
    os.makedirs(folder, exist_ok=True)
print("Writing the project code into", REPO)
''')]
    for i, (f, step, what) in enumerate(CODE_FILES, 1):
        out.append(md(f"### 0.{i} `{f}` ({step})\n{what}"))
        out.append(file_cell(f))
    return out


def tests_section():
    out = [md("""
## Appendix A. Automated tests

Thirty-eight tests check the cleaning rules, the SCD Type 2 logic, every validation gate (each gate is shown
failing on deliberately broken data), the full pipeline on a small synthetic dataset, and the analysis and model
code. The cells below write the test files and then run them with pytest.
""")]
    for f in TEST_FILES:
        out.append(file_cell(f))
    out.append(code(r'''
import subprocess, sys
result = subprocess.run([sys.executable, "-m", "pytest", "-q", "--color=no", "-p", "no:cacheprovider", "tests"], cwd=REPO, capture_output=True, text=True)
print(result.stdout[-1500:] or result.stderr[-1500:])
assert result.returncode == 0, "a test failed"
'''))
    return out


def powerbi_section():
    import importlib.util
    spec = importlib.util.spec_from_file_location("build_pbip", REPO / "dashboard" / "build_pbip.py")
    b = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(b)
    rel = "\n".join(f"{ft}[{fc}]  *-->1  {tt}[{tc}]" + ("" if active else "   (inactive)")
                     for ft, fc, tt, tc, active in b.RELATIONSHIPS)
    blocks = []
    for table in b.TABLE_ORDER:
        ms = [m for m in b.MEASURES if m[0] == table]
        if not ms:
            continue
        blocks.append(f"-- {table}")
        for _, name, expr, fmt, _folder in ms:
            blocks.append(f"{name} = {expr}" + (f"    -- format {fmt}" if fmt else ""))
        blocks.append("")
    dax = "\n".join(blocks).rstrip()
    return [md(f"""
## Appendix B. Power BI model: relationships and DAX measures

The Power BI project (`dashboard/IPL_Scorebook/`, opened with Power BI Desktop) loads the 18 tables written in
section 8 (the `Model` table is called `MLModel` there). These are its relationships (many side → one side;
inactive ones avoid ambiguous filter paths) and its {len(b.MEASURES)} DAX measures.

```text
{rel}
```

```dax
{dax}
```
""")]


cells = [
    md(r"""
# IPL Phase-Performance and Style-Drift Data Warehouse
**Data Wrangling group project · B.Tech CSE (Data Science), NMIMS MPSTME · Semester V (2026-27)**

Group members: Sanjeet Singh Tuteja (L076) · _[Member 2 name, roll no.]_ · _[Member 3 name, roll no.]_

## Objective
We take seventeen seasons of public IPL ball-by-ball data (2008–2024) through the full wrangling
pipeline (extraction, cleaning, transformation and loading into a SQLite star schema), then use the
wrangled data for insights, a classification model and a Power BI dashboard.

The project asks two questions:

1. **Style drift.** Does the phase of the innings in which a player mostly bats or bowls
   (Powerplay overs 1–6, Middle 7–15, Death 16–20) stay the same from season to season? Who
   changes, and how often?
2. **Powerplay signal.** How much of a match result can be predicted from the first six overs of
   each innings?

This notebook runs end to end from the two raw CSV files. **Section 0 contains every line of the
project's code**, one cell per file; each cell writes its file into the `src/` package (or `sql/`,
`mappings/`), so the same code is used by this notebook, the command-line pipeline and the tests.
Sections 1–8 then run that code and show the output of every stage. Appendix A holds the automated
tests and runs them; Appendix B lists the Power BI model's relationships and DAX measures.
"""),
    *code_section(),
    code(r"""
import os, sys, sqlite3, zipfile, urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from IPython.display import Image, display

REPO = Path.cwd().resolve().parent if Path.cwd().name == "notebooks" else Path.cwd().resolve()
sys.path.insert(0, str(REPO))

from src import analysis, extract, ml, pipeline, powerbi
from src.config import PHASES, QUALIFY_BALLS, Paths

P = Paths(root=REPO)
RAW, LOGS, EXPORT = P.raw, P.logs, P.export
pd.set_option("display.max_columns", 40, "display.width", 200, "display.max_colwidth", 70)
print("Project root:", REPO)
"""),

    # ------------------------------------------------------------------ extraction
    md(r"""
## 1. Data extraction

**Source.** *IPL Complete Dataset (2008–2024)* by Prateek Bhardwaj on Kaggle (dataset version 3,
last updated 8 June 2024): two files, `matches.csv` (one row per match) and `deliveries.csv` (one
row per ball). The ball-by-ball records originate from **Cricsheet** (cricsheet.org).

**How it was obtained.** A direct download of the dataset archive from Kaggle's public download
endpoint (the cell below). Public datasets download without an API key through this endpoint; if
it is blocked, the same two files can be downloaded by hand from the dataset page after signing in.

**Access constraints and licence.** No rate limits were hit (one 1.9 MB request). The Kaggle
dataset is published under the Open Database License (database) and Database Contents License
(contents); the underlying Cricsheet data is under the Open Data Commons Attribution License, so
both sources are credited. The data is used for coursework and analysis only, not for wagering.

The raw files are never edited. They are read as text, checksummed and copied unchanged into
staging tables, so every later number can be traced back to a file hash (step E1).
"""),
    code(r"""
SOURCE_URL = "https://www.kaggle.com/datasets/patrickb1912/ipl-complete-dataset-20082020"
API_URL = "https://www.kaggle.com/api/v1/datasets/download/patrickb1912/ipl-complete-dataset-20082020"
DATASET_VERSION = "Kaggle version 3 (files dated 2024-06-08)"
DOWNLOAD_DATE = "2026-10-18"

if not all((RAW / f).exists() for f in ("matches.csv", "deliveries.csv")):
    RAW.mkdir(parents=True, exist_ok=True)
    archive = RAW / "ipl_archive.zip"
    urllib.request.urlretrieve(API_URL, archive)
    with zipfile.ZipFile(archive) as z:
        z.extractall(RAW)
    archive.unlink()

for f in ("matches.csv", "deliveries.csv"):
    p = RAW / f
    print(f"{f:15s} {p.stat().st_size / 1e6:6.1f} MB   sha256 {extract.sha256(p)[:20]}...")

raw_m = extract.read_raw(RAW / "matches.csv")
raw_d = extract.read_raw(RAW / "deliveries.csv")
print("matches:", raw_m.shape, "  deliveries:", raw_d.shape)
raw_m.head(3)
"""),
    code(r"""raw_d.head(3)"""),

    md(r"""
### 1.1 Why this dataset needs wrangling
Before writing any cleaning code we profiled the raw text for the problems we expected. The cell
below shows each one with evidence from the raw files.
"""),
    code(r"""
teams = sorted(set(raw_m.team1) | set(raw_m.team2))
print(f"{len(teams)} distinct team strings, e.g. renames and a spelling variant:")
print("  ", [t for t in teams if any(k in t for k in ("Delhi", "Punjab", "Pune", "Royal", "Deccan"))])

print("\nSeason labels that are not a plain year:", sorted(s for s in raw_m.season.unique() if not s.isdigit()))

v = raw_m.venue.value_counts()
print(f"\n{v.size} distinct venue strings; the same grounds appear under several names, e.g.:")
print("  ", sorted(x for x in v.index if any(k in x for k in ("Chinnaswamy", "Kotla", "Arun Jaitley", "Zayed"))))

overs = raw_d.over.astype(int)
print(f"\nOver numbers run {overs.min()}..{overs.max()} (0-based); the phases are defined on overs 1-20.")

na = {c: int((raw_m[c] == "NA").sum()) for c in raw_m.columns if (raw_m[c] == "NA").any()}
print("\n'NA' text tokens in matches.csv:", na)
print("matches with no city:", int((raw_m.city.isin(["", "NA"])).sum()))

print("\nextras_type:", raw_d.extras_type.replace("", "(blank)").value_counts().to_dict())
"""),
    md(r"""
So the raw data has renamed and misspelt teams, one ground under up to five names, missing cities,
text season labels such as `2007/08` (which is actually IPL 2008), 0-based overs, `NA` strings
instead of nulls, and wides and no-balls that must not count as legal balls. None of this is
visible from a quick `df.describe()`, and each one changes the answers if left alone.
"""),

    # ------------------------------------------------------------------ pipeline
    md(r"""
## 2. Run the ETL pipeline (E1–E12)

`pipeline.run` executes every step and stops before exporting if any of the nine validation gates
fails. The sections after this cell open up each stage and show what it did.

| Step | What it does |
|---|---|
| E1–E2 | Register raw files (SHA-256, row counts) and stage them unchanged in SQLite |
| E3 | Profile every column; test the ten expected data-quality issues |
| E4–E6 | Canonicalise teams, venues, cities and players; normalise types; derive flags |
| E7–E10 | Build dimensions, three fact tables and the SCD Type 2 player-phase profile |
| E11 | Validation gates G1–G9 |
| E12 | Export analysis tables and the ML feature table |
"""),
    code(r"""
exit_code = pipeline.run(P, source_url=SOURCE_URL, dataset_version=DATASET_VERSION, download_date=DOWNLOAD_DATE)
assert exit_code == 0, "a validation gate failed - see logs/validation_report.csv"
"""),
    code(r"""
pd.read_csv(LOGS / "extraction_log.csv").tail(2)[
    ["file", "source_url", "dataset_version", "download_date", "sha256", "rows", "columns"]]
"""),
    md(r"""### 2.1 Profiling result: the ten expected issues"""),
    code(r"""pd.read_csv(LOGS / "data_quality_findings.csv")"""),
    md(r"""
Eight of the ten expected issues were confirmed. Two were not: player names in this version of the
data are already consistent (Cricsheet uses one registered name per player), and the
`(match, inning, over, ball)` key happens to be unique here, but only because extras re-use ball
numbers in a way we cannot rely on; we still use our own `delivery_seq` key (section 4).
"""),

    # ------------------------------------------------------------------ cleaning
    md(r"""
## 3. Data cleaning

### 3.1 Cleaning log
Every rule writes a row to `logs/cleaning_log.csv` with the raw value, the clean value and the
number of rows changed.
"""),
    code(r"""
log = pd.read_csv(LOGS / "cleaning_log.csv")
print(len(log), "logged cleaning rules,", f"{log.rows_affected.sum():,}", "cell changes in total")
log.groupby(["step", "rule"]).agg(rules=("rule", "size"), rows_affected=("rows_affected", "sum")) \
   .sort_values("rows_affected", ascending=False)
"""),
    md(r"""
### 3.2 What we found, what we did, and why

| Problem | Evidence | Decision | Why this method |
|---|---|---|---|
| `NA` / blank text tokens | 1,074 `method`, 51 `city`, ~95% of the dismissal columns | Convert to real NULLs | They are missing-value markers, not values |
| Structural nulls (`extras_type`, `dismissal_kind`, `player_dismissed`, `fielder`) | ~95% null | **Flag** as the category `none`; never impute | Absence means "no extra / no wicket"; imputing would invent events |
| Missing `city` | 51 matches (Dubai, Sharjah) | Filled from the venue mapping | Deterministic: the ground fixes the city, so this is a lookup, not a guess |
| Missing `winner`, `player_of_match`, `result_margin` | 5 no-results, 14 ties | **Kept NULL**; result coded in `match_status` | A no-result has no winner; filling it would be wrong |
| `method` (D/L) almost always null | 98.1% null | Converted to a 0/1 `is_dl_applied` flag; raw column dropped | The only information is "D/L or not" |
| Season stored as text (`2007/08`, `2009/10`, `2020/21`) | 178 matches | Season = calendar year of the match date (D-01) | The labels are ambiguous; the date is not |
| 0-based overs | over 0..19 | Shifted to 1..20 (D-02) | Phases are defined on 1–20 |
| Team renames and a misspelling | 19 raw names | Spelling variants merged; renames kept as **SCD Type 2** spells of one franchise (D-03) | A rename is history, not an error; the franchise id keeps them together |
| Venue variants | 58 raw strings → 36 grounds | Hand-checked mapping table; renamed grounds merged (D-04) | Venue effects must compare the same physical ground |
| Player name variants | 30 fuzzy pairs proposed | **Left as-is**: merged only on an identical letters-and-digits key (D-05) | 13 of the 30 pairs played in the same match, so they are different people; the rest differ in initials and seasons (see 3.4). A wrong merge is worse than a missed one |
| 7-ball overs | 29 overs, 19 innings reach 121 legal balls | **Kept and flagged** (G5 exceptions, D-20) | Real umpire miscounts recorded as bowled; deleting a ball would change real totals |
| Shortened / D-L matches and Super Overs | 21 D-L, 14 Super Overs | Kept in the warehouse; excluded from phase aggregates (Super Over innings) and from ML (`ml_eligible = 0`) | They do not follow the 20-over phase structure |
| Duplicate rows | 0 duplicate deliveries on the grain key | Grain key enforced by gate G2 | Checked rather than assumed |
"""),
    md(r"""### 3.3 Canonical mapping tables (teams and venues)"""),
    code(r"""
map_team = pd.read_csv(P.clean / "map_team.csv")
display(map_team[map_team.raw_name != map_team.canonical_name])
map_venue = pd.read_csv(P.clean / "map_venue.csv")
print(f"{map_venue.raw_name.nunique()} raw venue strings -> {map_venue.canonical_name.nunique()} canonical grounds")
map_venue[map_venue.raw_name != map_venue.canonical_name].head(12)
"""),
    md(r"""
### 3.4 Player name review
Fuzzy matching proposes pairs, but nothing is merged automatically. We checked the closest pairs
against the seasons and teams each name appears with:
"""),
    code(r"""
cand = pd.read_csv(LOGS / "player_fuzzy_candidates.csv")
seasons = raw_d.merge(raw_m[["id", "date"]], left_on="match_id", right_on="id")
def seasons_of(name):
    s = seasons[(seasons.batter == name) | (seasons.bowler == name)]
    return f"{s.date.str[:4].min()}-{s.date.str[:4].max()}" if len(s) else "-"
roles = pd.concat([raw_d[["match_id", c]].rename(columns={c: "name"})
                   for c in ("batter", "bowler", "non_striker", "fielder", "player_dismissed")])
matches_of = roles[roles.name != "NA"].drop_duplicates().groupby("name").match_id.apply(set)
check = cand.copy()
check["seasons_a"] = check.name_a.map(seasons_of)
check["seasons_b"] = check.name_b.map(seasons_of)
check["shared_matches"] = [len(matches_of.get(a, set()) & matches_of.get(b, set())) for a, b in zip(check.name_a, check.name_b)]
print((check.shared_matches > 0).sum(), "of", len(check), "pairs appear in the same match at least once (so are two people)")
check.head(12)
"""),
    md(r"""
High similarity scores, but different people. Thirteen pairs played in the same match (for example
`RG Sharma` and `R Sharma`, Rohit and Rahul; `HH Pandya` and `KH Pandya`, the Pandya brothers). The
rest never overlap and differ in initials and seasons: `CJ Green` (Chris, KKR 2020) and `C Green`
(Cameron, 2023–24), `T Thushara` (Thilan, 2009–10) and `N Thushara` (Nuwan, 2024), `D Jansen` and
`M Jansen` (twin brothers). Merging on fuzzy scores would have silently combined real players, so all
30 pairs were left separate.
"""),

    # ------------------------------------------------------------------ transformation
    md(r"""
## 4. Data transformation

### 4.1 Aggregation and reshape: deliveries → innings phases → one row per match
`fact_delivery` holds 260,920 balls. For the match-level questions and the ML target we aggregate
to match × innings × phase, then pivot so each match becomes one row with first-innings and
second-innings Powerplay columns. The cell below redoes this in plain pandas and checks it against
the warehouse table built by the pipeline.
"""),
    code(r"""
con = sqlite3.connect(P.db)
fd = pd.read_sql("SELECT match_key, inning, phase_key, total_runs, is_legal_for_bowler, is_wicket "
                 "FROM fact_delivery WHERE inning IN (1, 2)", con)
pp = (fd[fd.phase_key == 1]
      .groupby(["match_key", "inning"])
      .agg(pp_runs=("total_runs", "sum"), pp_wickets=("is_wicket", "sum"), pp_balls=("is_legal_for_bowler", "sum"))
      .reset_index()
      .pivot(index="match_key", columns="inning"))
pp.columns = [f"inn{i}_{c}" for c, i in pp.columns]
pp["inn1_pp_run_rate"] = pp.inn1_pp_runs * 6 / pp.inn1_pp_balls

fms = pd.read_sql("SELECT match_key, inn1_pp_runs, inn1_pp_wickets, inn2_pp_runs, inn1_pp_run_rate "
                  "FROM fact_match_summary", con).set_index("match_key")
both = pp.join(fms, rsuffix="_dw", how="inner")
same = lambda a, b: ((a == b) | (a.isna() & b.isna())).all()   # no-result matches have no 2nd innings
assert same(both.inn1_pp_runs, both.inn1_pp_runs_dw) and same(both.inn2_pp_runs, both.inn2_pp_runs_dw)
assert np.allclose(both.inn1_pp_run_rate, both.inn1_pp_run_rate_dw, atol=1e-6, equal_nan=True)
print(f"{len(fd):,} deliveries -> {len(pp):,} match rows; pandas re-derivation matches the warehouse")
pp.head()
"""),
    md(r"""
### 4.2 Engineered features

* **Phase** of every ball from its over (1–6 Powerplay, 7–15 Middle, 16–20 Death), and
  **legal-ball flags** (`is_legal_for_bowler` excludes wides and no-balls; `is_faced_by_batter`
  excludes wides only). Without these, run rates and strike rates are wrong.
* **Phase index** (the core derived feature for question 1). The Middle phase has 9 of the 20
  overs, so raw ball shares would make almost everyone a "Middle" player. We normalise by the
  league:

  `phase_share = player's balls in the phase ÷ player's balls that season`
  `phase_index = phase_share ÷ league phase_share (same role and season)`

  An index of 1.0 means "as much of this phase as the average player". The **primary phase** is the
  phase with the highest index, for player-seasons with at least 60 balls (also checked at 120).
* **Powerplay run-rate difference** (batting first minus chasing) for question 2.
* **Leakage-free team and venue history** for the models: the franchise's previous-season win %
  and the venue's average first-innings score from earlier matches only.

The next cell recomputes the phase index for one season from the delivery table and compares it
with the warehouse.
"""),
    code(r"""
q = '''SELECT f.batter_key AS player_key, f.phase_key, COUNT(*) AS balls
       FROM fact_delivery f JOIN dim_season s USING (season_key)
       WHERE s.year = 2024 AND f.phase_key IS NOT NULL AND f.is_faced_by_batter = 1
       GROUP BY 1, 2'''
b = pd.read_sql(q, con)
b["phase_share"] = b.balls / b.groupby("player_key").balls.transform("sum")
league = b.groupby("phase_key").balls.sum() / b.balls.sum()
b["phase_index"] = b.phase_share / b.phase_key.map(league)

dw = pd.read_sql('''SELECT player_key, phase_key, phase_index FROM fact_player_season_phase f
                    JOIN dim_season s USING (season_key) WHERE s.year = 2024 AND role_type = 'batting' ''', con)
cmp = b.merge(dw, on=["player_key", "phase_key"], suffixes=("", "_dw"))
print("league batting share by phase, 2024:", league.round(3).to_dict())
print("max |difference| vs warehouse:", float((cmp.phase_index - cmp.phase_index_dw).abs().max()))
"""),
    md(r"""
### 4.3 SCD Type 2: each player's primary phase over time
`dim_player_phase_profile` stores one row per *spell*: a run of seasons with the same primary
phase. When the phase changes, the old row is closed and a new one opens, so history is kept.
Two well-known players as a sanity check:
"""),
    code(r"""
spells = pd.read_sql('''SELECT pl.canonical_name AS player, pr.role_type, ph.phase_name AS primary_phase,
                               ROUND(pr.phase_index_value, 2) AS phase_index, pr.valid_from_season,
                               pr.valid_to_season, pr.qualifying_seasons, pr.is_current
                        FROM dim_player_phase_profile pr
                        JOIN dim_player pl USING (player_key)
                        JOIN dim_phase ph ON ph.phase_key = pr.primary_phase_key
                        WHERE pl.canonical_name IN ('HH Pandya', 'MS Dhoni') AND pr.role_type = 'batting'
                        ORDER BY player, valid_from_season''', con)
spells
"""),
    md(r"""
MS Dhoni has been a Death-overs batter in every qualifying season since 2011 (13 seasons, one open
spell). Hardik Pandya was a Death batter from 2015 to 2021 and a Middle-overs batter from 2022,
which fits his move up the order after joining Gujarat Titans as captain. The method recovers role
changes that cricket followers already know about, which gives us some confidence in it.
"""),

    # ------------------------------------------------------------------ loading
    md(r"""
## 5. Loading and storage

The wrangled data is loaded into **SQLite** (`db/ipl_dw.sqlite`) as a star schema with three fact
tables at different grains and seven dimensions, plus analysis views and CSV exports.
"""),
    code(r"""
from src import dictionary, erd
if not (REPO / "docs" / "er_diagram_keys.png").exists():  # first run in a new folder: draw it
    (REPO / "docs").mkdir(exist_ok=True)
    dictionary.main()  # data dictionary parsed from sql/ddl.sql
    erd.run()          # ER diagram drawn from the data dictionary
display(Image(REPO / "docs" / "er_diagram_keys.png", width=900))
"""),
    code(r"""
tables = pd.read_sql("SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') "
                     "AND name NOT LIKE 'sqlite_%' ORDER BY type, name", con)
tables["rows"] = [con.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in tables.name]
tables[tables.name.str.match(r"(dim|fact|v)_")]
"""),
    md(r"""A star-join query against the warehouse: 2024 Powerplay batting run rate by franchise."""),
    code(r"""
pd.read_sql('''
    SELECT t.franchise_id, ROUND(SUM(f.total_runs) * 6.0 / SUM(f.is_legal_for_bowler), 2) AS pp_run_rate,
           SUM(f.is_wicket) AS wickets
    FROM fact_delivery f
    JOIN dim_team t   ON t.team_key = f.batting_team_key
    JOIN dim_phase p  ON p.phase_key = f.phase_key
    JOIN dim_season s ON s.season_key = f.season_key
    WHERE s.year = 2024 AND p.phase_name = 'Powerplay'
    GROUP BY t.franchise_id ORDER BY pp_run_rate DESC''', con)
"""),
    md(r"""
### 5.1 Validation gates
The pipeline refuses to export unless all nine gates pass. G4 and G5 list explained exceptions
(shortened matches; 7-ball overs) instead of hiding them.
"""),
    code(r"""pd.read_csv(LOGS / "validation_report.csv")[["gate", "description", "status", "failures", "detail"]]"""),
    code(r"""
g5 = pd.read_csv(LOGS / "g5_exceptions.csv")
print(len(g5), "seven-ball overs (umpire miscounts), by season:", g5.merge(
    raw_m[["id", "date"]].astype({"id": int}), left_on="source_match_id", right_on="id").date.str[:4].value_counts().sort_index().to_dict())
"""),

    # ------------------------------------------------------------------ insights
    md(r"""
## 6. Insights

`analysis.run` answers six questions and saves every table and chart under
`data/export/analysis/`. The four headline insights follow, each backed by a chart or test.
"""),
    code(r"""
res = analysis.run(P)
FIGS = EXPORT / "analysis" / "figures"
rates = res["q2_league_phase_rates"]
"""),
    md(r"""### Insight 1. The scoring boom is front-loaded: the Powerplay changed most"""),
    code(r"""
display(Image(FIGS / "q2_league_phase_rates.png", width=760))
wide = rates.pivot(index="season", columns="phase_name", values="run_rate")[["Powerplay", "Middle", "Death"]]
change = pd.DataFrame({"2008": wide.loc[2008], "2022": wide.loc[2022], "2024": wide.loc[2024]})
change["% change 2008-2024"] = (100 * (change["2024"] / change["2008"] - 1)).round(1)
change["% change 2022-2024"] = (100 * (change["2024"] / change["2022"] - 1)).round(1)
display(change.round(2))
pp_rates = rates[rates.phase_name == "Powerplay"].set_index("season")
print("Powerplay boundary % 2008 -> 2024:", pp_rates.boundary_pct[2008], "->", pp_rates.boundary_pct[2024],
      "| dot-ball %:", pp_rates.dot_pct[2008], "->", pp_rates.dot_pct[2024])
fms_all = pd.read_sql("SELECT s.year, AVG(inn1_total_runs) AS avg_first_innings FROM fact_match_summary f "
                      "JOIN dim_season s USING (season_key) WHERE match_status = 'completed' GROUP BY 1", con)
print("Average first-innings total:", fms_all.set_index("year").avg_first_innings.round(1).loc[[2008, 2022, 2023, 2024]].to_dict())
"""),
    md(r"""
**Finding.** The Powerplay run rate rose from 7.70 to 9.46 runs per over between 2008 and 2024
(+23%), against +10.5% for the Middle overs and +12.7% for the Death overs. Most of that jump is
recent: +21% between 2022 and 2024 alone, the first two seasons of the Impact Player rule. Batters
now hit a boundary off 24.9% of balls faced in the Powerplay (19.7% in 2008) and the dot-ball
share has fallen from 49.7% to 42.0%. Average first-innings totals went from 171 in 2022 to 190
in 2024. The common belief is that T20 scoring grew through Death-overs hitting; the data says the
biggest change since 2022 is at the start of the innings. (Association only: the rule change is a
plausible cause, not a proven one.)
"""),
    md(r"""### Insight 2. Winning the Powerplay is a strong but not decisive signal"""),
    code(r"""
display(Image(FIGS / "q6_powerplay_win_rate.png", width=760))
display(res["q6_powerplay_correlation"])
res["q6_powerplay_win_rate"]
"""),
    md(r"""
**Finding.** Across 1,055 completed, full-length matches, the side with the higher Powerplay run
rate won 65.5% of the time. The effect is graded: when the team batting first out-scores the
chasers' Powerplay by more than 3 runs an over it wins 82% of matches; when it is out-scored by
more than 3 an over it wins only 19%. The point-biserial correlation between the Powerplay
run-rate difference and the result is 0.36, so the first six overs carry real information, but a
third of matches are still won by the side that lost the Powerplay.
"""),
    md(r"""### Insight 3. The toss itself is a coin flip; the decision after it is not"""),
    code(r"""
display(res["q5_toss_overall"])
field_share = pd.read_sql("SELECT s.year, ROUND(100.0 * AVG(toss_decision = 'field'), 1) AS pct_chose_field "
                          "FROM fact_match_summary f JOIN dim_season s USING (season_key) GROUP BY 1", con)
print(field_share.set_index("year").pct_chose_field.loc[[2008, 2012, 2016, 2019, 2022, 2024]].to_dict())
res["q5_toss_by_venue"].head(8)
"""),
    md(r"""
**Finding.** Toss winners won 50.8% of decided matches, which is no better than chance. But toss
winners who chose to **field** won 53.9% (377 of 700) against 45.4% (177 of 390) for those who
chose to bat; a chi-square test of independence gives χ² = 6.86, p = 0.009. Captains have learned
this: the share choosing to field moved between 35% and 66% a season before 2014, then stayed above
80% every season from 2016 to 2019. No
single venue shows a significant toss effect on its own (all p > 0.05 with 27–118 matches each), so
the overall effect is small and should not be over-read at ground level.
"""),
    md(r"""### Insight 4. A player's "phase" is not a fixed trait"""),
    code(r"""
display(res["q1_drift_summary"])
moves = res["q1_drift_moves"]
display(moves.pivot_table(index=["role_type", "from_phase"], columns="to_phase", values="n", fill_value=0))
res["q1_worked_examples"]
"""),
    md(r"""
**Finding.** Among players with at least two qualifying seasons (60+ balls), 115 of 188 batters
(61%) and 134 of 241 bowlers (56%) changed their primary phase at least once. The result holds at
a stricter 120-ball threshold (63% of batters, 54% of bowlers), so it is not small-sample noise.
The *type* of move differs by role: 90% of batters' moves (241 of 269) involve the Middle overs,
which is a batter moving one slot up or down the order, while 47% of bowlers' moves (127 of 271)
are straight swaps between the Powerplay and the Death, the two specialist new-ball and
end-of-innings roles. Scouting a player by "he is a Death bowler" is therefore a statement about
one season, not about the player.
"""),
    md(r"""### Supporting views: venues and teams"""),
    code(r"""
display(Image(FIGS / "q4_venues.png", width=640))
display(Image(FIGS / "q3_team_powerplay_heatmap.png", width=760))
"""),
    md(r"""
Dharamsala (184) and the Brabourne (178) have the highest average first-innings totals but few
matches; among grounds with many matches, Bengaluru's Chinnaswamy (174 over 90 matches) is the
high-scoring outlier. At Jaipur's Sawai Mansingh the side batting first won only 35% of 57
matches. The franchise heatmap shows the league-wide jump in 2023–24, with SRH and KKR posting the
highest Powerplay run rates of any team-season in 2024.
"""),

    # ------------------------------------------------------------------ ML
    md(r"""
## 7. Machine learning: does the Powerplay predict the winner?

**Task.** Binary classification. Target `bat_first_won` = 1 if the team batting first won.
Only completed, full-length matches without a Super Over or D-L are used (1,055 matches).

**Two prediction points**, so the model never sees information from after the moment it predicts:

* **Model A**: after the first-innings Powerplay (that Powerplay, toss, venue history, both teams'
  previous-season win %).
* **Model B**: after both Powerplays (adds the chasing side's Powerplay).

**Algorithms.** Logistic regression (interpretable, linear), a decision tree (readable rules) and
a random forest (non-linear, lower variance), each compared with two baselines: always predicting
the training majority class, and a cricket rule of thumb ("higher Powerplay run rate wins").

**Methodology.**
* Chronological split by season: train 2008–2021, validation 2022, test 2023–2024. A random split
  would let the model learn from future seasons.
* Preprocessing (median imputation, scaling) sits inside a scikit-learn `Pipeline`, so it is fitted
  on training folds only.
* Hyper-parameters are chosen by **forward-chaining cross-validation**: each fold trains on all
  earlier seasons and validates on the next one (14 folds), scored by ROC-AUC.
* The final models are refitted on train + validation and score the test seasons **once**.
"""),
    code(r"""
mres = ml.run(P)
MLF = EXPORT / "ml" / "figures"
display(mres["split"])
cv = mres["cv_results"]
cv.loc[cv.groupby(["feature_set", "model"]).cv_roc_auc.idxmax(),
       ["feature_set", "model", "C", "max_depth", "min_samples_leaf", "folds", "cv_roc_auc"]]
"""),
    code(r"""
m = mres["metrics"]
test = m[m.split == "test"][["feature_set", "model", "params", "accuracy", "precision", "recall", "f1", "roc_auc"]]
display(test.round(3))
display(Image(MLF / "model_comparison.png", width=820))
"""),
    code(r"""
display(Image(MLF / "roc_test.png", width=820))
display(Image(MLF / "confusion_matrices.png", width=820))
"""),
    code(r"""
imp = mres["feature_importance"]
display(imp[imp.feature_set == "B"].pivot_table(index="feature", columns="model", values="value")
        .sort_values("random_forest", ascending=False).round(3))
display(Image(MLF / "decision_tree_model_B.png", width=900))
"""),
    code(r"""
preds = mres["test_predictions"]
lr_b = preds[(preds.feature_set == "B") & (preds.model == "logistic_regression")]
print("Model B logistic regression accuracy by test season:", lr_b.groupby("season").correct.mean().round(3).to_dict())
feats = pd.read_csv(EXPORT / "ml_features.csv")
print("Batting-first win rate, training seasons vs test seasons:",
      round(feats[feats.season <= 2021].bat_first_won.mean(), 3), "vs",
      round(feats[feats.season >= 2023].bat_first_won.mean(), 3))
ups = mres["upsets"]
print("Confident (>= 70%) wrong predictions on the test seasons:")
ups.groupby(["feature_set", "model"]).size()
"""),
    md(r"""
**Results and interpretation.**

* **Model A (first-innings Powerplay only)** is weak. The best model, logistic regression, reaches
  60.6% accuracy and ROC-AUC 0.66 on 2023–24, no better than the one-line rule "batting first
  wins if its Powerplay run rate is above the training median" (59.2%, AUC 0.67). Six overs of one
  innings say little about a 40-over match.
* **Model B (both Powerplays)** is clearly better: logistic regression 68.3% accuracy, precision
  0.72, recall 0.64, F1 0.68, ROC-AUC 0.73; the random forest has the best AUC (0.75) but lower
  accuracy (66.2%). Both beat the majority baseline (47.9%) by a wide margin, **but only just beat
  the rule "higher Powerplay run rate wins" (66.9%, AUC 0.73)**. The honest conclusion is that most
  of the signal is captured by one subtraction; the models add one or two percentage points.
* **What drives it.** The strongest single feature in every Model B is the *chasing side's
  Powerplay wickets*, not a run rate: it is the root split of the decision tree, the largest
  logistic-regression coefficient and a quarter of the forest's importance. In the seasons the
  final models were fitted on (2008–2022), chasers who lost at most one Powerplay wicket won 71%
  of the time; those who lost two or
  more won 36%. Team form from the previous season and venue history add almost nothing.
* **Where it underperforms.** Recall for batting-first wins is only 0.64 (27 of 74 missed), and
  2023 was harder than 2024 (66% vs 70% accuracy). The base rate also shifted: batting first won
  45% of training matches but 52% of test matches, which is why the majority baseline falls below
  50%. The Impact Player rule from 2023 changed the game the model was trained on; a 2025 model
  should weight recent seasons more. With 142 test matches, one match is 0.7 percentage points of
  accuracy, so differences of 1–2 points between models are within noise.
"""),

    # ------------------------------------------------------------------ Power BI
    md(r"""
## 8. Export for the Power BI dashboard
The dashboard reads one workbook, `data/export/powerbi/IPL_PowerBI_Data.xlsx` (one Excel table per
sheet, also written as CSVs), containing the star-schema tables with names denormalised for easy
slicing, plus the model outputs (test predictions vs actual, metrics and feature importance). The
Power BI project built on it is `dashboard/IPL_Scorebook/`; its relationships and DAX measures are
listed in Appendix B.
"""),
    code(r"""
pbi = powerbi.run(P)
pd.DataFrame([(k, len(v), len(v.columns)) for k, v in pbi.items()], columns=["table", "rows", "columns"])
"""),

    # ------------------------------------------------------------------ limitations
    md(r"""
## 9. Limitations

* **What the data cannot tell us.** There is no ball-tracking, field-placement, pitch or weather
  data, no batting order and no information on the Impact Player substitutions themselves, so we
  can describe *when* players bat or bowl but not *why* their role changed, and we cannot separate
  the Impact Player rule from other changes in 2023–24 (new venues, new franchises, player
  turnover).
* **Phase is a proxy for role.** A batter's phase share depends on how long the batters above him
  last. A top-order batter on a strong side can look like a Death batter in a season when the
  openers kept going. The phase index removes the league-wide effect, not the team effect.
* **Thresholds are choices.** Who counts as having "changed phase" depends on the 60-ball
  qualification threshold; we report 120 balls as well, and the headline percentages move by only
  2–3 points, but individual players can flip.
* **Wrangling decisions that could bias results.** Renamed grounds are merged (Feroz Shah Kotla
  and Arun Jaitley Stadium are one venue), which assumes the pitch did not change with the name;
  franchises keep their history across renames (Delhi Daredevils → Delhi Capitals), which assumes
  continuity; 7-ball overs are kept as bowled; shortened, D-L and Super Over matches are left out
  of the ML set (40 matches), which slightly favours "normal" games.
* **Small test set and a moving target.** 142 test matches give wide confidence intervals, and the
  game itself changed between training and test seasons.
* **Correlation, not causation.** The toss and Powerplay findings are associations in
  observational data.

## 10. Conclusion
The wrangling work (entity resolution of 19 team strings and 58 venue strings, the legal-ball and
phase logic, a delivery-grain star schema with SCD Type 2 history and nine validation gates) is
what makes the questions answerable at all. The answers: most players' primary phase is not
stable from season to season; the Powerplay has changed more than any other phase since the Impact
Player rule; and while the two Powerplays predict the winner about two-thirds of the time, most of
that signal is captured by a one-line rule, with Powerplay wickets in the chase mattering more
than Powerplay runs.
"""),
    *tests_section(),
    *powerbi_section(),
    code(r"""con.close()
print("Notebook finished without errors.")"""),
]

nb = nbf.v4.new_notebook()
nb.cells = cells
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nb.metadata["language_info"] = {"name": "python"}
nbf.write(nb, OUT)
print("wrote", OUT.name)
