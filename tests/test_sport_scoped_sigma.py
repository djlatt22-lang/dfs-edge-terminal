"""Regression tests for sport-specific prop standard deviations."""
import unittest

from app.services.model import MARKET_SIGMA, sigma_for_market


class TestSportScopedSigma(unittest.TestCase):
    def test_basketball_assists_not_overwritten_by_esports(self):
        self.assertEqual(MARKET_SIGMA["player_assists"], 2.6)
        self.assertEqual(sigma_for_market("player_assists", 6.5, "Basketball"), 2.6)

    def test_esports_assists_use_separate_prior(self):
        self.assertEqual(sigma_for_market("player_assists", 6.5, "Esports"), 6.0)

    def test_other_sports_keep_generic_market_prior(self):
        self.assertEqual(sigma_for_market("player_assists", 6.5, "Other"), 2.6)

    def test_no_collision_in_other_market(self):
        self.assertEqual(sigma_for_market("player_rebounds", 6.5, "Basketball"), 3.2)

    def test_unknown_market_uses_sport_fallback(self):
        self.assertAlmostEqual(sigma_for_market("made_up_market", 10.0, "Basketball"), 3.0)


if __name__ == "__main__":
    unittest.main()
