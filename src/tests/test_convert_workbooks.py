from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from convert_workbooks import ConversionError, convert_online_directory, merge_player_lists, require_online_workbooks  # noqa: E402


class PlayerListConversionTests(unittest.TestCase):
    def test_new_official_workbook_requires_its_online_counterpart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            official = root / "fantacalcio"
            online = root / "fantacalcio-online"
            official.mkdir()
            online.mkdir()
            (official / "Quotazioni_Fantacalcio_Stagione_2027_28.xlsx").touch()

            with self.assertRaisesRegex(ConversionError, "obbligatorio"):
                require_online_workbooks(official, online)

    def test_online_extractor_selects_and_renames_ui_evidence_columns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            online = Path(directory)
            workbook = online / "Quotazioni_Fantacalcio_Stagione_2027_28.xlsx"
            data = pd.DataFrame({
                "Nome": ["ROSSI Mario"], "Ruolo Fantacalcio.it": ["C"],
                "Squadra": ["Roma"], "IS %": [83], "ETA'": [24], "RAT": [70],
            })
            with pd.ExcelWriter(workbook) as writer:
                pd.DataFrame([[None] * len(data.columns)]).to_excel(writer, header=False, index=False)
                data.to_excel(writer, startrow=1, index=False)

            [csv_path] = convert_online_directory(online)
            self.assertEqual(
                ["NomeOnline", "R", "SquadraOnline", "starting_index", "age"],
                pd.read_csv(csv_path).columns.tolist(),
            )

    def test_merge_preserves_official_columns_and_adds_online_evidence_by_id_link(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            official = root / "data" / "player_lists" / "fantacalcio"
            online = root / "data" / "player_lists" / "fantacalcio-online"
            official.mkdir(parents=True)
            online.mkdir(parents=True)
            filename = "Quotazioni_Fantacalcio_Stagione_2027_28.csv"
            pd.DataFrame({"Id": [7], "R": ["C"], "Nome": ["Rossi"], "Squadra": ["Roma"], "Qt.A": [10], "Qt.I": [8], "Diff.": [2], "FVM": [20], "Qt.A M": [12]}).to_csv(official / filename, index=False)
            pd.DataFrame({"NomeOnline": ["ROSSI Mario"], "R": ["C"], "SquadraOnline": ["Roma"], "starting_index": [83], "age": [24]}).to_csv(online / filename, index=False)
            pd.DataFrame({"Id": [7], "NomeOnline": ["ROSSI Mario"], "SquadraOnline": ["Roma"]}).to_csv(online / "Collegamenti_Fantacalcio_Online_Stagione_2027_28.csv", index=False)

            [final_path] = merge_player_lists(root)
            final = pd.read_csv(final_path)
            self.assertEqual(["Id", "R", "Nome", "Squadra", "Qt.A", "Qt.I", "Diff.", "FVM", "Qt.A M", "starting_index", "age"], final.columns.tolist())
            self.assertEqual((83, 24), tuple(final.loc[0, ["starting_index", "age"]]))

    def test_merge_rejects_links_to_an_unknown_official_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            official = root / "data" / "player_lists" / "fantacalcio"
            online = root / "data" / "player_lists" / "fantacalcio-online"
            official.mkdir(parents=True)
            online.mkdir(parents=True)
            filename = "Quotazioni_Fantacalcio_Stagione_2027_28.csv"
            pd.DataFrame({"Id": [7], "R": ["C"], "Nome": ["Rossi"], "Squadra": ["Roma"], "Qt.A": [10], "Qt.I": [8], "Diff.": [2], "FVM": [20]}).to_csv(official / filename, index=False)
            pd.DataFrame({"NomeOnline": ["ROSSI Mario"], "R": ["C"], "SquadraOnline": ["Roma"], "starting_index": [83], "age": [24]}).to_csv(online / filename, index=False)
            pd.DataFrame({"Id": [99], "NomeOnline": ["ROSSI Mario"], "SquadraOnline": ["Roma"]}).to_csv(online / "Collegamenti_Fantacalcio_Online_Stagione_2027_28.csv", index=False)

            with self.assertRaisesRegex(ConversionError, "non presente"):
                merge_player_lists(root)


if __name__ == "__main__":
    unittest.main()
