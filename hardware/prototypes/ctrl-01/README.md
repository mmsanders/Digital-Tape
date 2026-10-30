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
  lock, its spring, and the Record blocker;
- **six card slots** filling the rest of the case (two top, two bottom, two right),
  and **five card variants** to try in them.

## Decisions Michael has made

| | |
|---|---|
| Row (top to bottom) | Record · gap (one key) · Play · FF · Rew · Stop · spring housing inside |
| Keys | One piece, no stem: body with rails, a shoulder inset all round that stops on the shell, and a cap whose underside lands on the shell at full press. **Shrunk to the device row** (27 Oct) |
| Catch | P business end (1.2 mm hook, 45° ramp, flat ledge), its lines run on to the edge of the key face |
| Stop | No ledge. One even ramp, 30° from the press direction, then a flat that runs to the shoulder |
| Record | **Blocker in the shell, moved by Play** (27 Oct). Record latches on the slide lock like every key, but while Play is up a blocker stops it after 1.2 mm. Play's 45° pin slides the blocker out of the way as Play goes down and pulls it back as Play comes up. A firm press on Record goes into the shell, not into Play. (The first proposal hung the gate on Play itself; a hard press on Record would have pushed Play down.) |
| Slide lock | Thick latches with the LADDER Stop-tab shape (28 Oct): catch corner and chamfer as before, then the top rises 1.7 mm toward the far end. Length stays 3.9 mm, not LADDER's 7, because at 11 mm pitch a longer latch would meet the next key's catch at full lock travel. Prints back face down |
| Key comb | **Separate part** (30 Oct). The printed back half had the guides built in: the slide lock could not get under them and the keys were trapped in closed rail tunnels. Keys slide into the comb on the bench; the comb drops in over the lock. Generator and gates updated; **`print/` STLs not yet regenerated** (drawings with Michael for review) |
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
| Guidance | Fins between the keys, from the back half's side wall to the spine, with a rail slot for each neighbouring key (FIT-01: 0.15 mm a side). Fins stop 0.2 mm short of the pawls |
| Slide lock | X 6–12, Z 22.9–26.35, Y 18.7–88.4 plus spring boss; runs in a back-half channel with 0.35 mm snap lips; rests up against a stop block, spring at the bottom in the housing |

Latch behaviour, from the 2D simulation in `mech.kinematics()` (catch against pawl):

| Key | Lock first moves at | Latches at | Overtravel | Max lock shift |
|---|---|---|---|---|
| Record, Play, FF, Rew | 2.0 mm | 3.8 mm | 1.2 mm | 1.2 mm |
| Stop | 0.4 mm | never | — | 2.1 mm by 4.0 mm |

Record lands on the blocker at **1.2 mm** while Play is up, 0.8 mm before it could reach the lock, so nothing else pops.

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

## Printing (A1 Mini, PLA as before)

| Plate | Notes |
|---|---|
| `ctrl01-plate-shell.stl` | Both halves, outer faces down, as a matched pair. **No supports.** Bridges: each slot mouth (40 mm, 2.5 mm deep) and each fin (16.8 mm); small overhangs about 1 mm at rail slots and card rails |
| `ctrl01-plate-mech.stl` | Keys upright with **support under the caps only** (the cap underside is flat because it is the stop). Spare FF included. Slide lock back face down; blocker flat |
| `ctrl01-plate-cards.stl` | Flat, no supports. Also carries a spare slide lock with the rising latches (the first mech plate printed flat-topped ones) |

## Assembly

1. Back half on the table, inside up.
2. Snap the slide lock into its channel; pencil spring on its bottom boss, into the housing.
3. Pencil springs on the five spine bosses.
4. For each key: hold it fully pressed, lower it straight into its slot (the extension drops into the half-aperture), let go. Do Play before Record.
5. Press Stop to free anything that latched.
6. Drop the blocker onto Play's pin, into its channel in the gap.
7. Front half on; press round the rim until the eight ridges click. Coin notch on the right side to open.

## What to try

- **Assembly:** anything that would not stay put or needed forcing; the seam all round (paper slip about 0.1 mm, fingernail step); open and close 10 times.
- **Keys:** each one 20 presses, count latches; Stop frees everything; FF pops Play; feel of Stop (kitchen scale if handy).
- **Record**, 10 each: alone (should stop after a short travel and pop nothing); Play then Record; both together; Record then Play; Stop while recording; FF while recording.
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
| `mech.py` | keys, catch and pawl outlines, latch simulation, slide lock, blocker |
| `shell.py` | halves, tongue/groove/ridges, the bay |
| `cards.py` | slots and cards |
| `assembly.py` | parts placed in every state; interference check |
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
| Record, Play, FF, Rew latch on the flat ledge with ≥ 0.8 mm overtravel | the catch reversed (the WP-04 failure) |
| Stop never latches and shifts the lock ≥ 2.1 mm by 4.0 mm | a key with a ledge |
| Record meets the lock ≥ 0.5 mm after the blocker stops it | — |
| A pawl, anywhere in the lock's travel, never meets the next key | 6 mm of lock travel |
| No two parts overlap: at rest, every key at full press and at its peak lock push, every key at 1/2/3/4 mm, Play driving the blocker at 1–4 mm, Play + Record (37 states) | a key moved 0.4 mm off its slot |
| The blocker stops Record at 1.2 mm while Play is up | the blocker where Play would have moved it |
| Every printed part is one valid solid | — |
| Keys print upright with support only under the cap; slide lock, blocker and cards need none | a reversed catch |
| Plates fit the 180 × 180 bed | — |
| Plain slots take every card; rib slots grip every card; slot clearances are as specified | — |
| The detent takes card C into its notch | card A, which has no notch, clashes with the bump |
| Every latch rises ≥ 1.5 mm toward its far end (the Stop-tab shape) | the flat-topped latch first printed |
| Record's finger and Play's arm span their key's whole front face and join it across ≥ 20 mm² (24 and 42) | the 27 Oct defect: an arm hanging on a 0.01 mm strip |

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
| `print/ctrl01-plate-shell.stl` | `8608f150cb086d3df2b3e47fcb84e22f38301be8630dd081b5e5b0b02ce0cac1` |
| `print/ctrl01-plate-mech.stl` | `4ea27281da9222114a2aa6832fda90128111aa6a6c599609e94d5a7b3640e753` |
| `print/ctrl01-plate-cards.stl` | `5de983e20f38742d97c338d2a8f4a94009af63780cf4cc0a2405878e19921335` |
| `print/ctrl01-front.stl` | `d73380c47740c63af08ac5866aedec0338f74f0d5645a5d3b4d6c76cc3ad90da` |
| `print/ctrl01-back.stl` | `ac4e3f2376553000bf7e32714eef9ed05f600272136f23fdd39e9f71faa7fbc8` |
| `print/ctrl01-bar.stl` | `1f475af9c98d1d3d5f069aa3f6bfc9ebbd3f040b364920da5bdb31045b559bb5` |
| `print/ctrl01-blocker.stl` | `c6ab517a65b05cb6dd5c0d9d6c538d9f77423dcff57afd12554a811b8ccb0c52` |
| `print/ctrl01-key-rec.stl` | `6b380e5cacef0ba10ea1300e2d3c84bde0878754660fde78542a9345543a2e4a` |
| `print/ctrl01-key-play.stl` | `0462d7895a2bcf8ba7bb2a498aca1470c2db1a25065f3b79804ccf33ab9782e3` |
| `print/ctrl01-key-ff.stl` | `efb99f00db402e0d8bebea6e410584e5bf93f15d9df04520a3863797b0824d99` |
| `print/ctrl01-key-rew.stl` | `f0cf613ea76225ece2e79015b899cf1ba1d4952ccbd34dfbf38c7872b82c8997` |
| `print/ctrl01-key-stop.stl` | `3eff05b9a1125dedfae021b7970e057321dbfbcda01fd3e546ba7fd221031eac` |
| `print/ctrl01-card-A.stl` … `-E.stl` | see `sha256sum print/ctrl01-card-*.stl` |
