// Viva preparation guide: each member's part, their slides, what to say and the questions to expect.
// Every number comes from reports/facts.json (written by reports/facts.py from the pipeline outputs).
const path = require("path");
const L = require("./lib");
const { FACTS: F, p, h, bullet, table, pageBreak, makeDoc, save, fmt, setBodySize, AlignmentType } = L;

setBodySize(21);
const W = 9026;
const M1 = "Sanjeet Singh Tuteja (L076)", M2 = "[Member 2]", M3 = "[Member 3]";
const S1 = "Sanjeet", S2 = "[Member 2]", S3 = "[Member 3]";

const test = (fs, model) => F.ml.test.find((r) => r.feature_set === fs && r.model === model);
const pct = (x, d = 1) => (100 * x).toFixed(d);
const lrB = test("B", "logistic_regression"), rfB = test("B", "random_forest"), dtB = test("B", "decision_tree");
const ruleB = test("B", "baseline_higher_pp_rate_wins"), majB = test("B", "baseline_majority");
const lrA = test("A", "logistic_regression"), ruleA = test("A", "baseline_pp_rate_above_train_median");
const i1 = F.i1, i2 = F.i2, i3 = F.i3, i4 = F.i4, wh = F.warehouse, m = F.matches;
const split = Object.fromEntries(F.ml.split.map((s) => [s.part, s]));
const band = (b) => Math.round(i2.bands.find((x) => x.pp_rr_diff_band === b).bat_first_win_pct);
const gap = (100 * (lrB.accuracy - ruleB.accuracy)).toFixed(1);
const upsLR = F.ml.upsets.find((u) => u.feature_set === "B" && u.model === "logistic_regression").n;

const qa = (rows) => table([["Likely question", "How to answer"], ...rows], [2650, W - 2650], { size: 19 });
const concepts = (rows) => table([["Concept", "Explain it like this"], ...rows], [2250, W - 2250], { size: 19 });
const numbers = (pairs) => {
  const rows = [["What", "Number", "What", "Number"]];
  for (let i = 0; i < pairs.length; i += 2) {
    const a = pairs[i], b = pairs[i + 1] || ["", ""];
    rows.push([a[0], a[1], b[0], b[1]]);
  }
  return table(rows, [2900, 1613, 2900, 1613], { size: 19 });
};
const script = (label, lines) => [
  p(`**${label}**`, { after: 40, keepNext: true }),
  table([[lines.join("\n")]], [W], { size: 20, header: false }),
  p("", { after: 60 }),
];
const show = (items) => items.map((t) => bullet(t, 0, { after: 30 }));

// ------------------------------------------------------------------ front matter
const front = [
  h("Viva Preparation Guide: Who Did What and What to Explain", 0),
  p("IPL Phase-Performance and Style-Drift Data Warehouse  |  Data Wrangling group project  |  B.Tech CSE (Data Science), Semester V", { align: AlignmentType.CENTER, after: 160 }),

  h("How this guide works", 1),
  p("The work is divided by the pipeline stages in the project guidelines (sections 4.1 to 4.7), so each member owns one part from start to finish and presents it on a continuous block of slides. Each member's section below has the same six parts: **what was done** in your part, the **concepts** you must explain, **what to say** on your slides, the **questions** to expect with answers, the **numbers** to remember, and the **files** to have open."),
  p("Replace [Member 2] and [Member 3] with your names. The contribution statement has been updated to the same split. If your group divided the work differently, swap the sections and keep the slide blocks."),

  h("1. The split at a glance", 1),
  table([
    ["Member", "Owns (guideline stages)", "Course units", "Presents", "Documents and code"],
    [M1, "Data extraction, cleaning, loading and validation (4.1, 4.2, 4.4)", "U3 Getting and Cleaning Data, U4 Data Warehousing, U6 ETL", "Slides 1-4", "Cleaning and Transformation Log; notebook sections 1-3 and 5; extract.py, clean.py, load.py, validate.py; sql/ddl.sql; mappings/"],
    [M2, "Transformation, feature engineering and insights (4.3, 4.5)", "U5 Dimensional Modelling (aggregate facts, SCD Type 2)", "Slides 5-8", "Report sections 3.3 and 4; notebook sections 4 and 6; transform.py, scd2.py, analysis.py"],
    [M3, "Machine learning, Power BI dashboard and the written report (4.6, 4.7)", "U7 Decision Trees", "Slides 9-10 and the live demo", "Report (owner); Power BI Build Guide; notebook sections 7-8; features.py, ml.py, powerbi.py"],
  ], [1700, 2050, 1700, 1050, W - 6500], { size: 18 }),
  p("", { after: 40 }),
  p("**Running order (about 3 to 4 minutes each, then questions).** Each speaker ends with a one-line handover:", { after: 40 }),
  table([
    ["Slides", "Speaker", "Handover line at the end"],
    ["1-4: cover, questions and dataset, wrangling, pipeline", S1, `"Now ${S2} will explain how we transformed this data and what it shows."`],
    ["5-8: phase index, three insight slides", S2, `"Now ${S3} will show whether the Powerplay can predict the winner."`],
    ["9-10: machine learning, dashboard demo, limitations", S3, "\"Thank you. We are happy to take questions.\""],
  ], [3600, 1400, W - 5000], { size: 19 }),

  h("2. Five things every member must know", 1),
  p("Any examiner can ask anyone these, so all three members should be able to say them without notes:", { after: 40 }),
  bullet(`**Dataset:** Kaggle "IPL Complete Dataset (2008-2024)", version 3, built from Cricsheet; two related files (matches and deliveries); ${fmt(F.raw.matches_rows)} matches, ${fmt(F.raw.deliveries_rows)} balls, 17 seasons.`),
  bullet("**Two questions:** (1) style drift: does a player's main phase of the innings stay the same each season? (2) Powerplay signal: how much of the result do the first six overs predict?"),
  bullet(`**Warehouse:** SQLite star schema, 3 fact tables and 7 dimensions, 28 foreign keys, 9 validation gates, all passing.`),
  bullet(`**Insights:** Powerplay run rate +${Math.round(i1.Powerplay.chg_08_24)}% since 2008 (most of it since 2022); higher Powerplay run rate wins ${i2.higher_wins}%; toss is a coin flip (${i3.overall}%) but fielding first wins ${i3.field_pct}%; ${i4.batting_60.pct}% of batters and ${i4.bowling_60.pct}% of bowlers change phase.`),
  bullet(`**Model:** logistic regression after both Powerplays: ${pct(lrB.accuracy)}% accuracy, ROC-AUC ${lrB.roc_auc.toFixed(2)}, only ${gap} points above the rule "higher Powerplay run rate wins"; the chasing side's Powerplay wickets matter most.`),
];

// ------------------------------------------------------------------ member 1
const member1 = [
  pageBreak(),
  h(`3. ${M1}: extraction, cleaning, loading and validation`, 1),
  h("3.1 What was done in this part", 2),
  bullet(`**Chose and sourced the dataset.** Downloaded the Kaggle archive (one 1.9 MB request, no API key, no rate limit), recorded its URL, version, date and licence (ODbL; Cricsheet data under ODC Attribution).`),
  bullet(`**Extraction (E1-E2).** SHA-256 checksum and row counts in logs/extraction_log.csv; both files staged unchanged as text in SQLite, so the raw data is never edited.`),
  bullet(`**Profiling (E3).** Tested the 10 data problems we expected before cleaning; 8 were confirmed (renames, a misspelt team, near-empty D/L column, ties and no-results, venue variants and missing cities, text seasons and 0-based overs, wides and no-balls, structural nulls).`),
  bullet(`**Cleaning (E4-E6).** ${F.cleaning.rules} logged rules changing ${fmt(F.cleaning.cells)} cells: ${F.raw.team_strings} team strings resolved to ${wh.franchises} franchises; ${F.raw.venue_strings} venue strings to ${wh.dim_venue} grounds; ${F.raw.na_city} missing cities filled by lookup; "NA" text turned into real NULLs; structural nulls flagged as "none"; season taken from the match date (${F.raw.season_text_rows} matches); overs shifted to 1-20; D/L turned into a 0/1 flag (${m.dl} matches); legal-ball flags for ${fmt(F.raw.wides)} wides and ${fmt(F.raw.noballs)} no-balls.`),
  bullet(`**Player names.** Fuzzy matching proposed ${F.cleaning.fuzzy_pairs} similar pairs; none were merged, because 13 of them played in the same match (two different people).`),
  bullet(`**Loading.** Star schema in SQLite (db/ipl_dw.sqlite) from sql/ddl.sql: 3 facts (${fmt(wh.fact_delivery)} deliveries, ${fmt(wh.fact_match_summary)} matches, ${fmt(wh.fact_player_season_phase)} player-season-phase rows), 7 dimensions, 6 views, plus CSV exports.`),
  bullet(`**Validation (E11).** Nine gates G1-G9. On the first real run G5 failed (19 innings with 121 legal balls); traced to ${F.cleaning.seven_ball_overs} seven-ball overs, kept as real umpire miscounts and listed as exceptions (decision D-20). Also added two renamed grounds to the venue mapping.`),
  bullet("**Documents.** The Cleaning and Transformation Log (found / done / left as-is and why) and the ER diagram."),

  h("3.2 Concepts you must be able to explain", 2),
  concepts([
    ["ETL", "Extract, Transform, Load. Ours runs as steps E1 to E12: register and stage the raw files, profile, clean, build dimensions and facts, validate, export."],
    ["Provenance", "Being able to trace every number back to its source. We keep raw files untouched and record a checksum, URL, version and date for each."],
    ["Flag vs impute vs drop", "Flag when the missing value has a meaning (no extra = 'none'); fill by lookup when it is certain (city from venue); leave NULL when nothing is true (winner of a no-result). We never guessed values statistically."],
    ["Entity resolution", "Mapping every spelling of the same thing to one canonical name, through hand-checked mapping tables in mappings/ (teams, venues, cities, players)."],
    ["Legal ball", "Wides and no-balls are not legal for the bowler; wides are not faced by the batter. A regular innings has at most 120 legal balls."],
    ["Grain", "What one row of a fact table means. fact_delivery is one row per (match, inning, delivery_seq)."],
    ["Surrogate key", "An integer key we assign (team_key, venue_key) instead of using the name, so a rename does not break joins."],
    ["Star schema", "Fact tables of measurements in the centre, joined to dimension tables that describe them. Conformed dimensions are shared by all facts."],
    ["Referential integrity", "Every foreign key in a fact finds its row in the dimension (gate G1 checks all 28)."],
    ["Reconciliation", "Row counts match at every stage, raw to staging to clean to warehouse (gate G9)."],
  ]),

  h("3.3 Your slides: what to say", 2),
  ...script("Slide 1: cover", [
    "Good morning. We are " + S1 + ", " + S2 + " and " + S3 + ".",
    "Our project is the IPL Phase-Performance and Style-Drift Data Warehouse.",
    "We took seventeen seasons of public IPL ball-by-ball data through the full wrangling pipeline.",
    "Then we used the warehouse for four insights, a match-outcome model and a Power BI dashboard.",
    `I will cover the data and the pipeline. ${S2} will cover the transformation and insights, and ${S3} the model and the dashboard.`,
  ]),
  ...script("Slide 2: two questions, one public dataset", [
    "We asked two questions.",
    "First, style drift: does the phase a player mostly bats or bowls in stay the same each season?",
    "Second, the Powerplay signal: how much of the result can the first six overs predict?",
    `Our data is the Kaggle IPL Complete Dataset, version 3, built from Cricsheet. It has two related files: ${fmt(F.raw.matches_rows)} matches and ${fmt(F.raw.deliveries_rows)} balls, from 2008 to 2024.`,
    "It meets every rule in the brief: real, public, more than 1,000 rows, and two tables that must be joined.",
  ]),
  ...script("Slide 3: the raw data needed real wrangling", [
    "The raw data was messy in ways that change the answers.",
    `There were ${F.raw.team_strings} team names for ${wh.franchises} franchises, and ${F.raw.venue_strings} venue names for ${wh.dim_venue} grounds.`,
    "Seasons were stored as text, like 2007/08 for IPL 2008, and overs started at zero.",
    "Our rule was: flag, don't impute, when a missing value has a meaning. An empty extras type means no extra, so we label it 'none'.",
    `We did not merge look-alike player names, because 13 of the ${F.cleaning.fuzzy_pairs} pairs played in the same match.`,
  ]),
  ...script("Slide 4: from two CSV files to a validated star schema", [
    "The pipeline has six steps and runs from one command or from the notebook.",
    "We never edit the raw files. We checksum them and stage them unchanged, so every number traces back to the source.",
    "The warehouse is a star schema in SQLite: three fact tables at three grains and seven dimensions, linked by 28 foreign keys.",
    "Nothing is exported unless nine validation gates pass.",
    `On the first real run one gate failed: 19 innings had 121 legal balls. We traced it to ${F.cleaning.seven_ball_overs} overs where the umpires allowed seven balls, kept them, and listed them as exceptions.`,
    `Now ${S2} will explain how we transformed this data and what it shows.`,
  ]),

  h("3.4 Questions to expect", 2),
  qa([
    ["Why this dataset?", "It is real and public, has two related files with about 262,000 rows, and it is genuinely messy: renamed teams, up to five names for one ground, text seasons and structural nulls. It also has a clear target (who wins) and many dashboard dimensions: season, team, venue, phase."],
    ["How did you get the data? Any constraints?", "We downloaded the public archive from Kaggle's download endpoint. It needed no API key and we hit no rate limit. The licence is ODbL, and the Cricsheet data underneath is ODC Attribution, so we credit both."],
    ["Why keep the raw files untouched?", "For provenance and reproducibility. We record a SHA-256 checksum, URL, version and date, and stage the files unchanged. If the checksum changes, we know the source changed."],
    ["How did you handle missing values?", `Three methods, each for a reason. Flag: an empty extras type means 'none'. Lookup: a missing city comes from the venue mapping (${F.raw.na_city} matches). Leave NULL: a no-result has no winner, so the outcome goes in match_status.`],
    ["Were there duplicates?", "We checked instead of assuming: zero duplicate deliveries. Ball numbers repeat after wides and no-balls, so we built our own key, delivery_seq, from the source row order. Gate G2 enforces it on every run."],
    ["How did you handle team renames?", "A rename is history, not an error. Delhi Daredevils and Delhi Capitals are two name spells of one franchise in a Type 2 dimension. Only the real misspelling, Rising Pune Supergiants, was merged. Deccan Chargers and Sunrisers Hyderabad stay separate: different owners."],
    ["Why not merge similar player names?", `Fuzzy matching proposed ${F.cleaning.fuzzy_pairs} pairs and 13 of them played in the same match, like Rohit and Rahul Sharma, so they are different people. A wrong merge mixes two careers. We merge only identical name keys.`],
    ["What is a star schema and why use one?", "Facts hold measurements at a fixed grain; dimensions describe them. Our three facts (per ball, per match, per player-season-phase) share seven dimensions, so every analysis uses the same team, venue and season definitions."],
    ["What are the validation gates? Did any fail?", `Nine SQL checks that must pass before export: keys, grain, run arithmetic, targets, legal balls, mappings, winners, SCD spells, row counts. G5 failed first: 19 innings had 121 legal balls. The cause was ${F.cleaning.seven_ball_overs} real seven-ball overs. We kept them and list them; eight or more legal balls in an over would still fail.`],
    ["Why SQLite and not just CSV?", "The guidelines ask for a persistent form beyond a flat CSV. SQLite gives keys, check constraints, views and SQL queries in one file, with no server. We also export CSVs and an Excel workbook for Power BI."],
    ["How do you know no rows were lost?", `Gate G9 reconciles counts: ${fmt(F.raw.deliveries_rows)} deliveries in the raw file, staging, clean table and fact table, and ${fmt(F.raw.matches_rows)} matches in each.`],
    ["What does 2007/08 mean in the data?", "It is how this Kaggle version labels IPL 2008, played in April to June 2008. The label is ambiguous, so the season is the calendar year of the match date."],
  ]),

  h("3.5 Numbers to remember", 2),
  numbers([
    ["Matches / balls", `${fmt(F.raw.matches_rows)} / ${fmt(F.raw.deliveries_rows)}`],
    ["Seasons", "17 (2008-2024)"],
    ["Team strings / franchises", `${F.raw.team_strings} / ${wh.franchises}`],
    ["Venue strings / grounds", `${F.raw.venue_strings} / ${wh.dim_venue}`],
    ["Cleaning rules / cells changed", `${F.cleaning.rules} / ${fmt(F.cleaning.cells)}`],
    ["Missing cities filled", String(F.raw.na_city)],
    ["Wides / no-balls", `${fmt(F.raw.wides)} / ${fmt(F.raw.noballs)}`],
    ["Seven-ball overs", String(F.cleaning.seven_ball_overs)],
    ["Fuzzy pairs / merged", `${F.cleaning.fuzzy_pairs} / 0`],
    ["Facts / dimensions / FKs", "3 / 7 / 28"],
    ["Validation gates", "9, all PASS"],
    ["Ties / no-results / D-L", `${m.tie} / ${m.no_result} / ${m.dl}`],
  ]),

  h("3.6 Be ready to show", 2),
  ...show([
    "Notebook sections 1 (extraction and the raw problems), 2 (pipeline run and profiling), 3 (cleaning log and mappings) and 5 (star schema, star-join query, validation gates).",
    "logs/extraction_log.csv, logs/cleaning_log.csv, logs/validation_report.csv and logs/g5_exceptions.csv.",
    "mappings/teams.csv and mappings/venues.csv; sql/ddl.sql; docs/decision_log.md; the ER diagram.",
  ]),
];

// ------------------------------------------------------------------ member 2
const member2 = [
  pageBreak(),
  h(`4. ${M2}: transformation, feature engineering and insights`, 1),
  h("4.1 What was done in this part", 2),
  bullet(`**Reshape and aggregation.** Grouped the ${fmt(wh.fact_delivery)} balls by match, innings and phase, then pivoted the innings into columns, so each match is one row with both Powerplays (fact_match_summary, ${fmt(wh.fact_match_summary)} rows). Re-derived it in plain pandas in the notebook and it matches the warehouse exactly.`),
  bullet("**Phase of every ball.** Powerplay overs 1-6, Middle 7-15, Death 16-20 (Super Over innings have no phase)."),
  bullet(`**Phase index (the engineered feature).** Player's share of his balls in a phase divided by the league's share for the same role and season; grouped by player, season, role and phase (fact_player_season_phase, ${fmt(wh.fact_player_season_phase)} rows). Primary phase = highest index in a season with 60+ balls; re-checked at 120.`),
  bullet(`**SCD Type 2 player profile.** Each player's primary phase stored as spells with valid-from and valid-to seasons: ${fmt(wh.dim_player_phase_profile)} spells and 540 phase changes.`),
  bullet("**Insights analysis (six questions).** Phase drift, league run rates by phase, team Powerplay and Death profiles, venues, the toss (chi-square test) and the Powerplay against the result (point-biserial correlation), with all charts."),
  bullet("**Documents.** Report sections 3.3 (transformation) and 4 (insights); notebook sections 4 and 6."),

  h("4.2 Concepts you must be able to explain", 2),
  concepts([
    ["Aggregation and pivot", "Group by collapses many rows into one per group (balls into match x innings x phase); pivot turns innings 1 and 2 into side-by-side columns."],
    ["Phase index", `phase share / league phase share. In 2024 the league's batting balls were 31% Powerplay, 46% Middle, 22% Death, so raw shares make everyone look like a Middle player. 1.0 = league average.`],
    ["Threshold and sensitivity", "60 balls (about ten overs) before a season counts. We repeat at 120 balls to show the results do not depend on that choice."],
    ["SCD Type 1 vs Type 2", "Type 1 overwrites the old value and loses history. Type 2 adds a new row with valid-from and valid-to dates and an is_current flag, so history is kept."],
    ["Gap rule (D-07)", "A season under 60 balls neither opens nor closes a spell; a change is dated from the next qualifying season."],
    ["Chi-square test of independence", "Tests whether two categorical variables are related. Here: toss decision (bat or field) against whether the toss winner won."],
    ["p-value", "The chance of a result this extreme if there were no real effect. Below 0.05 we reject 'no effect'."],
    ["Point-biserial correlation", "Correlation between a continuous variable (Powerplay run-rate difference) and a binary one (batting first won)."],
    ["Association vs causation", "Two things moving together does not prove one causes the other; our data is observational."],
    ["Impact Player rule", "From IPL 2023 each team may bring in one substitute during a match. It gives an extra batter, so top orders can attack earlier: a plausible reason for the Powerplay jump, not a proven one."],
  ]),

  h("4.3 Your slides: what to say", 2),
  ...script("Slide 5: the engineered feature, a phase index", [
    "Thank you. The key transformation is the phase index.",
    "A player's raw share of balls in a phase is biased, because the Middle overs are 9 of the 20.",
    "So we divide his share by the league's share for the same role and season. An index of 1.0 means league average.",
    "His primary phase is the phase with the highest index, in a season with at least 60 balls.",
    "We keep the history as a Type 2 slowly changing dimension. For example, Hardik Pandya was a Death batter from 2015 to 2021 and a Middle batter from 2022.",
  ]),
  ...script("Slide 6: insight 1, the scoring boom is front-loaded", [
    `The Powerplay run rate rose from ${i1.Powerplay.y2008.toFixed(2)} to ${i1.Powerplay.y2024.toFixed(2)} runs an over: up ${Math.round(i1.Powerplay.chg_08_24)} percent since 2008.`,
    `The Middle and Death overs rose only ${Math.floor(i1.Middle.chg_08_24)} to ${Math.round(i1.Death.chg_08_24)} percent.`,
    `And ${Math.round(i1.Powerplay.chg_22_24)} percent came in just 2022 to 2024, the first Impact Player seasons.`,
    "We call this an association, not a proven cause.",
  ]),
  ...script("Slide 7: insights 2 and 3, the Powerplay and the toss", [
    `The side with the higher Powerplay run rate won ${i2.higher_wins} percent of ${fmt(i2.matches)} matches.`,
    `When batting first led by more than three runs an over it won ${band("> 3")} percent. When it trailed by that much, ${band("< -3")} percent.`,
    `Toss winners won only ${i3.overall} percent: a coin flip.`,
    `But teams that chose to field won ${i3.field_pct} percent, against ${i3.bat_pct} percent for batting. The chi-square test gives p = ${i3.p}, so the decision and the result are not independent.`,
  ]),
  ...script("Slide 8: insight 4, a player's phase is not a fixed trait", [
    `${i4.batting_60.pct} percent of batters and ${i4.bowling_60.pct} percent of bowlers changed their primary phase at least once.`,
    "At a stricter 120-ball threshold the shares barely move, so it is not noise.",
    "Batters mostly move one slot up or down the order. Bowlers often swap between the Powerplay and the Death.",
    `Now ${S3} will show whether the Powerplay can predict the winner.`,
  ]),

  h("4.4 Questions to expect", 2),
  qa([
    ["What is your non-trivial transformation?", `Two aggregations. Balls grouped by match, innings and phase, then pivoted so each match is one row with both Powerplays (${fmt(wh.fact_match_summary)} rows). And balls grouped by player, season, role and phase to get the phase index (${fmt(wh.fact_player_season_phase)} rows). The notebook re-derives the first in pandas and it matches exactly.`],
    ["What is the phase index? Why not the raw share?", "Share of a player's balls in a phase divided by the league's share. The Middle phase is 9 of 20 overs, so on raw shares almost everyone is 'Middle'. The index removes that: above 1 means more of that phase than average."],
    ["Why 60 balls?", "About ten overs; below that one innings can swing a player's shares. We re-ran at 120 balls: the share of players who changed moved by only a few points (61% to 63% for batters, 56% to 54% for bowlers)."],
    ["Explain SCD Type 2 in your project.", "Each row is a spell: player, role, primary phase, valid-from, valid-to and is_current. When the phase changes we close the old row and open a new one. Gate G8 checks that spells never overlap and that each player-role has one current row."],
    ["How is Type 2 different from Type 1?", "Type 1 would overwrite Pandya's phase with 'Middle' and lose 2015-2021. Type 2 adds a row with validity dates, so we can ask what his role was in any season."],
    ["Did the Impact Player rule cause the Powerplay boom?", "We cannot prove it. The timing matches, but players, squads, pitches and strategy also changed. So we report an association and call the rule a plausible cause."],
    ["Explain your chi-square test.", `Null hypothesis: toss decision and winning are independent. On 1,090 decided matches chi-square = ${i3.chi2} with 1 degree of freedom, p = ${i3.p}, below 0.05, so we reject independence. Tested ground by ground, none of the ${i3.venues_tested} grounds is significant, so the effect is real but small.`],
    ["What does r = 0.36 mean?", `A point-biserial correlation between the Powerplay run-rate difference and whether batting first won. 0.36 is a moderate positive link; the banded chart shows it: from ${band("< -3")}% to ${band("> 3")}%.`],
    ["Why are your insights non-obvious?", "Each goes against a common belief. People credit Death-overs hitting, but the Powerplay changed most. People think winning the toss helps, but only the decision matters. People label players 'death bowlers', but most players change phase."],
    ["Why do batters and bowlers drift differently?", `Batters move one slot up or down the order, so ${i4.bat_middle_pct}% of their moves pass through the Middle overs. Bowlers are used as specialists, so ${i4.bowl_ppdeath_pct}% of their moves are swaps between Powerplay and Death.`],
    ["Which venue scores the most?", "We only rank grounds with 10 or more matches. Dharamsala is top at 184 but with only 13 matches; Bengaluru's Chinnaswamy, 174 over 90 matches, is the reliable high-scoring ground."],
  ]),

  h("4.5 Numbers to remember", 2),
  numbers([
    ["PP run rate 2008 / 2024", `${i1.Powerplay.y2008.toFixed(2)} / ${i1.Powerplay.y2024.toFixed(2)}`],
    ["PP change 2008-24 / 2022-24", `+${Math.round(i1.Powerplay.chg_08_24)}% / +${Math.round(i1.Powerplay.chg_22_24)}%`],
    ["Middle / Death change 2008-24", `+${i1.Middle.chg_08_24}% / +${i1.Death.chg_08_24}%`],
    ["Avg 1st innings 2022 / 2024", `${Math.round(i1.avg_inn1["2022"])} / ${Math.round(i1.avg_inn1["2024"])}`],
    ["Higher PP rate wins", `${i2.higher_wins}% of ${fmt(i2.matches)}`],
    ["Win % at > +3 / < -3", `${band("> 3")}% / ${band("< -3")}%`],
    ["Toss winner wins", `${i3.overall}%`],
    ["Field / bat first wins", `${i3.field_pct}% / ${i3.bat_pct}%`],
    ["Chi-square / p", `${i3.chi2} / ${i3.p}`],
    ["Correlation r", String(i2.r)],
    ["Batters / bowlers changed (60)", `${i4.batting_60.pct}% / ${i4.bowling_60.pct}%`],
    ["Spells / phase changes", `${fmt(wh.dim_player_phase_profile)} / 540`],
  ]),

  h("4.6 Be ready to show", 2),
  ...show([
    "Notebook section 4 (the pandas re-derivation, the phase-index check, the Dhoni and Pandya spells) and section 6 (the four insights and their charts).",
    "data/export/analysis/ (tables and figures); src/transform.py, src/scd2.py, src/analysis.py; the drift table data/export/drift_table.csv.",
  ]),
];

// ------------------------------------------------------------------ member 3
const member3 = [
  pageBreak(),
  h(`5. ${M3}: machine learning, Power BI dashboard and the report`, 1),
  h("5.1 What was done in this part", 2),
  bullet(`**Framed the ML task.** Binary classification: did the team batting first win? ${fmt(m.ml_eligible)} complete, full-length matches (${m.excluded_ml} no-results, ties, Super Overs and D/L matches left out).`),
  bullet("**Two prediction points.** Model A after the first-innings Powerplay; Model B after both Powerplays. Each uses only what is known at that moment."),
  bullet("**Leakage-free features.** Powerplay runs, wickets, run rate, boundaries and dot-ball %; toss; each franchise's previous-season win % (a new franchise gets a neutral 0.5); the venue's average first-innings score from earlier matches only."),
  bullet(`**Models and baselines.** Logistic regression, decision tree, random forest; baselines: majority class and a cricket rule ("higher Powerplay run rate wins").`),
  bullet(`**Method.** Time split: train 2008-2021 (${split.train.matches}), validation 2022 (${split.val.matches}), test 2023-2024 (${split.test.matches}). Forward-chaining cross-validation (14 folds) on ROC-AUC; imputation and scaling inside a scikit-learn pipeline; test seasons scored once.`),
  bullet("**Evaluation.** Accuracy, precision, recall, F1, ROC-AUC, confusion matrices, ROC curves, feature importance, and a list of confident wrong predictions (upsets)."),
  bullet(`**Power BI.** Workbook of 18 tables exported from the warehouse, including ${fmt(F.pbi_tables.TestPredictions)} test predictions; relationships, DAX measures and three pages (overview, drill-down, model insights) in the build guide.`),
  bullet("**Report.** Owner of the written report, which brings all parts together."),

  h("5.2 Concepts you must be able to explain", 2),
  concepts([
    ["Baseline", "A simple reference a model must beat. Majority class = always predict the most common result; our rule baseline = higher Powerplay run rate wins."],
    ["Data leakage", "When a model sees information it would not have at prediction time. It makes test scores look better than real use."],
    ["Time-based split", "Train on the past, test on the future, because the game changes over seasons."],
    ["Forward-chaining CV", "Each fold trains on all seasons before season s and validates on s; 14 folds over 2008-2022."],
    ["Pipeline", "Imputer and scaler are fitted on the training fold only, then applied to validation and test data."],
    ["Accuracy / precision / recall / F1", "Share correct / of predicted bat-first wins, how many were right / of actual bat-first wins, how many we found / harmonic mean of precision and recall."],
    ["ROC-AUC", "The chance that a random bat-first win gets a higher score than a random chase win. 0.5 = guessing, 1.0 = perfect."],
    ["Confusion matrix", "Counts of true and false positives and negatives."],
    ["Decision tree (U7)", "Splits the data on the feature that best separates winners (Gini impurity); max_depth and min_samples_leaf stop it from overfitting."],
    ["Random forest", "Many trees on random samples and features, averaged; less variance than one tree."],
    ["Power BI model", "One-to-many relationships from dimensions (Season, Venue, Phase) to facts; DAX measures such as Run Rate = runs x 6 / legal balls; slicers and drill-down."],
  ]),

  h("5.3 Your slides and the demo: what to say", 2),
  ...script("Slide 9: can the Powerplay predict the winner?", [
    "Thank you. Our task is binary classification: does the team batting first win?",
    `We used ${fmt(m.ml_eligible)} complete matches. Model A predicts after the first Powerplay, Model B after both.`,
    "We split by time: train on 2008 to 2021, validate on 2022, and test once on 2023 and 2024.",
    "We tuned with forward-chaining cross-validation, so each fold trains only on earlier seasons.",
    `Model B logistic regression reached ${pct(lrB.accuracy)} percent accuracy and ROC-AUC ${lrB.roc_auc.toFixed(2)}.`,
    `But the simple rule, higher Powerplay run rate wins, reached ${pct(ruleB.accuracy)} percent. So the model adds only ${gap} points, and we report that honestly.`,
    "The strongest feature is the chasing side's Powerplay wickets.",
  ]),
  ...script("Slide 10: the dashboard demo (about 2 minutes)", [
    "Our Power BI dashboard reads a workbook exported from the warehouse, including the model's test predictions.",
    "Page 1: drag the season slider to 2023-2024 and show the Powerplay run-rate card rise; click UAE to show the seasons played there.",
    "Page 2: open KKR in the heatmap to show its three phases; pick Hardik Pandya in the player slicer to show his spells.",
    "Page 3: switch the prediction point from B to A. Accuracy drops from about 68 to 61 percent. Show the predicted-versus-actual matrix and the upsets table.",
  ]),
  ...script("Slide 10: limitations and close", [
    "Our main limitations: no ball-tracking, pitch or batting-order data; phase is only a proxy for role; and our findings are associations, not causes.",
    "What we learned is that the value was in the wrangling. With clean data, the answers were clear.",
    "Thank you. We are happy to take questions.",
  ]),

  h("5.4 Questions to expect", 2),
  qa([
    ["What is your target and why classification?", `bat_first_won: 1 if the team batting first won, else 0. The outcome is a category, so it is classification. ${m.excluded_ml} matches with no winner or a broken 20-over structure are left out.`],
    ["Why two models, A and B?", "Each model may only use what is known when it predicts. Model A cannot see the chase, Model B has both Powerplays. This avoids leakage and measures how much the first six overs tell us."],
    ["Why not a random 80/20 split?", "The game changes over time. A random split would train on 2024 and test on 2010, which leaks the future. A time split works like a real forecast."],
    ["What is forward-chaining cross-validation?", "Each fold trains on all seasons before one season and validates on that season: 14 folds over 2008-2022. We pick the settings with the best average ROC-AUC."],
    ["How did you prevent leakage?", "Features use only earlier data (previous-season win %, venue averages from earlier matches). Imputer and scaler sit inside the pipeline, so they fit on training folds only. The test seasons were scored once, after tuning."],
    ["Explain the metrics of your best model.", `Accuracy ${pct(lrB.accuracy)}%. Precision ${lrB.precision.toFixed(2)}: when it says batting first wins, it is right ${Math.round(100 * lrB.precision)}% of the time. Recall ${lrB.recall.toFixed(2)}: it finds ${lrB.tp} of ${lrB.tp + lrB.fn} batting-first wins. F1 ${lrB.f1.toFixed(2)}. ROC-AUC ${lrB.roc_auc.toFixed(2)}.`],
    ["Why tune on ROC-AUC, not accuracy?", "AUC judges the ranking at every threshold, not just the 0.5 cut-off, and it does not depend on the class balance, which moved between seasons."],
    ["Your model barely beats a simple rule. Is that a failure?", `It is an honest result. Most of the signal is the Powerplay run-rate difference, which the rule already uses. With ${split.test.matches} test matches one match is 0.7 points, so a ${gap}-point gap is within noise. The guidelines ask us to report where the model underperforms.`],
    ["Which feature matters most?", `The chasing side's Powerplay wickets: the tree's first split, the largest logistic-regression coefficient and ${Math.round(100 * F.ml.rf_b_top[0].value)}% of the forest's importance. Chasers who lost at most one Powerplay wicket won ${F.ml.chase_win_le1_wkt}%; two or more, ${F.ml.chase_win_ge2_wkt}%.`],
    ["Why is the majority baseline below 50%?", `It always predicts the training majority, 'chase wins' (batting first won only ${F.ml.bat_first_win_train}% of training matches). In the test seasons batting first won ${F.ml.bat_first_win_test}%, so always saying 'chase' scores ${pct(majB.accuracy)}%.`],
    ["Why these three algorithms?", "Logistic regression is interpretable through its coefficients; a decision tree gives readable rules and is in our syllabus; a random forest handles non-linear effects with less variance. Comparing them with baselines shows whether complexity helps. Here it barely does."],
    ["How did you stop the tree overfitting?", "We tuned max_depth (2 to 5) and min_samples_leaf (5 or 20) by cross-validation. Model B chose depth 3 with at least 20 matches per leaf."],
    ["Why is Model A weak?", `It only sees one innings' Powerplay, six overs of a 40-over match. It scores ${pct(lrA.accuracy)}%, no better than the median rule (${pct(ruleA.accuracy)}%).`],
    ["How is Power BI connected to the data?", "The pipeline exports one Excel workbook with 18 tables. In Power BI we set one-to-many relationships from dimensions to facts and wrote DAX measures. After re-running the pipeline, Refresh updates the report."],
    ["Why Excel and not SQLite directly?", "Power BI Desktop has no built-in SQLite connector; it needs a separate ODBC driver. An Excel workbook imports in one step on any lab PC, and the data is the same."],
    ["Where is the interactivity?", "Season slider, country tiles and venue dropdown on page 1; drill-down from franchise to phase and a player slicer on page 2; prediction-point and model slicers on page 3."],
    ["How would you improve the model?", "Predict at more points in the match (for example after 10 overs), add player-strength features, weight recent seasons more, and calibrate the probabilities."],
  ]),

  h("5.5 Numbers to remember", 2),
  numbers([
    ["Eligible / excluded matches", `${fmt(m.ml_eligible)} / ${m.excluded_ml}`],
    ["Train / val / test matches", `${split.train.matches} / ${split.val.matches} / ${split.test.matches}`],
    ["CV folds", "14"],
    ["LR (B) accuracy / AUC", `${pct(lrB.accuracy)}% / ${lrB.roc_auc.toFixed(2)}`],
    ["LR (B) precision / recall / F1", `${lrB.precision.toFixed(2)} / ${lrB.recall.toFixed(2)} / ${lrB.f1.toFixed(2)}`],
    ["Rule (B) accuracy / AUC", `${pct(ruleB.accuracy)}% / ${ruleB.roc_auc.toFixed(2)}`],
    ["Random forest (B) acc / AUC", `${pct(rfB.accuracy)}% / ${rfB.roc_auc.toFixed(2)}`],
    ["Decision tree (B) acc / AUC", `${pct(dtB.accuracy)}% / ${dtB.roc_auc.toFixed(2)}`],
    ["Majority baseline", `${pct(majB.accuracy)}%`],
    ["LR (A) accuracy / AUC", `${pct(lrA.accuracy)}% / ${lrA.roc_auc.toFixed(2)}`],
    ["Confusion matrix LR (B)", `TN ${lrB.tn}, FP ${lrB.fp}, FN ${lrB.fn}, TP ${lrB.tp}`],
    ["Confident wrong calls LR (B)", String(upsLR)],
    ["Bat first won: train / test", `${F.ml.bat_first_win_train}% / ${F.ml.bat_first_win_test}%`],
    ["Power BI tables / pages", "18 / 3"],
  ]),

  h("5.6 Be ready to show", 2),
  ...show([
    "Notebook section 7 (split, cross-validation, metrics table, ROC curves, confusion matrices, feature importance, decision tree, upsets) and section 8 (the Power BI export).",
    "The .pbix with all three pages, and the 60-90 second screen recording as a backup if the laptop or projector fails.",
    "data/export/ml/ (metrics.csv, test_predictions.csv, figures); src/features.py and src/ml.py; the Power BI Build Guide.",
  ]),
];

// ------------------------------------------------------------------ shared
const shared = [
  pageBreak(),
  h("6. Questions any member may get", 1),
  qa([
    ["What was the hardest part?", "Getting the data right before any number made sense: team and venue names, the season and over conventions, and legal balls. The seven-ball overs only showed up when we ran the real data, and a validation gate caught them."],
    ["What are your main limitations?", `No ball-tracking, pitch, weather or batting-order data; phase is only a proxy for role; the 60-ball threshold is a choice; ${m.excluded_ml} non-standard matches are left out of the model; and our findings are associations, not causes.`],
    ["Which wrangling decisions could bias your results?", "Merging renamed grounds assumes the pitch did not change with the name; keeping franchise history across renames assumes continuity; keeping seven-ball overs adds a few balls; leaving out D/L and Super Over matches favours normal games."],
    ["Why is there also a Streamlit app?", "We built a Streamlit prototype first because it runs on any laptop and can be tested automatically. The submitted dashboard is Power BI, as the guidelines require; both read the same exported data."],
    ["Is the project reproducible?", "Yes. One command, or Run All in the notebook, rebuilds everything from the two raw files in about two and a half minutes. Random seeds are fixed, and 38 automated tests check the pipeline."],
    ["What would you do with more time?", "Add ball-tracking or batting-order data to explain why roles change, predict at more points in the match, and refresh the warehouse with new seasons."],
    ["What did each of you do?", "Each member names their own part from section 1, in one sentence. It matches the contribution statement."],
  ]),

  h("7. Before the viva", 1),
  bullet("Fill in the names and roll numbers in the report, cleaning log, deck and contribution statement."),
  bullet("Build the .pbix with the Power BI Build Guide, export the PDF, and put real screenshots in the report and deck."),
  bullet("Record a 60-90 second screen capture of the dashboard as a backup for the demo."),
  bullet("Each member runs the notebook once and opens every file in their \"Be ready to show\" list."),
  bullet("Rehearse once in order with a timer, including the handover lines."),
  bullet("Print your own section of this guide and bring it."),
];

save(makeDoc([...front, ...member1, ...member2, ...member3, ...shared], { title: "Viva Preparation Guide" }),
  path.join(L.ROOT, "submission", "08_Viva_Preparation_Guide.docx"));
