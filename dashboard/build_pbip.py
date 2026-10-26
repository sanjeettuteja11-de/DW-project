"""Build the IPL Scorebook Power BI project (PBIP: TMDL semantic model + PBIR report).

    python dashboard/build_pbip.py

Output: dashboard/IPL_Scorebook/
    IPL_Scorebook.pbip                 open this in Power BI Desktop
    IPL_Scorebook.SemanticModel/       tables, relationships, measures (TMDL)
    IPL_Scorebook.Report/              three report pages (PBIR JSON) and the theme
    data/                              the CSVs the model is built from

Every table's query carries its CSV inside it (gzip + base64), so the project refreshes with
no setup. Set the DataFolder parameter to the data/ folder to read the CSV files instead.
"""
from __future__ import annotations

import base64
import gzip
import json
import shutil
import uuid
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "export" / "powerbi" / "csv"
HERE = Path(__file__).resolve().parent
OUT = HERE / "IPL_Scorebook"
NAME = "IPL_Scorebook"
THEME_FILE = HERE / "IPL_Scorebook_Theme.json"
BASE_THEME = HERE / "resources" / "CY24SU10.json"

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric"
VC_SCHEMA = f"{SCHEMA}/item/report/definition/visualContainer/1.3.0/schema.json"
PAGE_SCHEMA = f"{SCHEMA}/item/report/definition/page/1.2.0/schema.json"

# palette (matches the theme)
INK, MUTED, SOFT, RULE, PAPER = "#1B1F24", "#6E6A62", "#3D3A35", "#CFC7B6", "#F4F1EA"
PP, MID, DEATH, OCHRE, GREY = "#C8553D", "#2E6F95", "#2F5D50", "#D9A23B", "#B9B2A3"
PHASE_COLOURS = {"Powerplay": PP, "Middle": MID, "Death": DEATH}


def uid(*parts: str) -> str:
    """Stable lineage tags, so rebuilding the project does not churn every file."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "ipl-scorebook/" + "/".join(parts)))


# ============================================================== data
FEATURE_LABELS = {
    "inn1_pp_runs": "Batting-first PP runs", "inn1_pp_wickets": "Batting-first PP wickets",
    "inn1_pp_run_rate": "Batting-first PP run rate", "inn1_pp_boundaries": "Batting-first PP boundaries",
    "inn1_pp_dot_pct": "Batting-first PP dot %", "toss_decision_bat": "Toss winner chose to bat",
    "toss_winner_bat_first": "Toss winner batted first",
    "venue_avg_first_innings_prior": "Ground's average first innings",
    "bat_first_prev_season_win_pct": "Batting side's last-season win %",
    "chase_prev_season_win_pct": "Chasing side's last-season win %",
    "inn2_pp_runs": "Chasing PP runs", "inn2_pp_wickets": "Chasing PP wickets",
    "inn2_pp_run_rate": "Chasing PP run rate", "inn2_pp_boundaries": "Chasing PP boundaries",
    "inn2_pp_dot_pct": "Chasing PP dot %",
}


MODEL_SHORT = {"baseline_majority": "Majority class", "baseline_pp_rate_above_train_median": "Rule: PP rate > median",
               "baseline_higher_pp_rate_wins": "Rule: higher PP rate", "logistic_regression": "Logistic regression",
               "decision_tree": "Decision tree", "random_forest": "Random forest"}


def load_tables() -> dict[str, pd.DataFrame]:
    """The Power BI workbook tables, plus a few readable label columns for the report."""
    t = {p.stem: pd.read_csv(p) for p in sorted(SRC.glob("*.csv"))}
    t["MLModel"] = t.pop("Model")

    m = t["Matches"]
    w = m["inn2_pp_wickets"]
    band = pd.cut(w, [-1, 0, 1, 2, 3, 99], labels=["0", "1", "2", "3", "4+"]).astype(object)
    m["chase_pp_wickets_band"] = band.where(w.notna() & (m["ml_eligible"] == 1))
    m["chase_pp_wickets_order"] = w.clip(upper=4).where(m["chase_pp_wickets_band"].notna())

    fi = t["FeatureImportance"]
    fi["feature_label"] = fi["feature"].map(FEATURE_LABELS).fillna(fi["feature"])

    t["MLModel"]["model_short"] = t["MLModel"]["model"].map(MODEL_SHORT)

    sp = t["PhaseSpells"]
    sp["spell_status"] = sp["is_current"].map({1: "current", 0: "closed"})
    return t


def m_type(df: pd.DataFrame, c: str) -> tuple[str, str]:
    """(M type, TMDL dataType) for a column."""
    if c == "match_date":
        return "type date", "dateTime"
    s = df[c]
    if pd.api.types.is_bool_dtype(s):
        return "type logical", "boolean"
    if pd.api.types.is_integer_dtype(s):
        return "Int64.Type", "int64"
    if pd.api.types.is_float_dtype(s):
        return "type number", "double"
    return "type text", "string"


HIDDEN = {"season_key", "venue_key", "player_key", "match_key", "profile_key", "source_match_id", "team_key",
          "pp_diff_band_order", "chase_pp_wickets_order", "phase_key"}
NO_SUM = {"season", "inning", "is_current", "is_super_over", "is_dl_applied", "ml_eligible", "is_baseline",
          "active", "qualifies", "is_primary_phase", "valid_from_season", "valid_to_season", "last_seen_season",
          "from_season", "to_season", "start_over", "end_over", "toss_winner_bat_first", "correct",
          "predicted_bat_first_won", "actual_bat_first_won", "bat_first_won", "toss_winner_won",
          "inn1_pp_wickets", "inn2_pp_wickets", "result_margin"}
FORMATS = {"phase_index_value": "0.00", "phase_index": "0.00", "prob_bat_first_wins": "0.00", "confidence": "0.00",
           "score": "0.00", "pp_run_rate_diff": "0.00", "inn1_pp_run_rate": "0.00", "inn2_pp_run_rate": "0.00",
           "strike_rate": "0.0", "economy": "0.00", "phase_share": "0.0%", "league_phase_share": "0.0%",
           "accuracy": "0.0%", "precision": "0.0%", "recall": "0.0%", "f1": "0.000", "roc_auc": "0.000",
           "value": "0.000", "abs_value": "0.000", "index_shift": "0.00"}
SORT_BY = {("Phase", "phase"): "phase_key", ("Matches", "pp_diff_band"): "pp_diff_band_order",
           ("TestPredictions", "pp_diff_band"): "pp_diff_band_order",
           ("Matches", "chase_pp_wickets_band"): "chase_pp_wickets_order"}


# ============================================================== measures
# (table, name, DAX, format, folder)
MEASURES = [
    ("InningsPhase", "Total Runs", "SUM ( InningsPhase[runs] )", "#,0", "Scoring"),
    ("InningsPhase", "Legal Balls", "SUM ( InningsPhase[legal_balls] )", "#,0", "Scoring"),
    ("InningsPhase", "Run Rate", "DIVIDE ( [Total Runs] * 6, [Legal Balls] )", "0.00", "Scoring"),
    ("InningsPhase", "Boundary %", "DIVIDE ( SUM ( InningsPhase[boundaries] ), SUM ( InningsPhase[balls_faced] ) )", "0.0%", "Scoring"),
    ("InningsPhase", "Dot %", "DIVIDE ( SUM ( InningsPhase[dots] ), [Legal Balls] )", "0.0%", "Scoring"),
    ("InningsPhase", "PP Run Rate", "CALCULATE ( [Run Rate], Phase[phase] = \"Powerplay\" )", "0.00", "Scoring"),
    ("InningsPhase", "PP Boundary %", "CALCULATE ( [Boundary %], Phase[phase] = \"Powerplay\" )", "0.0%", "Scoring"),
    ("InningsPhase", "PP Dot %", "CALCULATE ( [Dot %], Phase[phase] = \"Powerplay\" )", "0.0%", "Scoring"),
    ("InningsPhase", "PP RR First Season", "VAR s = MIN ( Season[season] ) RETURN CALCULATE ( [PP Run Rate], Season[season] = s )", "0.00", "Scoring"),
    ("InningsPhase", "PP RR Last Season", "VAR s = MAX ( Season[season] ) RETURN CALCULATE ( [PP Run Rate], Season[season] = s )", "0.00", "Scoring"),
    ("InningsPhase", "Death Run Rate", "CALCULATE ( [Run Rate], Phase[phase] = \"Death\" )", "0.00", "Scoring"),
    ("InningsPhase", "PP RR Change", "DIVIDE ( [PP RR Last Season], [PP RR First Season] ) - 1", "+0%;-0%;0%", "Scoring"),

    ("Season", "Season Range", "VAR a = MIN ( Season[season] ) VAR b = MAX ( Season[season] ) RETURN IF ( a = b, FORMAT ( a, \"0\" ), FORMAT ( a, \"0\" ) & \"–\" & FORMAT ( b, \"0\" ) )", None, "Labels"),
    ("Season", "First Season", "MIN ( Season[season] )", "0", "Labels"),
    ("Season", "Last Season", "MAX ( Season[season] )", "0", "Labels"),

    ("Matches", "Match Count", "COUNTROWS ( Matches )", "#,0", "Matches"),
    ("Matches", "Avg First-Innings Score", "CALCULATE ( AVERAGE ( Matches[inn1_total_runs] ), Matches[match_status] = \"completed\" )", "0", "Matches"),
    ("Matches", "Avg 1st Inns (10+ matches)", "IF ( [Match Count] >= 10, [Avg First-Innings Score] )", "0", "Matches"),
    ("Matches", "200+ Totals", "CALCULATE ( COUNTROWS ( Matches ), Matches[inn1_total_runs] >= 200 ) + CALCULATE ( COUNTROWS ( Matches ), Matches[inn2_total_runs] >= 200 ) + 0", "#,0", "Matches"),
    ("Matches", "200+ Totals Last Season", "VAR s = MAX ( Season[season] ) RETURN CALCULATE ( [200+ Totals], Season[season] = s )", "#,0", "Matches"),
    ("Matches", "Toss Winner Win %", "AVERAGE ( Matches[toss_winner_won] )", "0.0%", "Matches"),
    ("Matches", "Chose To Field %", "DIVIDE ( CALCULATE ( COUNTROWS ( Matches ), Matches[toss_decision] = \"field\" ), COUNTROWS ( Matches ) )", "0%", "Matches"),
    ("Matches", "Bat-First Win %", "CALCULATE ( AVERAGE ( Matches[bat_first_won] ), Matches[ml_eligible] = 1 )", "0%", "Matches"),
    ("Matches", "Chase Win %", "CALCULATE ( 1 - AVERAGE ( Matches[bat_first_won] ), Matches[ml_eligible] = 1 )", "0%", "Matches"),
    ("Matches", "Higher PP Rate Wins %", "CALCULATE ( AVERAGEX ( Matches, IF ( ( Matches[pp_run_rate_diff] > 0 ) = ( Matches[bat_first_won] = 1 ), 1, 0 ) ), Matches[ml_eligible] = 1, Matches[pp_run_rate_diff] <> 0 )", "0.0%", "Matches"),

    ("TeamMatches", "Team Win %", "AVERAGE ( TeamMatches[won] )", "0.0%", "Teams"),
    ("TeamMatches", "Team Matches", "COUNTROWS ( TeamMatches )", "#,0", "Teams"),

    ("PlayerSeasonPhase", "Player Balls", "SUM ( PlayerSeasonPhase[balls] )", "#,0", "Players"),
    ("PlayerSeasonPhase", "Phase Share", "DIVIDE ( [Player Balls], CALCULATE ( [Player Balls], REMOVEFILTERS ( Phase ) ) )", "0%", "Players"),
    ("PlayerSeasonPhase", "Strike Rate", "DIVIDE ( SUM ( PlayerSeasonPhase[runs] ) * 100, [Player Balls] )", "0.0", "Players"),
    ("PlayerSeasonPhase", "Economy Rate", "DIVIDE ( SUM ( PlayerSeasonPhase[runs] ) * 6, [Player Balls] )", "0.00", "Players"),

    ("PhaseSpells", "Spells", "COUNTROWS ( PhaseSpells )", "#,0", "Phase drift"),
    ("PhaseSpells", "Drift Pool", "COUNTROWS ( FILTER ( SUMMARIZE ( PhaseSpells, PhaseSpells[player_key], PhaseSpells[role_type] ), CALCULATE ( SUM ( PhaseSpells[qualifying_seasons] ) ) >= 2 ) )", "#,0", "Phase drift"),
    ("PhaseSpells", "Players Who Changed", "COUNTROWS ( FILTER ( SUMMARIZE ( PhaseSpells, PhaseSpells[player_key], PhaseSpells[role_type] ), CALCULATE ( COUNTROWS ( PhaseSpells ) ) > 1 ) )", "#,0", "Phase drift"),
    ("PhaseSpells", "Changed %", "DIVIDE ( [Players Who Changed], [Drift Pool] )", "0%", "Phase drift"),
    ("PhaseSpells", "Qualifying Seasons", "SUM ( PhaseSpells[qualifying_seasons] )", "0", "Phase drift"),
    ("PhaseSpells", "Spell Colour", "SWITCH ( SELECTEDVALUE ( PhaseSpells[primary_phase] ), \"Powerplay\", \"#C8553D\", \"Middle\", \"#2E6F95\", \"Death\", \"#2F5D50\", \"#8C9196\" )", None, "Formatting"),

    ("PhaseChanges", "Phase Changes", "COUNTROWS ( PhaseChanges )", "#,0", "Phase drift"),
    ("PhaseChanges", "Moves Touching Middle %", "DIVIDE ( CALCULATE ( COUNTROWS ( PhaseChanges ), FILTER ( PhaseChanges, PhaseChanges[from_phase] = \"Middle\" || PhaseChanges[to_phase] = \"Middle\" ) ), COUNTROWS ( PhaseChanges ) )", "0%", "Phase drift"),

    ("ModelMetrics", "Test Accuracy", "AVERAGE ( ModelMetrics[accuracy] )", "0.0%", "Model"),
    ("ModelMetrics", "ROC AUC", "AVERAGE ( ModelMetrics[roc_auc] )", "0.00", "Model"),
    ("ModelMetrics", "Baseline Accuracy", "CALCULATE ( [Test Accuracy], REMOVEFILTERS ( MLModel ), MLModel[is_baseline] = 1, MLModel[model] <> \"baseline_majority\" )", "0.0%", "Model"),
    ("ModelMetrics", "Selected Model", "CALCULATE ( SELECTEDVALUE ( TestPredictions[model] ), REMOVEFILTERS ( MLModel ) )", None, "Model"),
    ("ModelMetrics", "Model Bar Colour", "IF ( SELECTEDVALUE ( MLModel[model] ) = [Selected Model], \"#1B1F24\", IF ( SELECTEDVALUE ( MLModel[is_baseline] ) = 1, \"#D8D2C4\", \"#A9A294\" ) )", None, "Formatting"),
    ("ModelMetrics", "ROC AUC (selected)", "CALCULATE ( [ROC AUC], TREATAS ( VALUES ( TestPredictions[model] ), MLModel[model] ) )", "0.00", "Model"),

    ("TestPredictions", "Predictions", "COUNTROWS ( TestPredictions )", "#,0", "Model"),
    ("TestPredictions", "Test Matches", "DISTINCTCOUNT ( TestPredictions[match_key] )", "#,0", "Model"),
    ("TestPredictions", "Hit Rate", "AVERAGE ( TestPredictions[correct] )", "0.0%", "Model"),
    ("TestPredictions", "Lift vs Baseline", "( [Hit Rate] - [Baseline Accuracy] ) * 100", "+0.0\" pts\";-0.0\" pts\";0.0\" pts\"", "Model"),
    ("TestPredictions", "P(Bat First Wins)", "AVERAGE ( TestPredictions[prob_bat_first_wins] )", "0.00", "Model"),
    ("TestPredictions", "PP Gap", "AVERAGE ( TestPredictions[pp_run_rate_diff] )", "0.0", "Model"),
    ("TestPredictions", "Confident Miss P", "CALCULATE ( AVERAGE ( TestPredictions[prob_bat_first_wins] ), TestPredictions[correct] = 0, TestPredictions[confidence] >= 0.7 )", "0.00", "Model"),
    ("TestPredictions", "Confident Misses", "CALCULATE ( COUNTROWS ( TestPredictions ), TestPredictions[correct] = 0, TestPredictions[confidence] >= 0.7 ) + 0", "#,0", "Model"),

    ("FeatureImportance", "RF Importance", "CALCULATE ( SUM ( FeatureImportance[abs_value] ), MLModel[model] = \"random_forest\" )", "0.000", "Model"),
]

# (from table, from column, to table, to column, active)
RELATIONSHIPS = [
    ("Matches", "season_key", "Season", "season_key", True),
    ("Matches", "venue_key", "Venue", "venue_key", True),
    ("TeamMatches", "season_key", "Season", "season_key", True),
    ("TeamMatches", "venue_key", "Venue", "venue_key", True),
    ("TeamMatches", "franchise_id", "Franchise", "franchise_id", True),
    ("TeamMatches", "match_key", "Matches", "match_key", False),
    ("InningsPhase", "season_key", "Season", "season_key", True),
    ("InningsPhase", "phase_key", "Phase", "phase_key", True),
    ("InningsPhase", "venue_key", "Venue", "venue_key", True),
    ("InningsPhase", "batting_franchise", "Franchise", "franchise_id", True),
    ("InningsPhase", "match_key", "Matches", "match_key", False),
    ("Team", "franchise_id", "Franchise", "franchise_id", True),
    ("PlayerSeasonPhase", "season_key", "Season", "season_key", True),
    ("PlayerSeasonPhase", "phase_key", "Phase", "phase_key", True),
    ("PlayerSeasonPhase", "player_key", "Player", "player_key", True),
    ("PlayerSeasonPhase", "role_type", "Role", "role_type", True),
    ("PhaseSpells", "player_key", "Player", "player_key", True),
    ("PhaseSpells", "role_type", "Role", "role_type", True),
    ("PhaseChanges", "player_key", "Player", "player_key", True),
    ("PhaseChanges", "role_type", "Role", "role_type", True),
    ("ModelMetrics", "feature_set", "FeatureSet", "feature_set", True),
    ("ModelMetrics", "model", "MLModel", "model", True),
    ("TestPredictions", "season", "Season", "season", True),
    ("TestPredictions", "venue_key", "Venue", "venue_key", True),
    ("TestPredictions", "feature_set", "FeatureSet", "feature_set", True),
    ("TestPredictions", "model", "MLModel", "model", True),
    ("TestPredictions", "match_key", "Matches", "match_key", False),
    ("FeatureImportance", "feature_set", "FeatureSet", "feature_set", True),
    ("FeatureImportance", "model", "MLModel", "model", True),
]

TABLE_ORDER = ["Season", "Phase", "Venue", "Franchise", "Team", "Player", "Role", "Matches", "TeamMatches",
               "InningsPhase", "PlayerSeasonPhase", "PhaseSpells", "PhaseChanges", "FeatureSet", "MLModel",
               "ModelMetrics", "TestPredictions", "FeatureImportance"]


def q(name: str) -> str:
    """Quote a TMDL object name when it is not a plain identifier."""
    if name.replace("_", "").isalnum() and not name[0].isdigit():
        return name
    return "'" + name.replace("'", "''") + "'"


def write_model(tables: dict[str, pd.DataFrame]) -> None:
    sm = OUT / f"{NAME}.SemanticModel"
    d = sm / "definition"
    (d / "tables").mkdir(parents=True)
    (d / "cultures").mkdir()
    (sm / ".pbi").mkdir()
    data_dir = OUT / "data"
    data_dir.mkdir()

    (sm / "definition.pbism").write_text(encoding="utf-8", data=json.dumps({
        "$schema": f"{SCHEMA}/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.0", "settings": {}}, indent=2))
    (sm / ".platform").write_text(encoding="utf-8", data=json.dumps({
        "$schema": f"{SCHEMA}/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": NAME},
        "config": {"version": "2.0", "logicalId": uid("semanticModel")}}, indent=2))
    (sm / ".pbi" / "editorSettings.json").write_text(encoding="utf-8", data=json.dumps({
        "version": "1.0", "parallelQueryLoading": True, "typeDetectionEnabled": True,
        "relationshipImportEnabled": False, "shouldNotifyUserOfNameConflictResolution": True}, indent=2))
    (d / "database.tmdl").write_text(encoding="utf-8", data="database\n\tcompatibilityLevel: 1567\n\n")
    (d / "cultures" / "en-US.tmdl").write_text(encoding="utf-8", data=
        "cultureInfo en-US\n\n\tlinguisticMetadata =\n\t\t\t{\n\t\t\t  \"Version\": \"1.0.0\",\n"
        "\t\t\t  \"Language\": \"en-US\"\n\t\t\t}\n\t\tcontentType: json\n\n")

    order = ["DataFolder"] + TABLE_ORDER
    model = ["model Model", "\tculture: en-US", "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
             "\tsourceQueryCulture: en-US", "\tdataAccessOptions", "\t\tlegacyRedirects",
             "\t\treturnErrorValuesAsNull", "",
             "annotation PBI_QueryOrder = " + json.dumps(order), "",
             "annotation __PBI_TimeIntelligenceEnabled = 0", "",
             "annotation PBIDesktopVersion = 2.137.952.0 (24.10)", "",
             "annotation PBI_ProTooling = [\"DevMode\"]", ""]
    model += [f"ref table {t}" for t in TABLE_ORDER] + ["", "ref cultureInfo en-US", ""]
    (d / "model.tmdl").write_text(encoding="utf-8", data="\n".join(model) + "\n")

    (d / "expressions.tmdl").write_text(encoding="utf-8", data=
        'expression DataFolder = "" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = false]\n'
        f"\tlineageTag: {uid('expr', 'DataFolder')}\n\n"
        "\tannotation PBI_NavigationStepName = Navigation\n\n"
        "\tannotation PBI_ResultType = Text\n\n")

    rel = []
    for ft, fc, tt, tc, active in RELATIONSHIPS:
        rel.append(f"relationship {ft}_{fc}_{tt}")
        if not active:
            rel.append("\tisActive: false")
        rel += [f"\tfromColumn: {ft}.{fc}", f"\ttoColumn: {tt}.{tc}", ""]
    (d / "relationships.tmdl").write_text(encoding="utf-8", data="\n".join(rel) + "\n")

    for t in TABLE_ORDER:
        df = tables[t]
        csv_bytes = df.to_csv(index=False, lineterminator="\n").encode("utf-8")
        (data_dir / f"{t}.csv").write_bytes(csv_bytes)
        b64 = base64.b64encode(gzip.compress(csv_bytes, 9, mtime=0)).decode("ascii")
        lines = [f"table {t}", f"\tlineageTag: {uid('table', t)}", ""]
        for mt, mname, expr, fmt, folder in MEASURES:
            if mt != t:
                continue
            lines.append(f"\tmeasure {q(mname)} = {expr}")
            if fmt:
                lines.append(f"\t\tformatString: {fmt}")
            lines.append(f"\t\tdisplayFolder: {folder}")
            lines.append(f"\t\tlineageTag: {uid('measure', t, mname)}")
            lines.append("")
        types = []
        for c in df.columns:
            mtype, dtype = m_type(df, c)
            types.append(f'{{"{c}", {mtype}}}')
            lines.append(f"\tcolumn {q(c)}")
            lines.append(f"\t\tdataType: {dtype}")
            if dtype == "dateTime":
                lines.append("\t\tformatString: d mmm yyyy")
            elif c in FORMATS:
                lines.append(f"\t\tformatString: {FORMATS[c]}")
            elif dtype == "int64":
                lines.append("\t\tformatString: 0")
            lines.append(f"\t\tlineageTag: {uid('column', t, c)}")
            numeric = dtype in ("int64", "double")
            summ = "sum" if numeric and c not in NO_SUM and c not in HIDDEN and not c.endswith("_key") else "none"
            lines.append(f"\t\tsummarizeBy: {summ}")
            if c in HIDDEN or c.endswith("_key") and c != "franchise_id":
                lines.append("\t\tisHidden")
            if (t, c) in SORT_BY:
                lines.append(f"\t\tsortByColumn: {SORT_BY[(t, c)]}")
            lines.append(f"\t\tsourceColumn: {c}")
            lines.append("")
            lines.append("\t\tannotation SummarizationSetBy = Automatic")
            if dtype == "dateTime":
                lines.append("")
                lines.append("\t\tannotation UnderlyingDateTimeDataType = Date")
            lines.append("")
        m_lines = [
            "let",
            f'    Raw = if DataFolder = null or Text.Length(DataFolder) = 0 then Binary.Decompress(Binary.FromText("{b64}", BinaryEncoding.Base64), Compression.GZip) else File.Contents(DataFolder & "{t}.csv"),',
            '    Source = Csv.Document(Raw, [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
            "    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),",
            f"    Typed = Table.TransformColumnTypes(Promoted, {{{', '.join(types)}}}, \"en-US\")",
            "in",
            "    Typed",
        ]
        lines += [f"\tpartition {t} = m", "\t\tmode: import", "\t\tsource ="]
        lines += ["\t\t\t\t" + ml for ml in m_lines]
        lines += ["", "\tannotation PBI_ResultType = Table", ""]
        (d / "tables" / f"{t}.tmdl").write_text(encoding="utf-8", data="\n".join(lines) + "\n")

    write_diagram(sm, tables)


def write_diagram(sm: Path, tables: dict[str, pd.DataFrame]) -> None:
    """Model view layout: dimensions across the top and bottom, facts in the middle."""
    pos = {
        "Season": (40, 20), "Phase": (300, 20), "Venue": (560, 20), "Franchise": (820, 20), "Team": (1080, 20),
        "Matches": (40, 330), "TeamMatches": (300, 330), "InningsPhase": (560, 330),
        "PlayerSeasonPhase": (820, 330), "TestPredictions": (1080, 330),
        "Player": (820, 640), "Role": (560, 640), "PhaseSpells": (300, 640), "PhaseChanges": (40, 640),
        "FeatureSet": (1080, 640), "MLModel": (1340, 640), "ModelMetrics": (1340, 330),
        "FeatureImportance": (1340, 20),
    }
    nodes = [{"location": {"x": pos[t][0], "y": pos[t][1]}, "nodeIndex": t, "nodeLineageTag": uid("table", t),
              "size": {"height": 260, "width": 234}, "zIndex": i} for i, t in enumerate(TABLE_ORDER)]
    (sm / "diagramLayout.json").write_text(encoding="utf-8", data=json.dumps({
        "version": "1.1.0",
        "diagrams": [{"ordinal": 0, "scrollPosition": {"x": 0, "y": 0}, "nodes": nodes, "name": "All tables",
                      "zoomValue": 70, "pinKeyFieldsToTop": True, "showExtraHeaderInfo": False,
                      "hideKeyFieldsWhenCollapsed": False, "tablesLocked": False}],
        "selectedDiagram": "All tables", "defaultDiagram": "All tables"}, indent=2))


# ============================================================== report helpers
def L(v: str) -> dict:
    return {"expr": {"Literal": {"Value": v}}}


def S(s: str) -> dict:
    return L("'" + s.replace("'", "''") + "'")


def N(x: float) -> dict:
    return L(f"{x}D")


def B(b: bool) -> dict:
    return L("true" if b else "false")


def C(hexv: str) -> dict:
    return {"solid": {"color": S(hexv)}}


def col(t: str, c: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": t}}, "Property": c}}


def mea(t: str, m: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": t}}, "Property": m}}


def ref(field: dict) -> str:
    k = "Column" if "Column" in field else "Measure"
    return f"{field[k]['Expression']['SourceRef']['Entity']}.{field[k]['Property']}"


def proj(field: dict, name: str | None = None, active: bool | None = None) -> dict:
    k = "Column" if "Column" in field else "Measure"
    p = {"field": field, "queryRef": ref(field), "nativeQueryRef": field[k]["Property"]}
    if name:
        p["displayName"] = name
    if active is not None:
        p["active"] = active
    return p


def eq_selector(field: dict, value: str) -> dict:
    return {"data": [{"scopeId": {"Comparison": {"ComparisonKind": 0, "Left": field,
                                                 "Right": {"Literal": {"Value": "'" + value + "'"}}}}}]}


def in_filter(t: str, c: str, values: list[str]) -> dict:
    return {"filter": {"Version": 2, "From": [{"Name": "x", "Entity": t, "Type": 0}],
                       "Where": [{"Condition": {"In": {
                           "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "x"}}, "Property": c}}],
                           "Values": [[{"Literal": {"Value": v}}] for v in values]}}}]}}


def gradient(field: dict, low: str, high: str) -> dict:
    return {"solid": {"color": {"expr": {"FillRule": {
        "Input": field,
        "FillRule": {"linearGradient2": {
            "min": {"color": {"Literal": {"Value": f"'{low}'"}}},
            "max": {"color": {"Literal": {"Value": f"'{high}'"}}},
            "nullColoringStrategy": {"strategy": {"Literal": {"Value": "'asZero'"}}}}}}}}}}


ALL = {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}


class Page:
    def __init__(self, name: str, display: str):
        self.name, self.display = name, display
        self.visuals: list[dict] = []
        self.interactions: list[dict] = []
        self.z = 0

    def add(self, name: str, x: int, y: int, w: int, h: int, visual: dict, filters: list | None = None) -> str:
        self.z += 100
        c = {"$schema": VC_SCHEMA, "name": name,
             "position": {"x": x, "y": y, "z": self.z, "height": h, "width": w, "tabOrder": self.z},
             "visual": visual}
        if filters:
            c["filterConfig"] = {"filters": filters}
        self.visuals.append(c)
        return name

    def no_filter(self, source: str, targets: list[str]) -> None:
        self.interactions += [{"source": source, "target": t, "type": "NoFilter"} for t in targets]


def chrome(title: str | None = None, subtitle: str | None = None, header: bool = True) -> dict:
    vco = {"title": [{"properties": {"show": B(bool(title))} | ({"text": S(title)} if title else {})}],
           "subTitle": [{"properties": {"show": B(bool(subtitle))} | ({"text": S(subtitle)} if subtitle else {})}],
           "background": [{"properties": {"show": B(False)}}],
           "border": [{"properties": {"show": B(False)}}],
           "dropShadow": [{"properties": {"show": B(False)}}]}
    if not header:
        vco["visualHeader"] = [{"properties": {"show": B(False)}}]
    return vco


def chart(vtype: str, roles: dict, title: str, subtitle: str, objects: dict | None = None,
          sort: tuple[dict, str] | None = None) -> dict:
    qs = {role: {"projections": projs} for role, projs in roles.items()}
    query = {"queryState": qs}
    if sort:
        query["sortDefinition"] = {"sort": [{"field": sort[0], "direction": sort[1]}], "isDefaultSort": False}
    return {"visualType": vtype, "query": query, "objects": objects or {},
            "visualContainerObjects": chrome(title, subtitle), "drillFilterOtherVisuals": True}


def run(text: str, font: str = "DIN", size: float = 10, color: str = INK, bold: bool = False,
        italic: bool = False) -> dict:
    style = {"fontFamily": font, "fontSize": f"{size}pt", "color": color}
    if bold:
        style["fontWeight"] = "bold"
    if italic:
        style["fontStyle"] = "italic"
    return {"value": text, "textStyle": style}


def textbox(paragraphs: list[list[dict]], align: str = "left") -> dict:
    paras = [{"textRuns": runs, "horizontalTextAlignment": align} for runs in paragraphs]
    vco = chrome(header=False)
    return {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": paras}}]},
            "visualContainerObjects": vco, "drillFilterOtherVisuals": True}


def rule_box(colour: str) -> dict:
    v = textbox([[run("")]])
    v["visualContainerObjects"]["background"] = [{"properties": {
        "show": B(True), "color": C(colour), "transparency": N(0)}}]
    return v


def card(t: str, m: str, label: str, colour: str = INK, size: int = 30) -> dict:
    objects = {"labels": [{"properties": {"color": C(colour), "fontSize": N(size), "fontFamily": S("Georgia")}}],
               "categoryLabels": [{"properties": {"show": B(True), "color": C(MUTED), "fontSize": N(9),
                                                  "fontFamily": S("DIN")}}]}
    return {"visualType": "card",
            "query": {"queryState": {"Values": {"projections": [proj(mea(t, m), name=label)]}}},
            "objects": objects, "visualContainerObjects": chrome(header=False), "drillFilterOtherVisuals": True}


def slicer(t: str, c: str, mode: str, header: str, single: bool = False, default: list[str] | None = None,
           horizontal: bool = False, search: bool = False) -> dict:
    general = {"orientation": N(1 if horizontal else 0)}
    if default:
        general["filter"] = in_filter(t, c, default)
    if search:
        general["selfFilterEnabled"] = B(True)
    objects = {"data": [{"properties": {"mode": S(mode)}}],
               "general": [{"properties": general}],
               "header": [{"properties": {"show": B(True), "text": S(header), "fontColor": C(MUTED),
                                          "textSize": N(9), "fontFamily": S("DIN")}}],
               "items": [{"properties": {"fontColor": C(INK), "textSize": N(10), "fontFamily": S("DIN")}}],
               "selection": [{"properties": {"singleSelect": B(single), "strictSingleSelect": B(single),
                                             "selectAllCheckboxEnabled": B(False)}}]}
    return {"visualType": "slicer",
            "query": {"queryState": {"Values": {"projections": [proj(col(t, c), active=True)]}}},
            "objects": objects, "visualContainerObjects": chrome(header=False), "drillFilterOtherVisuals": True}


def nav_button(text: str, target: str, current: bool) -> dict:
    colour = INK if current else MUTED
    objects = {
        "icon": [{"properties": {"show": B(False)}, "selector": {"id": "default"}}],
        "text": [{"properties": {"show": B(True), "text": S(text), "fontColor": C(colour), "fontSize": N(9),
                                 "fontFamily": S("DIN"), "bold": B(current)}, "selector": {"id": "default"}}],
        "fill": [{"properties": {"show": B(False)}, "selector": {"id": "default"}}],
        "outline": [{"properties": {"show": B(current), "lineColor": C(INK), "weight": N(1)},
                     "selector": {"id": "default"}}],
    }
    vco = chrome(header=False)
    vco["visualLink"] = [{"properties": {"show": B(True), "type": S("PageNavigation"),
                                         "navigationSection": S(target)}}]
    return {"visualType": "actionButton", "objects": objects, "visualContainerObjects": vco,
            "drillFilterOtherVisuals": True}


def phase_colours(field: dict) -> list[dict]:
    return [{"properties": {"fill": C(v)}, "selector": eq_selector(field, k)} for k, v in PHASE_COLOURS.items()]


def axes(cat_type: str | None = "Categorical", value_show: bool = True, grid: bool = True,
         cat_title: str | None = None, val_title: str | None = None) -> dict:
    ca = {"show": B(True), "showAxisTitle": B(bool(cat_title)), "fontSize": N(8), "labelColor": C(MUTED),
          "gridlineShow": B(False)}
    if cat_type:
        ca["axisType"] = S(cat_type)
    if cat_title:
        ca["titleText"] = S(cat_title)
    va = {"show": B(value_show), "showAxisTitle": B(bool(val_title)), "fontSize": N(8), "labelColor": C(MUTED),
          "gridlineShow": B(grid), "gridlineColor": C("#DDD6C8")}
    if val_title:
        va["titleText"] = S(val_title)
    return {"categoryAxis": [{"properties": ca}], "valueAxis": [{"properties": va}]}


def labels(show: bool = True, size: int = 8, colour: str = INK) -> dict:
    return {"labels": [{"properties": {"show": B(show), "fontSize": N(size), "color": C(colour)}}]}


def legend(show: bool = True) -> dict:
    return {"legend": [{"properties": {"show": B(show), "position": S("TopLeft"), "showTitle": B(False),
                                       "fontSize": N(8), "labelColor": C(SOFT)}}]}


def lines(width: int = 3) -> dict:
    return {"lineStyles": [{"properties": {"strokeWidth": N(width), "lineChartType": S("linear"),
                                           "showMarker": B(False)}}]}


def single_colour(colour: str) -> dict:
    return {"dataPoint": [{"properties": {"fill": C(colour)}}]}


def ref_line(value: float, axis: str = "y1AxisReferenceLine") -> dict:
    return {axis: [{"properties": {"show": B(True), "value": N(value), "lineColor": C(MUTED),
                                   "transparency": N(30), "style": S("dashed"), "width": N(1),
                                   "dataLabelShow": B(False)}, "selector": {"id": "1"}}]}


# ============================================================== pages
KICK = "THE IPL SCOREBOOK  ·  2008–2024"
FOOT = ("Data: Cricsheet ball-by-ball records via Kaggle (IPL Complete Dataset 2008–2024, v3): 1,095 matches, "
        "260,920 deliveries, cleaned into the project warehouse ipl_dw.sqlite. Run rate = runs × 6 ÷ legal balls. "
        "Phases: Powerplay overs 1–6, Middle 7–15, Death 16–20.")
PAGES = [("p1_league", "League"), ("p2_players", "Players"), ("p3_teams", "Teams")]


def header(p: Page, idx: int, headline: str, dek: str) -> None:
    p.add("rule_top", 24, 130, 1232, 2, rule_box(INK))
    p.add("kicker", 24, 12, 700, 20, textbox([[run(f"{KICK}  ·  {idx} OF 3  ·  {p.display.upper()}",
                                                    size=8.5, color=PP, bold=True)]]))
    p.add("headline", 24, 32, 860, 48, textbox([[run(headline, font="Georgia", size=26, color=INK)]]))
    p.add("dek", 24, 82, 860, 46, textbox([[run(dek, size=10, color=SOFT)]]))
    for i, (pname, disp) in enumerate(PAGES):
        p.add(f"nav_{i + 1}", 1040 + i * 72, 8, 68, 24, nav_button(disp, pname, pname == p.name))
    p.add("rule_mid", 24, 212, 1232, 1, rule_box(RULE))
    p.add("footer", 24, 698, 1232, 18, textbox([[run(FOOT, size=7, color=MUTED)]]))


def stat_row(p: Page, stats: list[tuple]) -> list[str]:
    names = []
    for i, (t, m, label, colour) in enumerate(stats):
        names.append(p.add(f"stat_{i + 1}", 24 + i * 310, 140, 290, 66, card(t, m, label, colour)))
        if i:
            p.add(f"stat_sep_{i}", 24 + i * 310 - 10, 150, 1, 46, rule_box(RULE))
    return names


def page_league() -> Page:
    p = Page("p1_league", "League")
    header(p, 1, "The Powerplay got loud.",
           "Teams scored 7.70 runs an over in the first six overs of 2008 and 9.46 in 2024. Most of that jump "
           "came in the last two seasons, after the Impact Player rule gave every side an extra batter.")
    p.add("slicer_season", 900, 40, 170, 84, slicer("Season", "season", "Between", "Seasons"))
    p.add("slicer_country", 1086, 40, 170, 84, slicer("Venue", "country", "Basic", "Grounds in"))
    stat_row(p, [
        ("InningsPhase", "PP RR Last Season", "Powerplay run rate, latest season", PP),
        ("InningsPhase", "PP RR Change", "change since the first season shown", INK),
        ("Matches", "200+ Totals Last Season", "200-plus innings, latest season", INK),
        ("Matches", "Toss Winner Win %", "of toss winners won the match", INK),
    ])
    phase = col("Phase", "phase")
    p.add("main_runrate", 24, 220, 764, 282, chart(
        "lineChart",
        {"Category": [proj(col("Season", "season"), active=True)],
         "Y": [proj(mea("InningsPhase", "Run Rate"), name="Runs per over")],
         "Series": [proj(phase)]},
        "Runs per over, by phase of the innings",
        "Every phase is up. The Powerplay line climbs hardest after 2022.",
        {**axes(cat_type=None), **legend(), **lines(3), "dataPoint": phase_colours(phase)}))
    p.add("pp_detail", 812, 220, 444, 136, chart(
        "lineChart",
        {"Category": [proj(col("Season", "season"), active=True)],
         "Y": [proj(mea("InningsPhase", "PP Boundary %"), name="Balls hit for 4 or 6"),
               proj(mea("InningsPhase", "PP Dot %"), name="Dot balls")]},
        "More boundaries, fewer dots",
        "Powerplay only. Share of legal balls.",
        {**axes(cat_type=None), **legend(), **lines(2),
         "dataPoint": [{"properties": {"fill": C(PP)}, "selector": {"metadata": "InningsPhase.PP Boundary %"}},
                       {"properties": {"fill": C(GREY)}, "selector": {"metadata": "InningsPhase.PP Dot %"}}]}))
    toss = col("Matches", "toss_decision")
    p.add("toss", 812, 366, 444, 136, chart(
        "clusteredBarChart",
        {"Category": [proj(toss, name="Toss winner chose to", active=True)],
         "Y": [proj(mea("Matches", "Toss Winner Win %"), name="Toss winner won")]},
        "Win the toss, bowl first",
        "Toss winners' win rate by their choice (chi-square p = 0.009).",
        {**axes(cat_type=None, value_show=False, grid=False), **labels(size=9),
         "dataPoint": [{"properties": {"fill": C(GREY)}},
                       {"properties": {"fill": C(PP)}, "selector": eq_selector(toss, "field")}]},
        sort=(mea("Matches", "Toss Winner Win %"), "Descending")))
    p.add("rule_row3", 24, 508, 1232, 1, rule_box(RULE))
    era = col("Season", "era")
    p.add("big_totals", 24, 516, 400, 176, chart(
        "columnChart",
        {"Category": [proj(col("Season", "season"), active=True)],
         "Y": [proj(mea("Matches", "200+ Totals"), name="Innings of 200+")],
         "Series": [proj(era)]},
        "Innings of 200 or more",
        "18 in 2022, 37 in 2023, 41 in 2024.",
        {**axes(value_show=False, grid=False), **labels(size=7), **legend(False),
         "dataPoint": [{"properties": {"fill": C(GREY)}, "selector": eq_selector(era, "Before 2023")},
                       {"properties": {"fill": C(PP)}, "selector": eq_selector(era, "Impact Player era (2023-)")}]}))
    p.add("bowl_first", 444, 516, 372, 176, chart(
        "columnChart",
        {"Category": [proj(col("Season", "season"), active=True)],
         "Y": [proj(mea("Matches", "Chose To Field %"), name="Chose to field")]},
        "Captains now bowl first",
        "Share of toss winners who chose to field.",
        {**axes(value_show=False, grid=False), **labels(size=7), **single_colour(SOFT)}))
    p.add("grounds", 836, 516, 420, 176, chart(
        "clusteredBarChart",
        {"Category": [proj(col("Venue", "venue_short"), name="Ground", active=True)],
         "Y": [proj(mea("Matches", "Avg 1st Inns (10+ matches)"), name="Average first innings")],
         "Tooltips": [proj(mea("Matches", "Match Count"), name="Matches")]},
        "Where the first innings runs highest",
        "Average first-innings score, grounds with 10+ matches.",
        {**axes(cat_type=None, value_show=False, grid=False), **labels(size=8), **single_colour(SOFT)},
        sort=(mea("Matches", "Avg 1st Inns (10+ matches)"), "Descending")))
    return p


def page_players() -> Page:
    p = Page("p2_players", "Players")
    header(p, 2, "Nobody stays in one phase for long.",
           "A player's primary phase is the one where he faced or bowled most of his balls, relative to the "
           "league. Of 188 batters who qualified in two or more seasons, 115 changed it at least once; so did "
           "134 of 241 bowlers. Pick a player on the right.")
    role = p.add("slicer_role", 900, 40, 150, 84, slicer("Role", "role_type", "Basic", "Role", single=True,
                                                         default=["'batting'"]))
    player = p.add("slicer_player", 1066, 40, 190, 62, slicer("Player", "player", "Dropdown", "Player",
                                                              single=True, default=["'AT Rayudu'"], search=True))
    stats = stat_row(p, [
        ("PhaseSpells", "Drift Pool", "players with 2+ qualifying seasons", INK),
        ("PhaseSpells", "Players Who Changed", "changed primary phase at least once", INK),
        ("PhaseSpells", "Changed %", "of them changed", PP),
        ("PhaseChanges", "Phase Changes", "phase changes (closed SCD2 rows)", INK),
    ])
    phase = col("Phase", "phase")
    p.add("balls_by_phase", 24, 220, 560, 232, chart(
        "columnChart",
        {"Category": [proj(col("Season", "season"), active=True)],
         "Y": [proj(mea("PlayerSeasonPhase", "Phase Share"), name="Share of his balls")],
         "Series": [proj(phase)]},
        "Where his balls came from, season by season",
        "Share of the selected player's balls in each phase. Use the Player box above to change him.",
        {**axes(value_show=False, grid=False), **labels(size=7, colour="#FFFFFF"), **legend(),
         "dataPoint": phase_colours(phase)}))
    restless = p.add("restless", 604, 220, 300, 232, chart(
        "tableEx",
        {"Values": [proj(col("Player", "player"), name="Player"),
                    proj(mea("PhaseSpells", "Spells"), name="Spells"),
                    proj(mea("PhaseSpells", "Qualifying Seasons"), name="Seasons")]},
        "Most restless careers",
        "Spells = separate runs in one primary phase.",
        {"columnHeaders": [{"properties": {"fontSize": N(8)}}], "values": [{"properties": {"fontSize": N(9)}}]},
        sort=(mea("PhaseSpells", "Spells"), "Descending")))
    status = col("PhaseSpells", "primary_phase")
    p.add("spells", 924, 220, 332, 232, chart(
        "tableEx",
        {"Values": [proj(col("PhaseSpells", "valid_from_season"), name="From"),
                    proj(col("PhaseSpells", "last_seen_season"), name="Last seen"),
                    proj(status, name="Primary phase"),
                    proj(col("PhaseSpells", "qualifying_seasons"), name="Seasons"),
                    proj(col("PhaseSpells", "phase_index_value"), name="Index"),
                    proj(col("PhaseSpells", "spell_status"), name="Row")]},
        "His spells in the warehouse",
        "Rows of dim_player_phase_profile (SCD Type 2).",
        {"columnHeaders": [{"properties": {"fontSize": N(8)}}],
         "values": [{"properties": {"fontSize": N(9)}},
                    {"properties": {"backColor": {"solid": {"color": {"expr": mea("PhaseSpells", "Spell Colour")}}},
                                    "fontColor": C("#FFFFFF")},
                     "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}],
                                  "metadata": "PhaseSpells.primary_phase"}}]},
        sort=(col("PhaseSpells", "valid_from_season"), "Ascending")))
    p.add("rule_row3", 24, 460, 1232, 1, rule_box(RULE))
    moves = p.add("moves", 24, 468, 330, 224, chart(
        "pivotTable",
        {"Rows": [proj(col("PhaseChanges", "from_phase"), name="From")],
         "Columns": [proj(col("PhaseChanges", "to_phase"), name="To")],
         "Values": [proj(mea("PhaseChanges", "Phase Changes"), name="Moves")]},
        "Where players move",
        "Changes of primary phase, row to column.",
        {"values": [{"properties": {"fontSize": N(10)}},
                    {"properties": {"backColor": gradient(mea("PhaseChanges", "Phase Changes"), PAPER, "#8FB3CC")},
                     "selector": {**ALL, "metadata": "PhaseChanges.Phase Changes"}}],
         "rowHeaders": [{"properties": {"fontSize": N(10)}}], "columnHeaders": [{"properties": {"fontSize": N(9)}}],
         "subTotals": [{"properties": {"rowSubtotals": B(True), "columnSubtotals": B(True)}}]}))
    rr = mea("InningsPhase", "Run Rate")
    p.add("franchise_heat", 374, 468, 882, 224, chart(
        "pivotTable",
        {"Rows": [proj(col("Franchise", "latest_name"), name="Franchise"), proj(phase, name="Phase")],
         "Columns": [proj(col("Season", "season"), name="Season")],
         "Values": [proj(rr, name="Run rate")]},
        "Franchise batting run rate, every season",
        "Current franchises. Expand a franchise (+) to split it into Powerplay, Middle and Death.",
        {"values": [{"properties": {"fontSize": N(8)}},
                    {"properties": {"backColor": gradient(rr, PAPER, "#D9806B")},
                     "selector": {**ALL, "metadata": "InningsPhase.Run Rate"}}],
         "rowHeaders": [{"properties": {"fontSize": N(9), "showExpandCollapseButtons": B(True)}}],
         "columnHeaders": [{"properties": {"fontSize": N(8)}}],
         "subTotals": [{"properties": {"rowSubtotals": B(False), "columnSubtotals": B(False)}}]}),
        filters=[{"name": "active_only", "field": col("Franchise", "active"), "type": "Categorical",
                  "filter": in_filter("Franchise", "active", ["1L"])["filter"]}])
    p.no_filter(player, stats + [restless, moves])
    p.no_filter(restless, [v["name"] for v in p.visuals if v["name"] != restless])
    del role
    return p


def page_model() -> Page:
    p = Page("p3_model", "Model")
    header(p, 3, "Six overs tell you two-thirds of the story.",
           "Models trained on 2008–2021 and tuned on 2022 were tested once, on the 142 matches of 2023–24. "
           "Knowing both Powerplays, logistic regression called 68.3% of results: 1.4 points better than the "
           "rule 'the side with the higher Powerplay run rate wins'.")
    p.add("slicer_set", 900, 40, 190, 84, slicer("FeatureSet", "prediction_point", "Basic", "Prediction point",
                                                 single=True, default=["'B: after both Powerplays'"]))
    p.add("slicer_model", 1106, 40, 150, 62, slicer("TestPredictions", "model_label", "Dropdown", "Model",
                                                    single=True, default=["'Logistic regression'"]))
    stat_row(p, [
        ("TestPredictions", "Hit Rate", "of 142 test matches called correctly", PP),
        ("ModelMetrics", "ROC AUC (selected)", "ROC-AUC on the test seasons", INK),
        ("ModelMetrics", "Baseline Accuracy", "best simple rule on the same matches", INK),
        ("TestPredictions", "Lift vs Baseline", "the model's edge over that rule", INK),
    ])
    bars = p.add("every_model", 24, 220, 392, 232, chart(
        "clusteredBarChart",
        {"Category": [proj(col("MLModel", "model_short"), name="Model", active=True)],
         "Y": [proj(mea("ModelMetrics", "Test Accuracy"), name="Test accuracy")],
         "Tooltips": [proj(mea("ModelMetrics", "ROC AUC"), name="ROC-AUC")]},
        "Test accuracy, every model",
        "Same 142 matches. Dark bar = model picked above.",
        {**axes(cat_type=None, value_show=False, grid=False), **labels(size=8),
         "dataPoint": [{"properties": {"fill": {"solid": {"color": {"expr": mea("ModelMetrics", "Model Bar Colour")}}}},
                        "selector": ALL}]},
        sort=(mea("ModelMetrics", "Test Accuracy"), "Descending")))
    p.add("pp_gap", 436, 220, 400, 232, chart(
        "columnChart",
        {"Category": [proj(col("Matches", "pp_diff_band"), name="Powerplay run-rate gap", active=True)],
         "Y": [proj(mea("Matches", "Bat-First Win %"), name="Batting side won")],
         "Tooltips": [proj(mea("Matches", "Match Count"), name="Matches")]},
        "Win the Powerplay, usually win the match",
        "Batting side's win rate by Powerplay run-rate gap.",
        {**axes(value_show=False, grid=False), **labels(size=8), **single_colour(SOFT), **ref_line(0.5)},
        sort=(col("Matches", "pp_diff_band"), "Ascending")))
    outcome = col("TestPredictions", "actual_label")
    p.add("scatter", 856, 220, 400, 232, chart(
        "scatterChart",
        {"Category": [proj(col("TestPredictions", "match_key"), name="Match")],
         "Series": [proj(outcome, name="What happened")],
         "X": [proj(mea("TestPredictions", "PP Gap"), name="Powerplay run-rate gap")],
         "Y": [proj(mea("TestPredictions", "P(Bat First Wins)"), name="Model's chance the batting side wins")]},
        "Every test match, as the model saw it",
        "Above the dashed line = called for the batting side.",
        {**axes(cat_type=None, cat_title="Powerplay run-rate gap", val_title="P(batting side wins)"), **legend(),
         **ref_line(0.5),
         "dataPoint": [{"properties": {"fill": C(INK)}, "selector": eq_selector(outcome, "Bat first won")},
                       {"properties": {"fill": C(OCHRE)}, "selector": eq_selector(outcome, "Chase won")}]}))
    p.add("rule_row3", 24, 460, 1232, 1, rule_box(RULE))
    preds = mea("TestPredictions", "Predictions")
    p.add("confusion", 24, 468, 280, 224, chart(
        "pivotTable",
        {"Rows": [proj(col("TestPredictions", "actual_label"), name="Actual")],
         "Columns": [proj(col("TestPredictions", "predicted_label"), name="Predicted")],
         "Values": [proj(preds, name="Matches")]},
        "Called vs happened",
        "Test matches for the selected model.",
        {"values": [{"properties": {"fontSize": N(12)}},
                    {"properties": {"backColor": gradient(preds, PAPER, "#8FB3CC")},
                     "selector": {**ALL, "metadata": "TestPredictions.Predictions"}}],
         "rowHeaders": [{"properties": {"fontSize": N(9)}}], "columnHeaders": [{"properties": {"fontSize": N(9)}}],
         "subTotals": [{"properties": {"rowSubtotals": B(False), "columnSubtotals": B(False)}}]}))
    p.add("chase_wickets", 324, 468, 300, 224, chart(
        "columnChart",
        {"Category": [proj(col("Matches", "chase_pp_wickets_band"), name="Wickets lost in the chasing Powerplay",
                           active=True)],
         "Y": [proj(mea("Matches", "Chase Win %"), name="Chasing side won")],
         "Tooltips": [proj(mea("Matches", "Match Count"), name="Matches")]},
        "Lose two early, lose the chase",
        "Chasing side's win rate by PP wickets lost.",
        {**axes(value_show=False, grid=False, cat_title="wickets lost in the chasing Powerplay"),
         **labels(size=8), **single_colour(OCHRE), **ref_line(0.5)},
        sort=(col("Matches", "chase_pp_wickets_band"), "Ascending")))
    p.add("importance", 644, 468, 300, 224, chart(
        "clusteredBarChart",
        {"Category": [proj(col("FeatureImportance", "feature_label"), name="Feature", active=True)],
         "Y": [proj(mea("FeatureImportance", "RF Importance"), name="Importance")]},
        "What the forest leaned on",
        "Random forest feature importance.",
        {**axes(cat_type=None, value_show=False, grid=False), **labels(size=7), **single_colour(SOFT)},
        sort=(mea("FeatureImportance", "RF Importance"), "Descending")))
    p.add("misses", 964, 468, 292, 224, chart(
        "tableEx",
        {"Values": [proj(col("TestPredictions", "match_date"), name="Date"),
                    proj(col("TestPredictions", "bat_first_team"), name="Batted first"),
                    proj(col("TestPredictions", "winner_team"), name="Winner"),
                    proj(mea("TestPredictions", "Confident Miss P"), name="P(bat 1st)")]},
        "Confident misses",
        "Wrong calls made with 70% or more confidence.",
        {"columnHeaders": [{"properties": {"fontSize": N(8)}}], "values": [{"properties": {"fontSize": N(8)}}]},
        sort=(col("TestPredictions", "match_date"), "Ascending")))
    p.no_filter(bars, [v["name"] for v in p.visuals if v["name"] != bars])
    return p


def page_teams() -> Page:
    p = Page("p3_teams", "Teams")
    header(p, 3, "Chasing wins, but not for everyone.",
           "Across 1,055 decided matches the chasing side won 54%. Gujarat Titans have the best record of the "
           "current franchises (62%), Punjab Kings the worst (46%). Pick seasons or a franchise on the right.")
    p.add("slicer_season", 900, 40, 170, 84, slicer("Season", "season", "Between", "Seasons"))
    p.add("slicer_franchise", 1086, 40, 170, 62, slicer("Franchise", "latest_name", "Dropdown", "Franchise",
                                                         search=True))
    stat_row(p, [
        ("Matches", "Chase Win %", "of decided matches won by the chasing side", PP),
        ("Matches", "Avg First-Innings Score", "average first-innings score", INK),
        ("Matches", "Match Count", "matches", INK),
        ("Matches", "200+ Totals", "innings of 200 or more", INK),
    ])
    active = [{"name": "active_only", "field": col("Franchise", "active"), "type": "Categorical",
               "filter": in_filter("Franchise", "active", ["1L"])["filter"]}]
    p.add("chase_by_season", 24, 220, 600, 232, chart(
        "columnChart",
        {"Category": [proj(col("Season", "season"), active=True)],
         "Y": [proj(mea("Matches", "Chase Win %"), name="Chasing side won")]},
        "Chasing side's win rate, every season",
        "Above the dashed line, chasing won more often than defending.",
        {**axes(value_show=False, grid=False), **labels(size=7), **single_colour(OCHRE), **ref_line(0.5)}))
    role = col("TeamMatches", "role")
    p.add("team_win", 644, 220, 612, 232, chart(
        "clusteredBarChart",
        {"Category": [proj(col("Franchise", "latest_name"), name="Franchise", active=True)],
         "Y": [proj(mea("TeamMatches", "Team Win %"), name="Win %")],
         "Series": [proj(role, name="Batting")]},
        "Win rate by franchise, batting first vs chasing",
        "Current franchises, all their seasons.",
        {**axes(cat_type=None, value_show=False, grid=False), **labels(size=7), **legend(),
         "dataPoint": [{"properties": {"fill": C(SOFT)}, "selector": eq_selector(role, "Batting first")},
                       {"properties": {"fill": C(OCHRE)}, "selector": eq_selector(role, "Chasing")}]},
        sort=(col("Franchise", "latest_name"), "Ascending")), filters=active)
    p.add("rule_row3", 24, 460, 1232, 1, rule_box(RULE))
    p.add("death_rr", 24, 468, 400, 224, chart(
        "clusteredBarChart",
        {"Category": [proj(col("Franchise", "latest_name"), name="Franchise", active=True)],
         "Y": [proj(mea("InningsPhase", "Death Run Rate"), name="Death-overs run rate")]},
        "Who finishes hardest",
        "Batting run rate in overs 16-20, current franchises.",
        {**axes(cat_type=None, value_show=False, grid=False), **labels(size=8), **single_colour(DEATH)},
        sort=(mea("InningsPhase", "Death Run Rate"), "Descending")), filters=active)
    p.add("pp_rr", 444, 468, 400, 224, chart(
        "clusteredBarChart",
        {"Category": [proj(col("Franchise", "latest_name"), name="Franchise", active=True)],
         "Y": [proj(mea("InningsPhase", "PP Run Rate"), name="Powerplay run rate")]},
        "Who starts fastest",
        "Batting run rate in overs 1-6, current franchises.",
        {**axes(cat_type=None, value_show=False, grid=False), **labels(size=8), **single_colour(PP)},
        sort=(mea("InningsPhase", "PP Run Rate"), "Descending")), filters=active)
    p.add("pom", 864, 468, 392, 224, chart(
        "clusteredBarChart",
        {"Category": [proj(col("Matches", "player_of_match"), name="Player", active=True)],
         "Y": [proj(mea("Matches", "Match Count"), name="Player of the match awards")]},
        "Most player-of-the-match awards",
        "AB de Villiers leads with 25. Scroll for more.",
        {**axes(cat_type=None, value_show=False, grid=False), **labels(size=8), **single_colour(SOFT)},
        sort=(mea("Matches", "Match Count"), "Descending")))
    return p


# ============================================================== report files
def write_report(pages: list[Page]) -> None:
    rp = OUT / f"{NAME}.Report"
    d = rp / "definition"
    (d / "pages").mkdir(parents=True)
    res = rp / "StaticResources"
    (res / "SharedResources" / "BaseThemes").mkdir(parents=True)
    (res / "RegisteredResources").mkdir(parents=True)
    shutil.copy(BASE_THEME, res / "SharedResources" / "BaseThemes" / "CY24SU10.json")
    theme_name = "IPL_Scorebook_Theme.json"
    shutil.copy(THEME_FILE, res / "RegisteredResources" / theme_name)

    (rp / "definition.pbir").write_text(encoding="utf-8", data=json.dumps({
        "$schema": f"{SCHEMA}/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}}, indent=2))
    (rp / ".platform").write_text(encoding="utf-8", data=json.dumps({
        "$schema": f"{SCHEMA}/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": NAME},
        "config": {"version": "2.0", "logicalId": uid("report")}}, indent=2))
    (d / "version.json").write_text(encoding="utf-8", data=json.dumps({
        "$schema": f"{SCHEMA}/item/report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"},
        indent=2))
    report = {
        "$schema": f"{SCHEMA}/item/report/definition/report/1.2.0/schema.json",
        "themeCollection": {
            "baseTheme": {"name": "CY24SU10", "reportVersionAtImport": "5.59", "type": "SharedResources"},
            "customTheme": {"name": theme_name, "reportVersionAtImport": "5.59", "type": "RegisteredResources"}},
        "layoutOptimization": "None",
        "objects": {
            "section": [{"properties": {"verticalAlignment": S("Top")}}],
            "outspacePane": [{"properties": {"visible": B(False), "expanded": B(False)}}]},
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": "CY24SU10", "path": "BaseThemes/CY24SU10.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": theme_name, "path": theme_name, "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True,
                     "allowChangeFilterTypes": True, "useDefaultAggregateDisplayName": True},
        "slowDataSourceSettings": {"isCrossHighlightingDisabled": False, "isSlicerSelectionsButtonEnabled": False,
                                   "isFilterSelectionsButtonEnabled": False, "isFieldWellButtonEnabled": False,
                                   "isApplyAllButtonEnabled": False}}
    (d / "report.json").write_text(encoding="utf-8", data=json.dumps(report, indent=2, ensure_ascii=False))
    (d / "pages" / "pages.json").write_text(encoding="utf-8", data=json.dumps({
        "$schema": f"{SCHEMA}/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [p.name for p in pages], "activePageName": pages[0].name}, indent=2))
    for p in pages:
        pd_ = d / "pages" / p.name
        (pd_ / "visuals").mkdir(parents=True)
        page = {"$schema": PAGE_SCHEMA, "name": p.name, "displayName": p.display, "displayOption": "FitToPage",
                "height": 720, "width": 1280}
        if p.interactions:
            page["visualInteractions"] = p.interactions
        (pd_ / "page.json").write_text(encoding="utf-8", data=json.dumps(page, indent=2, ensure_ascii=False))
        for v in p.visuals:
            vd = pd_ / "visuals" / v["name"]
            vd.mkdir()
            (vd / "visual.json").write_text(encoding="utf-8", data=json.dumps(v, indent=2, ensure_ascii=False))


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    tables = load_tables()
    write_model(tables)
    write_report([page_league(), page_players(), page_teams()])
    (OUT / f"{NAME}.pbip").write_text(encoding="utf-8", data=json.dumps({
        "$schema": f"{SCHEMA}/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
        "settings": {"enableAutoRecovery": True}}, indent=2))
    shutil.copy(HERE / "resources" / "README.txt", OUT / "README.txt")
    (OUT / ".gitignore").write_text(encoding="utf-8", data="**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")
    n = sum(len(list((OUT / f"{NAME}.Report/definition/pages" / p).glob("visuals/*"))) for p, _ in PAGES)
    print(f"wrote {OUT} ({len(tables)} tables, {len(MEASURES)} measures, {len(RELATIONSHIPS)} relationships, "
          f"{n} visuals)")


if __name__ == "__main__":
    main()
