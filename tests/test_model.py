from app.services.math_utils import american_to_implied, devig_two_way
from app.services.model import BookPair, infer_projection


def test_american_implied():
    assert round(american_to_implied(-110), 4) == 0.5238
    assert round(american_to_implied(100), 4) == 0.5


def test_devig_even_market():
    over, under = devig_two_way(-110, -110)
    assert round(over, 4) == 0.5
    assert round(under, 4) == 0.5


def test_projection_above_dfs_line():
    pairs = [
        BookPair("fanduel", 250.5, -115, -105),
        BookPair("draftkings", 251.5, -110, -110),
        BookPair("caesars", 249.5, -120, 100),
    ]
    p = infer_projection(dfs_line=240.5, market_key="player_pass_yds", sport_group="American Football", pairs=pairs)
    assert p is not None
    assert p.projection > 240.5
    assert p.over_probability_at_dfs_line > 0.5


def test_market_sigma_keeps_basketball_and_esports_distinct():
    from app.services.model import sigma_for_market
    assert sigma_for_market("player_assists", 5.5, "Basketball") == 2.6
    assert sigma_for_market("player_assists", 5.5, "Esports") == 6.0


def test_one_bookmaker_cannot_count_as_multiple_independent_sources():
    pairs = [
        BookPair("fanduel", 250.5, -115, -105),
        BookPair("fanduel", 260.5, -115, -105),
        BookPair("draftkings", 251.5, -110, -110),
    ]
    p = infer_projection(dfs_line=250.5, market_key="player_pass_yds",
                         sport_group="American Football", pairs=pairs)
    assert p is not None
    assert p.source_count == 2
    assert p.consensus_line < 255
