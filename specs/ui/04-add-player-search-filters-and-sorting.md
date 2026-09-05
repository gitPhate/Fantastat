# 04: Add auction-time player search, filters, and sorting

**What to build:** Make the catalogue useful for rapid auction lookup. The user can type part of a quotation-list player name, narrow the table by role, club, or unified-guide tier, and sort the visible auction evidence without a page navigation or external request.

**Blocked by:** 02: Build the SQLite snapshot and initial player catalogue.

**Status:** ready-for-agent

- [ ] With no search or filters, the table shows the complete selected-season player universe.
- [ ] Name search runs as the user types and performs case-insensitive substring matching without requiring wildcard characters.
- [ ] Search uses names from the authoritative quotation list and does not apply fuzzy matching, aliases, or name-based identity fallback.
- [ ] Matches are ordered by exact name match first, name prefix second, and other substring matches third before the active table sort resolves ties.
- [ ] Role, club, and unified-guide tier filters can be combined with each other and with name search.
- [ ] Players without unified-guide coverage remain visible and can be distinguished from players assigned a guide tier.
- [ ] The table displays name, role, club, current quotation, FVM, rank, predicted appearances, predicted fantasy average, expected points, and guide tier.
- [ ] Every displayed column supports deterministic sorting, including missing-value behavior.
- [ ] Search, filtering, and sorting operate entirely from data already loaded into the local page.
- [ ] Automated tests cover matching precedence, case handling, combined filters, missing enrichment, empty results, and deterministic sorting.

