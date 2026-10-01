# WP-09 R52 mechanical adapter contract

The Product adapter is observation plumbing, not an oracle.  It may call only
the frozen public engine API and instrument the supplied `tape_dev` callbacks.
It must not expose private allocator state, inspect Product internals, filter
callbacks, synthesize expected media, or supply a verdict consumed by the
oracle.

## Case setup

For the selected row in `evidence/plan.json`, construct the raw stage-0 fixture
described below, byte-for-byte, with an independently chosen cartridge UUID:

- **Superblock (tapefs §4), primary and mirror byte-identical:** every §4 field
  filled, as `synthetic.py`'s `superblock()` demonstrates:
  - version 1.0, `state` VALID, any UUID, and an inert `sb_generation`;
  - sample rate 44,100, 2 channels, 16 bits, `chunk_bytes` 524,288;
  - `nominal_length_s` 9 / 12 / 15 for `total_chunks` 4 / 5 / 6, so that §2
    derives exactly the stored `total_chunks` (GEOMETRY_OK);
  - `a_high_water` 2;
  - index slot bytes 65,536;
  - LBAs A0 8, A1 136, B0 264, B1 392, chunk base 2048, and mirror
    `block_count − 1`, where `block_count = 2048 + total_chunks × 1024 + 1`.

  A fixture missing these fields is unmountable (§4.1 phase 2).
- **Side A:** A0 is a structurally valid, **empty** Side-A index at **sequence
  1**, and A1 is invalid (zero). tapefs §4.2 step 1 needs a selectable Side A
  for any mount. §5.5 makes `cartridge_sequence` the maximum over every
  structurally valid slot, so the oracle's expected commit at sequence 4 holds
  only if no A slot is at sequence 3 or above.
- **Side B:** live B0 has sequence 3 and exactly `[(2, 0, 12)]`; B1 is invalid.
- Consequently, raw-media derivation gives `free_next == 3` and one, two, or
  three allocatable chunks, and `cartridge_sequence == 3`.

(#126 maintenance.) This text specifies the fixture #99 relied on but did not
state, and that the #107 disposition verified from Product adapter source. No
assertion changes. `raw_before` keeps its four keys. The A-slot premise is
checked from raw bytes by the separate row
`tests/strengthen_r55` `WP09.capacity.fixture_a_slot_premise`.
- Seeded Side-B PCM frames are `(100+i, -200-i)` for `i=0..11`.
- Every input frame is the deterministic per-case sample defined in
  `oracle.input_sample`; the adapter must read the plan/input, not duplicate an
  expected-output model.

Mount Side B, record from the row's start/middle/end position in its named
mode, and retain raw bytes for both 512-byte superblocks and each B slot's
header plus exact entry array before and after the operation.

## Calls and observations

Emit one `wp09-capacity-r52-v1` JSON object per plan row, in plan order.  Field
names and nesting are demonstrated by the checked-in synthetic observations.
All numeric fields are JSON integers.  Symbolic results use the exact public
enum names.

1. Mount and report public info, seek to `at`, and arm the named mode.
2. Feed the `oracle.prefill_requests` sequence.  Each call must fully accept
   with `TAPE_OK`.  After each feed, service until `more_work == false` using
   exactly the row's block budget.
3. Feed `final_requested`.  Report the actual accepted value and result.  The
   target edge is `TAPE_ERR_CARTRIDGE_FULL` with the row's positive
   `final_accepted` and no callback I/O inside `tape_feed`.
4. Before servicing that accepted prefix, call commit once.  Record
   `TAPE_ERR_BUSY` and zero callbacks.
5. Service to `more_work == false`; public status must then report no frames
   owed.  Commit, unmount, create a fresh instance, and remount Side B.
6. Report public info and render the complete remounted timeline.  Store exact
   interleaved little-endian stereo s16 PCM as zlib level 9 plus base64.

Every device callback is appended in occurrence order with a global 1-based
`ordinal`, the causing call label in `step`, `op` (`read`, `write`, or
`flush`), and raw return `rc`.  Reads/writes also carry `lba` and `count`.
Each feed and premature commit reports `events_from_call` explicitly; omitted
is not zero.  Each service call reports its exact budget, result, and
`more_work` value.

The adapter must calculate `fixture_sha256` over canonical compact JSON of
`raw_before` (`sort_keys=True`, separators `(',', ':')`).  It may add fields;
they carry no authority.

## Integration boundary

Permitted integration changes are mechanical include/library paths and a
sparse callback wrapper that records the fields above.  Do not alter the plan,
fixture geometry, requests, budgets, raw bytes, callback classification, or
public results to accommodate an implementation.  A Product run must identify
the exact Product commit, tree, and adapter source SHA-256 when invoking
`replay.py`.
