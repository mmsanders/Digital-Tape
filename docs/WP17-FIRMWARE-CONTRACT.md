# WP-17 bench firmware — contract FW-1

**Status:** ISSUED by PM, 2 November 2026 PDT ([ADR-201](DECISIONS.md#adr-201--phase-3-opened-round-1-issued)).
Changes after issue are PM decisions recorded here and in both lead issues.
**2 November clarification (ADR-202 / PM #648):** admission follows WP-14 §2;
F1 compares the seven normal-rate golden PCM payloads, not whole-WAV hashes.

The device is described in [DEVICE-DESIGN](DEVICE-DESIGN.md) and the phase in
[the Phase 3 plan](PHASE3-PLAN.md). The normative engine behaviour is spec/engine-api.md and
spec/tapefs-v1.md, at the revision in spec/VERSION.md.

## 1. Scope

WP-17 puts the shared engine on a **Teensy 4.1** with an SGTL5000 audio board (the PJRC Teensy
Audio Adaptor or its equivalent) and plays a cartridge made by the Phase 2 desktop tools. It
covers:
1. a build of the unchanged engine for the Teensy;
2. a block-device binding for the Teensy's built-in microSD slot;
3. the play path: mount, render, I²S out to the headphone jack;
4. minimal controls: Play and Stop as two inputs;
5. measurement hooks for the criteria in §6.

Recording, the second slot, copy, the speaker, aux, depth-sensitive scrub and LED status
belong to WP-18 to WP-20, under their own contracts.

## 2. What does not change

- **`engine/` stays byte-identical** to the pinned tree `d96b4245`, including `engine/port/`.
  The `engine/port/dev_sd.c` stub stays a stub. Teensy code lives in `firmware/bench/`
  (guardrail 09: the engine has no board knowledge).
- Firmware calls only the public API in `engine/include/tape.h`. It must not reimplement
  seek, render, mixing, rate or any other engine behaviour (guardrail 12, CLAUDE.md §6).
- No heap use for engine storage. The instance memory (`tape_instance_size()`) and every
  buffer the engine is given are static, caller-owned storage (guardrail 08).
- The format, the desktop tools and their contracts are unchanged.

## 3. Build

- PlatformIO or Arduino CLI with the **Teensy core and toolchain versions pinned** in the repo.
  Software chooses and records them.
- `firmware/bench/` builds the engine sources with the same warning set the desktop build uses
  (`-Werror` for engine files).
- CI compiles the firmware for the Teensy 4.1 on every PR that touches `firmware/` or
  `engine/`, and prints the map-file sizes (§6). CI never flashes hardware.

## 4. Block device

- A `tape_dev` over the built-in SDIO slot (the Teensy core's SD/SdFat raw sector access),
  in `firmware/bench/`.
- **Partition view:** the binding reads the MBR and presents TAPEFS partition 2 (`tapefs` §3)
  as LBA 0, exactly as the desktop `tapectl` does. **Admission uses WP-14 §2 exact
  recognition**, with the approved [E-1 overlay](SPEC-ERRATA.md): `55 AA`, entries 1/2
  matching the prescribed fields/extents, entries 3/4 zero, and safe view bounds.
  A change only to bootstrap bytes 0–439, disk signature 440–443 or reserved bytes
  444–445 does not by itself refuse admission. Provisioning still writes the §3.1
  values; full desktop `verify` diagnostics remain WP-14 §4.1 and can report an
  `MBR_LAYOUT` finding on an admitted card. Recognition is not full validation or
  permission to write outside the view. Bad signature/entries/extents still refuse;
  an unreadable MBR is I/O failure. Software may reuse portable `host/port/` layout
  code or an equivalent, tested against the independent recognition cases.
- `flush` returns success only after the card has left the busy state (engine-api §3).
- This WP-17 slot is the **work** slot, so it binds `write`. The read-only source slot,
  bound with `write == NULL` (guardrail 06), arrives with WP-18.
- **One block per device call is allowed for now.** Write batching stays off until the Q-P2-1
  any-subset coverage is complete (ADR-195 §4).

## 5. Play path

- Mount Side A (or B) with `tape_mount`; render with `tape_render` into the audio output
  buffer; refill the play ring with `tape_service` outside the audio interrupt. Follow
  engine-api §6.3 for the render loop and §11 for boundaries.
- Output at 44.1 kHz, 16-bit stereo over I²S to the SGTL5000 headphone output. The headphone
  volume cap is a WP-19 criterion. **Until it lands, the bench output is set to a fixed low
  level, and nobody wears headphones on the bench without a volume check.**
- **Play** starts rendering from the current position. **Stop** stops rendering and keeps the
  position. Pulling the cartridge stops audio, and the firmware unmounts cleanly when it can.
  Resume follows the spec's resume-position criterion when WP-17 reaches it.
- End of tape: audio stops at `at_end`. LED behaviour arrives with WP-20.

## 6. Acceptance mapping (criteria in spec/acceptance.md and CLAUDE.md)

| # | Criterion | How it is shown |
|---|---|---|
| F1 Goldens on target | At 1.0×, the firmware's rendered PCM for the seven normal-rate WP-11 cases is **byte-identical** to the reference PCM | Prepare the exact MANIFEST side, position and frame count. Stream PCM over USB for exact comparison, or hash the extracted PCM payload on both sides. `SHA256SUMS` authenticates whole reference WAV files; it is not a raw-PCM digest. Negative control: an altered sample or ±1 Q16.16 rate unit must fail |
| F2 Budgets | RAM (.data + .bss + instance) ≤ 200 KiB; stack ≤ 8 KiB; engine .rodata ≤ 32 KiB (guardrail 08) | Map-file sizes printed in CI; stack high-water from a painted stack on target. Negative control: an injected oversized static must fail the gate |
| F3 Warm instant-on | Wake from sleep with a mounted cartridge to first non-silent frame < 100 ms (guardrail 04) | Firmware-timed with the MCU cycle counter, wake interrupt to the first non-silent frame handed to I²S, printed on serial; Michael's verdict in MICHAEL-CHECKS decides (ADR-208). Negative control: an injected 150 ms delay must log ≥ 150 ms |
| F4 Commit latency | Synchronous `tape_commit` at `TAPE_MAX_ENTRIES` < 200 ms on the slowest candidate card | Firmware-timed `tape_commit` duration and ring underrun count, logged during WP-18/19 recording; zero underruns is strict, Michael judges dropouts (ADR-208). Listed here because it uses the WP-17 port |
| F5 Play/Stop and removal | Play renders, Stop holds the position, removal stops audio without corrupting the card (`tapectl verify` OK afterwards) | Michael's witnessed bench record plus `verify` output |
| F6 No engine change | `engine/` tree equals `d96b4245` | CI tree check |

F1, F2 and F6 run without bench hardware (F1's host half and F2's static sizes in CI). F3,
F5 and the target halves need the bench.

F1's seven cases are `play-1x-quiet`, `play-1x-fortissimo`, `splice`, `overdub`,
`overwrite`, `reset-b`, and `promote`. The three `scrub-*` cases retain their actual
rates/schedule in `tests/golden/MANIFEST`; all ten original desktop/engine regressions
remain required and byte-unchanged. They are not ten firmware-at-1.0× vectors.
The host half proves the portable render path only, not target I²S output.
F2 reports engine .data/.bss plus caller instance once, separately from board/core
storage; static accounting does not pass the target stack criterion.

## 7. Independence

This is a port and consumer, not engine code. As with the desktop tools (ADR-158), Verification
authors the WP-17 acceptance tests from this contract in parallel, without reading the firmware,
and disposes Software's exact head. Structural Rule 1 still governs any engine change, and none
is licensed here.
