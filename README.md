# IPL Phase-Performance and Style-Drift Data Warehouse

Data Wrangling course project (NMIMS MPSTME, B.Tech CSE-DS). A dimensional data warehouse built
from public IPL ball-by-ball data. It answers two questions:

1. **Style drift.** Does the phase of the innings (Powerplay 1–6, Middle 7–15, Death 16–20) in which
   a player mostly bats or bowls stay the same from season to season? Who changed, and by how much?
2. **Powerplay signal.** How much of a match result can be predicted from the first six overs?

The full plan is in [`docs/IPL_DW_Project_Document.docx`](docs/IPL_DW_Project_Document.docx).

## Status

| Phase | Status |
|-------|--------|
| 0. Setup and scoping | Done: repository, environment, structure |
| 1. Extraction and profiling | Code done (E1–E3). **Waiting for the real dataset** in `data/raw/` |
| 2. Cleaning | Code done (E4–E6). Seed mapping tables in `mappings/` to be confirmed against the real data |
| 3. Warehouse design and load | Code done: DDL, dimensions, facts, gates G1–G9 (E7–E9, E11) |
| 4. Transformation and SCD2 | Code done: phase index, SCD Type 2 profile, drift table, sensitivity (E10) |
| 5. Insights | Code done: `src/analysis.py` + `notebooks/03_insights` (six section-10 questions, figures) |
| 6. Machine learning | Code done: `src/ml.py` + `notebooks/04_ml` (baselines, LR, tree, forest, season split) |
| 7. Dashboard | Code done: Streamlit app `dashboard/app.py` (three pages, filters, tooltips) |
| 8. Report and presentation | To do |

Everything has only been run on a **synthetic test fixture** so far (`tests/synthetic.py`). No
numbers in this repository are real IPL results yet, and the "Finding" cells in the notebooks are
still to be written from the real data.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 1. Download the Kaggle IPL dataset (matches.csv + deliveries.csv, 2008 onwards)
#    and put both files, unchanged, in data/raw/

# 2. Run the whole ETL; provenance goes to logs/extraction_log.csv
python -m src.pipeline --source-url "<kaggle dataset url>" --dataset-version "<version>"

# 3. Analysis (Phase 5) and models (Phase 6): tables and figures in data/export/analysis and data/export/ml
python -m src.analysis
python -m src.ml

# 4. Dashboard (Phase 7)
streamlit run dashboard/app.py

# 5. Notebooks: open notebooks/01-04 in Jupyter / VS Code and "Run All"

# Tests (use the synthetic fixture, not your data)
python -m pytest -q
```

The run exits with code 1 and stops before exporting if any gate fails. If G6 fails, a team or
venue string is not in `mappings/`: check `logs/unmapped_entities.csv`, add a row to
`mappings/teams.csv` or `mappings/venues.csv`, and run again. If the dataset covers fewer seasons
than 2008–2024, pass `--expected-franchises N`.

## Pipeline

| Step | Module | Output |
|------|--------|--------|
| E1 Register raw files (SHA-256, row counts) | `src/extract.py` | `logs/extraction_log.csv` |
| E2 Stage unchanged | `src/extract.py` | `stg_matches`, `stg_deliveries` |
| E3 Profile; test the 10 expected issues | `src/profiling.py` | `logs/profiling_report.csv`, `logs/data_quality_findings.csv` |
| E4 Canonicalise teams, venues, players | `src/clean.py` | `data/clean/map_*.csv`, `logs/cleaning_log.csv`, `logs/player_fuzzy_candidates.csv` |
| E5 Normalise (dates, season year, overs 1–20, structural nulls) | `src/clean.py` | `clean_matches`, `clean_deliveries` |
| E6 Flags (match status, Super Over, D/L, legal balls) | `src/clean.py` | flag columns |
| E7 Dimensions with surrogate keys | `src/transform.py` | `dim_*` |
| E8 `fact_delivery` (delivery_seq, phase) | `src/transform.py` | `fact_delivery` |
| E9 Aggregate facts | `src/transform.py` | `fact_match_summary`, `fact_player_season_phase` |
| E10 SCD Type 2 player phase profile | `src/scd2.py` | `dim_player_phase_profile`, drift table |
| E11 Validation gates G1–G9 | `src/validate.py` | `logs/validation_report.csv`, `logs/g4_exceptions.csv` |
| E12 Export for dashboard and ML | `src/export.py`, `src/features.py` | `data/export/*.csv` |
| Phase 5 insights | `src/analysis.py` | `data/export/analysis/` (tables + figures) |
| Phase 6 models | `src/ml.py` | `data/export/ml/` (metrics, CV, importances, upsets, tree) |

Everything is orchestrated by `src/pipeline.py`. Each run rebuilds `db/ipl_dw.sqlite` from the raw
files, so the pipeline is re-runnable and deterministic.

## Warehouse

Star schema in [`sql/ddl.sql`](sql/ddl.sql); analysis views in [`sql/views.sql`](sql/views.sql);
column-level data dictionary in [`docs/data_dictionary.csv`](docs/data_dictionary.csv)
(regenerate with `python -m src.dictionary`).

- **Facts:** `fact_delivery` (match × inning × delivery_seq), `fact_match_summary` (match),
  `fact_player_season_phase` (player × season × role × phase).
- **Dimensions:** `dim_match`, `dim_team` (Type 2 on name), `dim_venue`, `dim_player`,
  `dim_season`, `dim_phase`, `dim_player_phase_profile` (Type 2 on primary phase).

**Phase index.** `phase_share` = a player's balls in a phase ÷ their balls that season;
`phase_index` = `phase_share` ÷ the league's `phase_share` for the same role and season. The index
corrects for the Middle overs having 9 of the 20 overs. `primary_phase` is the phase with the
highest index, for player-seasons with at least 60 balls (also reported at 120).

## Validation gates

| Gate | Check |
|------|-------|
| G1 | Every foreign key resolves |
| G2 | No duplicate (match, inning, delivery_seq) |
| G3 | total_runs = batsman_runs + extra_runs |
| G4 | target_runs = first-innings total + 1; shortened/D-L matches listed |
| G5 | ≤ 120 legal balls per innings, ≤ 6 per Super Over innings |
| G6 | No unmapped team/venue; franchise count as expected |
| G7 | Winner is a participant or the match has no result |
| G8 | SCD2 spells do not overlap; one current row per player and role |
| G9 | Row counts reconcile raw → staging → clean → warehouse |

## Repository layout

```
data/raw/        matches.csv, deliveries.csv (untouched; not committed)
data/staging/  data/clean/  data/export/
db/              ipl_dw.sqlite (generated)
sql/             ddl.sql, views.sql
src/             extract, profiling, clean, transform, load, validate, scd2, features, export,
                 pipeline, analysis, ml, charts
mappings/        hand-maintained canonical mapping tables (teams, venues, cities, players)
notebooks/       01_profiling, 02_cleaning, 03_insights, 04_ml (build_notebooks.py regenerates them)
logs/            extraction, cleaning, validation logs (generated)
docs/            project document, decision log, data dictionary
dashboard/       Streamlit dashboard (app.py)
tests/           synthetic fixture and tests
```

Decisions (thresholds, merges, exclusions) are in [`docs/decision_log.md`](docs/decision_log.md).

## Data and licence

Ball-by-ball records originate from [Cricsheet](https://cricsheet.org) and are redistributed as
Kaggle datasets. Record the exact Kaggle URL, version, download date and licence, and cite both
sources in the report. Outputs are for coursework and analysis only, not for wagering.
