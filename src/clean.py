"""E4 (canonicalise), E5 (normalise) and E6 (flag).

Every rule that changes a value writes a row to the cleaning log with the
number of rows it affected. Raw/staging data is never modified.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from rapidfuzz import fuzz

from .config import NULL_TOKENS, Paths

# Column names differ between Kaggle dataset versions.
DELIVERY_ALIASES = {"batsman": "batter", "id": "match_id"}
MATCH_ALIASES = {"match_id": "id"}
EXTRAS_ALIASES = {"wide": "wides", "noball": "noballs", "bye": "byes", "legbye": "legbyes"}
PLAYER_COLUMNS = ("batter", "bowler", "non_striker", "player_dismissed", "fielder")
FUZZY_REVIEW_SCORE = 85


def key(s: pd.Series | str):
    """Comparison key: lower case, letters and digits only."""
    if isinstance(s, str):
        return re.sub(r"[^a-z0-9]", "", s.lower())
    return s.str.lower().str.replace(r"[^a-z0-9]", "", regex=True)


@dataclass
class CleaningLog:
    rows: list = field(default_factory=list)

    def add(self, step, table, column, rule, raw_value, clean_value, rows_affected):
        if rows_affected:
            self.rows.append({"step": step, "table": table, "column": column, "rule": rule,
                              "raw_value": raw_value, "clean_value": clean_value,
                              "rows_affected": int(rows_affected)})

    def frame(self) -> pd.DataFrame:
        cols = ["step", "table", "column", "rule", "raw_value", "clean_value", "rows_affected"]
        return pd.DataFrame(self.rows, columns=cols)


@dataclass
class CleanResult:
    matches: pd.DataFrame
    deliveries: pd.DataFrame
    team_map: pd.DataFrame
    venue_map: pd.DataFrame
    player_map: pd.DataFrame
    fuzzy_candidates: pd.DataFrame
    unmapped: pd.DataFrame
    log: pd.DataFrame


def nullify(df: pd.DataFrame, table: str, log: CleaningLog) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if col == "source_row":
            continue
        s = out[col].astype("string").str.strip()
        is_null = s.isin(NULL_TOKENS)
        log.add("E5", table, col, "null token -> NULL", "|".join(sorted(s[is_null].unique())), "NULL",
                is_null.sum())
        out[col] = s.mask(is_null)
    return out


def _to_int(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").astype("Int64")


# ---------------------------------------------------------------- canonicalise

def canonical_teams(matches, deliveries, paths: Paths, log: CleaningLog):
    seed = pd.read_csv(paths.mappings / "teams.csv", dtype=str).fillna("")
    by_key = {key(r.raw_name): r for r in seed.itertuples()}
    cols = [(matches, "matches", c) for c in ("team1", "team2", "toss_winner", "winner")] + \
           [(deliveries, "deliveries", c) for c in ("batting_team", "bowling_team")]
    raw_counts = pd.concat([df[c].dropna() for df, _, c in cols]).value_counts()
    rows, unmapped = [], []
    for raw, n in raw_counts.items():
        hit = by_key.get(key(raw))
        if hit is None:
            unmapped.append({"entity_type": "team", "raw_value": raw, "rows": int(n)})
            continue
        rows.append({"raw_name": raw, "canonical_name": hit.canonical_name,
                     "franchise_id": hit.franchise_id, "rows": int(n),
                     "method": "exact" if raw == hit.raw_name else "normalised key"})
    team_map = pd.DataFrame(rows, columns=["raw_name", "canonical_name", "franchise_id", "rows", "method"])
    lookup = dict(zip(team_map.raw_name, team_map.canonical_name))
    for df, table, col in cols:
        before = df[col]
        df[col] = before.map(lookup)
        for raw, canon in lookup.items():
            if raw != canon:
                log.add("E4", table, col, "team canonical name", raw, canon, (before == raw).sum())
    return team_map, unmapped


def _strip_city_suffix(name: str, cities: set[str]) -> str:
    while "," in name:
        head, tail = name.rsplit(",", 1)
        if key(tail) not in cities:
            break
        name = head.strip()
    return name


def canonical_venues(matches, paths: Paths, log: CleaningLog):
    seed = pd.read_csv(paths.mappings / "venues.csv", dtype=str).fillna("")
    city_seed = pd.read_csv(paths.mappings / "cities.csv", dtype=str).fillna("")
    city_map = dict(zip(city_seed.raw_city, city_seed.canonical_city))

    before = matches["city"]
    matches["city"] = before.replace(city_map)
    for raw, canon in city_map.items():
        log.add("E4", "matches", "city", "city canonical name", raw, canon, (before == raw).sum())

    cities = {key(c) for c in pd.concat([before.dropna(), matches["city"].dropna(),
                                         seed["city"], city_seed["raw_city"]]) if c}
    manual = {key(r.raw_name): r for r in seed.itertuples()}

    venues = matches[["venue", "city"]].dropna(subset=["venue"])
    info = []
    for raw in venues["venue"].unique():
        stripped = _strip_city_suffix(raw, cities)
        hit = manual.get(key(raw)) or manual.get(key(stripped))
        info.append({"raw_name": raw, "stripped": stripped, "vkey": key(stripped),
                     "manual_name": hit.canonical_name if hit else None,
                     "manual_city": hit.city if hit and hit.city else None})
    info = pd.DataFrame(info, columns=["raw_name", "stripped", "vkey", "manual_name", "manual_city"])
    counts = venues["venue"].value_counts()
    info["rows"] = info["raw_name"].map(counts).astype(int)

    # Venues without a manual rule: group by key, canonical = most frequent stripped spelling.
    auto = info[info.manual_name.isna()].sort_values(["vkey", "rows", "stripped"],
                                                     ascending=[True, False, True])
    auto_name = auto.groupby("vkey")["stripped"].first()
    info["canonical_name"] = info["manual_name"].fillna(info["vkey"].map(auto_name))
    info["method"] = np.where(info.manual_name.notna(), "manual", "normalised key")

    # City: manual seed wins, else most frequent recorded city for the canonical venue.
    lookup = dict(zip(info.raw_name, info.canonical_name))
    with_city = pd.DataFrame({"canonical": venues["venue"].map(lookup), "city": venues["city"]}).dropna()
    mode_city = with_city.groupby("canonical")["city"].agg(lambda s: s.value_counts().index[0])
    manual_city = info.dropna(subset=["manual_city"]).groupby("canonical_name")["manual_city"].first()
    venue_city = mode_city.combine_first(manual_city)
    venue_city.update(manual_city)
    info["city"] = info["canonical_name"].map(venue_city)

    before = matches["venue"]
    matches["venue"] = before.map(lookup)
    for r in info.itertuples():
        if r.raw_name != r.canonical_name:
            log.add("E4", "matches", "venue", f"venue canonical name ({r.method})", r.raw_name,
                    r.canonical_name, r.rows)
    missing_city = matches["city"].isna()
    filled_venues = matches.loc[missing_city, "venue"]
    matches.loc[missing_city, "city"] = filled_venues.map(venue_city)
    for v, n in filled_venues[filled_venues.isin(venue_city.index)].value_counts().items():
        log.add("E4", "matches", "city", "fill city from venue mapping", f"NULL ({v})",
                venue_city[v], n)
    unmapped = [{"entity_type": "venue_city", "raw_value": v, "rows": int(n)}
                for v, n in matches.loc[matches["city"].isna(), "venue"].value_counts().items()]
    venue_map = info[["raw_name", "canonical_name", "city", "rows", "method"]]
    return venue_map, unmapped


def canonical_players(matches, deliveries, paths: Paths, log: CleaningLog):
    """Merge only on identical name keys or approved manual rules; fuzzy pairs go to review."""
    if "fielder" in deliveries:
        f = deliveries["fielder"]
        sub = f.str.contains(r"\(sub\)", regex=True, na=False)
        deliveries.loc[sub, "fielder"] = f[sub].str.replace(r"\s*\(sub\)", "", regex=True).str.strip()
        log.add("E4", "deliveries", "fielder", "strip '(sub)' marker", "<name> (sub)", "<name>", sub.sum())

    cols = [(deliveries, "deliveries", c) for c in PLAYER_COLUMNS if c in deliveries] + \
           [(matches, "matches", "player_of_match")]
    raw = pd.concat([df[c].dropna() for df, _, c in cols])
    raw = raw.str.replace(r"\s+", " ", regex=True).str.strip()
    counts = raw.value_counts()
    names = pd.DataFrame({"raw_name": counts.index, "rows": counts.values})
    names["nkey"] = key(names["raw_name"])

    seed = pd.read_csv(paths.mappings / "players.csv", dtype=str).fillna("")
    merges = seed[seed.decision.str.lower() == "merge"]
    manual = dict(zip(merges.raw_name, merges.canonical_name))

    names = names.sort_values(["nkey", "rows", "raw_name"], ascending=[True, False, True])
    by_key = names.groupby("nkey")["raw_name"].first()
    names["canonical_name"] = names["nkey"].map(by_key)
    names["method"] = np.where(names.raw_name == names.canonical_name, "exact", "normalised key")
    override = names.raw_name.map(manual).fillna(names.canonical_name.map(manual))
    names["canonical_name"] = override.fillna(names["canonical_name"])
    names.loc[override.notna(), "method"] = "manual"

    lookup = dict(zip(names.raw_name, names.canonical_name))
    for df, table, col in cols:
        before = df[col].str.replace(r"\s+", " ", regex=True).str.strip()
        df[col] = before.map(lookup)
    for r in names[names.raw_name != names.canonical_name].itertuples():
        log.add("E4", "all", "player columns", f"player canonical name ({r.method})", r.raw_name,
                r.canonical_name, r.rows)

    fuzzy = fuzzy_candidates(names.drop_duplicates("canonical_name")["canonical_name"], seed)
    player_map = names[["raw_name", "canonical_name", "rows", "method"]].reset_index(drop=True)
    return player_map, fuzzy


def fuzzy_candidates(canonical: pd.Series, seed: pd.DataFrame) -> pd.DataFrame:
    """Pairs of distinct canonical names sharing a surname that look alike, for manual review."""
    decided = {frozenset((r.raw_name, r.canonical_name)) for r in seed.itertuples()}
    df = pd.DataFrame({"name": canonical.values})
    df["surname"] = key(df["name"].str.split().str[-1])
    rows = []
    for _, grp in df.groupby("surname"):
        names = grp["name"].tolist()
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                score = fuzz.ratio(key(a), key(b))
                if score >= FUZZY_REVIEW_SCORE and frozenset((a, b)) not in decided:
                    rows.append({"name_a": a, "name_b": b, "score": round(score, 1)})
    return pd.DataFrame(rows, columns=["name_a", "name_b", "score"]).sort_values(
        "score", ascending=False, ignore_index=True)


# ------------------------------------------------------------------ normalise

def normalise_matches(m: pd.DataFrame, has_super_over_innings: set, log: CleaningLog) -> pd.DataFrame:
    m = m.rename(columns={k: v for k, v in MATCH_ALIASES.items() if k in m and v not in m})
    m["id"] = _to_int(m["id"])

    date = pd.to_datetime(m["date"], format="ISO8601", errors="coerce")
    retry = date.isna() & m["date"].notna()
    date[retry] = pd.to_datetime(m.loc[retry, "date"], dayfirst=True, errors="coerce", format="mixed")
    log.add("E5", "matches", "date", "parse non-ISO date (day first)", "dd/mm/yyyy", "yyyy-mm-dd", retry.sum())
    m["match_date"] = date.dt.strftime("%Y-%m-%d")

    # Season: the year the match was played. "2007/08" style labels are Kaggle artefacts.
    season_text = m["season"]
    year = date.dt.year.astype("Int64")
    fallback = year.isna()
    year[fallback] = _to_int(season_text[fallback].str[:4])
    for raw in season_text[~fallback].unique():
        rows = (season_text == raw) & ~fallback
        years = year[rows].unique()
        if len(years) == 1 and str(raw) != str(years[0]):
            log.add("E5", "matches", "season", "season label -> year of match date", raw, int(years[0]),
                    rows.sum())
    log.add("E5", "matches", "season", "season from label (date missing)", "text", "int", fallback.sum())
    m["season_year"] = year

    m["toss_decision"] = m["toss_decision"].str.lower()

    # Result type. Older versions: result in {normal, tie, no result} + win_by_runs/win_by_wickets.
    result = m["result"].str.lower() if "result" in m else pd.Series(pd.NA, index=m.index, dtype="string")
    if "result_margin" not in m and "win_by_runs" in m:
        runs, wkts = _to_int(m["win_by_runs"]).fillna(0), _to_int(m["win_by_wickets"]).fillna(0)
        normal = result == "normal"
        result = result.mask(normal & (runs > 0), "runs").mask(normal & (runs == 0), "wickets")
        m["result_margin"] = runs.where(runs > 0, wkts).where(result.isin(["runs", "wickets"]))
        log.add("E5", "matches", "result", "derive result_margin from win_by_*", "normal", "runs/wickets",
                normal.sum())
    no_result = result.isin(["no result", "no_result"]) | (result.isna() & m["winner"].isna())
    m["result_type"] = result.mask(no_result, "no_result")
    m["result_margin"] = _to_int(m["result_margin"]) if "result_margin" in m else pd.NA
    for col in ("target_runs", "target_overs"):
        m[col] = pd.to_numeric(m[col], errors="coerce") if col in m else np.nan

    # E6 flags
    so = m["super_over"].str.upper().isin(["Y", "1", "TRUE"]) if "super_over" in m else False
    m["is_super_over"] = (so | m["id"].isin(has_super_over_innings)).astype(int)
    if "method" in m:
        m["is_dl_applied"] = m["method"].notna().astype(int)
        log.add("E6", "matches", "method", "derive is_dl_applied; drop raw column", "D/L", 1,
                m["method"].notna().sum())
    elif "dl_applied" in m:
        m["is_dl_applied"] = (_to_int(m["dl_applied"]).fillna(0) > 0).astype(int)
    else:
        m["is_dl_applied"] = 0
    m["match_status"] = np.select([m.result_type == "no_result", m.result_type == "tie"],
                                  ["no_result", "tie"], "completed")
    keep = ["id", "season_year", "match_date", "city", "venue", "team1", "team2", "toss_winner",
            "toss_decision", "winner", "result_type", "result_margin", "target_runs", "target_overs",
            "is_super_over", "is_dl_applied", "match_status", "player_of_match", "source_row"]
    return m[keep].rename(columns={"id": "match_id"})


def _derive_extras_type(d: pd.DataFrame, log: CleaningLog) -> pd.Series:
    """Older Kaggle versions have wide_runs/noball_runs/... instead of extras_type."""
    out = pd.Series(pd.NA, index=d.index, dtype="string")
    for col, label in (("penalty_runs", "penalty"), ("legbye_runs", "legbyes"), ("bye_runs", "byes"),
                       ("noball_runs", "noballs"), ("wide_runs", "wides")):
        if col in d:
            hit = _to_int(d[col]).fillna(0) > 0
            out[hit] = label
    log.add("E5", "deliveries", "extras_type", "derive from *_runs columns", "*_runs", "extras_type",
            out.notna().sum())
    return out


def normalise_deliveries(d: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    d = d.rename(columns={k: v for k, v in DELIVERY_ALIASES.items() if k in d and v not in d})
    for col in ("match_id", "inning", "over", "ball", "batsman_runs", "extra_runs", "total_runs"):
        d[col] = _to_int(d[col])
    for col in ("batsman_runs", "extra_runs", "total_runs"):
        missing = d[col].isna()
        log.add("E5", "deliveries", col, "missing runs -> 0", "NULL", 0, missing.sum())
        d[col] = d[col].fillna(0)

    if d["over"].min() == 0:
        log.add("E5", "deliveries", "over", "shift 0-based overs to 1-20", "0..19", "1..20", len(d))
        d["over"] = d["over"] + 1

    if "extras_type" not in d:
        d["extras_type"] = _derive_extras_type(d, log)
    et = d["extras_type"].str.lower().replace(EXTRAS_ALIASES)
    log.add("E5", "deliveries", "extras_type", "structural null -> 'none'", "NULL", "none", et.isna().sum())
    d["extras_type"] = et.fillna("none")
    dk = d["dismissal_kind"].str.lower()
    log.add("E5", "deliveries", "dismissal_kind", "structural null -> 'none'", "NULL", "none", dk.isna().sum())
    d["dismissal_kind"] = dk.fillna("none")
    if "is_wicket" in d:
        d["is_wicket"] = _to_int(d["is_wicket"]).fillna(0).astype(int)
    else:
        d["is_wicket"] = d["player_dismissed"].notna().astype(int)
        log.add("E5", "deliveries", "is_wicket", "derive from player_dismissed", "", "0/1", len(d))

    so_col = _to_int(d["is_super_over"]).fillna(0) > 0 if "is_super_over" in d else False
    d["is_super_over_innings"] = ((d["inning"] > 2) | so_col).astype(int)

    # Ball numbers repeat on extras; the grain uses source order within (match, inning).
    d = d.sort_values("source_row", kind="stable")
    d["delivery_seq"] = d.groupby(["match_id", "inning"]).cumcount() + 1

    # E6 legal-ball and measure flags
    d["is_legal_for_bowler"] = (~d["extras_type"].isin(["wides", "noballs"])).astype(int)
    d["is_faced_by_batter"] = (d["extras_type"] != "wides").astype(int)
    d["is_boundary"] = d["batsman_runs"].isin([4, 6]).astype(int)
    d["is_dot"] = ((d["is_legal_for_bowler"] == 1) & (d["total_runs"] == 0)).astype(int)
    keep = ["match_id", "inning", "delivery_seq", "batting_team", "bowling_team", "over", "ball",
            "batter", "bowler", "non_striker", "batsman_runs", "extra_runs", "total_runs",
            "extras_type", "is_wicket", "player_dismissed", "dismissal_kind", "fielder",
            "is_super_over_innings", "is_legal_for_bowler", "is_faced_by_batter", "is_boundary",
            "is_dot", "source_row"]
    return d[keep].reset_index(drop=True)


def run(paths: Paths, staged: dict[str, pd.DataFrame]) -> CleanResult:
    log = CleaningLog()
    matches = nullify(staged["matches"], "matches", log)
    deliveries = nullify(staged["deliveries"], "deliveries", log)

    deliveries = normalise_deliveries(deliveries, log)
    so_matches = set(deliveries.loc[deliveries.is_super_over_innings == 1, "match_id"].unique())
    matches = normalise_matches(matches, so_matches, log)

    team_map, unmapped_teams = canonical_teams(matches, deliveries, paths, log)
    venue_map, unmapped_venues = canonical_venues(matches, paths, log)
    player_map, fuzzy = canonical_players(matches, deliveries, paths, log)
    unmapped = pd.DataFrame(unmapped_teams + unmapped_venues, columns=["entity_type", "raw_value", "rows"])

    team_map.to_csv(paths.clean / "map_team.csv", index=False)
    venue_map.to_csv(paths.clean / "map_venue.csv", index=False)
    player_map.to_csv(paths.clean / "map_player.csv", index=False)
    fuzzy.to_csv(paths.logs / "player_fuzzy_candidates.csv", index=False)
    unmapped.to_csv(paths.logs / "unmapped_entities.csv", index=False)
    log_df = log.frame()
    log_df.to_csv(paths.logs / "cleaning_log.csv", index=False)
    return CleanResult(matches, deliveries, team_map, venue_map, player_map, fuzzy, unmapped, log_df)
