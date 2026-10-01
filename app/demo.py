DEMO_ROWS = [
    {
        "id": "demo1", "provider": "PrizePicks", "provider_key": "prizepicks", "sport": "NFL", "sport_key": "americanfootball_nfl",
        "player": "Demo Quarterback", "market": "player_pass_yds", "market_label": "Passing Yards", "line": 244.5, "projection": 262.4,
        "edge": 17.9, "edge_pct": 7.32, "z_edge": 0.325, "over_probability": 62.7, "under_probability": 37.3,
        "recommended_side": "MORE", "recommended_probability": 62.7, "confidence": 84.0, "grade": "A", "source_count": 6,
        "consensus_line": 256.5, "line_spread": 4.0, "sigma": 55.0, "multiplier": None,
        "matchup": "Demo Away @ Demo Home", "away_team": "Demo Away", "home_team": "Demo Home", "commence_time": "2026-10-01T20:15:00Z",
        "notes": ["Demo data — add ODDS_API_KEY for live lines"],
        "books": [
            {"book": "Book A", "book_key": "book_a", "line": 257.5, "over": -110, "under": -110},
            {"book": "Book B", "book_key": "book_b", "line": 255.5, "over": -105, "under": -115},
        ],
        "method": "de-vigged sportsbook consensus → implied distribution",
    },
    {
        "id": "demo2", "provider": "Underdog", "provider_key": "underdog", "sport": "NBA", "sport_key": "basketball_nba",
        "player": "Demo Guard", "market": "player_points", "market_label": "Points", "line": 25.5, "projection": 22.8,
        "edge": -2.7, "edge_pct": -10.59, "z_edge": -0.386, "over_probability": 35.0, "under_probability": 65.0,
        "recommended_side": "LESS", "recommended_probability": 65.0, "confidence": 87.0, "grade": "A+", "source_count": 7,
        "consensus_line": 23.5, "line_spread": 2.0, "sigma": 7.0, "multiplier": None,
        "matchup": "Demo West @ Demo East", "away_team": "Demo West", "home_team": "Demo East", "commence_time": "2026-10-01T23:00:00Z",
        "notes": ["Demo data — add ODDS_API_KEY for live lines"], "books": [],
        "method": "de-vigged sportsbook consensus → implied distribution",
    },
    {
        "id": "demo3", "provider": "PrizePicks", "provider_key": "prizepicks", "sport": "MLB", "sport_key": "baseball_mlb",
        "player": "Demo Starter", "market": "pitcher_strikeouts", "market_label": "Pitcher Strikeouts", "line": 5.5, "projection": 6.42,
        "edge": 0.92, "edge_pct": 16.73, "z_edge": 0.418, "over_probability": 66.2, "under_probability": 33.8,
        "recommended_side": "MORE", "recommended_probability": 66.2, "confidence": 82.0, "grade": "A+", "source_count": 5,
        "consensus_line": 6.0, "line_spread": 1.0, "sigma": 2.2, "multiplier": None,
        "matchup": "Demo Club @ Demo Club 2", "away_team": "Demo Club", "home_team": "Demo Club 2", "commence_time": "2026-10-01T22:40:00Z",
        "notes": ["Demo data — add ODDS_API_KEY for live lines"], "books": [],
        "method": "de-vigged sportsbook consensus → implied distribution",
    },
]

DEMO_SPORTS = [
    {"key": "americanfootball_nfl", "group": "American Football", "title": "NFL", "active": True},
    {"key": "americanfootball_ncaaf", "group": "American Football", "title": "NCAAF", "active": True},
    {"key": "basketball_nba", "group": "Basketball", "title": "NBA", "active": True},
    {"key": "basketball_wnba", "group": "Basketball", "title": "WNBA", "active": True},
    {"key": "baseball_mlb", "group": "Baseball", "title": "MLB", "active": True},
    {"key": "icehockey_nhl", "group": "Ice Hockey", "title": "NHL", "active": True},
    {"key": "soccer_usa_mls", "group": "Soccer", "title": "MLS", "active": True},
    {"key": "mma_mixed_martial_arts", "group": "Mixed Martial Arts", "title": "MMA", "active": True},
]
