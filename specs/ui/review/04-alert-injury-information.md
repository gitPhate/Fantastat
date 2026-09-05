# 04: Mark players with injury information

**What to build:** Add a clear, accessible alert to each player-table row when the player has data in `infortuni`, allowing managers to notice injury-related information without opening player details.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] A player with non-empty `infortuni` data is visibly marked in the table.
- [ ] A player without `infortuni` data is not marked as injured or at risk by default.
- [ ] The indication uses accessible text or an equivalent non-color-only signal and explains that injury information is available.
- [ ] The indication remains correct across season changes, filtering, sorting, and row selection.
- [ ] Automated tests cover populated, empty, and missing `infortuni` values.
