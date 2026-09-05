# 03: Open the unified auction guide beside the season picker

**What to build:** Place a button next to the season picker that opens a dedicated offline guide page for the selected season. The page renders the unified auction guide while preserving access to the exact generated Markdown source.

**Blocked by:** None (can start immediately)

**Status:** implemented

- [x] A clearly labeled guide button is visible next to the season picker.
- [x] Activating the button opens a dedicated page for the selected season and renders its unified auction guide.
- [x] For the 2026/27 season, the guide page reads the exact content of `output\\2026-27\\guida_unificata_asta.md` and also exposes the untouched Markdown source.
- [x] The guide action works without an internet connection and does not mutate the guide artifact.
- [x] The button and guide behavior remain correct after changing seasons, including a clear response when a guide is unavailable.
