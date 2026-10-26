# CTRL-01 — controls rig (owner-directed prototype)

Michael asked for this round directly on 26 Oct 2026. It follows the parked
owner layout (#569, `docs/PACKAGES/WP04-OWNER-LAYOUT-2026-10-24.md`) and the
LADDER-01/02 latch prototypes (#431). It is **not a PM-issued hardware round and
not acceptance**. Nothing here qualifies a latch, a shell, a material or Guardrail 13.

The plan and drawings are the private canvas "CTRL-01 Controls Rig Plan"
(https://claude.ai/artifact/GaMoTPLGY164HNuQtNNfCV).

## Decisions Michael has made for this round

| | |
|---|---|
| Row (top to bottom on the device) | Record · gap (one key) · Play · FF · Rew · Stop · spring housing |
| Record | **Play gates Record** (approved). Record latches on the slide lock with the same catch as every key, and a gate on Play stops it after 2 mm unless Play is down. A hook from Record directly onto Play was dropped: the same two faces would have to hold Record and let Play pass, pushed the same way |
| Rig housing | **Full 68 × 110 × 29 mm shell** (approved), split at mid-depth; the back half locates everything, the front half adds flat faces and clearance |
| Key | **Starts from the LADDER-02 P key exactly** (26 Oct): body, rails, spring groove and tooth unchanged. Where the stem began, the body carries on up without the rails, inset 1.5 mm a side, so a flat shoulder all round stops on the shell. At the old installed cap height there is a one-piece cap whose flat underside lands on the shell at full press |
| Catch | The old P catch for now. Michael will talk through a new one once the body is right |
| Slide lock | Every latch thickened to the Stop version; prints flat so no latch root is a single layer line |
| Stop | Long even ramp, then a flat that runs to the end of the key, beyond where the key travels |
| Solenoid | None |
| Files | Generator, tests and STLs committed here (approved) |

Still open: travel and pitch for the device row. The rig keeps LADDER's 6.2 mm travel for now.

## Source

The LADDER-01/02 generator was never committed. Michael supplied his
`latch-rig.zip` on 26 Oct (SHA-256
`e49c6a49e0e13cf72b0f16365bee634df4ccb2aae97272ab5d4cb9f25882689b`). The key
constants in `ctrl01.py` are copied from its `rig.py`, with FIT-01's spring and
boss values. `reference/ladder02-key-P-2.stl` is the key Michael printed, kept
as the check that the rebuild is exact.

## What exists so far

One key: `print/ctrl01-key-P.stl`, modelled and exported upright as it prints.
`key-preview.png` shows it beside the LADDER-02 key.

| File | SHA-256 |
|---|---|
| `print/ctrl01-key-P.stl` | `1cbef7ae97d1ec052e3d85a1ba02c1dd93eabc3297f4fc9ed0abd475c5704c51` |
| `reference/ladder02-key-P-2.stl` | `a3e0dafd342506e78b6ed5b2aff249397ccee33154ced8ec70c394ce8a5ece0a` |

**Print it upright with support under the cap only.** The cap overhangs the
extension by 4 mm all round, and its underside is flat on purpose because it is
the down-stop. Everything else prints as LADDER did.

```sh
pip install cadquery pytest
python3 hardware/prototypes/ctrl-01/ctrl01.py                    # writes print/
cd hardware/prototypes/ctrl-01 && python3 -m pytest -q test_ctrl01.py
```

## Gates and their negative controls

| Gate | Negative control (must fail) |
|---|---|
| One valid solid | — |
| The rebuilt LADDER key matches Michael's printed `key-P-2.stl` to 0.02 mm | the L key (h = 0.9) |
| Below the shoulder the new key is identical to the old one | the tooth reversed (the WP-04 failure) |
| The shoulder reaches at least 1.0 mm past the shell aperture, per side (1.5 inset − 0.4 clearance = 1.1) | a 0.8 mm inset |
| The cap underside lands on the shell at full press (6.2 mm travel) | the cap moved 1 mm |
| No downward face steeper than 45° except the declared ones (groove roof, cap underside, the engraved letter) | the tooth reversed |
