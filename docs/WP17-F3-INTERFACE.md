# WP-17 F3 warm wake: interface declaration (F3-IF/1)

**Software Lead declaration for [#674](https://github.com/mmsanders/Digital-Tape/issues/674),
10 November 2026.** This is the public interface that V398's
[BINDING-NEEDED](https://github.com/mmsanders/digital-tape-verification/blob/9aa2716ac82a6f614d4743790b55b42a28b21e1f/tests/wp17_hands_on_r1/BINDING-NEEDED.md)
asks for before any F3 code is written.
- Items 1–5 there are answered in §2–§7 below.
- No firmware, checker or host code comes with it.
- Verification may bind tests to this document, FW-1 and ADR-208/209. A change after
  Verification publishes is `F3-IF/2`, returned to #674, not a silent edit.

**Authority and scope.**
- Normative authority stays with FW-1 §6 (F3), guardrail 04, engine-api §5 (warm start)
  and ADR-208/209.
- This declaration only narrows how the bench shows F3.
- It does not change `engine/` (pinned `d96b4245`), BE1-IF/3, the cleared BE-1 checker
  (`44050059`) or helper (`9929ef5f`), or any imported package.
- BE1-IF/3 keeps F3 `NOT_RUN` (`f3_method_pending`) and F4 `NOT_RUN` (`f4_deferred`).
- F3 gets its own new, separately bound route (§6). F4 is **reserved only** (§8).
- No recording, copy or new hardware scope.

## 1. What is being timed

FW-1 F3: wake from sleep with a mounted cartridge to the first non-silent frame,
under 100 ms (guardrail 04).
- The firmware times it with its own MCU counter and prints it on serial.
- Michael's MICHAEL-CHECKS verdict decides (ADR-208).
- Nothing here is an external timing qualification, and no instrument is required.

### 1.1 Bench warm sleep

Warm sleep uses the engine's own warm-start mechanism (engine-api §5; guardrail 04:
retained warm buffers belong to the caller). The firmware gains one static caller-owned
buffer:
- `fw_warm_pcm`: `FW_WARM_FRAMES = 8192` stereo s16 frames, 32 768 bytes (about 186 ms).
- It is board storage, outside the engine RAM sum that F2 counts. The F2 report lists it
  separately.

The `sleep` command (§3) runs this exact sequence:
1. Refuse unless a card is `MOUNTED` and the player is stopped.
2. Read `P` with `tape_tell`.
3. Render ahead, through the public API only, into `fw_warm_pcm`:
   - `tape_seek(P)`, then `tape_set_rate(1.0×)`;
   - alternate `tape_service` and `tape_render` until 8192 frames are rendered, or a short
     render ends the side;
   - `tape_set_rate(0)`.
   - `W` is the number of frames rendered. Nothing is mixed, rated or computed outside the
     engine (guardrail 12).
4. `tape_unmount`. The position it returns is printed, but the resume point is `P`, not
   that value.
5. Build the descriptor `{data = fw_warm_pcm, data_bytes = 32768, valid_frames = W,
   start_frame = P, uuid, side}`.
   - `uuid` comes from `tape_get_info` before unmount, and `side` is the mounted side.
   - `start_frame` is 32-bit in the API. If `P > UINT32_MAX` or `W == 0`, the firmware
     passes `NULL` (a cold wake), and the WAKE line reports `warm 0`.
6. Arm the wake triggers (§1.2), print the `SLEEP` reply (§3), and idle:
   - `WFI` between interrupts;
   - CPU clock unchanged (no frequency scaling);
   - the SGTL5000 stays powered at the fixed FW-1 low level, and the I²S output carries
     silence;
   - the card stays powered and inserted.

**This is `sleep_level bench-idle`.** A production low-power state is a later hardware
decision and is not declared here; that state may gate clocks, power down the codec or
cut card power. A deeper level would be `F3-IF/2`, with its own binding (PM question Q1, §9).

### 1.2 Trigger, start event and end event

| Item | Declaration |
|---|---|
| Trigger `button` | The first falling edge on `PIN_PLAY` (pin 2) while asleep. A pin-change interrupt is attached at step 6 and detached at wake. There is no debounce on this edge. This is the trigger for Michael's check |
| Trigger `serial` | The `wake` command line (§3), completed while asleep. It is recorded and reported, but it is a **diagnostic only**: an F3 candidate observation needs `button` (§6) |
| Start event `wake_interrupt` | `t0`: `DWT->CYCCNT` and `millis()` read **first** in the pin-change ISR, or for `serial`, when the `wake` line is parsed |
| Wake path | After `t0`, with no `WFI` until the measurement closes: (control build only: the §5 delay) → `tape_mount(side, P, &warm or NULL)` → `tape_set_rate(1.0×)` → rendering starts in the audio interrupt. There is **no `tape_seek` and no pre-service**, which would discard the warm ring. The main loop then runs `tape_service` as in normal play |
| End event `first_non_silent_frame_handed_to_i2s` | `t1`: in the audio interrupt, after `fw_player_render` fills a block and **before** `transmit()`. It is the first block since `t0` that contains any non-zero sample on either channel. `t1` reads `DWT->CYCCNT` and `millis()` |
| Diagnostic `first_engine_block` | `te`: the first block since `t0` in which `tape_render` produced at least one frame, even if every sample is zero. This separates a silent passage at `P` from a slow wake |

**Not counted, stated so Michael's verdict covers them:**
- the pin-to-ISR latency before `t0`;
- the Teensy Audio I²S DMA and codec latency after `t1` (up to two 128-frame blocks,
  about 5.8 ms);
- button bounce.

The measurement is the firmware's own observation, not an external qualification.

**Timeout.** If no non-silent block arrives within 2000 ms of `t0` by `millis()`, the
firmware closes the measurement with `status timeout`. Silence at `P` is a setup fault
and is reported, never hidden. Bench procedure: put the stop position inside audible
material.

## 2. Timer encoding, conversion, rounding and wrap

| Field | Rule |
|---|---|
| Counter | ARM DWT `CYCCNT`, 32-bit, enabled at boot. It is read only while the core runs: `t0` is taken in the ISR after wake, and nothing executes `WFI` until `t1` |
| `cycles` | `(t1 − t0) mod 2^32`, as an unsigned 32-bit difference |
| `cpu_hz` | `F_CPU_ACTUAL` at `t0`. It must be equal at `t1`; a change is `status clock_changed` |
| `elapsed_us` | `ceil(cycles × 1 000 000 / cpu_hz)`, computed in unsigned 64-bit. **Rounded up**, so the conversion can never under-report. 149 999.5 µs prints as 150 000 |
| `millis` | `millis(t1) − millis(t0)`, unsigned 32-bit: an independent coarse cross-check |
| Wrap | One wrap of `CYCCNT` takes `2^32 / cpu_hz` seconds, 7.158 s at 600 MHz. If `millis ≥ 7000`, the cycle difference may have wrapped, and the firmware prints `status wrap` with `elapsed_us` and `cycles` as `-`. With the 2000 ms timeout this cannot happen on a working build; it is declared so a fault cannot fake a short time |
| Cross-check (checker) | For `status ok`: `|elapsed_us − millis × 1000| ≤ 2000`, otherwise `MISMATCH timer_inconsistent`. 2000 µs covers two 1 ms ticks of `millis` granularity |
| `engine_us` | The same conversion for `te − t0`, or `-` if no engine frame arrived. Diagnostic only |

Integers are unsigned decimal ASCII with no separators, signs or leading zeros (`0` is
`0`).

## 3. Serial grammar additions

Existing BE1-IF/3 lines, commands and the boot sequence are **unchanged**. The new lines
below are printed **only** in reply to the three new commands, so a BE-1 session that
never sends them produces a transcript the cleared BE-1 checker still accepts. Line
endings, ASCII-only text and the `<u>`/`<i>`/`<hex64>` tokens follow BE1-IF/3 §3. `<hex32>`
is 32 lowercase hex digits and `<hex40>` is 40.

| Command | Reply lines, in order |
|---|---|
| `build` | `BUILD …` (below) |
| `sleep` | `BUILD …`, then `SLEEP 0 position <u> unmount_position <u> warm_frames <u>`. Refusals: `ERR usage or no mounted card` (no card); `SLEEP REFUSED playing`; `SLEEP <i> …` with a non-zero engine code if the render-ahead or unmount failed (the card is then dropped as `CARD GONE service failed`) |
| `wake` | Only while asleep; otherwise `ERR not asleep`. Sets trigger `serial` |

```
BUILD id <hex32> commit <hex40> dirty <0|1> env <name> inject_us <u> cpu_hz <u> warm_frames_max <u>
WAKE trigger <button|serial> status <ok|timeout|wrap|clock_changed|mount_failed> elapsed_us <u|-> cycles <u|-> cpu_hz <u> millis <u> engine_us <u|-> warm <0|1> mount <i> position <u> inject_us <u> id <hex32>
```

`WAKE` is printed from the main loop once the measurement closes, after which the player
continues in normal play (Stop works as before).
- `warm` is `tape_info.warm_start_used` after the mount.
- `mount` is the `tape_mount` result.
- `position` is `P`.
- `id` repeats the build id.
- `mount_failed` is used when `tape_mount` returns non-zero. The card is then dropped as in
  BE1-IF/3.

## 4. Build identity and binary linkage

No firmware hashes itself.
1. A PlatformIO pre-build script, `firmware/bench/tools/build_id.py`, computes:
   - `commit`: `git rev-parse HEAD`;
   - `dirty`: 1 if `git status --porcelain` lists anything outside `firmware/bench/.pio/`;
   - `id`: 16 random bytes as 32 hex, from the host CSPRNG, new for every build.

   It passes them, with the env name and `inject_us`, as defines.
2. The image contains exactly one ASCII marker, in `.rodata`:
   `DTBUILD id=<hex32> commit=<hex40> dirty=<0|1> env=<name> inject_us=<u>`.
3. A post-build step writes `build.json` beside `firmware.hex`
   (schema `digital-tape/fw-build/1`):
   `{schema, id, commit, dirty, env, inject_us, engine_tree, toolchain{…five BE1-IF/3 pins},
   firmware_hex_sha256, firmware_elf_sha256}`.
   - The hashes are computed by the host after linking.
   - `engine_tree` is `git rev-parse HEAD:engine`.
4. **Linkage the checker enforces:**
   - `sha256(firmware.hex) = build.json.firmware_hex_sha256`;
   - the Intel-HEX-decoded image contains the §4.2 marker exactly once, with fields equal
     to `build.json`;
   - every `BUILD` and `WAKE` line in the attempt's capture carries the same `id`, and
     `BUILD` carries the same `commit`, `dirty`, `env` and `inject_us`;
   - `engine_tree = d96b4245e04d74078f8938744b1394c3018516f7`;
   - the toolchain equals the five BE1-IF/3 pins;
   - a candidate needs `dirty 0`.

   A rebuild of the same commit gets a new `id` and a new hash. Evidence binds the exact
   artifact flashed, never "the commit".

## 5. Controlled 150 ms delay seam

- **A build env only:** `teensy41_ctl_wake150`, defined `-DFW_WAKE_INJECT_US=150000`.
- The production env `teensy41` does not define it. The seam's code is compiled out
  (`#if`), and the symbol `fw_wake_inject` exists only in the control image.
- No command, pin or runtime value reaches it.
- **Behaviour:** immediately after `t0`, busy-wait on `DWT->CYCCNT` until at least
  `inject_us` has elapsed by the §2 conversion, then continue the wake path.
- **Marker:** `inject_us` is printed in `BUILD` and `WAKE`, and recorded in the `DTBUILD`
  marker and `build.json`; `env` names the control.
- **CI** (firmware-bench workflow) builds the control env and checks:
  - `arm-none-eabi-nm` finds `fw_wake_inject` in the control ELF and **not** in the
    production ELF;
  - the production `build.json` has `inject_us 0`.
- **Meaning:** the control proves the measurement can report a delay of at least 150 ms.
  - A control observation with `elapsed_us < 150000` is `MISMATCH`
    (`injected_delay_underreported`); 149 999 fails.
  - It is never an F3 candidate result and never a MICHAEL-CHECKS entry.
  - A control build's `WAKE` line offered as a candidate is `MISMATCH`
    (`control_build_as_candidate`).

## 6. Offline F3 route (new; BE-1 unchanged)

A new checker, implemented only after V405's binding is imported (§10):

```
python firmware/bench/tools/f3_evidence.py --offline BUNDLE --out REPORT.json
```

It has the same safety rules as the BE-1 checker:
- it opens no port, device or socket, and never flashes or provisions;
- it reads only `BUNDLE`;
- it writes only `REPORT.json`, created exclusively.

Exit codes:

| Exit | When |
|---|---|
| 0 | Every requested item is `CONSISTENT`, `CONTROL_DETECTED` or `NOT_RUN` |
| 1 | Any `NOT_ACCEPTABLE` or `PENDING_PM` |
| 2 | Any `INVALID` or `MISMATCH` |
| 64 | Usage |

**Bundle** `BUNDLE/manifest.json`, schema `digital-tape/f3-session/1`. Closed keys, as in
BE1-IF/3 §2: unknown keys are `INVALID field_unknown`.
- `session`: `id`, `kind` (`physical | simulation`), `timestamp`, `operator`,
  `capture_tool`.
- `candidate`: `build_id` (hex32), `firmware_hex_sha256`.
- `files`: path, sha256 and bytes. BE1-IF/3 §2 file rules apply unchanged: safe paths,
  every file listed, size and digest checked.
- `observations`: a list.

The bundle must contain `firmware.hex` and `build.json` for every build its observations
cite.

**Observation:**
- `id`, `sequence` and `superseded_by`/`supersede_reason`, as in BE1-IF/3;
- `provenance`: `actual | simulated | not_run`;
- `kind`: `candidate | control_wake150`;
- `capture`: the raw file from `bench_capture.py`, run **unchanged** as
  `--send sleep --until-interrupt --timeout 120` (§6 of BE1-IF/3), one file per attempt;
- `michael_check`: a record path (§7), for `candidate` + `actual` only.

**Checks per observation.** All run, and the worst outcome wins, as in BE1-IF/3 §4.
- The capture parses under BE1-IF/3 §3 plus §3 here.
- It contains exactly one `BUILD`, one `SLEEP 0` and one `WAKE`, in that order.
- `WAKE status ok`.
- §2 cross-check.
- §4 linkage.
- `kind` matches `env`/`inject_us`.
- A `candidate` needs `trigger button`.
- A `control_wake150` needs `elapsed_us ≥ 150000`.
- `warm 0` on a candidate is reported (`cold_wake`) but is not by itself a failure: F3's
  number is still measured. Warm-start validity is a separate acceptance row.

**States:** `INVALID`, `MISMATCH`, `NOT_RUN`, `PENDING_PM`, `NOT_ACCEPTABLE`,
`CONTROL_DETECTED`, `CONSISTENT`.
- Every report carries `accepted: false`.
- `physical_run` is true only for an `actual` observation in a `physical` session.
- `target_met` (`elapsed_us < 100000`) is reported but is not a verdict.
- `CONSISTENT` means artifact consistency. It is never acceptance or PASS.

**Retention.** Every attempt, including failures, timeouts, cold wakes and superseded
attempts, stays in the bundle with its own observation and raw capture. A superseded
`INVALID`/`MISMATCH` still counts in `overall` and the exit status, as in BE1-IF/3 §4.
Simulation can never make `physical_run` true.

## 7. MICHAEL-CHECKS record and normalization

Each check gets one row in `docs/MICHAEL-CHECKS.md`. The row starts with its record ID
`MC-<YYYYMMDD>-<n>`, where `n` is 1, 2, … within the day.

The bundle carries the machine-readable twin, `michael/<ID>.json`
(schema `digital-tape/michael-check/1`):

```json
{"schema": "digital-tape/michael-check/1", "id": "MC-20261201-1", "date": "2026-12-01",
 "criterion": "F3", "build_id": "<hex32>", "firmware_hex_sha256": "<hex64>",
 "log_sha256": "<hex64 of the raw capture file>", "tried": "free text",
 "logged": {"elapsed_us": 0, "millis": 0, "warm": 1},
 "verdict": "acceptable | not acceptable", "note": "string | null",
 "pm_disposition": null}
```

- **Transcription:** `logged` must equal the `WAKE` line exactly, as integers.
- **Identity:** `build_id`, `firmware_hex_sha256` and `log_sha256` must equal the
  observation's. Otherwise the outcome is `MISMATCH michael_record_mismatch`.
- **Verdict:** exactly `acceptable` or `not acceptable`, lowercase, with one space.
  `not acceptable` requires a non-empty `note`. Anything else is `INVALID verdict_value`.
- **Outcomes:**
  - `not acceptable` → `NOT_ACCEPTABLE` (a fast number does not save it);
  - `acceptable` with `elapsed_us ≥ 100000` → a recorded miss, which may pass under
    ADR-208.
- **Miss over 20%** (`elapsed_us × 5 > 600000`, that is, over 120 000 µs) requires:
  `pm_disposition = {"reference": URL, "build_id", "log_sha256", "elapsed_us"}`.
  - The reference is a PM issue comment or DECISIONS anchor.
  - All four fields must match, otherwise the outcome is `PENDING_PM`.
  - The checker matches fields only. Whether the reference is a genuine reviewed PM
    disposition is Verification's review, never a Product boolean.
- **What a verdict cannot waive:** zero commit underruns, the resume window, callback copy
  progress, tears or atomicity, counts and records, or cap margins. None of them are F3
  fields; F3 has no field that could waive them.
- **No record:** an `actual` candidate without a record stays `NOT_RUN`
  (`michael_check_absent`).
- **Never a record:** simulations and `control_wake150` observations are never MICHAEL-CHECKS
  entries. A record that cites one is `MISMATCH`.

## 8. F4 — RESERVED, not implemented

These names are reserved for the WP-18/19 recording contract. Nothing is built or
evaluated now, and the F3 checker reports F4 `NOT_RUN f4_deferred`.
- **Command** `commit`.
- **Reply line:**
  `COMMIT entries <u> ring_depth_frames <u> card <text> cycles <u> cpu_hz <u> elapsed_us <u> underruns_before <u> underruns_after <u> result <i> id <hex32>`.
- **Intended semantics:**
  - `entries = 4096` (`TAPE_MAX_ENTRIES`) on the declared slowest card;
  - `ring_depth_frames` is the actual record-ring depth;
  - `underruns_after − underruns_before` is the strict count across that synchronous
    `tape_commit`, and must be 0;
  - an absent count is not zero;
  - same timer rules as §2.

## 9. Open questions for PM, with safe defaults

| # | Question | Safe default used here |
|---|---|---|
| Q1 | Is `bench-idle` warm sleep (WFI, codec and card powered, caller warm buffer) the right depth for the WP-17 F3 check, or must the bench reach a deeper low-power state first? | `bench-idle`, labeled in every result. A deeper state is a new version with its own binding |
| Q2 | Is the Play-button edge the right trigger for Michael's check? | Yes. Serial `wake` is a diagnostic only |
| Q3 | Is the 8192-frame (186 ms) warm buffer acceptable? It adds 32 KiB of board storage outside the counted engine RAM | Yes. Size declared here; a change is a new version |

## 10. Order of work

1. This declaration, then Verification405 binds and publishes tests: the serial grammar,
   `f3_evidence.py`, and a host simulation of the measurement arithmetic (below).
2. Software imports V405's merged package unchanged in its own commit. **Only then** come
   the firmware hook, the `build_id.py`/`build.json` steps, the control env, the CI checks,
   `f3_evidence.py` and the first-board packet update.
3. **Host simulation seam**, for blind tests without hardware:
   `fwhost wake-sim SCENARIO.json` prints the exact `WAKE` line the firmware's portable
   measurement module would print.
   - Scenario keys: `cpu_hz`, `t0_cycles`, `t0_ms`, `inject_us`, `trigger`, `mount`,
     `warm`, `position`, `id`, and `blocks`.
   - Each element of `blocks` is `{cycles, ms, engine_frames, nonzero}`, in order, as the
     audio interrupt would hand them.
   - The same C module runs on the Teensy with the real `DWT->CYCCNT`/`millis()`.
4. No target run, flash, serial connection to a device or MICHAEL-CHECKS entry happens in
   this tranche.
