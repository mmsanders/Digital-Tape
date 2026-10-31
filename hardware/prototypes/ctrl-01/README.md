# CTRL-01 — controls rig (owner-directed prototype)

Michael asked for this round directly (26–27 Oct 2026). It follows the parked owner
layout (#569, `docs/PACKAGES/WP04-OWNER-LAYOUT-2026-10-24.md`) and the LADDER-01/02
latch prototypes (#431). It is **not a PM-issued hardware round and not acceptance**.
Nothing here qualifies a latch, a shell, a material, a card slot or Guardrail 13.

Plan and drawings: the private canvas "CTRL-01 Controls Rig Plan"
(https://claude.ai/artifact/GaMoTPLGY164HNuQtNNfCV). Its early boards predate the
decisions below; where they differ, this README and the code win.

## What it is

The real 68 × 110 × 29 mm case, split at mid-depth, with:

- **the transport sectioned off in its own bay** down the left side, meant to carry
  forward into the final design unchanged if it works: five shrunk keys, the slide
  lock, its spring, and the Record latch slider;
- **six card slots** filling the rest of the case (two top, two bottom, two right),
  and **five card variants** to try in them.

> **1 Nov, in progress: block keys and a new shell.** The generator and gates in this folder
> now describe the next round (block keys on a 13 mm pitch, 4 mm travel, four portrait card
> slots in the top and bottom faces, a tighter clasp). `print/` still holds the 31 Oct files
> and the rest of this README still describes them, until Michael has seen the drawings.

## Decisions Michael has made

| | |
|---|---|
| Row (top to bottom) | Record · gap (one key) · Play · FF · Rew · Stop · spring housing inside |
| Keys | One piece, no stem: body with rails, a shoulder inset all round that stops on the shell, and a cap whose underside lands on the shell at full press. **Shrunk to the device row** (27 Oct) |
| Catch | P business end (1.2 mm hook, 45° ramp, flat ledge), its lines run on to the edge of the key face |
| Stop | No ledge. One even ramp, 30° from the press direction, then a flat that runs to the shoulder |
| Record | **Latches to Play, never to the slide lock** (31 Oct). Record has no catch. A slider driven by a diagonal rail on Play (it cannot turn, and Play drives it both ways) carries a hook. Play up: the hook is out of Record's way, so Record alone goes down and springs back up (firmware will ignore it). Play latched: Record's toe ramps the hook aside (nudging Play 0.8 mm deeper) and the hook drops in behind it. Stop or FF lifts Play, which pulls the hook out, and Record comes up too. Replaces the 27 Oct blocker, which twisted and let Record pop Play |
| Slide lock | Thick latches with the LADDER Stop-tab shape (28 Oct): catch corner and chamfer as before, then the top rises 1.7 mm toward the far end. Length stays 3.9 mm, not LADDER's 7, because at 11 mm pitch a longer latch would meet the next key's catch at full lock travel. Body 0.1 mm slimmer each side from 31 Oct (Michael shaved the sides to fit). Prints back face down |
| Key comb | **Separate part** (30 Oct). The printed back half had the guides built in: the slide lock could not get under them and the keys were trapped in closed rail tunnels. Keys slide into the comb on the bench; the comb drops in over the lock. A front half printed before 30 Oct is kept: a glue-in piece adds the blocker's inner guide, which used to hang from a fin |
| Shell | Full size, back half is the chassis: everything that locates a part is on it; the front half adds flat faces and clearance |
| Solenoid | None |
| Files | Generator, tests and STLs committed here |

## The transport bay (what would be locked in)

Device frame: X in from the key side, Y down from the top, Z back from the front; seam at Z 14.5.

| | |
|---|---|
| Bay | X 0–21.3 (inner wall, the "spine", at X 19.3–21.3), Y 13.5–105, full depth. Closed by end walls in both halves and the spine/partition |
| Key pitch | 11 mm; key centres at Y 26, (gap 37), 48, 59, 70, 81 |
| Key | Body 12 (depth) × 7 (row) × 9 mm, rails 2.5 × 1.0 on the row faces; extension 9.5 × 4.5 through the 2.5 mm wall (inset 1.25, aperture clearance 0.25, so 1.0 mm of shoulder catches the shell); cap 12 × 8 × 2.5 with a symbol |
| Travel | **5.0 mm** (LADDER was 6.2). At rest the caps stand 7.5 mm proud of the side face: 5 mm of travel plus the cap |
| Springs | Pencil springs everywhere (14 free / about 4 solid; FIT-01: Ø3.0 boss, Ø4.5 hole). Key springs run from the key's groove to a boss on the spine, 10 mm at rest, 5 mm pressed. One bar spring, 11 mm at rest |
| Guidance | **Key comb** (separate part): fins between the keys, from the side wall to the spine, with a rail slot for each neighbouring key (FIT-01: 0.15 mm a side). Fins stop 0.2 mm short of the pawls |
| Slide lock | X 6.1–11.9, Z 22.9–26.35, Y 18.7–88.4 plus spring boss; runs in a back-half channel with 0.35 mm snap lips; rests up against a stop block, spring at the bottom in the housing |

Latch behaviour, from the 2D simulation in `mech.kinematics()` (catch against pawl):

| Key | Lock first moves at | Latches at | Overtravel | Max lock shift |
|---|---|---|---|---|
| Play, FF, Rew | 2.0 mm | 3.8 mm | 1.2 mm | 1.2 mm |
| Stop | 0.4 mm | never | — | 2.1 mm by 4.0 mm |

Record, from `mech.record_latch()` (toe against the slider's hook, in plan): alone it meets nothing; with Play latched it pushes the slider at most 0.8 mm (one mm of slider per mm of key: a ramp, not a wall), is held at **4.3 mm** on a flat ledge, and is free again once Play has risen to 1.0 mm.

## Cards and slots

Cards are GameCube class, 36 × 40 × 7 mm, and sit 3 mm proud. Each place takes two slots, one in each half. Each pocket is open toward the seam except for two edge rails, so no pocket has a roof bridged over it.

| Slot | Where | Clearance a side | Holding |
|---|---|---|---|
| TF | top, front | 0.20 | none |
| TB | top, back | 0.30 | none |
| RF | right side, front | 0.40 | none |
| RB | right side, back | 0.30 | crush ribs (0.10 interference) |
| BF | bottom, front | 0.30 | crush ribs |
| BB | bottom, back | 0.30 | flex detent: a cantilever with a 0.6 mm bump that drops into card C's notch |

Top and bottom cards go in along their 36 mm side (40 mm opening); side cards along their 40 mm side (36 mm opening). That is the only way six fit in 110 mm; the device sketch has its two slots the other way round.

| Card | |
|---|---|
| A | 0.5 mm chamfer on every edge (baseline) |
| B | square edges |
| C | chamfered, detent notches (for BB) |
| D | chamfered, thumb dimples on the top face |
| E | chamfered, 0.4 mm label recess |


**Portrait cards (31 Oct).** For the side slot Michael liked (RB: 0.30 mm and crush ribs), 2 mm taller (42 × 36 × 7) so 5 mm stands proud. Face, from the proud end: grip notches on both sides, a 1.2 mm grab scoop under a 2 mm lip, a 0.4 mm label window over the lower two-thirds. `ctrl01-card-portrait.stl` is solid; `ctrl01-card-snap-face/-back.stl` snap together: a tongue all round the back half's rim, a 0.25 mm bead on each side clicking into a relief in the face half's groove, 2.3 mm hollow inside.
## Printing (A1 Mini, PLA as before)

| Plate | Notes |
|---|---|
| `ctrl01-plate-shell.stl` | Both halves, outer faces down, as a matched pair. **No supports.** Bridges: each slot mouth (40 mm, 2.5 mm deep); small overhangs about 1 mm at card rails |
| `ctrl01-plate-rebuild.stl` | **30 Oct reprint**: new back half (shell settings), key comb and glue-in guide (mech settings; set per object). Comb prints spine down, no supports |
| `ctrl01-plate-latch.stl` | **31 Oct**: Record latch slider (floor down), new Record and Play keys (upright, **support under the caps only**), slimmer slide lock, the solid portrait card and both snap-card halves. Mech settings for the keys, slider and lock; shell settings for the cards. The snap face half prints face up; its groove underneath is a 1.2 mm bridge |
| `ctrl01-plate-mech.stl` | Keys upright with **support under the caps only** (the cap underside is flat because it is the stop). Spare FF included. Slide lock back face down; latch slider flat; key comb spine down |
| `ctrl01-plate-cards.stl` | Flat, no supports. Also carries a spare slide lock with the rising latches (the first mech plate printed flat-topped ones; mech settings) and the **new front half** (shell settings), so the slider's inner guide comes built in |

## Assembly

The check `assembly.assembly_sequence()` slides every part in along these paths, in this order.

1. **Keys into the comb, on the bench:** each key slides in from the comb's outer end, cap last, rails into its tunnels.
2. **Slide lock:** back half on the table, inside up. Snap the lock into its channel; pencil spring on its bottom boss, into the housing.
3. **Comb:** lower it, keys and all, straight into the back half over the lock: spine against the backstop wall, ends between the end walls, each key's extension into its half-aperture.
4. **Latch slider:** drop it onto Play's rail, floor toward the front, hook toward Record.
5. **Key springs:** squeeze each with tweezers and slip it between the key's post and its boss on the spine.
6. Press Stop to free anything that latched.
7. **Front half** on; press round the rim until the eight ridges click. Coin notch on the right side to open.

Use the new front half from the cards plate. Only if keeping a front half printed before 30 Oct: glue `ctrl01-guide-retrofit.stl` in first, its long strip along the side wall, butted against the bay's top end wall and the front wall. It then sits where the new front half has the guide built in.

## What to try

- **Assembly:** anything that would not stay put or needed forcing; the seam all round (paper slip about 0.1 mm, fingernail step); open and close 10 times.
- **Keys:** each one 20 presses, count latches; Stop frees everything; FF pops Play; feel of Stop (kitchen scale if handy).
- **Record**, 10 each: alone (goes down, springs back, pops nothing); Play then Record (both stay down); hold Record fully, then Play; Stop while recording (both up); FF while recording.
- **Cards:** every card in every slot: insert, feel, hold upside down, pull out. Which clearance feels right, ribs versus detent versus nothing, which edge and grip you like.
- **Caps:** square or askew; the 7.5 mm proud height.
- Anything that breaks.

## What this changes on the device sketch

- The transport bay is **21.3 mm wide** (sketch: about 16). With 36 mm cartridges centred, the right column gets tighter; a later layout pass has to absorb about 5 mm.
- Key order: Record, gap, Play, FF, Rew, Stop, with the spring housing below Stop. The headphone jack can no longer sit in the bottom-left corner.
- Caps stand 7.5 mm proud of the side face (5 mm travel + cap). Recessing the key area, or shorter travel, are options once the latch is proven.
- The rig's slot orientation and the slot count are for testing, not a layout.

## Code

| File | |
|---|---|
| `layout.py` | every shared number |
| `mech.py` | keys, catch and pawl outlines, latch simulation, slide lock, Record latch slider and its simulation |
| `shell.py` | halves, tongue/groove/ridges, the bay, the key comb, the glue-in guide |
| `cards.py` | slots and cards |
| `assembly.py` | parts placed in every state; interference check; build order and paths in |
| `build.py` | print poses, plates, STLs |
| `test_rig.py` | gates below |
| `key_v1.py`, `test_key_v1.py` | the full-size LADDER-based key from earlier on 26 Oct (superseded; outputs in `print/v1/`) |

```sh
pip install cadquery pytest shapely
python3 hardware/prototypes/ctrl-01/build.py                 # writes print/
cd hardware/prototypes/ctrl-01 && python3 -m pytest -q        # about 2 minutes
```

## Gates and their negative controls

| Gate | Negative control (must fail) |
|---|---|
| Play, FF, Rew latch on the flat ledge with ≥ 0.8 mm overtravel | the catch reversed (the WP-04 failure) |
| Stop never latches and shifts the lock ≥ 2.1 mm by 4.0 mm | a key with a ledge |
| A pawl, anywhere in the lock's travel, never meets the next key | 6 mm of lock travel |
| No two parts overlap: at rest, every key at full press and at its peak lock push, every latch key at 1/2/3/4 mm, Record alone, Record pushing past the hook, Record held, Stop releasing both (38 states) | a key moved 0.4 mm off its slot |
| Record latch: alone, Record meets nothing; Play's press brings the hook past the resting toe; with Play latched Record ramps the hook aside (≤ 0.8 mm, slope ≤ 1.5), is held on a ledge with ≥ 0.5 mm overtravel, and is free before Play is fully up (≥ 0.6 mm) | a toe without its chamfer stalls; a hook left in Record's lane catches Record alone; a hook too wide never lets go |
| Play's latched depth is the depth the latch is built for (3.8 mm) | — |
| Record never comes within 0.5 mm of the slide lock | — |
| Portrait cards grip in RB and touch only its ribs; the snap card's halves close without overlap into a full 42 × 36 × 7 card | a bead bigger than its relief |
| Every printed part is one valid solid | — |
| Keys print upright with support only under the cap; slide lock, latch slider, comb, glue-in guide and cards need none (the snap face half: only its groove) | a reversed catch |
| Plates fit the 180 × 180 bed | — |
| Plain slots take every card; rib slots grip every card; slot clearances are as specified | — |
| The detent takes card C into its notch | card A, which has no notch, clashes with the bump |
| Every latch rises ≥ 1.5 mm toward its far end (the Stop-tab shape) | the flat-topped latch first printed |
| Every part has a clear straight path in, in build order (keys into comb, lock, comb with keys, latch slider, front half); only the lock's snap lips are allowed in the way | the back half as printed on 28 Oct, comb built in: neither the lock nor a key gets in |
| The glue-in guide clears every part in every state | the guide set 0.5 mm too far in hits the latch slider |
| Record's web and Play's arm span their key's whole front face and join it across ≥ 20 mm² (24 and 42) | the 27 Oct defect: an arm hanging on a 0.01 mm strip |

Numbers that come from the printer, not this code: key slide 0.15 mm a side, spring
holes and bosses (FIT-01); the P preference (LADDER-01/02). The latch simulation is
geometry only; LADDER-01 saw 0.6–0.8 mm of engagement lost on the real printer.

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
| `print/ctrl01-plate-latch.stl` | `a5f9b70aca711ee05cff2353f45e806df77f861bf99527d5212f4acf28d8d261` |
| `print/ctrl01-latch.stl` | `fa4ac09395624e0eab7e0e5001a158010de050af0fc6fbcec7fd7a6005f0828e` |
| `print/ctrl01-card-portrait.stl` | `32dc9f0b4d3210a9820f4e5b5201ede57e17620f1c64c052349f44201c02aa92` |
| `print/ctrl01-card-snap-face.stl` | `33f9dc3a41d05a188b7248d2e31aa8e87c43344f256c7f9e07a4fcb044507c4b` |
| `print/ctrl01-card-snap-back.stl` | `3595cd367e1b370de68dec6417dfe69b4b1bf860107b193675a7d3a5a6b6ebdf` |
| `print/ctrl01-plate-shell.stl` | `f0eed41118c88eae54f331261da8b031164eaeeb35ef3e3a65cd89c6021561cb` |
| `print/ctrl01-plate-mech.stl` | `fcae5ee7a33760bcc8b3f02afe6ef2b8651373b23b98e58327df18f8f45238ce` |
| `print/ctrl01-plate-cards.stl` | `98b99ebe95a2ddec8f8adfc86e916c777b425e046b30c3c75ddeea942910a3b9` |
| `print/ctrl01-front.stl` | `da5874690faf963064143a80e1833f17908296bcb5378326859a6538c52ad309` |
| `print/ctrl01-back.stl` | `e6760984772dc56540b44dce2bacd6fc186ba88b237192e8460cd81e24d5dbbd` |
| `print/ctrl01-plate-rebuild.stl` | `2e23799c366afb908f533c53b5e8aead48ec0895e4571aa3061446884d8451f3` |
| `print/ctrl01-comb.stl` | `1eb89001ea7f93927ae96ee6444760df01990c94c9081c2265876e6f7c5edc85` |
| `print/ctrl01-guide-retrofit.stl` | `ceb57df13f007479139e45bbd0f63c14ad89c32f24c12f0ee544444691755104` |
| `print/ctrl01-bar.stl` | `55525bae7b13986efedc9e73edfd0995ab7cb042681bb7ad89265bc671bf954f` |
| `print/ctrl01-key-rec.stl` | `b232be4f0fd3730a40c923695ead1f84d5f803b115836439d404d08bec4f61cb` |
| `print/ctrl01-key-play.stl` | `cbe3b476170f7439cc1fab9bb07f50e715818898f6cfae66409ffc0d6ee10d59` |
| `print/ctrl01-key-ff.stl` | `efb99f00db402e0d8bebea6e410584e5bf93f15d9df04520a3863797b0824d99` |
| `print/ctrl01-key-rew.stl` | `f0cf613ea76225ece2e79015b899cf1ba1d4952ccbd34dfbf38c7872b82c8997` |
| `print/ctrl01-key-stop.stl` | `3eff05b9a1125dedfae021b7970e057321dbfbcda01fd3e546ba7fd221031eac` |
| `print/ctrl01-card-A.stl` … `-E.stl` | see `sha256sum print/ctrl01-card-*.stl` |
