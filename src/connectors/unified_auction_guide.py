"""Connect normalized unified-guide records to the official player list."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import sys
import tempfile
import unicodedata

import pandas as pd


SRC = Path(__file__).resolve().parents[1]
ROOT = SRC.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ranking import artifact_directory, season_start  # noqa: E402


RECORD_COLUMNS = (
    "nome_guida",
    "squadra_guida",
    "fascia",
    "funzione",
    "note",
    "status_rischi",
    "rigori_piazzati",
    "gerarchia_pacchetto",
    "fonti",
    "confidenza",
    "da_verificare",
)
OUTPUT_COLUMNS = (
    "id",
    "nome_guida",
    "nome_listone",
    "ruolo",
    "squadra",
    "squadra_guida",
    "fascia",
    "funzione",
    "note",
    "infortuni",
    "status_rischi",
    "rigori_piazzati",
    "gerarchia_pacchetto",
    "fonti",
    "confidenza",
    "da_verificare",
    "match_status",
)
REQUIRED_VALUES = (
    "nome_guida",
    "squadra_guida",
    "fascia",
    "funzione",
    "note",
    "fonti",
    "confidenza",
)
CANONICAL_TIERS = {
    "Super Top",
    "Top",
    "Semitop",
    "Fascia alta",
    "Fascia media",
    "Low cost",
    "Scommessa",
    "Da monitorare",
}
CANONICAL_FUNCTIONS = {
    "P": {
        "Titolare sicuro",
        "Titolare con riserva",
        "Secondo da pacchetto",
        "Alternanza",
    },
    "D": {
        "Premium bonus",
        "Esterno da bonus",
        "Centrale da modificatore",
        "Titolare affidabile",
        "Rotazione",
        "Scommessa",
    },
    "C": {
        "Premium bonus",
        "Titolare offensivo",
        "Qualità-prezzo",
        "Da voto",
        "Rotazione",
        "Scommessa",
    },
    "A": {
        "Prima scelta",
        "Titolare",
        "Seconda punta / partner",
        "Rotazione offensiva",
        "Ultimo slot",
        "Scommessa",
    },
}
CONFIDENCE_VALUES = {"Alta", "Media", "Bassa"}
ROLE_ORDER = {"P": 0, "D": 1, "C": 2, "A": 3}


class AuctionGuideConnectorError(ValueError):
    """A guide or player-list problem that prevents safe CSV publication."""


def _error(path: Path, season: str, cause: str) -> AuctionGuideConnectorError:
    return AuctionGuideConnectorError(f"Stagione {season}, file {path}: {cause}")


def _comparison_key(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]", "", without_accents.lower())


def _split_markdown_row(line: str) -> list[str]:
    """Split one Markdown table row while preserving escaped field pipes."""
    content = line.strip()
    if not content.startswith("|") or not content.endswith("|"):
        return []
    cells = re.split(r"(?<!\\)\|", content[1:-1])
    return [cell.strip().replace(r"\|", "|") for cell in cells]


def _normalized_section(markdown: str, path: Path, season: str) -> str:
    match = re.search(
        r"^## 9\. Schede giocatore normalizzate\s*$"
        r"(.*?)(?=^## \d+\.|\Z)",
        markdown,
        flags=re.MULTILINE | re.DOTALL,
    )
    if match is None:
        raise _error(path, season, "sezione 9 normalizzata mancante")
    return match.group(1)


def parse_normalized_records(
    markdown: str,
    path: Path,
    season: str,
) -> pd.DataFrame:
    """Return the standardized records from every section-9 Markdown table."""
    section = _normalized_section(markdown, path, season)
    rows: list[dict[str, str]] = []
    in_records_table = False

    for line_number, line in enumerate(section.splitlines(), start=1):
        cells = _split_markdown_row(line)
        if tuple(cells) == RECORD_COLUMNS:
            in_records_table = True
            continue
        if not cells:
            in_records_table = False
            continue
        if not in_records_table or all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        if len(cells) != len(RECORD_COLUMNS):
            raise _error(
                path,
                season,
                f"riga {line_number} della sezione 9 con {len(cells)} campi; "
                f"attesi {len(RECORD_COLUMNS)}",
            )
        rows.append(dict(zip(RECORD_COLUMNS, cells)))

    if not rows:
        raise _error(path, season, "nessuna scheda normalizzata trovata")

    records = pd.DataFrame(rows, columns=RECORD_COLUMNS)
    for column in REQUIRED_VALUES:
        missing = records.index[records[column].str.strip().eq("")].tolist()
        if missing:
            raise _error(
                path,
                season,
                f"campo obbligatorio {column} vuoto nella scheda {missing[0] + 1}",
            )

    duplicate = records.duplicated(["nome_guida", "squadra_guida"], keep=False)
    if duplicate.any():
        values = records.loc[duplicate, ["nome_guida", "squadra_guida"]].iloc[0]
        raise _error(
            path,
            season,
            "scheda duplicata per "
            f"{values['nome_guida']} ({values['squadra_guida']})",
        )

    invalid_tiers = sorted(set(records["fascia"]) - CANONICAL_TIERS)
    if invalid_tiers:
        raise _error(
            path,
            season,
            f"fascia non canonica: {', '.join(invalid_tiers)}",
        )
    invalid_confidence = sorted(set(records["confidenza"]) - CONFIDENCE_VALUES)
    if invalid_confidence:
        raise _error(
            path,
            season,
            f"confidenza non valida: {', '.join(invalid_confidence)}",
        )
    return records


def _read_player_list(path: Path, season: str) -> pd.DataFrame:
    try:
        players = pd.read_csv(path, dtype={"Id": "Int64"})
    except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise _error(path, season, f"listone non leggibile: {exc}") from exc
    required = {"Id", "R", "Nome", "Squadra"}
    missing = sorted(required - set(players.columns))
    if missing:
        raise _error(path, season, f"colonne mancanti: {', '.join(missing)}")
    players = players.loc[:, ["Id", "R", "Nome", "Squadra"]].copy()
    if players["Id"].isna().any() or players["Id"].duplicated().any():
        raise _error(path, season, "Id nullo o duplicato nel listone")
    invalid_roles = sorted(set(players["R"].dropna()) - set(CANONICAL_FUNCTIONS))
    if invalid_roles:
        raise _error(
            path,
            season,
            f"ruolo Classic non valido: {', '.join(invalid_roles)}",
        )
    players["Nome"] = players["Nome"].astype(str).str.strip()
    players["Squadra"] = players["Squadra"].astype(str).str.strip()
    players["_name_key"] = players["Nome"].map(_comparison_key)
    return players


def _resolve_player(
    record: pd.Series,
    players: pd.DataFrame,
) -> tuple[pd.Series | None, str]:
    name_key = _comparison_key(record["nome_guida"])
    same_name = players[players["_name_key"] == name_key]
    same_team = same_name[same_name["Squadra"] == record["squadra_guida"]]
    if len(same_team) == 1:
        return same_team.iloc[0], "matched"
    if len(same_name) == 1:
        return same_name.iloc[0], "matched_team_mismatch"
    return None, "unmatched"


def _validate_functions(
    records: pd.DataFrame,
    resolved: list[tuple[pd.Series | None, str]],
    path: Path,
    season: str,
) -> None:
    all_functions = set().union(*CANONICAL_FUNCTIONS.values())
    for record, resolution in zip(records.itertuples(index=False), resolved):
        values = [value.strip() for value in record.funzione.split("|")]
        invalid = [value for value in values if value not in all_functions]
        if invalid:
            raise _error(
                path,
                season,
                f"funzione non canonica per {record.nome_guida}: {', '.join(invalid)}",
            )
        official, _ = resolution
        if official is None:
            continue
        role_functions = CANONICAL_FUNCTIONS[official["R"]]
        wrong_role = [value for value in values if value not in role_functions]
        if wrong_role:
            raise _error(
                path,
                season,
                f"funzione non valida per ruolo {official['R']} di "
                f"{record.nome_guida}: {', '.join(wrong_role)}",
            )


def extract_players(
    season: str,
    root: Path = ROOT,
    guide_path: Path | None = None,
) -> pd.DataFrame:
    """Connect one season's normalized guide records to official player IDs."""
    season_start(season)
    artifact = artifact_directory(root, season)
    guide_path = guide_path or artifact / "guida_unificata_asta.md"
    player_list_path = (
        root
        / "data"
        / "player_lists"
        / "fantacalcio"
        / f"Quotazioni_Fantacalcio_Stagione_{season}.csv"
    )
    try:
        markdown = guide_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise _error(guide_path, season, f"guida non leggibile: {exc}") from exc

    records = parse_normalized_records(markdown, guide_path, season)
    players = _read_player_list(player_list_path, season)
    resolved = [_resolve_player(record, players) for _, record in records.iterrows()]
    _validate_functions(records, resolved, guide_path, season)

    rows = []
    for (_, record), (official, status) in zip(records.iterrows(), resolved):
        rows.append(
            {
                "id": pd.NA if official is None else official["Id"],
                "nome_guida": record["nome_guida"],
                "nome_listone": "" if official is None else official["Nome"],
                "ruolo": "" if official is None else official["R"],
                "squadra": "" if official is None else official["Squadra"],
                "squadra_guida": record["squadra_guida"],
                "fascia": record["fascia"],
                "funzione": record["funzione"],
                "note": record["note"],
                "infortuni": "",
                "status_rischi": record["status_rischi"],
                "rigori_piazzati": record["rigori_piazzati"],
                "gerarchia_pacchetto": record["gerarchia_pacchetto"],
                "fonti": record["fonti"],
                "confidenza": record["confidenza"],
                "da_verificare": record["da_verificare"],
                "match_status": status,
            }
        )

    result = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    result["id"] = result["id"].astype("Int64")
    role_order = result["ruolo"].map(ROLE_ORDER).fillna(len(ROLE_ORDER))
    return (
        result.assign(_role_order=role_order)
        .sort_values(
            ["_role_order", "squadra", "nome_guida"],
            kind="stable",
            na_position="last",
        )
        .drop(columns="_role_order")
        .reset_index(drop=True)
    )


def write_csv(frame: pd.DataFrame, output_path: Path) -> None:
    """Atomically publish a connected guide CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.stem}-",
        suffix=output_path.suffix,
        dir=output_path.parent,
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        frame.to_csv(temporary, index=False, encoding="utf-8-sig")
        os.replace(temporary, output_path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--season",
        required=True,
        help="Stagione nel formato YYYY_YY, per esempio 2026_27",
    )
    parser.add_argument("--guide", type=Path, help="Guida Markdown da leggere")
    parser.add_argument("--output", type=Path, help="CSV di destinazione")
    args = parser.parse_args()
    artifact = artifact_directory(ROOT, args.season)
    output_path = args.output or artifact / "giocatori_guida_unificata_asta.csv"
    try:
        frame = extract_players(args.season, guide_path=args.guide)
        write_csv(frame, output_path)
    except AuctionGuideConnectorError as exc:
        parser.error(str(exc))
    statuses = frame["match_status"].value_counts().to_dict()
    print(f"Scritti {len(frame)} giocatori in {output_path}")
    print(f"Esiti identità: {statuses}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
