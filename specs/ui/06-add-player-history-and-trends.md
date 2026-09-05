# 06: Add season-by-season player history and trend charts

**What to build:** Extend the selected-player panel with historical evidence joined exclusively by player ID. The user can compare raw performance statistics and historical ranking results season by season and see compact trends for appearances and fantasy average.

**Blocked by:** 05: Show current player evidence in a right-hand detail panel.

**Status:** ready-for-agent

- [ ] The detail panel shows one chronologically ordered row per historical season available for the selected player ID.
- [ ] Each row combines that season's raw statistics and historical ranking fields when both are available.
- [ ] A missing statistics row or ranking row remains visibly unavailable and does not remove the other source's evidence.
- [ ] Historical names, clubs, or roles never replace the selected season's authoritative player identity.
- [ ] Compact charts show appearances and fantasy-average trends using the same season order and values as the history table.
- [ ] Zero appearances are distinguished from a season in which the player ID has no statistics row.
- [ ] Players with no historical evidence receive a clear empty state while retaining their current-season detail.
- [ ] Automated tests cover multi-season joins, partial history, changed descriptive attributes, zero appearances, chart data, and no-history players.

