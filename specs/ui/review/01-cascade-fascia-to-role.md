# 01: Cascade fascia options from role

**What to build:** Make the fascia (child) filter depend on the selected role (parent), so the available fascia choices always belong to the active role and invalid child selections cannot remain active.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] With no role selected, the fascia control follows the agreed all-role behavior and does not hide valid fascia values.
- [ ] Selecting a role restricts the fascia options to fascia values belonging to that role.
- [ ] Changing or clearing the role clears or safely adjusts a fascia selection that is no longer valid.
- [ ] The table results and empty-state behavior remain correct when role and fascia are combined.
- [ ] Automated tests cover initial state, role changes, clearing the parent, and invalid child selections.
