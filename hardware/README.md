# Hardware workspace

> **PARKED through Phase 2 (#309, ADR-160).** No PM-issued hardware work until Phase 3 opens or
> Michael requests it. Start a resume from [the roadmap's parked hardware PR record](../docs/PACKAGES/README.md#parked-hardware-pr-record).
> The WP04-01 packet (`packets/wp04-01/`), the `packet-wp04` Make rules and the CAD generators
> still encode the retired library-printer route (STL only, 6 h, one spool); Michael's A1 Mini
> (nominal 180 × 180 × 180 mm) is the default printer. `packets/wp04-01/plate-map.md` also wrongly
> calls its 250 × 210 layout A1 Mini-sized. Regenerating for the A1 Mini is the first resume task.
> The card plan is settled: three PNY 64 GB V30 cards are bought (CLAUDE.md §5); the withdrawn
> "64 GB cart" below refers to the earlier unpurchased cart, not to those cards.

Owner: Hardware Lead. Current [status](../docs/STATUS-HARDWARE.md), authority in
[CLAUDE.md](../CLAUDE.md), hardware revisions in [spec/hw/VERSION.md](../spec/hw/VERSION.md).

| Surface | Purpose |
|---|---|
| cad/transport/ and packets/wp04-01/ | Reproducible blind mechanism/clasp print packet |
| cad/cartridge/ and mech/ | Cartridge geometry and generated estimates |
| thermal/ | Charger, transient and solenoid models; estimates are not qualification |
| characterisation/ | Sustained-write and media-atomicity tools |
| measurements/ | Procedure and raw-data template for independent audit |
| fabrication_gate.py | CLOSED/nonzero while safety acceptance/qualification is missing |

Use make -C hardware thermal-check mech-check solenoid-test atomicity-test spec-check
for stdlib checks; fabrication-gate-test exercises the safety gate’s control path.
CAD targets packet-check, shell-test and packet-duplicates need CadQuery.
The GitHub hardware workflow supplies Python 3.11 and KiCad 8; check your local
environment rather than inheriting a previous agent’s installed-tool claims.
ERC/DRC has no actual design to check until schematic/board files exist.

**No board fabrication or cell charging while fabrication-gate is CLOSED.**
Green models, CAD and regression checks do not clear that hold.

Hardware owns versioned spec/hw changes and notifies Software of changed interfaces.
Product safety limits remain PM-owned in spec/acceptance.md. Do not edit engine/
or firmware/. Every parts order needs Michael; the old 64 GB cart is withdrawn.
