-- Analysis views over the star schema (consumed by notebooks and dashboard exports).

DROP VIEW IF EXISTS v_league_phase_rates;
DROP VIEW IF EXISTS v_team_phase_profile;
DROP VIEW IF EXISTS v_venue_profile;
DROP VIEW IF EXISTS v_player_drift;
DROP VIEW IF EXISTS v_player_phase_profile;
DROP VIEW IF EXISTS v_match_phase;

-- League run rate and wickets by season and phase (regular innings only).
CREATE VIEW v_league_phase_rates AS
SELECT s.year AS season, p.phase_key, p.phase_name,
       SUM(f.total_runs) AS runs,
       SUM(f.is_legal_for_bowler) AS legal_balls,
       ROUND(SUM(f.total_runs) * 6.0 / NULLIF(SUM(f.is_legal_for_bowler), 0), 3) AS run_rate,
       SUM(f.is_wicket) AS wickets,
       ROUND(100.0 * SUM(f.is_boundary) / NULLIF(SUM(f.is_faced_by_batter), 0), 2) AS boundary_pct,
       ROUND(100.0 * SUM(f.is_dot) / NULLIF(SUM(f.is_legal_for_bowler), 0), 2) AS dot_pct
FROM fact_delivery f
JOIN dim_season s ON s.season_key = f.season_key
JOIN dim_phase p ON p.phase_key = f.phase_key
GROUP BY s.year, p.phase_key, p.phase_name;

-- Team x season x phase batting and bowling profile, by franchise so renames stay together.
CREATE VIEW v_team_phase_profile AS
WITH bat AS (
    SELECT t.franchise_id, f.season_key, f.phase_key,
           SUM(f.total_runs) AS runs_scored, SUM(f.is_legal_for_bowler) AS balls_batted,
           SUM(f.is_wicket) AS wickets_lost
    FROM fact_delivery f JOIN dim_team t ON t.team_key = f.batting_team_key
    WHERE f.phase_key IS NOT NULL GROUP BY 1, 2, 3),
bowl AS (
    SELECT t.franchise_id, f.season_key, f.phase_key,
           SUM(f.total_runs) AS runs_conceded, SUM(f.is_legal_for_bowler) AS balls_bowled,
           SUM(f.is_wicket) AS wickets_taken
    FROM fact_delivery f JOIN dim_team t ON t.team_key = f.bowling_team_key
    WHERE f.phase_key IS NOT NULL GROUP BY 1, 2, 3)
SELECT b.franchise_id, s.year AS season, p.phase_name,
       ROUND(b.runs_scored * 6.0 / NULLIF(b.balls_batted, 0), 3) AS batting_run_rate,
       b.wickets_lost,
       ROUND(w.runs_conceded * 6.0 / NULLIF(w.balls_bowled, 0), 3) AS bowling_economy,
       w.wickets_taken
FROM bat b
JOIN bowl w ON w.franchise_id = b.franchise_id AND w.season_key = b.season_key AND w.phase_key = b.phase_key
JOIN dim_season s ON s.season_key = b.season_key
JOIN dim_phase p ON p.phase_key = b.phase_key;

-- Venue first-innings scores and phase run rates.
CREATE VIEW v_venue_profile AS
SELECT v.canonical_name AS venue, v.city,
       COUNT(*) AS matches,
       ROUND(AVG(s.inn1_total_runs), 1) AS avg_first_innings,
       ROUND(AVG(s.inn2_total_runs), 1) AS avg_second_innings,
       ROUND(AVG(s.inn1_pp_run_rate), 3) AS avg_inn1_pp_run_rate,
       ROUND(AVG(s.bat_first_won), 3) AS bat_first_win_rate
FROM fact_match_summary s JOIN dim_venue v ON v.venue_key = s.venue_key
WHERE s.match_status = 'completed' AND s.inn1_total_runs IS NOT NULL
GROUP BY v.canonical_name, v.city;

-- SCD2 spells with names.
CREATE VIEW v_player_phase_profile AS
SELECT pr.profile_key, pl.canonical_name AS player, pr.role_type, ph.phase_name AS primary_phase,
       pr.phase_index_value, pr.valid_from_season, pr.valid_to_season, pr.last_seen_season,
       pr.qualifying_seasons, pr.is_current
FROM dim_player_phase_profile pr
JOIN dim_player pl ON pl.player_key = pr.player_key
JOIN dim_phase ph ON ph.phase_key = pr.primary_phase_key;

-- Transitions between consecutive spells (the drift table).
CREATE VIEW v_player_drift AS
SELECT a.player, a.role_type, a.primary_phase AS from_phase, b.primary_phase AS to_phase,
       a.valid_to_season AS from_season, b.valid_from_season AS to_season
FROM v_player_phase_profile a
JOIN v_player_phase_profile b
  ON b.player = a.player AND b.role_type = a.role_type AND b.valid_from_season > a.valid_to_season
WHERE NOT EXISTS (
    SELECT 1 FROM v_player_phase_profile c
    WHERE c.player = a.player AND c.role_type = a.role_type
      AND c.valid_from_season > a.valid_to_season AND c.valid_from_season < b.valid_from_season);

-- Match x batting franchise x phase totals (regular innings); small enough for dashboard filtering.
CREATE VIEW v_match_phase AS
SELECT m.source_match_id, se.year AS season, v.canonical_name AS venue, t.franchise_id,
       t.canonical_name AS team, f.inning, ph.phase_name, ph.phase_key,
       SUM(f.total_runs) AS runs, SUM(f.is_legal_for_bowler) AS legal_balls, SUM(f.is_wicket) AS wickets,
       SUM(f.is_boundary) AS boundaries, SUM(f.is_dot) AS dots
FROM fact_delivery f
JOIN dim_match m ON m.match_key = f.match_key
JOIN dim_season se ON se.season_key = f.season_key
JOIN dim_venue v ON v.venue_key = m.venue_key
JOIN dim_team t ON t.team_key = f.batting_team_key
JOIN dim_phase ph ON ph.phase_key = f.phase_key
GROUP BY m.source_match_id, se.year, v.canonical_name, t.franchise_id, t.canonical_name, f.inning,
         ph.phase_name, ph.phase_key;
