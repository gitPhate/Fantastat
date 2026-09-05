# 05: Show current player evidence in a right-hand detail panel

**What to build:** Let the user select a catalogue row and inspect the player's current auction evidence without losing the search results. A persistent right-hand panel presents authoritative identity and quotation data followed by ranking and unified-guide enrichment.

**Blocked by:** 02: Build the SQLite snapshot and initial player catalogue.

**Status:** implemented

- [ ] Selecting a catalogue player opens or updates a persistent right-hand detail panel without navigating away from the table.
- [ ] The panel identifies the selected player by Fantacalcio ID and shows the selected season's quotation-list name, role, club, current quotation, and FVM.
- [ ] Current ranking evidence includes rank, predicted appearances, predicted fantasy average, expected points, and validation status.
- [ ] Unified-guide evidence includes tier, function, notes, risks or injuries, set pieces, and hierarchy when supplied by the snapshot.
- [ ] Missing ranking or guide enrichment is explicitly shown as unavailable rather than hidden, synthesized, or treated as zero.
- [ ] Selecting another row replaces the detail content while preserving the current search, filters, sorting, and season.
- [ ] The panel remains usable on the supported laptop and desktop layout; phone-specific behavior is not required.
- [ ] Automated tests verify ID-based selection, field provenance, missing-data presentation, and preservation of catalogue state.
