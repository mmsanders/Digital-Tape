# spec/acceptance.md — Acceptance criteria

> **STATUS: DRAFT-5. NOT FROZEN.** All fourteen DRAFT-4 findings dispositioned (PM Decisions 007).
> `tapefs-v1.md` §§1–8 and `engine-api.md` §§2–8, §12 are the **freeze candidate**; operations and the
> state matrix freeze at the first green WP-10 run. Hashes in `spec/VERSION.md` are authoritative.

**Revision:** DRAFT-5 · **Issued:** 4 Sep 2026 · **Owner:** Program Manager
**Supersedes:** DRAFT-4. Versioned in step with `tapefs-v1.md` and `engine-api.md`, and from DRAFT-5 that claim is **enforced by `spec/VERSION.md` and a CI gate** rather than asserted in a header.
**Incorporates:** V4-001…V4-014 per PM Decisions 007.

A work package is complete when its criterion below holds **and the Verification Lead has independently confirmed it** — not when the implementer says so. Criteria are stated so they can be checked, not argued.

---

## Stream 1 — Engine

| WP | Criterion |
|---|---|
| **WP-06** Block device, superblock, index commit | Format → mount → commit → unmount → mount round-trips on the file device. Every refusal path in `tapefs` §4.1 (all three phases) and §5.1/§5.2/§5.3 has a test that exercises it, including the six named below (WP-06a…WP-06f). `tape_commit` returns only after the final flush, writes **at most 97 blocks** and performs **exactly two flushes** (invariant 24) |
| **WP-06a** Effective writability *(V4-001)* | On a **writable** device carrying structurally valid **v1.1** media: mount succeeds, `tape_info.writable == false`, `version_minor == 1`. `arm`, `reset_b`, `promote` and `respool` return **`TAPE_ERR_READ_ONLY`**. `feed` and `commit` return **`TAPE_ERR_BUSY`** — the instance cannot reach the armed state, so `engine-api` §10's *Mounted, idle* row governs and `READ_ONLY` is not what a conforming engine returns there. Superblock repair is **skipped**, not refused: the mount returns `TAPE_OK` with `needs_repair` true. **Zero `dev_write` calls in every one of those cases**, counted by the simulator (invariant 23) |
| **WP-06b** Undefined field values *(V4-012)* | A CRC-correct superblock with `state = 2`, both copies identical, must return **`TAPE_ERR_UNSUPPORTED_STATE`** with zero writes and no repair. Same for `promote_stage = 2`. `state = 0` and `state = 1` remain the only accepted values |
| **WP-06c** Interval disjointness *(V4-002)* | Two entries whose half-open physical-frame intervals **overlap** must be refused at mount, including the minimal case: two one-frame entries at the same `(first_chunk_id, start_frame)`. Two entries sharing a **chunk** with **disjoint** frame ranges — the splice-trim shape — must be **accepted**. A Side B index referencing chunks Side A also references must be accepted. The check must complete without reading any chunk: assert zero chunk-region reads during mount |
| **WP-06d** Geometry | Refused at exact equality with the mirror block; accepted one block short. A superblock whose stored `total_chunks` differs from the value `GEOMETRY_OK` derives from its own `nominal_length_s` is **refused**. `version_major = 2` with one torn copy **writes nothing**. Both slots valid with equal sequence is refused |
| **WP-06e** Stale promote stage | Media left at `promote_stage = 1` by an injected crash between `tapefs` §9.3 steps 4 and 6 must remain **fully usable**: `tape_arm` succeeds (after clearing the stage), a recording commits, and a subsequent `tape_promote` completes rather than returning `TAPE_ERR_INCONSISTENT`. Assert `promote_stage == 0` on media after the first `arm`/`reset_b`/`respool`, and that **no index commit by `arm`'s recording path, `reset_b` or `respool` occurs on media with `promote_stage == 1`** (invariant 25a) — `tape_promote`'s own phase-2 commits at `tapefs` §9.3.2 steps 7–8 are the sole exception and must **not** be flagged, since `promote_stage` is 1 across exactly that window. Also assert that stage clearing happens **after** each call's own preconditions: `tape_arm` on Side A, `tape_arm` with `entries_free` insufficient, and `tape_respool` with no valid destination must each still perform **zero writes** on stage-1 media. The regression this guards is a one-power-loss, ordinary-use path that permanently disabled promote |
| **WP-06f** Both-side mount *(`tapefs` §4.2)* | A cartridge whose **Side A** index is unselectable fails the mount with that error **whichever side was requested**. A cartridge whose **Side B** index is unselectable mounts on **Side A** with `free_next == a_high_water`, and `tape_reset_side_b` from that mount recovers it — while a mount **requesting Side B** returns `TAPE_ERR_NO_VALID_INDEX`, and `tape_set_side(TAPE_SIDE_B)` on the Side-A mount returns the same. Without those two refusals the API reaches a mounted state with no live index for the mounted side. A Side-A mount of a cartridge with a recorded Side B derives `free_next` from **Side B's** live index, and a `respool`/`promote` issued from that Side-A mount allocates above it — asserted by the simulator, since the failure mode is allocating over Side B's live chunks |
| **WP-07** Allocator, copy-on-write Side B | `tape_reset_side_b` completes in < 1 s and **moves no chunk**. Fuzzing over 10 000 random edit sequences never produces a Side B **allocation or write destination** below `a_high_water`. Side B *references* below the mark are correct and must not be flagged — the oracle identifies ownership by allocation, not by chunk id. `free_next` after remount equals invariant 12's derived value. **Every committed index satisfies interval disjointness** — a trim that leaves two entries claiming one physical frame is a defect |
| **WP-08** Playback, seek, scrub | 1.0× playback bit-exact against `tests/golden/`. Every rate in the ramp table bit-exact. **`tape_seek(N)` followed by `tape_render` emits frame `N` as its first output**, asserted at every run boundary and at ±1 frame around it *(V4-010)*. The `engine-api` §6.2/§6.3/§8 algorithms are the only implementation of the arithmetic. Required boundary cases: **one-frame timeline at `rate_q16_16 = INT32_MAX`** must clamp at `max_pos`, not overshoot *(V4-009)*; zero-frame timeline; `rate_q16_16 = 0`; reverse from `position == max_pos` snaps to the last frame and emits it; reverse from 0 emits frame 0 once then stops; reverse at the most negative rate does not wrap position |
| **WP-09** Record modes | Overwrite, overdub, splice each match their golden WAV. Overdub of full-scale against full-scale saturates at ±32767/−32768, never wraps. Splice at t=0, mid-run, exact run boundary and end all validate per `engine-api` §11. `tape_seek` and `tape_set_rate` while armed both return `TAPE_ERR_BUSY` |
| **WP-12** Re-spool | After a completed pass, the side is exactly one entry and renders bit-identically. **Invariant 10 holds at every write**, asserted by the simulator: no write destination ever intersects the live set of either side. The corrected V3-003 case — `a_high_water = 10`, one live B entry spanning chunks 10–11 so `len = 2` and `free_next = 12` — must send pass 1 to `[12, 14)` and then **run** pass 2 back into `[10, 12)`, reclaiming both chunks. A second case in which no lower run of `len` chunks exists must **decline** pass 2 and leave the cartridge compacted and intact. Both destinations must satisfy the `≥ a_high_water` floor as well as disjointness. **Re-spool of an empty Side B returns `TAPE_OK` with `*more_work == false` and zero writes, leaving a valid zero-entry index** *(V4-005)*; the same input to `tape_promote` must return `TAPE_ERR_INVALID_ARG` with zero writes, and the suite asserts both in one test so the asymmetry is deliberate and visible. Insufficient free space returns `TAPE_ERR_CARTRIDGE_FULL` and changes nothing |
| **WP-12a** Long-operation contract *(V4-007)* | For each of `respool`, `promote` and `dup`: a budget smaller than the work must be driven to completion by **repeated calls to the same function**, and the loop must terminate. While one is in progress, calls to the **other two** return `TAPE_ERR_BUSY`, and `abort`, `unmount`, `seek`, `set_rate`, `arm`, `feed`, `commit`, `set_side` and `reset_b` return `TAPE_ERR_BUSY` — **all forty-five cells of the three in-progress rows exercised**, which is what `engine-api` §10 claims and DRAFT-4 tested nowhere. `render` and `service` must stay allowed and audio must not stop. A continuation call with any argument changed except `block_budget`/`more_work`/`cb`/`user` returns `TAPE_ERR_INVALID_ARG`, does no work, and leaves the operation in progress. **A continuation returning `TAPE_ERR_IO` must set `*more_work = false` and return the instance to Mounted-idle** — injected by failing the device mid-operation, then asserting `tape_unmount` succeeds rather than returning `TAPE_ERR_BUSY` forever. **Conversely, a `TAPE_ERR_BUSY` returned to any of those other calls must leave the operation running**: after each of the forty-five `B` cells, the next continuation call must still advance the same operation and must not restart it — asserted by counting chunk-region writes across the whole loop |
| **WP-13** Embedded readiness | `.data + .bss + tape_instance_size()` ≤ 200 KiB summed — the same single gate `engine-api` §4 states, not a separate ceiling on the instance alone; `.rodata` ≤ 32 KiB; no allocator symbol links; stack ≤ 8 KiB by call-graph analysis; no indirect call outside `dev.h`; **no engine-owned state outside the caller's `mem` block** (invariant 19). All six as CI gates, green. **The gate reports the measured `tape_instance_size()` in its output**, so the §5.1 disjointness scratch shows up as a number rather than as a surprise |
| **WP-36** Slot capability | Fuzzing over 100 000 random transport input sequences against a source-slot device with `write == NULL` produces zero calls to `dev_write` on that device. The debug assertion never fires |

## Stream 2 — Verification

### WP-10 — Crash injection

Power loss injected at **every** write boundary, and torn writes at every block write, across a scripted session covering format, load, play, overwrite, overdub, splice, commit, reset B, re-spool (both passes), promote (all boundaries in `tapefs` §9.3.4), **the stage-clearing superblock write that `arm`/`reset_b`/`respool` perform on stage-1 media** (`tapefs` §8), and duplicate. **Exhaustive, not sampled** — the injection-point count is reported.

**Universal assertions, after every injection:**

- No allocated chunk is unreachable from the live index **beyond what `tapefs` §7 permits**. Precisely: `free_next` equals `max(a_high_water, max over live-B entries of last + 1)`. **Chunks superseded by an overwrite are expected to be unreachable and must not be reported** — they are the format's only sanctioned leak and re-spool reclaims them. *(DRAFT-2's blanket reachability assertion contradicted the allocator and would have failed every ordinary overwrite; V3-014.)*
- The live index of each mountable side passes `tapefs` §5.2 in full, **including interval disjointness**.
- Referenced audio is intact for whatever generation is selected.
- **`promote_stage` on media is 1 only in the states invariant 25 permits**, and any mount with `promote_stage == 1` matches exactly one row of §9.3.3 — a mount that matches none must return `TAPE_ERR_INCONSISTENT`, and the suite must contain a deliberately corrupted case that does.

**Per-operation allowed-state sets.** DRAFT-2 required "remount succeeds, Side A byte-identical to session start" for every injection, which contradicts what duplicate, format and promote are specified to do (V3-013). Each operation now has its own oracle:

| Operation | Permitted outcomes after any injection |
|---|---|
| Play, seek, scrub | No change to either side |
| Overwrite, overdub, splice, commit | Side A unchanged (referenced frames). Side B is **exactly** the pre-operation or post-operation generation, never between |
| Reset B | Side A unchanged. Side B is the pre- or post-reset generation |
| Re-spool | Side A unchanged. Side B renders bit-identically to before, in either the pre-pass or post-pass layout. **Never a layout referencing overwritten chunks** |
| **Promote** | Side A and Side B are each one of the **eleven** enumerated rows in `tapefs` §9.3.4 — including the mixed pair from a crash between steps 3 and 4, **the A-low/B-high pair from a crash between steps 7 and 8, and the both-low/old-high-water state from a crash between 8 and 9** *(V4-003)*. All referenced audio intact in whichever generation is selected. **Side A is not required to be byte-identical to session start; a completed promote changes it by design.** Empty Side B returns `TAPE_ERR_INVALID_ARG` having written nothing |
| **Promote, `S == 0`** *(the first-use path)* | Format, record onto the empty Side B, promote. Adopt-in-place gives `S = 0`, so **every** injection between steps 4 and 6 must match **exactly one** row of §9.3.3 — row 1 — and resume to the completed layout via step 5's decline. Invariant 25's "exactly one row" is asserted here specifically, because this is where DRAFT-5's first cut had two rows matching the same media |
| **Promote, stored position** | **Every `tape_promote` returning `TAPE_OK` clears the stored `(uuid, A)` and `(uuid, B)` positions** — asserted on the full path, on the step-5 decline, on a resume entering at step 8 and at step 9, and on the NOTHING TO DO classification — on the **terminal** call only (`*more_work == false`), so an incremental promote does not rewrite the position table on every continuation. The last of those is the one that matters most: a crash between the final superblock write and the position clear leaves media complete but positions stale, and the re-run that has to clean it up is exactly the call that commits nothing |
| **Promote, re-run** | From **every** row of §9.3.4, a repeated `tape_promote` must reach the completed state **without performing a second chunk copy where the table says none is needed**, asserted by counting chunk-region writes. Two cases are mandatory: **(a) exact tail capacity** — a cartridge with exactly `len` free chunks above the original `free_next`, crashed between phase-1 steps 3 and 4, must complete via adopt-in-place and must **not** return `TAPE_ERR_CARTRIDGE_FULL` *(V4-004)*; **(b) repeated crashes at that same boundary** must not consume successive staging runs — free-chunk count is asserted non-decreasing across the retries |
| **Duplicate, destination shape** *(`tapefs` §9.5)* | A completed copy has `a_high_water == ⌈src_A.total_frames / CHUNK_FRAMES⌉`, Side A compacted to `[0, a_high_water)`, `sb_generation == 1`, A0 at `side = 0`/`sequence = 1` and B0 at `side = 1`/`sequence = 2`. **The destination must mount on Side B as well as Side A** — a B0 written with `side = 0` fails §5.2 and would leave the copy with no usable sandbox. **Three mandatory regressions:** (i) the copy **mounts** — a destination whose `a_high_water` was left stale or zero fails §5.2's Side A bound and is unusable; (ii) a **layout-preserving** copy is rejected by construction — copy a fragmented C-90 source onto a C-60 destination that passes the capacity precondition and assert no chunk id ≥ destination `total_chunks` is ever addressed; (iii) **reusable destination** — pre-load the destination with a valid A0 at `sequence = 500` for a *different* cartridge, run `tape_dup`, and assert the mounted audio is the source's, not the old cartridge's. That last one is silent data substitution, not a crash |
| Duplicate | **Source unchanged, always** — absolute. Destination is the pre-copy cartridge, `TAPE_ERR_INCOMPLETE`, `TAPE_ERR_BAD_MAGIC` if it was blank and crashed before the final superblock, or the completed copy with its fresh UUID, `sb_generation == 1`, and a Side B mirroring its new Side A. **Each of the four preconditions — aliasing, read-only destination, geometry, capacity — writes nothing at all** (invariant 18), and a destination failing more than one must return the error the `tapefs` §9.5 order specifies *(V4-006)*. **The re-run path must be exercised**: after an interrupted copy, calling `tape_dup` again on the same destination *device* must complete it |
| Format, reusable media | The old cartridge unchanged, `TAPE_ERR_INCOMPLETE`, or the new empty cartridge. **A raw device failing `GEOMETRY_OK` is refused with `TAPE_ERR_GEOMETRY` and zero writes, before any block is destroyed** *(V4-006)* |
| Format, blank media | The above, **or `TAPE_ERR_BAD_MAGIC`** — before step 4's flush no valid superblock has ever existed and remount cannot succeed. This is the single permitted "does not mount" case in the whole suite. **After step 4's flush and before step 5, the permitted outcome is the new empty cartridge** — exactly one structurally valid superblock, both empty indices durable. On the harness's writable device phase 3 repairs the primary and **`needs_repair` must be false**; the `needs_repair == true` form of this state is asserted on a read-only device instead *(V4-014)* |

### WP-11 — Golden suite and runner

One command runs everything. Comparison byte-exact, **no tolerance** (ADR-016). A failure emits an audible-difference WAV plus first differing frame, channel, both values, delta, count and peak. Fixtures are generated once, listened to by a human, and committed; regeneration requires logged PM approval.

**Goldens may not be frozen until three things are true**, all of which DRAFT-5 supplies and none of which DRAFT-4 did: the render phase convention (`engine-api` §6.3), the portable negative-interpolation rule (§8), and the checked warm-range arithmetic (§5).

**Portability gate *(V4-013)*.** The `engine-api` §8 interpolation must be proven equal to the arithmetic-shift result over the **full** `(b − a, f)` domain — `b − a` across `[−65535, 65535]`, `f` across a exhaustive-by-construction sweep including 0, 1, 0x7FFFFFFF, 0x80000000 and 0xFFFFFFFF — and the golden suite must run green on **at least two toolchains**, one of them the embedded target. A single-toolchain green is not evidence of portability, which is the whole point of the finding.

**Mutation testing before each phase gate.** Seven mutations, each caught:

1. Off-by-one in a chunk boundary calculation.
2. Index commit written *before* the chunks are flushed.
3. `sequence` not incremented on commit.
4. CRC computed over the wrong byte range.
5. A Side B **allocation** permitted one chunk below `a_high_water` *(the allocation, not a reference — see WP-07)*.
6. Saturating clamp replaced with a plain cast, so overdub wraps.
7. **Warm-start buffer accepted for the wrong `(uuid, side, frame range)`.** Fixtures must include `start_frame` near `UINT32_MAX` with non-zero `valid_frames`, `valid_frames == 0`, and `data_bytes` one byte short of `valid_frames × 4` — the arithmetic maxima that make this mutation catchable at all *(V4-011)*.

Any mutation the suite does not catch is a coverage gap and a finding of equal weight to an engine bug.

---

## Cross-stream — the specs themselves

| Gate | Criterion |
|---|---|
| **Spec bundle integrity** | `spec/VERSION.md` lists every spec file with its revision and SHA-256. CI fails if any spec file's hash differs from the manifest, or if the three revision strings are not identical. **This gate exists because on 4 Sep `main` published `tapefs-v1.md` at DRAFT-3, `engine-api.md` at DRAFT-3 and `acceptance.md` at DRAFT-1** — three documents that each claimed in their own headers to be versioned in step. Nothing checked, so nothing caught it. Third silent-desync incident on this project; first one with a mechanism |

---

## Firmware criteria referenced by the specs

| Behaviour | Criterion |
|---|---|
| **Commit latency** *(V4-008)* | Worst-case wall time of a synchronous `tape_commit` at `TAPE_MAX_ENTRIES`, measured on the bench build against the slowest candidate card: **< 200 ms**, and in every case less than the play ring's depth (~372 ms). This number is what makes `engine-api` §7.1's "bounded" a fact rather than an assumption. A card that misses it is a card-selection finding, not a licence to make commit incremental |
| **Instant-on, warm** | Wake from sleep with a mounted cartridge to first rendered non-silent frame: **< 100 ms**, measured on the bench build with a logic analyser on I²S |
| **Warm-start validity** | The retained ring is passed as a `tape_warm_start` descriptor with correct `uuid`, `side`, `start_frame`, `valid_frames` and `data_bytes`. A deliberately mismatched descriptor must produce `warm_start_used = false` and a correct, silent-free mount — **not** audio from the wrong cartridge |
| **Instant-on, cold** | Card init begins within 20 ms of the cartridge-detect switch closing. Play pressed 1 s after insert produces audio within 100 ms of the press |
| **Resume position** | Checkpoint to device flash every 10 s of playback and on every transport state change. After abrupt removal, resume lands in `[T − 12 s, T − 2 s]` where **T is the true position at the moment of removal** — not the checkpoint. Measuring against the checkpoint would admit a 10 s error the specified algorithm cannot produce and would fail to catch a cadence regression. Table holds 64 `(uuid, side)` entries, LRU. Promote clears both entries for that UUID; reset B clears `(uuid, B)` |
| **Scrub ramp** | Rate schedule driven into `tape_set_rate`: 4.0× at t=0, linear to 12.0× at t=1.5 s, hold. Reverse mirrors with negative rates. Scrub goldens drive this exact table |
| **Record light** | Colour from `tape_status().entries_free` as a fraction of `TAPE_MAX_ENTRIES`: **green** ≥ 25 % free, **yellow** < 25 %, **red** at 0 — and at 0 the record button does not hold. Off while not armed |
| **End of tape** | `at_end` releases the play button within 50 ms |
| **Cartridge full mid-record** | On `TAPE_ERR_CARTRIDGE_FULL`, firmware stops the transport, releases the buttons, and commits. The recording up to that point is present on the next mount |
| **Output cap** | Codec output limited in the volume register to the level producing 85 dB SPL on the specified reference headphones, re-asserted every boot, unreachable from any user control. SPL meter and coupler, **witnessed by Michael** |
| **Copy progress** | LED row position reflects `blocks_done / blocks_total` from the progress callback; never a timer |

---

## Media atomicity — the format's one physical assumption

`tapefs` §8 and §13 rest on a 512-byte SD block write being atomic under power loss. It is true of essentially every card in practice and is not universally guaranteed, and DRAFT-4's first cut cited a work package (WP-19) that does not exist in this document — so the format's single load-bearing physical assumption had no acceptance criterion at all.

**Criterion.** On each candidate card SKU, with the card powered from a switched supply: write a known 512-byte pattern to a fixed block, cut power at randomised offsets inside the write window, then re-read. Across at least 1 000 cuts per SKU, every read must return **either** the previous content **or** the new content in full — never a mixture. A single torn block is a blocker finding and forces a format change, not a firmware workaround.

Run during **WP-05** card characterisation, on the same cards bought for the sustained-write measurement. Results recorded per SKU with revision, alongside the write-speed numbers.

> **WP-04, WP-05, WP-22 and WP-26 are hardware work packages and are defined in `claude/digital-tape-player-plan.md`, not here.** This document defines WP-06…WP-13 and WP-36 only. Saying so explicitly because DRAFT-4 cited a work package that existed nowhere, and a reader had no way to tell the difference between that and a cross-document reference.

---

## Hardware safety limits (PM-owned; measurements live in `spec/hw/`)

**These state limits, not mechanisms.** DRAFT-1 named the charger's NTC input as the means of enforcing the charge window, which over-constrained a limit into an implementation no candidate part could meet. How a limit is met is the Hardware Lead's choice; *that* it is met, in hardware and not defeatable by firmware, is not.

| Limit | Value |
|---|---|
| **Charge window** | Charging suspended below 0 °C or above **45 °C** cell temperature. Enforced in hardware; firmware cannot override. Mechanism is the Hardware Lead's — a TS network designed so 45 °C maps to the charger's hot-suspend threshold, a part with a suitable threshold, or a series cutoff. **Note:** a BQ25896's native hot *suspend* is T5 ≈ 60 °C; T3 ≈ 45 °C only drops charge voltage 200 mV ([TI datasheet](https://www.ti.com/lit/ds/symlink/bq25896.pdf)). Verified by sweeping cell temperature across both thresholds |
| **Solenoid — single pulse** | Bounded in hardware to the shortest duration that reliably releases the latch, plus stated margin. **The number comes from WP-04/WP-22 measurement, not from this document.** Verified by holding the gate high and measuring coil current |
| **Solenoid — sustained power** | **Average coil power ≤ 0.25 W over any rolling 10 s window**, enforced in hardware, not defeatable by firmware. Stated as power because power is what damages a coil. The limit must sit above the fastest legitimate use — a child alternating stop and play about twice a second — and below the coil's continuous rating; if those do not leave a gap the answer is a shorter pulse or a lower-power coil, not a looser limit. Verified by driving the gate at 100 Hz continuously: average coil power must fall to and stay at or below the limit within 2 s. Component values and worst-case tolerance are part of the deliverable before WP-26; a PPTC is a third-layer backstop and may not be the element establishing this bound |
| **Worst-case thermal** | Charge at full rate + copy + all LEDs for one hour: no external surface above ambient + 15 K; cell surface below 45 °C. **Junction temperatures of the charger, regulator and MCU reported individually**, not inferred from a lumped enclosure model — a 30 s copy is a transient the lumped model does not resolve. Witnessed by Michael |
| **Deep-discharge latch** | Hardware load switch disconnects the cell below ~3.2 V, released by charger insertion. Must not add perceptible latency to wake-from-sleep; if it does, escalate rather than trading against instant-on |
