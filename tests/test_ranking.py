import sys
from pathlib import Path
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ranking import predict, rank_players, season_name, season_start  # noqa: E402


class RankingCalculationTests(unittest.TestCase):
    def test_weights_follow_the_most_recent_season_and_missing_year_is_excluded(self):
        stats = {
            "2021_22": pd.DataFrame({"Id": [1], "Pv": [10.0], "Fm": [6.0]}),
            "2022_23": pd.DataFrame({"Id": [], "Pv": [], "Fm": []}),
            "2023_24": pd.DataFrame({"Id": [1], "Pv": [20.0], "Fm": [7.0]}),
        }
        result = predict([1], list(stats), stats, (3, 2, 1))
        # The middle season is absent, so only weights 1 and 3 are denominators.
        self.assertEqual((17.5, 6.86, 120.05), result[1])

    def test_zero_appearances_stays_in_presence_average_but_not_fantamedia_weight(self):
        stats = {
            "2021_22": pd.DataFrame({"Id": [1], "Pv": [0.0], "Fm": [float("nan")]}),
            "2022_23": pd.DataFrame({"Id": [1], "Pv": [10.0], "Fm": [6.0]}),
        }
        self.assertEqual((6.67, 6.0, 40.02), predict([1], list(stats), stats, (2, 1))[1])

    def test_dense_rank_resets_by_role_and_keeps_players_without_history(self):
        players = pd.DataFrame({
            "Id": [1, 2, 3, 4], "R": ["P", "P", "P", "D"],
            "Nome": ["Zeta", "Alfa", "Nullo", "Difensore"], "Squadra": ["x"] * 4,
        })
        forecasts = {1: (1.0, 10.0, 10.0), 2: (1.0, 10.0, 10.0), 3: None, 4: (1.0, 9.0, 9.0)}
        ranked = rank_players(players, forecasts, {"P": "VALIDATO", "D": "NON_VALIDATO", "C": "x", "A": "x"})
        self.assertEqual([2, 1, 3, 4], ranked["Id"].tolist())
        self.assertEqual([1, 1, pd.NA, 1], ranked["Rank"].tolist())
        self.assertEqual("SENZA_STORICO", ranked.iloc[2]["Validazione"])

    def test_future_season_is_derived_without_hard_coding(self):
        self.assertEqual(2027, season_start("2027_28"))
        self.assertEqual("2027_28", season_name(2027))


if __name__ == "__main__":
    unittest.main()
