"""Serve the read-only, offline auction catalogue from a SQLite snapshot."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sqlite3
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from build_snapshot import SCHEMA_VERSION


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIRECTORY = ROOT / "src" / "ui_assets"


class SnapshotUnavailable(ValueError):
    """A snapshot cannot safely be used by the local UI."""


def preferred_season_start(today: date) -> int:
    return today.year if today.month >= 8 else today.year - 1


def choose_season(seasons: list[int], today: date | None = None) -> int:
    if not seasons:
        raise SnapshotUnavailable("Lo snapshot non contiene stagioni selezionabili. Esegui python src/build_snapshot.py dopo avere generato gli artefatti stagionali.")
    preferred = preferred_season_start(today or date.today())
    return preferred if preferred in seasons else max(seasons)


def _connect(database: Path) -> sqlite3.Connection:
    if not database.is_file():
        raise SnapshotUnavailable("Snapshot mancante. Esegui: python src/build_snapshot.py")
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        version = connection.execute("SELECT value FROM metadata WHERE key = 'schema_version'").fetchone()
    except sqlite3.DatabaseError as exc:
        connection.close()
        raise SnapshotUnavailable("Snapshot incompatibile. Rigeneralo con: python src/build_snapshot.py") from exc
    if version is None or version["value"] != str(SCHEMA_VERSION):
        connection.close()
        raise SnapshotUnavailable("Snapshot incompatibile. Rigeneralo con: python src/build_snapshot.py")
    return connection


def _rows(connection: sqlite3.Connection, query: str, values: tuple[object, ...] = ()) -> list[dict[str, object]]:
    return [dict(row) for row in connection.execute(query, values)]


def bootstrap(database: Path) -> dict[str, object]:
    connection = _connect(database)
    try:
        seasons = _rows(connection, "SELECT season_start, label FROM seasons ORDER BY season_start")
    finally:
        connection.close()
    starts = [int(item["season_start"]) for item in seasons]
    return {"seasons": seasons, "selected_season": choose_season(starts)}


def catalogue(database: Path, season_start: int) -> list[dict[str, object]]:
    connection = _connect(database)
    try:
        valid = connection.execute("SELECT 1 FROM seasons WHERE season_start = ?", (season_start,)).fetchone()
        if valid is None:
            raise SnapshotUnavailable("Stagione non presente nello snapshot. Scegli una stagione dal selettore.")
        return _rows(connection, """
            SELECT p.player_id AS id, p.name, p.role, p.club, p.quotation, p.fvm,
                   r.rank, r.predicted_appearances, r.predicted_fantasy_average,
                   r.expected_points, r.validation_status, g.tier, g.injuries
            FROM players p
            LEFT JOIN rankings r ON r.season_start = p.season_start AND r.player_id = p.player_id
            LEFT JOIN guides g ON g.season_start = p.season_start AND g.player_id = p.player_id
            WHERE p.season_start = ?
        """, (season_start,))
    finally:
        connection.close()


def auction_guide(root: Path, season_start: int) -> str:
    """Read the generated guide verbatim for a selected season."""
    season = f"{season_start}-{(season_start + 1) % 100:02d}"
    path = root / "output" / season / "guida_unificata_asta.md"
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise SnapshotUnavailable(f"Guida d'asta non disponibile per la stagione {season}.") from exc


def documentation(root: Path) -> list[dict[str, str]]:
    """Return the files available in the repository documentation directory."""
    directory = root / "docs"
    if not directory.is_dir():
        raise SnapshotUnavailable("La directory docs non è disponibile.")
    return [
        {"path": path.relative_to(directory).as_posix(), "name": path.name}
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    ]


def document(root: Path, relative_path: str) -> dict[str, str]:
    """Read one documentation file, rejecting paths outside docs/."""
    directory = (root / "docs").resolve()
    path = (directory / Path(relative_path)).resolve()
    try:
        path.relative_to(directory)
    except ValueError as exc:
        raise SnapshotUnavailable("Documento non valido.") from exc
    if not path.is_file():
        raise SnapshotUnavailable("Documento non trovato.")
    try:
        return {"name": path.name, "path": path.relative_to(directory).as_posix(), "content": path.read_text(encoding="utf-8")}
    except (OSError, UnicodeError) as exc:
        raise SnapshotUnavailable("Il documento non può essere letto.") from exc


def player_detail(database: Path, season_start: int, player_id: int) -> dict[str, object]:
    connection = _connect(database)
    try:
        current = _rows(connection, """
            SELECT p.player_id AS id, p.name, p.role, p.club, p.quotation, p.fvm,
              r.rank, r.predicted_appearances, r.predicted_fantasy_average, r.expected_points,
              r.validation_status, g.tier, g.function, g.notes, g.injuries, g.risks,
              g.set_pieces, g.hierarchy
            FROM players p LEFT JOIN rankings r ON r.season_start=p.season_start AND r.player_id=p.player_id
            LEFT JOIN guides g ON g.season_start=p.season_start AND g.player_id=p.player_id
            WHERE p.season_start=? AND p.player_id=?
        """, (season_start, player_id))
        if not current:
            raise SnapshotUnavailable("Giocatore non presente nella stagione selezionata.")
        history = _rows(connection, """
            SELECT seasons.season_start, s.appearances, s.fantasy_average,
              r.rank, r.predicted_appearances, r.predicted_fantasy_average, r.expected_points,
              CASE WHEN s.player_id IS NULL THEN 0 ELSE 1 END AS has_statistics,
              CASE WHEN r.player_id IS NULL THEN 0 ELSE 1 END AS has_ranking
            FROM (SELECT season_start FROM statistics WHERE player_id=?
                  UNION SELECT season_start FROM rankings WHERE player_id=?) seasons
            LEFT JOIN statistics s ON s.season_start=seasons.season_start AND s.player_id=?
            LEFT JOIN rankings r ON r.season_start=seasons.season_start AND r.player_id=?
            ORDER BY seasons.season_start
        """, (player_id, player_id, player_id, player_id))
    finally:
        connection.close()
    for row in history:
        start = int(row["season_start"])
        row["label"] = f"{start}/{(start + 1) % 100:02d}"
    return {"player": current[0], "history": history}


class AuctionHandler(SimpleHTTPRequestHandler):
    """Static assets plus intentionally small JSON-only read endpoints."""

    database: Path

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, directory=str(ASSET_DIRECTORY), **kwargs)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        route = urlparse(self.path)
        if not route.path.startswith("/api/"):
            return super().do_GET()
        try:
            query = parse_qs(route.query)
            if route.path == "/api/bootstrap":
                payload = bootstrap(self.database)
            elif route.path == "/api/catalogue":
                payload = catalogue(self.database, int(query["season"][0]))
            elif route.path == "/api/player":
                payload = player_detail(self.database, int(query["season"][0]), int(query["id"][0]))
            elif route.path == "/api/guide":
                guide = auction_guide(ROOT, int(query["season"][0]))
                data = guide.encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/markdown; charset=utf-8")
                self.send_header("Content-Disposition", "inline")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            elif route.path == "/api/docs":
                payload = documentation(ROOT)
            elif route.path == "/api/doc":
                payload = document(ROOT, query["path"][0])
            else:
                self._json({"error": "Endpoint non trovato."}, HTTPStatus.NOT_FOUND)
                return
            self._json(payload)
        except (KeyError, ValueError, SnapshotUnavailable) as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_POST(self) -> None:  # noqa: N802
        self._json({"error": "L'applicazione è in sola lettura."}, HTTPStatus.METHOD_NOT_ALLOWED)


def serve(database: Path, port: int) -> None:
    # Validate before opening the socket so recovery instructions are immediate.
    bootstrap(database)
    AuctionHandler.database = database
    server = ThreadingHTTPServer(("127.0.0.1", port), AuctionHandler)
    print(f"Fantastat offline: http://127.0.0.1:{port}")
    print("Usa Ctrl+C per arrestare il server.")
    server.serve_forever()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / "output" / "fantastat.sqlite3")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        serve(args.database, args.port)
    except SnapshotUnavailable as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
