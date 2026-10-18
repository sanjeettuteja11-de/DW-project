// Written report (submission item 4): 5-7 pages, plain academic style, numbers from reports/facts.json.
const path = require("path");
const L = require("./lib");
const { FACTS: F, p, h, bullet, table, image, caption, makeDoc, save, fmt, setBodySize, AlignmentType } = L;

setBodySize(22);
const W = 9026;
const EX = (...a) => path.join(L.ROOT, "data", "export", ...a);
const FIG = (n) => path.join(L.ROOT, "reports", "figures", n);
const C = { center: AlignmentType.CENTER, right: AlignmentType.RIGHT };

const i1 = F.i1, i2 = F.i2, i3 = F.i3, i4 = F.i4, ml = F.ml, m = F.matches, wh = F.warehouse;
const test = (fs, model) => ml.test.find((r) => r.feature_set === fs && r.model === model);
const pct = (x, d = 1) => (100 * x).toFixed(d);
const lrB = test("B", "logistic_regression"), rfB = test("B", "random_forest"), dtB = test("B", "decision_tree");
const ruleB = test("B", "baseline_higher_pp_rate_wins"), majB = test("B", "baseline_majority");
const lrA = test("A", "logistic_regression"), ruleA = test("A", "baseline_pp_rate_above_train_median");
const split = Object.fromEntries(ml.split.map((s) => [s.part, s]));
const band = (b) => i2.bands.find((x) => x.pp_rr_diff_band === b).bat_first_win_pct;
const gap = (100 * (lrB.accuracy - ruleB.accuracy)).toFixed(1);

const children = [
  h("IPL Phase-Performance and Style-Drift Data Warehouse", 0),
  p("Data Wrangling Group Project Report  |  B.Tech CSE (Data Science), Semester V  |  NMIMS MPSTME, Mumbai  |  October 2026", { align: C.center, after: 30 }),
  p("Group members: Sanjeet Singh Tuteja (L076), [Member 2 name, roll no.], [Member 3 name, roll no.]", { align: C.center, after: 160 }),

  h("1. Objective", 1),
  p(`The Indian Premier League's ball-by-ball records are public, but in raw form they cannot answer even simple questions reliably: teams have been renamed, the same ground appears under several names, seasons are stored as text, and wides and no-balls distort every per-ball rate. Our objective was to take seventeen seasons of these records (2008 to 2024) through the full wrangling pipeline into a validated SQLite star schema, and to use the result to answer two questions:`),
  bullet("**Style drift.** Does the phase of the innings in which a player mostly bats or bowls (Powerplay overs 1-6, Middle 7-15, Death 16-20) stay the same from season to season? Who changes, and how often?"),
  bullet("**Powerplay signal.** How much of a match result can be predicted from the first six overs of each innings?", 0, { after: 100 }),
  p("The second question defines our machine-learning task, and both feed a three-page Power BI dashboard."),

  h("2. Dataset", 1),
  p(`We used the Kaggle dataset ^^${F.source.title}^^ by ${F.source.owner} (version ${F.source.version}, updated ${F.source.updated}), which is compiled from Cricsheet's ball-by-ball records. The database is published under the Open Database License and the underlying Cricsheet data under the Open Data Commons Attribution License, so both are credited. The data was downloaded on ${F.source.download_date} from Kaggle's public download endpoint; no API key, authentication or rate limits were involved.`),
  table([
    ["File", "Grain", "Rows", "Cols", "Main fields"],
    ["matches.csv", "one row per match", fmt(F.raw.matches_rows), F.raw.matches_cols, "season, date, city, venue, team1, team2, toss winner and decision, winner, result, margin, target, super over, method (D/L), umpires"],
    ["deliveries.csv", "one row per ball", fmt(F.raw.deliveries_rows), F.raw.deliveries_cols, "match id, innings, batting and bowling team, over, ball, batter, bowler, non-striker, runs off bat, extras and type, wicket, dismissal kind, fielder"],
  ], [1450, 1450, 900, 600, W - 4400], { align: [null, null, C.right, C.right, null] }),
  p(`Table 1. The two raw files (${F.raw.first_date} to ${F.raw.last_date}).`, { align: C.center, size: 19, before: 40, after: 100 }),
  p("The dataset meets every requirement in the brief: it is real and public, well above 1,000 rows, made of two related files that must be joined, has a clear prediction target (who wins) and many dashboard dimensions (season, team, venue, phase, player). It is also messy in ways that change the answers if ignored:", { after: 60 }),
  bullet(`${F.raw.team_strings} team strings for ${wh.franchises} franchises (renames and a misspelling), and ${F.raw.venue_strings} venue strings for ${wh.dim_venue} grounds, with ${F.raw.na_city} matches missing a city;`),
  bullet(`seasons stored as text on ${F.raw.season_text_rows} matches ('2007/08' is IPL 2008) and overs numbered from 0;`),
  bullet(`'NA' text instead of nulls (${fmt(F.raw.na_method)} of ${fmt(F.raw.matches_rows)} values in the D/L column) and about 95% structural nulls in the event columns;`),
  bullet(`${fmt(F.raw.wides)} wides and ${fmt(F.raw.noballs)} no-balls that are not legal balls, and ${F.cleaning.seven_ball_overs} overs in which the umpires allowed seven legal balls;`),
  bullet(`${m.tie} ties, ${m.no_result} no-results, ${m.super_over} Super Overs and ${m.dl} rain-affected (D/L) matches that break the 20-over structure.`, 0, { after: 100 }),

  h("3. Methodology", 1),
  p("The pipeline is a Python package run by one command or by the submitted notebook, which executes end to end in about two and a half minutes. Every stage writes a log, and every modelling decision has an ID in a decision log (D-01 to D-20)."),
  h("3.1 Extraction", 2),
  p("The two files are downloaded, SHA-256 checksummed and recorded in an extraction log with the source URL, version and download date, then staged unchanged in SQLite as text. Nothing downstream edits the raw files, so every number can be traced back to a file hash. Before writing any cleaning code we profiled every column and tested the ten problems we expected; eight were confirmed."),
  h("3.2 Cleaning", 2),
  p(`Our rule was to flag rather than impute whenever a missing value carries meaning. Table 2 summarises the main decisions; the full log (${F.cleaning.rules} rules, each with its row count) is submitted separately.`, { after: 80 }),
  table([
    ["Problem", "Decision", "Why"],
    ["'NA' tokens; structural nulls in extras and dismissal columns", "Real NULLs; explicit category 'none'; never imputed", "Absence means no extra or no wicket"],
    [`Missing city (${F.raw.na_city} matches)`, "Filled from the venue mapping", "Deterministic lookup, not a guess"],
    [`No winner (${m.no_result} no-results, ${m.tie} ties)`, "Left NULL; outcome in match_status", "A no-result has no winner"],
    ["Season as text; overs 0-19", "Season = year of match date; overs shifted to 1-20", "Labels are ambiguous; phases use overs 1-20"],
    ["Team renames and a misspelling", "Misspelling merged; renames kept as SCD Type 2 spells of one franchise", "A rename is history, not an error"],
    [`${F.raw.venue_strings} venue strings`, `Hand-checked mapping; renamed grounds merged (${wh.dim_venue} grounds)`, "Compare the same physical ground"],
    [`${F.cleaning.fuzzy_pairs} similar player-name pairs`, "Not merged; only identical name keys merge", "13 pairs played in the same match; a wrong merge is worse than a missed one"],
    [`${F.cleaning.seven_ball_overs} seven-ball overs`, "Kept and listed as exceptions", "Real umpire miscounts, recorded as bowled"],
  ], [2850, 3300, W - 6150]),
  p("Table 2. Main cleaning decisions.", { align: C.center, size: 19, before: 40, after: 60 }),
  h("3.3 Transformation", 2),
  p("**Reshape and aggregation.** Deliveries are grouped by match, innings and phase and then pivoted so each match becomes one row with first- and second-innings Powerplay runs, wickets, boundaries, dot-ball percentage and run rate. The notebook re-derives this table in plain pandas and checks that it matches the warehouse exactly."),
  p("**Engineered features.** Every ball gets a phase and two legal-ball flags (wides and no-balls are not legal for the bowler; wides are not faced by the batter). For the first question we derived a **phase index**: a player's share of his balls that fall in a phase, divided by the league's share for the same role and season. Without it the Middle overs, which are 9 of the 20, would make almost every player a \"Middle\" player. A player's primary phase is the phase with the highest index in a season with at least 60 balls (re-checked at 120). For the models we built time-aware features: each franchise's previous-season win percentage and each venue's average first-innings score from earlier matches only."),
  p(`**History.** A Type 2 slowly changing dimension stores each player's primary phase as spells with valid-from and valid-to seasons (${fmt(wh.dim_player_phase_profile)} spells), so a change of role closes one row and opens another instead of overwriting it.`),
  h("3.4 Loading and validation", 2),
  p(`The wrangled data is loaded into SQLite as a star schema (Figure 1) with three fact tables at different grains (${fmt(wh.fact_delivery)} deliveries, ${fmt(wh.fact_match_summary)} matches, ${fmt(wh.fact_player_season_phase)} player-season-phase rows) and seven dimensions, plus analysis views, CSV exports and an Excel workbook for Power BI. Nine validation gates must pass before anything is exported: referential integrity on all 28 foreign keys, a unique grain key, run arithmetic, targets equal to first-innings totals plus one (${F.cleaning.g4_exceptions} shortened or D/L matches listed), legal-ball limits (seven-ball overs listed), no unmapped names, valid winners, non-overlapping SCD spells, and row counts reconciled from raw files to warehouse. All nine pass.`),
  image(path.join(L.ROOT, "docs", "er_diagram_keys.png"), 4.6, { title: "ER diagram" }),
  caption("Figure 1. Star schema with every primary and foreign key (crow's foot = many side)."),

  h("4. Insights", 1),
  h("4.1 The scoring boom is front-loaded", 2),
  p(`Between 2008 and 2024 the Powerplay run rate rose from ${i1.Powerplay.y2008.toFixed(2)} to ${i1.Powerplay.y2024.toFixed(2)} runs per over (+${Math.round(i1.Powerplay.chg_08_24)}%), against +${i1.Middle.chg_08_24}% in the Middle overs and +${i1.Death.chg_08_24}% at the Death (Figure 2). Most of the rise came in the last two seasons: +${Math.round(i1.Powerplay.chg_22_24)}% from 2022 to 2024, the first two seasons of the Impact Player rule, while average first-innings totals went from ${Math.round(i1.avg_inn1["2022"])} to ${Math.round(i1.avg_inn1["2024"])}. Powerplay batters now hit a boundary off ${i1.pp_boundary.y2024}% of balls faced (${i1.pp_boundary.y2008}% in 2008) and the dot-ball share has fallen from ${i1.pp_dot.y2008}% to ${i1.pp_dot.y2024.toFixed(1)}%. The usual story is that T20 scoring grew through Death-overs hitting; since 2022 the bigger change has been at the start of the innings. This is an association: the rule change is a plausible cause, not a proven one.`),
  image(EX("analysis", "figures", "q2_league_phase_rates.png"), 4.5, { title: "Run rate by phase" }),
  caption("Figure 2. League run rate by phase and season."),
  h("4.2 Winning the Powerplay matters, but not decisively", 2),
  p(`In ${fmt(i2.matches)} completed full-length matches the side with the higher Powerplay run rate won ${i2.higher_wins}% of the time. The effect is graded (Figure 3): when the team batting first out-scored the chasers' Powerplay by more than three runs an over it won ${Math.round(band("> 3"))}% of matches, and when it was out-scored by that much it won ${Math.round(band("< -3"))}% (point-biserial r = ${i2.r}). Still, about one match in three goes to the side that lost the Powerplay.`),
  image(EX("analysis", "figures", "q6_powerplay_win_rate.png"), 4.5, { title: "Powerplay difference" }),
  caption("Figure 3. Batting-first win rate by the difference between the two Powerplay run rates."),
  h("4.3 The toss is a coin flip; the decision after it is not", 2),
  p(`Toss winners won ${i3.overall}% of decided matches. Those who chose to field won ${i3.field_pct}% (${i3.field_won} of ${i3.field_n}) against ${i3.bat_pct}% (${i3.bat_won} of ${i3.bat_n}) for those who chose to bat; a chi-square test of independence gives χ² = ${i3.chi2}, p = ${i3.p}. Captains appear to have learned this: the share choosing to field moved between ${i3.field_share_pre2014_min}% and ${i3.field_share_pre2014_max}% a season before 2014 and stayed above 80% from 2016 to 2019. No single ground shows a significant effect on its own (${i3.venues_tested} grounds with 20+ matches tested, smallest p = ${i3.venue_min_p}), so the effect is real but small.`),
  h("4.4 A player's phase is not a fixed trait", 2),
  table([
    ["Qualification", "Role", "Players with 2+ qualifying seasons", "Changed primary phase at least once", "Share"],
    ...[60, 120].flatMap((t) => ["batting", "bowling"].map((r) => {
      const d = i4[`${r}_${t}`];
      return [`${t} balls`, r, String(d.pool), String(d.changed), `${d.pct}%`];
    })),
  ], [1500, 1200, 2400, 2700, W - 7800], { align: [null, null, C.right, C.right, C.right] }),
  p("Table 3. Players who changed primary phase, at two qualification thresholds.", { align: C.center, size: 19, before: 40, after: 100 }),
  p(`Most players change primary phase at least once, and the share barely moves when the threshold is doubled, so it is not small-sample noise (Table 3). The type of move differs by role: ${i4.bat_middle_pct}% of batters' moves (${i4.bat_middle_moves} of ${i4.bat_moves}) involve the Middle overs, a step up or down the batting order, while ${i4.bowl_ppdeath_pct}% of bowlers' moves (${i4.bowl_ppdeath_moves} of ${i4.bowl_moves}) are swaps between the Powerplay and the Death, the two specialist roles. The method passes a sanity check on familiar players: MS Dhoni has been a Death-overs batter in every qualifying season since 2011, and Hardik Pandya moved from Death (2015-21) to Middle from 2022, when he moved up the order as Gujarat Titans captain.`),

  h("5. Machine learning", 1),
  p(`**Task.** Binary classification of whether the team batting first wins, on the ${fmt(m.ml_eligible)} completed full-length matches. So that each prediction uses only what is known at the time, there are two feature sets. **Model A** uses information available after the first-innings Powerplay (that Powerplay, the toss, venue history, both teams' previous-season form); **Model B** adds the chasing side's Powerplay.`),
  p("**Models and baselines.** Logistic regression (linear and interpretable), a decision tree (readable rules) and a random forest (non-linear, lower variance), each compared with two baselines: always predicting the training majority class, and a cricket rule of thumb (for Model B, \"the side with the higher Powerplay run rate wins\")."),
  p(`**Methodology.** Seasons are split in time order: training ${split.train.seasons.split(" ")[0]}-2021 (${split.train.matches} matches), validation 2022 (${split.val.matches}) and test 2023-24 (${split.test.matches}); a random split would let the models learn from the future. Imputation and scaling sit inside a scikit-learn pipeline, so they are fitted on training folds only. Hyper-parameters were chosen by forward-chaining cross-validation on ROC-AUC (each of 14 folds trains on earlier seasons and validates on the next), and the test seasons were scored once.`, { after: 80 }),
  table([
    ["Feature set", "Model", "Accuracy", "Precision", "Recall", "F1", "ROC-AUC"],
    ...[["B", "Majority-class baseline", majB], ["B", "Rule: higher PP run rate wins", ruleB], ["B", "Logistic regression", lrB],
      ["B", "Decision tree", dtB], ["B", "Random forest", rfB], ["A", "Rule: PP run rate above median", ruleA], ["A", "Logistic regression", lrA]]
      .map(([fs, name, r]) => [fs, name, pct(r.accuracy), r.precision.toFixed(2), r.recall.toFixed(2), r.f1.toFixed(2), r.roc_auc.toFixed(2)]),
  ], [1150, 2900, 1000, 1000, 900, 900, W - 7850], { align: [C.center, null, C.right, C.right, C.right, C.right, C.right] }),
  p(`Table 4. Test-season results (2023-24, ${split.test.matches} matches); accuracy in %.`, { align: C.center, size: 19, before: 40, after: 100 }),
  image(EX("ml", "figures", "roc_test.png"), 5.1, { title: "ROC curves" }),
  caption("Figure 4. ROC curves on the test seasons for Model A (left) and Model B (right)."),
  p(`**Results.** Model A is weak: the best model (logistic regression, ${pct(lrA.accuracy)}% accuracy, AUC ${lrA.roc_auc.toFixed(2)}) does no better than the rule "batting first wins if its Powerplay run rate is above the training median" (${pct(ruleA.accuracy)}%, AUC ${ruleA.roc_auc.toFixed(2)}). Model B is clearly better (logistic regression ${pct(lrB.accuracy)}% accuracy, F1 ${lrB.f1.toFixed(2)}, AUC ${lrB.roc_auc.toFixed(2)}; random forest AUC ${rfB.roc_auc.toFixed(2)}) and far above the majority baseline (${pct(majB.accuracy)}%), but only ${gap} points above the one-line rule (${pct(ruleB.accuracy)}%, AUC ${ruleB.roc_auc.toFixed(2)}). Most of the signal is a single subtraction.`),
  p(`**What drives it.** The most useful feature in every Model B is the chasing side's Powerplay **wickets**, not a run rate: it is the decision tree's first split, the largest logistic-regression coefficient and ${Math.round(100 * ml.rf_b_top[0].value)}% of the forest's importance. In the seasons the final models were fitted on, chasers who lost at most one Powerplay wicket won ${ml.chase_win_le1_wkt}% of matches, and those who lost two or more won ${ml.chase_win_ge2_wkt}%. Previous-season form and venue history added almost nothing.`),
  p(`**Where it underperforms.** Recall for batting-first wins is ${lrB.recall.toFixed(2)} (${lrB.fn} of ${lrB.fn + lrB.tp} missed), 2023 was harder than 2024 (${ml.lr_b_by_season["2023"]}% against ${ml.lr_b_by_season["2024"]}%), and the logistic model made ${ml.upsets.find((u) => u.feature_set === "B" && u.model === "logistic_regression").n} confident (70%+) wrong calls. The base rate also moved: batting first won ${ml.bat_first_win_train}% of training matches but ${ml.bat_first_win_test}% of test matches, which is why the majority baseline scores below 50%. With ${split.test.matches} test matches one match is 0.7 points of accuracy, so the gap between the best models and the rule is within noise.`),

  h("6. Dashboard walkthrough", 1),
  p("The Power BI dashboard reads one workbook exported from the warehouse, including the models' test-season predictions, and has three pages (Figure 5). Each page has a title, a plain-language note and slicers, so a non-technical reader can follow the story."),
  bullet("**Overview: how the IPL changed.** Season, country and venue slicers; cards for matches, average first-innings score, the latest Powerplay run rate and its change, and the toss winner's win rate; a run-rate-by-phase line chart with the Impact Player era marked; toss decision against win rate; and the highest-scoring grounds."),
  bullet("**Teams and players (detail and drill-down).** A franchise-by-season run-rate heatmap whose rows drill down from franchise to phase; a player slicer driving a phase-index chart and the SCD Type 2 spells table; and a from/to matrix of every phase change."),
  bullet("**Model insights.** Prediction-point and model slicers; accuracy, ROC-AUC and the rule baseline as cards; a model comparison; the predicted-versus-actual matrix; predicted probability against the Powerplay difference, coloured by correct and wrong; feature importance; and the list of confident wrong predictions.", 0, { after: 80 }),
  image(FIG("dashboard_strip.png"), 6.27, { title: "Dashboard pages" }),
  caption("Figure 5. Dashboard pages: overview, teams and players, model insights."),

  h("7. Limitations", 1),
  bullet("**What the data cannot tell us.** There is no ball-tracking, pitch, weather or batting-order data and no record of Impact Player substitutions, so we can describe when players bat or bowl but not why their roles change, and we cannot separate the rule change from other changes in 2023-24."),
  bullet("**Phase is a proxy for role.** A batter's phase share depends on how long the batters above him last; the index removes the league-wide effect, not the team effect."),
  bullet("**Thresholds are choices.** The 60-ball rule decides who counts. Doubling it changes the headline shares by only a few points, but individual players can flip."),
  bullet(`**Wrangling decisions that could bias results.** Renamed grounds are merged (this assumes the pitch did not change with the name), franchise history is kept across renames (assumes continuity), seven-ball overs are kept, and ${m.excluded_ml} non-standard matches are left out of the models, which slightly favours normal games.`),
  bullet("**Small, shifting test set, and association only.** The game changed between training and test seasons, and the toss and Powerplay findings are correlations in observational data, not causes.", 0, { after: 100 }),

  h("8. Conclusion", 1),
  p(`Most of the work, and most of the value, was in the wrangling: resolving ${F.raw.team_strings} team strings and ${F.raw.venue_strings} venue strings, fixing the season and over conventions, defining legal balls and phases, and building a validated star schema with SCD Type 2 history. With that in place the answers are clear. A player's primary phase is usually not stable across seasons. The Powerplay has changed more than any other phase since the Impact Player rule. And the two Powerplays predict the winner about two times in three, but a one-line rule captures almost all of that, and Powerplay wickets in the chase matter more than Powerplay runs.`),

  h("References", 1),
  p(`Bhardwaj, P. (2024). ^^${F.source.title}^^, version 3 [dataset]. Kaggle. ${F.source.url}`, { align: AlignmentType.LEFT, after: 40 }),
  p("Cricsheet. Ball-by-ball match data. https://cricsheet.org (Open Data Commons Attribution License).", { align: AlignmentType.LEFT, after: 40 }),
  p("Kimball, R. and Ross, M. (2013). ^^The Data Warehouse Toolkit^^, 3rd ed. Wiley.", { align: AlignmentType.LEFT, after: 40 }),
  p("Pedregosa, F. et al. (2011). Scikit-learn: Machine learning in Python. ^^Journal of Machine Learning Research^^, 12, 2825-2830.", { align: AlignmentType.LEFT, after: 40 }),
];

save(makeDoc(children, { title: "IPL Phase-Performance and Style-Drift Data Warehouse: Project Report" }),
  path.join(L.ROOT, "submission", "04_Project_Report.docx"));
