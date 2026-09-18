# Hardware status

**Updated: 18 September 2026 · Owner: PM disposition of submitted Hardware evidence;
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
| Cartridge clasp | Rev-5 library plate did not produce a returned result — recorded as inconclusive. `cartridge-shell.md` is at **rev 0.3**: the library/no-printer premise is void, PETG is selectable, PLA retained as the conservative case, no number moved | **The rev-5 plate does not fit a 180 mm bed** (it is 228 mm). Rebuild needs the confirmed build volume and PM's approval of the split; then printed fit, retention, creep/drop and independent audit |
| Media | Atomicity judge has 43 checks and negative controls | Real rig/firmware/protocol traces, ≥1,000 qualifying cuts per exact SKU/revision; no atomicity PASS yet |
| WP-05 | PR #87 submits five raw sustained-write runs: three PNY 64 GB V30 samples clear the 23.3 MB/s screening bar at 25.41–27.36 MB/s worst-window; the onn V10 negative control fails at 15.34 MB/s. One PNY run is at 80% fill | Keep A-2's filled condition. Exact PNY part/revision/CID, independent audit, reader/card attribution, atomicity and production end-to-end copy remain open; no card is qualified |
| Ruggedization | **`spec/hw/ruggedization.md` rev 0.1 proposed**: load path, 18-mode failure/mitigation matrix each with a detection check, and a numeric staged protocol — 1.0 m onto declared concrete, 12 orientations cumulative, n=2, metronome shake plus tumble, two negative controls, inert cell throughout | PM approval of the numbers and Verification review of the criteria **before any trial**. Loaded mass is an estimate, not a measurement. Stage 2 is gated on printer calibration coupons |
| Printing | Michael owns an A1 Mini. Process baseline, calibration/repeatability coupons K-1..K-6 and the per-part process record are planned in `hardware/printing/owned-printer-baseline.md` | Machine facts confirmed from the machine (build volume, nozzle, AMS, slicer version); K-1/K-2 run and reviewed. **Nothing printed, nothing measured, nothing qualified** |

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

**The spec/hw manifest gate now has retained controls of its own**
(`hardware/test_spec_manifest.py`, run by `make -C hardware spec-check`). Adding
`ruggedization.md` to the manifest was a hand edit to a tuple, and one deleted line would have
put it back outside the gate while the gate still printed OK — demonstrated, then closed. Six
controls, including the file-list check that catches exactly that deletion.

Michael owns purchases and physical trials. The PNY cards and A1 Mini are purchased
facts, not qualification or permission for another purchase. Old ~$115/$152 cart
estimates are not current quotes or approvals. Active assignments live only in
[Hardware's issue queue](https://github.com/mmsanders/Digital-Tape/issues?q=is%3Aissue%20is%3Aopen%20label%3Ahardware-lead).
