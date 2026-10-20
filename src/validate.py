"""E11: validation gates G1-G9 (section 9.2).

Each gate is a SQL check against the warehouse. A gate returns PASS, FAIL or
SKIP plus the number of offending rows and a short detail. The pipeline stops
with a non-zero exit code if any gate fails.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

DESCRIPTIONS = {
    "G1": "Referential integrity: every foreign key in every fact resolves to a dimension row",
    "G2": "Grain: zero duplicates on (match, inning, delivery_seq)",
    "G3": "total_runs = batsman_runs + extra_runs on every delivery",
    "G4": "Completed regular matches: target_runs = first-innings total + 1 (exceptions listed)",
    "G5": "Regular innings <= 120 legal balls; Super Over innings <= 6 (7-ball overs listed as exceptions)",
    "G6": "No raw team/venue/player string unmapped; distinct franchises = expected",
    "G7": "Winner is team1, team2 or an explicit non-result category",
    "G8": "SCD2 integrity: no overlapping spells; exactly one current row per player and role",
    "G9": "Row-count reconciliation across raw, staging and warehouse",
}


@dataclass
class GateResult:
    gate: str
    status: str
    failures: int
    detail: str

    @property
    def passed(self) -> bool:
        return self.status != "FAIL"


def _scalar(conn, sql, params=()):
    return conn.execute(sql, params).fetchone()[0]


def _result(gate, failures, detail, skip=False) -> GateResult:
    status = "SKIP" if skip else ("PASS" if failures == 0 else "FAIL")
    return GateResult(gate, status, int(failures), detail)


FOREIGN_KEYS = [
    # (fact table, column, dimension, dimension key, nullable). Every key runs fact -> dimension.
    ("fact_delivery", "match_key", "dim_match", "match_key", False),
    ("fact_delivery", "date_key", "dim_date", "date_key", False),
    ("fact_delivery", "season_key", "dim_season", "season_key", False),
    ("fact_delivery", "venue_key", "dim_venue", "venue_key", False),
    ("fact_delivery", "phase_key", "dim_phase", "phase_key", True),
    ("fact_delivery", "batting_team_key", "dim_team", "team_key", False),
    ("fact_delivery", "bowling_team_key", "dim_team", "team_key", False),
    ("fact_delivery", "batter_key", "dim_player", "player_key", False),
    ("fact_delivery", "bowler_key", "dim_player", "player_key", False),
    ("fact_delivery", "non_striker_key", "dim_player", "player_key", False),
    ("fact_delivery", "player_dismissed_key", "dim_player", "player_key", True),
    ("fact_delivery", "fielder_key", "dim_player", "player_key", True),
    ("fact_match_summary", "match_key", "dim_match", "match_key", False),
    ("fact_match_summary", "date_key", "dim_date", "date_key", False),
    ("fact_match_summary", "season_key", "dim_season", "season_key", False),
    ("fact_match_summary", "venue_key", "dim_venue", "venue_key", False),
    ("fact_match_summary", "bat_first_team_key", "dim_team", "team_key", False),
    ("fact_match_summary", "chase_team_key", "dim_team", "team_key", False),
    ("fact_match_summary", "toss_winner_key", "dim_team", "team_key", False),
    ("fact_match_summary", "winner_key", "dim_team", "team_key", True),
    ("fact_match_summary", "player_of_match_key", "dim_player", "player_key", True),
    ("fact_player_season_phase", "player_key", "dim_player", "player_key", False),
    ("fact_player_season_phase", "season_key", "dim_season", "season_key", False),
    ("fact_player_season_phase", "phase_key", "dim_phase", "phase_key", False),
    ("fact_player_season_phase", "profile_key", "dim_player_phase_profile", "profile_key", True),
]


def g1(conn, ctx) -> GateResult:
    bad = []
    for table, col, dim, dkey, nullable in FOREIGN_KEYS:
        n = _scalar(conn, f"""
            SELECT COUNT(*) FROM {table} f LEFT JOIN {dim} d ON f.{col} = d.{dkey}
            WHERE (f.{col} IS NOT NULL AND d.{dkey} IS NULL) {'' if nullable else f'OR f.{col} IS NULL'}""")
        if n:
            bad.append((f"{table}.{col}", n))
    n = len(conn.execute("PRAGMA foreign_key_check").fetchall())
    if n:
        bad.append(("PRAGMA foreign_key_check", n))
    return _result("G1", sum(c for _, c in bad),
                   "; ".join(f"{k}: {v}" for k, v in bad) or f"{len(FOREIGN_KEYS)} foreign keys checked")


def g2(conn, ctx) -> GateResult:
    n = _scalar(conn, """SELECT COUNT(*) FROM (SELECT 1 FROM fact_delivery
                         GROUP BY match_key, inning, delivery_seq HAVING COUNT(*) > 1)""")
    return _result("G2", n, f"{n} duplicated grain keys")


def g3(conn, ctx) -> GateResult:
    n = _scalar(conn, "SELECT COUNT(*) FROM fact_delivery WHERE total_runs != batsman_runs + extra_runs")
    return _result("G3", n, f"{n} deliveries where total_runs != batsman_runs + extra_runs")


def g4(conn, ctx) -> GateResult:
    if _scalar(conn, "SELECT COUNT(*) FROM dim_match WHERE target_runs IS NOT NULL") == 0:
        return _result("G4", 0, "target_runs not present in this dataset version", skip=True)
    df = pd.read_sql("""
        SELECT m.source_match_id, m.target_runs, m.target_overs, m.is_dl_applied,
               s.inn1_total_runs, s.inn1_legal_balls
        FROM dim_match m JOIN fact_match_summary s USING (match_key)
        WHERE m.match_status IN ('completed', 'tie') AND m.target_runs IS NOT NULL
          AND s.inn1_total_runs IS NOT NULL""", conn)
    mismatch = df[df.target_runs != df.inn1_total_runs + 1].copy()
    explained = (mismatch.is_dl_applied == 1) | (mismatch.target_overs.fillna(20) < 20)
    mismatch["explanation"] = explained.map({True: "shortened or D/L match", False: "UNEXPLAINED"})
    out = ctx.get("logs")
    if out is not None:
        mismatch.to_csv(Path(out) / "g4_exceptions.csv", index=False)
    n_bad = int((~explained).sum())
    return _result("G4", n_bad, f"{len(df)} matches checked; {int(explained.sum())} listed exceptions "
                                f"(shortened/D-L); {n_bad} unexplained (see logs/g4_exceptions.csv)")


def g5(conn, ctx) -> GateResult:
    # An over with 7 legal balls is a real umpire miscount and is recorded as bowled (D-20):
    # it raises that innings' limit by one ball and is listed in logs/g5_exceptions.csv.
    # An over with 8+ legal balls, or an innings over its limit without such overs, fails.
    overs = pd.read_sql("""
        SELECT m.source_match_id, f.match_key, f.inning, f.over, f.is_super_over_innings AS so,
               SUM(f.is_legal_for_bowler) AS legal
        FROM fact_delivery f JOIN dim_match m USING (match_key)
        GROUP BY f.match_key, f.inning, f.over""", conn)
    seven = overs[overs.legal == 7]
    out = ctx.get("logs")
    if out is not None:
        seven.assign(explanation="umpire miscount: 7 legal balls in the over").drop(
            columns="match_key").to_csv(Path(out) / "g5_exceptions.csv", index=False)
    inn = overs.groupby(["match_key", "inning", "so"], as_index=False).agg(
        legal=("legal", "sum"), extra=("legal", lambda s: int((s == 7).sum())),
        worst_over=("legal", "max"))
    limit = inn.so.map({0: 120, 1: 6}) + inn.extra
    n = int(((inn.legal > limit) | (inn.worst_over > 7)).sum())
    over_limit = int((inn.legal > inn.so.map({0: 120, 1: 6})).sum())
    return _result("G5", n, f"{n} innings over the legal-ball limit unexplained; {len(seven)} seven-ball "
                            f"overs listed ({over_limit} innings reach 121; see logs/g5_exceptions.csv)")


def g6(conn, ctx) -> GateResult:
    unmapped = _scalar(conn, "SELECT COALESCE(SUM(rows), 0) FROM audit_unmapped")
    kinds = _scalar(conn, "SELECT COUNT(*) FROM audit_unmapped")
    franchises = _scalar(conn, "SELECT COUNT(DISTINCT franchise_id) FROM map_team")
    expected = ctx.get("expected_franchises")
    wrong_count = expected is not None and franchises != expected
    detail = f"{kinds} unmapped raw strings ({unmapped} rows); {franchises} franchises"
    if expected is not None:
        detail += f" (expected {expected})"
    return _result("G6", kinds + int(wrong_count), detail)


def g7(conn, ctx) -> GateResult:
    n = _scalar(conn, """
        SELECT COUNT(*) FROM dim_match m JOIN fact_match_summary s USING (match_key)
        WHERE (s.winner_key IS NOT NULL AND s.winner_key NOT IN (s.bat_first_team_key, s.chase_team_key))
           OR (s.winner_key IS NULL AND m.match_status NOT IN ('no_result', 'tie'))""")
    return _result("G7", n, f"{n} matches with an invalid winner")


def g8(conn, ctx) -> GateResult:
    overlaps = _scalar(conn, """
        SELECT COUNT(*) FROM dim_player_phase_profile a JOIN dim_player_phase_profile b
          ON a.player_key = b.player_key AND a.role_type = b.role_type AND a.profile_key < b.profile_key
        WHERE a.valid_from_season <= COALESCE(b.valid_to_season, 9999)
          AND b.valid_from_season <= COALESCE(a.valid_to_season, 9999)""")
    not_one_current = _scalar(conn, """
        SELECT COUNT(*) FROM (SELECT SUM(is_current) c FROM dim_player_phase_profile
                              GROUP BY player_key, role_type) WHERE c != 1""")
    bad_current = _scalar(conn, """SELECT COUNT(*) FROM dim_player_phase_profile
        WHERE (is_current = 1) != (valid_to_season IS NULL)""")
    n = overlaps + not_one_current + bad_current
    return _result("G8", n, f"{overlaps} overlapping spell pairs; {not_one_current} player-roles without "
                            f"exactly one current row; {bad_current} rows with inconsistent is_current")


def g9(conn, ctx) -> GateResult:
    raw = ctx.get("raw_counts", {})
    counts = {
        "raw deliveries": raw.get("deliveries"),
        "stg_deliveries": _scalar(conn, "SELECT COUNT(*) FROM stg_deliveries"),
        "clean_deliveries": _scalar(conn, "SELECT COUNT(*) FROM clean_deliveries"),
        "fact_delivery": _scalar(conn, "SELECT COUNT(*) FROM fact_delivery"),
        "raw matches": raw.get("matches"),
        "stg_matches": _scalar(conn, "SELECT COUNT(*) FROM stg_matches"),
        "dim_match": _scalar(conn, "SELECT COUNT(*) FROM dim_match"),
        "fact_match_summary": _scalar(conn, "SELECT COUNT(*) FROM fact_match_summary"),
    }
    d = {v for k, v in counts.items() if "deliver" in k and v is not None}
    m = {v for k, v in counts.items() if "deliver" not in k and v is not None}
    orphan = _scalar(conn, """SELECT COUNT(DISTINCT match_id) FROM clean_deliveries
                              WHERE match_id NOT IN (SELECT match_id FROM clean_matches)""")
    n = (len(d) - 1) + (len(m) - 1) + orphan
    return _result("G9", n, "; ".join(f"{k}={v}" for k, v in counts.items())
                   + f"; deliveries for unknown matches={orphan}")


GATES = {"G1": g1, "G2": g2, "G3": g3, "G4": g4, "G5": g5, "G6": g6, "G7": g7, "G8": g8, "G9": g9}


def run_gates(conn: sqlite3.Connection, gates, ctx: dict) -> list[GateResult]:
    results = []
    for g in gates:
        try:
            results.append(GATES[g](conn, ctx))
        except sqlite3.Error as e:  # a missing table is a failure, not a crash
            results.append(GateResult(g, "FAIL", 1, f"error: {e}"))
    return results


def write_report(results: list[GateResult], path: Path, run_id: str) -> pd.DataFrame:
    df = pd.DataFrame([{
        "run_id": run_id,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "gate": r.gate, "description": DESCRIPTIONS[r.gate], "status": r.status,
        "failures": r.failures, "detail": r.detail,
    } for r in results])
    df.to_csv(path, index=False)
    return df
