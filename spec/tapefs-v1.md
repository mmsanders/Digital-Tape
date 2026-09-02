# spec/tapefs-v1.md — TAPEFS v1.0

**Revision:** DRAFT-3 · **Issued:** 2 Sep 2026 · **Status:** for adversarial review; not frozen
**Owner:** Program Manager. Changes require PM sign-off (escalation trigger #1).
**Supersedes:** DRAFT-1 (31 Aug). Incorporates verification findings V-001…V-022, issues #3, #4, #14, and Michael's answers to Q-002, Q-003, Q-004.

This is the on-media format for a Digital Tape Player cartridge. It is normative and byte-exact. Where it is ambiguous, that is a defect — report it.

---

## 0. Two design rules that govern everything below

**Rule 1 — The engine computes. The caller owns anything that needs entropy, hardware knowledge, or memory beyond the engine's budget.** The cartridge UUID, the format epoch, the warm-start buffer, and the block device's geometry are all supplied by the caller. The engine never generates identity, never reads a clock, and never trusts `block_count`.

**Rule 2 — Identity and validity are written last, after the content they describe.** Every operation that changes what a cartridge *is* — format, duplicate, promote — writes the audio and the index first and the superblock that makes them valid last. A cartridge interrupted mid-operation is therefore recognisably unfinished, never silently wrong.

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
| `TAPE_MAX_ENTRIES` | 4 096 (occupies blocks 1–96 of a slot) |

All multi-byte integers are little-endian. All CRCs are CRC-32/ISO-HDLC: polynomial 0xEDB88320 (reflected), init 0xFFFFFFFF, reflect in and out, final XOR 0xFFFFFFFF.

---

## 2. Tape lengths

A cartridge's length is a **format-time parameter**, not a format constant. `nominal_length_s` in the superblock records it and every region size is derived from it at format time (ADR-008).

| Designation | `nominal_length_s` | Side A store | Chunks | Copy at high-speed 4-bit (~22 MB/s) |
|---|---|---|---|---|
| **C-60 — the standard cartridge** | 3 600 | 635 MB | 1 211 | ~29 s |
| C-90 | 5 400 | 953 MB | 1 817 | ~43 s |
| C-120 | 7 200 | 1 270 MB | 2 422 | ~58 s |

**C-60 is the standard.** It meets the 30-second copy requirement on the plain 3.3 V high-speed interface with no UHS-I switching and with a write rate every V30 card guarantees. Longer cartridges are permitted by the format and are expected to exist; they copy more slowly and the label says what they are. Nothing in this format closes off longer lengths, and nothing in it should.

`nominal_length_s` is what the label says. It is not a limit on Side B's timeline (§9.1).

---

## 3. Media layout

The card carries an MBR with two partitions. **Provisioning the MBR and partition 1 is `tapectl`'s job, not the engine's.** Every `tape_dev` the engine sees is a block view of partition 2 alone; LBA 0 below is the first block of partition 2.

| # | Type | Size | Contents |
|---|---|---|---|
| 1 | 0x0C FAT32 | 16 MiB | `README.TXT` and optional label art. Never read by the device. |
| 2 | 0xDA | remainder | TAPEFS |

| LBA | Blocks | Region |
|---|---|---|
| 0 | 8 | Superblock, primary. Block 0 used; 1–7 reserved, zero. |
| 8 | 128 | Index slot **A0** |
| 136 | 128 | Index slot **A1** |
| 264 | 128 | Index slot **B0** |
| 392 | 128 | Index slot **B1** |
| 520 | 1 528 | Reserved, zero (alignment padding) |
| 2 048 | `total_chunks × 1024` | Chunk store. Chunk *N* begins at `lba_chunk_base + N × 1024`. |
| *last block* | 1 | Superblock, mirror |

There is no preroll cache. Instant-on is not a format feature (§12).

---

## 4. Superblock (512 bytes)

| Offset | Size | Field | Notes |
|---|---|---|---|
| 0 | 8 | `magic` | `54 41 50 45 46 53 00 01` — `"TAPEFS\0\x01"` |
| 8 | 2 | `version_major` | 1 |
| 10 | 2 | `version_minor` | 0 |
| 12 | 4 | `sb_generation` | Incremented on every superblock write. See §4.1 |
| 16 | 1 | `state` | 0 = `VALID`, 1 = `WRITE_IN_PROGRESS`. See §9.5 |
| 17 | 3 | *reserved* | zero |
| 20 | 16 | `cartridge_uuid` | Caller-supplied. RFC 4122 v4 by convention; the engine only stores it |
| 36 | 4 | `sample_rate` | 44100 |
| 40 | 2 | `channels` | 2 |
| 42 | 2 | `bits_per_sample` | 16 |
| 44 | 4 | `chunk_bytes` | 524288 |
| 48 | 4 | `nominal_length_s` | Label value. §2 |
| 52 | 4 | `total_chunks` | Capacity of the chunk store |
| 56 | 4 | `a_high_water` | Chunk ids `[0, a_high_water)` are Side A, immutable |
| 60 | 4 | `index_slot_bytes` | 65536 |
| 64 | 4 | `lba_index_a0` | 8 |
| 68 | 4 | `lba_index_a1` | 136 |
| 72 | 4 | `lba_index_b0` | 264 |
| 76 | 4 | `lba_index_b1` | 392 |
| 80 | 4 | `lba_chunk_base` | 2048 |
| 84 | 4 | `lba_superblock_mirror` | partition size − 1 |
| 88 | 32 | `label` | UTF-8, NUL-padded. Advisory; the printed label is authoritative |
| 120 | 4 | `format_epoch` | Caller-supplied Unix time at format. Informational |
| 124 | 384 | *reserved* | zero |
| 508 | 4 | `crc32` | Over bytes 0…507 |

**Forward compatibility.** Bytes 0–19 — magic, both version fields, `sb_generation`, `state` — are frozen across all future major versions. A v1 reader must be able to read them from v2 media in order to refuse it correctly.

### 4.1 Two-copy protocol

Both superblocks carry `sb_generation`. **Every superblock update writes the mirror first, flushes, then writes the primary, flushes.** Each write is a single 512-byte block.

On mount, read both. A copy is *structurally valid* iff its magic matches and its CRC verifies. Then:

- Neither valid → `TAPE_ERR_BAD_MAGIC` or `TAPE_ERR_CRC`.
- Exactly one valid → use it. On a **writable** device, rewrite the other from it. On a read-only device (`write == NULL`), use it without repair; `tape_get_info` reports `needs_repair`.
- Both valid, different `sb_generation` → use the higher.
- Both valid, equal `sb_generation` → they must be byte-identical. If not, `TAPE_ERR_INCONSISTENT`.

**Only then** check `version_major`. If it is not 1 → `TAPE_ERR_VERSION`, and the engine touches nothing. An unsupported version is not corruption and must never trigger repair; that is how an old reader would downgrade new media. `version_minor` > 0 → mount read-only.

**Then** check `state`. `WRITE_IN_PROGRESS` → `TAPE_ERR_INCOMPLETE`. The cartridge is an interrupted duplicate; the remedy is to run the duplicate again.

**Then** validate geometry, before any further I/O:

- `sample_rate`, `channels`, `bits_per_sample`, `chunk_bytes`, `index_slot_bytes` equal the constants in §1;
- the six `lba_*` fields equal the values in §3, and `lba_superblock_mirror == block_count − 1`;
- `a_high_water ≤ total_chunks`;
- `lba_chunk_base + total_chunks × 1024 ≤ block_count`, computed in 64-bit;
- `total_chunks ≥ 1`.

`block_count` comes from the caller and is **untrusted input** — geometry checks exist to protect against it as much as against the card. Any failure → `TAPE_ERR_GEOMETRY`.

---

## 5. Index slot (65 536 bytes = 128 blocks)

**Block 0 is the header and nothing else.** Bytes 64–511 are reserved and must be zero.

| Offset | Size | Field |
|---|---|---|
| 0 | 8 | `magic` = `"TAPEIDX\x01"` |
| 8 | 4 | `sequence` (u32) |
| 12 | 1 | `side` — 0 = A, 1 = B |
| 13 | 3 | *reserved*, zero |
| 16 | 4 | `entry_count` (≤ `TAPE_MAX_ENTRIES`) |
| 20 | 8 | `total_frames` (u64) — sum of `frame_count` over all entries |
| 28 | 32 | *reserved*, zero |
| 60 | 4 | `crc32` — over bytes 0…59 concatenated with the entry array |

**The entry array begins at byte 512 — block 1.** Entry *i* is at byte `512 + 12 × i`. Bytes beyond `512 + 12 × entry_count` are undefined and not CRC-covered.

### 5.1 Entry — a run over consecutive chunks

| Offset | Size | Field |
|---|---|---|
| 0 | 4 | `first_chunk_id` |
| 4 | 4 | `start_frame` — 0 … 131 071, offset into the first chunk |
| 8 | 4 | `frame_count` — ≥ 1; **may exceed `CHUNK_FRAMES`** |

A run occupies chunk ids `first_chunk_id, first_chunk_id + 1, …, last_chunk_id` where

```
last_chunk_id = first_chunk_id + (start_frame + frame_count − 1) / CHUNK_FRAMES
```

(integer division). Frames are laid out contiguously across the run: the first chunk contributes frames `start_frame …`, every subsequent chunk contributes all 131 072 of its frames, and the last is truncated by `frame_count`.

**Consequence:** a freshly formatted or freshly re-spooled side is **one entry**. Entries are consumed by edits, not by tape length. Each splice costs two entries (one split, one insert), so a side that starts as one entry has room for roughly **2 000 splices** before re-spool. (Earlier documents said 4 000; that counted entries, not splices.)

Entries are ordered by timeline position. The timeline position of entry *i* is the sum of `frame_count` over entries `0 … i−1`. Implementations may cache a prefix-sum array; it is not part of the on-media format.

`sequence` is monotonic **per cartridge**, shared across all four slots, incremented on every commit to either side.

### 5.2 Validity

A slot is **valid** iff all of:

- `magic` matches; `side` matches the slot's assignment; `entry_count ≤ TAPE_MAX_ENTRIES`; `crc32` verifies;
- `total_frames` equals the sum of `frame_count` over the entries;
- every entry has `frame_count ≥ 1`, `start_frame < CHUNK_FRAMES`, and `last_chunk_id < total_chunks`;
- **for Side A:** every entry has `last_chunk_id < a_high_water`.

The Side A check is against the *last* chunk of each run, not the first. This is the invariant that keeps the sandbox out of the music, and an off-by-one at the end of a run is the way it would fail.

---

## 6. Chunks

A chunk is 131 072 frames of raw interleaved PCM. No header, no padding. A chunk written partially still occupies a full slot; bytes beyond the referenced range are **undefined, not zero**.

> Any comparison of "Side A is unchanged" must be over *referenced frames*, reconstructed through the index. A raw region compare produces false failures on the tail chunk of a run.

---

## 7. Allocation

Chunk ids partition as:

- `[0, a_high_water)` — Side A. Immutable. No runtime code path writes here.
- `[a_high_water, free_next)` — allocated to Side B.
- `[free_next, total_chunks)` — free.

**`free_next` is derived at mount, never stored:**

```
free_next = max over live-B entries of (last_chunk_id + 1), floored at a_high_water
```

Allocation is a bump pointer over that value and hands out **contiguous runs**. Because it is derived from the *committed* index, chunks written by an operation that never committed are above `free_next` on the next mount and are simply reused. The aborted-write leak class does not exist.

Chunks superseded by an overwrite sit below the live maximum and remain allocated until re-spool (§9.4) reclaims them. That is the only leak source, and it is bounded.

---

## 8. The commit protocol

An index slot is 128 blocks and cannot be written atomically. Atomicity is by ordering:

1. Write chunk data for the operation.
2. **Flush.**
3. Write the entry array into blocks 1 … ⌈`entry_count` × 12 / 512⌉ of the **inactive** slot for this side.
4. **Flush.**
5. Write block 0 of that slot — the 64-byte header, zero-padded to 512 — with the new `sequence`, `entry_count`, `total_frames`, and the CRC over the entries just written. **This is the commit point.**
6. **Flush.** `tape_commit` returns success only after this flush succeeds. If it fails, return `TAPE_ERR_IO`; the on-media state is indeterminate until remount, at which point the ordinary mount rules resolve it.

Before step 5, block 0 holds the previous generation's header, whose CRC does not match the new entries; a crash before step 5 leaves an invalid slot and mount falls back to the other one. A crash during step 5 leaves a header that fails its own CRC, with the same result.

**Flush** means the data has reached media: on SD, the card has left the busy state, not merely accepted the blocks.

**The assumption:** a 512-byte SD block write is atomic under power loss. True of essentially all cards in practice; not universally guaranteed. It is tested against real media in WP-19, not inherited. See §13.

---

## 9. Operations

### 9.1 Record — overwrite, overdub, splice

All three allocate fresh chunks and commit per §8. None modifies a chunk in place.

- **Overwrite** replaces the timeline from the current position. Entries wholly covered are dropped; a partially covered entry is trimmed.
- **Overdub** reads existing frames, adds input sample-wise at `int32`, and **clamps** to `[−32768, 32767]` — a saturating clamp, never a wrap. Exact formula in `engine-api.md` §8.
- **Splice** inserts at the current position, pushing everything after it later. The run containing the insertion point is split into two entries; new entries for the inserted material go between them.

`nominal_length_s` is not a limit. Side B's timeline may exceed it. The limits are `total_chunks` and `TAPE_MAX_ENTRIES`.

**Cartridge full.** `tape_feed` reserves capacity before accepting frames (`engine-api.md` §7) and returns `TAPE_ERR_CARTRIDGE_FULL` with a short accept when allocation would pass `total_chunks`. Frames already accepted remain owed and are committed normally. **The child keeps everything recorded up to the moment it filled.**

**Index full.** An operation that would exceed `TAPE_MAX_ENTRIES` returns `TAPE_ERR_INDEX_FULL` and commits nothing. `tape_status` exposes `entries_free` so firmware can show headroom before the wall (Q-003: the record light runs green → yellow → red, and at red the record button does not hold). Recovery is re-spool.

### 9.2 Reset Side B

Copy the live Side A index into Side B's inactive slot with `side` = 1 and `sequence` + 1; commit per §8. Moves no audio. Sub-second.

### 9.3 Promote Side B to Side A

The only destructive operation on Side A. Two phases, each individually crash-safe under §8 and §4.1:

**Phase 1.** Write B's timeline, compacted, to free chunks beginning at `free_next` → range `[S, E)`. Commit a new A index referencing `[S, E)` as one entry. Write the superblock with `a_high_water = E` (mirror, then primary).

**Phase 2.** Write the same timeline again to `[0, len)`. Commit a new A index referencing `[0, len)`. Write the superblock with `a_high_water = len`. Commit a new B index identical to A.

**Recovery.** A crash in phase 1 before its superblock write leaves an A index referencing chunks ≥ `a_high_water`, which §5.2 rejects; mount falls back to A's previous generation and the promote did not happen. A crash after phase 1's superblock but before phase 2 completes leaves a valid, playable cartridge whose Side A lives high and whose space below is stranded; re-running promote completes phase 2.

**Invariant after a completed promote:** `a_high_water == ⌈len / CHUNK_FRAMES⌉` and the cartridge contains no unreachable allocated space.

Promote invalidates any device-side stored position for (this UUID, Side A) — §11.

### 9.4 Re-spool

Rewrites Side B's timeline as one contiguous run and commits a new index, reclaiming superseded chunks.

**The rule that makes it safe:** re-spool writes only to a destination region **disjoint from every chunk the live index references**, then commits. The engine chooses the lowest such region: `[a_high_water, …)` when that is disjoint from the live set, otherwise `[free_next, …)`. On a fragmented cartridge that is two passes — up, then down — each crash-safe.

**Precondition:** free space ≥ the timeline length, else `TAPE_ERR_CARTRIDGE_FULL`. A nearly full cartridge cannot be re-spooled.

Re-spool preserves rendered audio bit-exactly. It is incremental and interruptible; it commits nothing until the destination is fully written, so an interrupted re-spool leaves the previous index live and partial work above `free_next` for reuse.

### 9.5 Duplicate

Whole-cartridge copy, source slot → work slot. The destination is **erased**; that is what dubbing over a tape does, and it is announced by the first block written.

1. Write the destination superblock with `state = WRITE_IN_PROGRESS` (mirror, then primary). From here the destination does not mount as audio.
2. Write Side A's chunks, then A's index, then B's index (B mirrors A). All under §8.
3. Write the destination superblock with `state = VALID`, the **caller-supplied fresh `cartridge_uuid`**, the caller-supplied `format_epoch`, and the source's `nominal_length_s` and geometry. Mirror, then primary. **This is the commit and the identity assignment, and it is last** (Rule 2).

A crash anywhere between 1 and 3 leaves `TAPE_ERR_INCOMPLETE` on mount — an unfinished copy, not corruption. Re-run to finish.

A copy is a different cartridge. Reproducing the UUID would make two physical objects claim one identity, and device-side state keyed by UUID (§11) would silently merge them.

### 9.6 Format

`tape_format` receives the UUID, epoch, label and `nominal_length_s` from the caller and writes, byte-exactly:

| Region | State |
|---|---|
| Both superblocks | `state = VALID`, `sb_generation = 1`, `a_high_water = 0` |
| A0 | Valid, empty: `sequence` = 1, `side` = 0, `entry_count` = 0, `total_frames` = 0, CRC over the header only |
| A1 | **Invalid:** all 512 bytes of block 0 zero |
| B0 | Valid, empty: `sequence` = 2, `side` = 1 |
| B1 | **Invalid:** all 512 bytes of block 0 zero |

Exactly one valid generation per side; the partner deliberately invalid. `TAPE_ERR_INCONSISTENT` therefore stays unreachable through normal operation.

---

## 10. Sequence exhaustion

`sequence` and `sb_generation` are u32. At one commit per second that is 136 years. On reaching 0xFFFFFFFE the engine returns `TAPE_ERR_SEQUENCE_EXHAUSTED` and refuses further commits. Neither wraps.

---

## 11. What the cartridge does not store

**Playback position.** The source slot is read-only, so a cartridge played there has no writable surface. Position lives in the **device's** flash as a table keyed by `(cartridge_uuid, side)` → `position_frames` (u32), holding the ~64 most recently used entries with least-recently-used eviction. The engine reports position at unmount and accepts it at mount; it never writes it to media. Firmware checkpoints on a cadence and resumes 2 s early — `spec/acceptance.md`. Promote clears the (UUID, A) entry; reset B clears the (UUID, B) entry.

**The position table is the UUID's only sanctioned consumer.** Adding another is an escalation, because every consumer is a new place where duplicate identities cause harm.

Michael has accepted the consequence (Q-004): a tape resumes where *this player* left it, not where the tape was last played.

---

## 12. Instant-on is not a format feature

Two firmware mechanisms, neither on the card:

1. **Wake from sleep with a cartridge mounted.** The caller-supplied play ring is retained across sleep and `tape_mount` accepts it as a warm-start buffer; rendering begins from it while `tape_service` re-establishes the card.
2. **Cold insert.** Card initialisation begins on the cartridge-detect switch, not on the play press. A child's hand takes longer to reach play than the card takes to come up.

Guardrail 04 (wake to audio < 100 ms) is enforced in `firmware/`, measured there, and tested there.

---

## 13. Assumptions this format inherits

1. A 512-byte SD block write is atomic under power loss (§8). Tested on real media in WP-19 using the fault-injection harness's torn-write mode as the comparison.
2. A flush that returns success means data has reached media.
3. Card wear from re-spool and promote is acceptable at family write volumes.
4. A cartridge is never mounted by two hosts concurrently.
5. `block_count` may be wrong; §4.1's geometry checks are the defence.

---

## 14. Open before freeze

- The Side-B-has-no-warm-start asymmetry: `tape_mount` warm-start applies to whichever side was mounted at sleep. Confirm this reads correctly in `engine-api.md`.
- Whether `TAPE_ERR_INCOMPLETE` should carry enough information for firmware to distinguish "interrupted copy" from "interrupted promote". Currently both are recoverable by re-running the operation, and the distinction may not matter.
- Michael's note that a child may lose patience with a 43-second C-90 copy — flagged for the LED-row behaviour in firmware, not a format concern.
