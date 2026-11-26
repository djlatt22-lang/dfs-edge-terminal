import asyncio
from app.services.odds_api import OddsApiClient


def book(key, line, over=-110, under=-110):
    return {
        "key": key, "title": key, "last_update": "2026-11-26T10:00:00Z",
        "markets": [{
            "key": "player_points",
            "outcomes": [
                {"name": "Over", "description": "Sample Player", "point": line, "price": over},
                {"name": "Under", "description": "Sample Player", "point": line, "price": under},
            ],
        }],
    }


def test_market_consensus_is_not_advertised_as_verified_grade():
    client = OddsApiClient(api_key="fake-not-used")
    event = {
        "id": "test-event", "sport_key": "basketball_ncaab",
        "sport_title": "NCAAB", "away_team": "A", "home_team": "B",
        "commence_time": "2026-11-27T20:00:00Z",
        "bookmakers": [book("prizepicks", 14.5),
                       book("fanduel", 17.5),
                       book("draftkings", 17.5),
                       book("caesars", 17.5)],
    }
    rows, thin, unmodeled = client._normalize_event(event)
    asyncio.run(client.close())
    assert rows and thin == 0 and unmodeled == 0
    row = rows[0]
    assert row["grade"] == "RESEARCH"
    assert row["calibration_status"] == "NOT_VALIDATED"
    assert row["heuristic_grade"] in {"A+", "A", "B+", "B", "C"}
    assert row["source_count"] == 3
    assert row["line_observed_at"] is None
    assert row["provider_book_last_update"] == "2026-11-26T10:00:00Z"
