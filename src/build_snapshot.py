"""Build the immutable local SQLite data snapshot used by the auction UI."""

from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
import re
import sqlite3
import tempfile
from typing import Any

import pandas as pd

from ranking import ROLES, RankingError, season_name


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 2
ARTIFACT_SEASON_RE = re.compile(r"^(\d{4})-(\d{2})$")
QUOTE_COLUMNS = ("Id", "R", "Nome", "Squadra", "Qt.A", "FVM")
ONLINE_PLAYER_COLUMNS = ("starting_index", "age")
RANKING_COLUMNS = ("Id", "Rank", "PresenzePreviste", "FantamediaPrevista", "PuntiAttesi", "Validazione")
GUIDE_COLUMNS = ("id", "fascia", "funzione", "note", "infortuni", "status_rischi", "rigori_piazzati", "gerarchia_pacchetto")
INJURY_COLUMNS = ("Id", "Player", "Club", "Role", "ExpectedReturn")
STATS_COLUMNS = ("Id", "R", "Nome", "Squadra", "Pv", "Fm")


class SnapshotError(ValueError):
    """An invalid source that prevents publishing a partially-built snapshot."""


def display_label(start: int) -> str:
    return f"{start}/{(start + 1) % 100:02d}"


def discover_seasons(root: Path) -> list[int]:
    """Discover only valid season directories below generated artifacts."""
    output = root / "output"
    if not output.is_dir():
        return []
    starts = []
    for directory in output.iterdir():
        match = ARTIFACT_SEASON_RE.fullmatch(directory.name)
        if not directory.is_dir() or match is None:
            continue
        start, end = int(match.group(1)), int(match.group(2))
        if end != (start + 1) % 100:
            raise SnapshotError(f"Directory artefatti con stagione non valida: {directory}")
        starts.append(start)
    return sorted(starts)


def _read(path: Path, season: str, columns: tuple[str, ...], kind: str, require_ids: bool = True) -> pd.DataFrame:
    if not path.is_file():
        raise SnapshotError(f"Stagione {season}: file {kind} mancante: {path}")
    try:
        frame = pd.read_csv(path)
    except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise SnapshotError(f"Stagione {season}: file {kind} non leggibile: {path}") from exc
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise SnapshotError(f"Stagione {season}: colonne mancanti in {path}: {', '.join(missing)}")
    frame = frame.loc[:, columns].copy()
    if require_ids and (frame[columns[0]].isna().any() or frame[columns[0]].duplicated().any()):
        raise SnapshotError(f"Stagione {season}: Id nullo o duplicato in {path}")
    return frame


def _optional_read(path: Path, season: str, columns: tuple[str, ...], kind: str) -> pd.DataFrame | None:
    return None if not path.exists() else _read(path, season, columns, kind, require_ids=kind != "guida")


def _player_list_paths(root: Path, season: str) -> tuple[Path, Path]:
    """Return the authoritative list and its optional Online-enriched copy."""
    official = root / "data" / "player_lists" / "fantacalcio" / f"Quotazioni_Fantacalcio_Stagione_{season}.csv"
    start, end = season.split("_")
    enriched = root / "output" / f"{start}-{end}" / f"Quotazioni_Fantacalcio_Stagione_{season}.csv"
    return official, enriched


def _value(value: Any) -> Any:
    return None if value is None or value is pd.NA or (isinstance(value, float) and math.isnan(value)) else value


def _insert_frame(connection: sqlite3.Connection, table: str, columns: tuple[str, ...], frame: pd.DataFrame) -> None:
    values = [tuple(_value(value) for value in row) for row in frame.loc[:, columns].itertuples(index=False, name=None)]
    connection.executemany(
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
        values,
    )


def _merge_injuries(
    guide: pd.DataFrame | None,
    injuries: pd.DataFrame | None,
    player_ids: pd.Series,
    injury_path: Path,
    season: str,
) -> pd.DataFrame | None:
    """Add current injury information to the guide-shaped enrichment frame."""
    if injuries is None:
        return guide

    unknown_ids = injuries.loc[~injuries["Id"].isin(set(player_ids)), "Id"]
    if not unknown_ids.empty:
        ids = ", ".join(str(value) for value in unknown_ids.tolist())
        raise SnapshotError(f"Stagione {season}: Id infortunato non presente nel listone {injury_path}: {ids}")

    injury_values = injuries.set_index("Id")["ExpectedReturn"]
    if guide is None:
        guide = pd.DataFrame(columns=GUIDE_COLUMNS)

    guide = guide.copy()
    guide["infortuni"] = guide["infortuni"].where(
        ~guide["id"].isin(injury_values.index),
        guide["id"].map(injury_values),
    )
    missing = injuries.loc[~injuries["Id"].isin(set(guide["id"])), ["Id", "ExpectedReturn"]].copy()
    if not missing.empty:
        additions = pd.DataFrame({column: pd.NA for column in GUIDE_COLUMNS}, index=missing.index)
        additions["id"] = missing["Id"]
        additions["infortuni"] = missing["ExpectedReturn"]
        guide = pd.concat([guide, additions], ignore_index=True)
    return guide.loc[:, GUIDE_COLUMNS]


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE seasons (season_start INTEGER PRIMARY KEY, label TEXT NOT NULL);
        CREATE TABLE players (
            season_start INTEGER NOT NULL, player_id INTEGER NOT NULL, name TEXT NOT NULL,
            role TEXT NOT NULL, club TEXT NOT NULL, quotation REAL, fvm REAL,
            starting_index REAL, age REAL,
            PRIMARY KEY (season_start, player_id)
        );
        CREATE TABLE rankings (
            season_start INTEGER NOT NULL, player_id INTEGER NOT NULL, rank INTEGER,
            predicted_appearances REAL, predicted_fantasy_average REAL, expected_points REAL,
            validation_status TEXT, PRIMARY KEY (season_start, player_id)
        );
        CREATE TABLE guides (
            season_start INTEGER NOT NULL, player_id INTEGER NOT NULL, tier TEXT,
            function TEXT, notes TEXT, injuries TEXT, risks TEXT, set_pieces TEXT, hierarchy TEXT,
            PRIMARY KEY (season_start, player_id)
        );
        CREATE TABLE statistics (
            season_start INTEGER NOT NULL, player_id INTEGER NOT NULL, name TEXT, role TEXT,
            club TEXT, appearances REAL, fantasy_average REAL,
            PRIMARY KEY (season_start, player_id)
        );
        CREATE INDEX statistics_player_history ON statistics(player_id, season_start);
        CREATE INDEX rankings_player_history ON rankings(player_id, season_start);
        """
    )


def _add_history(connection: sqlite3.Connection, root: Path) -> None:
    for path in sorted((root / "data" / "stats").glob("Statistiche_Fantacalcio_Stagione_*.csv")):
        match = re.search(r"(\d{4})_(\d{2})\.csv$", path.name)
        if match is None:
            continue
        season = match.group(0).removesuffix(".csv")
        start = int(match.group(1))
        frame = _read(path, season, STATS_COLUMNS, "statistiche")
        if (~frame["R"].isin(ROLES)).any():
            raise SnapshotError(f"Stagione {season}: ruolo non valido in {path}")
        frame = frame.rename(columns={"Id": "player_id", "Nome": "name", "R": "role", "Squadra": "club", "Pv": "appearances", "Fm": "fantasy_average"})
        frame.insert(0, "season_start", start)
        _insert_frame(connection, "statistics", ("season_start", "player_id", "name", "role", "club", "appearances", "fantasy_average"), frame)


def build_snapshot(root: Path = ROOT, database: Path | None = None) -> Path:
    """Validate all artifact seasons and atomically publish their SQLite snapshot."""
    database = database or root / "output" / "fantastat.sqlite3"
    seasons = discover_seasons(root)
    database.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=".fantastat-", suffix=".sqlite3", dir=database.parent)
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with sqlite3.connect(temporary) as connection:
            _create_schema(connection)
            connection.execute("INSERT INTO metadata VALUES (?, ?)", ("schema_version", str(SCHEMA_VERSION)))
            for start in seasons:
                season = season_name(start)
                artifact = root / "output" / f"{start}-{(start + 1) % 100:02d}"
                official_path, enriched_path = _player_list_paths(root, season)
                quotes = _read(official_path, season, QUOTE_COLUMNS, "listone")
                source_quotes = pd.read_csv(enriched_path) if enriched_path.is_file() else pd.DataFrame()
                for column in ONLINE_PLAYER_COLUMNS:
                    quotes[column] = source_quotes[column] if column in source_quotes.columns else pd.NA
                if (~quotes["R"].isin(ROLES)).any():
                    raise SnapshotError(f"Stagione {season}: ruolo non valido nel listone")
                connection.execute("INSERT INTO seasons VALUES (?, ?)", (start, display_label(start)))
                players = quotes.rename(columns={"Id": "player_id", "Nome": "name", "R": "role", "Squadra": "club", "Qt.A": "quotation", "FVM": "fvm"})
                players.insert(0, "season_start", start)
                _insert_frame(connection, "players", ("season_start", "player_id", "name", "role", "club", "quotation", "fvm", "starting_index", "age"), players)

                ranking = _optional_read(artifact / "ranking.csv", season, RANKING_COLUMNS, "ranking")
                if ranking is not None:
                    ranking = ranking.rename(columns={"Id": "player_id", "Rank": "rank", "PresenzePreviste": "predicted_appearances", "FantamediaPrevista": "predicted_fantasy_average", "PuntiAttesi": "expected_points", "Validazione": "validation_status"})
                    ranking.insert(0, "season_start", start)
                    _insert_frame(connection, "rankings", ("season_start", "player_id", "rank", "predicted_appearances", "predicted_fantasy_average", "expected_points", "validation_status"), ranking)

                injury_path = artifact / "infortuni_fantacalcio.csv"
                injuries = _optional_read(injury_path, season, INJURY_COLUMNS, "infortuni")
                guide = _optional_read(artifact / "giocatori_guida_unificata_asta.csv", season, GUIDE_COLUMNS, "guida")
                if guide is not None:
                    # Unmatched guide references have no authoritative player ID and
                    # are deliberately omitted rather than guessed by name.
                    guide = guide[guide["id"].notna()].copy()
                    if guide["id"].duplicated().any():
                        raise SnapshotError(f"Stagione {season}: Id duplicato nella guida: {artifact / 'giocatori_guida_unificata_asta.csv'}")
                guide = _merge_injuries(guide, injuries, quotes["Id"], injury_path, season)
                if guide is not None:
                    guide = guide.rename(columns={"id": "player_id", "fascia": "tier", "funzione": "function", "note": "notes", "infortuni": "injuries", "status_rischi": "risks", "rigori_piazzati": "set_pieces", "gerarchia_pacchetto": "hierarchy"})
                    guide.insert(0, "season_start", start)
                    _insert_frame(connection, "guides", ("season_start", "player_id", "tier", "function", "notes", "injuries", "risks", "set_pieces", "hierarchy"), guide)
            _add_history(connection, root)
            connection.execute("PRAGMA user_version = 1")
        connection.close()
        os.replace(temporary, database)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except PermissionError:
            pass
        raise
    return database


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / "output" / "fantastat.sqlite3")
    args = parser.parse_args()
    try:
        database = build_snapshot(database=args.database)
    except SnapshotError as exc:
        parser.error(str(exc))
    print(f"Snapshot creato: {database}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
