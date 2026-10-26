# CTRL-01 — controls rig (owner-directed prototype)

Michael asked for this round directly on 26 Oct 2026, following the parked
owner layout (#569, `docs/PACKAGES/WP04-OWNER-LAYOUT-2026-10-24.md`) and the
LADDER-01/02 latch prototypes (#431). It is **not a PM-issued hardware round and
not acceptance**. Nothing here qualifies a latch, a shell, a material or Guardrail 13.

The plan and drawings are the private canvas "CTRL-01 Controls Rig Plan"
(https://claude.ai/artifact/GaMoTPLGY164HNuQtNNfCV).

## Decisions Michael has made for this round

| | |
|---|---|
| Row (top to bottom on the device) | Record · gap (one key) · Play · FF · Rew · Stop · spring housing |
| Record | **Play gates Record** (approved): Record latches on the slide lock with the same P catch as every key, and a gate on Play stops it after 2 mm unless Play is down. A hook from Record directly onto Play was dropped: the same two faces would have to hold Record and let Play pass, pushed the same way |
| Rig housing | **Full 68 × 110 × 29 mm shell** (approved), split at mid-depth; the back half locates everything, the front half adds flat faces and clearance |
| Keys | One piece, no stem; P business end (1.2 mm hook, 45° ramp, flat ledge) unchanged, root carried to the inner end |
| Slide lock | Every latch thickened to the Stop version; prints flat so no latch root is a single layer line |
| Stop | Long even ramp from the inner end, then a flat that runs to the end of the key, beyond where the key travels |
| Solenoid | None |
| Files | Generator, tests and STLs committed here (approved) |

Still open: travel (5 mm proposed, was 6.2) and pitch (11 mm proposed).

## What exists so far

Only a single FF key, so Michael can see the shape: `stl/ctrl01-key-ff.stl`,
oriented to print cap-up (inner end on the bed, no supports). `key-preview.png`
shows it from three sides.

| File | SHA-256 |
|---|---|
| `stl/ctrl01-key-ff.stl` | `e6aefbfa9bc9346c0f72545c25befd20a72ba0b91e6d72c71effeb7568b39617` |

```sh
pip install cadquery pytest
python3 hardware/prototypes/ctrl-01/ctrl01.py                    # writes stl/
cd hardware/prototypes/ctrl-01 && python3 -m pytest -q test_ctrl01.py
```

## Gates and their negative controls

| Gate | Negative control (must fail) |
|---|---|
| One valid solid | — |
| No downward face steeper than 45° above the bed | the same key with an 80° ramp |
| The ledge in the hook lane faces the cap (the WP-04 root-cause orientation) | the key mirrored along the press axis |
| The hook lane inward of the ramp is empty, so a light touch can't shift the slide lock | the key with a block added in that lane |
| The business end is P (1.2 mm, 45°) | — |

Numbers that come from the printer, not this code: key slide 0.15 mm a side and
the pen-spring Ø5.0 pocket are from FIT-01; the 0.6–0.8 mm engagement loss is
from LADDER-01. Everything else is a proposal until it is printed.
