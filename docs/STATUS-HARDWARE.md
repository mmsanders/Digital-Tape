# Hardware status

**Updated: 20 September 2026 · Owner: PM disposition of submitted Hardware evidence;
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
| Cartridge clasp | PR #92 head `0943571...` retains rev-6 WP-24 and WP-04 plates inside the nominal `180 x 180 x 180 mm` envelope with 5 mm XY margins, Z ≤175 mm and fail-closed vertex checks. PM reproduced packet identity/validation | Existing library test remains configured for the library. New work defaults to the A1 Mini; usable edges/process and every physical result remain unproved. Record printer, material, profile, fit, retention, creep/drop and independent measurement audit |
| Media | Atomicity judge has 43 checks and negative controls | Real rig/firmware/protocol traces, ≥1,000 qualifying cuts per exact SKU/revision; no atomicity PASS yet |
| WP-05 | PR #87 head `e520c2c...` is an exact self-audited repair of `P1-R21-V01`: 26 retained controls cover 30 top-level and 35 nested fields; the writer and five legacy records are unchanged | Independent Verification re-audits the exact repaired method before any acquisition. No schema-2 physical record exists; identity, attribution, atomicity, filled-condition qualification and end-to-end copy remain open |
| Ruggedization | PR #92 head `0943571...` transcribes CS-1–CS-5 for the method and passes 23 retained sharp controls, 51 independently restated values and 42 field-specific red mutations. The two-plate packet bytes are unchanged | Wait held for independent audit of the exact head. RG-8–RG-10, apparatus, tool and regulatory-method gaps remain. No print, physical or live-cell destructive test and no compliance claim |

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

The source-generated rev-6 split packet implements the PM direction: every WP-24 base
and matching lid share one plate; the WP-04 experiment occupies the second; 5 mm XY
margins, Z ≤175 mm, blindness, full sweeps, controls, supports-off instructions and
fail-closed bounds checks are retained. This is not permission to print or evidence
that the advertised edge is usable.

Michael reports a sensitive food-preparation scale, normal screwdrivers and sockets,
and likely access to a soldering iron. These are availability facts only. Hardware
must state the minimum published resolution, accuracy/calibration and capacity before
using the scale, and must keep torque, displacement, force, sharp-test, audio and
reference-standard gaps explicit. No purchase request or owner action is blocking the
current source/tool/packet work.

Michael reports an A1 Mini test print in progress and expects the library to be
available Monday. Do not reconfigure the existing library test for the A1 Mini.
Default new prints to the A1 Mini and retain the library for oversized PLA. Current
owned filament is one spool of white Bambu PLA Basic. Hardware must recommend the
minimum additional material, printer-proven brand/product/profile and drying/storage/
nozzle constraints before Michael decides whether to buy anything. PETG and TPU are
candidate needs, not requirements or purchase approvals. Every result is bound to its
actual printer/material/profile; an owner-reported print is not acceptance evidence.

PM's [P1-R21 primary-source note](REVIEW/P1-R21-CPSC-PRIMARY-SOURCE-NOTE.md)
authenticates the current eCFR banner, official Probe B drawings, edge-test tape and
apparatus, exemptions and applicable over-36-through-96-month use/abuse inputs.
Hardware bound and controlled those inputs at held PR #92 head `0943571...`; PM's
retrieval and Hardware's transcription are not independent method acceptance or a
regulatory-compliance claim.
