# Project status

**16 November 2026.** Phases 1 and 2 are complete. Phase 3 (bench firmware) is open and
**waiting on parts**.

## Where things stand

| Phase | State |
|---|---|
| 1 Audio engine | Done (3 Oct). Frozen at engine tree `d96b4245`; format frozen |
| 2 Desktop tools | Done for Windows 11 (1 Nov). Michael has made real cartridges with the app. Scope frozen: it loads cartridges, nothing more |
| 3 Bench firmware | Open since 2 Nov. Play path, card binding and warm-wake timer are written and pass off-target. **Nothing has run on a Teensy yet, because there is no Teensy** |

## What blocks progress

**The first parts order.** About $62 before tax and shipping: Teensy 4.1 with headers, audio
shield, header strip, breadboard, jumpers, buttons, USB cable. The checked list with links
is group 1 in [the bench parts list](../hardware/sourcing/PHASE3-BENCH.md). Michael is
ordering it. Until it arrives, no firmware number is real.

## When the parts arrive

In this order. Each step is one session plus Michael at the bench.

1. **Bring-up.** Solder the audio-board header, wire it, flash, insert a cartridge made
   with the desktop app, press Play. Steps are in
   [the firmware README](../firmware/bench/README.md). Keep the volume low and check it
   with the headphones off your ears first.
2. **Listen for clicks.** The firmware blocks the audio interrupt while it reads the card
   (`loop_call` in `firmware/bench/src/main.cpp`). A slow card read may be audible as a
   click that the underrun counter does not see. If so, the fix is a small FIFO in
   firmware between the engine and the interrupt; the engine does not change.
3. **Goldens on target** (F1): `firmware/bench/tools/golden_serial.py` compares the
   Teensy's audio with the reference, byte for byte.
4. **Warm wake** (F3): `sleep`, press Play, read the `WAKE us …` line, then the `wake150`
   check. Add a row to [MICHAEL-CHECKS](MICHAEL-CHECKS.md).
5. **Stack and removal** (F2, F5): `info` prints the stack high-water mark; pull the card
   mid-play and run `tapectl verify` on it afterwards.

Then recording and the second slot (WP-18/19), keys and LEDs (WP-20), and the power-cut
test on the PNY cards. Criteria are in [the Phase 3 ledger](PHASE3-LEDGER.md).

## Waiting on Michael

See [FOR-MICHAEL](FOR-MICHAEL.md): the parts order, the speaker loudness limit, and two
open pull requests to close.

## How work runs now

[ADR-210](DECISIONS.md#adr-210--light-process-outside-the-engine), 16 November: the
tests-first, independently verified process applies to the engine and the format only.
Firmware, tools and hardware are one lead, one session, one PR, judged by Michael on the
bench. Rules are in [CLAUDE.md](../CLAUDE.md) §3.

## Holds that stand

- Guardrails 01 to 13. Engine pinned, format frozen.
- Output: fixed low level until the headphone cap (WP-19) lands. Nobody wears headphones
  on the bench without a volume check.
- One block per card write call; write batching stays off (six long crash-test cases could
  not be run; see the ledger).
- Fabrication and cell charging CLOSED. No card is qualified yet.
- The desktop app and ingest never run elevated; `tapectl` never writes a disk the user
  did not pick.
- Deferred, not dropped: the unaided app test ([G2](WP15-G2-PROTOCOL.md)) before anyone
  else uses the app; macOS; the ADR-196 limitations.

[Hardware status](STATUS-HARDWARE.md) · [Device design](DEVICE-DESIGN.md) ·
[Phase 3 plan](PHASE3-PLAN.md) · [previous status](archive/status-history/2026-11-08-before-ADR-210.md)
