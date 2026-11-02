# Rew/FF depth sensing — proposal (WP-20)

**Owner:** Hardware Lead · **Status:** PROPOSAL (a sketch, no print). **Drafted:** 1 November 2026
for [P3-R1-HW (#641)](https://github.com/mmsanders/Digital-Tape/issues/641), input main `3826018`.
It answers [DEVICE-DESIGN](../../docs/DEVICE-DESIGN.md) §6 item 3. No CTRL-01 file is changed:
the rig is Michael's (#641, "Not in this task").

## 1. Proposal: a linear Hall sensor and a captured magnet

Each Rew and FF key carries a small N52 disc magnet. A ratiometric linear Hall sensor sits behind
the key's end of travel, facing it. As the key goes down, the magnet approaches the sensor, the field
rises smoothly, and the Teensy's ADC reads it continuously. Firmware turns the reading into depth
using each key's two calibration points (rest and full press), and depth into `tape_set_rate`.

| | |
|---|---|
| Sensor | TI **DRV5055A4** (±169 mT, about 7.5 mV/mT at 3.3 V per TI's datasheet), TO-92, ratiometric to 3.3 V. The **A3** (±85 mT, double the sensitivity) is the bench alternative |
| Magnet | K&J **D32-N52**, Ø4.76 × 3.18 mm, axially magnetised |
| Read by | Teensy 4.1 ADC, 12-bit at 3.3 V ref (0.81 mV per count), averaged |
| Cost per key | $0.77 + $0.35 = **$1.12**; $2.24 for both keys |
| Contact or wear | None. The sensor never touches the key |

**Why not the alternatives:**

| Option | Why not |
|---|---|
| Force-sensitive resistor under the key | Senses force, not travel, so nothing registers until the key bottoms. That throws away the 4 mm travel the child feels. FSRs also drift, show hysteresis and wear, and need a stiff backing stack |
| Reflective optical (TCRT5000 class) | Workable, but sensitive to ambient light leaking into the bay, dust and print colour. Bigger part |
| Slide potentiometer | A wiper contact wears and gets dirty; there's no room in a 12.4 mm key |
| Capacitive | Possible but complex to make reliable against a child's hand on the shell |

## 2. Where it fits in the CTRL-01 key

The CTRL-01 frame (from `prototypes/ctrl-01/README.md`): X goes in from the key side.
- The key underside is at X 12.5 at rest and X 16.5 at full press (4 mm travel).
- The comb fins run to the spine at X 19.3.
- The key spring runs from a groove in the key to a boss on the spine.

```
   side face                         comb spine
   │                                     ║
   │  ┌────────── key block ─────────┐   ║
 ──┼──┤   ┌──┐  (spring groove,       ├─  ║  ┌────┐
   │  │   │M │   unchanged)           │   ║  │ H  │◄─ DRV5055 in a pocket in the spine,
   │  └───┴──┴───────────────────────┘   ║  └─┬┬┬┘   branded face toward the key,
   │      ▲ magnet in a closed pocket     ║    │││    leads out the back to the board
   │        beside the spring groove      ║
       X 12.5 rest ──► X 16.5 full        X ≈ 19.5 sensor face
       gap at full press ≈ 3.0 mm, at rest ≈ 7.0 mm
```

- **Magnet pocket:** Ø4.9 × 3.3 mm, blind, in the key block beside the spring groove (the block is
  7 mm across, leaving about 1.1 mm of wall each side). It is printed with a **pause at layer** on the
  A1 Mini: the magnet drops in and the next layers close it over, so the magnet is sealed inside the
  PLA with no opening (§5).
- **Sensor pocket:** about 4.2 × 3.3 × 1.7 mm in the comb spine, open to the back for the leads.
  The sensor is pressed in or held with a drop of glue. The face is on the key axis, offset to line
  up with the magnet.
- Nothing else in the key changes: the block shape, rails, flange, spring and travel stay the same.

## 3. Resolution and range

On-axis field of the D32 disc (Br ≈ 1.45 T), with the gap at full press set to 3.0 mm:

| Depth (mm) | 0 | 0.5 | 1.0 | 1.5 | 2.0 | 2.5 | 3.0 | 3.5 | 4.0 |
|---|---|---|---|---|---|---|---|---|---|
| Gap (mm) | 7.0 | 6.5 | 6.0 | 5.5 | 5.0 | 4.5 | 4.0 | 3.5 | 3.0 |
| Field (mT) | 19.6 | 23.2 | 27.9 | 33.8 | 41.5 | 51.6 | 65.1 | 83.4 | 108.6 |

**With the A4 sensor:**
- the full stroke swings about 670 mV, which is **about 830 ADC counts**;
- at the light end, the first 0.5 mm is about 33 counts. With about ±4 counts of noise after
  averaging, that resolves **about 0.06 mm** at the lightest press, and much finer deeper in the stroke.

That is far more than the "smooth gradient" Michael asked for. Even 20 usable speed steps would
feel continuous.

**A3 option:** twice the counts at the light end, but it saturates above 85 mT, around 3.4 mm deep.
That's acceptable, because the last 0.6 mm can simply be "full speed". Alternatively, keep A3 and move
the sensor to a 4 mm gap.

The curve is steep and nonlinear (roughly 1/gap³). That's fine: firmware maps through a stored curve
normalised by the two calibration points, and the depth-to-speed curve is set with Michael in WP-20.
The figures above are a model (on-axis formula for a disc magnet), not a measurement. The bench
confirms them with lines 15–17 of [PHASE3-BENCH.md](../sourcing/PHASE3-BENCH.md).

## 4. Things the bench must check

1. **Calibration drift:** rest and full readings per key over temperature and time. Ratiometric
   output tracks supply changes; magnet temperature drift is about −0.12 %/°C for N52.
2. **The pencil spring is steel.** It moves with the key, so its effect is mostly a constant offset
   that calibration absorbs. Check for hysteresis between press and release.
3. **Crosstalk** from the neighbouring key's magnet at 13 mm pitch. The model estimate is under 1 mT,
   about 1% of span. It doesn't matter for Rew+FF together, because both pressed gives no scrub
   anyway (DEVICE-DESIGN §3).
4. **The speaker magnet** sits on the front face, more than 30 mm away. Confirm it gives no offset.
5. **Dead band:** a first-press threshold of about 0.3 mm, so rattle and a resting finger don't scrub.

## 5. Child safety: the magnet

A small neodymium magnet is a serious swallowing hazard. EN 71-1 treats a magnet with flux index
over 50 kG²mm² that fits the small-parts cylinder as hazardous if it can be liberated. This disc is
well above that index. **Guardrail 13 requires that the magnet can't come out**, even after drop,
torque, tension and bite abuse.

The printed key seals it inside, with no pocket opening. In production it must be overmoulded or
fully encapsulated, and the key itself must survive abuse testing without splitting. That has to be
designed and tested before final enclosure CAD, not added later. The bench magnets are loose parts:
keep them away from children.
