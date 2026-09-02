# spec/acceptance.md — Acceptance criteria

**Revision:** DRAFT-1 · **Issued:** 2 Sep 2026 · **Owner:** Program Manager (frozen with the format at the Phase 0 gate)

A work package is complete when its criterion below holds **and the Verification Lead has independently confirmed it** — not when the implementer says so. Criteria are stated so they can be checked, not argued.

---

## Stream 1 — Engine

| WP | Criterion |
|---|---|
| **WP-06** Block device, superblock, index commit | Format → mount → commit → unmount → mount round-trips on the file device. Every mount rule in `tapefs` §4.1 and §5.2 has a test that exercises its refusal path. `tape_commit` returns only after the final flush. |
| **WP-07** Allocator, copy-on-write Side B | `tape_reset_side_b` completes in < 1 s and moves no chunk. Fuzzing over 10 000 random edit sequences never produces a Side B run with `first_chunk_id < a_high_water`. `free_next` after remount equals the value derived from the live index, never a stored one. |
| **WP-08** Playback, seek, scrub | 1.0× playback is bit-exact against `tests/golden/`. Every scrub rate in the ramp table renders bit-exact. Seek to every run boundary ±1 frame lands on the specified frame. The interpolation formula in `engine-api` §8 is the only path — a second implementation of it is a defect. |
| **WP-09** Record modes | Overwrite, overdub, splice each match their golden WAV. Overdub of full-scale material against full-scale material produces ±32767/−32768, never a wrap. Splice at t=0, mid-run, run boundary and end all validate per `engine-api` §11. |
| **WP-12** Re-spool | After re-spool, Side B is exactly one entry and renders bit-identically to before. Invariant 10 (destination disjoint from live set) holds at every write, asserted by the simulator. Re-spool on a cartridge with insufficient free space returns `TAPE_ERR_CARTRIDGE_FULL` and changes nothing. |
| **WP-13** Embedded readiness | `tape_instance_size()` ≤ 200 KiB; `.rodata` ≤ 32 KiB; no allocator symbol links; stack ≤ 8 KiB by call-graph analysis; no indirect call outside `dev.h`. All five as CI gates, green. |
| **WP-36** Slot capability | Fuzzing over 100 000 random transport input sequences with a source-slot device whose `write == NULL` produces zero calls to `dev_write` on that device. The debug assertion in `dev_write` never fires. |

## Stream 2 — Verification (owed to the Verification Lead)

| WP | Criterion |
|---|---|
| **WP-10** Crash injection | For a scripted session covering format, load, play, overwrite, overdub, splice, commit, reset B, re-spool, promote (both phases) and duplicate: power loss is injected at **every** write boundary, and torn-write injected at every block write. After each, remount succeeds; Side A's referenced frames are byte-identical to the session start; Side B is either the pre- or post-operation state; no allocated chunk below derived `free_next` is unreachable. Exhaustive, not sampled — the count of injection points is reported. |
| **WP-11** Golden suite and runner | One command runs everything. Comparison is byte-exact with no tolerance (ADR-016). A failure emits an audible-difference WAV plus first differing frame, channel, both values, delta, count and peak. Fixtures are committed once, listened to by a human, and never regenerated without a logged PM approval. Mutation testing before each phase gate: the seven mutations in the Verification Charter §7 are each caught. |

## Firmware criteria referenced by the specs

| Behaviour | Criterion |
|---|---|
| **Instant-on, warm** | Wake from sleep with a mounted cartridge to first rendered non-silent frame: **< 100 ms**, measured on the bench build with a logic analyser on I²S. |
| **Instant-on, cold** | Card initialisation begins within 20 ms of the cartridge-detect switch closing. Play pressed 1 s after insert produces audio within 100 ms of the press. |
| **Resume position** | Checkpoint to device flash every 10 s of playback and on every transport state change. After abrupt removal, resume lands in `[checkpoint − 12 s, checkpoint − 2 s]`. Table holds 64 `(uuid, side)` entries, LRU eviction. Promote clears `(uuid, A)`; reset B clears `(uuid, B)`. |
| **Scrub ramp** | Rate schedule while a scrub button is held, driven into `tape_set_rate`: 4.0× at t=0, linear to 12.0× at t=1.5 s, hold. Reverse mirrors with negative rates. Golden fixtures for scrub drive this exact table. |
| **Record light** | Colour from `tape_status().entries_free` as a fraction of `TAPE_MAX_ENTRIES`: **green** ≥ 25 % free, **yellow** < 25 %, **red** at 0 — and at 0 the record button does not hold (the solenoid releases it). While not armed, the light is off. |
| **End of tape** | `at_end` from `tape_status` releases the play button within 50 ms. |
| **Cartridge full mid-record** | On `TAPE_ERR_CARTRIDGE_FULL`, firmware stops the transport, releases the buttons, and commits. The recording up to that point is present on the next mount. |
| **Output cap** | Codec output limited in the volume register to the level that produces 85 dB SPL on the specified reference headphones, re-asserted on every boot, unreachable from any user control. Verified with an SPL meter and coupler, witnessed by Michael. |
| **Copy progress** | LED row position reflects `blocks_done / blocks_total` from the progress callback; never a timer. |

## Hardware safety limits (PM-owned; measurements live in `spec/hw/`)

**These state limits, not mechanisms.** DRAFT-1 of this file named the charger's NTC input as the means of enforcing the charge window; that over-constrained a limit into an implementation and produced a criterion no candidate part could meet. Corrected below. How a limit is met is the Hardware Lead's choice; *that* it is met, in hardware and not defeatable by firmware, is not.

| Limit | Value |
|---|---|
| **Charge window** | Charging is suspended when cell temperature is below 0 °C or above **45 °C**. Enforced in hardware; firmware cannot override or defeat it. Mechanism is the Hardware Lead's — a TS network designed so 45 °C maps to the charger's hot-suspend threshold, a part with a suitable threshold, or a series thermal cutoff. **Note:** a BQ25896's native hot *suspend* is T5 ≈ 60 °C; its T3 ≈ 45 °C only drops charge voltage by 200 mV ([TI datasheet](https://www.ti.com/lit/ds/symlink/bq25896.pdf)). That part meets this limit only with a deliberately designed TS divider. Verified by sweeping cell temperature across both thresholds and observing charge current. |
| **Solenoid — single pulse** | Any single energisation ≤ 50 ms regardless of the gate input. Verified by holding the gate high and measuring coil current. |
| **Solenoid — duty** | Coil duty ≤ 5 % over any rolling 1 s window, enforced in hardware. Verified by driving the gate with a continuous 100 Hz square wave: average coil current must fall to ≤ 5 % of the energised value within 2 s and stay there. This is the retrigger-loop failure the one-shot alone does not cover — the Hardware Lead's finding, and the reason there are now two solenoid limits rather than one. Component values and worst-case tolerance analysis are part of the deliverable, before WP-26. |
| **Worst-case thermal** | Charge at full rate + copy + all LEDs for one hour: no external surface above ambient + 15 K; cell surface below 45 °C. **Junction temperatures of the charger, regulator and MCU reported individually**, not inferred from a lumped enclosure model — a 30 s copy is a transient the lumped model does not resolve. Witnessed by Michael. |
| **Deep-discharge latch** | Hardware load switch disconnects the cell below ~3.2 V, released by charger insertion. Must not add perceptible latency to wake-from-sleep (guardrail 04); if it does, escalate rather than trading against instant-on. |
