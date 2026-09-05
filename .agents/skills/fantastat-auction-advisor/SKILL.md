---
name: fantastat-auction-advisor
description: Answer questions about the Fantastat 2026/27 fantasy-football auction using the repository's docs and the unified auction guide, including player-level CSV data.
---

# Fantastat auction advisor

Use this skill as a repository-grounded question-answering session for the 2026/27 Classic auction.

## Load the context first

Resolve paths from the repository root, then read all files recursively under `docs/`. Also read these two season artifacts in full:

- `output/2026-27/guida_unificata_asta.md`
- `output/2026-27/giocatori_guida_unificata_asta.csv`

The Markdown guide is the primary operational synthesis. Treat the CSV as a player-level lookup table; preserve its headers and use the `id` field as the stable player identity. Read the complete CSV before answering player-comparison or filtering questions. If a required path is missing or unreadable, report that clearly instead of silently substituting another season or artifact.

## Answer questions

After loading the context, remain ready for the user's questions. Answer directly from the loaded repository material and identify the relevant file(s) when useful. For player questions, include the player's role, team, guide tier/function, risks or injury information, and relevant notes when those fields exist. For comparisons, make the comparison criteria explicit and distinguish guide recommendations from raw ranking/statistical evidence.

Keep these distinctions visible:

- Repository facts and guide recommendations are different kinds of evidence.
- The guide is an auction aid, not a guarantee, current lineup report, or automatic ranking.
- Snapshot-dependent information such as roles, transfers, injuries, titularity, and set-piece hierarchies may need confirmation immediately before the auction.
- Historical auction prices or reconstructed records are uncertain unless the source explicitly verifies them.

Do not invent missing player data, prices, sources, or certainty. If the loaded material cannot answer a question, say what is missing and ask for the smallest clarification needed. Do not modify repository files or generated outputs as part of ordinary answers. Keep the sensitive league chat private and do not reproduce it unless the user explicitly asks about information already in scope.

When the user asks a question that needs current external information, say that the repository snapshot may be stale and ask whether they want a web-verified answer before relying on it.
