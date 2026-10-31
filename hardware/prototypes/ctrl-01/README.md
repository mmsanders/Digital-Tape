# CTRL-01 — controls rig (owner-directed prototype)

Michael asked for this round directly (26 Oct–1 Nov 2026). It follows the parked owner
layout (#569, `docs/PACKAGES/WP04-OWNER-LAYOUT-2026-10-24.md`) and the LADDER-01/02
latch prototypes (#431). It is **not a PM-issued hardware round and not acceptance**.
Nothing here qualifies a latch, a shell, a material, a card slot or Guardrail 13.

## This round (1 Nov): the Play/Record rig

Michael scaled the test back to the one thing that has not worked yet: Record latching
to Play. The rig is a 26 × 80 × 29 mm housing holding **Record, Play and Stop only**,
everything inside **at full device scale**: the block keys, the comb, the slide lock and
the Record latch slider are the same parts the full device would use. All of it prints
on one plate.

Earlier rounds in this folder, and their STLs, are in Git history: the full 68 × 110
case with five keys and six card slots (26–31 Oct, last STLs at commit 6e82cef) and the
full-device block-key layout (commit 50eaa44).

## Decisions Michael has made

| | |
|---|---|
| Keys | **Blocks, no caps** (1 Nov): 12.4 (row) × 16 (depth), running straight out of the shell, 1 mm round on the edges, symbol engraved. **4 mm proud, 4 mm travel.** A 1 mm flange inside the wall stops a key at rest; at full press its block lands on the comb |
| Row | Record on its own, a 10.6 mm gap, then Play and Stop side by side in one opening with a 0.6 mm gap (13 mm pitch) |
| Play symbol | Turned round (31 Oct): the triangle points toward the front face |
| Catch | P business end (1.2 mm hook, 45° ramp, flat ledge), lines run on to the edge of the key face. Play's sits 0.4 mm lower so it latches sooner |
| Stop | No ledge: one even ramp, then a flat to the shoulder. **38°** from the press direction: 4 mm of travel is too short for the 30° Michael chose to shift the lock 2.1 mm |
| Record | **Latches to Play, never to the slide lock** (31 Oct). Record has no catch. Play's diagonal rail drives a latch slider (both ways) carrying a hook. Play up: the hook is out of Record's way, so Record alone goes down and springs back (accepted). Play latched: Record's toe ramps the hook aside and the hook drops in behind it. Stop lifts Play, which pulls the hook out, and Record comes up too |
| Latch slider | **Long, between two long guides** (1 Nov, after Michael asked about an extension onto another ledge): a 35 mm plate from Record's lane past Play's rail into Stop's lane, 13.3 mm wide, its inner edge on a guide rail in the front half and its outer edge on the partition, so it cannot turn. The hook's holding face and the back of Record's toe **lean 25°**, so Record's spring pushes the slider toward release instead of against it |
| Slide lock | Latches with LADDER's Stop-tab shape (top rises 1.7 mm), now 5.5 mm long on the 13 mm pitch. Body 0.1 mm slimmer each side (Michael shaved the sides to fit, 31 Oct). Pawls for Play and Stop only |
| Key comb | Separate part (30 Oct): keys slide into it on the bench, it drops in over the lock |
| Clasp | Snap ridges 0.45 mm (were 0.25: the halves pulled apart too easily), 10 mm long, seven of them |
| Material | PLA (Michael, 1 Nov: PETG-HF not this time) |
| Solenoid | None |

## How it moves

Device frame: X in from the key side, Y down from the top, Z back from the front; seam at Z 14.5.

| | |
|---|---|
| Keys | Record Y 16, Play Y 41, Stop Y 54; body 12 × 7 × 9 with 2.5 × 1.0 rails; underside at X 12.5 at rest |
| Springs | Pencil springs (14 free / about 4 solid). Key springs from the key's groove to a boss on the comb's spine, 9 mm at rest, 5 mm pressed. One lock spring, 11 mm at rest |
| Guidance | Comb fins from X 7.5 to the spine (X 19.3), rail tunnels 0.15 mm a side; the blocks run in the shell openings (0.2 mm a side) and land on the fins |
| Slide lock | X 7.1–12.9, Z 20.5–26.35, Y 32.7–65.4 plus spring boss, in a back-half channel with 0.35 mm snap lips |
| Latch slider | X 5.8–19.1, Z 2.7–5.6 (floor 0.8 mm where Record's toe passes over it), Y 20.8–56 at rest, moving +Y with Play one for one |

From the simulations (`mech.kinematics()`, `mech.record_latch()`):

| | |
|---|---|
| Play | the lock first moves at 1.0 mm, latches at 2.8 mm, 1.2 mm to spare |
| Stop | moves the lock from 0.5 mm, 2.1 mm by 3.2 mm, never latches |
| Record alone | meets nothing |
| Play pressed, Record up | the hook passes in front of the toe without touching it |
| Record after Play | ramps the hook aside, nudging Play 0.9 mm deeper (of 1.2), is held at 3.25 mm (0.75 mm overtravel); hook over toe 0.9 mm |
| Stop while recording | Record is free once Play is back within 0.7 mm of the top |

**Why the slider should come back.** It is driven both ways: Play's rail runs in a
closed slot, so Play coming up pulls the slider back; it does not wait on friction. At
release both springs push it back (Play's through the rail, Record's through the 25° lean,
which is steeper than PLA-on-PLA friction of about 0.3), against only the light friction of
the long guides: roughly four times the force needed, where the 31 Oct slider had about 1.2.

## Printing (A1 Mini, PLA)

`ctrl01-plate-rig.stl`, everything on one plate. Set per object:

| Part | Pose | Settings |
|---|---|---|
| Front and back halves | outer faces down | 3 walls, 4 top/bottom, 15% infill. No supports: the key openings split at the seam, so nothing is bridged |
| Comb | spine down | 4 walls, 40% infill, no supports |
| Slide lock | back face down | 4 walls, 40%, no supports |
| Latch slider | floor down | 4 walls, 40%, no supports |
| Record, Play, Stop, spare Play | upright | 4 walls, 40%; **tree supports from the plate under the blocks only** (30° threshold) |

## Assembly

The check `assembly.assembly_sequence()` slides every part in along these paths, in this order.

1. **Keys into the comb, on the bench:** each slides in from the comb's outer end, block last.
2. **Slide lock:** back half on the table, inside up. Snap the lock into its channel; pencil spring on its bottom boss, into the housing.
3. **Comb:** lower it, keys and all, into the back half over the lock, each block into its half-opening.
4. **Latch slider:** drop it onto Play's rail, floor toward the front, hook toward Record.
5. **Key springs:** squeeze each with tweezers and slip it between the key's post and its boss on the spine.
6. Press Stop to free anything that latched.
7. **Front half** on (its guide rail goes beside the slider's inner edge); press round the rim until the ridges click. Coin notch on the right side to open.

## What to try

- **Record**, 10 each: alone (goes down, springs back, nothing else moves); Play then Record (both stay down); hold Record fully down, then Play; Stop while recording (both come up, every time); press Record hard while recording.
- **The slider:** does it stay square, and come back by itself when Play comes up, with and without Record down?
- **Play and Stop:** 20 presses each; does Play latch every time, does Stop free it?
- **Keys:** the 4 mm proud and 4 mm travel; the blocks in their openings (rattle, rub); the symbols.
- **Clasp:** does it hold now; open and close 10 times.
- Anything that breaks.

## Code

| File | |
|---|---|
| `layout.py` | every shared number (rig size, row and bay at the top) |
| `mech.py` | keys, catch and pawl outlines, latch simulation, slide lock, latch slider and its simulation |
| `shell.py` | halves, tongue/groove/ridges, the bay, the comb |
| `cards.py` | card slots (none on the rig) and the 31 Oct portrait cards |
| `assembly.py` | parts placed in every state; interference check; build order and paths in |
| `build.py` | print poses, the plate, STLs |
| `test_rig.py` | gates below |
| `key_v1.py`, `test_key_v1.py` | the full-size LADDER-based key from 26 Oct (superseded; outputs in `print/v1/`) |

```sh
pip install cadquery pytest shapely
python3 hardware/prototypes/ctrl-01/build.py                 # writes print/
cd hardware/prototypes/ctrl-01 && python3 -m pytest -q        # about a minute
```

## Gates and their negative controls

| Gate | Negative control (must fail) |
|---|---|
| Play latches on the flat ledge with ≥ 0.8 mm overtravel | the catch reversed (the WP-04 failure) |
| Stop never latches and shifts the lock ≥ 2.1 mm by 3.2 mm | a key with a ledge |
| A pawl, anywhere in the lock's travel, never meets the next key | 6 mm of lock travel |
| Every latch rises ≥ 1.5 mm toward its far end (the Stop-tab shape) | the flat-topped latch first printed |
| No two parts overlap: at rest, Play and Stop at full press and peak lock push and at 1/2/3/4 mm, Record alone, Record pushing past the hook, Record held, Stop releasing both (24 states) | a key moved 0.4 mm off its slot |
| Record latch: alone Record meets nothing; Play brings the hook past the resting toe; Record ramps the hook aside (slope ≤ 1.5, Play nudged ≤ 1.0 mm) and is held with ≥ 0.5 mm overtravel; Record is free before Play is fully up (≥ 0.6 mm) | a toe without its chamfer stalls; a hook left in Record's lane catches Record alone; a hook too wide never lets go |
| The holding face leans more than PLA friction (tan ≥ 0.35), so Record helps the slider back | a square holding face |
| The slider is at least twice as long as it is wide, with a guide on each edge | a slider cut short at the slot, like 31 Oct's |
| Play's latched depth is the depth the latch is built for (2.8 mm) | — |
| Record never comes within 0.5 mm of the slide lock | — |
| Every part has a clear straight path in, in build order; only the lock's snap lips are allowed in the way | the 28 Oct back half with the comb built in: neither the lock nor a key gets in |
| Record's web and Play's arm join their key across ≥ 20 mm² (24 and 42) | an arm hanging on a 0.01 mm strip (the 27 Oct defect) |
| Every printed part is one valid solid; keys print upright with support only under the block; lock, slider, comb and cards need none | a reversed catch |
| The plate fits the 180 × 180 bed | — |
| The snap card's halves close without overlap into a full 42 × 36 × 7 card | a bead bigger than its relief |

Numbers from the printer, not this code: key slide 0.15 mm a side, spring holes and
bosses (FIT-01); the P preference (LADDER-01/02). The simulations are geometry only;
LADDER-01 saw 0.6–0.8 mm of engagement lost on the real printer, which is why the hook
now overlaps the toe by 0.9 mm.

## Source

The LADDER-01/02 generator was never committed. Michael supplied his
`latch-rig.zip` on 26 Oct (SHA-256
`e49c6a49e0e13cf72b0f16365bee634df4ccb2aae97272ab5d4cb9f25882689b`);
`reference/ladder02-key-P-2.stl` is the key he printed (SHA-256
`a3e0dafd342506e78b6ed5b2aff249397ccee33154ced8ec70c394ce8a5ece0a`), kept as
the check that `key_v1.py` rebuilt it exactly.

## Files

| File | SHA-256 |
|---|---|
| `print/ctrl01-plate-rig.stl` | `8236c1baf468fcd934c566df7288543dd2a8acbbcd1855e1ea469ca105e14dd3` |
| `print/ctrl01-back.stl` | `668f62f8db252f6ea6132db745ee3957e5d3b57b48d91a6e07508ed4a1e6e30d` |
| `print/ctrl01-bar.stl` | `eff52f354f070fcd8b771554884902e543fb832c8f22bdb1973599ad1bb068e0` |
| `print/ctrl01-card-portrait.stl` | `32dc9f0b4d3210a9820f4e5b5201ede57e17620f1c64c052349f44201c02aa92` |
| `print/ctrl01-card-snap-back.stl` | `3595cd367e1b370de68dec6417dfe69b4b1bf860107b193675a7d3a5a6b6ebdf` |
| `print/ctrl01-card-snap-face.stl` | `33f9dc3a41d05a188b7248d2e31aa8e87c43344f256c7f9e07a4fcb044507c4b` |
| `print/ctrl01-comb.stl` | `34935bec0da0f79a1fcbf55aef0f84cbbd0235dc68f53300bbaf2c86de3cd6f2` |
| `print/ctrl01-front.stl` | `338b3fdb5300edad8acf115c5d0a3987fac62bebaf418fd980e2eb492b928e79` |
| `print/ctrl01-key-play.stl` | `92195d61aa264aef2bf8eb0ee1e6fec7eb6810390fb78c9fd8e0017e657ee2b8` |
| `print/ctrl01-key-rec.stl` | `d64243b6ba88288ce8c051954f2cd16f703d4bb47c3904c489b60c8688c9607a` |
| `print/ctrl01-key-stop.stl` | `55775b84901ddca29cfb88b6de639c4f091069a6ec9b262fb4fa3f3e3204a046` |
| `print/ctrl01-latch.stl` | `213922b5ccc5354c73d9cfef6309cb9ee481a23d115893a56e80fb9fbbf68071` |
