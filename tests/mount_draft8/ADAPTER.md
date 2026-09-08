# Public-API probe and remaining adapter boundary

## Implemented mechanical probe

`mount_probe.c` calls only DRAFT-8 public functions: `tape_instance_size`, `tape_init`,
`tape_mount`, `tape_get_info`, and `tape_tell`. It uses fresh caller-owned instance,
play-ring and record-ring storage per process. `warm == NULL` and the fixture-selected
side/resume position are passed unchanged. No engine internals are observed.
The engine version of the build **must include the actual public header** through
`TAPE_PUBLIC_HEADER`; `candidate_api.h` exists only to compile/audit the standalone
verifier probe and its negative control. Do not use that transcription to force a
mismatched product ABI to link.

Fixture envelope (little-endian): magic `VM08` at 0; u32 block_count at 4; u32 side
at 8; u64 resume at 12; u32 writable at 20; u32 fail-write ordinal at 24; u32
fail-flush ordinal at 28; followed by 512 bytes primary, 512 bytes mirror, and four
65536-byte slots A0/A1/B0/B1. Callback LBAs refer to the cartridge partition, not
envelope offsets. Block zero and `block_count - 1` map to those two superblocks;
LBAs 8–519 map to the four slots. Other bytes read as poison. Reads, writes and
flushes are counted across init, mount, and post-mount queries. The read/write
callbacks reject out-of-range batches using widened arithmetic before copying.

`writable == 0` installs a real NULL write callback. Fault ordinals are one-based
callback numbers; zero disables faults. This tranche's only permitted write is
one 512-byte superblock repair, so callback and block ordinals coincide. Failed
writes are fail-before-write; successful writes update the in-memory image;
flush failures leave written bytes observable. This is **not a power-loss model**.
The existing fault/crash harness remains the foundation for WP-10.

The probe emits JSON with actual callback events, attempted repair bytes, return
codes, info, position, and final superblock bytes. `run.py` compares observations
against independent expectations and checks no chunk reads, no out-of-range I/O,
no writes/flushes on failing or read-only paths, exact repair destination/bytes,
and repair after required metadata reads. It does not demand a particular read
batching strategy. For neither structurally valid superblock, TapeFS §4.1 permits
BAD_MAGIC **or** CRC; the tests retain that set and invent no error precedence.
If the repair write fails, no flush count is imposed; successful repair writes
must be followed by one flush. Both repair failures must leave the mount queryable
and `needs_repair` true. Explicit FAULTED-call rejection testing is outside this probe.

Mechanical header names, include paths, link paths and equivalent symbol mappings
are permissible integration changes. Record them. Any assertion, accepted result,
range, case, failure treatment or scope change goes back to Verification/PM.
Do not implement a fake `tape_mount`, precompute expected answers, or add product APIs
so the tests build.

## Running sequence is not observable in this tranche

TapeFS §5.5 defines the maximum over **all structurally valid** slots. The public
`tape_info` has no sequence field; mount does not commit an index. Therefore the
fixture `M-structural-high-sequence-semantic-invalid` proves only that a high-sequence,
semantically invalid partner does not prevent selecting valid media. It does **not**
prove the counter was retained. A subsequent independently tested commit/reset/
promotion operation and its written header are required to observe sequence use.
Likewise, the four-commit running-counter requirement remains untested.

## Allocation and write-destination boundary

`free_chunks == total_chunks - derived_free_next` is observable at mount and tested
from live B even when A was requested, including lawful references below the water
mark, stale/invalid B partners, gaps, multi-chunk runs, and degraded-B. This is not
proof of an allocator's later decisions. There is no public allocate-only function.

`ownership.py` provides executable predicates for a future **verifier trace adapter**:

- For ordinary bump allocation, record the pre-allocation `a_high_water`, current
  free pointer, capacity, returned start, and chunk count. Assert a positive
  contiguous run beginning at the current pointer and bounded by the store.
- For ordinary Side-B audio writes, classify actual callback LBAs as audio first,
  then check the full batch interval against `[base + H*1024, base + capacity*1024)`.
  Do not classify legal Side-B **references** below H as writes or allocations.
- Obtain live indices and H from verifier-decoded committed media, not an internal
  implementation claim. Advance the free pointer within the operation from actual
  verified allocation evidence. A missing event is a failed trace, not a skip.
- Validate disjointness on every committed index using the verifier's byte decoder.
  Later re-spool/promote adapters must use their own **per-pass live sets** and
  exceptions. The ordinary predicate must never be applied to promote phase 2,
  format/duplicate, or re-spool's opportunistic second pass.

This is a test observation contract, **not an invented product API**. Integration
must demonstrate where allocation events come from or use public recording/edit
operations after their independent tests exist. No allocation event adapter, real
allocation trial, or 10,000 random edit sequence run was executed here. Until those
exist, the allocator/operation merge hold remains for that uncovered behaviour.
