# Decision log

Modelling and cleaning decisions, recorded as they are made (working rule, section 14).
Revisit each one after profiling the downloaded dataset in Phase 1.

| ID | Date | Decision | Rationale | Where |
|----|------|----------|-----------|-------|
| D-01 | 2026-09 | Season = calendar year of the match date, not the `season` text | Kaggle labels such as `2007/08` (for IPL 2008) and `2020/21` (for IPL 2020) are ambiguous; the date is not | `clean.normalise_matches` |
| D-02 | 2026-09 | Over numbers are shifted to 1–20 when the minimum over in the file is 0 | Newer Kaggle versions are 0-based; phases are defined on 1–20 | `clean.normalise_deliveries` |
| D-03 | 2026-09 | Deccan Chargers and Sunrisers Hyderabad are separate franchises | Different owners; SRH was a new franchise in 2013, not a rename | `mappings/teams.csv` |
| D-04 | 2026-09 | Renamed grounds are merged (Feroz Shah Kotla → Arun Jaitley Stadium; Sardar Patel/Motera → Narendra Modi Stadium) | Same physical ground; keeps venue effects comparable across seasons | `mappings/venues.csv` |
| D-05 | 2026-09 | Player names are merged automatically only when their letters-and-digits key is identical (e.g. `M.S. Dhoni` = `MS Dhoni`); fuzzy matches are only proposed for review | In Cricsheet-derived data a wrong merge (two real players combined) is worse than a missed one | `clean.canonical_players`, `logs/player_fuzzy_candidates.csv`, `mappings/players.csv` |
| D-06 | 2026-09 | Qualification threshold 60 balls; results also reported at 120 | Small samples make phases noisy (section 17) | `config.QUALIFY_BALLS`, `drift_sensitivity.csv` |
| D-07 | 2026-09 | SCD2 gap rule: a non-qualifying season neither opens nor closes a spell; a change is dated from the next qualifying season | Section 8.4 | `scd2.apply_season` |
| D-08 | 2026-09 | Open SCD2 rows have `valid_to_season = NULL` and `is_current = 1`; closed rows end at the last qualifying season with the old phase | Standard SCD2 convention; G8 checks both | `scd2.py`, `validate.g8` |
| D-09 | 2026-09 | Super Over innings (innings 3+) stay in `fact_delivery` with `phase_key = NULL` and are excluded from phase aggregates and ML features | They are not part of the 20-over phase structure | `transform.fact_delivery` |
| D-10 | 2026-09 | `is_boundary` = batsman_runs of 4 or 6 | The source has no boundary flag; all-run fours are rare | `clean.normalise_deliveries` |
| D-11 | 2026-09 | Bowler runs conceded exclude byes, leg-byes and penalty runs; bowler wickets exclude run outs, retirements and obstructing the field | Standard cricket scoring | `transform.fact_player_season_phase` |
| D-12 | 2026-09 | Batting dismissals count every delivery on which the player was dismissed (as striker or non-striker), except retired hurt / retired not out | A non-striker run out is still a dismissal | `transform.fact_player_season_phase` |
| D-13 | 2026-09 | Primary-phase ties are broken by more balls, then the earlier phase | Deterministic reruns | `transform.fact_player_season_phase` |
| D-14 | 2026-09 | Team history features use the franchise's previous-season win %, so renames keep their history; new franchises have no value (left missing for the model to impute) | No future information; section 11.3 | `features.build` |
