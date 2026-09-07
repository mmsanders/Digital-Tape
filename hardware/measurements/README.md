# hardware/measurements — audit-ready records

**Why this exists.** PM Decisions 006 §5 changed what "done" means for the safety measurements:
the SPL cap and the thermal limits are **witnessed by Michael and independently audited by the
Verification Lead** — from the method and the raw data, not from being in the room.

That is a real constraint on format, not a formality. An auditor who was not present cannot see
which thermocouple was where, cannot tell a settled reading from a drifting one, and cannot
distinguish a 0.2 K margin from a 0.2 K instrument error. **Everything they need has to be in
the record or the audit cannot happen** — and the person who has to notice a missing field is
the person writing it, weeks before anyone asks.

So the format is fixed in `TEMPLATE.md` and copied per session.

## Which measurements

| Package | Measurement | Why it needs an audit record |
|---|---|---|
| **WP-37** | Thermal validation and abuse | Safety limit, and it replaces every `EST` in `spec/hw/thermal-budget.md` |
| **WP-19** | The 85 dB SPL cap | Safety limit. The users are children (guardrail 11) |
| **WP-27** | Layout, DFM, assembly BOM | Different in kind — the "raw data" is the fab's DFM report and the stackup, not readings. Sections 3 and 5 adapt; the rest applies |
| **WP-24** | S-4, the 30 N pinch that must not open the cartridge | Safety-adjacent: a loose microSD is a choking hazard (ADR-105) |
| **WP-05** | Media atomicity, 1 000 power cuts per SKU | Not safety, but the format's central physical assumption. `characterisation/` already emits a machine-readable equivalent |

## The rule that makes it worth the effort

**Nobody grades their own homework** (CLAUDE.md §2). For WP-37 and WP-19 the person proposing
the criterion, running the test and reporting the result would otherwise all be me. Michael
witnessing splits one of those off; the Verification Lead auditing splits another. This template
is what makes the second split possible at a distance.

**A record that would read identically whether the measurement went well or badly is not a
record.** Sections 8 and 9 exist to prevent exactly that, and they are the two most likely to be
left thin.
