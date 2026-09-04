# spec/tapefs-v1.md — TAPEFS v1.0

> **STATUS: DRAFT-5. NOT FROZEN.** All fourteen DRAFT-4 findings dispositioned (PM Decisions 007).
> `tapefs-v1.md` §§1–8 and `engine-api.md` §§2–8, §12 are the **freeze candidate**; operations and the
> state matrix freeze at the first green WP-10 run. Hashes in `spec/VERSION.md` are authoritative.

**Revision:** DRAFT-5 · **Issued:** 4 Sep 2026 · **Status:** freeze candidate for §§1–8; §9–§10 remain open
**Owner:** Program Manager. Changes require PM sign-off (escalation trigger #1).
**Supersedes:** DRAFT-4 (2 Sep). Incorporates all fourteen findings V4-001…V4-014 per PM Decisions 007.

This is the on-media format for a Digital Tape Player cartridge. It is normative and byte-exact. Where it is ambiguous, that is a defect — report it.

**No prose-only patch.** From DRAFT-5 onward a change to this document is accepted only when it lands as a change to a reference algorithm, a table, an interval model, or an enumerated state — with the prose following. A finding that can only be answered by rewording is a documentation defect and is batched, not drafted.

**Newest normative text, least scrutinised, attack first:** §4.3 (effective writability), §5.1's interval model, and §9.3's `promote_stage` machinery. The last of these is a **new superblock field** and is the largest structural change since DRAFT-3.

---

## 0. Three rules that govern everything below

**Rule 1 — The engine computes. The caller owns anything that needs entropy, hardware knowledge, or memory beyond the engine's budget.** The cartridge UUID, the format epoch, the warm-start buffer and the block device's geometry are all supplied by the caller. The engine never generates identity, never reads a clock, and never trusts `block_count`.

**Rule 2 — Identity and validity are written last**, after the content they describe. A cartridge interrupted mid-operation is recognisably unfinished, never silently wrong.

**Rule 3 — Ownership is not reference.** A side may *reference* chunks it does not *own*. It may only allocate and write within what it owns. This is the copy-on-write mechanism the whole format rests on, and DRAFT-3 contradicted it (V3-009).

---

## 1. Constants

| Name | Value |
|---|---|
| `SAMPLE_RATE` | 44 100 Hz |
| `CHANNELS` | 2, interleaved L then R |
| `SAMPLE_FORMAT` | signed 16-bit little-endian |
| `FRAME_BYTES` | 4 |
| `BYTE_RATE` | 176 400 B/s |
| `BLOCK_BYTES` | 512 |
| `CHUNK_BYTES` | 524 288 (512 KiB) |
| `CHUNK_FRAMES` | 131 072 |
| `CHUNK_BLOCKS` | 1 024 |
| `CHUNK_SECONDS` | 2.972154195… (= 131 072 / 44 100) |
| `INDEX_SLOT_BYTES` | 65 536 (128 blocks) |
| `INDEX_ENTRY_BYTES` | 12 |
| `TAPE_MAX_ENTRIES` | 4 096 (blocks 1–96 of a slot) |
| `TAPE_MAX_TOTAL_FRAMES` | 4 294 967 295 (2³² − 1) — see §5.4 |
| `LBA_CHUNK_BASE` | 2 048 |

All multi-byte integers are little-endian. All CRCs are CRC-32/ISO-HDLC: polynomial 0xEDB88320 (reflected), init 0xFFFFFFFF, reflect in and out, final XOR 0xFFFFFFFF.

---

## 2. Tape lengths

Length is a **format-time parameter**, not a format constant. Every region size derives from it.

**Normative formula.** Given `nominal_length_s`, computed in 64-bit with overflow check:

```
frames       = (uint64_t)nominal_length_s * SAMPLE_RATE
total_chunks = (frames + CHUNK_FRAMES - 1) / CHUNK_FRAMES      /* ceiling */
reject if nominal_length_s == 0
reject if total_chunks == 0 or total_chunks > UINT32_MAX
reject if frames > TAPE_MAX_TOTAL_FRAMES                        /* §5.4 */
```

The store must cover the **full** labelled duration. A cartridge that cannot hold the time printed on it is a defect.

| Designation | `nominal_length_s` | `total_chunks` | Side A store | Holds | Copy at high-speed 4-bit (~22 MB/s) |
|---|---|---|---|---|---|
| **C-60 — the standard cartridge** | 3 600 | **1 212** | 635.4 MB | 3 602.25 s | ~29 s |
| C-90 | 5 400 | 1 817 | 952.6 MB | 5 400.40 s | ~43 s |
| C-120 | 7 200 | **2 423** | 1 270.3 MB | 7 201.53 s | ~58 s |

> DRAFT-3 gave 1 211 and 2 422 — a truncation where the formula requires a ceiling. A "C-60" formatted to DRAFT-3 held 3 599.28 s, twenty-eight hundredths of a second short of its own label (V3-012).

**C-60 is the standard.** It meets the 30-second copy target on the plain 3.3 V high-speed interface with a write rate every V30 card guarantees. Longer cartridges are permitted, copy more slowly, and say so on the label. `nominal_length_s` is not a limit on Side B's timeline (§9.1); it is what the label says.

### 2.1 The geometry predicate

One predicate decides whether a proposed cartridge image fits a given block device. **It is used in three places and stated once here** — §4.1 phase 2 (mount), §9.5 (duplicate) and §9.6 (format). DRAFT-4 stated it only at mount, so the two operations that *create* geometry could begin destroying media before discovering the geometry was impossible (V4-006).

```
GEOMETRY_OK(nominal_length_s, block_count):

  1.  frames, total_chunks per §2; reject on any §2 rejection.
  2.  block_count > LBA_CHUNK_BASE
  3.  LBA_CHUNK_BASE + (uint64_t)total_chunks * CHUNK_BLOCKS  <=  (uint64_t)block_count - 1
```

All arithmetic in 64-bit. Line 3 reserves the final block for the superblock mirror, and because `LBA_CHUNK_BASE` is 2 048 and the last fixed metadata block is 519, line 3 also subsumes every fixed metadata LBA. Failure → `TAPE_ERR_GEOMETRY`, **zero writes**.

---

## 3. Media layout

MBR with two partitions. **Provisioning the MBR and partition 1 is `tapectl`'s job.** Every `tape_dev` the engine sees is a block view of partition 2 alone; LBA 0 below is that partition's first block. The engine never sees the MBR.

| # | Type | Size | Contents |
|---|---|---|---|
| 1 | 0x0C FAT32 | 16 MiB | `README.TXT`, optional label art. Never read by the device |
| 2 | 0xDA | remainder | TAPEFS |

| LBA | Blocks | Region |
|---|---|---|
| 0 | 8 | Superblock, primary. Block 0 used; 1–7 reserved, zero |
| 8 | 128 | Index slot **A0** |
| 136 | 128 | Index slot **A1** |
| 264 | 128 | Index slot **B0** |
| 392 | 128 | Index slot **B1** |
| 520 | 1 528 | Reserved, zero (alignment padding) |
| 2 048 | `total_chunks × 1024` | Chunk store. Chunk *N* at `lba_chunk_base + N × 1024` |
| *`block_count − 1`* | 1 | Superblock, mirror |

There is no preroll cache. Instant-on is not a format feature (§12).

---

## 4. Superblock (512 bytes)

| Offset | Size | Field | Notes |
|---|---|---|---|
| 0 | 8 | `magic` | `54 41 50 45 46 53 00 01` — `"TAPEFS\0\x01"` |
| 8 | 2 | `version_major` | 1 |
| 10 | 2 | `version_minor` | 0 |
| 12 | 4 | `sb_generation` | Incremented once per **logical** update; see §4.1 |
| 16 | 1 | `state` | **0 = `VALID`, 1 = `WRITE_IN_PROGRESS`. No other value is defined** |
| 17 | 3 | *reserved* | zero |
| 20 | 16 | `cartridge_uuid` | Caller-supplied. The engine only stores it |
| 36 | 4 | `sample_rate` | 44100 |
| 40 | 2 | `channels` | 2 |
| 42 | 2 | `bits_per_sample` | 16 |
| 44 | 4 | `chunk_bytes` | 524288 |
| 48 | 4 | `nominal_length_s` | Label value. §2 |
| 52 | 4 | `total_chunks` | Capacity of the chunk store |
| 56 | 4 | `a_high_water` | Chunk ids `[0, a_high_water)` are **owned by** Side A |
| 60 | 4 | `index_slot_bytes` | 65536 |
| 64 | 4 | `lba_index_a0` | 8 |
| 68 | 4 | `lba_index_a1` | 136 |
| 72 | 4 | `lba_index_b0` | 264 |
| 76 | 4 | `lba_index_b1` | 392 |
| 80 | 4 | `lba_chunk_base` | 2048 |
| 84 | 4 | `lba_superblock_mirror` | `block_count − 1` |
| 88 | 32 | `label` | UTF-8, NUL-padded. Advisory |
| 120 | 4 | `format_epoch` | Caller-supplied. Informational |
| **124** | **4** | **`promote_stage`** | **NEW in DRAFT-5. 0 = no promote in flight, 1 = promote phase 1 committed. No other value is defined. §9.3** |
| **128** | **4** | **`promote_staging_chunk`** | **NEW in DRAFT-5. The staging run's first chunk id, `S`. Meaningful only when `promote_stage == 1`; zero otherwise** |
| 132 | 376 | *reserved* | zero |
| 508 | 4 | `crc32` | Over bytes 0…507 |

**Bytes 0–19 are frozen across all future major versions.** A v1 reader must be able to read magic, both version fields, `sb_generation` and `state` from v2 media in order to refuse it correctly.

> **Why a new field.** DRAFT-4 asked the recovery logic to infer "is a promote in flight, and how far did it get?" from the shapes of the two indices alone. The verifier showed the enumeration was incomplete (V4-003) and that the documented re-run could fail on a cartridge whose staging copy was already durable (V4-004). Both are symptoms of the same thing: **an intermediate state that is not self-identifying.** Every argument for "this shape can only arise from promote" was a reachability argument, and reachability arguments are what have failed most often on this project. Two u32 in reserved space, written by superblock writes that already happen, make the state say what it is. Zero extra writes, zero extra flushes.

### 4.1 Mount — selection, admission, then repair

DRAFT-3 ordered repair before the version check, which meant a v1 engine could write to v2 media it was forbidden to touch (V3-006). The three phases are now explicit and **only phase 3 writes**.

**Phase 1 — selection. No writes.**
Read both copies. A copy is *structurally valid* iff its magic matches and its CRC verifies.

- Neither valid → `TAPE_ERR_BAD_MAGIC` or `TAPE_ERR_CRC`. Mount ends.
- Exactly one valid → it is the candidate. Record that the partner needs repair.
- Both valid, different `sb_generation` → the higher is the candidate.
- Both valid, equal `sb_generation` → they must be byte-identical. If not, `TAPE_ERR_INCONSISTENT`.

**Phase 2 — admission. No writes.** In this order:

1. `version_major ≠ 1` → **`TAPE_ERR_VERSION`. Nothing is written. No repair. Mount ends.** An unsupported version is not corruption, and repairing it is how an old reader downgrades new media.
2. `version_minor > 0` → the mount is **not effectively writable** (§4.3); continue.
3. **Defined-value check.** `state ∈ {0, 1}` and `promote_stage ∈ {0, 1}`. Any other value → **`TAPE_ERR_UNSUPPORTED_STATE`. Nothing written. No repair.**
4. `state == WRITE_IN_PROGRESS` → `TAPE_ERR_INCOMPLETE`. Nothing written. The cartridge is an interrupted duplicate or format; the remedy is to re-run the operation.
5. Geometry, all in 64-bit:
   - `sample_rate`, `channels`, `bits_per_sample`, `chunk_bytes`, `index_slot_bytes` equal §1;
   - the six `lba_*` fields equal §3, and `lba_superblock_mirror == block_count − 1`;
   - `total_chunks ≥ 1` and `a_high_water ≤ total_chunks`;
   - **`GEOMETRY_OK(nominal_length_s, block_count)` (§2.1) holds, and the superblock's stored `total_chunks` equals the `total_chunks` that predicate derives.**

   Any failure → `TAPE_ERR_GEOMETRY`. Nothing written.

> Step 3 is V4-012. A CRC-correct superblock with `state = 2` previously passed admission — the only test was `state == WRITE_IN_PROGRESS` — so damaged or future state values **failed open** and the cartridge mounted read-write with its transaction state unknown. Undefined values now fail closed, which is the same discipline §4.1 step 1 already applies to `version_major`.
>
> Step 5's last line replaces DRAFT-4's pair of separate inequalities. Requiring the stored `total_chunks` to *equal* the derived value, rather than merely be ≥ the label's requirement, closes the gap where a cartridge could carry a store larger than its own geometry predicate produces and then disagree with a freshly formatted one of the same label. Exact-equality and one-block-short cases against the mirror are required tests.

`block_count` is caller-supplied and **untrusted**. These checks exist to defend against it as much as against the media.

**Phase 3 — repair. The only phase that writes.**
Performed only if the candidate passed phase 2, exactly one copy was structurally valid, and **the mount is effectively writable (§4.3)**. Rewrite the invalid copy from the candidate; flush.

**`sb_generation` is not incremented by repair.** Repair restores a copy of an existing logical state; it does not create a new one. Generation increments once per logical update, and a logical update writes **mirror first, flush, then primary, flush**.

Where repair is skipped, `tape_get_info` reports `needs_repair`. A recoverable cartridge still mounts in the source slot.

### 4.2 Index selection and derivation

After phase 3, mount performs §5.3 index-slot selection and §5.2 validation — **including §5.1's interval-disjointness requirement** — **for both sides, not only the requested one.** Then it derives `free_next` per §7 and seeks to the caller's `resume_frame` clamped to the timeline.

**Both sides, because both are needed:**

- `free_next` (§7) is defined over the **live Side B index**, so a Side-A mount that had not selected Side B could not compute it. `tape_respool` and `tape_promote` are both permitted from a Side-A mount and both allocate from `free_next`; with `free_next` degenerated to `a_high_water` they would allocate straight over Side B's live chunks, violating invariant 10.
- §9.3.1's adopt-in-place is safe only because Side A's entries satisfy §5.2's Side-A bound `last < a_high_water`. That bound has to have been *evaluated* for the argument to hold, and on a Side-B mount it would not have been.

**Outcomes:**

- **Side A has no valid index** (`TAPE_ERR_NO_VALID_INDEX` or `TAPE_ERR_INCONSISTENT` for that side) → **the mount fails with that error, whichever side was requested.** §5.3: a cartridge whose Side A cannot be selected is unusable.
- **Side A valid, Side B not** → **a mount requesting Side A succeeds**, with **`free_next = a_high_water`**. This is the state `tape_reset_side_b` exists to recover, and it can only be recovered from a successful mount. **A mount requesting Side B returns `TAPE_ERR_NO_VALID_INDEX`**, and `tape_set_side(TAPE_SIDE_B)` on the Side-A mount returns the same (`engine-api` §5) — without that, two calls reach a mounted state with no live index for the mounted side, where `total_frames`, `tape_tell` and `max_pos` are all undefined.
- Both valid → `free_next` per §7.

### 4.3 Effective writability

**One predicate authorises every write. It is the conjunction of two conditions, and DRAFT-4 stated only the first:**

```
effective_writable  =  (dev.write != NULL)  &&  (mounted version_minor == 0)
```

It is computed once at mount, stored in the instance, and exposed as `tape_info.writable`. **Every mutating call, and superblock repair, consults it.** A mount that is not effectively writable returns `TAPE_ERR_READ_ONLY` from every mutator and performs **zero** block writes — including no mirror repair.

> **V4-001, the blocker.** §4.1 phase 2 declared a `version_minor > 0` cartridge read-only, but every write authorisation in the API was defined solely by `dev.write != NULL`. On a writable device the state matrix therefore still permitted `reset_b`, `promote`, `respool` and — on Side B — `arm` against v1.1 media. A v1 engine could commit v1 indices and superblocks onto media whose newer minor semantics it does not understand, which is precisely the corruption the compatibility barrier exists to prevent. The barrier was written in one document and enforced in neither.
>
> The raw `dev.write != NULL` test survives *inside* `dev_write` as a last-line assertion (`engine-api.md` §3). It is no longer the permission model.

**Scope note — format and duplicate are outside this predicate.** `tape_format` and `tape_dup` take a raw `tape_dev`, not a mount. They read no version from the destination and are gated only on `dst_dev->write != NULL`. This is deliberate: the version barrier protects media you intend to keep using from *silent partial* writes by an engine that does not understand it. Erasing a cartridge is neither silent nor partial — it is what the work slot and the copy button are for, and a v1 player must be able to reclaim any card the household owns. A v2 cartridge placed in the work slot and copied over is destroyed on purpose.

---

## 5. Index slot (65 536 bytes = 128 blocks)

**Block 0 is the header and nothing else.** Bytes 64–511 reserved, zero.

| Offset | Size | Field |
|---|---|---|
| 0 | 8 | `magic` = `"TAPEIDX\x01"` |
| 8 | 4 | `sequence` (u32) |
| 12 | 1 | `side` — 0 = A, 1 = B |
| 13 | 3 | *reserved*, zero |
| 16 | 4 | `entry_count` (≤ `TAPE_MAX_ENTRIES`) |
| 20 | 8 | `total_frames` (u64) |
| 28 | 32 | *reserved*, zero |
| 60 | 4 | `crc32` — over bytes 0…59 concatenated with the entry array |

**The entry array begins at byte 512 — block 1.** Entry *i* at `512 + 12 × i`. Bytes beyond `512 + 12 × entry_count` are undefined and not CRC-covered.

`sequence` is monotonic **per cartridge**, shared across all four slots, incremented on every commit to either side.

### 5.1 Entry — a run over consecutive chunks

| Offset | Size | Field |
|---|---|---|
| 0 | 4 | `first_chunk_id` |
| 4 | 4 | `start_frame` — 0 … 131 071 |
| 8 | 4 | `frame_count` — ≥ 1; may exceed `CHUNK_FRAMES` |

**The run extent is computed in checked 64-bit and narrowed only after the bounds test:**

```
span = (uint64_t)start_frame + (uint64_t)frame_count - 1
last = (uint64_t)first_chunk_id + span / CHUNK_FRAMES
```

> DRAFT-3 expressed this in u32. With `start_frame = 131071` and `frame_count = 0xFFFFFFFF` the intermediate `start_frame + frame_count − 1` is 4 295 098 365, which wraps to **131 069** and validates clean — admitting a run whose physical extent reaches into the sandbox or past the device (V3-001). Arithmetic maxima are normative invalid-media cases.

#### The interval model — entries within one index must not overlap

Every entry occupies one **half-open interval of physical frames**, computed in 64-bit:

```
base_i = (uint64_t)first_chunk_id_i * CHUNK_FRAMES + (uint64_t)start_frame_i
end_i  = base_i + (uint64_t)frame_count_i          /* half-open: [base_i, end_i) */
```

**Requirement (part of §5.2 validity): for every pair of distinct entries *i*, *j* in the same index, the intervals are disjoint —**

```
end_i <= base_j  ||  end_j <= base_i
```

This is checkable from index metadata alone; **no chunk is read.** An implementation may check it any way it likes; a permitted bounded method is to sort an array of `entry_count` 16-bit entry indices by `base` (heapsort — in place, no recursion, ≤ 8 KiB of `mem`, O(n log n) at n ≤ 4 096) and compare adjacent pairs. That scratch array is inside the caller's `mem` block and counted in `tape_instance_size()`.

**Two entries may share a chunk**, and must be able to: a splice trim leaves two entries whose frame ranges fall in the same chunk on either side of the cut. What they may not do is claim the same physical frame twice. **The requirement is per index, not across sides** — Side B referencing chunks Side A also references is the copy-on-write mechanism (Rule 3) and is required, not merely tolerated.

> **V4-002.** DRAFT-4 stated the rule in prose and then offered a scalar "equivalently" — a bound on `total_frames` against a count of referenced chunks. It was not equivalent: two one-frame entries at the same physical frame give `total_frames = 2` against a permitted `CHUNK_FRAMES`, and pass. It was also **circular**: for Side B the expression depended on `free_next`, which §7 derives only from an already-validated live index, while non-overlap is part of deciding validity. The scalar test is deleted. The interval model above depends on nothing but the entry array and `CHUNK_FRAMES`, so it can be evaluated in phase 2 of slot validation with no ordering hazard.

Frames lie contiguously across the run: the first chunk contributes from `start_frame`, every intermediate chunk contributes all 131 072, the last is truncated by `frame_count`.

**A freshly re-spooled side is one entry; a freshly formatted side is zero entries.** Entries are consumed by edits, not by tape length. Each splice costs two entries, so a side starting as one entry has room for roughly 2 000 splices before re-spool.

Entries are ordered by timeline position; the position of entry *i* is the sum of `frame_count` over entries `0 … i−1`. A cached prefix-sum array is permitted and is not part of the on-media format.

### 5.2 Slot validity

A slot is **valid** iff all of:

- `magic` matches; `side` matches the slot's assignment; `entry_count ≤ TAPE_MAX_ENTRIES`; `crc32` verifies;
- `total_frames` equals the sum of `frame_count` over the entries, computed in 64-bit;
- `total_frames ≤ TAPE_MAX_TOTAL_FRAMES` (§5.4);
- every entry has `frame_count ≥ 1` and `start_frame < CHUNK_FRAMES`;
- every entry's `last` (§5.1) satisfies `last < total_chunks`;
- **every pair of entries has disjoint physical-frame intervals (§5.1);**
- **for Side A only:** every entry's `last < a_high_water`.

There is deliberately **no Side B lower bound.** Side B may reference chunks owned by Side A — see Rule 3 and §7.

Validity is evaluated against the superblock already selected by §4.1, and depends on nothing derived from either index.

### 5.3 Index-slot selection

DRAFT-1 had this rule; DRAFT-3 dropped it in restructuring, leaving implementations to invent one (V3-005). It is normative, it parallels §4.1, and **it performs no writes.**

For each side, classify both slots (A0/A1 or B0/B1) per §5.2, then:

- **Neither valid** → `TAPE_ERR_NO_VALID_INDEX` for that side.
- **Exactly one valid** → it is live. **The invalid partner is not repaired.** An invalid partner is the normal resting state after format (§9.6) and after every commit (§8) — repairing it would destroy the fallback the commit protocol depends on.
- **Both valid, different `sequence`** → the higher is live.
- **Both valid, equal `sequence`** → `TAPE_ERR_INCONSISTENT` for that side. Unreachable via §8; it means media fault or implementation bug, and it is not recovered from silently.

Side A in either error state: the cartridge is unusable. Side B in either: recoverable by `tape_reset_side_b`.

Promote's recovery (§9.3) depends on falling back from a newer-but-invalid A slot to the previous generation. That is this rule plus §5.2's Side A bound, and it is implementable byte-exactly.

### 5.4 Timeline cap

`total_frames` is capped at `TAPE_MAX_TOTAL_FRAMES` = 2³² − 1, which is 27.05 hours of audio — far beyond any cartridge this format describes. The cap exists because playback position is a 64-bit fixed-point value with 32 fractional bits, leaving 32 bits of whole frames (`engine-api.md` §6). Media declaring more is rejected at mount rather than becoming unseekable later (V3-010).

---

## 6. Chunks

131 072 frames of raw interleaved PCM. No header, no padding. A partially written chunk still occupies a full slot; bytes beyond the referenced range are **undefined, not zero**.

> Any comparison of "Side A is unchanged" must be over *referenced frames*, reconstructed through the index. A raw region compare produces false failures on the tail chunk of a run.

---

## 7. Ownership, reference, and allocation

**Ownership** partitions the chunk store:

- `[0, a_high_water)` — **owned by Side A.** No runtime path writes here, with exactly one exception: **promote phase 2** (§9.3), which writes low only after both live indices have been committed away from that region and only after an explicit disjointness check. Nothing else, ever.
- `[a_high_water, free_next)` — **allocated to Side B.**
- `[free_next, total_chunks)` — unallocated.

**Reference is separate from ownership.** Side B's index **may reference chunks owned by Side A**. That is precisely what `tape_reset_side_b` (§9.2) and a completed promote (§9.3) produce, and it is the copy-on-write mechanism that makes "start over" instant and makes Side B nearly free until it is edited.

What Side B may not do is **allocate or write** below `a_high_water`.

> DRAFT-3's engine invariant 4 required every Side B run to lie entirely at or above `a_high_water`. That forbids the format's own centrepiece: no implementation could pass both reset-B and that invariant (V3-009). The distinction between referencing and owning is the fix, and it is now Rule 3.

**`free_next` is derived at mount, never stored:**

```
free_next = max( a_high_water,
                 max over live-B entries of (last + 1) )
```

Entries referencing only Side A chunks yield `last + 1 ≤ a_high_water` and so do not raise it. Allocation is a bump pointer over that value and hands out **contiguous runs**.

Because it is derived from the *committed* index, chunks written by an operation that never committed sit above `free_next` on the next mount and are silently reused. **The aborted-write leak class does not exist.**

Chunks superseded by an overwrite sit below the live maximum and remain allocated until re-spool reclaims them. That is the only leak source, it is bounded, and it is **expected** — see `acceptance.md` WP-10, which DRAFT-3 got wrong in the opposite direction (V3-014).

---

## 8. The commit protocol

An index slot is 128 blocks and cannot be written atomically. Atomicity is by ordering:

1. Write chunk data for the operation.
2. **Flush.**
3. Write the entry array into blocks 1 … ⌈`entry_count` × 12 / 512⌉ of the **inactive** slot for this side.
4. **Flush.**
5. Write block 0 of that slot — the 64-byte header zero-padded to 512 — with the new `sequence`, `entry_count`, `total_frames` and the CRC over the entries just written. **This is the commit point.**
6. **Flush.**

Before step 5 the inactive slot's block 0 holds the previous generation's header, whose CRC does not match the newly written entries — so a crash before step 5 leaves an invalid slot and §5.3 falls back to the other one. A crash during step 5 leaves a header failing its own CRC, with the same result.

**Flush** means the data has reached media: on SD, the card has left the busy state, not merely accepted the blocks.

**Bounded cost.** For a recording commit, step 1's chunk data has already been written and flushed by `tape_service` before `tape_commit` is callable (`engine-api.md` §7). A commit therefore writes **at most 97 blocks** — 96 entry blocks at `TAPE_MAX_ENTRIES`, plus block 0 — and performs **exactly two flushes**. This bound is why `tape_commit` is a synchronous call with no budget (`engine-api.md` §7, V4-008); the measured worst case is a firmware criterion in `acceptance.md`.

**Stage clearing — an interrupted promote must not poison ordinary use.** `tape_arm`, `tape_reset_side_b` and `tape_respool` must, **after their own preconditions have passed and before their first index or chunk write**, check `promote_stage`. If it is 1, they write the superblock with `promote_stage = 0`, `promote_staging_chunk = 0`, `a_high_water` **unchanged** and `sb_generation` + 1 — mirror, flush, primary, flush — and only then proceed. `tape_promote` does **not** do this; it resumes per §9.3.3.

> **Why.** After §9.3 step 4 the cartridge is valid, playable, and both sides reference the staging run. Nothing stopped a child recording on Side B from there — and no ordinary operation writes the superblock, so `promote_stage` stayed 1 while B's index moved. Every later `tape_promote` then matched no row of §9.3.3 and returned `TAPE_ERR_INCONSISTENT` with zero writes: **one power loss during one superblock write, followed by entirely normal use, permanently disabled promote and reported it as a media fault.** Re-spool made it permanent rather than fixing it, because re-spool guarantees B ends as a single run at a *different* start. Clearing the stage at the three entry points that can precede an index commit lands every stage-1 state on a terminating classification in §9.3.0, and it costs one superblock update, once.
>
> **After preconditions, not before them.** These three calls have refusals that this document and `acceptance.md` both guarantee write nothing — `tape_respool` with no valid destination (`TAPE_ERR_CARTRIDGE_FULL`, "nothing changes"), `tape_arm` on Side A (`TAPE_ERR_READ_ONLY`) or with insufficient `entries_free` (`TAPE_ERR_INDEX_FULL`), `tape_respool` on an empty side (`TAPE_OK`, zero writes). Clearing "before doing anything else" would have made all four write a superblock before refusing. Clearing after the preconditions keeps every zero-write refusal intact and still guarantees what the rule is for: **no index commit ever lands on stage-1 media.**
>
> These three calls already require effective writability (§4.3), so nothing here writes to a mount that may not write. On a read-only mount `promote_stage` simply persists, which is correct: a source-slot cartridge plays fine in that state.

**The assumption:** a 512-byte SD block write is atomic under power loss. True of essentially all cards in practice; not universally guaranteed. Tested against real media under *Media atomicity* in `acceptance.md`, not inherited. See §13.

---

## 9. Operations

### 9.1 Record — overwrite, overdub, splice

All three allocate fresh chunks and commit per §8. None modifies a chunk in place.

- **Overwrite** replaces the timeline from the current position. Entries wholly covered are dropped; a partially covered entry is trimmed.
- **Overdub** reads existing frames, adds input at `int32`, and **clamps** to `[−32768, 32767]` — saturating, never wrapping. Exact formula in `engine-api.md` §8.
- **Splice** inserts at the current position. The run containing the insertion point is split into two entries; new entries for the inserted material go between them.

Every commit must leave an index satisfying §5.2, **including interval disjointness**. A trim that would leave two entries claiming the same physical frame is an implementation defect, not a permitted state.

`nominal_length_s` is not a limit; `total_chunks`, `TAPE_MAX_ENTRIES` and `TAPE_MAX_TOTAL_FRAMES` are.

**Cartridge full.** `tape_feed` reserves before accepting (`engine-api.md` §7) and returns `TAPE_ERR_CARTRIDGE_FULL` with a short accept. Frames already accepted remain owed and commit normally. **The child keeps everything recorded up to the moment it filled.**

**Index full.** An operation that would exceed `TAPE_MAX_ENTRIES` returns `TAPE_ERR_INDEX_FULL` and commits nothing. `tape_status` exposes `entries_free` so firmware can run the record light green → yellow → red; at red the record button does not hold. Recovery is re-spool.

### 9.2 Reset Side B

Copy the live Side A index into Side B's inactive slot with `side` = 1 and `sequence` + 1; commit per §8. **Moves no audio** — the resulting Side B references Side A's chunks, which Rule 3 permits. Sub-second.

Clears any device-side stored position for `(uuid, B)` (§11).

### 9.3 Promote Side B to Side A

The only destructive operation on Side A, and the only operation permitted to write below `a_high_water`. Incremental on the `block_budget` / `more_work` contract (`engine-api.md` §9), because a ~30 s blocking call in an engine that must service audio is not acceptable.

Throughout, `len = ⌈B.total_frames / CHUNK_FRAMES⌉` computed from the live Side B index in 64-bit, and `H` is the superblock's `a_high_water`.

#### 9.3.0 Entry classification — what a call does before it does anything

Evaluated at the first call of an operation, after mount state is known, **before any write**:

| Condition | Class | Action |
|---|---|---|
| Side B `total_frames == 0` | — | `TAPE_ERR_INVALID_ARG`, `*more_work = false`, **zero writes** |
| `promote_stage == 1` | **RESUME** | §9.3.3 |
| `promote_stage == 0` and A's and B's live entry arrays are **byte-identical** | **NOTHING TO DO** | `TAPE_OK`, `*more_work = false`, **zero writes** |
| otherwise | **FRESH** | §9.3.1 |

> Promoting an empty side would produce a zero-length entry, which §5.2 forbids, and would silently erase Side A — hence `TAPE_ERR_INVALID_ARG` rather than a no-op. Re-spool makes the opposite call for the same input, and §9.4 says why.
>
> **NOTHING TO DO** covers three real states with one rule: a cartridge whose promote already completed, a cartridge freshly reset-to-B (where B *is* A), and a cartridge whose phase 2 legitimately declined and cleared its stage. DRAFT-4 had no such rule and would have re-run a full copy on the first two.

#### 9.3.1 Phase 1 — get a compacted copy of B's timeline above the water line

**Adopt in place.** If B's live index is a **single entry** with `start_frame == 0` and `first_chunk_id ≥ H`, then B's timeline is already one compacted run lying wholly in Side B's own allocation. The staging run is that run, `S = first_chunk_id`. **No chunk is copied and no space is allocated**; steps 1 and 3 below are skipped.

Otherwise `S = free_next`, and the precondition applies: `total_chunks − free_next ≥ len`, else `TAPE_ERR_CARTRIDGE_FULL` with **zero writes**.

1. Write B's timeline, compacted, to `[S, S+len)`.
2. Commit a new **A** index — one entry `{first_chunk_id = S, start_frame = 0, frame_count = B.total_frames}`, `sequence` + 1.
3. **Commit a new B index referencing the same run**, `sequence` + 2.
4. Write the superblock with `a_high_water = S + len`, **`promote_stage = 1`, `promote_staging_chunk = S`** — mirror, flush, primary, flush.

After step 4 the cartridge is valid, playable, and both sides reference only `[S, S+len)`.

> **V4-004, and why the fix is a short-circuit rather than a detector.** A crash between steps 3 and 4 leaves A falling back to its previous generation (its new index references chunks ≥ the *old* `H`, which §5.2 rejects for Side A) while B's new index is valid — B has no lower bound. Derived `free_next` becomes `S + len`. DRAFT-4's re-run then computed the precondition against the *new* `free_next` and, on a cartridge with exactly `len` free chunks, returned `TAPE_ERR_CARTRIDGE_FULL` — refusing to finish a copy that was already durable and correct on the media. Repeated crashes at that boundary consumed a fresh staging run each time.
>
> Adopt-in-place removes the whole failure mode, and it does so **without needing to know a promote happened**. The state left behind by that crash is exactly "B is one compacted run above the water line", which is also what a plain re-spool produces — and in *both* cases the correct phase 1 is the same: adopt the run, commit A to it, raise the water line. No allocation, no reachability argument, and re-running is idempotent.

#### 9.3.2 Phase 2 — compact to the bottom

5. **Check that `[0, len)` is disjoint from the live set of both sides.**
   - If it is **not** disjoint: phase 2 declines. Write the superblock with **`promote_stage = 0`, `promote_staging_chunk = 0`**, `a_high_water` unchanged — mirror, flush, primary, flush — and return `TAPE_OK`. The cartridge is complete and correct, merely not compacted to the bottom.
   - **Space below `S` is stranded, and re-spool cannot reclaim it.** §9.4 requires every re-spool destination to lie at or above `a_high_water`, which the decline leaves at `S + len`. Only a later promote whose phase 2 succeeds — one following a genuinely different Side B — lowers the water line again. DRAFT-5's first cut said "until re-spool", which is wrong in the same way DRAFT-4's re-spool worked example was wrong: it described a reclamation the rules forbid.
6. Write the timeline to `[0, len)`.
7. Commit a new A index referencing `[0, len)`, `sequence` + 1.
8. Commit a new B index referencing `[0, len)`, `sequence` + 2.
9. Write the superblock with `a_high_water = len`, **`promote_stage = 0`, `promote_staging_chunk = 0`** — mirror, flush, primary, flush.

**Position clearing is not a step.** **Every `tape_promote` call returning `TAPE_OK` with `*more_work == false` clears the device-side stored positions for `(uuid, A)` and `(uuid, B)` (§11) before it returns** — the full path, the decline at step 5, every resume entry point, and the NOTHING TO DO classification. The `*more_work` condition is only to keep an incremental promote from rewriting the device's position table on every one of its hundreds of continuation calls; it is not a correctness distinction.

> As a numbered step 10 it was only reached on the uninterrupted full path. The decline at step 5 returns `TAPE_OK` having already replaced Side A's index in phase 1 step 2, and a crash between steps 9 and 10 leaves media final but positions stale.
>
> DRAFT-5's first cut then made it conditional on "has committed a new Side A index", which excluded three of the four paths the same sentence claimed to include: a resume at step 9 writes only a superblock, a resume at step 8 commits **B**, and a resume that re-tries step 5's decline write commits nothing. The stale entry survived on exactly the path the finding was raised about. **Clearing is idempotent and touches no media**, so the condition bought nothing and cost the guarantee — it is gone.

> **DRAFT-4's first cut proved step 5 unnecessary and the proof was wrong.** It argued that a compacted timeline of `len` chunks must reference at least `len` distinct chunks, so `free_next ≥ len` and `[0, len)` could not overlap `[S, S+len)`. That assumed entries never overlap each other — which §5.1 now requires, but which nothing checked at the time. An index with two entries both referencing chunk 0 would have made `S < len` and sent phase 2 straight through the only surviving copy. **The check replaces the proof.** A runtime test that costs one comparison is worth more than an argument that is correct only under an invariant stated two sections away.
>
> Step 5's decline path must still clear `promote_stage`, or the cartridge sits marked in-flight forever and every subsequent mount tries to resume a promote that has already decided not to happen.

#### 9.3.3 RESUME — `promote_stage == 1`

`S = promote_staging_chunk`. The live indices are compared against three shapes, in this order. **Each is decidable from the two entry arrays and the superblock; none requires reading a chunk, and none rests on an argument about what states are reachable.**

| Live A | Live B | Meaning | Resume at |
|---|---|---|---|
| single entry `{S, 0, N}` | byte-identical to A | phase 1 landed; phase 2 not committed | **step 5** |
| single entry `{0, 0, N}` | single entry `{S, 0, N}`, same `N`, **`S > 0`** | phase 2 committed A only | **step 8** |
| single entry `{0, 0, N}`, **`S > 0`** | byte-identical to A, and `H > len` | phase 2 committed both indices | **step 9** |
| anything else | | media fault or implementation defect | `TAPE_ERR_INCONSISTENT`, **zero writes** |

Resuming at step 8 performs **no chunk copy**: `[0, len)` is necessarily durable, because A's index committed at step 7 only after step 6's writes were flushed.

> **`S > 0` on row 2 is load-bearing.** Without it, rows 1 and 2 are the *same predicate* whenever `S == 0` — and `S == 0` is the ordinary first-use path: format leaves `a_high_water = 0`, the first Side B recording allocates from `free_next = 0` giving `{0, 0, N}`, and adopt-in-place then makes `S = 0`. A crash between steps 4 and 6 on that cartridge matched two rows, falsifying `engine-api` invariant 25 and the WP-10 assertion built on it. **Row 3 carries the same guard for the same reason.** `H > len` implies `S > 0` only through the engine's own `H = S + len` — which is exactly the kind of reachability argument this section promises not to rest on, and it fails on hand-crafted media: `promote_stage = 1`, `S = 0`, A ≡ B = `{0,0,N}`, `len = 5`, `H = 6` matches rows 1 **and** 3. With `S > 0` on rows 2 and 3, the three partition unconditionally — 1 against 2 and 1 against 3 by `S`, 2 against 3 by whether B is identical to A. (When `S == 0`, step 5 always declines, since the live set *is* `[0, len)`; only row 1 applies and it lands on the completed layout.)

#### 9.3.4 Recovery, by boundary

Every row is a mountable, playable cartridge unless stated. `H₀` is `a_high_water` before the promote.

| Crash point | `promote_stage` | Mounted state | Re-run behaviour |
|---|---|---|---|
| Before step 2 commits | 0 | Both sides at their previous generation | FRESH; chunks written above `free_next` are silently reused |
| Between 2 and 3 (allocating) | 0 | A's new index references ≥ `H₀` → §5.2 rejects → A falls back. **B untouched** | FRESH |
| Between 2 and 4 (adopt-in-place) | 0 | A falls back; B unchanged, still one compacted run above `H₀` | FRESH → adopt-in-place fires again. **No allocation** |
| Between 3 and 4 (allocating) | 0 | A falls back to its previous generation; **B at the phase-1 generation**, one compacted run `[S, S+len)` above `H₀`. Mixed pair, both internally valid | FRESH → **adopt-in-place fires**. No new allocation. *(V4-004)* |
| Between 4 and 6 | 1 | A ≡ B at `[S, S+len)`; `H = S+len` | RESUME → step 5 |
| Between 6 and 7 | 1 | As above; `[0, len)` written but referenced by nobody | RESUME → step 5 |
| **Between 7 and 8** | 1 | **A at `[0, len)`, B at `[S, S+len)`; `H = S+len`.** Both valid — A's `last = len−1 < H`. Both render identical audio | RESUME → **step 8**. *(V4-003)* |
| **Between 8 and 9** | 1 | **A ≡ B at `[0, len)`; `H` still `S+len`.** Chunks `[len, S+len)` unreachable — a permitted superseded-chunk leak | RESUME → **step 9**. *(V4-003)* |
| Decline at step 5, before its superblock lands | 1 | A ≡ B at `[S, S+len)` | RESUME → step 5 → declines again → retries the clearing write |
| After step 5's decline write | 0 | A ≡ B at `[S, S+len)`, `H = S+len` | NOTHING TO DO |
| After step 9 | 0 | A ≡ B at `[0, len)`, `H = len` | NOTHING TO DO |

> **Stage clearing interacts with two of these rows, safely and at a cost worth naming.** If `tape_arm`, `tape_reset_side_b` or `tape_respool` runs before the promote is resumed, §8 clears the stage and the next `tape_promote` classifies FRESH instead of RESUME. From the "between 7 and 8" row that means a full re-copy: adopt-in-place cannot fire (`S < H = S + len`), so it allocates at `free_next` and copies `len` chunks that were already durable at `[0, len)`. It terminates and it is safe — the destination is disjoint from both live sets and step 5 then succeeds — but on a nearly full cartridge it can return `TAPE_ERR_CARTRIDGE_FULL` where the direct resume needed no space at all. That is the price of not letting an interrupted promote poison ordinary use, and it is the right trade: the child who records on Side B has done nothing wrong.
>
> The "between 3 and 4" row corrects a claim in DRAFT-4's first cut that both indices would fall back. They do not: B has no lower bound, by design. The state is mixed but every generation present is internally valid and every referenced byte is intact, which is what the guarantee actually requires.

**Invariant after a completed phase 2:** `a_high_water == len`, `promote_stage == 0`, and no allocated chunk is unreachable.

### 9.4 Re-spool

Rewrites Side B's timeline as one contiguous run and commits, reclaiming superseded chunks.

**Empty Side B.** `total_frames == 0` → **`TAPE_OK`, `*more_work = false`, zero writes.** The index is left as it stands: valid, zero entries.

> **V4-005.** DRAFT-4 had no empty case at all: `len` computed to 0, the destination rule was vacuously satisfied, and WP-12's postcondition demanded exactly one entry while §5.2 forbids a zero-length one. Four different implementations were permissible. The no-op is the right answer because re-spool's contract is *make the timeline one contiguous run and reclaim what is stranded*, and an empty timeline is already maximally compact with nothing to reclaim. Contrast promote, which returns `TAPE_ERR_INVALID_ARG` on the same input: promoting an empty side **destroys Side A**. Same input, opposite answers, because the consequences are opposite — and `acceptance.md` asserts both.

**The rule, stated per pass** — DRAFT-3 stated it once and applied it only to the first (V3-003):

> Re-spool performs **at most two passes**. Before **each** pass, the destination must be a contiguous run of `len` chunks that is **(a)** entirely at or above `a_high_water`, and **(b)** disjoint from the live set — the chunks referenced by the live index of *either* side at that moment. Pass 2 runs only if such a run exists whose start is **strictly lower** than the current layout's start. If none exists, re-spool stops and keeps the pass-1 layout.

Two things this wording fixes from DRAFT-4's first cut. It said "a **free** contiguous run… strictly lower", and "free" elsewhere in this document means `≥ free_next` — so nothing strictly lower could ever qualify and pass 2 was unsatisfiable by construction. And it omitted the `a_high_water` floor, so a pass-2 destination could have landed on an unreferenced chunk *owned by Side A*, which is disjoint from the live set and still forbidden. Condition (a) closes that.

Pass 1 achieves compaction, which is what re-spool exists for. **The downward pass is opportunistic space reclamation, not a correctness requirement.**

> Worked example. `a_high_water = 10`; Side B is one live entry spanning chunks 10–11 (`len = 2`), so `free_next = 12`. The low destination `[10, 12)` overlaps the live set, so pass 1 writes `[12, 14)` and commits. Chunks 10 and 11 are now unreferenced, contiguous, at or above `a_high_water`, and number exactly `len` — so `[10, 12)` **passes** both conditions and pass 2 runs, landing the timeline back at the bottom and reclaiming the two chunks.
>
> DRAFT-4's first cut gave this example with `free_next = 11`, which cannot occur: a two-chunk run ending at chunk 10 would need `frame_count > CHUNK_FRAMES` with `last = 10`, contradicting §5.1. It then concluded that pass 2 declines. Both the arithmetic and the conclusion were wrong, and `acceptance.md` WP-12 required reproducing a state that cannot exist. Corrected in both documents.

**Precondition:** for a non-empty side, a pass-1 destination satisfying (a) and (b) must exist, else `TAPE_ERR_CARTRIDGE_FULL` and nothing changes. Pass 2 has no precondition beyond the test it performs itself.

**Re-spool does not always reduce the leak.** If pass 2 declines, pass 1 has moved the timeline up and stranded its old chunks — strictly more allocated-but-unreachable space than before. That is acceptable because it is bounded and the next re-spool or promote reclaims it, but it is a real property and it should not be described as though re-spool always frees space.

Re-spool preserves rendered audio bit-exactly. It commits nothing until a destination is fully written, so an interrupted pass leaves the previous index live and partial work above `free_next` for reuse.

### 9.5 Duplicate

Copies **Side A** — the music — from the source slot to the work slot. The destination is erased and reformatted in the process; that is what dubbing over a tape does, and it is announced by the first block written.

**The destination is a `tape_dev`, not a mounted `tape`.** DRAFT-4's first cut took a mounted destination, which made its own recovery rule impossible to follow: a blank card cannot be mounted (§4.1 phase 1 → `TAPE_ERR_BAD_MAGIC`) and an interrupted duplicate cannot be mounted either (phase 2 → `TAPE_ERR_INCOMPLETE`), so "re-run to finish" could never be performed. `tape_dup` therefore takes a raw device, exactly as `tape_format` does, and works on blank, valid and interrupted destinations alike.

**Side B is not copied.** The destination's Side B is initialised to mirror its new Side A, as a freshly formatted cartridge would be. **Duplicate copies the music, not the sandbox** — you are handing someone the album, not their sibling's scribbles over it, and the recipient gets a clean side to work on. This is a deliberate product decision, not an omission. *(The Verification Lead reviewed it as a product decision in the DRAFT-4 pass and did not recommend escalating it.)*

**Preconditions, in this order, all before any write:**

1. **Aliasing.** The destination device must not alias the source. The engine compares `dev.ctx` and, where the port can report device identity, that too. **A port that cannot distinguish two devices must not be handed the same one twice** — that obligation belongs to the port and is stated in `engine-api.md` §3. Aliasing → `TAPE_ERR_INVALID_ARG`.
2. **Writability.** `dst_dev->write == NULL` → `TAPE_ERR_READ_ONLY`. *(Unstated in DRAFT-4: a firmware path that wired the two slots backwards would have called a null pointer.)*
3. **Geometry.** `GEOMETRY_OK(dst_nominal_length_s, dst_dev->block_count)` (§2.1) → else `TAPE_ERR_GEOMETRY`. The caller supplies the destination's `nominal_length_s`; `total_chunks` is derived from it and from the destination's **own** `block_count`. **Nothing about the destination's geometry or label length comes from the source** — copying a C-90's `nominal_length_s` onto a C-60 store would produce a cartridge that cannot hold the time printed on it, which §2 defines as a defect.
4. **Capacity.** The source's Side A timeline must fit: `⌈src_A.total_frames / CHUNK_FRAMES⌉ ≤ total_chunks` and `src_A.total_frames ≤ TAPE_MAX_TOTAL_FRAMES`. Insufficient → `TAPE_ERR_DEST_TOO_SMALL`.

**Every one of the four refusals writes nothing** — all precede `WRITE_IN_PROGRESS`. The order is normative so that two implementations return the same error on a destination that fails more than one.

**Write order:**

Let `len_A = ⌈src_A.total_frames / CHUNK_FRAMES⌉`.

1. **If a structurally valid superblock exists on the destination**, write it with `state = WRITE_IN_PROGRESS`, `sb_generation` incremented, and **`promote_stage = 0`, `promote_staging_chunk = 0`** — mirror, flush, primary, flush. From here the destination does not mount as audio. *(On blank media there is nothing to invalidate; skip.)*
2. Write **A0, A1, B0 and B1** block 0 as 512 zero bytes each; flush.
3. Write the source's Side A timeline, **compacted, to `[0, len_A)`** on the destination; flush. Then write **A0** — its entry array (one entry `{0, 0, src_A.total_frames}`), flush, then its block 0 with `side = 0` and `sequence = 1`, flush — and **B0** with the same entry array but `side = 1` and `sequence = 2`. *(`side` must match the slot, per §5.2; a literal "identical to A0" would leave the destination's Side B unselectable — and under §4.2 that cartridge would mount on Side A only, contradicting this section's own promise that the destination gets a clean Side B.)*
4. Write the destination superblock with `state = VALID`, **`sb_generation = 1`**, **`a_high_water = len_A`**, `promote_stage = 0`, `promote_staging_chunk = 0`, the **caller-supplied fresh `cartridge_uuid`**, the caller-supplied `format_epoch`, and the destination's own geometry — mirror, flush, primary, flush. **This is the commit and the identity assignment, and it is last** (Rule 2).

> **DRAFT-5's first cut left three holes here, each of which produced a cartridge `tape_dup` reported as successful and the player could not read.**
>
> It never wrote `a_high_water`, so the new Side A index — referencing `[0, len_A)` — failed §5.2's Side A bound against a stale or zero water mark, giving `TAPE_ERR_NO_VALID_INDEX`, which §5.3 calls unusable. It said "write the source's Side A chunks" without saying *where*, while precondition 4 assumed compaction — so a layout-preserving copy of a C-90 onto a C-60 passed the precondition and then addressed chunks past the destination's store. And it committed "under §8", which selects the *inactive* slot: on reusable media A0 could still hold the **previous cartridge's** index at a far higher `sequence`, and §5.3 selects the higher sequence — so the copy could mount and play the wrong audio, silently. §9.6 avoids all three by writing slot 0 directly with fixed sequences; §9.5 now does the same.

**Permitted remount outcomes after a crash:**

| Crash point | Result |
|---|---|
| Inside step 1, before the mirror flush, reusable destination | The destination's old cartridge, unchanged |
| Inside step 1, after the mirror flush, reusable destination | `TAPE_ERR_INCOMPLETE` — the mirror carries `WRITE_IN_PROGRESS` at the higher generation and wins selection. Re-run `tape_dup` |
| After 1, before 4, reusable destination | `TAPE_ERR_INCOMPLETE`. Re-run `tape_dup` |
| Inside step 4, reusable destination | `TAPE_ERR_INCOMPLETE` — mirror is gen 1 `VALID`, primary still gen *n+1* `WRITE_IN_PROGRESS`, and the higher generation wins. Re-run `tape_dup`. Same generation-goes-backwards reasoning as §9.6 |
| Blank destination, before step 4's mirror flush | `TAPE_ERR_BAD_MAGIC`. Re-run `tape_dup` |
| **Blank destination, after step 4's mirror flush, before the primary** | **The completed copy.** Exactly one structurally valid superblock exists and both indices are durable, so §4.1 selects the mirror; phase 3 repairs the primary on an effectively writable mount, and a non-writable mount reports `needs_repair` |
| After 4 | The completed copy |

Re-running `tape_dup` to finish is possible precisely because it takes a device rather than a mount.

A copy is a different cartridge. Reproducing the UUID would make two objects claim one identity and silently merge the device-side state keyed by it (§11).

### 9.6 Format

Destructive and ordered (V3-008). The caller supplies UUID, epoch, label and `nominal_length_s`.

**Preconditions, before any write:** `dev->write == NULL` → `TAPE_ERR_READ_ONLY`; `GEOMETRY_OK(nominal_length_s, dev->block_count)` (§2.1) → else `TAPE_ERR_GEOMETRY`. Both write nothing.

1. **If a structurally valid superblock exists**, write it with `state = WRITE_IN_PROGRESS`, `sb_generation` incremented, and **`promote_stage = 0`, `promote_staging_chunk = 0`** — **mirror, flush, then primary, flush**, matching §4.1 and §9.5. *(Clearing the stage here matters: media carrying a damaged `promote_stage` would otherwise remount from an interrupted format as `TAPE_ERR_UNSUPPORTED_STATE`, an outcome `acceptance.md`'s format oracle does not permit.)* From here the cartridge does not mount. *On blank media there is nothing to invalidate — skip.*
2. Write A1 and B1 block 0 as 512 zero bytes each; flush.
3. Write A0 and B0 headers — valid, empty, `entry_count` 0, `total_frames` 0, `sequence` 1 and 2 respectively, CRC over the header alone; flush.
4. Write the **mirror** superblock: `state = VALID`, `sb_generation = 1`, `a_high_water = 0`, `promote_stage = 0`, `promote_staging_chunk = 0`; flush.
5. Write the **primary** superblock, byte-identical; flush. **This is the commit.**

**Resulting state.** Exactly one valid generation per side; A1 and B1 deliberately invalid. `TAPE_ERR_INCONSISTENT` therefore stays unreachable through normal operation, which is what makes it meaningful when it fires.

**`sb_generation` restarts at 1.** Format and duplicate establish a *new cartridge*, so the monotonicity rule of `engine-api.md` invariant 7 does not apply across them. On reusable media this means that between steps 4 and 5 the primary still carries the higher generation from step 1 — and it says `WRITE_IN_PROGRESS`, so §4.1 selects it and returns `TAPE_ERR_INCOMPLETE`. That is the correct answer, and it is why the generation going backwards at step 5 is safe rather than merely tolerable.

**Permitted remount outcomes after a crash:**

| Crash point | Result |
|---|---|
| Inside step 1, before the mirror flush, reusable media | The old cartridge, unchanged |
| Inside step 1, after the mirror flush, reusable media | `TAPE_ERR_INCOMPLETE` — the mirror carries `WRITE_IN_PROGRESS` at the higher generation and wins selection. Re-run format |
| After 1, before 5, reusable media | `TAPE_ERR_INCOMPLETE` — the primary still holds the step-1 `WRITE_IN_PROGRESS` at the higher generation and wins selection. Re-run format |
| Blank media, before step 4's flush | **`TAPE_ERR_BAD_MAGIC`** — no valid superblock has ever existed. This is the one case where "remount succeeds" cannot hold, and `acceptance.md` WP-10 permits it explicitly |
| **Blank media, after step 4's flush, before step 5** | **The new empty cartridge.** Exactly one structurally valid superblock exists — the mirror — and both empty indices are durable, so §4.1 phase 1 selects it and phase 2 passes. **On an effectively writable mount phase 3 repairs the primary and `needs_repair` is false; on a non-writable mount it mounts with `needs_repair` true** *(V4-014)* |
| After 5 | The new empty cartridge |

---

## 10. Sequence exhaustion

`sequence` and `sb_generation` are u32. At one commit per second that is 136 years. On reaching 0xFFFFFFFE the engine returns `TAPE_ERR_SEQUENCE_EXHAUSTED` and refuses further commits. Neither wraps.

---

## 11. What the cartridge does not store

**Playback position.** The source slot is read-only, so a cartridge played there has no writable surface. Position lives in the **device's** flash as a table keyed by `(cartridge_uuid, side)` → `position_frames` (u32), holding the ~64 most recently used entries, LRU eviction. The engine reports position at unmount and accepts it at mount; it never writes it to media. Firmware checkpoints on a cadence and resumes 2 s early — see `acceptance.md`.

- **Promote clears `(uuid, A)` and `(uuid, B)` on every `TAPE_OK` return with `*more_work == false`** — including the classification that changes nothing. Usually both timelines changed. When they did not — press promote straight after a reset-B and it is correctly a no-op — the Side A position is cleared anyway and a 20-minute mark is lost. That is deliberate: after an interrupted promote the engine cannot tell a stale entry from a live one, clearing is idempotent, and resuming at a frame index from a timeline that no longer exists is worse than starting over.
- Reset B clears `(uuid, B)`.
- Duplicate assigns a fresh UUID, so the destination simply has no entry.

**The position table is the UUID's only sanctioned consumer.** Adding another is an escalation, because every consumer is a new place where duplicate identities cause harm.

---

## 12. Instant-on is not a format feature

Two firmware mechanisms, neither on the card:

1. **Wake from sleep with a cartridge mounted.** The caller's play ring is retained across sleep and passed to `tape_mount` as a warm-start descriptor; rendering begins from it while `tape_service` re-establishes the card.
2. **Cold insert.** Card initialisation begins on the cartridge-detect switch, not on the play press.

**The warm-start descriptor carries `uuid`, `side`, `start_frame`, `valid_frames` and `data_bytes`** (`engine-api.md` §5). DRAFT-3 passed a bare pointer and length with no identity, so a ring retained from cartridge X side A could be rendered into a mount of cartridge Y side B with nothing to detect it (V3-016). **A mismatch disables warm start; it does not fail the mount** — a wrong buffer should cost instant-on, not the cartridge.

Guardrail 04 (wake to audio < 100 ms) is enforced, measured and tested in `firmware/`.

---

## 13. Assumptions this format inherits

1. A 512-byte SD block write is atomic under power loss (§8). Tested on real media under *Media atomicity* in `acceptance.md`, against the harness's torn-write mode.
2. A flush returning success means data has reached media.
3. Card wear from re-spool and promote is acceptable at family write volumes.
4. A cartridge is never mounted by two hosts concurrently.
5. `block_count` may be wrong; §2.1 and §4.1 phase 2 are the defence.

---

## 14. Freeze scope and what is still open

**§§1–8 are the freeze candidate** — constants, lengths, the geometry predicate, layout, superblock, mount, index, chunks, ownership, and the commit protocol. That is the byte-level surface the Software Lead's read path and the golden fixtures are built against, and it is the part the DRAFT-4 pass found structurally sound.

**§9 and `engine-api.md` §10 do not freeze with them.** They are behaviour, and behaviour freezes when tests prove it, not when prose settles. They freeze at the first green WP-10 run.

Open, in §9 and beyond:

- §9.3's `promote_stage` is new and load-bearing. Every claim about resume now rests on a stored value rather than on inference, which is the improvement — but the field itself has had one review pass by its author and none by anyone else.
- Whether `TAPE_ERR_INCOMPLETE` should distinguish an interrupted duplicate from an interrupted format. Both are recovered by re-running the operation, so the distinction may not earn its field.
- Michael's note that a child may lose patience with a 43-second C-90 copy — a firmware LED behaviour, not a format concern.
