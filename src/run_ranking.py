"""CLI entry point for player ranking generation."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from ranking import RankingError, run, season_start


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera il ranking statistico dei calciatori.")
    parser.add_argument("--season", required=True, help="Stagione nel formato YYYY_YY, ad esempio 2026_27")
    args = parser.parse_args()
    try:
        season_start(args.season)
        ranking, validation = run(Path(__file__).resolve().parents[1], args.season)
    except RankingError as exc:
        parser.error(str(exc))
    print(f"Creati: {ranking} e {validation}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
