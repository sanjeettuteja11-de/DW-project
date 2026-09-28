-- IPL Phase-Performance and Style-Drift Data Warehouse: star schema (deliverable D5).
-- Layer 4 (warehouse) and layer 5 (marts). Rebuilt on every pipeline run.
-- Column comments ("-- ...") are parsed by src/dictionary.py into docs/data_dictionary.csv.

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS dim_player_phase_profile;
DROP TABLE IF EXISTS fact_player_season_phase;
DROP TABLE IF EXISTS fact_match_summary;
DROP TABLE IF EXISTS fact_delivery;
DROP TABLE IF EXISTS dim_match;
DROP TABLE IF EXISTS dim_phase;
DROP TABLE IF EXISTS dim_season;
DROP TABLE IF EXISTS dim_player;
DROP TABLE IF EXISTS dim_venue;
DROP TABLE IF EXISTS dim_team;

-- @table dim_team: Team dimension, SCD Type 2 on team name; one row per franchise name spell.
CREATE TABLE dim_team (
    team_key            INTEGER PRIMARY KEY,  -- Surrogate key
    franchise_id        TEXT NOT NULL,        -- Stable franchise code shared across renames (e.g. DEL)
    canonical_name      TEXT NOT NULL UNIQUE, -- Canonical team name for this spell
    valid_from_season   INTEGER NOT NULL,     -- First season this name was used
    valid_to_season     INTEGER,              -- Last season of this name; NULL while current
    is_current          INTEGER NOT NULL CHECK (is_current IN (0, 1))  -- 1 for the franchise's latest name if it played in the latest season
);

-- @table dim_venue: Canonical venues.
CREATE TABLE dim_venue (
    venue_key           INTEGER PRIMARY KEY,  -- Surrogate key
    canonical_name      TEXT NOT NULL UNIQUE, -- Canonical venue name (variants in map_venue)
    city                TEXT                  -- City, filled from the venue mapping when missing
);

-- @table dim_player: Canonical players.
CREATE TABLE dim_player (
    player_key          INTEGER PRIMARY KEY,  -- Surrogate key
    canonical_name      TEXT NOT NULL UNIQUE  -- Canonical player name (variants in map_player)
);

-- @table dim_season: Seasons.
CREATE TABLE dim_season (
    season_key          INTEGER PRIMARY KEY,  -- Surrogate key
    year                INTEGER NOT NULL UNIQUE  -- Calendar year the season was played
);

-- @table dim_phase: Innings phases (3 rows).
CREATE TABLE dim_phase (
    phase_key           INTEGER PRIMARY KEY,  -- 1 Powerplay, 2 Middle, 3 Death
    phase_name          TEXT NOT NULL UNIQUE, -- Phase name
    start_over          INTEGER NOT NULL,     -- First over of the phase (1-based)
    end_over            INTEGER NOT NULL      -- Last over of the phase (1-based)
);

-- @table dim_match: Match dimension.
CREATE TABLE dim_match (
    match_key           INTEGER PRIMARY KEY,  -- Surrogate key
    source_match_id     INTEGER NOT NULL UNIQUE,  -- Match id in the source files
    season_key          INTEGER NOT NULL REFERENCES dim_season(season_key),  -- Season
    match_date          TEXT NOT NULL,        -- Match date (ISO yyyy-mm-dd)
    venue_key           INTEGER NOT NULL REFERENCES dim_venue(venue_key),  -- Venue
    team1_key           INTEGER NOT NULL REFERENCES dim_team(team_key),  -- Team listed first in the source
    team2_key           INTEGER NOT NULL REFERENCES dim_team(team_key),  -- Team listed second in the source
    toss_winner_key     INTEGER NOT NULL REFERENCES dim_team(team_key),  -- Toss winner
    toss_decision       TEXT NOT NULL CHECK (toss_decision IN ('bat', 'field')),  -- Toss decision
    match_status        TEXT NOT NULL CHECK (match_status IN ('completed', 'tie', 'no_result')),  -- Match status
    result_type         TEXT,                 -- runs, wickets, tie or no_result
    result_margin       INTEGER,              -- Winning margin in runs or wickets
    target_runs         INTEGER,              -- Target set for the chasing side (source value)
    target_overs        REAL,                 -- Overs available to the chasing side (source value)
    is_super_over       INTEGER NOT NULL CHECK (is_super_over IN (0, 1)),  -- 1 if a Super Over was played
    is_dl_applied       INTEGER NOT NULL CHECK (is_dl_applied IN (0, 1)),  -- 1 if Duckworth-Lewis was applied (from raw `method`)
    player_of_match_key INTEGER REFERENCES dim_player(player_key)  -- Player of the match
);

-- @table fact_delivery: Delivery-grain fact; one row per match x inning x delivery_seq.
CREATE TABLE fact_delivery (
    match_key           INTEGER NOT NULL REFERENCES dim_match(match_key),  -- Match
    season_key          INTEGER NOT NULL REFERENCES dim_season(season_key),  -- Season (denormalised from dim_match)
    inning              INTEGER NOT NULL,     -- Innings number; 3+ are Super Over innings
    delivery_seq        INTEGER NOT NULL,     -- Order of the delivery within the innings (source row order)
    batting_team_key    INTEGER NOT NULL REFERENCES dim_team(team_key),  -- Batting team
    bowling_team_key    INTEGER NOT NULL REFERENCES dim_team(team_key),  -- Bowling team
    batter_key          INTEGER NOT NULL REFERENCES dim_player(player_key),  -- Batter on strike
    bowler_key          INTEGER NOT NULL REFERENCES dim_player(player_key),  -- Bowler
    non_striker_key     INTEGER NOT NULL REFERENCES dim_player(player_key),  -- Non-striker
    player_dismissed_key INTEGER REFERENCES dim_player(player_key),  -- Player dismissed; NULL when no wicket
    fielder_key         INTEGER REFERENCES dim_player(player_key),  -- Fielder involved; NULL when none
    phase_key           INTEGER REFERENCES dim_phase(phase_key),  -- Phase; NULL for Super Over innings
    over                INTEGER NOT NULL CHECK (over BETWEEN 1 AND 20),  -- Over number, 1-based
    ball                INTEGER NOT NULL,     -- Ball number within the over as recorded (repeats on extras)
    batsman_runs        INTEGER NOT NULL,     -- Runs off the bat
    extra_runs          INTEGER NOT NULL,     -- Extras on this delivery
    total_runs          INTEGER NOT NULL,     -- batsman_runs + extra_runs
    extras_type         TEXT NOT NULL,        -- wides, noballs, byes, legbyes, penalty or none
    is_wicket           INTEGER NOT NULL CHECK (is_wicket IN (0, 1)),  -- 1 if a wicket fell
    dismissal_kind      TEXT NOT NULL,        -- Dismissal kind or none
    is_super_over_innings INTEGER NOT NULL CHECK (is_super_over_innings IN (0, 1)),  -- 1 for Super Over innings
    is_legal_for_bowler INTEGER NOT NULL CHECK (is_legal_for_bowler IN (0, 1)),  -- 0 for wides and no-balls
    is_faced_by_batter  INTEGER NOT NULL CHECK (is_faced_by_batter IN (0, 1)),  -- 0 for wides
    is_boundary         INTEGER NOT NULL CHECK (is_boundary IN (0, 1)),  -- 1 if batsman_runs is 4 or 6
    is_dot              INTEGER NOT NULL CHECK (is_dot IN (0, 1)),  -- 1 for a legal ball with no runs
    PRIMARY KEY (match_key, inning, delivery_seq)
);

-- @table fact_match_summary: Match-grain aggregate fact; innings 1 = batting first, innings 2 = chasing.
CREATE TABLE fact_match_summary (
    match_key           INTEGER PRIMARY KEY REFERENCES dim_match(match_key),  -- Match
    season_key          INTEGER NOT NULL REFERENCES dim_season(season_key),  -- Season
    venue_key           INTEGER NOT NULL REFERENCES dim_venue(venue_key),  -- Venue
    bat_first_team_key  INTEGER NOT NULL REFERENCES dim_team(team_key),  -- Team batting first
    chase_team_key      INTEGER NOT NULL REFERENCES dim_team(team_key),  -- Team batting second
    toss_winner_key     INTEGER NOT NULL REFERENCES dim_team(team_key),  -- Toss winner
    toss_decision       TEXT NOT NULL,        -- bat or field
    toss_winner_bat_first INTEGER NOT NULL,   -- 1 if the toss winner batted first
    inn1_pp_runs        INTEGER,              -- Innings 1 Powerplay runs
    inn1_pp_wickets     INTEGER,              -- Innings 1 Powerplay wickets
    inn1_pp_legal_balls INTEGER,              -- Innings 1 Powerplay legal balls
    inn1_pp_boundaries  INTEGER,              -- Innings 1 Powerplay boundaries
    inn1_pp_dot_pct     REAL,                 -- Innings 1 Powerplay dot balls / legal balls x 100
    inn1_pp_run_rate    REAL,                 -- Innings 1 Powerplay runs x 6 / legal balls
    inn1_total_runs     INTEGER,              -- Innings 1 total
    inn1_wickets        INTEGER,              -- Innings 1 wickets
    inn1_legal_balls    INTEGER,              -- Innings 1 legal balls
    inn2_pp_runs        INTEGER,              -- Innings 2 Powerplay runs
    inn2_pp_wickets     INTEGER,              -- Innings 2 Powerplay wickets
    inn2_pp_legal_balls INTEGER,              -- Innings 2 Powerplay legal balls
    inn2_pp_boundaries  INTEGER,              -- Innings 2 Powerplay boundaries
    inn2_pp_dot_pct     REAL,                 -- Innings 2 Powerplay dot balls / legal balls x 100
    inn2_pp_run_rate    REAL,                 -- Innings 2 Powerplay runs x 6 / legal balls
    inn2_total_runs     INTEGER,              -- Innings 2 total
    inn2_wickets        INTEGER,              -- Innings 2 wickets
    inn2_legal_balls    INTEGER,              -- Innings 2 legal balls
    winner_key          INTEGER REFERENCES dim_team(team_key),  -- Winner; NULL for no result or undecided tie
    result_type         TEXT,                 -- runs, wickets, tie or no_result
    match_status        TEXT NOT NULL,        -- completed, tie or no_result
    bat_first_won       INTEGER,              -- ML target: 1 if the team batting first won; NULL without a winner
    ml_eligible         INTEGER NOT NULL CHECK (ml_eligible IN (0, 1))  -- 1 if completed, no Super Over, no D/L, both innings present
);

-- @table fact_player_season_phase: Aggregate fact; one row per player x season x role_type x phase (regular innings only).
CREATE TABLE fact_player_season_phase (
    player_key          INTEGER NOT NULL REFERENCES dim_player(player_key),  -- Player
    season_key          INTEGER NOT NULL REFERENCES dim_season(season_key),  -- Season
    role_type           TEXT NOT NULL CHECK (role_type IN ('batting', 'bowling')),  -- Role
    phase_key           INTEGER NOT NULL REFERENCES dim_phase(phase_key),  -- Phase
    balls               INTEGER NOT NULL,     -- Balls faced (batting, excl. wides) or legal balls bowled
    runs                INTEGER NOT NULL,     -- Runs scored (batting) or conceded (bowling; excl. byes/leg-byes)
    wickets             INTEGER NOT NULL,     -- Dismissals (batting) or bowler-credited wickets (bowling)
    boundaries          INTEGER NOT NULL,     -- Fours and sixes hit or conceded
    dots                INTEGER NOT NULL,     -- Dot balls faced or bowled
    strike_rate         REAL,                 -- Batting: runs x 100 / balls
    economy             REAL,                 -- Bowling: runs x 6 / balls
    season_balls        INTEGER NOT NULL,     -- Player's balls in all phases that season for this role
    phase_share         REAL NOT NULL,        -- balls / season_balls
    league_phase_share  REAL NOT NULL,        -- League balls in phase / league balls, same role and season
    phase_index         REAL NOT NULL,        -- phase_share / league_phase_share
    qualifies           INTEGER NOT NULL CHECK (qualifies IN (0, 1)),  -- 1 if season_balls >= qualification threshold
    is_primary_phase    INTEGER NOT NULL CHECK (is_primary_phase IN (0, 1)),  -- 1 for the phase with the highest phase_index (qualifying seasons only)
    PRIMARY KEY (player_key, season_key, role_type, phase_key)
);

-- @table dim_player_phase_profile: SCD Type 2 history of each player's primary phase per role.
CREATE TABLE dim_player_phase_profile (
    profile_key         INTEGER PRIMARY KEY,  -- Surrogate key
    player_key          INTEGER NOT NULL REFERENCES dim_player(player_key),  -- Player
    role_type           TEXT NOT NULL CHECK (role_type IN ('batting', 'bowling')),  -- Role
    primary_phase_key   INTEGER NOT NULL REFERENCES dim_phase(phase_key),  -- Primary phase for this spell
    phase_index_value   REAL NOT NULL,        -- Primary-phase index in the season the spell opened
    valid_from_season   INTEGER NOT NULL,     -- First qualifying season of the spell
    valid_to_season     INTEGER,              -- Last qualifying season with this phase; NULL while current
    last_seen_season    INTEGER NOT NULL,     -- Latest qualifying season covered by the spell
    qualifying_seasons  INTEGER NOT NULL,     -- Number of qualifying seasons in the spell
    is_current          INTEGER NOT NULL CHECK (is_current IN (0, 1)),  -- 1 for the open spell
    threshold_balls     INTEGER NOT NULL      -- Qualification threshold used to build the spell
);

CREATE INDEX ix_fact_delivery_season_phase ON fact_delivery (season_key, phase_key);
CREATE INDEX ix_fact_delivery_batter ON fact_delivery (batter_key);
CREATE INDEX ix_fact_delivery_bowler ON fact_delivery (bowler_key);
CREATE INDEX ix_profile_player ON dim_player_phase_profile (player_key, role_type);
