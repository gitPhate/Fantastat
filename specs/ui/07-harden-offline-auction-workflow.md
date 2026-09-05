# 07: Harden the application for offline auction use

**What to build:** Complete and verify the operator workflow for preparing the trusted snapshot and running the catalogue locally during an auction. The finished application must require no internet access, expose no mutation path, and document how to recover from missing or invalid local data.

**Blocked by:** 03: Add automatic season selection and the season picker; 04: Add auction-time player search, filters, and sorting; 05: Show current player evidence in a right-hand detail panel; 06: Add season-by-season player history and trend charts.

**Status:** implemented

- [ ] Separate documented commands build or replace the SQLite snapshot and launch the local UI.
- [ ] Starting or using the UI never rebuilds the snapshot and never writes to the database.
- [ ] The server binds to the local machine only and does not provide authentication or multi-user features.
- [ ] All scripts, stylesheets, fonts, chart code, and other runtime assets are bundled locally.
- [ ] An automated or inspectable check demonstrates that normal startup, search, filtering, selection, chart rendering, and season switching make no internet requests.
- [ ] The UI does not inspect source-file timestamps or warn that its trusted snapshot is stale.
- [ ] Missing snapshots, incompatible database schemas, and snapshots without seasons produce clear recovery instructions rather than partial operation.
- [ ] End-to-end verification covers snapshot creation, application startup, catalogue lookup, player detail, history, and season switching using representative local data.
- [ ] Existing ranking behavior and its full automated test suite remain unchanged except for the approved season-scoped artifact layout.
