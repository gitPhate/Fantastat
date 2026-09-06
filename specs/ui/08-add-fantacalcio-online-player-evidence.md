# 08: Show Fantacalcio Online player evidence

**What to build:** Enrich the selected player's detail panel with the
Fantacalcio Online Indice di titolarità and age stored in the trusted snapshot.

**Blocked by:** 05: Show current player evidence in a right-hand detail panel.

**Status:** implemented

- [ ] The snapshot imports nullable `starting_index` and `age` from the merged
  player-list CSV without changing the official player universe or ranking.
- [ ] The detail panel labels and displays Indice di titolarità and Età.
- [ ] Missing Online evidence is explicitly presented as unavailable.
- [ ] Automated tests cover persistence from the merged CSV through the player
  detail response and panel.
