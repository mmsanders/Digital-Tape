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
| Cartridge clasp | Rev-5 library plate did not produce a returned result. Michael confirms the A1 Mini's advertised nominal `180 x 180 x 180 mm` volume; usable edges and process remain uncharacterized | Regenerate the approved two-plate source packet inside a stated conservative margin with automated bounds controls; do not print until separately authorized, then record fit, retention, creep/drop and independent measurement audit |
| Media | Atomicity judge has 43 checks and negative controls | Real rig/firmware/protocol traces, ≥1,000 qualifying cuts per exact SKU/revision; no atomicity PASS yet |
| WP-05 | Verification independently reproduced all 95 legacy stored rates. Its audit at verifier `d6c8c99...` blocks PR #87 schema 2: ordered per-write primitives are not retained and thirteen corrupted/missing primitive variants escape analysis. The actual unchanged legacy ancestor is `c0e6a83ae44c...` | Hardware repairs V01/V02 with a closed, ordered schema and retained controls, without a physical run. Verification re-audits the corrected exact head before acquisition. Identity, attribution, atomicity, filled-condition qualification and end-to-end copy remain open; no card is qualified |
| Ruggedization | Draft PR #92 head `faf8ed4...` passes 21 internal protocol/sharp controls, but its source record remains incomplete. Owner confirms only the printer's advertised nominal envelope and has a food scale, ordinary hand tools and a likely soldering iron | Bind the method directly to current official 16 CFR 1500.48/.49 text/figures and crosswalk applicable 1500.50/.53 use/abuse rules; regenerate the bounded two-plate packet. Record tool minimums and gaps. No print, physical or live-cell destructive test |

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

PM approves a source-generated split-plate direction inside the owner-confirmed
nominal `180 x 180 x 180 mm` envelope: use a stated conservative edge margin, keep
every WP-24 base with its matching lid on one plate and move the WP-04 button
experiment to a second plate. Preserve blindness, full sweeps and controls, supports-
off instructions, and fail-closed bounds checks. This is not permission to print or
evidence that the full advertised edge is usable.

Michael reports a sensitive food-preparation scale, normal screwdrivers and sockets,
and likely access to a soldering iron. These are availability facts only. Hardware
must state the minimum published resolution, accuracy/calibration and capacity before
using the scale, and must keep torque, displacement, force, sharp-test, audio and
reference-standard gaps explicit. No purchase request or owner action is blocking the
current source/tool/packet work.
