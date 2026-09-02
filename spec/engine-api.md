# spec/engine-api.md — Tape Engine API v1.0

**Revision:** DRAFT-3 · **Issued:** 2 Sep 2026 · **Status:** for adversarial review; not frozen
**Owner:** Program Manager. Changes require PM sign-off.
**Companion:** `spec/tapefs-v1.md` DRAFT-3, normative for everything on media.

C99. No operating system. No dynamic allocation, ever — not on firmware, not on desktop. No recursion. No libc file I/O. No floating point in the audio path. The only coupling to the outside world is the block device in §2.

---

## 1. The principle

> **The engine computes. The caller owns anything that needs entropy, hardware knowledge, or memory beyond the engine's budget.**

This has so far decided the warm-start buffer, the cartridge UUID, the format epoch, and the absence of any clock or timeout inside the engine. When a new question arises, apply it before asking.

A corollary the engine *does* own: **identity and validity are written last**, after the content they describe (`tapefs-v1.md` Rule 2).

---

## 2. Error codes

```c
typedef enum {
  TAPE_OK = 0,
  TAPE_ERR_IO,                 /* block device returned failure */
  TAPE_ERR_BAD_MAGIC,
  TAPE_ERR_CRC,
  TAPE_ERR_VERSION,            /* version_major != 1; nothing touched */
  TAPE_ERR_GEOMETRY,           /* superblock fails the tapefs §4.1 geometry checks */
  TAPE_ERR_INCOMPLETE,         /* superblock state == WRITE_IN_PROGRESS */
  TAPE_ERR_INCONSISTENT,       /* two valid copies, equal generation/sequence, different bytes */
  TAPE_ERR_NO_VALID_INDEX,
  TAPE_ERR_READ_ONLY,          /* write against write == NULL, or against Side A */
  TAPE_ERR_CARTRIDGE_FULL,
  TAPE_ERR_INDEX_FULL,
  TAPE_ERR_SEQUENCE_EXHAUSTED,
  TAPE_ERR_NOT_MOUNTED,
  TAPE_ERR_BUSY,               /* the state matrix in §10 forbids this call now */
  TAPE_ERR_UNDERRUN,           /* tape_render had less than requested */
  TAPE_ERR_INVALID_ARG,
} tape_result;
```

Every call returns `tape_result`. There are no error strings. There are no timeouts: the engine has no clock and must not acquire one.

---

## 3. Block device

```c
typedef struct {
  int (*read)(void *ctx, uint32_t lba, uint32_t count, void *dst);
  int (*write)(void *ctx, uint32_t lba, uint32_t count, const void *src);
  int (*flush)(void *ctx);
  void *ctx;
  uint32_t block_count;
} tape_dev;
```

Callbacks return 0 on success, non-zero on failure. `count` is in 512-byte blocks. **Every `tape_dev` is a block view of TAPEFS partition 2** — LBA 0 is the partition's first block. The engine never sees the MBR.

**`write` is `NULL` for a read-only device.** That is the entire mechanism for the source slot. There is no flag, no mode, no permission check. A write path that reaches a read-only device dereferences null and dies in test rather than corrupting a cartridge in the field.

`block_count` is caller-supplied and **untrusted**; `tape_mount` validates the superblock's geometry against it and refuses on mismatch.

`flush` must not return success until data has reached media.

**All indirect calls in the engine go through three `static inline` wrappers in one file** — `dev_read`, `dev_write`, `dev_flush` in `engine/src/dev.h`. Nothing else dereferences a `tape_dev` member; CI checks this at source level. `dev_write` asserts a non-`NULL` pointer **in debug builds only**; in release it dereferences.

Three implementations exist and the engine cannot distinguish them: file-backed (desktop), fault-injecting simulator (crash harness, with power-loss-after-N-writes and torn-write modes), real SD (firmware).

---

## 4. Memory

The caller owns all storage. The engine allocates nothing, ever.

```c
size_t tape_instance_size(void);   /* compile-time constant */

tape_result tape_init(void *mem, size_t mem_len,
                      const tape_dev *dev,
                      void *play_ring, size_t play_ring_len,
                      void *rec_ring,  size_t rec_ring_len,
                      tape **out);
```

| Buffer | Minimum | Purpose |
|---|---|---|
| `mem` | `tape_instance_size()` | Live index, scratch index, superblock, staging blocks, state |
| `play_ring` | 65 536 B | ~372 ms of playback. Retained across sleep by the caller for warm start |
| `rec_ring` | 65 536 B | ~372 ms of capture |

**Two budgets, both asserted in CI:**

| Budget | Ceiling | Counts |
|---|---|---|
| RAM | 200 KiB | `.data` + `.bss` + `tape_instance_size()` |
| Flash | 32 KiB | `.rodata` |

Dominant RAM terms: two index arrays at 4 096 × 12 B ≈ 48 KiB each. Ring buffers are outside the budget. `TAPE_MAX_ENTRIES` = 4 096 is an engine memory constraint, not a media one.

**Stack:** maximum depth ≤ 8 KiB, asserted in CI from `-fstack-usage` and the call graph. This subsumes "no recursion".

---

## 5. Lifecycle

```c
typedef enum { TAPE_SIDE_A = 0, TAPE_SIDE_B = 1 } tape_side;

tape_result tape_mount(tape *t, tape_side side, uint64_t resume_frame,
                       const void *warm_start, size_t warm_start_len);
tape_result tape_unmount(tape *t, uint64_t *out_position_frame);
```

`tape_mount` runs `tapefs-v1.md` §4.1 in full — two-copy resolution, version refusal, `state`, geometry — then §5.2 slot validation, then derives `free_next`, then seeks to `resume_frame` (clamped to the timeline). If `warm_start` is non-`NULL` it is the caller's retained play ring from before sleep; rendering may begin from it immediately while the card comes up.

`tape_unmount` returns the current position in frames. **The engine never writes position to media.**

Mounting a read-only device succeeds for either side; subsequent write calls return `TAPE_ERR_READ_ONLY`. A read-only mount never repairs.

```c
typedef struct {
  uint8_t  uuid[16];
  char     label[33];
  uint32_t nominal_length_s;
  uint64_t total_frames;        /* of the mounted side */
  uint32_t total_chunks, free_chunks;
  uint32_t entry_count, entries_free;
  bool     writable;
  bool     needs_repair;        /* one superblock copy was invalid; device is read-only */
} tape_info;

tape_result tape_get_info(const tape *t, tape_info *out);
tape_result tape_set_side(tape *t, tape_side side);
```

`tape_set_side` commits nothing and discards nothing; it returns `TAPE_ERR_BUSY` if a recording is armed or frames are owed. It does not implicitly commit — implicit commits are how a child loses work they did not mean to keep.

---

## 6. Transport

```c
tape_result tape_seek(tape *t, uint64_t frame);         /* beyond end clamps; TAPE_OK */
uint64_t    tape_tell(const tape *t);
tape_result tape_set_rate(tape *t, int32_t rate_q16_16);

tape_result tape_render(tape *t, int16_t *out, uint32_t frames, uint32_t *rendered);
tape_result tape_service(tape *t, uint32_t block_budget, bool *more_work);

typedef struct {
  bool     at_end, at_start;     /* end-of-media / start-of-media conditions */
  bool     recording_armed, frames_owed;
  uint32_t entries_free;         /* for the record-light headroom colour */
  uint32_t free_chunks;
} tape_status_t;
tape_result tape_status(const tape *t, tape_status_t *out);
```

`rate_q16_16` is signed 16.16 fixed point; `0x00010000` is 1.0×; negative plays in reverse. **The engine accepts instantaneous rates only.** The scrub spool-up ramp (4.0× → 12.0×) is owned by firmware and specified as a rate-versus-time schedule in `spec/acceptance.md`, so it can be golden-tested by driving `tape_set_rate` from a table.

**`tape_render` is interrupt-safe.** It pulls from `play_ring` only, never touches the block device, never blocks. On a short ring it writes what it has, sets `*rendered`, returns `TAPE_ERR_UNDERRUN`; the caller fills the rest with silence. **`tape_service` does all card I/O**, at most `block_budget` blocks per call, setting `*more_work` if more remains. A desktop harness services to completion then renders, making output deterministic; firmware interleaves them. **Both produce identical bytes** — this is the cross-target contract.

`tape_render` performs zero block-device calls. The simulator counts them and the suite asserts zero across a full playback.

---

## 7. Recording

```c
typedef enum { TAPE_REC_OVERWRITE = 0, TAPE_REC_OVERDUB, TAPE_REC_SPLICE } tape_rec_mode;

tape_result tape_arm(tape *t, tape_rec_mode mode);
tape_result tape_feed(tape *t, const int16_t *in, uint32_t frames, uint32_t *accepted);
tape_result tape_commit(tape *t);
tape_result tape_abort(tape *t);
```

`tape_arm` fails with `TAPE_ERR_READ_ONLY` on Side A or a read-only device; with `TAPE_ERR_INDEX_FULL` if `entries_free` is zero for the requested mode.

**`tape_feed` reserves before it accepts.** It computes remaining capacity from `total_chunks` and the in-memory bump pointer without I/O, and accepts only frames it can guarantee a chunk for. `*accepted < frames` with `TAPE_ERR_CARTRIDGE_FULL` means the cartridge is full *now*, reported in the call that hit the wall. `tape_service` never discovers fullness on its own. Accepted frames are **owed** by the engine and will be committed.

**`tape_commit` refuses while frames are owed.** If `rec_ring` is non-empty it returns `TAPE_ERR_BUSY`; the caller runs `tape_service` until `frames_owed` clears, then commits. Once `tape_commit` has been called, `tape_feed` returns `TAPE_ERR_BUSY` until the commit completes or is aborted. `tape_commit` executes `tapefs-v1.md` §8 exactly, including the final flush, and is the only call that changes what is on the card during recording.

`tape_abort` discards owed frames and pending chunks. The next mount reclaims them because `free_next` is derived.

---

## 8. Exact audio arithmetic

Both formulas are normative. Independent implementations must produce identical bytes.

**Overdub.** For each sample, existing `e` and input `x` as `int16_t`:

```c
int32_t s = (int32_t)e + (int32_t)x;
if (s >  32767) s =  32767;
if (s < -32768) s = -32768;
out = (int16_t)s;
```

A saturating clamp. Not a curve, not a wrap.

**Variable-rate playback.** Position is `uint64_t` with 32 fractional bits. Each rendered frame: let `i` = position >> 32, `f` = (uint32_t)position, samples `a` = frame `i`, `b` = frame `i + 1` (per channel). If `i + 1` is beyond the last frame, `b = a`.

```c
out = (int16_t)( a + (int32_t)( ((int64_t)(b - a) * (int64_t)f) >> 32 ) );
position += (int64_t)rate_q16_16 << 16;   /* 16.16 → 32.32 */
```

Arithmetic shift; truncation toward negative infinity; no rounding; channels independent with the same `f`. No anti-aliasing, no pitch preservation, no crossfade — the aliasing is the intended sound.

---

## 9. Cartridge operations

```c
typedef void (*tape_progress_fn)(void *user, uint32_t blocks_done, uint32_t blocks_total);

tape_result tape_reset_side_b(tape *t);
tape_result tape_promote(tape *t, tape_progress_fn cb, void *user);
tape_result tape_respool(tape *t, uint32_t block_budget, bool *more_work);
tape_result tape_dup(tape *src, tape *dst, const uint8_t new_uuid[16], uint32_t epoch,
                     tape_progress_fn cb, void *user);
tape_result tape_format(const tape_dev *dev, const uint8_t uuid[16], uint32_t epoch,
                        const char *label, uint32_t nominal_length_s);
```

Progress callbacks carry **counts only** — blocks done, blocks total. Rates and ETAs are the caller's, because only the caller knows what a second is. **Do not add `timeout_ms` to any engine call**; it will look like a bug fix during SD bring-up and it is a guardrail violation.

`tape_promote` is the two-phase protocol of `tapefs-v1.md` §9.3; expect ~30 s. `tape_respool` is incremental on the `block_budget` contract. `tape_dup` writes the destination's identity **last**, per §9.5. `tape_format` writes the byte-exact initial state of §9.6.

---

## 10. State matrix

Rows are the engine's state; columns are calls. **B** = `TAPE_ERR_BUSY`; **✓** = allowed; **RO** = `TAPE_ERR_READ_ONLY` if the device or side is read-only, else allowed.

| State ↓ / Call → | seek/rate/render | arm | feed | commit | abort | set_side | reset_b | promote | respool | dup (as src) | dup (as dst) | unmount |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Mounted, idle | ✓ | RO | B | B | B | ✓ | RO | RO | RO | ✓ | RO | ✓ |
| Playing (rate ≠ 0) | ✓ | RO | B | B | B | B | B | B | B | ✓ | B | ✓ |
| Armed, no frames owed | ✓ | B | ✓ | ✓ | ✓ | B | B | B | B | B | B | B |
| Armed, frames owed | ✓ | B | ✓ | **B** | ✓ | B | B | B | B | B | B | B |
| Commit in progress | ✓ | B | B | B | B | B | B | B | B | B | B | B |
| Re-spool / promote / dup in progress | ✓ (render from ring) | B | B | B | B | B | B | B | B | B | B | B |
| Not mounted | `NOT_MOUNTED` for all except `tape_mount`, `tape_format` |

`tape_unmount` while armed is refused: the caller must commit or abort first, so a child's recording is never silently dropped by a firmware path that forgot to ask.

---

## 11. Boundary semantics

| Situation | Result |
|---|---|
| `tape_seek` beyond end | Clamp to end, `TAPE_OK` |
| Forward render at exact end | `*rendered` = 0, `TAPE_OK`, `at_end` set |
| Reverse render at frame 0 | `*rendered` = 0, `TAPE_OK`, `at_start` set |
| Splice into an empty side | Creates the first entry at position 0 |
| Splice at exact end | Append |
| Overwrite at end | Append |
| Overdub at end | Append; input passes through unchanged |
| Any edit beyond end | Unreachable — position is always clamped |

End of tape is not an error. Firmware turns `at_end` into the play button popping up.

---

## 12. Invariants

Assertable at any quiescent point; the property suite generates arbitrary edit sequences and checks all of them.

1. `total_frames` equals the sum of `frame_count` over live entries.
2. No live entry's `last_chunk_id` ≥ `total_chunks`.
3. No Side A entry's `last_chunk_id` ≥ `a_high_water`.
4. Every Side B run lies entirely ≥ `a_high_water`.
5. Every entry has `frame_count ≥ 1` and `start_frame < CHUNK_FRAMES`.
6. `sequence` and `sb_generation` strictly increase across successive commits.
7. Re-spool preserves rendered audio bit-exactly; after it, Side B is one entry.
8. Any edit sequence followed by re-spool renders identically to the same sequence without it.
9. After a completed promote, `a_high_water` equals the chunk count of the timeline and no allocated chunk is unreachable.
10. Re-spool's destination is disjoint from every chunk the live index references, at every write.
11. No allocator symbol links into the engine.
12. `tape_render` performs zero block-device calls.
13. No indirect call exists outside the three `dev_*` wrappers.
14. Maximum stack depth ≤ 8 KiB.
15. Duplicate writes the destination superblock's `state = VALID` and `cartridge_uuid` in the final superblock write, after all chunks and both indices.

---

## 13. What the engine must never contain

Any `#ifdef` naming a board, chip, or peripheral. Any reference to buttons, LEDs, solenoids, codecs, jacks, or volume. Any API returning a pointer the caller must free. Any dependency beyond freestanding libc. Any clock, timer, or timeout. Any entropy source. Any codec, container, or metadata parsing.

If the engine appears to need one of these, apply §1 first; if it still does, escalate.

---

## 14. Open before freeze

- Whether `block_budget` should be blocks or a byte count. Blocks is the current answer because it matches what the device does.
- The required `tape_service` cadence, as a number, once the bench build measures it. The failure mode is audible underrun, not corruption.
- Whether `tape_status` should also expose `sb_generation`/`sequence` for `tapectl verify`. Cheap to add; not needed by firmware.
