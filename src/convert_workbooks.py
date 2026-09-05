"""Extract the `Tutti` sheet of Fantacalcio Excel workbooks into CSV files.

Run after adding a new season's player-list or statistics workbook so
`ranking.py` (which reads CSV only) has a matching input file:

    python src/convert_workbooks.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


PLAYER_LIST_COLUMNS = ["Id", "R", "Nome", "Squadra", "Qt.A", "Qt.I", "Diff.", "FVM"]
STATS_COLUMNS = [
    "Id", "R", "Nome", "Squadra", "Pv", "Mv", "Fm", "Gf", "Gs",
    "Rp", "Rc", "R+", "R-", "Ass", "Amm", "Esp", "Au",
]


def convert_directory(directory: Path, columns: list[str]) -> list[Path]:
    written = []
    for xlsx_path in sorted(directory.glob("*.xlsx")):
        if xlsx_path.name.startswith("~$"):
            continue
        data = pd.read_excel(xlsx_path, sheet_name="Tutti", header=1)
        csv_path = xlsx_path.with_suffix(".csv")
        data.loc[:, columns].to_csv(csv_path, index=False, encoding="utf-8")
        written.append(csv_path)
    return written


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    for sub, columns in (
        ("data/player_lists", PLAYER_LIST_COLUMNS),
        ("data/stats", STATS_COLUMNS),
    ):
        for path in convert_directory(root / sub, columns):
            print(f"Creato: {path}")


if __name__ == "__main__":
    main()
