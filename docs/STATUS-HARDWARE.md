# Hardware status

**Updated: 8 September 2026 · Owner: Hardware Lead.**

PR #18 is merged. Current hardware revisions/hashes are in spec/hw/VERSION.md.
WP04-01 rev 5 contains 19 objects, four lids, deliberate blind controls, and an
explicit SUPPORTS OFF card. CAD rebuild/geometry, printable-packet/thermal/atomicity
tooling, and KiCad workflow jobs passed at 218b3b123781064c32b234f44dc165ccc5c72fa5.
No schematic/board exists yet; a green KiCad job is not ERC/DRC of a nonexistent design.

| Area | Evidence | Remaining work |
|---|---|---|
| Fabrication gate | Make target now propagates CLOSED/nonzero; isolated accepted/qualified fixture can open; regression runs in CI | IR-018-18 response awaits independent disposition; real gate remains CLOSED |
| Solenoid | Provisional analysis, same-edge admission removes reviewed handoff race | IR-018-16: bind exact HC221 part/timing at 3.3 V, intended R/C and temperature; no assumed guarantee |
| Safety | Three IR-015 responses exist | Independent charger, sustained coil-power and transient-junction acceptance; no fabrication or cell charging |
| Cartridge clasp | Code-defined geometry and estimate tables; zero closed-strain geometry checks | Printed fit, retention, creep/drop and independent measurement audit |
| Media | Atomicity judge has 43 checks and negative controls | Real rig/firmware/protocol traces, ≥1,000 qualifying cuts per exact SKU/revision; no atomicity PASS yet |
| WP-05 | 64 GB cart withdrawn per Michael | Source cheap small cards and review bench exact parts before any purchase |

The local stdlib checks were reproduced; CAD validation was established by GitHub
CI, not by claiming CadQuery existed in this scratch environment.
Run make -C hardware fabrication-gate before any fabrication/charging decision.
Five blockers currently remain. Green regression/thermal checks are not qualification.

Michael owns purchases and physical trials. Old ~$115/$152 cart estimates are not
current quotes or approvals. Latest priorities are in [the round brief](REVIEW/README.md).
