# Hardware status

**Updated: 19 September 2026 · Owner: PM disposition of submitted Hardware evidence;
Hardware retains engineering control.**

PR #18 is merged. PR #47 is merged at
`8d9e8bdffc245d797702a2b3a461348672b0644a`. Current hardware revisions/hashes
are in spec/hw/VERSION.md.
WP04-01 rev 5 contains 19 objects, four lids, deliberate blind controls, and an
explicit SUPPORTS OFF card. CAD rebuild/geometry, printable-packet/thermal/atomicity
tooling, and KiCad workflow jobs passed at 218b3b123781064c32b234f44dc165ccc5c72fa5.
No schematic/board exists yet; a green KiCad job is not ERC/DRC of a nonexistent design.

| Area | Evidence | Remaining work |
|---|---|---|
| Fabrication gate | Regression reproduced; the real gate remains **CLOSED/nonzero with five blockers** | No board fabrication or cell charging |
| Solenoid | TI `CD74HC221E`/`CD74HC221M96` bound to the 3.3 V rail; timing model remains **PROVISIONAL**. The supply-envelope criterion now has a **retained targeted control** in `hardware/thermal/test_solenoid.py` and its own `--mutate-supply` mode, both run by `make -C hardware solenoid-test` | IR-018-16 guaranteed 3.3 V pulse-width limit or independently reviewed bench evidence; placeholder pulse still depends on WP-04 |
| Safety | Three IR-015 responses indexed in PR #47; acceptance fields unsigned | Independent charger, sustained coil-power and transient-junction acceptance; no fabrication or cell charging |
| Cartridge clasp | Rev-5 library plate did not produce a returned result. Michael has bought an A1 Mini and is setting it up; the printer/process is not yet characterized | Rebase the packet on the owned-printer process, then record printed fit, retention, creep/drop and independent measurement audit |
| Media | Atomicity judge has 43 checks and negative controls | Real rig/firmware/protocol traces, ≥1,000 qualifying cuts per exact SKU/revision; no atomicity PASS yet |
| WP-05 | Verification independently reproduced all 95 stored rate values and the exact 15.34 MB/s onn failure plus 25.41–27.36 MB/s PNY passes | Correct the tool to retain primitive returned-byte/time/final-size and before/after capacity/free/occupancy evidence; derive summaries without trusting stored means; then seek a new physical rerun. Identity, attribution, atomicity and end-to-end copy remain open; no card is qualified |
| Ruggedization | Draft PR #92 head `7b80631...` is directionally useful, but Verification rejected it as an executable/auditable method | Resolve findings B01–B06: exact drop/shake/tumble mechanics, calibrated measurements and thresholds, measured red controls, sourced internal safety procedures, stage/restart/quarantine rules and quantitative printer-process controls. No physical or live-cell destructive test |

PR #47's spec/thermal/mechanical/solenoid/atomicity/fabrication regressions were
reproduced by PM; CadQuery was not available in the lead environment and was not
claimed as passing there. The supply-envelope inequality's control is now
**retained rather than one-off** (P1-R3-HW): injecting a 4.5–5.5 V part at the 3.3 V rail must
add exactly one failure, it must be the supply-envelope one, its message must name both the
envelope and the rail, and the control must stay specific while an unrelated criterion is also
failing. `--mutate-supply` deletes only that inequality and requires the suite to go red on
those checks; a genuine four-line source deletion was also confirmed to produce exit 1.
This is evidence hardening only — **no acceptance, no measurement, and no gate change.**
Run make -C hardware fabrication-gate before any fabrication/charging decision.
Five blockers currently remain. Green regression/thermal checks are not qualification.

Michael owns purchases and physical trials. The PNY cards and A1 Mini are purchased
facts, not qualification or permission for another purchase. Old ~$115/$152 cart
estimates are not current quotes or approvals. Active assignments live only in
[Hardware's issue queue](https://github.com/mmsanders/Digital-Tape/issues?q=is%3Aissue%20is%3Aopen%20label%3Ahardware-lead).

PM approves a split-plate direction for the A1 Mini, contingent on recording its
actual usable build volume: keep every WP-24 base with its matching lid on one plate
and move the WP-04 button experiment to a second plate. Preserve blindness, the full
sweeps and controls, regenerate from source and issue a new packet revision. This is
not permission to print. Hardware now owns method corrections only; it must stop
before machine-bound rebuild or physical execution if usable volume is unavailable.
