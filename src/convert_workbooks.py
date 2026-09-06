"""Extract and merge player-list workbooks into ranking-ready CSV files.

Run after adding a season's official Fantacalcio and Fantacalcio Online
workbooks. The final CSV in ``data/player_lists`` keeps the official
Fantacalcio identity and quotations and adds the Online-only player evidence.

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
ONLINE_SOURCE_COLUMNS = ["Nome", "Ruolo Fantacalcio.it", "Squadra", "IS %", "ETA'"]
ONLINE_COLUMNS = ["NomeOnline", "R", "SquadraOnline", "starting_index", "age"]
LINK_COLUMNS = ["Id", "NomeOnline", "SquadraOnline"]


class ConversionError(ValueError):
    """A source workbook or explicit cross-source link is not usable."""


def _season_from_name(path: Path) -> str:
    prefix = "Quotazioni_Fantacalcio_Stagione_"
    if not path.stem.startswith(prefix):
        raise ConversionError(f"Nome file non valido: {path}")
    return path.stem.removeprefix(prefix)


def _read_excel(path: Path, **kwargs: object) -> pd.DataFrame:
    try:
        return pd.read_excel(path, **kwargs)
    except (OSError, ValueError) as exc:
        raise ConversionError(f"Workbook non leggibile {path}: {exc}") from exc


def convert_directory(directory: Path, columns: list[str]) -> list[Path]:
    """Extract official Fantacalcio or statistics workbooks with a Tutti sheet."""
    written = []
    for xlsx_path in sorted(directory.glob("*.xlsx")):
        if xlsx_path.name.startswith("~$"):
            continue
        data = _read_excel(xlsx_path, sheet_name="Tutti", header=1)
        missing = [column for column in columns if column not in data.columns]
        if missing:
            raise ConversionError(f"Colonne mancanti in {xlsx_path}: {', '.join(missing)}")
        csv_path = xlsx_path.with_suffix(".csv")
        data.loc[:, columns].to_csv(csv_path, index=False, encoding="utf-8")
        written.append(csv_path)
    return written


def convert_official_player_lists(directory: Path) -> list[Path]:
    """Extract complete official ``Tutti`` sheets while checking Classic fields."""
    written = []
    for xlsx_path in sorted(directory.glob("*.xlsx")):
        if xlsx_path.name.startswith("~$"):
            continue
        _season_from_name(xlsx_path)
        data = _read_excel(xlsx_path, sheet_name="Tutti", header=1)
        missing = [column for column in PLAYER_LIST_COLUMNS if column not in data.columns]
        if missing:
            raise ConversionError(f"Colonne mancanti in {xlsx_path}: {', '.join(missing)}")
        csv_path = xlsx_path.with_suffix(".csv")
        data.to_csv(csv_path, index=False, encoding="utf-8")
        written.append(csv_path)
    return written


def convert_online_directory(directory: Path) -> list[Path]:
    """Extract the Online fields used to enrich the official player list."""
    written = []
    for xlsx_path in sorted(directory.glob("*.xlsx")):
        if xlsx_path.name.startswith("~$"):
            continue
        _season_from_name(xlsx_path)
        data = _read_excel(xlsx_path, sheet_name=0, header=1)
        missing = [column for column in ONLINE_SOURCE_COLUMNS if column not in data.columns]
        if missing:
            raise ConversionError(f"Colonne mancanti in {xlsx_path}: {', '.join(missing)}")
        csv_path = xlsx_path.with_suffix(".csv")
        data.loc[:, ONLINE_SOURCE_COLUMNS].set_axis(ONLINE_COLUMNS, axis="columns").to_csv(
            csv_path, index=False, encoding="utf-8"
        )
        written.append(csv_path)
    return written


def require_online_workbooks(official_directory: Path, online_directory: Path) -> None:
    """Require an Online workbook for every newly supplied official workbook."""
    for official_path in official_directory.glob("Quotazioni_Fantacalcio_Stagione_*.xlsx"):
        if official_path.name.startswith("~$"):
            continue
        online_path = online_directory / official_path.name
        if not online_path.is_file():
            raise ConversionError(
                f"Workbook Fantacalcio Online obbligatorio mancante per {official_path.name}: {online_path}"
            )


def merge_player_lists(root: Path) -> list[Path]:
    """Build canonical player-list CSVs using explicit Fantacalcio-ID links.

    Online workbooks do not expose Fantacalcio IDs, so a link file is required
    instead of a heuristic name match. Every official player must have exactly
    one link and each linked Online player may appear once. Official players
    without an Online counterpart remain in the final CSV with empty Online
    evidence, preserving the authoritative Classic universe.
    """
    official_directory = root / "data" / "player_lists" / "fantacalcio"
    online_directory = root / "data" / "player_lists" / "fantacalcio-online"
    written = []
    for official_path in sorted(official_directory.glob("Quotazioni_Fantacalcio_Stagione_*.csv")):
        season = _season_from_name(official_path)
        online_path = online_directory / official_path.name
        links_path = online_directory / f"Collegamenti_Fantacalcio_Online_Stagione_{season}.csv"
        if not online_path.is_file() or not links_path.is_file():
            continue
        official = pd.read_csv(official_path)
        online = pd.read_csv(online_path)
        links = pd.read_csv(links_path)
        for path, frame, columns in (
            (official_path, official, PLAYER_LIST_COLUMNS),
            (online_path, online, ONLINE_COLUMNS),
            (links_path, links, LINK_COLUMNS),
        ):
            missing = [column for column in columns if column not in frame.columns]
            if missing:
                raise ConversionError(f"Stagione {season}: colonne mancanti in {path}: {', '.join(missing)}")
        if official["Id"].isna().any() or official["Id"].duplicated().any():
            raise ConversionError(f"Stagione {season}: Id nullo o duplicato in {official_path}")
        if links["Id"].isna().any() or links["Id"].duplicated().any():
            raise ConversionError(f"Stagione {season}: Id nullo o duplicato in {links_path}")
        if not set(links["Id"]).issubset(set(official["Id"])):
            raise ConversionError(f"Stagione {season}: collegamento con Id non presente nel listone ufficiale")
        if links[["NomeOnline", "SquadraOnline"]].duplicated().any():
            raise ConversionError(f"Stagione {season}: giocatore Online collegato piu' volte in {links_path}")
        enrichment = links.merge(online, on=["NomeOnline", "SquadraOnline"], how="left", validate="one_to_one", indicator=True)
        if (enrichment["_merge"] != "both").any():
            raise ConversionError(f"Stagione {season}: collegamento Online non risolto in {links_path}")
        final = official.merge(
            enrichment.loc[:, ["Id", "starting_index", "age"]], on="Id", how="left", validate="one_to_one"
        )
        start, end = season.split("_")
        output_directory = root / "output" / f"{start}-{end}"
        output_directory.mkdir(parents=True, exist_ok=True)
        output_path = output_directory / official_path.name
        final.to_csv(output_path, index=False, encoding="utf-8")
        written.append(output_path)
    return written


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    official_directory = root / "data" / "player_lists" / "fantacalcio"
    online_directory = root / "data" / "player_lists" / "fantacalcio-online"
    require_online_workbooks(official_directory, online_directory)
    for path in convert_official_player_lists(official_directory):
        print(f"Creato: {path}")
    for path in convert_online_directory(online_directory):
        print(f"Creato: {path}")
    for path in convert_directory(root / "data" / "stats", STATS_COLUMNS):
        print(f"Creato: {path}")
    for path in merge_player_lists(root):
        print(f"Creato: {path}")


if __name__ == "__main__":
    main()
