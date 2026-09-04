# spec/engine-api.md — Tape Engine API v1.0

> **STATUS: DRAFT-5. NOT FROZEN.** All fourteen DRAFT-4 findings dispositioned (PM Decisions 007).
> `tapefs-v1.md` §§1–8 and `engine-api.md` §§2–8, §12 are the **freeze candidate**; operations and the
> state matrix freeze at the first green WP-10 run. Hashes in `spec/VERSION.md` are authoritative.

**Revision:** DRAFT-5 · **Issued:** 4 Sep 2026 · **Status:** §§2–8 and §12 are the freeze candidate; §9–§10 remain open
**Owner:** Program Manager. Changes require PM sign-off.
**Supersedes:** DRAFT-4 (2 Sep). Incorporates V4-001…V4-014 per PM Decisions 007.
**Companion:** `spec/tapefs-v1.md` DRAFT-5, normative for everything on media.

C99. No operating system. No dynamic allocation, ever. No recursion. No libc file I/O. No floating point in the audio path. No clock. The only coupling to the outside world is the block device in §3.

**No prose-only patch.** A change to this document is accepted only when it lands as a change to a reference algorithm, a signature, a matrix cell, or an invariant — with the prose following.

---

## 1. The principles

> **1 — The engine computes. The caller owns anything that needs entropy, hardware knowledge, or memory beyond the engine's budget.**
> **2 — Identity and validity are written last**, after the content they describe.
> **3 — Ownership is not reference.** A side may reference chunks it does not own; it may only allocate and write within what it owns.

Principle 1 has now decided the warm-start buffer, the cartridge UUID, the format epoch, and the absence of any clock or timeout. Apply it before asking.

---

## 2. Error codes

```c
typedef enum {
  TAPE_OK = 0,
  TAPE_ERR_IO,                 /* block device returned failure */
  TAPE_ERR_BAD_MAGIC,
  TAPE_ERR_CRC,
  TAPE_ERR_VERSION,            /* version_major != 1; nothing written, no repair */
  TAPE_ERR_UNSUPPORTED_STATE,  /* a superblock field holds a value v1 does not define:
                                  state or promote_stage outside {0,1}. Nothing written */
  TAPE_ERR_GEOMETRY,           /* fails tapefs §2.1 GEOMETRY_OK or §4.1 phase 2 */
  TAPE_ERR_INCOMPLETE,         /* superblock state == WRITE_IN_PROGRESS */
  TAPE_ERR_INCONSISTENT,       /* two valid copies that cannot be ordered: equal sb_generation and
                                  not byte-identical (superblock), or equal sequence at all (index);
                                  or promote_stage == 1 with index shapes matching no resume row */
  TAPE_ERR_NO_VALID_INDEX,
  TAPE_ERR_READ_ONLY,          /* the mount is not effectively writable (§3.1), a raw destination
                                  device has write == NULL, or tape_arm against Side A */
  TAPE_ERR_CARTRIDGE_FULL,
  TAPE_ERR_INDEX_FULL,
  TAPE_ERR_DEST_TOO_SMALL,     /* tape_dup: destination cannot hold the source timeline */
  TAPE_ERR_SEQUENCE_EXHAUSTED,
  TAPE_ERR_NOT_MOUNTED,
  TAPE_ERR_BUSY,               /* the state matrix in §10 forbids this call now */
  TAPE_ERR_UNDERRUN,           /* tape_render was short because the play ring was short */
  TAPE_ERR_INVALID_ARG,        /* includes tape_dup aliasing and continuation-argument mismatch */
} tape_result;
```

Every call returns `tape_result`. There are no error strings, no timeouts, and no clock.

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

Callbacks return **0 on success, non-zero on failure** — never engine error codes. `count` is in 512-byte blocks. **Every `tape_dev` is a block view of TAPEFS partition 2**; LBA 0 is that partition's first block. The engine never sees the MBR, and `tape_format` cannot create one — card provisioning belongs to `tapectl`.

**`write` is `NULL` for a read-only device.** That is necessary for a mount to be writable. It is not sufficient — see §3.1.

`block_count` is caller-supplied and **untrusted**; `tapefs` §2.1 and §4.1 phase 2 validate geometry against it in 64-bit and refuse on mismatch.

`flush` must not return success until data has reached media.

**Port obligation — device identity.** `tape_dup` must be able to tell two devices apart. The engine compares `dev.ctx` for pointer equality and, where the port supplies a device-identity accessor, that too. **A port that cannot distinguish two devices must not hand the same one to `tape_dup` twice.** The engine cannot verify this; it is a port contract, stated here because it is the only place a caller will look.

**All indirect calls go through three `static inline` wrappers in one file** — `dev_read`, `dev_write`, `dev_flush` in `engine/src/dev.h`. Nothing else dereferences a `tape_dev` member, with one declared exception: `tape_dup`'s aliasing check compares `dev.ctx` and lives in `dev.h` alongside the wrappers. CI checks this at source level and the exception is in the allowlist by name.

Three implementations exist and the engine cannot distinguish them: file-backed (desktop), fault-injecting (crash harness — power-loss-after-N-writes and torn writes, the Verification Lead's, single injector per ADR-025), real SD (firmware).

### 3.1 Effective writability — the one permission predicate

```
effective_writable  =  (dev.write != NULL)  &&  (mounted version_minor == 0)
```

Computed once at mount, stored in the instance, exposed as `tape_info.writable`, and consulted by **every** mutating call and by superblock repair. A mount that is not effectively writable returns `TAPE_ERR_READ_ONLY` from every mutator and performs **zero** block writes, including no mirror repair.

`dev_write` retains a `write != NULL` assertion in debug builds as a **last-line** check, not as the permission model. **It is a test instrument, not a field safety net** — on a freestanding MCU address 0 is usually mapped (vector table or a flash alias), so an indirect call through a null `write` in a release build is undefined and often *silent*. The predicate above is the safety; the assertion is what makes a violation visible in CI.

> **V4-001, the blocker.** DRAFT-4 said "the absence of the function *is* the permission" and defined the state matrix's `W` as `write != NULL`. `tapefs` §4.1 separately declared a `version_minor > 0` cartridge read-only. Nothing joined the two, so on a writable device a v1 engine was authorised by the matrix to `reset_b`, `promote`, `respool` and arm Side B against v1.1 media — committing v1 structures onto media whose newer semantics it does not understand. The compatibility barrier existed in prose and in no code path.

**Raw-device operations are outside this predicate.** `tape_format` and `tape_dup` take a `tape_dev`, not a mount, and are gated only on `dev->write != NULL`. `tapefs` §4.3 says why erasing a newer-minor cartridge on purpose is different from writing to one by accident.

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
| `mem` | `tape_instance_size()` | Live index, scratch index, superblock, staging blocks, the §5.1 disjointness scratch, all engine state |
| `play_ring` | 65 536 B | ~372 ms of playback. Retained across sleep by the caller for warm start |
| `rec_ring` | 65 536 B | ~372 ms of capture |

**Nothing engine-owned lives in `.bss`.** All per-instance state is inside `mem`, so two mounted cartridges — which `tape_dup` requires — cannot overwrite each other's index. This is not a style preference; it is a reentrancy requirement.

**Two budgets, both asserted in CI:**

| Budget | Ceiling | Counts |
|---|---|---|
| RAM | 200 KiB | `.data` + `.bss` + `tape_instance_size()`, summed. This is the single gate; `acceptance.md` WP-13 states the same sum |
| Flash | 32 KiB | `.rodata` |

`TAPE_MAX_ENTRIES` = 4 096 is an engine memory constraint, not a media one. **Stack:** maximum depth ≤ 8 KiB, asserted in CI from `-fstack-usage` and the call graph; this subsumes "no recursion".

> **New in DRAFT-5, and it costs RAM.** `tapefs` §5.1's interval-disjointness check needs a bounded sort. A permutation array of `entry_count` 16-bit indices is 8 KiB at the maximum, and it lives in `mem`. RAM was at 72 % before the commit and record paths added their state, so **report the new `tape_instance_size()` in the next status**; if the sum crosses 200 KiB, escalate rather than shrinking `TAPE_MAX_ENTRIES` unilaterally — entry count is the child's splice budget and it is a product number.

---

## 5. Lifecycle

```c
typedef enum { TAPE_SIDE_A = 0, TAPE_SIDE_B = 1 } tape_side;

typedef struct {
  const void *data;         /* frames, same layout as tape_render output */
  uint32_t    data_bytes;   /* NEW in DRAFT-5: size of the buffer at `data` */
  uint32_t    valid_frames;
  uint32_t    start_frame;  /* timeline frame the first sample represents */
  uint8_t     uuid[16];
  tape_side   side;
} tape_warm_start;

tape_result tape_mount(tape *t, tape_side side, uint64_t resume_frame,
                       const tape_warm_start *warm);   /* warm may be NULL */
tape_result tape_unmount(tape *t, uint64_t *out_position_frame);
```

`tape_mount` runs `tapefs` §4.1 in full — selection, admission, then repair — then §5.3 index-slot selection and §5.2 validity **including interval disjointness, for both sides regardless of which was requested** (`tapefs` §4.2), then derives `free_next`, then seeks to `resume_frame` clamped to the timeline. `at_end` and `at_start` are cleared.

A cartridge whose **Side A** has no selectable index fails the mount whichever side was asked for. A cartridge whose **Side B** has none mounts on **Side A** with `free_next = a_high_water` — the only state `tape_reset_side_b` can be called from — and returns `TAPE_ERR_NO_VALID_INDEX` to a mount that asked for Side B.

**Warm start is used only if every one of these holds**, computed in 64-bit:

```c
end = (uint64_t)warm->start_frame + (uint64_t)warm->valid_frames;

warm != NULL
&& warm->valid_frames > 0
&& (uint64_t)warm->data_bytes >= (uint64_t)warm->valid_frames * FRAME_BYTES
&& end <= total_frames
&& (uint64_t)warm->start_frame <= resume_frame && resume_frame < end
&& memcmp(warm->uuid, mounted uuid, 16) == 0
&& warm->side == mounted side
```

Otherwise the descriptor is ignored, `tape_get_info` reports `warm_start_used = false`, and the mount proceeds normally. **A wrong buffer costs instant-on, never correctness.**

> **V4-011.** DRAFT-4 wrote the containment test as prose over 32-bit fields. A direct C evaluation of `start_frame + valid_frames` wraps for `start_frame` near `UINT32_MAX`, so a stale ring could be accepted for a range it does not cover — exactly the defect WP-11's seventh mutation exists to catch, admitted by the spec that defines the mutation. The checked-64-bit rule the format uses for media extents now applies here too. `data_bytes` is new: without it the engine had no way to know the caller's buffer was big enough for the `valid_frames` it claimed, and principle 1 says the caller owns the buffer — but it does not say the engine must take its dimensions on trust.

`tape_unmount` returns the current position in **whole frames, truncated**. The engine never writes position to media.

Mounting a read-only device succeeds for either side; every subsequent mutator returns `TAPE_ERR_READ_ONLY`, and repair is skipped (§3.1).

```c
typedef struct {
  uint8_t  uuid[16];
  char     label[33];
  uint32_t nominal_length_s;
  uint64_t total_frames;        /* of the mounted side */
  uint32_t total_chunks, free_chunks;
  uint32_t entry_count, entries_free;
  uint16_t version_minor;       /* NEW: why writable may be false on a writable device */
  bool     writable;            /* effective_writable, §3.1 */
  bool     needs_repair;        /* one superblock copy invalid; mount not effectively writable */
  bool     warm_start_used;
} tape_info;

tape_result tape_get_info(const tape *t, tape_info *out);
tape_result tape_set_side(tape *t, tape_side side);
```

`tape_set_side` commits nothing and discards nothing; `TAPE_ERR_BUSY` if a recording is armed or frames are owed, and **`TAPE_ERR_NO_VALID_INDEX` if the requested side had no selectable index at mount** (`tapefs` §4.2). Without that second refusal a Side-A mount of a cartridge with a damaged Side B could switch to a side with no live index at all. It does not implicitly commit — implicit commits are how a child loses work they did not mean to keep.

---

## 6. Transport

```c
tape_result tape_seek(tape *t, uint64_t frame);   /* beyond end clamps; TAPE_OK */
uint64_t    tape_tell(const tape *t);             /* whole frames, truncated */
tape_result tape_set_rate(tape *t, int32_t rate_q16_16);

tape_result tape_render(tape *t, int16_t *out, uint32_t frames, uint32_t *rendered);
tape_result tape_service(tape *t, uint32_t block_budget, bool *more_work);

typedef struct {
  bool     at_end, at_start;
  bool     recording_armed, frames_owed;
  uint32_t entries_free;         /* drives the record light's green/yellow/red */
  uint32_t free_chunks;
} tape_status_t;
tape_result tape_status(const tape *t, tape_status_t *out);
```

`rate_q16_16` is signed 16.16 fixed point; `0x00010000` is 1.0×; negative plays in reverse; **zero is stopped**. The engine accepts instantaneous rates only. The scrub spool-up ramp is owned by firmware and specified as a rate-versus-time schedule in `acceptance.md`, so it can be golden-tested by driving `tape_set_rate` from a table.

**`tape_seek` and `tape_set_rate` clear `at_end` and `at_start`.** Without that, reversing away from either boundary would be impossible.

### 6.1 Position representation

Position is `uint64_t` with 32 fractional bits, so the whole part holds 32 bits of frames — which is why `tapefs` §5.4 caps `total_frames` at 2³² − 1.

```c
const uint64_t max_pos = ((uint64_t)total_frames) << 32;  /* fits: (2^32-1)<<32 < 2^64 */
const int64_t  step    = (int64_t)rate_q16_16 * 65536;    /* 16.16 -> 32.32 */
```

`rate_q16_16` is `int32_t`, so `|step| ≤ 2^47`. **Negating `step` is therefore always defined** — it can never be `INT64_MIN`. That bound is normative; it is what makes the reverse branch below safe to write as `-step`.

### 6.2 The advance — normative

```c
if (step > 0) {
    uint64_t s = (uint64_t)step;
    at_start = false;                                     /* moving away from the start */
    if (position >= max_pos || s >= max_pos - position) { position = max_pos; at_end = true; }
    else                                                  position += s;
} else if (step < 0) {
    uint64_t s = (uint64_t)(-step);
    at_end = false;                                       /* moving away from the end */
    if (position <= s) { position = 0; at_start = true; }
    else                 position -= s;
}
```

**Each direction clears the other's flag.** Without that, `at_start` set by a reverse pass that reached 0 would remain true while the playhead advanced forward under an already-positive rate — `tape_set_rate` was the only thing that cleared it, and the caller has no reason to call it — so `tape_status` would report "at the start of the tape" from the middle of it.

> **V4-009.** DRAFT-4 tested `position > max_pos - s`. With a one-frame timeline (`max_pos = 2^32`), `position = 0` and `rate_q16_16 = INT32_MAX`, `s ≈ 2^47`, so `max_pos - s` **wraps** as unsigned, the comparison is false, and the code executed `position += s` — leaving `position > max_pos` and the next `i` out of range. A valid API input walked straight through the clamp that exists to stop exactly that. Comparing without subtracting the step from the endpoint removes the wrap; the `position >= max_pos` disjunct handles an already-at-or-past-end position and the empty timeline.

### 6.3 The render loop — normative, and it fixes the sample phase

```c
*rendered = 0;
if (total_frames == 0) { at_end = true; return TAPE_OK; }  /* empty: checked first, see §11 */
if (rate_q16_16 == 0)   return TAPE_OK;                    /* stopped: no frames, no flag change */

if (step < 0 && position >= max_pos) position = max_pos - 1; /* snap onto the last frame */

for (n = 0; n < frames; n++) {
    if (step > 0 && position >= max_pos) { at_end = true; break; }
    if (step < 0 && at_start)                              break;

    i = (uint32_t)(position >> 32);
    f = (uint32_t)position;
    a = frame i;
    b = (i + 1 < total_frames) ? frame (i + 1) : a;

    emit interpolate(a, b, f);        /* §8 — FETCH AND EMIT AT THE CURRENT POSITION */
    (*rendered)++;

    advance();                        /* §6.2 — THEN MOVE */
}
```

**Fetch, emit, then advance.** `tape_seek(N)` followed by `tape_render` emits frame *N* as its first output.

> **V4-010.** DRAFT-4 said "the clamp is evaluated **before** each sample is fetched" and put the update pseudocode above the fetch rule. Read literally, the position advanced before the first fetch, so the first frame after a seek was *N+1* — contradicting `tape_seek`'s own "lands on the specified frame". Two conforming renderers would have differed by one frame at every seek and at stream start, which means golden PCM could not be frozen at all. The ordering is now in one algorithm rather than distributed across three sections, and the seek-then-render case is a normative example in `acceptance.md` WP-08.

**The snap.** With a negative rate and `position == max_pos` there is no frame under the playhead — `i` would be `total_frames`. Snapping to `max_pos − 1` puts the playhead on the last frame with `f = 0xFFFFFFFF`; since `i + 1` is beyond the end, `b = a` and the emitted sample is that frame exactly, with no interpolation artefact. This is what makes "press rewind at the end of the tape" work.

**Return value.** `TAPE_ERR_UNDERRUN` is returned **only** when the shortfall was caused by the play ring not holding the frames the position range required. A shortfall caused by `at_end`, `at_start` or `rate == 0` returns `TAPE_OK`. The caller fills the remainder with silence in either case, but only one of them is a problem.

**`tape_render` is interrupt-safe.** It pulls from `play_ring` only, never touches the block device, never blocks. **`tape_service` does all card I/O**, at most `block_budget` blocks per call, setting `*more_work` if more remains.

A desktop harness services to completion then renders, making output deterministic; firmware interleaves them. **Both produce identical bytes** — the cross-target contract. `tape_render` performs zero block-device calls; the simulator counts them and the suite asserts zero across a full playback.

---

## 7. Recording

```c
typedef enum { TAPE_REC_OVERWRITE = 0, TAPE_REC_OVERDUB, TAPE_REC_SPLICE } tape_rec_mode;

tape_result tape_arm(tape *t, tape_rec_mode mode);
tape_result tape_feed(tape *t, const int16_t *in, uint32_t frames, uint32_t *accepted);
tape_result tape_commit(tape *t);
tape_result tape_abort(tape *t);
```

`tape_arm` fails with `TAPE_ERR_READ_ONLY` on Side A or a mount that is not effectively writable, and `TAPE_ERR_INDEX_FULL` if `entries_free` is insufficient for the requested mode.

**`tape_arm`, `tape_reset_side_b` and `tape_respool` clear a stale `promote_stage` after their own preconditions have passed and before their first index or chunk write** (`tapefs` §8). The ordering matters: clearing it earlier would make `tape_arm`'s `TAPE_ERR_READ_ONLY` and `TAPE_ERR_INDEX_FULL` refusals, and `tape_respool`'s `TAPE_ERR_CARTRIDGE_FULL`, write a superblock before refusing — and all three are specified to write nothing. It is one superblock update, it happens at most once after an interrupted promote, and it is what stops an interrupted promote from permanently disabling promote on a cartridge that is otherwise in daily use. It is deliberately **not** in `tape_commit`, so §7.1's 97-block bound stands.

**The recording cursor is fixed at arm time.** `tape_arm` captures the current position as the edit point, and §10 forbids `tape_seek` and `tape_set_rate` while armed — so there is exactly one position the edit can apply at, and no reading of the spec produces a different one (V3-011).

**`tape_feed` reserves before it accepts.** It computes remaining capacity from `total_chunks` and the in-memory bump pointer **without I/O**, and accepts only frames it can guarantee a chunk for. `*accepted < frames` with `TAPE_ERR_CARTRIDGE_FULL` means the cartridge is full *now*, reported in the call that hit the wall; `tape_service` never discovers fullness on its own. Accepted frames are **owed** by the engine and will be committed.

### 7.1 `tape_commit` is synchronous

**`tape_commit` refuses while frames are owed.** If `rec_ring` is non-empty it returns `TAPE_ERR_BUSY`; the caller runs `tape_service` until `frames_owed` clears, then commits.

`tape_commit` then executes `tapefs` §8 **in full, including the final flush, and returns only after it.** It has no budget and no continuation. By the time it is callable all chunk data is already durable, so it writes **at most 97 blocks and performs exactly two flushes** (`tapefs` §8). On failure, `TAPE_ERR_IO`; the on-media state is indeterminate until remount, where `tapefs` §4.1 and §5.3 resolve it.

Once `tape_commit` has been called it does not return until it is done, so `tape_feed` cannot be called during it and there is no state in which `tape_abort` could interrupt it. **`tape_abort` discards owed frames and pending chunks before a commit, never during one.** The next mount reclaims the pending chunks, because `free_next` is derived.

> **V4-008.** DRAFT-4 carried a "Commit in progress" row in the state matrix and a rule that `tape_abort` was permitted during a commit and took effect if the index header block had not yet been written — while `tape_commit` had no budget, no `more_work`, and no defined asynchronous return. Reaching that row required concurrent re-entry, which this API neither permits nor defines. One implementation would have made commit synchronous and left the row unreachable; another would have invented asynchronous semantics. **Synchronous is the honest reading**, because the operation it describes is bounded at 97 blocks — this is not the 30-second copy that forced `tape_promote` incremental. The row and the abort rule are deleted rather than specified, and `acceptance.md` adds a measured worst-case commit latency as a firmware criterion so the assumption behind "bounded" is a number and not a belief.

---

## 8. Exact audio arithmetic

Both formulas are normative; independent implementations must produce identical bytes on every supported target.

**Overdub — a saturating clamp.** Not a curve, not a wrap.

```c
int32_t s = (int32_t)e + (int32_t)x;
if (s >  32767) s =  32767;
if (s < -32768) s = -32768;
out = (int16_t)s;
```

**Variable-rate playback.** Let `i = position >> 32`, `f = (uint32_t)position`, `a` = frame `i`, `b` = frame `i + 1` per channel. If `i + 1` is beyond the last frame, `b = a` (§6.3).

```c
int64_t  d = (int64_t)(b - a) * (int64_t)f;      /* |d| < 2^48 */
int64_t  q;
if (d >= 0) {
    q = (int64_t)((uint64_t)d >> 32);            /* logical shift of a non-negative value */
} else {
    uint64_t m = (uint64_t)(-d);                 /* |d| < 2^48, so -d is defined */
    q = -(int64_t)((m + 0xFFFFFFFFu) >> 32);     /* -ceil(m / 2^32) == floor(d / 2^32) */
}
out = (int16_t)((int32_t)a + (int32_t)q);
```

Channels independent with the same `f`. No rounding. No anti-aliasing, no pitch preservation, no crossfade — the aliasing is the intended sound.

**Why not `>> 32` on the product.** `d` is negative whenever `b < a`, and right-shifting a negative signed integer is **implementation-defined in C99**. DRAFT-4's single-line formula demanded flooring in prose and expressed it with an operator that is not required to floor, so a desktop build and an embedded build could legitimately emit different PCM for the same cartridge — violating the cross-target contract and making golden bytes unfreezable (V4-013). The formulation above computes the same floored quotient using only unsigned shifts and is portable across every freestanding C99 target. Verified equal to the arithmetic-shift result over the full `(b − a, f)` domain by exhaustive comparison in the golden suite.

**No clamp is needed on the result.** With `f/2^32 ∈ [0, 1)`, `a + q` lies in `[min(a,b), max(a,b)]`, which is inside `int16` range by construction. Adding a clamp here would hide an arithmetic bug rather than prevent one.

---

## 9. Cartridge operations

```c
typedef void (*tape_progress_fn)(void *user, uint32_t blocks_done, uint32_t blocks_total);

tape_result tape_reset_side_b(tape *t);
tape_result tape_promote(tape *t, uint32_t block_budget, bool *more_work,
                         tape_progress_fn cb, void *user);
tape_result tape_respool(tape *t, uint32_t block_budget, bool *more_work);
tape_result tape_dup(tape *src, const tape_dev *dst_dev,
                     const uint8_t new_uuid[16], uint32_t epoch,
                     uint32_t dst_nominal_length_s,
                     uint32_t block_budget, bool *more_work,
                     tape_progress_fn cb, void *user);
tape_result tape_format(const tape_dev *dev, const uint8_t uuid[16], uint32_t epoch,
                        const char *label, uint32_t nominal_length_s);
```

Progress callbacks carry **counts only**. Rates and ETAs belong to the caller, because only the caller knows what a second is. **Do not add `timeout_ms` to any engine call** — it will look like a bug fix during SD bring-up and it is a principle-1 violation.

### 9.1 The incremental contract — one model, normative

`tape_respool`, `tape_promote` and `tape_dup` each do at most `block_budget` blocks of work per call and set `*more_work` while any remains.

**A long operation is driven to completion by repeated calls to the same function.** The first call made while no long operation is in progress starts one. While `*more_work` is true:

- a further call to **that same function** advances it;
- a call to **either of the other two** returns `TAPE_ERR_BUSY`.

**Argument stability.** On a continuation call, every argument except `block_budget`, `more_work`, `cb` and `user` must equal the value passed to the initiating call — for `tape_dup` that includes `dst_dev` (compared by `ctx`), `new_uuid`, `epoch` and `dst_nominal_length_s`. A mismatch returns `TAPE_ERR_INVALID_ARG`, performs no work, and leaves the operation in progress.

**Termination on error.** **Any return from a continuation call to the operation's own function**, other than `TAPE_OK` and `TAPE_ERR_INVALID_ARG`, ends the operation: `*more_work` is set false and the instance returns to *Mounted, idle*. Media is left in whatever state it reached, which `tapefs` §4.1 and §5.3 resolve on the next mount.

**A `TAPE_ERR_BUSY` returned to any *other* call has no effect on the operation in progress.** That is the whole point of the in-progress rows: nine calls plus the two sibling long operations return `BUSY` there, and if `BUSY` terminated the operation, a stray `tape_seek` from a copy screen would silently cancel a 30-second `tape_dup` and the caller's next call would restart it from the beginning.

> Without this rule the in-progress rows had no error exit at all. `tape_abort` and `tape_unmount` are both `B` there and there is no `tape_cancel`, so a card pulled mid-`tape_respool` — `TAPE_ERR_IO`, `*more_work` still true — left an instance that only `tape_respool` could advance, which would keep failing, and that `tape_unmount` would refuse forever. §10's claim that the rows are exitable held only on the success path.

> **V4-007.** DRAFT-4's §9 required repeated calls to drive these operations while its state matrix returned `TAPE_ERR_BUSY` from all three in the "in progress" row. No public call could advance any of them; all three were uncompletable under the normative matrix, and an adapter could not encode a conforming call loop.
>
> **Rejected alternative: continuation through `tape_service`.** It gives `tape_service` no way to distinguish "frames still owed" from "a long operation still running", and it makes the card write for an operation the caller has stopped tracking. Firmware's copy screen also wants the progress callback attached to the call it made. One model is normative and it is the one above.

### 9.2 The operations

- `tape_reset_side_b` — `tapefs` §9.2. Sub-second, moves no audio, and the resulting Side B references Side A's chunks, which Rule 3 permits. Not incremental.
- `tape_promote` — `tapefs` §9.3. Entry classification, adopt-in-place phase 1, `promote_stage` on media, and a resume table with no reachability arguments in it. `TAPE_ERR_INVALID_ARG`, `*more_work = false` and zero writes on an empty Side B. **Every call that returns `TAPE_OK` with `*more_work == false` clears the stored positions for `(uuid, A)` and `(uuid, B)` before returning** — full path, step-5 decline, every resume entry point, and the NOTHING TO DO classification.
- `tape_respool` — `tapefs` §9.4, at most two passes, second pass optional. **`TAPE_OK`, `*more_work = false` and zero writes on an empty Side B** — the opposite answer to promote's, for the reason §9.4 gives.
- `tape_dup` — `tapefs` §9.5. Destination is a **`tape_dev *`, not a mounted `tape`**, so a blank or interrupted destination can be written and a failed copy re-run. Four preconditions in a normative order — aliasing, writability, geometry, capacity — **each writing nothing**. Copies Side A only; the destination's Side B is initialised to mirror it.
- `tape_format` — `tapefs` §9.6, an ordered destructive transaction. Refuses a read-only device and a destination failing `GEOMETRY_OK`, **before any write**.

---

## 10. State matrix

**Normative.** Every row is reachable and every cell is exercised by `acceptance.md`.

**B** = `TAPE_ERR_BUSY`; **✓** = allowed; **W** = requires **effective writability** (§3.1), else `TAPE_ERR_READ_ONLY`.

> **W is about the mount, not the mounted side.** DRAFT-4's first cut marked these RO and defined `TAPE_ERR_READ_ONLY` as "write against `write == NULL`, or against Side A" — which forbade `tape_promote` from a Side-A mount and forbade `tape_dup` outright, since duplicating writes the destination's Side A by definition. The Side-A rule applies to `tape_arm` and `tape_feed` only: those write *the mounted side*. `reset_b`, `promote` and `dup` write regions chosen by the operation, not by what is mounted. DRAFT-5 additionally makes `W` include the version-minor condition (§3.1), which is V4-001.

`tape_dup` takes a source `tape *` and a destination `tape_dev *`, so only the source's row applies; the destination is a raw device with no state in this table. Its own preconditions are in `tapefs` §9.5.

| State ↓ / Call → | seek | set_rate | render | service | status / info / tell | arm | feed | commit | abort | set_side | reset_b | promote | respool | dup (as src) | unmount |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Mounted, idle | ✓ | ✓ | ✓ | ✓ | ✓ | W+SideB | B | B | B | ✓ | W | W | W | ✓ | ✓ |
| Playing (rate ≠ 0) | ✓ | ✓ | ✓ | ✓ | ✓ | W+SideB | B | B | B | B | B | B | B | ✓ | ✓ |
| Armed, no frames owed | **B** | **B** | ✓ | ✓ | ✓ | B | ✓ | ✓ | ✓ | B | B | B | B | B | B |
| Armed, frames owed | **B** | **B** | ✓ | ✓ | ✓ | B | ✓ | **B** | ✓ | B | B | B | B | B | B |
| **Respool in progress** | B | B | ✓ | ✓ | ✓ | B | B | B | B | B | B | B | **✓** | B | B |
| **Promote in progress** | B | B | ✓ | ✓ | ✓ | B | B | B | B | B | B | **✓** | B | B | B |
| **Dup in progress** | B | B | ✓ | ✓ | ✓ | B | B | B | B | B | B | B | B | **✓** | B |
| Not mounted | `TAPE_ERR_NOT_MOUNTED` for all except `tape_mount`, `tape_format`, `tape_init`, and `tape_dup` on the destination device |

**There is no "commit in progress" row.** `tape_commit` is synchronous (§7.1), so no state exists between its call and its return.

**`tape_arm` is the only call gated on the mounted side** — `W+SideB` means an effectively writable mount and `TAPE_SIDE_B`; Side A gives `TAPE_ERR_READ_ONLY`.

**The three in-progress rows differ only in which long-operation column is ✓** — the continuation call for the operation actually running. That is §9.1 expressed as cells, and it is what makes the row reachable and exitable.

**`tape_seek` and `tape_set_rate` are forbidden while armed.** The recording cursor is fixed at arm time (§7). This resolves the ambiguity by removing it rather than documenting it, and it matches the object: you cannot seek a tape deck while it is recording, because the head is where the head is.

**`tape_render` stays allowed in every mounted row** so firmware can monitor and so audio never stops during a copy, and `tape_service` is always allowed because it is the call that clears owed frames.

**`tape_unmount` while armed or mid-operation is refused.** The caller must commit, abort, or finish first, so a child's recording is never silently dropped by a firmware path that forgot to ask.

---

## 11. Boundary semantics

| Situation | Result |
|---|---|
| `tape_seek` beyond end | Clamp to `max_pos`, `TAPE_OK`, flags cleared |
| `tape_seek(N)` then render, forward | **First emitted frame is `N`** (§6.3) |
| Forward render at `position == max_pos` | `*rendered` = 0, `TAPE_OK`, `at_end` set |
| Render at `rate_q16_16 == 0`, non-empty timeline | `*rendered` = 0, `TAPE_OK`, no flag change |
| Render on an empty timeline, **any rate including 0** | `*rendered` = 0, `TAPE_OK`, `at_end` set — the empty check precedes the rate check (§6.3) |
| Reverse render from `position == 0` | Emits frame 0 once, then `at_start` is set and the loop stops: `*rendered` = 1 |
| Reverse render with `at_start` already set | `*rendered` = 0, `TAPE_OK` |
| Reverse render from `position == max_pos` | Snaps to `max_pos − 1` and emits the last frame first (§6.3) |
| Splice into an empty side | Creates the first entry at position 0 |
| Splice at exact end | Append |
| Overwrite at end | Append |
| Overdub at end | Append; input passes through unchanged |
| Any edit beyond end | Unreachable — position is always clamped |

End of tape is not an error. Firmware turns `at_end` into the play button popping up.

---

## 12. Invariants

Assertable at any quiescent point. The property suite generates arbitrary edit sequences and checks all of them.

1. `total_frames` equals the sum of `frame_count` over live entries, computed in 64-bit.
2. `total_frames ≤ TAPE_MAX_TOTAL_FRAMES`.
3. No live entry's `last` (tapefs §5.1) is ≥ `total_chunks`.
4. No **Side A** entry's `last` is ≥ `a_high_water`.
5. **Every chunk Side B *allocates or writes* has id ≥ `a_high_water`.** Side B *referencing* chunks below the mark is correct and expected — it is what reset-B and a completed promote produce. *(DRAFT-3's invariant 4 forbade the reference and was unsatisfiable; V3-009.)*
6. Every entry has `frame_count ≥ 1` and `start_frame < CHUNK_FRAMES`.
7. `sequence` and `sb_generation` strictly increase across successive **logical** updates on one cartridge; superblock repair does not increment `sb_generation`. **`tape_format` and `tape_dup` establish a new cartridge and set `sb_generation = 1`; the rule does not span them** (`tapefs` §9.6).
8. Re-spool preserves rendered audio bit-exactly; after a completed pass, the side is exactly one entry — **or zero entries, if the timeline was empty and re-spool was a no-op**.
9. Any edit sequence followed by re-spool renders identically to the same sequence without it.
10. **Every re-spool and promote write destination is disjoint from the live set of both sides at the moment of that write.**
11. **After a promote that reached `tapefs` §9.3.2 step 9**, `a_high_water` equals the timeline's chunk count, `promote_stage == 0`, and no allocated chunk is unreachable.
11a. **After any `tape_promote` returning `TAPE_OK`** — including the decline at step 5 and the NOTHING TO DO classification — `promote_stage == 0` and **both live indices have byte-identical entry arrays**. *(Invariant 11 alone was false for the decline path: with `a_high_water = 2`, Side B one entry at chunk 3 spanning five chunks, adopt-in-place raises the water line to 8, step 5 finds `[0,5)` overlapping the live set `[3,8)` and declines — leaving `a_high_water = 8` against a five-chunk timeline, and chunks `[0,3)` allocated and unreachable. Both of 11's clauses false, with `TAPE_OK` returned. It is stated over entry arrays rather than "the same single run" because §5.2 admits a multi-entry Side A on crafted media.)*
11b. **Side A's live index, on any cartridge this engine wrote, has at most one entry.** Side A is written only by `tapefs` §9.3.1 step 2, §9.3.2 step 7, §9.5 step 3 and §9.6 step 3, and every one of those writes zero or one entry. Several arguments in §9.3 already lean on this; it is stated so they do not have to lean on it silently. **Mount does not enforce it** — §5.2 places no entry-count bound on Side A — so it is not assertable over arbitrary media, and §9.3.3's rows test "single entry" directly rather than assuming it.
12. `free_next` equals `max(a_high_water, max over live-B entries of last + 1)` — recomputed at mount, never stored.
13. No allocator symbol links into the engine.
14. `tape_render` performs zero block-device calls.
15. No indirect call exists outside the three `dev_*` wrappers.
16. Maximum stack depth ≤ 8 KiB.
17. `tape_dup` writes the destination's `state = VALID`, `cartridge_uuid` and `a_high_water` in the final superblock write, after all chunks and both indices. **The destination's Side A timeline is compacted to `[0, len_A)`, its A0 and B0 slots are written directly with `sequence` 1 and 2, and all four index slots' block 0 are zeroed first** (`tapefs` §9.5) — so no slot surviving from the destination's previous cartridge can outrank the new index.
18. **`tape_dup` and `tape_format` perform zero writes when any precondition fails** — aliasing, writability, geometry or capacity.
19. No engine-owned state lives outside the caller's `mem` block.
20. **Within one index, every pair of entries has disjoint half-open physical-frame intervals** (`tapefs` §5.1). **Across sides, overlap is permitted and expected — never a violation**, and equally never required: two empty sides, or a fully re-recorded Side B, share nothing. Promote's phase-2 safety check assumes nothing about either; mount rejects media violating the first.
21. Promote writes below `a_high_water` only in phase 2, only after both live indices reference the staging run, and only after the explicit disjointness check in `tapefs` §9.3 step 5 passes.
22. `tape_promote` on a Side B with `total_frames == 0` returns `TAPE_ERR_INVALID_ARG` and writes nothing.
23. **No block write occurs on a mount whose `effective_writable` (§3.1) is false** — including superblock repair. Asserted by the simulator, not only by inspection.
24. **`tape_commit` performs at most 97 block writes and exactly two flushes**, and returns only after the second.
25. **`promote_stage` on media is 1 only after `tapefs` §9.3 step 4 and before either step 9 or a stage-clearing write (`tapefs` §8)**, and `promote_staging_chunk` is the staging run's first chunk whenever it is 1. Every mount with `promote_stage == 1` matches **exactly one** row of §9.3.3 — the three rows partition the space because **rows 2 and 3 both require `S > 0`** — row 1 against row 2 and row 1 against row 3 by `S`, row 2 against row 3 by whether B's entry array is identical to A's. *(Row 3's `H > len` implies `S > 0` only through the engine's own `H = S + len`, which is a reachability argument and fails on crafted media; the explicit guard does not.)*
25a. **`tape_arm`, `tape_reset_side_b` and `tape_respool` leave `promote_stage == 0`** on any effectively writable mount, after their own preconditions pass and before their first index or chunk write (`tapefs` §8, stage clearing). **No index commit by any of those three occurs on media with `promote_stage == 1`.** `tape_promote`'s own phase-2 commits (`tapefs` §9.3.2 steps 7–8) are the sole exception and are by design — `promote_stage` is 1 from step 4 until step 9, which is precisely the window those two commits fall in.
26. **A mount that fails admission (`TAPE_ERR_VERSION`, `TAPE_ERR_UNSUPPORTED_STATE`, `TAPE_ERR_INCOMPLETE`, `TAPE_ERR_GEOMETRY`) performs zero writes.**

---

## 13. What the engine must never contain

Any `#ifdef` naming a board, chip or peripheral. Any reference to buttons, LEDs, solenoids, codecs, jacks or volume. Any API returning a pointer the caller must free. Any dependency beyond freestanding libc. Any clock, timer or timeout. Any entropy source. Any codec, container or metadata parsing. Any static buffer holding per-instance state.

If the engine appears to need one of these, apply §1 first; if it still does, escalate.

---

## 14. Freeze scope and what is still open

**§§2–8 and §12 are the freeze candidate.** Error codes, the device contract and its permission predicate, memory, lifecycle, transport arithmetic, recording, exact audio arithmetic, and the invariant list. These are what the golden fixtures and the read path are built against.

**§9 and §10 do not freeze with them** — they freeze at the first green WP-10 run, for the reason `tapefs` §14 gives.

Open:

- The required `tape_service` cadence, as a number, once the bench build measures it. The failure mode is audible underrun, not corruption.
- The measured worst-case `tape_commit` latency, which is what makes §7.1's "bounded" a fact. Firmware criterion in `acceptance.md`.
- The new `tape_instance_size()` after §5.1's disjointness scratch. RAM was at 72 %.
- Whether `tape_status` should expose `sb_generation`/`sequence` for `tapectl verify`. Cheap; not needed by firmware.
- `block_budget` is in **blocks**, matching what the device does. Settled; recorded here so it stops being reopened.
