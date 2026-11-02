# Copy button — placement options

**Owner:** Hardware Lead proposes · **Michael chooses.** **Drafted:** 1 November 2026 for
[P3-R1-HW (#641)](https://github.com/mmsanders/Digital-Tape/issues/641), input main `3826018`.
It answers [DEVICE-DESIGN](../../docs/DEVICE-DESIGN.md) §6 item 1. A dedicated button is an added
physical control, so PM records the decision once Michael picks.

## What every option shares

Copy writes the rear cartridge onto the front one, so **a press that starts a copy destroys what is
on the front cartridge.** Whatever the placement:

- **Different from the transport keys:** a round, low button, not a block key. Gray, because orange
  means record or write on the cartridge rims, and the button only starts something the ring then
  shows.
- **Recessed** about 1 mm below its surround, so a flat surface, a bag or a palm can't press it.
- **Hold to start:** about 2 s, with the LED ring filling as it's held. Letting go early cancels.
  Firmware does this in WP-20.
- **Only with both cartridges in.** Otherwise the ring shows "no" and nothing happens.
- Momentary and soft-tactile. No latch.
- Progress is on the front LED ring (WP-18, from the callback, never a timer).

## Options

| | A — Top, beside the rear slot (recommended) | B — Right side, below the volume wheel | C — Front, below the LED ring |
|---|---|---|---|
| **Where** | The top face's free end next to the slots: about 28 mm of top width is left after a 36–40 mm slot | Right side face, under the Ø16 wheel and away from the aux-in jack | Front face, centred under the ring and grille |
| **Story for a 7-year-old** | Strongest: the button sits *with the cartridges*. "This button copies that one to this one" | Weak: nothing links it to the cartridges | Good: it sits right next to the ring that shows copy progress |
| **Accidental press** | Low if recessed. The top is pushed when inserting cartridges, so it needs the recess and the hold | Low: it isn't a face the hand grips while playing. But it's next to the wheel the thumb uses | **Highest:** the front is the face held and pushed, and it faces the floor when the player is dropped face down |
| **Separation from transport** | Different face from the left-side keys | Different face | Different face |
| **Space** | Tight but fits a Ø8–10 mm button. Shares the top with the label windows | Shares the side with the wheel and aux-in | Competes with the Ø46 grille and the label window |
| **Guardrail 13** | Top is a drop-impact face. The recess protects it | Side is protected by the corner bumpers | Front impacts are common, and a protruding button is exposed |
| **Mechanics** | Simple: a plunger through the top shell half, switch on the board edge | Simple, but next to the wheel's mechanism | Needs a board area behind the speaker region |

**Recommendation: A.** The button lives with the two cartridges it acts on, it stays off the faces a
child grips, and the recess plus the hold covers the top being pushed during insertion. **B** is the
fallback if top space runs out once the cartridge slots are designed in Phase 4. **C** isn't
recommended because of accidental presses.

Nothing here is printed yet. Once Michael picks, the button can be added to the bench as one more
tactile switch (line 6 of [PHASE3-BENCH.md](../sourcing/PHASE3-BENCH.md)), and to the shell in Phase 4.
