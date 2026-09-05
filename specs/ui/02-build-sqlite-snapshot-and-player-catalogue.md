# 02: Build the SQLite snapshot and initial player catalogue

**What to build:** Provide an explicit snapshot-build workflow that discovers available auction seasons, validates their inputs, and atomically creates one read-only SQLite database. A local web application must be able to start from that snapshot and display the complete player universe for an available season, enriched by ranking and unified-guide data when present.

**Blocked by:** 01: Organize generated artifacts by auction season.

**Status:** ready-for-agent

- [ ] The snapshot builder discovers auction seasons from the season-scoped generated-artifact directories and records their starting year and display label.
- [ ] Each season's player universe and displayed identity fields come exclusively from its Fantacalcio quotation CSV.
- [ ] Ranking and unified-guide data are left-joined to the player universe exclusively by Fantacalcio player ID.
- [ ] Historical statistics and historical rankings are stored in season-aware, long-form structures suitable for player history queries.
- [ ] One player may have different descriptive attributes across seasons without losing the stable ID-based relationship.
- [ ] Duplicate or null player IDs, missing required files, unreadable inputs, and required-schema errors stop the build with the affected season, file, and cause identified.
- [ ] Missing ranking, guide, or historical enrichment remains nullable and never removes an otherwise valid current player.
- [ ] The completed database replaces the previous snapshot atomically only after every selected season passes validation.
- [ ] The generated SQLite snapshot is excluded from version control.
- [ ] The local application starts from the snapshot without reading or regenerating source CSV files and can render the full catalogue for an available season.
- [ ] Automated tests cover discovery, joins, validation failures, nullable enrichment, atomic replacement, and the initial catalogue response.

