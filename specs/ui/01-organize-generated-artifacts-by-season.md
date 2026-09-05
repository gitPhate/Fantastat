# 01: Organize generated artifacts by auction season

**What to build:** Make generated ranking and unified-guide artifacts discoverable under a consistent auction-season directory. Generation must accept an explicit season and support future seasons without source-code edits, while preserving the ranking specification's reproducibility and validation guarantees.

**Blocked by:** None (can start immediately).

**Status:** implemented

- [ ] A season is represented by `YYYY_YY` at command boundaries and by `YYYY-YY` in the generated-artifact directory name.
- [ ] Ranking, validation, and unified-guide artifacts for the same auction season are written beneath that season's directory.
- [ ] Ranking generation still writes final artifacts only after calculation and validation complete successfully.
- [ ] Unified-guide extraction accepts the target season instead of relying on hard-coded season-specific inputs or outputs.
- [ ] Generating artifacts for a future valid season requires only the corresponding inputs, not source-code changes.
- [ ] Existing ranking and guide tests are updated or extended to cover season-scoped output discovery and invalid season handling.
