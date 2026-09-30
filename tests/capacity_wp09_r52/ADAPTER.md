# WP-09 R52 mechanical adapter contract

The Product adapter is observation plumbing, not an oracle.  It may call only
the frozen public engine API and instrument the supplied `tape_dev` callbacks.
It must not expose private allocator state, inspect Product internals, filter
callbacks, synthesize expected media, or supply a verdict consumed by the
oracle.

## Case setup

For the selected row in `evidence/plan.json`, construct the raw stage-0 fixture
described below, byte-for-byte, with an independently chosen cartridge UUID:

- Side A high-water is 2.
- Live B0 has sequence 3 and exactly `[(2, 0, 12)]`; B1 is invalid.
- The primary and mirror superblocks agree and `total_chunks` is the row value.
- Consequently, raw-media derivation gives `free_next == 3` and one, two, or
  three allocatable chunks.
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
