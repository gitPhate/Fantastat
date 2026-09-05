# 04: Mark players with injury information

**What to build:** Add a clear, accessible alert to each player-table row when the player has data in `infortuni`, allowing managers to notice injury-related information without opening player details.

**Blocked by:** None (can start immediately)

**Status:** implemented

- [x] A player with non-empty `infortuni` data is visibly marked next to the player’s name in the table.
- [x] A player without `infortuni` data is not marked as injured or at risk by default.
- [x] The indication uses accessible text or an equivalent non-color-only signal and explains that injury information is available.
- [x] The indication remains correct across season changes, filtering, sorting, and row selection.
- [x] Automated tests cover populated, empty, and missing `infortuni` values.
