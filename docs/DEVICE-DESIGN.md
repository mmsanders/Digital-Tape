# Device design — current owner baseline

**1 November 2026 PDT.** This is the one current description of the player and cartridge.
It combines:
- Michael's layout (intake #569, 24 Oct);
- the CTRL-01 controls rig (`hardware/prototypes/ctrl-01/`, 26 Oct–1 Nov);
- his decisions of 1 November ([ADR-199](DECISIONS.md#adr-199--phase-25-cleanout-device-design-baseline-and-phase-3-answers)).

It is a design reference, not released CAD or qualification. Items marked **OPEN** need
Michael's answer (§6). Guardrail 13 (kid-resistant mechanics) governs everything here.

## 1. Envelope and materials

| Part | Baseline |
|---|---|
| Player | About 68 × 110 × 29 mm, split front/back at mid-depth; tongue and groove with snap ridges; four corner bumpers about 2 mm proud |
| Cartridge | GameCube class, about 36 × 40 × 7 mm. Fit, retention and contacts are not designed yet |
| Colour language | Blue shell; gray structural parts; **orange means record/write** |
| Prototype material | PLA on Michael's A1 Mini. Production material undecided |

## 2. Faces

| Face | Contents |
|---|---|
| Top | Two cartridge slots, one behind the other. Front: play/record, orange rim, label window. Rear: copy source, read-only, gray rim |
| Front | Speaker grille (about Ø46 over an about Ø40 speaker); 16-LED ring for position, copy progress and status; cartridge label window |
| Left side | Transport keys (§3) |
| Right side | Volume wheel (about Ø16); aux jack(s) (§4) |
| Bottom | Headphone jack (must move from the bottom-left corner because of the key bay); USB-C for charge and data; battery LEDs |
| Top-left bumper | Perforated over a MEMS microphone in a sealed boot, near Record |

## 3. Transport: mechanical latching keys, no solenoid

**Decided (Michael, 1 Nov): no solenoid. Nothing pops up by itself.** The firmware reads
key positions and shows state on the LED ring.

| Element | Baseline (from CTRL-01) |
|---|---|
| Keys | Block keys, no caps: 12.4 × 16 mm, 4 mm proud, 4 mm travel, symbol engraved. Order: Record, gap, Play, Stop (then Rew, FF in the full row) |
| Play | Latches down on a slide lock (P catch: 1.2 mm hook, 45° ramp, flat ledge) |
| Stop | Momentary; its ramp shifts the slide lock and releases Play |
| Record | Latches **only to Play**, through a latch slider driven by Play. Alone, Record springs back. Stop lifts Play, which releases Record. A hard press on Record goes into the shell, not into Play |
| Rew / FF | In the full five-key row; behaviour is **OPEN** (Q6) |
| Bay | 21.3 mm wide; keys proud of the side face |
| Springs | Pencil springs (about 14 mm free) |

Because nothing auto-pops, these spec behaviours need replacing at Phase 3 kickoff:
- "end of tape releases Play within 50 ms";
- "cartridge full mid-record releases the buttons".

The proposal is in Q3 and Q7.

## 4. Audio

| Path | Baseline |
|---|---|
| Headphones | 3.5 mm jack. Output cap **85 dB SPL** on reference headphones, set in the codec, re-asserted at boot, unreachable from controls (guardrail 11) |
| **Speaker (new requirement)** | About Ø40 driver with its own amplifier. **It gets its own loudness cap**, enforced in hardware/codec and unreachable from controls, like the headphone cap. The value is set at Phase 3 kickoff from toy-safety acoustic limits that Hardware researches |
| Microphone | MEMS mic, top-left |
| Aux | **Two aux ports** (Michael, 1 Nov). Roles **OPEN** (Q1) |
| Volume | Wheel; it can never exceed the caps |

Speaker behaviour with headphones and while recording is **OPEN** (Q2).

## 5. Electronics, power and copy (targets, not designs)

| Item | Baseline |
|---|---|
| MCU | Teensy 4.1 for the Phase 3 bench; production board later (spec/hw/board-rev-a.md is versioned and will be revised) |
| Card bus | SDR50 at 1.8 V primary, High Speed 4-bit fallback (later phases) |
| Copy | Rear slot to front slot. A whole C-60 copy in under 30 s on the production system (guardrail 10, not provable on the bench). How a child starts a copy is **OPEN** (Q5) |
| Battery | About 1,200 mAh estimate. Charging and fabrication stay CLOSED until the safety gate opens |

## 6. Open questions for Michael

1. **Aux ports.** One in and one out? Or two inputs? Is the headphone jack separate, making
   three jacks in all?
2. **Speaker behaviour.**
   - Mute the speaker when headphones are plugged in? (Proposed: yes.)
   - Mute it while recording, to avoid feedback? (Proposed: yes.)
3. **End of tape.** Proposed: audio stops, Play stays down and the LED ring shows "end"
   until the child presses Stop. The alternative is auto-rewind or loop.
4. **Record source.** Proposed: an aux input if one is plugged in, otherwise the
   microphone. With two inputs, which one wins?
5. **Starting a copy.** There is no copy key in the drawing. Options:
   - a dedicated key;
   - Record pressed with a cartridge in the rear slot;
   - starting automatically when both slots hold cartridges and Play is pressed.
6. **Rew/FF.** Momentary, with the scrub ramp while held? Do they also work while Play is
   latched, to cue and review?
7. **Cartridge full while recording.** Proposed: recording stops and is kept, the keys stay
   down, and the ring shows red until Stop.
8. **Key position.** Are side keys settled, or are face keys still in play?

## 7. Superseded

These no longer describe the design (history is in Git and docs/archive/hardware/):
- the solenoid transport (Route A/B, hook bar, one-shot driver);
- the 86 × 54 × 12 mm cartridge and its clasp analysis;
- the September parts cart and order 1a/1b;
- the library-printer packet route.

The coil safety limits in spec/acceptance.md stay until a spec revision removes them.
