import sys
from pathlib import Path
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ranking import artifact_directory, effective_appearances, predict, rank_players, season_name, season_start  # noqa: E402


class RankingCalculationTests(unittest.TestCase):
    def test_weights_follow_the_most_recent_season_and_missing_year_is_excluded(self):
        stats = {
            "2021_22": pd.DataFrame({"Id": [1], "Pv": [10.0], "Fm": [6.0]}),
            "2022_23": pd.DataFrame({"Id": [], "Pv": [], "Fm": []}),
            "2023_24": pd.DataFrame({"Id": [1], "Pv": [20.0], "Fm": [7.0]}),
        }
        result = predict([1], list(stats), stats, (3, 2, 1))
        # The middle season is absent, so only weights 1 and 3 are denominators.
        self.assertEqual((17.5, 6.86, 17.5, 120.05), result[1])

    def test_zero_appearances_stays_in_presence_average_but_not_fantamedia_weight(self):
        stats = {
            "2021_22": pd.DataFrame({"Id": [1], "Pv": [0.0], "Fm": [float("nan")]}),
            "2022_23": pd.DataFrame({"Id": [1], "Pv": [10.0], "Fm": [6.0]}),
        }
        self.assertEqual((6.67, 6.0, 6.67, 40.02), predict([1], list(stats), stats, (2, 1))[1])

    def test_effective_appearances_saturate_above_30(self):
        self.assertEqual(16.0, effective_appearances(16.0))
        self.assertEqual(28.0, effective_appearances(28.0))
        self.assertEqual(30.0, effective_appearances(30.0))
        self.assertEqual(31.25, effective_appearances(35.0))
        self.assertEqual(32.0, effective_appearances(38.0))

    def test_effective_appearances_are_used_for_expected_points(self):
        stats = {
            "2023_24": pd.DataFrame({"Id": [6434], "Pv": [21.0], "Fm": [6.29]}),
            "2024_25": pd.DataFrame({"Id": [6434, 6646], "Pv": [34.0, 35.0], "Fm": [7.01, 6.76]}),
            "2025_26": pd.DataFrame({"Id": [6434, 6646], "Pv": [35.0, 32.0], "Fm": [7.30, 6.64]}),
        }
        forecasts = predict([6434, 6646], list(stats), stats, (10, 5, 3))
        self.assertEqual((32.39, 7.11, 30.6, 217.57), forecasts[6434])
        self.assertEqual((33.0, 6.68, 30.75, 205.41), forecasts[6646])

    def test_dense_rank_resets_by_role_and_keeps_players_without_history(self):
        players = pd.DataFrame({
            "Id": [1, 2, 3, 4], "R": ["P", "P", "P", "D"],
            "Nome": ["Zeta", "Alfa", "Nullo", "Difensore"], "Squadra": ["x"] * 4,
        })
        forecasts = {1: (1.0, 10.0, 1.0, 10.0), 2: (1.0, 10.0, 1.0, 10.0), 3: None, 4: (1.0, 9.0, 1.0, 9.0)}
        ranked = rank_players(players, forecasts, {"P": "VALIDATO", "D": "NON_VALIDATO", "C": "x", "A": "x"})
        self.assertEqual([2, 1, 3, 4], ranked["Id"].tolist())
        self.assertEqual([1, 1, pd.NA, 1], ranked["Rank"].tolist())
        self.assertEqual("SENZA_STORICO", ranked.iloc[2]["Validazione"])

    def test_future_season_is_derived_without_hard_coding(self):
        self.assertEqual(2027, season_start("2027_28"))
        self.assertEqual("2027_28", season_name(2027))

    def test_artifacts_are_scoped_by_hyphenated_season_directory(self):
        self.assertEqual(Path("output/2027-28"), artifact_directory(Path("."), "2027_28"))
        with self.assertRaisesRegex(ValueError, "Stagione non valida"):
            artifact_directory(Path("."), "2027-28")


if __name__ == "__main__":
    unittest.main()
