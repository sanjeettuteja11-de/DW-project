// Power BI build guide: how to turn IPL_PowerBI_Data.xlsx into the .pbix (submission item 3).
const path = require("path");
const { Paragraph, TextRun, AlignmentType } = require("docx");
const L = require("./lib");
const { FACTS: F, p, h, bullet, numbered, table, image, caption, pageBreak, makeDoc, save, fmt, setBodySize } = L;

setBodySize(21);
const W = 9026;
const FIG = (n) => path.join(L.ROOT, "reports", "figures", n);

// DAX / code lines in a monospace font (no shading, per the plain document style)
const code = (lines) => lines.map((l, i) => new Paragraph({
  children: [new TextRun({ text: l, font: "Consolas", size: 18 })],
  spacing: { after: i === lines.length - 1 ? 120 : 0, line: 240 },
  indent: { left: 360 },
}));

const t = F.pbi_tables;
const children = [
  h("Power BI Dashboard: Build Guide", 0),
  p("IPL Phase-Performance and Style-Drift Data Warehouse  |  Data Wrangling group project", { align: AlignmentType.CENTER, after: 160 }),

  p("This guide turns the exported workbook into the required Power BI file (IPL_DW_Dashboard.pbix) with three report pages: an overview, a detail / drill-down page and a model-insights page. Every number on the pages comes from the wrangled warehouse and the model outputs, so nothing is typed in by hand. Allow about 45 minutes."),
  p("**You need:** Power BI Desktop (free, Windows only: use a college lab PC or a group member's Windows laptop), and the file data/export/powerbi/IPL_PowerBI_Data.xlsx. If the pipeline is re-run, run python -m src.powerbi again and press Home > Refresh in Power BI."),

  h("1. Load the data", 1),
  numbered("Open Power BI Desktop > Home > Get data > Excel workbook > select IPL_PowerBI_Data.xlsx.", "numbers"),
  numbered("In the Navigator tick the 18 **sheets** (green sheet icons, not the tbl... table items): Season, Phase, Venue, Franchise, Team, Player, Role, Matches, TeamMatches, InningsPhase, PlayerSeasonPhase, PhaseSpells, PhaseChanges, FeatureSet, Model, ModelMetrics, TestPredictions, FeatureImportance.", "numbers"),
  numbered("Click **Transform data**. For each table check that the first row was used as headers and that key columns are Whole number (all *_key columns, season, year columns), match_date is Date, and rates and probabilities are Decimal number. Close & Apply.", "numbers"),
  table([
    ["Table", "Rows", "Grain / use"],
    ["Season, Phase, Venue, Franchise, Player, Role", `${t.Season}, ${t.Phase}, ${t.Venue}, ${t.Franchise}, ${t.Player}, ${t.Role}`, "Dimensions for slicers"],
    ["Matches", fmt(t.Matches), "One row per match: teams, toss, Powerplay stats, totals, result"],
    ["TeamMatches", fmt(t.TeamMatches), "One row per team per match (team win %)"],
    ["InningsPhase", fmt(t.InningsPhase), "Match x innings x phase: runs, legal balls, wickets, boundaries, dots"],
    ["PlayerSeasonPhase", fmt(t.PlayerSeasonPhase), "Player x season x role x phase, with the phase index"],
    ["PhaseSpells / PhaseChanges", `${fmt(t.PhaseSpells)} / ${t.PhaseChanges}`, "SCD Type 2 spells and the transitions between them"],
    ["FeatureSet, Model", `${t.FeatureSet}, ${t.Model}`, "Slicer tables for the model page"],
    ["ModelMetrics, TestPredictions, FeatureImportance", `${t.ModelMetrics}, ${fmt(t.TestPredictions)}, ${t.FeatureImportance}`, "Test-season metrics, predicted vs actual per match, feature importance"],
  ], [3400, 1500, W - 4900]),

  h("2. Relationships (Model view)", 1),
  p("Delete any relationship Power BI detected automatically, then create exactly these (all one-to-many, single cross-filter direction, from the first table to the second):"),
  table([
    ["From (one side)", "To (many side)"],
    ["Season[season_key]", "Matches[season_key], TeamMatches[season_key], InningsPhase[season_key], PlayerSeasonPhase[season_key]"],
    ["Venue[venue_key]", "Matches[venue_key], TeamMatches[venue_key], InningsPhase[venue_key]"],
    ["Phase[phase_key]", "InningsPhase[phase_key], PlayerSeasonPhase[phase_key]"],
    ["Franchise[franchise_id]", "TeamMatches[franchise_id], InningsPhase[batting_franchise]"],
    ["Player[player_key]", "PlayerSeasonPhase[player_key], PhaseSpells[player_key], PhaseChanges[player_key]"],
    ["Role[role_type]", "PlayerSeasonPhase[role_type], PhaseSpells[role_type], PhaseChanges[role_type]"],
    ["FeatureSet[feature_set]", "ModelMetrics[feature_set], TestPredictions[feature_set], FeatureImportance[feature_set]"],
    ["Model[model]", "ModelMetrics[model], TestPredictions[model], FeatureImportance[model]"],
  ], [2600, W - 2600]),
  p("Team is kept only as a reference list of name spells and needs no relationship. Do not relate Matches to TestPredictions: it would create a second filter path from Season and Power BI would make one of them inactive.", { before: 80 }),

  h("3. Measures (DAX)", 1),
  p("Home > Enter data > create an empty table named _Measures, then add each measure below with New measure (set the format shown in brackets)."),
  ...code([
    "Matches = COUNTROWS ( Matches )",
    "Avg First Innings = CALCULATE ( AVERAGE ( Matches[inn1_total_runs] ), Matches[match_status] = \"completed\" )   [0 dp]",
    "Run Rate = DIVIDE ( SUM ( InningsPhase[runs] ) * 6, SUM ( InningsPhase[legal_balls] ) )   [2 dp]",
    "Powerplay Run Rate = CALCULATE ( [Run Rate], Phase[phase] = \"Powerplay\" )   [2 dp]",
    "PP Run Rate (Last Season) = VAR y = MAX ( Season[season] ) RETURN CALCULATE ( [Powerplay Run Rate], Season[season] = y )",
    "PP Run Rate (First Season) = VAR y = MIN ( Season[season] ) RETURN CALCULATE ( [Powerplay Run Rate], Season[season] = y )",
    "PP Run Rate Change % = DIVIDE ( [PP Run Rate (Last Season)], [PP Run Rate (First Season)] ) - 1   [%]",
    "Boundary % = DIVIDE ( SUM ( InningsPhase[boundaries] ), SUM ( InningsPhase[balls_faced] ) )   [%]",
    "Dot Ball % = DIVIDE ( SUM ( InningsPhase[dots] ), SUM ( InningsPhase[legal_balls] ) )   [%]",
    "Toss Winner Win % = AVERAGE ( Matches[toss_winner_won] )   [%, 1 dp]",
    "Bat First Win % = AVERAGE ( Matches[bat_first_won] )   [%, 1 dp]",
    "Team Win % = AVERAGE ( TeamMatches[won] )   [%, 1 dp]",
    "Phase Index = AVERAGE ( PlayerSeasonPhase[phase_index] )   [2 dp]",
    "Phase Changes = COUNTROWS ( PhaseChanges )",
    "Predictions = COUNTROWS ( TestPredictions )",
    "Test Matches = DISTINCTCOUNT ( TestPredictions[match_key] )",
    "Model Accuracy = AVERAGE ( TestPredictions[correct] )   [%, 1 dp]",
    "Model ROC-AUC = MAX ( ModelMetrics[roc_auc] )   [2 dp]",
    "Baseline Accuracy = CALCULATE ( MAX ( ModelMetrics[accuracy] ), ModelMetrics[is_baseline] = 1,",
    "                    ModelMetrics[model] <> \"baseline_majority\", REMOVEFILTERS ( Model ) )   [%, 1 dp]",
  ]),
  p("AVERAGE ignores blanks, so ties and no-results (blank win columns) drop out of the win percentages automatically."),

  h("4. Page 1: Overview (\"How the IPL changed, 2008-2024\")", 1),
  image(FIG("dashboard_page1_overview.png"), 5.9, { title: "Page 1 layout" }),
  caption("Page 1 layout: build it to look like this."),
  table([
    ["Visual", "Fields and settings"],
    ["Title text box", "\"How the IPL changed, 2008-2024\"; subtitle \"League overview: 1,095 matches, 260,920 balls, 17 seasons\""],
    ["Slicers (left)", "Season[season] (style Between, a slider); Venue[country] (style Tile); Venue[venue_short] (Dropdown, search on)"],
    ["4 cards (new Card visual)", "[Matches]; [Avg First Innings]; [PP Run Rate (Last Season)] titled \"Powerplay run rate, last season\" with [PP Run Rate Change %] as a reference label; [Toss Winner Win %]"],
    ["Line chart", "X: Season[season] (continuous), Y: [Run Rate], Legend: Phase[phase]. Markers on. Analytics pane > X-axis constant line at 2022.5 labelled \"Impact Player era\""],
    ["Column chart", "X: Matches[toss_decision], Y: [Toss Winner Win %]; data labels on; Y-axis constant line at 0.5 (dashed)"],
    ["Bar chart", "Y: Venue[venue_short], X: [Avg First Innings]; visual filter [Matches] is greater than or equal to 10; Top N = 8 by [Avg First Innings]; sort descending"],
    ["Narrative text box", "The three-sentence summary shown in the layout (Powerplay +23% since 2008; toss 50.8% overall but 53.9% field vs 45.4% bat)"],
  ], [2000, W - 2000]),

  h("5. Page 2: Detail and drill-down (\"Teams and players\")", 1),
  image(FIG("dashboard_page2_detail.png"), 5.9, { title: "Page 2 layout" }),
  caption("Page 2 layout. The HH Pandya example is the Player slicer's default selection."),
  table([
    ["Visual", "Fields and settings"],
    ["Slicers (left)", "Franchise[franchise_id] (Dropdown); Role[role_type] (Tile, single select, default batting); Player[player] (Dropdown, single select, search on, default HH Pandya); Season[season] (Between)"],
    ["Matrix (heatmap) with drill-down", "Rows: Franchise[franchise_id], then Phase[phase] (two levels, so each franchise expands into its three phases); Columns: Season[season]; Values: [Run Rate]. Format > Row headers > +/- icons on. Cell elements > Background color on (gradient light to dark blue). This is the drill-down: click ⊞ to open a franchise."],
    ["Line chart", "X: Season[season], Y: [Phase Index], Legend: Phase[phase]; constant line at 1.0 (league average). Filtered by the Player and Role slicers."],
    ["Table", "PhaseSpells[primary_phase], [valid_from_season], [valid_to_season], [qualifying_seasons], [is_current] (all set to Don't summarize); sort by valid_from_season"],
    ["Matrix", "Rows: PhaseChanges[from_phase], Columns: PhaseChanges[to_phase], Values: [Phase Changes]; background colour on. Format > Edit interactions: set the Player slicer to None for this visual so it always shows all players for the selected role."],
  ], [2000, W - 2000]),
  p("Optional drill-through page: add a page \"Player detail\", put Player[player] in its Drill-through well and copy the line chart and spells table onto it. Right-clicking a player anywhere then offers Drill through > Player detail.", { before: 80 }),

  h("6. Page 3: Model insights (\"Can the Powerplay predict the winner?\")", 1),
  image(FIG("dashboard_page3_model.png"), 5.9, { title: "Page 3 layout" }),
  caption("Page 3 layout, showing Model B (both Powerplays) with logistic regression selected."),
  table([
    ["Visual", "Fields and settings"],
    ["Slicers (left)", "FeatureSet[prediction_point] (Tile, single select, default B); Model[model_label] (Dropdown, single select, default Logistic regression); TestPredictions[season] (Tile)"],
    ["4 cards", "[Model Accuracy]; [Model ROC-AUC]; [Baseline Accuracy] titled \"Rule: higher PP rate wins\"; [Test Matches]"],
    ["Clustered bar chart", "Y: ModelMetrics[model_label], X: Max of ModelMetrics[accuracy] and Max of ModelMetrics[roc_auc]. Edit interactions: Model slicer > None (the chart compares all models)."],
    ["Matrix (predicted vs actual)", "Rows: TestPredictions[actual_label], Columns: TestPredictions[predicted_label], Values: [Predictions]; background colour on. This is the confusion matrix."],
    ["Bar chart", "Y: FeatureImportance[feature], X: Max of FeatureImportance[value]; visual filter FeatureImportance[model] = random_forest; Top 7. Edit interactions: Model slicer > None."],
    ["Scatter chart", "X: TestPredictions[pp_run_rate_diff], Y: TestPredictions[prob_bat_first_wins] (both Don't summarize), Values: TestPredictions[match_key], Legend: TestPredictions[correct]. Constant lines at Y = 0.5 and X = 0. (Baselines have no probability, so the chart is empty for them.)"],
    ["Table (upsets)", "TestPredictions[match_date], [bat_first_team], [chase_team], [winner_team], [prob_bat_first_wins]; visual filters correct = 0 and confidence >= 0.7; sort by confidence descending"],
    ["Narrative text box", "Model B logistic regression: 68.3% accuracy, ROC-AUC 0.73, only 1.4 points above the one-line rule; the chasing side's Powerplay wickets matter more than any run rate."],
  ], [2000, W - 2000]),

  h("7. Finish and export", 1),
  bullet("Rename the pages \"Overview\", \"Teams and players\" and \"Model insights\". Keep the default theme or pick one theme for all pages; use the same phase colours everywhere (Powerplay, Middle, Death)."),
  bullet("Check the numbers against the report: 1,095 matches; Powerplay run rate 9.46 in 2024 (7.70 in 2008); toss winner win 50.8%; Model B logistic regression 68.3% accuracy, ROC-AUC 0.73."),
  bullet("File > Save as > IPL_DW_Dashboard.pbix. Then File > Export > Export to PDF > IPL_DW_Dashboard.pdf (the PDF fallback the guidelines ask for). Replace the layout images in the report and the deck with screenshots of the finished pages."),
  bullet("For the viva, record a 60-90 second screen capture of the slicers and the drill-down in use (Windows: Win + Alt + R starts the Xbox Game Bar recorder)."),
];

save(makeDoc(children, { title: "Power BI Build Guide" }), path.join(L.ROOT, "submission", "03b_PowerBI_Build_Guide.docx"));
