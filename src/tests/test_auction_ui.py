from datetime import date
from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from auction_ui import auction_guide, catalogue, choose_season, player_detail, preferred_season_start  # noqa: E402
from build_snapshot import build_snapshot, discover_seasons  # noqa: E402


class SnapshotAndUiTests(unittest.TestCase):
    def test_preferred_season_handles_july_and_august(self) -> None:
        self.assertEqual(2025, preferred_season_start(date(2026, 7, 31)))
        self.assertEqual(2026, preferred_season_start(date(2026, 8, 1)))
        self.assertEqual(2025, choose_season([2024, 2025], date(2026, 9, 1)))

    def test_snapshot_keeps_players_without_optional_enrichment_and_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            quotes = root / "data" / "player_lists"
            stats = root / "data" / "stats"
            artifact = root / "output" / "2026-27"
            quotes.mkdir(parents=True)
            stats.mkdir(parents=True)
            artifact.mkdir(parents=True)
            pd.DataFrame({"Id": [1, 2], "R": ["P", "D"], "Nome": ["Rossi", "Bianchi"], "Squadra": ["Roma", "Inter"], "Qt.A": [10, 5], "FVM": [20, 10]}).to_csv(quotes / "Quotazioni_Fantacalcio_Stagione_2026_27.csv", index=False)
            pd.DataFrame({"Id": [1], "Rank": [1], "PresenzePreviste": [30], "FantamediaPrevista": [6.2], "PuntiAttesi": [186], "Validazione": ["VALIDATO"]}).to_csv(artifact / "ranking.csv", index=False)
            pd.DataFrame({"id": [1], "fascia": ["Top"], "funzione": ["Titolare"], "note": ["nota"], "infortuni": [""], "status_rischi": [""], "rigori_piazzati": [""], "gerarchia_pacchetto": [""]}).to_csv(artifact / "giocatori_guida_unificata_asta.csv", index=False)
            pd.DataFrame({"Id": [1], "R": ["P"], "Nome": ["Vecchio Rossi"], "Squadra": ["Milan"], "Pv": [0], "Fm": [None]}).to_csv(stats / "Statistiche_Fantacalcio_Stagione_2025_26.csv", index=False)
            database = build_snapshot(root, root / "output" / "snapshot.sqlite3")
            self.assertEqual([2026], discover_seasons(root))
            players = catalogue(database, 2026)
            self.assertEqual(2, len(players))
            self.assertIsNone(next(player for player in players if player["id"] == 2)["rank"])
            detail = player_detail(database, 2026, 1)
            self.assertEqual("Rossi", detail["player"]["name"])
            self.assertEqual(0.0, detail["history"][0]["appearances"])
            self.assertEqual("2025/26", detail["history"][0]["label"])

    def test_catalogue_includes_injury_information(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            quotes = root / "data" / "player_lists"
            artifact = root / "output" / "2026-27"
            quotes.mkdir(parents=True)
            artifact.mkdir(parents=True)
            pd.DataFrame({"Id": [1], "R": ["A"], "Nome": ["Rossi"], "Squadra": ["Roma"], "Qt.A": [10], "FVM": [20]}).to_csv(quotes / "Quotazioni_Fantacalcio_Stagione_2026_27.csv", index=False)
            pd.DataFrame({"id": [1], "fascia": ["Top"], "funzione": ["Titolare"], "note": ["nota"], "infortuni": ["Caviglia"], "status_rischi": [""], "rigori_piazzati": [""], "gerarchia_pacchetto": [""]}).to_csv(artifact / "giocatori_guida_unificata_asta.csv", index=False)
            database = build_snapshot(root, root / "output" / "snapshot.sqlite3")
            self.assertEqual("Caviglia", catalogue(database, 2026)[0]["injuries"])

    def test_auction_guide_is_read_verbatim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            guide = root / "output" / "2026-27" / "guida_unificata_asta.md"
            guide.parent.mkdir(parents=True)
            contents = "# Guida\n\nTesto con accenti: titolare.\n"
            guide.write_text(contents, encoding="utf-8")
            self.assertEqual(contents, auction_guide(root, 2026))


if __name__ == "__main__":
    unittest.main()
