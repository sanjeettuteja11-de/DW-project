// Cleaning & transformation log (submission item 2), built from reports/facts.json.
const path = require("path");
const L = require("./lib");
const { FACTS: F, p, h, table, makeDoc, save, fmt, setBodySize, AlignmentType } = L;

setBodySize(21);
const W = 9026; // A4 width minus 1-inch margins, in DXA
const C = F.cleaning.by_rule;
const venueRows = C["venue canonical name (manual)"] + C["venue canonical name (normalised key)"];

const children = [
  h("Cleaning and Transformation Log", 0),
  p("IPL Phase-Performance and Style-Drift Data Warehouse  |  Data Wrangling group project, B.Tech CSE (Data Science), NMIMS MPSTME, Semester V", { align: AlignmentType.CENTER, after: 40 }),
  p("Group: Sanjeet Singh Tuteja (L076), [Member 2 name, roll no.], [Member 3 name, roll no.]", { align: AlignmentType.CENTER, after: 160 }),

  p(`This log records what we found in the raw data, what we did about it, what we deliberately left as it was, and why. Every rule is also written row by row to logs/cleaning_log.csv by the pipeline (${F.cleaning.rules} logged rules changing ${fmt(F.cleaning.cells)} cells in total), and each modelling decision has an ID (D-01 to D-20) in docs/decision_log.md.`),

  h("1. Source and extraction", 1),
  table([
    ["Item", "Value"],
    ["Dataset", `${F.source.title}, Kaggle, by ${F.source.owner} (version ${F.source.version}, updated ${F.source.updated})`],
    ["URL", F.source.url],
    ["Method", "Direct download of the public dataset archive from Kaggle's download endpoint (no API key needed; one 1.9 MB request, no rate limit reached). Files are never edited: read as text, SHA-256 checksummed and staged unchanged."],
    ["Files", `matches.csv: ${fmt(F.raw.matches_rows)} rows x ${F.raw.matches_cols} columns (${F.raw.matches_mb} MB)\ndeliveries.csv: ${fmt(F.raw.deliveries_rows)} rows x ${F.raw.deliveries_cols} columns (${F.raw.deliveries_mb} MB)`],
    ["Checksums", `matches.csv ${F.raw.sha_matches.slice(0, 16)}...   deliveries.csv ${F.raw.sha_deliveries.slice(0, 16)}...`],
    ["Coverage", `${F.raw.first_date} to ${F.raw.last_date} (17 seasons)`],
    ["Licence", `${F.source.licence}. Ball-by-ball data from ${F.source.origin}. Used for coursework only.`],
  ], [1700, W - 1700]),

  h("2. Cleaning log: found, done, left as-is", 1),
  table([
    ["#", "What we found", "Evidence in the raw data", "What we did", "Rows / cells", "Why (and what was left as-is)"],
    ["1", "Text tokens instead of nulls", `'NA' in method (${fmt(F.raw.na_method)}), city (${F.raw.na_city}), winner, margin; blank or NA in event columns`, "Converted to real NULLs on read (11 column rules)", fmt(C["null token -> NULL"]), "They are missing-value markers, not values. Nothing imputed."],
    ["2", "Structural nulls", `extras_type blank on ${fmt(F.raw.blank_extras)} balls; dismissal columns null on ~95%`, "Flagged as an explicit category 'none' (extras_type, dismissal_kind); player keys stay NULL", fmt(C["structural null -> 'none'"]), "Absence means no extra / no wicket. Imputing would invent events; dropping would delete 95% of balls."],
    ["3", "Missing city", `${F.raw.na_city} matches (Dubai, Sharjah)`, "Filled from the hand-checked venue mapping", fmt(C["fill city from venue mapping"]), "Deterministic lookup (ground fixes city), not a statistical guess."],
    ["4", "City spellings", "Bangalore / Bengaluru; Mohali / Chandigarh", "One canonical name per city", fmt(C["city canonical name"]), "Consistent grouping."],
    ["5", "No winner / margin / target", `${F.matches.no_result} no-results, ${F.matches.tie} ties`, "Left NULL; outcome coded in match_status", "0", "Left as-is: a no-result has no winner, so filling it would be wrong."],
    ["6", "D/L column almost empty", "98.1% null; 21 matches 'D/L'", "Derived 0/1 flag is_dl_applied; raw column dropped", fmt(C["derive is_dl_applied; drop raw column"]), "The only information is whether D/L was applied."],
    ["7", "Season stored as text", `'2007/08', '2009/10', '2020/21' (${F.raw.season_text_rows} matches)`, "Season = calendar year of match date (D-01)", fmt(C["season label -> year of match date"]), "The labels are ambiguous ('2007/08' is IPL 2008); the date is not."],
    ["8", "Overs numbered from 0", "over 0..19", "Shifted to 1..20 (D-02)", fmt(C["shift 0-based overs to 1-20"]), "Phases are defined on overs 1-20."],
    ["9", "Team names", `${F.raw.team_strings} raw strings: renames (Delhi Daredevils > Capitals, Kings XI > Punjab Kings, RCB Bangalore > Bengaluru) and a misspelling (Rising Pune Supergiants)`, "Misspelling merged; renames kept as SCD Type 2 name spells of one franchise_id; Deccan Chargers and SRH kept separate (D-03)", fmt(C["team canonical name"]), "A rename is history, not an error. Different owners = different franchises."],
    ["10", "Venue names", `${F.raw.venue_strings} raw strings, up to five per ground (Feroz Shah Kotla / Arun Jaitley Stadium / '..., Delhi')`, `26 mapping rules (normalised key or manual); renamed grounds merged (D-04): ${F.warehouse.dim_venue} grounds`, fmt(venueRows), "Venue effects must compare the same physical ground."],
    ["11", "Player name variants", `No spelling variants; ${F.cleaning.fuzzy_pairs} fuzzy pairs proposed, 13 of which played in the same match`, "Merged only on an identical letters-and-digits key (D-05)", "0", "Left as-is: every checked pair was two people (Rohit / Rahul Sharma, Hardik / Krunal Pandya, Marco / Duan Jansen). A wrong merge is worse than a missed one."],
    ["12", "Wides and no-balls", `${fmt(F.raw.wides)} wides, ${fmt(F.raw.noballs)} no-balls`, "Flags is_legal_for_bowler (no wides/no-balls) and is_faced_by_batter (no wides)", "flag on every ball", "Run rates, strike rates and the 120-ball limit depend on legal balls."],
    ["13", "Overs with 7 legal balls", `${F.cleaning.seven_ball_overs} overs; 19 innings reach 121 legal balls (gate G5)`, "Kept as bowled and listed in logs/g5_exceptions.csv (D-20)", "0", "Left as-is: real umpire miscounts. Deleting a real ball would change real totals and break G9."],
    ["14", "Duplicates / grain", "0 duplicate deliveries; ball numbers repeat after extras", "Grain key (match, inning, delivery_seq) from source row order; checked by gate G2", "0", "Duplicates checked rather than assumed."],
    ["15", "Non-standard matches", `${F.matches.super_over} Super Overs, ${F.matches.dl} D/L, ${F.cleaning.g4_exceptions} shortened targets (G4)`, `Kept in the warehouse; Super Over innings excluded from phase aggregates (D-09); ${F.matches.excluded_ml} matches excluded from ML (ml_eligible = 0)`, "0", "They do not follow the 20-over phase structure."],
    ["16", "Columns not needed", "umpire1, umpire2, match_type", "Kept in staging; not loaded into the warehouse", "0", "Not used by either question; staging keeps them for audit."],
  ], [330, 1350, 1850, 2000, 900, W - 330 - 1350 - 1850 - 2000 - 900], { size: 17, align: [AlignmentType.CENTER, null, null, null, AlignmentType.RIGHT, null] }),

  h("3. Transformation log", 1),
  table([
    ["Step", "Input > output", "Operation", "Purpose"],
    ["E7 Dimensions", `clean tables > dim_season (${F.warehouse.dim_season}), dim_phase (${F.warehouse.dim_phase}), dim_team (${F.warehouse.dim_team} spells, ${F.warehouse.franchises} franchises), dim_venue (${F.warehouse.dim_venue}), dim_player (${F.warehouse.dim_player}), dim_match (${fmt(F.warehouse.dim_match)})`, "Distinct + surrogate integer keys; SCD Type 2 on team name", "Conformed dimensions shared by all three facts"],
    ["E8 fact_delivery", `${fmt(F.raw.deliveries_rows)} raw balls > ${fmt(F.warehouse.fact_delivery)} rows`, "Join to dimension keys; derived phase_key from the over, legal-ball flags, is_boundary (4 or 6 off the bat, D-10), is_dot, delivery_seq", "Delivery-grain fact; every later number is a sum over it"],
    ["E9a fact_match_summary", `${fmt(F.warehouse.fact_delivery)} balls > ${fmt(F.warehouse.fact_match_summary)} match rows`, "**Group by** match x innings x phase, then **pivot** innings into inn1_/inn2_ columns (Powerplay runs, wickets, balls, boundaries, dot %, run rate; totals); ML target bat_first_won; ml_eligible flag", "Match grain for questions on the toss and the Powerplay, and the ML table"],
    ["E9b fact_player_season_phase", `${fmt(F.warehouse.fact_delivery)} balls > ${fmt(F.warehouse.fact_player_season_phase)} rows`, "**Group by** player x season x role x phase; derived **phase_share, league_phase_share, phase_index** (= share / league share), qualifies (60+ balls), is_primary_phase (ties: D-13)", "Engineered feature for question 1: corrects for the Middle phase having 9 of 20 overs"],
    ["E10 SCD Type 2 profile", `${fmt(F.warehouse.fact_player_season_phase)} rows > ${fmt(F.warehouse.dim_player_phase_profile)} spells; 540 transitions`, "Season-by-season spells of the primary phase; gap rule D-07; open rows valid_to NULL (D-08); re-run at 120 balls for sensitivity", "History of each player's role; the drift table"],
    ["E12 ML features", `fact_match_summary > ml_features (${fmt(F.warehouse.fact_match_summary)} rows, ${fmt(F.matches.ml_eligible)} eligible)`, "**Time-aware** features: franchise's previous-season win % (D-14; none > 0.5, D-17); venue average first-innings score from earlier matches only", "No information from the future reaches the models"],
    ["Power BI export", "warehouse + model outputs > 14 tables in one workbook", "Names denormalised onto facts; team-per-match table (2,190 rows); innings x phase aggregate (6,443); test predictions vs actual (1,420)", "Few relationships needed in Power BI; slicers by team, venue, season"],
  ], [1550, 2300, 3200, W - 1550 - 2300 - 3200], { size: 17 }),

  h("4. Loading and validation", 1),
  p(`The final data is stored in SQLite (db/ipl_dw.sqlite: 3 fact tables, 7 dimensions, 6 analysis views), exported as CSV, and written to an Excel workbook for Power BI. The pipeline stops before exporting unless all nine gates pass. Result of the final run:`),
  table([["Gate", "Check", "Result"], ...F.gates.map((g) => [g.gate, g.description, `${g.status}: ${g.detail.replace(/;?\s*\(?see logs\/\S+\)?/g, "").trim()}`])],
    [700, 4200, W - 4900], { size: 17 }),
];

save(makeDoc(children, { title: "Cleaning and Transformation Log" }),
  path.join(L.ROOT, "submission", "02_Cleaning_and_Transformation_Log.docx"));
