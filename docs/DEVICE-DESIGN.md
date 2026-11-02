# Device design — current owner baseline

**2 November 2026 PDT.** This is the one current description of the player and cartridge.
It combines:
- Michael's layout (intake #569, 24 Oct);
- the CTRL-01 controls rig (`hardware/prototypes/ctrl-01/`, 26 Oct–1 Nov);
- his decisions of 1–2 November ([ADR-199](DECISIONS.md#adr-199--phase-25-cleanout-device-design-baseline-and-phase-3-answers), [ADR-200](DECISIONS.md#adr-200--device-behaviour-answers)).

It is a design reference, not released CAD or qualification. Items marked **OPEN** are listed
in §6. Guardrail 13 (kid-resistant mechanics) governs everything here.

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
| Left side | Transport keys (§3). Side keys are the current model; a face-key variant may come later and would change only the key section of the shell |
| Right side | Volume wheel (about Ø16); aux in (orange rim) |
| Bottom | Headphone / aux out jack (must move from the bottom-left corner because of the key bay); USB-C for charge and data; battery LEDs |
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
| Rew / FF | Momentary (spring back). Work with or without Play latched. **Depth-sensitive:** a light press scrubs gently, full depth scrubs fast, with a smooth gradient in between, so a light press scrubs while playing. Both pressed together: nothing happens until one is released |
| Bay | 21.3 mm wide; keys proud of the side face |
| Springs | Pencil springs (about 14 mm free) |

Because nothing auto-pops, two spec behaviours are replaced at Phase 3 kickoff:
- **End of tape:** audio stops, Play stays down, and the LED ring shows "end" until Stop.
- **Cartridge full while recording:** recording stops and is kept, the keys stay down, and the
  ring shows red until Stop.

Depth-sensitive Rew/FF replaces the fixed time-based scrub ramp in the spec. The engine is
unchanged: firmware maps press depth to `tape_set_rate`.

## 4. Audio

| Path | Baseline |
|---|---|
| Headphones / aux out | One 3.5 mm jack that serves as both headphones and line out. Output cap **85 dB SPL** on reference headphones, set in the codec, re-asserted at boot, unreachable from controls (guardrail 11) |
| **Speaker (new requirement)** | About Ø40 driver with its own amplifier. **It gets its own loudness cap**, enforced in hardware/codec and unreachable from controls, like the headphone cap. The value is set at Phase 3 kickoff from toy-safety acoustic limits that Hardware researches |
| Microphone | MEMS mic, top-left |
| Aux | Two ports: **aux in** (right side) and **aux out**, which is the headphone jack |
| Volume | Wheel; it can never exceed the caps |

**Rules:**
- Plugging in headphones mutes the speaker.
- The speaker is muted while recording, to avoid feedback. Headphones keep playing so the
  child can listen while recording.
- **Record source:** aux in if something is plugged in, otherwise the microphone.

## 5. Electronics, power and copy (targets, not designs)

| Item | Baseline |
|---|---|
| MCU | Teensy 4.1 for the Phase 3 bench; production board later (spec/hw/board-rev-a.md is versioned and will be revised) |
| Card bus | SDR50 at 1.8 V primary, High Speed 4-bit fallback (later phases) |
| Copy | Rear slot to front slot. A whole C-60 copy in under 30 s on the production system (guardrail 10, not provable on the bench). A copy starts from a **dedicated copy button**, separate from the transport keys (likely; placement **OPEN**) |
| Battery | About 1,200 mAh estimate. Charging and fabrication stay CLOSED until the safety gate opens |

## 6. Still open

1. **Copy button:** a dedicated button, separate from the clicky transport keys, is likely.
   Placement and feel are undecided.
2. **Promote B to A** (make the edited Side B the new original): which key combination
   triggers it. It must be hard to do by accident.
3. **Depth sensing for Rew/FF:** the mechanism (for example a Hall-effect sensor or a
   force-sensitive part under the key) and the depth-to-speed curve. Hardware proposes one
   in Phase 3. This is new for the CTRL-01 keys, which today are simple travel keys.
4. **Face-key variant:** possible later. Phase 3 and 4 use side keys only.

Answered on 2 November and folded in above:
- aux in and out;
- speaker muting;
- end of tape;
- record source;
- Rew/FF behaviour;
- cartridge full;
- side keys.

## 7. Superseded

These no longer describe the design (history is in Git and docs/archive/hardware/):
- the solenoid transport (Route A/B, hook bar, one-shot driver);
- the 86 × 54 × 12 mm cartridge and its clasp analysis;
- the September parts cart and order 1a/1b;
- the library-printer packet route.

The coil safety limits in spec/acceptance.md stay until a spec revision removes them.
