// Project explainer (study notes): every phase, how it was done, the libraries and where the code lives.
const path = require("path");
const { Paragraph, TextRun } = require("docx");
const L = require("./lib");
const { FACTS: F, p, h, bullet, numbered, table, image, caption, pageBreak, makeDoc, save, fmt, setBodySize, AlignmentType } = L;

setBodySize(21);
const W = 9026;
const FIG = (n) => path.join(L.ROOT, "reports", "figures", n);
const EX = (...a) => path.join(L.ROOT, "data", "export", ...a);

const code = (lines) => lines.map((l, i) => new Paragraph({
  children: [new TextRun({ text: l, font: "Consolas", size: 17 })],
  spacing: { after: i === lines.length - 1 ? 120 : 0, line: 230 },
  indent: { left: 360 },
  keepNext: i < lines.length - 1,
}));
const t2 = (rows, w1, opts = {}) => table(rows, [w1, W - w1], { size: 18, ...opts });
const t3 = (rows, w1, w2, opts = {}) => table(rows, [w1, w2, W - w1 - w2], { size: 18, ...opts });
const t4 = (rows, ws, opts = {}) => table(rows, [...ws, W - ws.reduce((a, b) => a + b, 0)], { size: 18, ...opts });
const gap = () => p("", { after: 60 });

const test = (fs, model) => F.ml.test.find((r) => r.feature_set === fs && r.model === model);
const pct = (x, d = 1) => (100 * x).toFixed(d);
const lrB = test("B", "logistic_regression"), rfB = test("B", "random_forest"), dtB = test("B", "decision_tree");
const ruleB = test("B", "baseline_higher_pp_rate_wins"), majB = test("B", "baseline_majority");
const lrA = test("A", "logistic_regression"), rfA = test("A", "random_forest"), dtA = test("A", "decision_tree");
const ruleA = test("A", "baseline_pp_rate_above_train_median");
const cv = (fs, model) => F.ml.cv_best.find((r) => r.feature_set === fs && r.model === model).cv_auc.toFixed(3);
const i1 = F.i1, i2 = F.i2, i3 = F.i3, i4 = F.i4, wh = F.warehouse, m = F.matches, C = F.cleaning.by_rule;
const split = Object.fromEntries(F.ml.split.map((s) => [s.part, s]));
const band = (b) => Math.round(i2.bands.find((x) => x.pp_rr_diff_band === b).bat_first_win_pct);

const children = [
  h("Project Explainer: How the IPL Data Warehouse Was Built", 0),
  p("Phase by phase: what each step does, how it was done, which library does the work and where it lives in the code", { align: AlignmentType.CENTER, after: 160 }),

  // ------------------------------------------------------------------ 0
  h("0. The project in one page", 1),
  p(`We took the two raw files of the Kaggle IPL dataset (${fmt(F.raw.matches_rows)} matches and ${fmt(F.raw.deliveries_rows)} balls, 2008 to 2024) through a layered pipeline: **raw files**, an untouched **staging** copy, a **clean** layer, a **star-schema warehouse** in SQLite, **validation gates**, and **exports**. Everything after that (insights, models, the Power BI workbook) reads only the exports or the warehouse. Each layer is built by one Python module in src/, and src/pipeline.py runs them in order. The figure shows the layers and the code behind each one.`),
  image(FIG("explainer_pipeline.png"), 5.6, { title: "Pipeline layers" }),
  caption("Figure 1. Pipeline layers, what each holds, and the module and functions that build it."),
  p("**How to run it.** The whole project rebuilds from the two raw files with these commands, or with Run All in notebooks/IPL_DW_Project.ipynb:", { after: 40 }),
  ...code([
    "python -m src.pipeline    # E1-E12: extract, profile, clean, warehouse, validate, export",
    "python -m src.analysis    # insights tables and figures  -> data/export/analysis/",
    "python -m src.ml          # models, metrics, figures      -> data/export/ml/",
    "python -m src.powerbi     # Power BI workbook             -> data/export/powerbi/",
    "python -m src.dictionary && python -m src.erd   # data dictionary and ER diagram",
  ]),

  // ------------------------------------------------------------------ 1
  h("1. Libraries and tools", 1),
  t3([
    ["Library", "What we used it for", "Where in the code"],
    ["Python standard library", "**sqlite3** for the database and all SQL; **hashlib** for SHA-256 checksums; **re** for name keys and pattern cleaning; **dataclasses** for small record types; **itertools** for the hyper-parameter grid; **argparse** for command-line options", "extract.py, load.py, validate.py, clean.py, ml.py, pipeline.py"],
    ["pandas", "Reading the CSVs as text and almost every cleaning and transformation step: map, groupby / agg, pivot-style reshaping, merge, crosstab, cut, read_sql / to_sql", "every module in src/"],
    ["numpy", "Vectorised rules (np.where, np.select) and safe division for rates", "clean.py, transform.py, features.py, ml.py"],
    ["rapidfuzz", "fuzz.ratio similarity to list look-alike player names for manual review (nothing merged automatically)", "clean.fuzzy_candidates()"],
    ["SQL (SQLite)", "Table definitions with primary keys, foreign keys and CHECK constraints; six analysis views; the validation-gate queries", "sql/ddl.sql, sql/views.sql, validate.py"],
    ["scipy.stats", "chi2_contingency (toss test) and pointbiserialr (Powerplay correlation)", "analysis.py"],
    ["scikit-learn", "LogisticRegression, DecisionTreeClassifier, RandomForestClassifier, DummyClassifier; SimpleImputer, StandardScaler, make_pipeline; accuracy, precision, recall, F1, ROC-AUC, confusion matrix, ROC curve; plot_tree", "ml.py"],
    ["matplotlib", "All report figures, the decision-tree drawing and the ER diagram", "charts.py, analysis.py, ml.py, erd.py"],
    ["openpyxl (through pandas)", "Writing the Power BI workbook, one Excel table per sheet", "powerbi.py"],
    ["Power BI Desktop and DAX", "The final three-page dashboard, built from the workbook", "Power BI Build Guide"],
    ["streamlit and altair", "A prototype dashboard used while developing (reads the same exports)", "dashboard/app.py"],
    ["nbformat, nbconvert, ipykernel", "Generating the notebooks and running them top to bottom", "notebooks/build_*.py"],
    ["pytest", "38 automated tests on a small synthetic dataset", "tests/"],
  ], 1900, 4600),

  // ------------------------------------------------------------------ 2
  h("2. Where everything lives", 1),
  t2([
    ["Folder or file", "What is inside"],
    ["data/raw/", "matches.csv and deliveries.csv exactly as downloaded (never edited)"],
    ["db/ipl_dw.sqlite", "One SQLite file holding the staging tables, the clean tables and the warehouse (rebuilt on every run)"],
    ["sql/ddl.sql, sql/views.sql", "The star schema (10 tables with keys and constraints) and the six analysis views"],
    ["src/", "One module per stage: config, extract, profiling, clean, transform, load, scd2, validate, features, export, pipeline, analysis, ml, powerbi, charts, dictionary, erd"],
    ["mappings/", "Hand-maintained canonical tables: teams.csv, venues.csv, cities.csv, players.csv"],
    ["logs/", "extraction_log, profiling_report, data_quality_findings, cleaning_log, player_fuzzy_candidates, unmapped_entities, validation_report, g4_exceptions, g5_exceptions"],
    ["data/clean/", "map_team.csv, map_venue.csv, map_player.csv: the mappings actually applied in the last run"],
    ["data/export/", "CSV copies of the dimensions, the match and player-season facts and the views; ml_features.csv; drift_table.csv; analysis/, ml/ and powerbi/ results"],
    ["notebooks/", "IPL_DW_Project.ipynb (the submission notebook) and the stage notebooks 01-04"],
    ["docs/", "Project plan, decision_log.md (D-01 to D-20), data_dictionary.csv, the ER diagram"],
    ["tests/, dashboard/, reports/", "Tests and synthetic fixture; Streamlit prototype; scripts that build the Word documents and figures"],
  ], 2400),

  // ------------------------------------------------------------------ 3
  h("3. Phase 1: Extraction (steps E1-E2)", 1),
  p("**Goal.** Get the data reproducibly, record exactly what we got, and keep an untouched copy that every later number can be traced back to."),
  numbered("**Download.** Notebook section 1 downloads the dataset archive from Kaggle's public download endpoint (urllib.request) and unzips it (zipfile) into data/raw/. No API key was needed and no rate limit was hit.", "numbers"),
  numbered("**Read everything as text.** extract.read_raw() calls pandas read_csv with dtype=str, keep_default_na=False and na_filter=False, so nothing is converted or guessed: the string \"NA\" stays \"NA\" until the cleaning step logs it.", "numbers"),
  numbered("**Checksum.** extract.sha256() hashes each file in 1 MB chunks with hashlib.", "numbers"),
  numbered("**Register (E1).** extract.register() appends one row per file to logs/extraction_log.csv: run id, file name, source URL, dataset version, download date, SHA-256, whether the checksum changed since the previous run, size, row count, column count and column names.", "numbers"),
  numbered("**Stage (E2).** extract.stage() adds a source_row number (1 to n) and writes the files unchanged to SQLite as stg_matches and stg_deliveries with DataFrame.to_sql, then re-counts the rows and stops the run if staging and file disagree.", "numbers"),
  p("**Why it was done this way.** Provenance: if the Kaggle file changes, the checksum shows it. source_row is also used later: it gives the true order of balls within an innings (delivery_seq), because ball numbers repeat after wides and no-balls.", { before: 60 }),
  ...code(["def read_raw(path):", "    return pd.read_csv(path, dtype=str, keep_default_na=False, na_filter=False)"]),

  h("3.1 Profiling (step E3)", 2),
  p("**Goal.** Measure the problems before writing any cleaning rule. profiling.column_profile() reports, for every staged column, the row count, null count and percentage (after treating NA-style tokens as missing), number of distinct values, inferred type (numeric or text), minimum, maximum and the five most common values (logs/profiling_report.csv). profiling.quality_findings() then tests the ten problems listed in the project plan and writes each as CONFIRMED or NOT FOUND with evidence (logs/data_quality_findings.csv)."),
  p(`**Result.** 8 of 10 confirmed: franchise renames, a misspelt team (Rising Pune Supergiants), the D/L column 98.1% empty, ${m.tie} ties and ${m.no_result} no-results, ${F.raw.venue_strings} venue strings with ${F.raw.na_city} missing cities, text seasons with 0-based overs, ${fmt(F.raw.wides)} wides and ${fmt(F.raw.noballs)} no-balls, and about 95% structural nulls. Not found: player-name spelling variants and duplicate (match, inning, over, ball) keys.`),

  // ------------------------------------------------------------------ 4
  h("4. Phase 2: Cleaning (steps E4-E6)", 1),
  p(`All cleaning is in src/clean.py; clean.run() calls the functions below in this order. Every rule writes a row to the cleaning log with the raw value, the clean value and the number of rows changed (${F.cleaning.rules} rules, ${fmt(F.cleaning.cells)} cell changes). The staging tables are never modified.`),
  h("4.1 Null tokens: nullify()", 2),
  p("Every value is trimmed, and any value in config.NULL_TOKENS (\"\", \"NA\", \"N/A\", \"NaN\", \"nan\", \"None\", \"none\", \"null\", \"NULL\") becomes a real missing value. This is the step that turns the 1,074 \"NA\" strings in the D/L column and the 51 in city into true NULLs."),
  h("4.2 Ball-level rules: normalise_deliveries()", 2),
  bullet("**Types.** match_id, inning, over, ball and the run columns become integers (pd.to_numeric, Int64)."),
  bullet(`**Overs.** If the smallest over is 0, every over is shifted by +1, so overs run 1-20 (${fmt(C["shift 0-based overs to 1-20"])} rows).`),
  bullet(`**Structural nulls are flagged, not imputed.** extras_type and dismissal_kind are lower-cased and a missing value becomes the category "none" (${fmt(C["structural null -> 'none'"])} cells across the two columns). player_dismissed and fielder stay NULL, because no player is involved.`),
  bullet("**Super Over innings.** is_super_over_innings = 1 when inning > 2."),
  bullet("**Grain key.** Rows are sorted by source_row (stable sort) and delivery_seq is the position within (match_id, inning): groupby(...).cumcount() + 1."),
  bullet("**Legal-ball and measure flags (E6).** These four columns are what every later run rate depends on:", 0, { after: 30 }),
  ...code([
    "is_legal_for_bowler = extras_type not in {wides, noballs}",
    "is_faced_by_batter  = extras_type != wides",
    "is_boundary         = batsman_runs in {4, 6}",
    "is_dot              = is_legal_for_bowler and total_runs == 0",
  ]),
  h("4.3 Match-level rules: normalise_matches()", 2),
  bullet("**Dates** are parsed as ISO (yyyy-mm-dd), with a day-first fallback for older versions of the file."),
  bullet(`**Season** = calendar year of the match date. The labels 2007/08, 2009/10 and 2020/21 map to 2008, 2010 and 2020 (${F.raw.season_text_rows} matches).`),
  bullet("**Result.** result_type is runs, wickets, tie or no_result; result_margin, target_runs and target_overs become numbers."),
  bullet(`**Flags (E6).** is_super_over (the super_over column is Y, or the match has innings 3+), is_dl_applied (method is not null; ${m.dl} matches, then the raw column is dropped), and match_status = no_result / tie / completed using np.select.`),
  p("Deliveries are cleaned before matches on purpose: Super Over matches are detected from the deliveries file and passed into normalise_matches().", { before: 40 }),
  h("4.4 Teams: canonical_teams() with mappings/teams.csv", 2),
  p(`clean.key() reduces a name to lower-case letters and digits. Every team string in six columns (team1, team2, toss_winner, winner, batting_team, bowling_team) is looked up by its key in mappings/teams.csv, which gives the canonical name and a stable **franchise_id** (for example DEL for both Delhi Daredevils and Delhi Capitals). ${F.raw.team_strings} strings resolve to ${wh.franchises} franchises; only the misspelling Rising Pune Supergiants is renamed (${fmt(C["team canonical name"])} cells). Any string not in the mapping is written to logs/unmapped_entities.csv, and gate G6 then stops the run.`),
  h("4.5 Venues and cities: canonical_venues()", 2),
  numbered("City names are standardised from mappings/cities.csv (Bangalore to Bengaluru, Mohali to Chandigarh).", "numbers2"),
  numbered("_strip_city_suffix() removes a trailing city, so \"Wankhede Stadium, Mumbai\" becomes \"Wankhede Stadium\".", "numbers2"),
  numbered("A manual rule in mappings/venues.csv wins where one exists (renamed grounds such as Feroz Shah Kotla to Arun Jaitley Stadium, Sheikh Zayed to Zayed Cricket Stadium).", "numbers2"),
  numbered("Otherwise spellings are grouped by their key and the most frequent spelling becomes the canonical name.", "numbers2"),
  numbered(`A missing city is filled from the venue's city (${F.raw.na_city} matches, all in Dubai and Sharjah). Result: ${F.raw.venue_strings} strings become ${wh.dim_venue} grounds.`, "numbers2"),
  h("4.6 Players: canonical_players() and fuzzy_candidates()", 2),
  p(`The "(sub)" marker is removed from substitute fielders. Names are merged only when their key is identical, or when a merge is approved in mappings/players.csv. fuzzy_candidates() compares canonical names that share a surname with rapidfuzz fuzz.ratio and lists pairs scoring 85 or more in logs/player_fuzzy_candidates.csv for a person to review. Of the ${F.cleaning.fuzzy_pairs} pairs, 13 played in the same match (for example RG Sharma and R Sharma), so they are different people, and none were merged.`),
  p("**Outputs of the cleaning phase.** clean_matches and clean_deliveries (written to SQLite by load.load_clean()), data/clean/map_team.csv, map_venue.csv and map_player.csv, logs/cleaning_log.csv, logs/player_fuzzy_candidates.csv and logs/unmapped_entities.csv."),

  // ------------------------------------------------------------------ 5
  h("5. Phase 3: Warehouse design and loading (steps E7-E9)", 1),
  h("5.1 The schema: sql/ddl.sql", 2),
  p("The star schema is defined in SQL with **PRIMARY KEY**, **REFERENCES** (foreign keys) and **CHECK** constraints, for example over BETWEEN 1 AND 20, is_wicket IN (0, 1) and toss_decision IN ('bat', 'field'). It has three fact tables at three grains, which share seven dimensions:"),
  t3([
    ["Table", "Grain (one row per)", "Main columns"],
    ["fact_delivery", "match x inning x delivery_seq", "keys to match, season, batting and bowling team, batter, bowler, non-striker, dismissed player, fielder, phase; runs; extras_type; is_wicket; the four flags"],
    ["fact_match_summary", "match", "inn1_ and inn2_ Powerplay runs, wickets, legal balls, boundaries, dot %, run rate; innings totals; bat-first and chase team; winner; bat_first_won; ml_eligible"],
    ["fact_player_season_phase", "player x season x role x phase", "balls, runs, wickets, boundaries, dots, strike rate, economy, phase_share, league_phase_share, phase_index, qualifies, is_primary_phase"],
    ["dim_match, dim_team, dim_venue, dim_player, dim_season, dim_phase", "one per entity", "surrogate key plus descriptive columns; dim_team is SCD Type 2 on the team name"],
    ["dim_player_phase_profile", "player x role x spell", "primary phase, valid_from_season, valid_to_season, is_current (SCD Type 2)"],
  ], 2300, 2050),
  p(`The column comments in ddl.sql are parsed by src/dictionary.py (regular expressions) into docs/data_dictionary.csv (118 columns), and src/erd.py draws the ER diagram from that dictionary, so the documentation cannot drift away from the real schema.`, { before: 60 }),
  h("5.2 Building dimensions and the delivery fact: src/transform.py", 2),
  bullet("**Surrogate keys.** _keys() sorts the distinct values and numbers them 1 to n, so a rerun on the same input gives the same keys."),
  bullet(`**dim_team (SCD Type 2).** For each canonical team name, the first and last season it appears; the franchise_id comes from the team mapping; is_current marks a franchise's latest name if it played in the latest season (${wh.dim_team} name spells for ${wh.franchises} franchises).`),
  bullet("**dim_season, dim_phase, dim_venue, dim_player.** Seasons from season_year; phases from config.PHASES (1 Powerplay overs 1-6, 2 Middle 7-15, 3 Death 16-20); venues with their city; every name that appears in any player column."),
  bullet("**dim_match.** One row per match, ordered by date, with foreign keys to season, venue, both teams, toss winner and player of the match."),
  bullet("**fact_delivery.** phase_of(over) turns the over into phase_key (NULL in Super Over innings); every team and player name is replaced by its dimension key."),
  h("5.3 Loading: src/load.py", 2),
  p("connect() opens SQLite with PRAGMA foreign_keys = ON. create_schema() runs ddl.sql and then views.sql. insert() first checks that the DataFrame has every column of the target table, then writes it with to_sql in chunks of 50,000 rows. Tables are inserted in WAREHOUSE_ORDER (dimensions before facts), so every foreign key already has its parent row."),

  // ------------------------------------------------------------------ 6
  h("6. Phase 4: Transformation and feature engineering (steps E9-E10)", 1),
  h("6.1 Match summary: the group-by and pivot", 2),
  p("transform._innings_stats() takes the regular innings of fact_delivery, keeps Powerplay versions of runs, wickets, legal balls, boundaries and dots (each set to 0 outside phase 1), and aggregates with groupby(match_key, inning). It then computes pp_run_rate = pp_runs x 6 / pp_legal_balls and pp_dot_pct = dots x 100 / legal balls. transform.fact_match_summary() **pivots** the result: for innings 1 and 2 each statistic is mapped onto the match row as inn1_... and inn2_... columns."),
  ...code([
    "for i in (1, 2):",
    "    part = inn[inn.inning == i].set_index(\"match_key\")",
    "    for c in stat_cols:",
    "        out[f\"inn{i}_{c}\"] = out[\"match_key\"].map(part[c])",
  ]),
  p(`It also derives the attributes the later questions need: **bat_first_team_key** (the batting team of innings 1), **chase_team_key** (the other team), **toss_winner_bat_first**, **bat_first_won** (winner = batting-first team; NULL when there is no winner) and **ml_eligible** (completed, no Super Over, no D/L, winner known, both innings present: ${fmt(m.ml_eligible)} of ${fmt(wh.fact_match_summary)} matches).`),
  h("6.2 Player-season-phase fact and the phase index", 2),
  p("transform.fact_player_season_phase() builds one row per player, season, role and phase from the regular innings. The definitions follow cricket scoring:"),
  bullet("Batting: balls = balls faced (is_faced_by_batter); runs = batsman_runs; wickets = dismissals, except retired hurt and retired not out."),
  bullet("Bowling: balls = legal balls; runs conceded = batsman_runs plus wide and no-ball extras (byes and leg-byes are not the bowler's); wickets = bowled, caught, lbw, stumped, caught and bowled, hit wicket."),
  bullet("A complete grid (a cross join with the three phases) gives every player-season-role a row for each phase, even one with zero balls."),
  p("Then the engineered feature:", { after: 30 }),
  ...code([
    "season_balls       = player's balls in all phases that season (same role)",
    "phase_share        = balls / season_balls",
    "league_phase_share = league balls in the phase / league balls (same season and role)",
    "phase_index        = phase_share / league_phase_share       # 1.0 = league average",
    "qualifies          = season_balls >= 60",
    "is_primary_phase   = highest phase_index (ties: more balls, then the earlier phase)",
  ]),
  p(`**Why the index.** In 2024 the league's batting balls were 31% Powerplay, 46% Middle and 22% Death, because the Middle phase has 9 of the 20 overs. On raw shares nearly everyone would be a Middle player; dividing by the league share removes that. Result: ${fmt(wh.fact_player_season_phase)} rows.`),
  h("6.3 SCD Type 2 player profile: src/scd2.py", 2),
  p("season_primaries() keeps one row per qualifying player, season and role with its primary phase. build_profile() then replays the seasons in order through apply_season(), exactly as a season-by-season load would maintain the dimension:"),
  bullet("No open row for the player and role: open one from this season."),
  bullet("Same primary phase as the open row: extend it (last_seen_season and qualifying_seasons go up)."),
  bullet("Different phase: close the open row (valid_to_season = its last qualifying season, is_current = 0) and open a new one."),
  bullet("Player did not qualify this season: nothing changes (the gap rule, decision D-07)."),
  p(`Result: ${fmt(wh.dim_player_phase_profile)} spells. drift_table() pairs each spell with the next one for the same player and role (groupby(...).shift(-1)) to list every change (540), with the phase indices before and after. sensitivity() rebuilds the whole chain at 60 and 120 balls to show the results do not depend on the threshold.`),

  // ------------------------------------------------------------------ 7
  h("7. Validation gates (step E11): src/validate.py", 1),
  p("Each gate is a function g1() to g9() that runs SQL against the warehouse and returns PASS or FAIL with a count. pipeline.run() stops with exit code 1, before exporting anything, if any gate fails. Results go to logs/validation_report.csv."),
  t3([
    ["Gate", "What it checks and how", "Result on the real data"],
    ["G1", "Every foreign key resolves: a LEFT JOIN from each of the 28 key columns to its dimension, counting misses, plus PRAGMA foreign_key_check", "0 failures"],
    ["G2", "Grain: GROUP BY match_key, inning, delivery_seq HAVING COUNT(*) > 1", "0 duplicates"],
    ["G3", "Run arithmetic: total_runs = batsman_runs + extra_runs on every ball", "0 failures"],
    ["G4", "Target = first-innings total + 1; mismatches explained by D/L or a shortened chase are listed", `1,090 checked, ${F.cleaning.g4_exceptions} explained`],
    ["G5", "At most 120 legal balls per innings (6 in a Super Over); an over with 7 legal balls is a listed exception, 8 or more fails", `${F.cleaning.seven_ball_overs} seven-ball overs listed`],
    ["G6", "No unmapped team or venue string; distinct franchises = 15", "pass"],
    ["G7", "The winner is one of the two teams, or the match has no winner by status", "0 failures"],
    ["G8", "SCD Type 2: no overlapping spells; exactly one current row per player and role", "0 failures"],
    ["G9", "Row counts reconcile: raw file = staging = clean = warehouse", `${fmt(F.raw.deliveries_rows)} balls and ${fmt(F.raw.matches_rows)} matches at every stage`],
  ], 700, 5500),

  h("8. Exports (step E12) and the analysis views", 1),
  p("sql/views.sql defines six views over the star schema, so the analysis and the dashboard never repeat the joins:"),
  t2([
    ["View", "What it computes"],
    ["v_league_phase_rates", "Season x phase: runs, legal balls, run rate, wickets, boundary %, dot %"],
    ["v_team_phase_profile", "Franchise x season x phase: batting run rate and wickets lost, bowling economy and wickets taken (grouped by franchise_id so renames stay together)"],
    ["v_venue_profile", "Venue: matches, average first- and second-innings totals, average first-innings Powerplay run rate, batting-first win rate"],
    ["v_player_phase_profile, v_player_drift", "SCD Type 2 spells with player and phase names, and the transitions between consecutive spells"],
    ["v_match_phase", "Match x batting franchise x innings x phase totals, small enough for dashboard filtering"],
  ], 2700),
  p("export.run() writes the six dimensions, fact_match_summary, fact_player_season_phase, the SCD Type 2 profile and five of the views to data/export/ as CSV, plus ml_features.csv (from features.build()), drift_table.csv and drift_sensitivity.csv. The 260,920-row fact_delivery stays in SQLite; reports/package_datasets.py exports it for the dataset zip. read_table() keeps integer columns that contain NULLs as integers, so a season shows as 2009, not 2009.0.", { before: 60 }),

  // ------------------------------------------------------------------ 9
  pageBreak(),
  h("9. Phase 5: How each insight is formed", 1),
  p("src/analysis.py answers the six analysis questions from the plan; analysis.run() writes the tables to data/export/analysis/ and the charts to data/export/analysis/figures/. Figure 2 shows how the cleaned columns are combined into the measures behind each insight; the sections below give the exact tables, attributes and calculations."),
  image(FIG("explainer_lineage.png"), 6.27, { title: "Attribute lineage" }),
  caption("Figure 2. From clean columns to derived attributes, aggregated measures and insights."),

  h("Insight 1: the scoring boom is front-loaded (question 2)", 2),
  t2([
    ["Source", "v_league_phase_rates = fact_delivery joined to dim_season (year) and dim_phase (phase_name); regular innings only"],
    ["Attributes", "total_runs, is_legal_for_bowler, is_faced_by_batter, is_boundary, is_dot, is_wicket, season, phase"],
    ["Calculation", "GROUP BY season, phase: run_rate = SUM(total_runs) x 6 / SUM(is_legal_for_bowler); boundary % = SUM(is_boundary) / SUM(is_faced_by_batter); dot % = SUM(is_dot) / SUM(is_legal_for_bowler). The notebook then pivots seasons against phases and computes the % change 2008-2024 and 2022-2024."],
    ["How the attributes link", "phase comes from over; the legal-ball flags come from extras_type. Without them a wide would count as a ball and there would be no phase split at all."],
    ["Result", `Powerplay run rate ${i1.Powerplay.y2008.toFixed(2)} to ${i1.Powerplay.y2024.toFixed(2)} (+${i1.Powerplay.chg_08_24}%; +${i1.Powerplay.chg_22_24}% in 2022-2024) against Middle +${i1.Middle.chg_08_24}% and Death +${i1.Death.chg_08_24}%. Powerplay boundary % ${i1.pp_boundary.y2008} to ${i1.pp_boundary.y2024}; dot % ${i1.pp_dot.y2008} to ${i1.pp_dot.y2024.toFixed(1)}. Average first-innings total ${Math.round(i1.avg_inn1["2022"])} (2022) to ${Math.round(i1.avg_inn1["2024"])} (2024).`],
    ["Code and output", "analysis.league_phase_rates(), fig_league_rates(); q2_league_phase_rates.csv and .png"],
  ], 1900),
  p("**Supporting view (question 3).** v_team_phase_profile gives each franchise's Powerplay and Death run rates by season; fig_team_heatmap() draws them as heatmaps. SRH (11.18) and KKR (11.05) had the highest Powerplay run rates of any team-season, both in 2024.", { before: 60 }),

  h("Insight 2: winning the Powerplay matters, but not decisively (question 6)", 2),
  t2([
    ["Source", `fact_match_summary, rows with ml_eligible = 1 (${fmt(i2.matches)} matches)`],
    ["Attributes", "inn1_pp_run_rate, inn2_pp_run_rate, inn1_pp_wickets, bat_first_won"],
    ["Calculation", "pp_rr_diff = inn1_pp_run_rate - inn2_pp_run_rate (powerplay_matches()). scipy.stats.pointbiserialr(bat_first_won, measure) for three measures. pd.cut splits pp_rr_diff into seven bands and the mean of bat_first_won in each band is the batting-first win rate. The rule check is the share of matches where (pp_rr_diff > 0) equals bat_first_won."],
    ["How the attributes link", "bat_first_won compares winner_key with bat_first_team_key (the batting team of innings 1). Both run rates come from the same Powerplay aggregation, so the difference compares like with like."],
    ["Result", `Correlation r = ${i2.r} for the difference (0.24 for the first-innings rate alone, -0.22 for first-innings Powerplay wickets). Win rate rises from ${band("< -3")}% (trailing by 3+ an over) to ${band("> 3")}% (leading by 3+). The side with the higher Powerplay run rate won ${i2.higher_wins}%.`],
    ["Code and output", "analysis.powerplay_vs_result(), fig_powerplay(); q6_powerplay_correlation.csv, q6_powerplay_win_rate.csv and .png"],
  ], 1900),

  h("Insight 3: the toss is a coin flip; the decision after it is not (question 5)", 2),
  t2([
    ["Source", "fact_match_summary joined to dim_venue, rows with a winner (1,090 matches)"],
    ["Attributes", "toss_decision, toss_winner_key, winner_key, venue"],
    ["Calculation", "In SQL (toss_matches()): toss_winner_won = CASE WHEN winner_key = toss_winner_key THEN 1 ELSE 0 END. pd.crosstab(toss_decision, toss_winner_won) gives a 2 x 2 table, and scipy.stats.chi2_contingency tests independence (on a 2 x 2 table scipy applies Yates' continuity correction). The same test is repeated for every venue with at least 20 decided matches."],
    ["The 2 x 2 table", `Chose to bat: ${i3.bat_won} won, ${i3.bat_n - i3.bat_won} lost. Chose to field: ${i3.field_won} won, ${i3.field_n - i3.field_won} lost.`],
    ["Result", `Toss winners won ${i3.overall}% overall. Fielding first won ${i3.field_pct}% against ${i3.bat_pct}% for batting first: chi-square = ${i3.chi2}, 1 degree of freedom, p = ${i3.p}. No single ground is significant on its own (${i3.venues_tested} grounds tested, smallest p = ${i3.venue_min_p}). The share choosing to field was ${i3.field_share_pre2014_min}-${i3.field_share_pre2014_max}% a season before 2014 and above 80% every season from 2016 to 2019.`],
    ["Code and output", "analysis.toss_matches(), toss_effect(); q5_toss_overall.csv, q5_toss_by_venue.csv"],
  ], 1900),

  h("Insight 4: a player's phase is not a fixed trait (question 1)", 2),
  t2([
    ["Source", "dim_player_phase_profile (SCD Type 2) and the drift table built from it; drift_sensitivity for the 120-ball check"],
    ["Attributes", "player_key, role_type, primary_phase_key, valid_from_season, valid_to_season; underneath them phase_index and balls from fact_player_season_phase"],
    ["Calculation", "Players with 2 or more qualifying seasons are the base. A player-role with more than one spell has changed phase. drift_summary() counts changes and players by role, and groups transitions by from_phase and to_phase; worked_examples() lists the changes with the largest rise in the new phase's index."],
    ["How the attributes link", "over > phase_key > balls per phase > phase_share > (divided by league share) phase_index > is_primary_phase > spells > transitions. Each step is one function in transform.py or scd2.py."],
    ["Result", `${i4.batting_60.changed} of ${i4.batting_60.pool} batters (${i4.batting_60.pct}%) and ${i4.bowling_60.changed} of ${i4.bowling_60.pool} bowlers (${i4.bowling_60.pct}%) changed at least once; at 120 balls ${i4.batting_120.pct}% and ${i4.bowling_120.pct}%. ${i4.bat_middle_pct}% of batters' moves (${i4.bat_middle_moves} of ${i4.bat_moves}) involve the Middle overs; ${i4.bowl_ppdeath_pct}% of bowlers' moves (${i4.bowl_ppdeath_moves} of ${i4.bowl_moves}) are Powerplay-Death swaps.`],
    ["Code and output", "scd2.drift_table(), scd2.sensitivity(), analysis.drift_summary(), worked_examples(); q1_drift_summary.csv, q1_drift_moves.csv, q1_worked_examples.csv"],
  ], 1900),
  p("**Supporting view (question 4).** v_venue_profile averages inn1_total_runs, inn2_total_runs, inn1_pp_run_rate and bat_first_won by venue from fact_match_summary joined to dim_venue; venue_profile() keeps grounds with 10 or more matches. Dharamsala is highest (184 over 13 matches); Chinnaswamy, Bengaluru (174 over 90) is the reliable high-scoring ground; at Jaipur the side batting first won only 35% of 57 matches.", { before: 60 }),

  h("9.1 Attribute link map", 2),
  p("The derived attributes that connect the raw columns to the insights and the model, with where each one is defined:", { after: 40 }),
  t4([
    ["Attribute", "Built from", "Rule", "Defined in"],
    ["phase_key", "over", "1-6 = 1, 7-15 = 2, 16-20 = 3; NULL in Super Overs", "transform.phase_of()"],
    ["is_legal_for_bowler", "extras_type", "not a wide or no-ball", "clean.normalise_deliveries()"],
    ["is_faced_by_batter", "extras_type", "not a wide", "clean.normalise_deliveries()"],
    ["is_boundary, is_dot", "batsman_runs, total_runs, legal flag", "4 or 6 off the bat; legal ball with 0 runs", "clean.normalise_deliveries()"],
    ["delivery_seq", "source_row", "order within (match, inning)", "clean.normalise_deliveries()"],
    ["season_year, match_status", "date, result", "year of the date; no_result / tie / completed", "clean.normalise_matches()"],
    ["pp_run_rate (inn1, inn2)", "Powerplay runs and legal balls", "runs x 6 / legal balls", "transform._innings_stats()"],
    ["bat_first_team_key", "inning, batting_team_key", "batting team of innings 1", "transform.fact_match_summary()"],
    ["bat_first_won", "winner_key, bat_first_team_key", "1 if they are equal; NULL with no winner", "transform.fact_match_summary()"],
    ["ml_eligible", "status, Super Over, D/L, innings", "completed, full-length, winner known", "transform.fact_match_summary()"],
    ["phase_share, phase_index", "balls by player-season-role-phase", "share / league share", "transform.fact_player_season_phase()"],
    ["is_primary_phase", "phase_index, balls", "highest index, 60+ balls", "transform.fact_player_season_phase()"],
    ["toss_winner_won", "winner_key, toss_winner_key", "1 if they are equal", "analysis.toss_matches()"],
    ["pp_rr_diff", "inn1_pp_run_rate, inn2_pp_run_rate", "first minus second", "analysis.powerplay_matches()"],
  ], [1900, 2200, 2600], { size: 17 }),

  // ------------------------------------------------------------------ 10
  pageBreak(),
  h("10. Phase 6: Machine learning", 1),
  h("10.1 How we came up with the idea", 2),
  bullet("**From the second research question.** The plan asked how much of a match result the first six overs can predict, once toss, venue and team history are accounted for. Every past match has a known winner, so this becomes **supervised binary classification**."),
  bullet("**Why \"the team batting first wins\" as the target.** Every match has exactly one batting-first side, so the label means the same thing in every match, and the features line up: innings 1 is always batting first, innings 2 always the chase."),
  bullet("**Why two prediction points.** Broadcast win-probability graphics update as a match goes on, so we measured the value of information at two moments: **Model A** after the first-innings Powerplay and **Model B** after both Powerplays. Each uses only what is known at that moment, which is also our main protection against leakage."),
  bullet("**Why baselines.** Cricket wisdom says \"win the Powerplay, win the match\". We turned it into a rule baseline to test whether machine learning adds anything, and added the majority-class baseline as the floor."),
  bullet("**Why these three algorithms.** Logistic regression is linear and interpretable through its coefficients; a depth-limited decision tree gives readable rules and covers course unit 7; a random forest averages many trees, so it can capture non-linear effects with less variance."),

  h("10.2 Data and features: src/features.py", 2),
  p(`features.build() reads fact_match_summary joined to dim_match, dim_season and dim_team, adds the history features, and keeps the ${fmt(m.ml_eligible)} rows with ml_eligible = 1. The result is data/export/ml_features.csv.`),
  t4([
    ["Feature", "Meaning", "Built from", "Leakage guard"],
    ["inn1_pp_runs, _wickets, _run_rate, _boundaries, _dot_pct", "Batting-first Powerplay (Models A and B)", "fact_match_summary", "only the first six overs"],
    ["toss_decision_bat", "1 if the toss winner chose to bat", "toss_decision", "known before play"],
    ["toss_winner_bat_first", "1 if the toss winner bats first", "toss_winner_key vs bat_first_team_key", "known before play"],
    ["venue_avg_first_innings_prior", "The venue's average first-innings total in earlier matches (league average if none)", "inn1_total_runs, venue_key", "expanding mean shifted by one match"],
    ["bat_first_ / chase_prev_season_win_pct", "Each franchise's win % in the previous season (0.5 if it has none)", "bat_first_won by franchise and season", "previous season only"],
    ["inn2_pp_ (same five)", "Chasing Powerplay (Model B only)", "fact_match_summary", "only the first six overs"],
  ], [2500, 2550, 1900], { size: 17 }),
  p("Never used as features: result_margin, player_of_match, winner and target_runs (target_runs is known only after the first innings ends, so it would leak into Model A).", { before: 60 }),

  h("10.3 How the models were trained: src/ml.py run()", 2),
  numbered("Read ml_features.csv; a missing previous-season win % (first season, or a new franchise) becomes a neutral 0.5 (decision D-17).", "numbers3"),
  numbered(`season_split(): train ${split.train.seasons.split(" ")[0]}-2021 (${split.train.matches} matches), validation 2022 (${split.val.matches}), test 2023-2024 (${split.test.matches}).`, "numbers3"),
  numbered("make_model() builds a scikit-learn Pipeline: SimpleImputer(median), then StandardScaler (logistic regression only), then the model; random_state = 42 for the tree and the forest, which has 300 trees.", "numbers3"),
  numbered("tune() tries every grid combination (itertools.product): logistic regression C in {0.01, 0.1, 1, 10}; tree max_depth in {2, 3, 4, 5} x min_samples_leaf in {5, 20}; forest max_depth in {3, 5, None} x min_samples_leaf in {5, 20}.", "numbers3"),
  numbered("forward_folds() makes 14 folds over 2008-2022: each fold trains on all seasons before season s and validates on s. The setting with the best mean ROC-AUC is kept.", "numbers3"),
  numbered("The tuned model is fitted on 2008-2021 and scored on 2022 (reported), then refitted on 2008-2022 and scored on 2023-2024 once: metrics() gives accuracy, precision, recall, F1, ROC-AUC and the confusion matrix.", "numbers3"),
  numbered("baselines() scores the majority class (DummyClassifier) and the rule on the same test seasons. importance() reads logistic-regression coefficients (standardised features) or tree and forest feature_importances_; wrong predictions made with 70%+ confidence are saved as upsets; plot_tree() draws the tree.", "numbers3"),
  ...code([
    "make_pipeline(SimpleImputer(strategy=\"median\"), StandardScaler(), LogisticRegression(C=...))",
    "for s in seasons[1:]:                      # forward-chaining folds",
    "    train = df.season < s;  validate = df.season == s",
  ]),

  h("10.4 Results on the test seasons (2023-2024)", 2),
  table([
    ["Set", "Model", "Accuracy %", "Precision", "Recall", "F1", "ROC-AUC", "CV ROC-AUC"],
    ...[["B", "Majority-class baseline", majB, "-"], ["B", "Rule: higher PP run rate wins", ruleB, "-"],
      ["B", "Logistic regression", lrB, cv("B", "logistic_regression")], ["B", "Decision tree", dtB, cv("B", "decision_tree")],
      ["B", "Random forest", rfB, cv("B", "random_forest")], ["A", "Rule: PP run rate above median", ruleA, "-"],
      ["A", "Logistic regression", lrA, cv("A", "logistic_regression")], ["A", "Decision tree", dtA, cv("A", "decision_tree")],
      ["A", "Random forest", rfA, cv("A", "random_forest")]]
      .map(([fs, n, r, c]) => [fs, n, pct(r.accuracy), r.precision.toFixed(2), r.recall.toFixed(2), r.f1.toFixed(2), r.roc_auc.toFixed(2), c]),
  ], [550, 2650, 1000, 950, 850, 750, 1000, W - 7750], { size: 17, align: [AlignmentType.CENTER, null, AlignmentType.RIGHT, AlignmentType.RIGHT, AlignmentType.RIGHT, AlignmentType.RIGHT, AlignmentType.RIGHT, AlignmentType.RIGHT] }),
  p("CV ROC-AUC is the mean over the 14 forward-chaining folds on 2008-2022; it is the number the settings were chosen by.", { size: 18, before: 40 }),
  image(EX("ml", "figures", "roc_test.png"), 5.4, { title: "ROC curves" }),
  caption("Figure 3. ROC curves on the test seasons for Model A (left) and Model B (right)."),

  h("10.5 Which is better, and how we decided", 2),
  p(`**Model B is better than Model A.** Test accuracy ${pct(lrB.accuracy)}% against ${pct(lrA.accuracy)}% and ROC-AUC ${lrB.roc_auc.toFixed(2)} against ${lrA.roc_auc.toFixed(2)} for logistic regression, and the cross-validation AUC shows the same gap (${cv("B", "logistic_regression")} against ${cv("A", "logistic_regression")}), so it is not luck of one test set. The reason is information: Model B sees the chasing side's Powerplay, and in particular how many wickets the chase lost, which Model A cannot know. Model A is no better than its rule baseline (${pct(lrA.accuracy)}% against ${pct(ruleA.accuracy)}%), because six overs of one innings say little about a 40-over match.`),
  p(`**Within Model B, logistic regression is our headline model.** It had the best cross-validation AUC (${cv("B", "logistic_regression")}), which is how we chose before looking at the test seasons, and it also has the best test accuracy (${pct(lrB.accuracy)}%) and F1 (${lrB.f1.toFixed(2)}). The random forest has a slightly higher test AUC (${rfB.roc_auc.toFixed(2)}) but lower accuracy (${pct(rfB.accuracy)}%) and a lower CV AUC (${cv("B", "random_forest")}). The decision tree is weakest (${pct(dtB.accuracy)}%, AUC ${dtB.roc_auc.toFixed(2)}), because a depth-3 tree uses only a few features. One match is 0.7 points of accuracy, so logistic regression and the forest are practically tied; we prefer logistic regression because it is simpler and its coefficients explain the result.`),
  p(`**Against the baselines.** All models beat the majority class (${pct(majB.accuracy)}%) by a wide margin, but the best model is only ${(100 * (lrB.accuracy - ruleB.accuracy)).toFixed(1)} points above the rule "higher Powerplay run rate wins" (${pct(ruleB.accuracy)}%, AUC ${ruleB.roc_auc.toFixed(2)}). The honest conclusion is that most of the signal is a single subtraction; the models confirm it and add the wickets effect.`),
  p("**How \"better\" was judged.** Every model is scored on the same 142 test matches, which were used once. Accuracy measures overall correctness, F1 balances precision and recall, and ROC-AUC measures how well the predicted probabilities rank batting-first wins above chase wins at every threshold. Settings were chosen by cross-validation AUC only, so the test set never influenced a choice."),

  h("10.6 What the model learned, and where it fails", 2),
  bullet(`**Chasing side's Powerplay wickets is the strongest feature.** It is the decision tree's first split (inn2_pp_wickets <= 1.5), the largest logistic-regression coefficient (+0.70: more chase wickets, more likely batting first wins) and ${Math.round(100 * F.ml.rf_b_top[0].value)}% of the forest's importance. In 2008-2022, chasers who lost at most one Powerplay wicket won ${F.ml.chase_win_le1_wkt}% of matches; two or more, ${F.ml.chase_win_ge2_wkt}%.`),
  bullet("Next come first-innings Powerplay wickets (coefficient -0.35), chasing Powerplay boundaries (-0.26) and first-innings Powerplay runs and run rate (about +0.16). Previous-season form, venue history and the toss add almost nothing."),
  bullet(`**Where it underperforms.** Recall for batting-first wins is ${lrB.recall.toFixed(2)} (${lrB.fn} of ${lrB.fn + lrB.tp} missed); 2023 was harder than 2024 (${F.ml.lr_b_by_season["2023"]}% against ${F.ml.lr_b_by_season["2024"]}%); the base rate moved from ${F.ml.bat_first_win_train}% batting-first wins in training to ${F.ml.bat_first_win_test}% in the test seasons, which is why the majority baseline is below 50%.`),

  // ------------------------------------------------------------------ 11
  h("11. Phase 7: The dashboard", 1),
  p("**Power BI data: src/powerbi.py.** build() queries the warehouse and the model outputs into 18 tables: dimensions (Season with an era column, Phase, Venue with country and a short name, Franchise, Team, Player, Role, FeatureSet, Model), facts with names already joined (Matches, TeamMatches, InningsPhase, PlayerSeasonPhase, PhaseSpells, PhaseChanges) and model outputs (ModelMetrics, TestPredictions, FeatureImportance). TeamMatches stacks a batting-first row and a chasing row for every match, so team win % is one AVERAGE; TestPredictions adds team names and confidence = max(p, 1 - p) to each prediction. write() saves them with pandas ExcelWriter (openpyxl), one Excel table per sheet, plus CSV copies."),
  p("**In Power BI.** The workbook is imported, one-to-many relationships are drawn from the dimension tables to the facts, and DAX measures do the arithmetic (for example Run Rate = DIVIDE(SUM(runs) * 6, SUM(legal_balls))). The three pages are the overview, teams and players (with the franchise-to-phase drill-down) and model insights; the Power BI Build Guide lists every visual and measure."),
  p("**Prototype.** dashboard/app.py is a Streamlit app (charts in altair) with the same three pages; it reads data/export/ and is tested automatically with streamlit's AppTest."),

  h("12. Phase 8: Notebook, tests and documents", 1),
  bullet("**Notebook.** notebooks/build_submission_notebook.py writes IPL_DW_Project.ipynb with nbformat; it is run with jupyter nbconvert --execute. The notebook runs the pipeline and re-derives key tables in plain pandas as cross-checks (the match pivot and the 2024 phase index both match the warehouse exactly)."),
  bullet("**Tests.** tests/synthetic.py generates a small fake IPL dataset with the same problems; conftest.py builds a whole project from it. The 38 pytest tests check the cleaning rules, that each gate catches the corruption it is designed for, the SCD Type 2 rules, and that analysis, models and dashboard run."),
  bullet("**Documents.** reports/facts.py collects every quoted number from the outputs into facts.json, and the Node scripts in reports/ build the Word documents from it, so no number is typed by hand. Every modelling decision has an ID in docs/decision_log.md."),

  h("13. Quick finder: if you are asked about X, open Y", 1),
  t2([
    ["Topic", "Open"],
    ["Where the data came from, checksums", "logs/extraction_log.csv; src/extract.py"],
    ["What was wrong with the raw data", "logs/data_quality_findings.csv, logs/profiling_report.csv; src/profiling.py"],
    ["Any cleaning rule and its row count", "logs/cleaning_log.csv; src/clean.py; mappings/"],
    ["The schema, keys, constraints", "sql/ddl.sql; docs/data_dictionary.csv; docs/er_diagram_keys.pdf"],
    ["Match summary, phase index", "src/transform.py: fact_match_summary(), fact_player_season_phase()"],
    ["SCD Type 2 rules", "src/scd2.py: apply_season(), build_profile(); dim_team in transform.py"],
    ["Validation gates", "src/validate.py; logs/validation_report.csv, g4_exceptions.csv, g5_exceptions.csv"],
    ["Insights and their tests", "src/analysis.py; sql/views.sql; data/export/analysis/"],
    ["Features and leakage", "src/features.py; data/export/ml_features.csv"],
    ["Models, tuning, metrics", "src/ml.py; data/export/ml/ (metrics, cv_results, test_predictions, figures)"],
    ["Dashboard data", "src/powerbi.py; data/export/powerbi/IPL_PowerBI_Data.xlsx"],
    ["Why a decision was made", "docs/decision_log.md (D-01 to D-20)"],
  ], 3300),
];

save(makeDoc(children, { title: "Project Explainer" }), path.join(L.ROOT, "submission", "09_Project_Explainer.docx"));
