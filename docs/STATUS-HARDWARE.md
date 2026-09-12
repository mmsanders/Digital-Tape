# Hardware status

**Updated: 12 September 2026 · Owner: Hardware Lead.**

PR #18 is merged. Current hardware revisions/hashes are in spec/hw/VERSION.md.
WP04-01 rev 5 contains 19 objects, four lids, deliberate blind controls, and an
explicit SUPPORTS OFF card. CAD rebuild/geometry, printable-packet/thermal/atomicity
tooling, and KiCad workflow jobs passed at 218b3b123781064c32b234f44dc165ccc5c72fa5.
No schematic/board exists yet; a green KiCad job is not ERC/DRC of a nonexistent design.

| Area | Evidence | Remaining work |
|---|---|---|
| Fabrication gate | Make target now propagates CLOSED/nonzero; isolated accepted/qualified fixture can open; regression runs in CI | IR-018-18 response awaits independent disposition; real gate remains CLOSED |
| Solenoid | Provisional analysis, same-edge admission removes reviewed handoff race. **Part bound 12 Sep**: TI `CD74HC221E`/`CD74HC221M96`, 2–6 V, covering the 3.3 V rail, dated distributor price/stock | IR-018-16 **narrowed, not closed**: the guaranteed pulse-width table at 3.3 V is still unread (datasheet hosts blocked). Verdict stays PROVISIONAL. Bench method proposed, needs no coil/cell/board |
| Safety | Three IR-015 responses exist; **indexed for review** in `hardware/measurements/IR-015-evidence-index.md` with assumptions, missing evidence and proposed instruments, acceptance fields left unsigned | Independent charger, sustained coil-power and transient-junction acceptance; no fabrication or cell charging |
| Cartridge clasp | Code-defined geometry and estimate tables; zero closed-strain geometry checks | Printed fit, retention, creep/drop and independent measurement audit. **Rev-5 plate reported in printing 12 Sep, not yet in hand; `RESULTS.md` is still blank** |
| Media | Atomicity judge has 43 checks and negative controls | Real rig/firmware/protocol traces, ≥1,000 qualifying cuts per exact SKU/revision; no atomicity PASS yet |
| WP-05 | **No cheap 4 GB V30 part exists to buy** (12 Sep): the only 4 GB microSD at the one reachable distributor is industrial SLC at $167.81 with no V30 marking. **Michael decided 12 Sep**: the no-64GB rule was cost-based and no longer excludes the 64 GB V30 part; buy a V30 arm and a cheap U3 arm at n = 2 and compare; all other cards off the list; revision-drift risk accepted | Michael orders from `hardware/sourcing/SHOPPING-LIST.md` (one open choice: 2 × 32 GB U3 at a real qty-2 break, or 10 × 16 GB U3). **PM must reconcile** CLAUDE.md §5, WP-05 and ORDER-1A, which still say no 64 GB and six SKUs. **Reader adequacy unknown — WP-05 A-4 invalidates results taken at the reader's ceiling** |

The local stdlib checks were reproduced; CAD validation was established by GitHub
CI, not by claiming CadQuery existed in this scratch environment. Reproduced 12 September
at main `40507bf`: spec-check, thermal-check, mech-check, solenoid-test, atomicity-test and
fabrication-gate-test all pass; `packet-check`, `shell-test` and `packet-duplicates` were
NOT RUN because CadQuery is absent here, and a missing dependency is not a passing test.

**Vendor access changed and the old blanket claim is now wrong.** `www.digikey.com` is
reachable from the Hardware environment; manufacturer sites, mirrored datasheet PDFs and
consumer retailers are not. Distributor parts can be sourced with dated price and stock;
datasheets and retail card prices cannot. Full table in `hardware/sourcing/2026-09-12-parts.md`.
Run make -C hardware fabrication-gate before any fabrication/charging decision.
Five blockers currently remain. Green regression/thermal checks are not qualification.

Michael owns purchases and physical trials. Old ~$115/$152 cart estimates are not
current quotes or approvals. Active assignments live only in
[Hardware's issue queue](https://github.com/mmsanders/Digital-Tape/issues?q=is%3Aissue%20is%3Aopen%20label%3Ahardware-lead).
