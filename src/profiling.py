"""E3: profile the staged data and test the expected data-quality issues (section 6).

Outputs
  logs/profiling_report.csv        one row per table x column
  logs/data_quality_findings.csv   issues 1-10 of section 6, confirmed or not found
"""
from __future__ import annotations

import re

import pandas as pd

from .config import NULL_TOKENS, Paths


def _as_null(s: pd.Series) -> pd.Series:
    s = s.astype("string").str.strip()
    return s.mask(s.isin(NULL_TOKENS))


def column_profile(name: str, df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col in df.columns:
        if col == "source_row":
            continue
        s = _as_null(df[col])
        num = pd.to_numeric(s, errors="coerce")
        numeric = num.notna().sum() == s.notna().sum() and s.notna().any()
        rows.append({
            "table": name,
            "column": col,
            "rows": len(s),
            "null_count": int(s.isna().sum()),
            "null_pct": round(100 * s.isna().mean(), 2) if len(s) else 0.0,
            "distinct": int(s.nunique()),
            "inferred_type": "numeric" if numeric else "text",
            "min": num.min() if numeric else s.min(),
            "max": num.max() if numeric else s.max(),
            "top_values": "; ".join(f"{k} ({v})" for k, v in s.value_counts().head(5).items()),
        })
    return pd.DataFrame(rows)


def _finding(n: int, issue: str, evidence: str, found: bool) -> dict:
    return {"issue": n, "description": issue, "status": "CONFIRMED" if found else "NOT FOUND",
            "evidence": evidence}


def quality_findings(matches: pd.DataFrame, deliveries: pd.DataFrame) -> pd.DataFrame:
    m = {c: _as_null(matches[c]) for c in matches.columns}
    d = {c: _as_null(deliveries[c]) for c in deliveries.columns}
    teams = pd.concat([m[c] for c in ("team1", "team2", "toss_winner", "winner") if c in m]
                      + [d[c] for c in ("batting_team", "bowling_team") if c in d]).dropna()
    team_names = sorted(teams.unique())
    renames = [t for t in team_names if t in {
        "Delhi Daredevils", "Kings XI Punjab", "Royal Challengers Bangalore",
        "Deccan Chargers", "Pune Warriors", "Kochi Tuskers Kerala"}]
    keyed = pd.Series(team_names).str.lower().str.replace(r"[^a-z]", "", regex=True)
    near = [t for t in team_names if t.endswith("s") and t[:-1] in team_names]

    out = [_finding(1, "Franchise renames and defunct teams", "; ".join(renames), bool(renames))]
    out.append(_finding(2, "Spelling variants of the same team",
                        "; ".join(f"{t[:-1]} / {t}" for t in near) or f"{keyed.nunique()} keys",
                        bool(near)))
    if "method" in m:
        pct = 100 * m["method"].isna().mean()
        out.append(_finding(3, "`method` column almost entirely null", f"{pct:.1f}% null", pct > 90))
    else:
        out.append(_finding(3, "`method` column almost entirely null", "column absent", False))
    res = m.get("result", pd.Series(dtype="string")).str.lower()
    so = m.get("super_over", pd.Series(dtype="string"))
    out.append(_finding(4, "No-result, tied and Super Over matches",
                        f"no result={int((res == 'no result').sum())}, tie={int((res == 'tie').sum())}, "
                        f"super_over=Y: {int((so == 'Y').sum())}",
                        bool((res.isin(['no result', 'tie'])).any() or (so == 'Y').any())))
    players = pd.concat([d[c] for c in ("batter", "batsman", "bowler", "non_striker") if c in d]).dropna()
    pkeys = players.drop_duplicates().to_frame("name")
    pkeys["key"] = pkeys["name"].str.lower().str.replace(r"[^a-z0-9]", "", regex=True)
    variants = pkeys.groupby("key")["name"].nunique()
    out.append(_finding(5, "Player name variants", f"{int((variants > 1).sum())} name keys with >1 spelling; "
                        f"{len(pkeys)} raw names", bool((variants > 1).any())))
    venues = m["venue"].dropna().drop_duplicates() if "venue" in m else pd.Series(dtype="string")
    vkeys = venues.str.split(",").str[0].str.lower().str.replace(r"[^a-z0-9]", "", regex=True)
    city_null = int(m["city"].isna().sum()) if "city" in m else 0
    out.append(_finding(6, "Venue name variants and missing city",
                        f"{len(venues)} raw venues -> {vkeys.nunique()} keys; {city_null} matches without city",
                        len(venues) > vkeys.nunique() or city_null > 0))
    seasons = m["season"].dropna().unique() if "season" in m else []
    text_seasons = [s for s in seasons if not re.fullmatch(r"\d{4}", s)]
    overs = pd.to_numeric(d["over"], errors="coerce")
    out.append(_finding(7, "Season stored as text; over numbering base",
                        f"non-integer seasons: {sorted(text_seasons)}; over min={overs.min()}, max={overs.max()}",
                        bool(text_seasons) or overs.min() == 0))
    et = d.get("extras_type", pd.Series(dtype="string")).str.lower()
    out.append(_finding(8, "Wides and no-balls affect legal-ball counts",
                        f"wides={int((et == 'wides').sum())}, noballs={int((et == 'noballs').sum())}",
                        bool(et.isin(["wides", "noballs"]).any())))
    struct = {c: round(float(100 * d[c].isna().mean()), 1) for c in
              ("extras_type", "player_dismissed", "dismissal_kind", "fielder") if c in d}
    out.append(_finding(9, "Structural nulls in event columns", str(struct), any(v > 0 for v in struct.values())))
    key = deliveries[["match_id", "inning", "over", "ball"]]
    dups = int(key.duplicated().sum())
    out.append(_finding(10, "(match, inning, over, ball) not unique", f"{dups} duplicate keys", dups > 0))
    return pd.DataFrame(out)


def run(paths: Paths, frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    report = pd.concat([column_profile(f"stg_{n}", df) for n, df in frames.items()], ignore_index=True)
    report.to_csv(paths.logs / "profiling_report.csv", index=False)
    findings = quality_findings(frames["matches"], frames["deliveries"])
    findings.to_csv(paths.logs / "data_quality_findings.csv", index=False)
    return findings
