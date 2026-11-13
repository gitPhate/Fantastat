# Creating a new season

This document is the repeatable workflow for preparing a new auction season.
Replace `<season>` with the underscore form used by the command line, for
example `2027_28`. Generated artifacts use the hyphen form, `2027-28`, as the
directory name under `output/`.

## Checklist

0. Export the league WhatsApp chat and regenerate the private documents.
1. Download the Fantacalcio.it and Fantacalcio Online player lists and convert them to CSV.
2. Optionally update the auction-guide source material and regenerate `docs/GUIDA_ASTA.md`.
3. Create the season research folder and collect current-season source material.
4. Aggregate the research into a unified guide and standardized player records in `output/<season>/guida_unificata_asta.md`.
5. Extract the unified guide into the standard player CSV.
6. Generate the statistical ranking for the new season.
7. Read the Fantacalcio injury list, create the season Markdown note, and extract the ID-bound `infortuni_fantacalcio.csv`.
8. Build the SQLite snapshot used by the auction UI.
9. Start the offline UI and verify the results.

The order matters: the player list and guide CSV must exist before the snapshot
is built, the injury CSV must be available before the snapshot build, and the
historical statistics must exist before ranking generation.

## 0. Export the chat and regenerate the private documents

Before the season starts, refresh the league context that lives only on the
maintainer's machine. The chat export and the documents derived from it contain
personal information: they are ignored by git (`data/chats/` and
`docs/private/`) and must never be committed, pasted into tracked files, or
sent to an external service.

1. In WhatsApp, open the league group and use *Export chat* (include media only
   if the auction-sheet photos need to be read again). Save the text file in
   `data/chats/`, replacing the previous export. Keep the file name WhatsApp
   generates.
2. Give an LLM the new export together with the current
   `docs/private/CONTEXT.md`, `docs/private/STORICO_ASTE.md` and
   `docs/RULES.md`, and ask it to update them with what happened since the last
   export:
   - `docs/private/CONTEXT.md`: group and organizers, participants (with
     entries and exits), the new season's organization and dates, recurring
     informal conventions, tools used, and the roll of honour.
   - `docs/private/STORICO_ASTE.md`: rosters and prices paid for each new
     auction, reconstructed from the photographed auction sheets and the chat
     text, one section per team with the poster of the photo. Mark uncertain
     names or prices (**?** or bold with a note) and keep the coverage and
     reliability notes; uncertain data must not be presented as verified.
   - `docs/RULES.md` (public, no personal data): rule changes voted in the chat,
     without names of members.
3. Review the output manually, in particular the reliability notes. Do not copy
   member names or chat quotations into any tracked file.
4. Before committing, check that nothing private leaked:

```powershell
git status --short
git grep -n -i "<a member name or a chat quotation>"
```

The original auction-sheet photos are not in the repository. The private
documents are the only structured record of historical auctions, so back them
up outside the repository.

## 1. Download, convert, and merge player lists

Go to Fantacalcio.it and download:

- the statistics workbook for the most recently completed season, for example
  `Statistiche_Fantacalcio_Stagione_2026_27.xlsx`;
- the quotation/player-list workbook for the auction season being prepared,
  for example `Quotazioni_Fantacalcio_Stagione_2027_28.xlsx`.

Put the statistics workbook in `data/stats/` and the quotation workbook in
`data/player_lists/fantacalcio/`. Preserve the
`Quotazioni_Fantacalcio_Stagione_YYYY_YY.xlsx` name. The official workbook
must contain the `Tutti` sheet; the converter reads its effective headers on
row two.

For every newly prepared auction season, download the corresponding Fantacalcio Online workbook and rename it to the
same season form, for example
`Quotazioni_Fantacalcio_Stagione_2027_28.xlsx`. Put it in
`data/player_lists/fantacalcio-online/`. Its effective headers must be on row
two and include `Nome`, `Ruolo Fantacalcio.it`, `Squadra`, `IS %`, and `ETA'`.

The Online source has no Fantacalcio ID and uses a different name format. For
each new season, create
`data/player_lists/fantacalcio-online/Collegamenti_Fantacalcio_Online_Stagione_YYYY_YY.csv`
with exactly these columns:

```csv
Id,NomeOnline,SquadraOnline
```

It must link every official player ID exactly once to the extracted Online name
and club. This is an explicit reviewed identity map, not a fuzzy name match.

Run the converter from the repository root:

```powershell
python src/convert_workbooks.py
```

This writes CSVs beside every workbook. The official CSV under
`data/player_lists/fantacalcio/` is always the ranking input. For each new
season, the required Online CSV and its reviewed links also produce the
generated enriched CSV `output/YYYY-YY/Quotazioni_Fantacalcio_Stagione_YYYY_YY.csv`, retaining
every official `Tutti`-sheet column and adding `starting_index` (the Online
`IS %`, Indice di titolarità) and `age` (the Online `ETA'`). Historical seasons
without Online data continue to use their official lists; the two UI fields are
unavailable for those seasons. Check the headers against the
[Fantacalcio legend](../data/player_lists/fantacalcio/LEGEND.md), the
[Fantacalcio Online legend](../data/player_lists/fantacalcio-online/LEGEND.md),
and [the statistics legend](../data/stats/LEGEND.md). Do not edit generated
CSVs; correct the workbook or reviewed link map and rerun the converter.

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

Build the guide from one logical, standardized player record for each player
mentioned. Narrative and role tables are the readable auction view of those
records; they must not introduce extra player facts or conflicting categories.
The guide must preserve source traceability, identify disagreements, and
separate facts, recommendations, and non-clinical risks.

Do not collect or normalize current injuries, availability, or expected return
in this step. Those data belong exclusively to the separate injury workflow in
step 7 and its `infortuni_fantacalcio.csv`; the snapshot builder imports that
CSV into the existing injury field in the database.

### Player identity and record

Write every player reference as `Name (Team)`. Once the identity is unambiguous,
prefer the exact `Nome` spelling in the current quotation list; retain a useful
different source spelling in `note`. The connector attaches the official
Fantacalcio.it `Id`, Classic role, and current team. Names are not authoritative
keys: do not guess an identity, role, or club for an ambiguous reference. Keep
the researched team in `squadra_guida` when it differs from the quotation list,
so that the discrepancy is emitted as `matched_team_mismatch`. If neither name
nor team can be resolved safely, use `Da verificare` for `squadra_guida`, set
`confidenza` to `Bassa`, explain the ambiguity in `da_verificare`, and accept an
`unmatched` row rather than inventing an identity.

To identify each player's current team, consult the current-season file in
`data/player_lists/`.

For every player cited in the guide, collect these normalized fields:

| Field | Purpose |
|---|---|
| `nome_guida` | Player name as written in the guide. |
| `squadra_guida` | Team stated by the research source. |
| `fascia` | Canonical auction tier. |
| `funzione` | Canonical auction role or intended use. Multiple values use ` | `. |
| `note` | Concise auction thesis and rationale. |
| `status_rischi` | Non-clinical risk: rotation, competition, uncertain minutes or role, unconfirmed transfer, or open set-piece hierarchy. |
| `rigori_piazzati` | Penalty, free-kick, and corner responsibilities or hierarchy. |
| `gerarchia_pacchetto` | Goalkeeper hierarchy, pairing, or another package dependency. |
| `fonti` | Supporting source labels and retrieval dates. |
| `confidenza` | `Alta`, `Media`, or `Bassa`, based on source agreement and freshness. |
| `da_verificare` | Facts to confirm at the call. Leave empty when none are needed. |

Use only these values for `fascia`:

```text
Super Top
Top
Semitop
Fascia alta
Fascia media
Low cost
Scommessa
Da monitorare
```

Use these canonical values for `funzione`, selecting one or more that apply:

```text
P: Titolare sicuro | Titolare con riserva | Secondo da pacchetto | Alternanza
D: Premium bonus | Esterno da bonus | Centrale da modificatore | Titolare affidabile | Rotazione | Scommessa
C: Premium bonus | Titolare offensivo | Qualità-prezzo | Da voto | Rotazione | Scommessa
A: Prima scelta | Titolare | Seconda punta / partner | Rotazione offensiva | Ultimo slot | Scommessa
```

For `rigori_piazzati`, use controlled terms such as `Primo rigorista`,
`Secondo rigorista`, `Candidato ai rigori`, `Primo tiratore punizioni`,
`Primo tiratore corner`, `Tiratore piazzati`, `Gerarchia aperta`, or
`Gerarchia discordante`. Put explanations and exceptional cases in `note` or
`status_rischi`, not in alternative category spellings.

Facts must have supporting sources; recommendations belong in `fascia`,
`funzione`, and `note`; uncertainty belongs in `status_rischi` or
`da_verificare`. Do not turn missing evidence into a negative fact. In
particular, an empty set-piece field does not mean the player cannot take set
pieces, and no non-clinical risk recorded does not mean there is no risk.

### Required Markdown structure

Keep these sections and role tables for the human-readable auction view:

```text
## 3. Portieri
## 4. Difensori
## 5. Centrocampisti
## 6. Attaccanti
## 7. Rigoristi e piazzati
## 8. Rischi e verifiche alla chiamata
## 9. Schede giocatore normalizzate
```

The role tables must explicitly assign each cited player a tier, function, and
auction note. Section 7 must name players using the same `Name (Team)` form
when recording penalty and set-piece hierarchies. Section 8 contains only
non-clinical risks and checks to make at the call; it must not contain injury
or expected-return data. Section 9 contains one normalized record per cited
player using all fields listed above, and is both the human-review source of
truth and the only guide section parsed by the connector. The prose and role
tables may summarize those records, but the connector never reconstructs
structured facts from narrative text.

Before publishing, verify that every cited player has a team, tier, and
function; that every set-piece, hierarchy, risk, and package reference belongs
to a player; that there are no duplicate logical `Name + Team` records; that
categories use the canonical vocabulary; and that source/listone discrepancies
are explicit. If a source cannot identify a player unambiguously, leave the
match unresolved for review rather than guessing.

## 5. Extract the guide into the standard CSV

Use the single reusable connector at
`src/connectors/unified_auction_guide.py`. Do not copy or customize it for each
season: season-specific differences belong in the guide and quotation CSV, not
in Python branches, alias tables, or hard-coded player categories. Preparing a
new season should require only new inputs and a different `--season` value. If
the normalized guide format itself changes, update this one connector and its
tests for every season.

The connector reads only the normalized records in section 9, validates the
required fields and canonical vocabulary, resolves each record against the
current quotation CSV, attaches the official `Id`, Classic role, and current
team, and atomically writes the season-scoped CSV. Run:

```powershell
python src/connectors/unified_auction_guide.py --season <season>
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
| `infortuni` | Always empty here; populated only by the separate injury workflow. |
| `status_rischi` | Non-clinical risks such as rotation, competition, or role uncertainty. |
| `rigori_piazzati` | Penalty and free-kick/corner responsibilities. |
| `gerarchia_pacchetto` | Goalkeeper package or hierarchy information. |
| `fonti` | Source labels and dates copied from the normalized record. |
| `confidenza` | `Alta`, `Media`, or `Bassa`, copied from the normalized record. |
| `da_verificare` | Open checks copied from the normalized record. |
| `match_status` | Matching result, such as `matched`, `matched_team_mismatch`, or `unmatched`. |

The connector uses conservative normalized equality for case, accents, spaces,
and punctuation; it never uses fuzzy name matching. It first requires the same
guide team and then permits a different official team only when the normalized
name identifies exactly one listone player. Structural errors, duplicate
logical records, invalid categories, and functions incompatible with the
official Classic role stop publication. Unresolved identities remain in the
CSV with a blank ID and `match_status=unmatched`; team discrepancies are marked
`matched_team_mismatch`.

The `infortuni` column is emitted empty for compatibility with the snapshot
schema. Do not populate it from the guide: step 7 is the exclusive injury
source. Review all rows whose `match_status` is not `matched`, all blank or
duplicate IDs, and unexpected output counts before continuing. The snapshot
builder loads only rows with valid IDs and never substitutes a guessed
identity.

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
(`data/player_lists/fantacalcio/Quotazioni_Fantacalcio_Stagione_<season>.csv`). Do not use
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
