# Concepts

Shared domain vocabulary for this project — entities, named processes, and status concepts with project-specific meaning. Seeded with core domain vocabulary, then accretes as ce-compound and ce-compound-refresh process learnings; direct edits are fine. Glossary only, not a spec or catch-all.

### Optimistic value

The value a writable entity (a number, switch, or select backed by the charger's settings) records immediately after sending a write, shown to the user before the device confirms it. Held until one of three things happens: the next fresh poll confirms it matches the device's reported value, the next fresh poll still disagrees and the optimistic timeout has elapsed, or the coordinator's data stops being available at all — in which case it is dropped immediately rather than held or resurrected on recovery. An optimistic value is compared against a write request in its raw, pre-display form (the same domain the device speaks), never the display-formatted value.

### Data freshness

Whether an entity's current data actually comes from the most recent successful poll, as opposed to older data being served through a run of tolerated poll failures. Data is fresh only immediately after a real successful poll; it is not fresh while failures are being tolerated, even though entities keep showing their last-known values throughout. Decisions that would otherwise compare against possibly-outdated device state — confirming or expiring an optimistic value, deciding whether a write would be a no-op — must not act while data is not fresh, because the device may have changed in ways the current data hasn't caught up to yet.
