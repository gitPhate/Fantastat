# Repository Guidelines

## What This Repository Is About

Fantastat is a private preparation and analysis tool for the fantasy-football league. Its main purpose is to support the annual Serie A Fantacalcio Classic auction: organize the available player list, study historical performance and auction prices, and produce a transparent statistical ranking that managers can combine with current football knowledge and auction strategy.

The 2026/27 league has 10 teams. Each team drafts 3 goalkeepers, 8 defenders, 8 midfielders, and 6 forwards in a calling-order auction. The budget is 500 credits usable across all roles, plus 50 additional credits reserved for forwards. The league also uses a defense modifier when at least four defenders are fielded. These rules and the auction guide are context for the project, not inputs to the statistical ranking unless a specification explicitly says otherwise.

The ranking is a quantitative signal, not a complete auction recommendation. It estimates expected appearances and fantasy average from recent historical seasons, with newer seasons weighted more heavily. Current prices, auction tactics, injuries, likely lineups, transfers, and editorial research can add information that the deliberately simple model does not capture.

## Repository Data

- `data/player_lists/fantacalcio/` contains official Fantacalcio.it quotation workbooks and extracted CSVs; these are the ranking inputs and define the Classic player universe. `data/player_lists/fantacalcio-online/` contains the required Online workbooks, extracted CSVs, and reviewed ID-link CSVs for new auction seasons. The converter writes the enriched player-list CSV under that season's `output/YYYY-YY/`; Online `starting_index` and `age` are UI evidence only. Historical seasons without Online data remain supported by their official lists.
- `data/stats/` contains Fantacalcio.it historical statistics workbooks, plus a CSV extracted from each workbook's `Tutti` sheet (via `src/convert_workbooks.py`); the ranking code reads only the CSV. The `Tutti` sheet/CSV provides player IDs, roles, appearances (`Pv`), fantasy average (`Fm`), and related performance fields. `data/stats/LEGEND.md` defines the columns.
- `data/seasons/` contains season-specific research gathered from football and Fantacalcio sources: likely lineups, injuries, set-piece takers, goalkeeper hierarchies, low-cost ideas, transfers, and auction notes. Use it as human decision support, not as an automatic ranking input unless the relevant spec is changed.
- `data/auction_guide/` and `docs/` contain the league context, rules, auction strategy, and historical reconstruction. `docs/RULES.md` is the current league-rule reference; market and roster rules are reconsidered each season and should be verified before relying on them.
- `data/chats/` holds the sensitive raw export of the league WhatsApp chat (a `.txt` export). The folder is **not tracked in git** (listed in `.gitignore`; removed from the repository history before the repo was made public) and exists only on the maintainer's machine. Parts of `docs/CONTEXT.md`, `docs/RULES.md` and `docs/STORICO_ASTE.md` were derived from it, so it is the source to re-read when those docs need updating. Keep it private and do not redistribute it.
- `output/` contains generated ranking and validation CSVs. Treat these as reproducible artifacts, not hand-edited source data.

Historical auction records are incomplete and partly reconstructed from photographs and chat messages. They are useful for context and future analysis, but uncertain names or prices must not be presented as verified facts. See `docs/STORICO_ASTE.md` for coverage and reliability notes.

## Source of Truth and Change Workflow

Use `specs/` as the behavioral source of truth for ranking behavior, formulas, validation, input requirements, and output schemas. Use `docs/` for league rules and domain context, and the data legends for workbook schemas. Before changing behavior, check whether the requested change belongs in the specification, configuration, documentation, or implementation.

When adding a new season, preserve the `YYYY_YY` naming convention, verify the official, Online, and statistics workbooks, prepare the reviewed Online-to-Fantacalcio ID-link CSV, and run `python src/convert_workbooks.py` to (re)generate their CSVs before running the ranking. Historical seasons may use only their official lists. Do not silently fill gaps or reinterpret uncertain source data. Keep raw league and player data private.

## Code Structure

The code area is `src/`: `ranking.py` contains calculation, validation, and file-handling logic; `run_ranking.py` is the CLI entry point; `convert_workbooks.py` extracts the `Tutti` sheet of each player-list and statistics workbook into a matching CSV; `tests/test_ranking.py` contains the automated tests; and `config.yaml` contains ranking configuration. Recency weights are listed newest first.

Use standard Python conventions: four-space indentation, `snake_case` functions and variables, `PascalCase` classes, and uppercase module constants. Keep type hints on public and calculation-heavy functions, use `pathlib.Path` for paths, and prefer small deterministic functions suitable for unit testing. Preserve the explicit error style by raising `RankingError` with the affected file, season, and cause. No formatter or linter is configured; keep changes PEP 8-compatible and imports grouped as in existing modules.

The implementation uses only the standard library, `pandas`, and `openpyxl`. There is no build step or dependency manifest. `ranking.py` reads plain CSV (headers on row one); `convert_workbooks.py` reads official `Tutti` sheets and Online row-two headers, then merges them through reviewed Fantacalcio IDs. Player identity is based on Fantacalcio.it `Id`, never on a fuzzy name match.

## Testing and Verification

Tests use the standard-library `unittest` framework and descriptive `test_<behavior>` names. Add focused tests for every formula, validation branch, input error, and season rollover changed. Prefer small in-memory pandas DataFrames; tests must not mutate source workbooks or committed output files.

Run the full suite from the repository root before submitting changes:

```powershell
python -m unittest discover -s src/tests -v
```

For the available season, regenerate both outputs with:

```powershell
python src/run_ranking.py --season 2026_27
```

The command must produce `output/ranking_2026_27.csv` and `output/validation_2026_27.csv` only after calculation and validation succeed. Confirm schema, role ordering, reproducibility, and any ranking changes against the relevant specification.

## Running the Auction UI

The offline auction UI is a read-only local server over a SQLite snapshot (see `docs/OFFLINE_AUCTION_UI.md`). From the repository root:

```powershell
python src/run_ranking.py --season 2026_27
python src/connectors/unified_auction_guide.py --season 2026_27
python src/build_snapshot.py   # writes output/fantastat.sqlite3 (not versioned)
python src/auction_ui.py       # serves http://127.0.0.1:8765
```

Run the first three steps only when the season data or ranking changed; otherwise start `auction_ui.py` directly. Use `--port` to change the port and `--database` to point at another snapshot. If the snapshot is missing or incompatible, the server tells you to rerun `build_snapshot.py`.

## Commits and Pull Requests

Recent history favors short imperative subjects such as `Implement player ranking backtest` and `Add role-specific recency weights support`. Keep each commit scoped to one coherent change.

Pull requests should explain the behavior and rationale, cite the relevant spec, list the test command and result, link any issue, and call out generated CSV or schema changes. Include sample output diffs when ranking behavior changes; screenshots are useful only for documentation rendering changes.
