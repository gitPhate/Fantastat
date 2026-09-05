# Creating a new season

This document is the repeatable workflow for preparing a new auction season.
Replace `<season>` with the underscore form used by the command line, for
example `2027_28`. Generated artifacts use the hyphen form, `2027-28`, as the
directory name under `output/`.

## Checklist

1. Download the new Fantacalcio.it workbooks and convert them to CSV.
2. Optionally update the auction-guide source material and regenerate `docs/GUIDA_ASTA.md`.
3. Create the season research folder and collect current-season source material.
4. Aggregate the research into `output/<season>/guida_unificata_asta.md`.
5. Extract the unified guide into the standard player CSV.
6. Generate the statistical ranking for the new season.
7. Read the Fantacalcio injury list, create the season Markdown note, and extract the ID-bound `infortuni_fantacalcio.csv`.
8. Build the SQLite snapshot used by the auction UI.
9. Start the offline UI and verify the results.

The order matters: the player list and guide CSV must exist before the snapshot
is built, the injury CSV must be available before the snapshot build, and the
historical statistics must exist before ranking generation.

## 1. Download and convert the Fantacalcio.it workbooks

Go to Fantacalcio.it and download:

- the statistics workbook for the most recently completed season, for example
  `Statistiche_Fantacalcio_Stagione_2026_27.xlsx`;
- the quotation/player-list workbook for the auction season being prepared,
  for example `Quotazioni_Fantacalcio_Stagione_2027_28.xlsx`.

Put the workbooks in `data/stats/` and `data/player_lists/`, respectively.
Preserve the `YYYY_YY` naming convention. The workbook must contain the
`Tutti` sheet; the converter reads that sheet with its effective headers on
row two. The ranking uses Classic fields and identifies players by
Fantacalcio.it `Id`, not by fuzzy name matching.

Run the converter from the repository root:

```powershell
python src/convert_workbooks.py
```

This writes a CSV beside every workbook. Check that the new files exist and
that their headers match [the player-list legend](../data/player_lists/LEGEND.md)
and [the statistics legend](../data/stats/LEGEND.md). Do not manually edit the
generated CSVs; fix the workbook or the conversion inputs and rerun the
converter if necessary.

## 2. Update the general auction guide (optional)

If the league rules, budget, roster composition, auction strategy, or external
auction guidance have changed, update the relevant files under
`data/auction_guide/`. Then use an LLM to revise `docs/GUIDA_ASTA.md` so that
it remains the general guide for the current league.

Review the generated text manually. It should reflect the current
`docs/RULES.md`, distinguish league-specific rules from generic advice, and
avoid presenting uncertain historical auction data as verified fact. This
guide is context for the season-specific guide; it is not automatically fed
into the statistical ranking.

## 3. Create the season research folder

Create `data/seasons/<season>/`, using the display form `YYYY-YY`, for example:

```powershell
New-Item -ItemType Directory -Force data/seasons/2027-28
```

Collect current-season research from several useful sources and save it in
that folder, preferably with one Markdown file per source or topic. Useful
topics include probable lineups, injuries, transfers, goalkeeper hierarchies,
set-piece and penalty takers, low-cost players, and auction notes.

Record the source URL, publication date or retrieval date, and any relevant
uncertainty in the files. Keep raw league chat and other private material
private. Research in this directory is human decision support and must not be
silently treated as an input to `ranking.py`.

## 4. Generate the unified auction guide

Give a frontier LLM the contents of `data/seasons/<season>/` together with the
current `docs/GUIDA_ASTA.md`, `docs/RULES.md`, and the relevant data legends.
Ask it to reconcile the sources and write:

```text
output/2027-28/guida_unificata_asta.md
```

The guide should preserve source traceability, identify disagreements, and
separate facts, recommendations, and risks. It must follow the Markdown
structure expected by `src/extract_auction_guide_players.py`: sections for
portieri, difensori, centrocampisti, attaccanti, piazzati, and injuries/risks.

Standardize every player's category against the canonical
`giocatori_guida_unificata_asta.csv` layout before extraction. In particular,
use stable values and meanings for `fascia` (tier) and `funzione` (auction
function); do not invent spelling variants or put a category in free-form
notes. Keep player names accompanied by their team so the connector can match
them to the official quotation list. If a source cannot identify a player
unambiguously, leave the match unresolved for review rather than guessing.

## 5. Extract the guide into the standard CSV

The connector is `src/extract_auction_guide_players.py`. It reads the unified
Markdown guide, resolves names against the current quotation CSV, attaches the
official `Id`, role, and team, and writes the season-scoped CSV. Run:

```powershell
python src/extract_auction_guide_players.py --season <season>
```

For `2027_28`, the inputs and output are:

```text
output/2027-28/guida_unificata_asta.md
output/2027-28/giocatori_guida_unificata_asta.csv
```

The standard CSV layout is:

| Column | Purpose |
|---|---|
| `id` | Official Fantacalcio.it player ID; the authoritative join key. Empty when matching needs review. |
| `nome_guida` | Player name as written in the unified guide. |
| `nome_listone` | Official quotation-list name after a successful match. |
| `ruolo` | Official Classic role: `P`, `D`, `C`, or `A`. |
| `squadra` | Official current team from the quotation list. |
| `squadra_guida` | Team stated in the guide, retained to expose discrepancies. |
| `fascia` | Standardized auction tier, such as `Top`, `Semitop`, `Fascia media`, or `Low cost`. |
| `funzione` | Standardized auction use, such as a role or tactical purpose. |
| `note` | Player-specific auction notes and rationale. |
| `infortuni` | Injury or availability information extracted from the guide. |
| `status_rischi` | Other risks, such as rotation, role uncertainty, or physical history. |
| `rigori_piazzati` | Penalty and free-kick/corner responsibilities. |
| `gerarchia_pacchetto` | Goalkeeper package or hierarchy information. |
| `source_sections` | Guide sections that contributed information to the row. |
| `match_status` | Matching result, such as `matched`, `matched_team_mismatch`, or `unmatched`. |

Review rows with `match_status` other than `matched`, blank IDs, duplicate IDs,
and unexpected category values before continuing. The snapshot builder only
loads rows with valid IDs and never substitutes a guessed identity.

## 6. Generate the ranking

Run the ranking for the auction season:

```powershell
python src/run_ranking.py --season <season>
```

For `2027_28`, this creates:

```text
output/2027-28/ranking.csv
output/2027-28/validation.csv
```

The command reads the new quotation CSV and the configured historical seasons
from `data/stats/`. It validates the inputs before publishing the outputs. Run
the full test suite when changing the workflow or ranking behavior:

```powershell
python -m unittest discover -s src/tests -v
```

Check the validation output, role ordering, schema, and reproducibility. The
ranking is a quantitative signal, not a replacement for the current-season
research in the unified guide.

## 7. Add the current injury snapshot

Open the current [Fantacalcio.it Serie A injury list](https://www.fantacalcio.it/infortunati-serie-a)
and record every listed player in a season Markdown note:

```text
data/seasons/<season>/infortuni_fantacalcio_<season>.md
```

Include each player's club and the return date or estimated return period when
the source provides one. Preserve the retrieval date and source URL in the
note. Then extract the same list into:

```text
output/<season>/infortuni_fantacalcio.csv
```

Bind each player to the `Id` in the current season's quotation CSV
(`data/player_lists/Quotazioni_Fantacalcio_Stagione_<season>.csv`). Do not use
fuzzy name matching or invent IDs. The CSV must contain `Id`, `Player`,
`Club`, `Role`, and `ExpectedReturn`; use `To be assessed` when no return
estimate is available. During the snapshot build, `build_snapshot.py` imports
`ExpectedReturn` into the database's existing `guides.injuries` field, making
the information visible in the player catalogue and detail panel.

## 8. Build the SQLite snapshot

The script is `src/build_snapshot.py`. It discovers all valid season folders
under `output/`, validates their quotation, ranking, guide, and historical
inputs, and atomically writes the local database:

```powershell
python src/build_snapshot.py
```

The resulting snapshot is `output/fantastat.sqlite3`. It is rebuilt from the
CSV artifacts and is not the source of truth. If the build fails, correct the
reported season/file/schema problem and rerun it; the previous snapshot is
preserved until a complete build succeeds.

## 9. Run and verify the auction UI

Start the read-only local UI:

```powershell
python src/auction_ui.py
```

Open `http://127.0.0.1:8765` in a browser. Verify that the new season is
available, the player catalogue contains the quotation-list universe, and
selected players show ranking, guide enrichment, and historical information.
The UI reads only `output/fantastat.sqlite3`; it does not rebuild the database
or fetch data from the Internet. Stop it with `Ctrl+C` when finished.
