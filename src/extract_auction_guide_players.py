"""Extract the player categories in the unified auction guide to a CSV.

The guide is the source for every qualitative field.  The current player list is
used solely to attach the official player ID, role, and team.
"""

from __future__ import annotations

import argparse
import re
import shutil
import unicodedata
from collections import defaultdict
from pathlib import Path

import pandas as pd

from ranking import artifact_directory, season_start


ROOT = Path(__file__).resolve().parents[1]


# Guide display names that clearly identify one official-list player, despite a
# different ordering, initial, accent, or abbreviated first name.
OFFICIAL_NAME_ALIASES = {
    ("Josep Martinez", "Inter"): "Martinez Jo.",
    ("Stankovic", "Venezia"): "Stankovic F.",
    ("Molina", "Roma"): "Molina N.",
    ("Ndicka", "Roma"): "N'Dicka",
    ("Yan Couto", "Como"): "Couto",
    ("Chalobah", "Como"): "Chalobah T.",
    ("Miranda", "Bologna"): "Miranda J.",
    ("Jimenez", "Fiorentina"): "Jimenez A.",
    ("Kristensen", "Atalanta"): "Kristensen T.",
    ("Nico Paz", "Como"): "Paz N.",
    ("Ederson", "Atalanta"): "Ederson D.S.",
    ("Conceição", "Juventus"): "Conceicao",
    ("Sucic", "Inter"): "Sucic P.",
    ("Unai Gómez", "Udinese"): "Unai Gomez",
    ("Lautaro Martinez", "Inter"): "Martinez L.",
    ("Gonçalo Ramos", "Milan"): "Ramos G.",
    ("Keinan Davis", "Udinese"): "Davis K.",
    ("Pio Esposito", "Inter"): "Esposito F.P.",
    ("Castro", "Roma"): "Castro S.",
    ("Soulé", "Roma"): "Soulè",
    ("Laurienté", "Sassuolo"): "Laurientè",
    ("El Bilal Touré", "Parma"): "Tourè E.",
    ("Che Adams", "Torino"): "Adams C.",
    ("Valdepeñas", "Como"): "Valdepenas",
    ("Cissé", "Verona"): "Cissè A.",
    ("Pellegrino", "Fiorentina"): "Pellegrino M.",
    ("Akor", "Venezia"): "Adams A.",
}

# The guide snapshot predates these confirmed team corrections.  Keep the guide
# team for traceability, while treating the official-list record as a match.
CONFIRMED_GUIDE_TEAM_CORRECTIONS = {
    ("Valdepeñas", "Como"),
    ("Cissé", "Verona"),
}

GOALKEEPER_PACKAGES = {
    ("Butez", "Como"): "Butez-Sanchez: ballottaggio aperto; valutare come coppia.",
    ("Josep Martinez", "Inter"): "Josep Martinez-Provedel: valutare come coppia.",
    ("Mandas", "Lazio"): "Mandas-Motta: valutare come coppia.",
}

# The defender table groups multiple players in one prose cell.  These are the
# individual fascia values stated in that cell; they must not be copied to every
# player in the group.
DEFENDER_FASCE = {
    "Dimarco": "Super Top", "Wesley": "Top", "Bremer": "Top",
    "Bastoni": "Top", "Pavlovic": "Top", "Solet": "Top",
    "Mancini": "Semitop",
    "Akanji": "Semitop", "Kalulu": "Semitop", "Di Lorenzo": "Semitop",
    "Ndicka": "Sotto ai Semitop", "Molina": "Top", "Zappacosta": "Fascia alta",
    "Spinazzola": "Fascia alta", "Celik": "Fascia alta",
    "Cambiaso": "Jolly 1ª fascia", "Miranda": "Fascia media",
    "Belghali": "Fascia media", "Yan Couto": "Possibile sorpresa",
    "Ostigard": "Top", "Ramon": "Sotto ai Semitop", "Bisseck": "Sotto ai Semitop",
    "Gila": "Semitop", "Rrahmani": "Semitop", "Chalobah": "Possibile sorpresa",
    "Lucumì": "Fascia alta", "Kristensen": "Fascia media",
    "Mina": "Sopra ai low cost", "Tiago Gabriel": "Sopra ai low cost",
    "Idzes": "Non specificata",
    "Koulierakis": "Possibile sorpresa", "Vojvoda": "Possibile sorpresa",
    "Jimenez": "Scommessa", "Kaiki": "Scommessa", "Valdepeñas": "Scommessa",
    "Lulli": "Scommessa", "Mitaj": "Scommessa", "Pedraza": "Low cost",
    "Rensch": "Scommessa", "Drameh": "Sorpresa",
    "Puczka": "Low cost aggiuntivo", "Palma": "Low cost aggiuntivo",
}


def normalize(value: str) -> str:
    """Return a conservative comparison key for display-name variations."""
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]", "", without_accents.lower())


def table_after(markdown: str, marker: str) -> list[list[str]]:
    """Return the data rows of the Markdown table beginning at ``marker``."""
    start = markdown.index(marker)
    rows: list[list[str]] = []
    for line in markdown[start:].splitlines():
        if not line.startswith("|"):
            if rows:
                break
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        if cells[0] in {"Fascia", "Funzione", "Fascia / funzione"}:
            continue
        rows.append(cells)
    return rows


def players_in_cell(cell: str) -> list[tuple[str, str]]:
    """Extract ``Name (Team)`` references from a category-table cell."""
    plain = cell.replace("**", "")
    matches = re.findall(r"(?:^|[,/])\s*([^,()/]+?)\s+\(([^)]+)\)", plain)
    return [(name.strip(), team.strip()) for name, team in matches]


def player_specific_note(note: str, name: str, team: str) -> str:
    """Keep only a table-note fragment that concerns this player or its group."""
    references = re.findall(r"[^,;]+\([^)]+\)", note)
    if not references:
        return note
    target = f"{name} ({team})"
    fragments = [fragment.strip() for fragment in note.split(";")]
    selected = [fragment for fragment in fragments if target in fragment]
    return "; ".join(selected)


def add_category_rows(markdown: str) -> dict[tuple[str, str], dict[str, list[str]]]:
    """Collect the guide's four role-category tables."""
    records: dict[tuple[str, str], dict[str, list[str]]] = defaultdict(
        lambda: defaultdict(list)
    )

    def add(
        name: str,
        team: str,
        fascia: str,
        funzione: str,
        note: str,
        section: str,
    ) -> None:
        record = records[(name, team)]
        for column, value in (
            ("fascia", fascia),
            ("funzione", funzione),
            ("note", note),
            ("source_sections", section),
        ):
            if value and value not in record[column]:
                record[column].append(value)

    for row in table_after(markdown, "| Fascia | Nomi | Uso all'asta |"):
        for name, team in players_in_cell(row[1]):
            add(name, team, row[0], "", player_specific_note(row[2], name, team), "§3 Portieri")

    defender_marker = "| Funzione | Fascia (fonti aggregate) |"
    if defender_marker not in markdown:
        defender_marker = "| Funzione | Priorità | Alternative / prezzo disciplinato | Note |"
    defender_name_columns = (2, 3) if "fonti aggregate" in defender_marker else (1, 2)
    for row in table_after(markdown, defender_marker):
        for cell in (row[index] for index in defender_name_columns):
            for name, team in players_in_cell(cell):
                add(
                    name,
                    team,
                    DEFENDER_FASCE.get(name, "Non specificata"),
                    row[0],
                    player_specific_note(row[-1], name, team),
                    "§4 Difensori",
                )

    for row in table_after(markdown, "| Fascia / funzione | Nomi | Motivo principale |"):
        for name, team in players_in_cell(row[1]):
            add(name, team, row[0], "", player_specific_note(row[2], name, team), "§5 Centrocampisti")

    for row in table_after(markdown, "| Fascia | Nomi | Valutazione |",):
        for name, team in players_in_cell(row[1]):
            add(name, team, row[0], "", player_specific_note(row[2], name, team), "§6 Attaccanti")

    return records


def section(markdown: str, number: int) -> str:
    """Get a numbered guide section without subsequent sections."""
    match = re.search(
        rf"^## {number}\..*?(?=^## {number + 1}\.|\Z)",
        markdown,
        flags=re.MULTILINE | re.DOTALL,
    )
    if match is None:
        raise ValueError(f"Guide section {number} not found")
    return match.group(0)


def mentions(line: str, name: str, team: str) -> bool:
    """Check a guide line for the exact display player reference."""
    return f"{name} ({team})" in line


def relevant_lines(markdown: str, name: str, team: str) -> list[str]:
    """Return compact guide lines mentioning a player, omitting source citations."""
    result = []
    for line in markdown.splitlines():
        if mentions(line, name, team):
            cleaned = re.sub(r"\s*\[[A-Z, ;0-9\-–àèéìòù\.]+\]$", "", line).strip()
            if cleaned:
                result.append(cleaned)
    return result


def set_piece_summary(markdown: str, name: str, team: str) -> str:
    """Summarise only the set-piece roles that the guide assigns to a player."""
    target = f"{name} ({team})"
    for line in markdown.splitlines():
        if not line.startswith("|") or target not in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 3 or cells[0] == "Squadra":
            continue
        roles = []
        if target in cells[1]:
            roles.append("Rigorista indicato")
        if target in cells[2]:
            roles.append("punizioni/corner indicati")
        if roles:
            return "; ".join(roles) + "."

    open_lines = relevant_lines(markdown, name, team)
    if open_lines:
        description = " ".join(open_lines).lower()
        roles = []
        if "rigori" in description:
            roles.append("Candidato ai rigori")
        if "punizioni" in description or "corner" in description or "piazzati" in description:
            roles.append("Tiratore di piazzati")
        if roles:
            return "; ".join(roles) + "; gerarchia aperta o discordante."
    return ""


def resolve_player(
    name: str, guide_team: str, player_list: pd.DataFrame
) -> tuple[pd.Series | None, str]:
    """Resolve a guide player to an official record without fuzzy guessing."""
    alias = OFFICIAL_NAME_ALIASES.get((name, guide_team))
    candidates = player_list[player_list["Nome"] == alias] if alias else pd.DataFrame()
    if candidates.empty:
        name_key = normalize(name)
        candidates = player_list[player_list["Nome"].map(normalize) == name_key]
    if len(candidates) != 1:
        return None, "unmatched"

    candidate = candidates.iloc[0]
    status = (
        "matched"
        if candidate["Squadra"] == guide_team
        or (name, guide_team) in CONFIRMED_GUIDE_TEAM_CORRECTIONS
        else "matched_team_mismatch"
    )
    return candidate, status


def extract(season: str, root: Path = ROOT, guide_path: Path | None = None) -> pd.DataFrame:
    """Build the requested player CSV as a deterministic DataFrame."""
    season_start(season)
    guide_path = guide_path or artifact_directory(root, season) / "guida_unificata_asta.md"
    player_list_path = root / "data" / "player_lists" / f"Quotazioni_Fantacalcio_Stagione_{season}.csv"
    guide = guide_path.read_text(encoding="utf-8")
    player_list = pd.read_csv(player_list_path, dtype={"Id": "Int64"})
    records = add_category_rows(guide)
    set_pieces = section(guide, 7)
    injuries = section(guide, 8)

    rows = []
    for (name, guide_team), record in records.items():
        official, status = resolve_player(name, guide_team, player_list)
        set_piece_info = set_piece_summary(set_pieces, name, guide_team)
        injury_lines = relevant_lines(injuries, name, guide_team)
        source_sections = list(record["source_sections"])
        if set_piece_info:
            source_sections.append("§7 Rigoristi e piazzati")
        if injury_lines:
            source_sections.append("§8 Infortuni e altri rischi")

        injury_state = ""
        risk_details = []
        if injury_lines:
            injury_cells = [line.strip("|").split("|") for line in injury_lines if line.startswith("|")]
            if injury_cells:
                injury_state = " | ".join(cells[1].strip() for cells in injury_cells)
                risk_details.extend(cells[2].strip() for cells in injury_cells)
            for line in injury_lines:
                if line.startswith("|"):
                    continue
                if "storico fisico" in line.lower():
                    risk_details.append("Storico fisico da prezzare.")
                else:
                    risk_details.append("Rischio da verificare alla chiamata.")

        rows.append(
            {
                "id": "" if official is None else official["Id"],
                "nome_guida": name,
                "nome_listone": "" if official is None else official["Nome"],
                "ruolo": "" if official is None else official["R"],
                "squadra": "" if official is None else official["Squadra"],
                "squadra_guida": guide_team,
                "fascia": " | ".join(record["fascia"]),
                "funzione": " | ".join(record["funzione"]),
                "note": " | ".join(record["note"]),
                "infortuni": injury_state,
                "status_rischi": " | ".join(risk_details),
                "rigori_piazzati": set_piece_info,
                "gerarchia_pacchetto": GOALKEEPER_PACKAGES.get((name, guide_team), ""),
                "source_sections": " | ".join(dict.fromkeys(source_sections)),
                "match_status": status,
            }
        )

    result = pd.DataFrame(rows)
    role_order = result["ruolo"].map({"P": 0, "D": 1, "C": 2, "A": 3}).fillna(4)
    return result.assign(_role_order=role_order).sort_values(
        ["_role_order", "squadra", "nome_guida"], na_position="last"
    ).drop(columns="_role_order")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", required=True, help="Stagione YYYY_YY, ad esempio 2026_27")
    parser.add_argument("--guide", type=Path, help="Percorso del Markdown della guida unificata")
    parser.add_argument("--output", type=Path, help="CSV di destinazione")
    args = parser.parse_args()
    artifact = artifact_directory(ROOT, args.season)
    output_path = args.output or artifact / "giocatori_guida_unificata_asta.csv"
    canonical_guide = artifact / "guida_unificata_asta.md"
    guide_path = args.guide or canonical_guide
    if guide_path.resolve() != canonical_guide.resolve():
        canonical_guide.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(guide_path, canonical_guide)
    output = extract(args.season, guide_path=guide_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"Wrote {len(output)} players to {output_path}")


if __name__ == "__main__":
    main()
