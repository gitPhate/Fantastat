# 03: Add automatic season selection and the season picker

**What to build:** Let the user view any auction season recorded in the trusted SQLite snapshot. The application chooses a useful default from the current date and provides a visible picker that switches the complete catalogue and its enrichments together.

**Blocked by:** 02: Build the SQLite snapshot and initial player catalogue.

**Status:** ready-for-agent

- [ ] The picker contains only auction seasons recorded in the SQLite snapshot.
- [ ] Picker labels use `YYYY/YY`, while season identity remains based on the four-digit starting year.
- [ ] From August through December, the preferred default is the season beginning in the current calendar year.
- [ ] From January through July, the preferred default is the season beginning in the previous calendar year.
- [ ] If the preferred season is unavailable, the newest available season is selected.
- [ ] Switching seasons updates the player universe, summary enrichment, selection state, and subsequent detail queries consistently.
- [ ] The application handles a snapshot containing no selectable seasons with a clear, actionable error.
- [ ] Automated tests cover the month boundary, July behavior, unavailable preferred seasons, picker labels, and season switching.

