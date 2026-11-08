# Hardware workspace

Owner: Hardware Lead. Current design: [docs/DEVICE-DESIGN.md](../docs/DEVICE-DESIGN.md).
Current status: [docs/STATUS-HARDWARE.md](../docs/STATUS-HARDWARE.md). Hardware
revisions: [spec/hw/VERSION.md](../spec/hw/VERSION.md). Authority: [CLAUDE.md](../CLAUDE.md) §5.

| Surface | Purpose |
|---|---|
| prototypes/ctrl-01/ | Michael's current controls rig: latching keys, Record-on-Play latch, slide lock (owner prototype) |
| characterisation/ | Sustained-write and media-atomicity tools; the Teensy self-run power-cut method (`POWER-CUT-SELFRUN.md`, ADR-208), the superseded comparator rig (`ATOMICITY-RIG.md`, revision 2) and its revision-2 evidence schema (`ATOMICITY-SCHEMA-R2.md`) and the speaker-limit research (`SPEAKER-LIMIT.md`) |
| controls/ | Phase 3 control proposals: Rew/FF depth sensing, copy-button placement |
| measurements/ | Procedure and raw-data template for independent audit |
| fabrication_gate.py | Returns CLOSED/nonzero while safety qualification is missing |
| cad/, packets/wp04-01/, mech/, thermal/ | Earlier design (86 × 54 mm cartridge, solenoid transport). Kept as history; not the current design |
| sourcing/ | `PHASE3-BENCH.md`, the Phase 3 bench parts list for Michael's approval; the September 2026 research is superseded history |

Checks:
- stdlib: `make -C hardware thermal-check mech-check solenoid-test atomicity-test spec-check`
- gate control path: `make -C hardware fabrication-gate-test`
- CadQuery: `packet-check`, `shell-test`, and `pytest` in `prototypes/ctrl-01`

**No board fabrication or cell charging while `fabrication-gate` is CLOSED.** Green models,
CAD or regression checks do not clear it. Hardware doesn't edit engine/ or firmware/, and
every parts order needs Michael.
