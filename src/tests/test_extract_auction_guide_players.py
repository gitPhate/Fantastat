"""Regression tests for the auction-guide player extractor."""

from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extract_auction_guide_players import ROOT, extract  # noqa: E402


class AuctionGuideExtractionTests(unittest.TestCase):
    def test_defender_fascia_and_set_piece_data_are_player_specific(self) -> None:
        players = extract("2026_27", guide_path=ROOT / "output" / "guida_unificata_asta_2026_27.md")
        pavlovic = players.loc[
            (players["nome_guida"] == "Pavlovic")
            & (players["squadra_guida"] == "Milan")
        ].iloc[0]
        orsolini = players.loc[
            (players["nome_guida"] == "Orsolini")
            & (players["squadra_guida"] == "Bologna")
        ].iloc[0]

        self.assertEqual(pavlovic["fascia"], "Top")
        self.assertEqual(orsolini["rigori_piazzati"], "Rigorista indicato; punizioni/corner indicati.")

        dybala = players.loc[
            (players["nome_guida"] == "Dybala")
            & (players["squadra_guida"] == "Roma")
        ].iloc[0]
        self.assertEqual(dybala["status_rischi"], "Storico fisico da prezzare.")

    def test_confirmed_guide_name_and_team_corrections_resolve(self) -> None:
        players = extract("2026_27", guide_path=ROOT / "output" / "guida_unificata_asta_2026_27.md")
        self.assertFalse((players["match_status"] != "matched").any())

        akor = players.loc[
            (players["nome_guida"] == "Akor")
            & (players["squadra_guida"] == "Venezia")
        ].iloc[0]
        self.assertEqual(akor["nome_listone"], "Adams A.")
        self.assertEqual(akor["squadra"], "Venezia")


if __name__ == "__main__":
    unittest.main()
