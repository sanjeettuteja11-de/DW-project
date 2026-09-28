"""Synthetic IPL-style matches.csv / deliveries.csv for testing the pipeline.

TEST FIXTURE ONLY - the numbers are random, not real cricket data. The files
reproduce the structure and the known quirks of the Kaggle dataset: franchise
renames, spelling variants, "2007/08" season labels, 0-based overs, repeated
ball numbers on extras, a no-result match, a tied match with a Super Over, a
D/L match, venue and player-name variants and missing cities.

Two planted style drifts: "Drift Batter" (DEL) opens in 2008-09 and bats at the
death in 2010-11; "Drift Bowler" (PBKS) bowls the Powerplay in 2008-09 and the
death in 2010-11.
"""
from __future__ import annotations

from itertools import permutations
from pathlib import Path

import numpy as np
import pandas as pd

SEASONS = (2008, 2009, 2010, 2011)
SEASON_LABEL = {2008: "2007/08", 2009: "2009", 2010: "2009/10", 2011: "2011"}
FRANCHISES = ("CSK", "DEL", "PBKS", "RPS")


def team_name(fr: str, year: int, rng) -> str:
    if fr == "CSK":
        return "Chennai Super Kings"
    if fr == "DEL":
        return "Delhi Daredevils" if year <= 2009 else "Delhi Capitals"
    if fr == "PBKS":
        return "Kings XI Punjab" if year <= 2010 else "Punjab Kings"
    return "Rising Pune Supergiants" if rng.random() < 0.3 else "Rising Pune Supergiant"


def venue_of(fr: str, year: int, rng) -> tuple[str, str]:
    if fr == "CSK":
        return "MA Chidambaram Stadium, Chepauk", "Chennai"
    if fr == "DEL":
        return ("Feroz Shah Kotla" if year <= 2009 else "Arun Jaitley Stadium"), "Delhi"
    if fr == "PBKS":
        return "Punjab Cricket Association Stadium, Mohali", ("Chandigarh" if rng.random() < .5 else "Mohali")
    name = "Maharashtra Cricket Association Stadium" + (", Pune" if rng.random() < .5 else "")
    return name, ("" if rng.random() < .5 else "Pune")


def squad(fr: str) -> list[str]:
    players = [f"{fr} Player {i}" for i in range(1, 12)]
    if fr == "CSK":
        players[5] = "MS Dhoni"
    if fr == "DEL":
        players[0] = "Drift Batter"
    if fr == "PBKS":
        players[10] = "Drift Bowler"
    return players


def batting_pairs(fr: str, year: int) -> dict[int, list[str]]:
    """Batters on strike in each phase (1 PP, 2 Middle, 3 Death)."""
    s = squad(fr)
    pairs = {1: [s[0], s[1]], 2: [s[2], s[3]], 3: [s[4], s[5]]}
    if fr == "DEL" and year >= 2010:
        pairs = {1: [s[6], s[1]], 2: [s[2], s[3]], 3: [s[4], s[0]]}
    return pairs


def bowling_plan(fr: str, year: int) -> list[str]:
    """Bowler for overs 1..20; each of five bowlers bowls four overs."""
    b = squad(fr)[6:]
    early = [b[4], b[0], b[4], b[0], b[4], b[0], b[1], b[2], b[3], b[1],
             b[2], b[3], b[1], b[2], b[3], b[4], b[1], b[2], b[3], b[0]]
    if fr == "PBKS" and year >= 2010:
        return [b[0], b[1], b[0], b[1], b[0], b[1], b[2], b[3], b[2], b[3],
                b[2], b[3], b[0], b[2], b[3], b[1], b[4], b[4], b[4], b[4]]
    return early


def display(name: str, year: int) -> str:
    return "M.S. Dhoni" if name == "MS Dhoni" and year == 2009 else name


def innings(rng, match_id, inning, bat, bowl, year, target=None, max_overs=20, script=None):
    rows, total, wkts = [], 0, 0
    pairs, plan = batting_pairs(bat, year), bowling_plan(bowl, year)
    for over in range(max_overs):
        phase = 1 if over < 6 else (2 if over < 15 else 3)
        striker, non = pairs[phase]
        legal, ball = 0, 1
        while legal < 6:
            ev = script.pop(0) if script is not None else None
            if ev is None:
                r = rng.random()
                if r < 0.03:
                    ev = ("wides", 0, 1)
                elif r < 0.04:
                    ev = ("noballs", int(rng.choice([0, 1, 4])), 1)
                elif r < 0.06:
                    ev = ("legbyes", 0, 1)
                else:
                    ev = ("NA", int(rng.choice([0, 0, 1, 1, 1, 2, 4, 6])), 0)
            etype, bruns, extra = ev
            wicket = etype == "NA" and wkts < 9 and rng.random() < 0.035 and script is None
            kind = str(rng.choice(["caught", "bowled", "lbw", "run out"])) if wicket else "NA"
            rows.append({
                "match_id": match_id, "inning": inning, "batting_team": team_name(bat, year, rng),
                "bowling_team": team_name(bowl, year, rng), "over": over, "ball": ball,
                "batter": display(striker, year), "bowler": display(plan[over], year),
                "non_striker": display(non, year), "batsman_runs": bruns, "extra_runs": extra,
                "total_runs": bruns + extra, "extras_type": etype, "is_wicket": int(wicket),
                "player_dismissed": display(striker, year) if wicket else "NA",
                "dismissal_kind": kind,
                "fielder": (f"{bowl} Player 2" + (" (sub)" if rng.random() < .2 else ""))
                if kind in ("caught", "run out") else "NA",
            })
            total += bruns + extra
            wkts += int(wicket)
            if etype not in ("wides", "noballs"):
                legal += 1
                ball += 1
            if bruns % 2 == 1:
                striker, non = non, striker
            if target is not None and total >= target:
                return rows, total, wkts
        striker, non = non, striker
    return rows, total, wkts


def generate(out_dir: Path, seed: int = 7) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    matches, deliveries = [], []
    match_id = 335982
    fixtures = [(y, h, a) for y in SEASONS for h, a in permutations(FRANCHISES, 2)]
    specials = {(2009, "CSK", "DEL"): "no_result", (2010, "DEL", "PBKS"): "tie",
                (2011, "RPS", "CSK"): "dl"}
    for i, (year, home, away) in enumerate(fixtures):
        match_id += 1
        kind = specials.get((year, home, away), "normal")
        venue, city = venue_of(home, year, rng)
        toss_winner = home if rng.random() < .5 else away
        decision = "bat" if rng.random() < .45 else "field"
        first = toss_winner if decision == "bat" else (away if toss_winner == home else home)
        second = away if first == home else home
        date = pd.Timestamp(f"{year}-04-01") + pd.Timedelta(days=i % 12 * 3)
        row = {"id": match_id, "season": SEASON_LABEL[year], "city": city,
               "date": date.strftime("%Y-%m-%d"), "match_type": "League", "venue": venue,
               "team1": team_name(home, year, rng), "team2": team_name(away, year, rng),
               "toss_winner": team_name(toss_winner, year, rng), "toss_decision": decision,
               "super_over": "N", "method": "NA", "umpire1": "Umpire A", "umpire2": "Umpire B"}
        if kind == "no_result":
            row.update(winner="NA", result="no result", result_margin="NA", target_runs="NA",
                       target_overs="NA", player_of_match="NA")
            matches.append(row)
            continue

        r1, t1, w1 = innings(rng, match_id, 1, first, second, year)
        if kind == "tie":
            script = [(r["extras_type"], r["batsman_runs"], r["extra_runs"]) for r in r1]
            r2, t2, w2 = innings(rng, match_id, 2, second, first, year, script=script)
            s3, s3t, _ = innings(rng, match_id, 3, second, first, year, max_overs=1,
                                 script=[("NA", 1, 0)] * 6)
            s4, _, _ = innings(rng, match_id, 4, first, second, year, target=s3t + 1, max_overs=1,
                               script=[("NA", 4, 0)] * 6)
            r2 = r2 + s3 + s4
            winner = first
            row.update(result="tie", result_margin="NA", super_over="Y", target_runs=t1 + 1,
                       target_overs=20)
        elif kind == "dl":
            target = int(t1 * 0.8)
            r2, t2, w2 = innings(rng, match_id, 2, second, first, year, target=target, max_overs=15)
            winner = second if t2 >= target else first
            row.update(result="wickets" if winner == second else "runs",
                       result_margin=(10 - w2) if winner == second else target - 1 - t2,
                       method="D/L", target_runs=target, target_overs=15)
        else:
            r2, t2, w2 = innings(rng, match_id, 2, second, first, year, target=t1 + 1)
            if t2 > t1:
                winner, result, margin = second, "wickets", 10 - w2
            elif t2 < t1:
                winner, result, margin = first, "runs", t1 - t2
            else:  # rare natural tie: award to the first team to keep the fixture simple
                winner, result, margin = first, "runs", 0
            row.update(result=result, result_margin=margin, target_runs=t1 + 1, target_overs=20)
        row["winner"] = team_name(winner, year, rng)
        row["player_of_match"] = display(squad(winner)[5], year)
        matches.append(row)
        deliveries += r1 + r2

    m, d = pd.DataFrame(matches), pd.DataFrame(deliveries)
    col_order = ["id", "season", "city", "date", "match_type", "player_of_match", "venue", "team1",
                 "team2", "toss_winner", "toss_decision", "winner", "result", "result_margin",
                 "target_runs", "target_overs", "super_over", "method", "umpire1", "umpire2"]
    m = m[col_order]
    out_dir.mkdir(parents=True, exist_ok=True)
    m.to_csv(out_dir / "matches.csv", index=False)
    d.to_csv(out_dir / "deliveries.csv", index=False)
    return m, d


if __name__ == "__main__":
    import sys
    m, d = generate(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
    print(len(m), "matches,", len(d), "deliveries")
