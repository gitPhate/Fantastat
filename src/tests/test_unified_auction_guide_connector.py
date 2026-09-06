"""Tests for the reusable unified-auction-guide connector."""

from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors.unified_auction_guide import (  # noqa: E402
    AuctionGuideConnectorError,
    extract_players,
    parse_normalized_records,
)


HEADER = (
    "| nome_guida | squadra_guida | fascia | funzione | note | "
    "status_rischi | rigori_piazzati | gerarchia_pacchetto | fonti | "
    "confidenza | da_verificare |"
)
SEPARATOR = "| " + " | ".join(["---"] * 11) + " |"


def guide(*rows: str) -> str:
    return "\n".join(
        [
            "# Guida",
            "",
            "## 9. Schede giocatore normalizzate",
            "",
            "### Ruolo",
            "",
            HEADER,
            SEPARATOR,
            *rows,
            "",
            "## 10. Controlli",
        ]
    )


class UnifiedAuctionGuideConnectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "data" / "player_lists").mkdir(parents=True)
        (self.root / "output" / "2027-28").mkdir(parents=True)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_player_list(self, rows: list[dict[str, object]]) -> None:
        pd.DataFrame(rows).to_csv(
            self.root
            / "data"
            / "player_lists"
            / "Quotazioni_Fantacalcio_Stagione_2027_28.csv",
            index=False,
        )

    def write_guide(self, markdown: str) -> Path:
        path = self.root / "output" / "2027-28" / "guida_unificata_asta.md"
        path.write_text(markdown, encoding="utf-8")
        return path

    def test_extracts_normalized_records_for_a_new_season(self) -> None:
        self.write_player_list(
            [
                {"Id": 10, "R": "P", "Nome": "Portiere", "Squadra": "Roma"},
                {"Id": 20, "R": "A", "Nome": "Punta", "Squadra": "Milan"},
            ]
        )
        self.write_guide(
            guide(
                "| Portiere | Roma | Top | Titolare sicuro | Nota P. | | | | Fonte | Alta | |",
                "| Punta | Milan | Semitop | Titolare \\| Ultimo slot | Nota A. | Rotazione. | | | Fonte | Media | Minuti. |",
            )
        )

        result = extract_players("2027_28", root=self.root)

        self.assertEqual(result["id"].tolist(), [10, 20])
        self.assertEqual(result["match_status"].tolist(), ["matched", "matched"])
        self.assertEqual(result.iloc[1]["funzione"], "Titolare | Ultimo slot")
        self.assertTrue(result["infortuni"].eq("").all())
        self.assertIn("fonti", result.columns)
        self.assertIn("da_verificare", result.columns)

    def test_marks_a_unique_player_with_a_different_team_for_review(self) -> None:
        self.write_player_list(
            [{"Id": 20, "R": "A", "Nome": "Punta", "Squadra": "Milan"}]
        )
        self.write_guide(
            guide(
                "| Punta | Roma | Top | Prima scelta | Trasferimento da verificare. | | | | Fonte | Bassa | Squadra. |"
            )
        )

        result = extract_players("2027_28", root=self.root)

        self.assertEqual(result.iloc[0]["id"], 20)
        self.assertEqual(result.iloc[0]["squadra"], "Milan")
        self.assertEqual(result.iloc[0]["squadra_guida"], "Roma")
        self.assertEqual(result.iloc[0]["match_status"], "matched_team_mismatch")

    def test_leaves_an_ambiguous_name_unmatched(self) -> None:
        self.write_player_list(
            [
                {"Id": 20, "R": "A", "Nome": "Rossi", "Squadra": "Milan"},
                {"Id": 21, "R": "C", "Nome": "Rossi", "Squadra": "Roma"},
            ]
        )
        self.write_guide(
            guide(
                "| Rossi | Da verificare | Scommessa | Scommessa | Identità incerta. | | | | Fonte | Bassa | Identità. |"
            )
        )

        result = extract_players("2027_28", root=self.root)

        self.assertTrue(pd.isna(result.iloc[0]["id"]))
        self.assertEqual(result.iloc[0]["match_status"], "unmatched")

    def test_rejects_duplicate_logical_records(self) -> None:
        path = Path("guida.md")
        markdown = guide(
            "| Punta | Roma | Top | Prima scelta | Nota. | | | | Fonte | Alta | |",
            "| Punta | Roma | Semitop | Titolare | Altra nota. | | | | Fonte | Media | |",
        )

        with self.assertRaisesRegex(AuctionGuideConnectorError, "scheda duplicata"):
            parse_normalized_records(markdown, path, "2027_28")

    def test_rejects_missing_section_and_malformed_rows(self) -> None:
        path = Path("guida.md")
        with self.assertRaisesRegex(AuctionGuideConnectorError, "sezione 9"):
            parse_normalized_records("# Guida", path, "2027_28")

        malformed = guide("| Punta | Roma | Top | Prima scelta | Troppo corta. |")
        with self.assertRaisesRegex(AuctionGuideConnectorError, "con 5 campi"):
            parse_normalized_records(malformed, path, "2027_28")

    def test_rejects_missing_or_noncanonical_record_values(self) -> None:
        path = Path("guida.md")
        cases = {
            "campo obbligatorio note": (
                "| Punta | Roma | Top | Prima scelta | | | | | Fonte | Alta | |"
            ),
            "fascia non canonica": (
                "| Punta | Roma | Prima fascia | Prima scelta | Nota. | | | | Fonte | Alta | |"
            ),
            "confidenza non valida": (
                "| Punta | Roma | Top | Prima scelta | Nota. | | | | Fonte | Certissima | |"
            ),
        }
        for message, row in cases.items():
            with self.subTest(message=message):
                with self.assertRaisesRegex(AuctionGuideConnectorError, message):
                    parse_normalized_records(guide(row), path, "2027_28")

    def test_rejects_a_function_from_the_wrong_role(self) -> None:
        self.write_player_list(
            [{"Id": 30, "R": "D", "Nome": "Difensore", "Squadra": "Roma"}]
        )
        self.write_guide(
            guide(
                "| Difensore | Roma | Top | Prima scelta | Nota. | | | | Fonte | Alta | |"
            )
        )

        with self.assertRaisesRegex(AuctionGuideConnectorError, "ruolo D"):
            extract_players("2027_28", root=self.root)

    def test_rejects_invalid_player_list_identity_fields(self) -> None:
        self.write_guide(
            guide(
                "| Punta | Roma | Top | Prima scelta | Nota. | | | | Fonte | Alta | |"
            )
        )
        cases = {
            "Id nullo o duplicato": [
                {"Id": 20, "R": "A", "Nome": "Punta", "Squadra": "Roma"},
                {"Id": 20, "R": "A", "Nome": "Altra", "Squadra": "Milan"},
            ],
            "ruolo Classic non valido": [
                {"Id": 20, "R": "W", "Nome": "Punta", "Squadra": "Roma"}
            ],
        }
        for message, rows in cases.items():
            with self.subTest(message=message):
                self.write_player_list(rows)
                with self.assertRaisesRegex(AuctionGuideConnectorError, message):
                    extract_players("2027_28", root=self.root)


if __name__ == "__main__":
    unittest.main()
