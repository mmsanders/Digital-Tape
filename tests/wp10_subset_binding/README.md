# WP-10 any-subset binding (Product #440)

Software's binding of Verification's any-subset persistence package
(`tests/wp10_subset_r1`, imported byte-identically at `54b3dd7` from Verification main
`fe8f3bdf`, subtree `c6cb573d`) into the **existing** WP-10 workers and the host load
route, following that package's `ADAPTER.md` (P2V183-EXEC-001). It transports actual
callbacks and raw observations. **It produces no verdict**: Verification compares the
projections with `model.py` and judges each operation with its own crash-state predicates.
No engine, port or shipping-binary change; nothing is batched.

## What each part does

| Operation (ADAPTER.md row) | Route | Transport |
|---|---|---|
| commit/record, reset-b, stage-clear closures | `crash_core_adapter` worker | new `S`/`R` commands; `B`/`C` unchanged |
| promote (alloc/adopt, first-use S0, partner/candidate closures, decline/resume seeds) | `promote_adapter` worker | new `S`/`R`; `M` reuses `subset:` names; old commands unchanged |
| respool (v3_003 pass 1/2, no-lower-run decline) | `respool_full_adapter` library | new `rf_subset`, `rf_subset_remount`; `rf_open`/`rf_case` unchanged |
| dup and format onto every raw shape | `format_dup_identity_adapter` worker | new `S`/`R`; old commands unchanged |
| load | `tapectl load` via the `tapectl-test` seam (ADR-164) | unchanged binary; seam trace with payloads |

**S (subset run).** It starts from the scenario's own fixture or from a recovered image,
and runs the scenario's normal setup and operation on a working image. Every write unit
(512 bytes) is logged with its absolute ID, call ID, LBA, bytes and acknowledgement. A
multi-block call logs one unit per block and keeps its call number. Every barrier result
is logged too. It can do any one of these:
- cut before operation unit k, including inside a call;
- cut at the entry of operation barrier j;
- fail operation write call j: the call is attempted, eligible to persist, and visible
  nowhere;
- fail operation barrier j.

After a cut every callback fails and nothing more is logged. A setup fault of the old
suite stays an actual failed write: the core closure repair fault, and the promote
closure's refused mount writes.

**R (remount).** A fresh engine instance and rings mount a device whose bytes are exactly
the projection. It emits that worker's existing raw facts: snapshots, mount results,
public info, and, where the worker renders, PCM hashes. Every mount starts from the
projection itself (Verification #186 V186-01, audited per binding):
- core, format/dup and respool mount one side, once;
- promote renders side A and side B, each from its own `img_copy` of the projection;
- the load route runs `verify`, `dump --side A` and `dump --side B` as three processes,
  each on its own fresh copy. Each command's image hash before and after, its seam trace and
  its output are kept, and a command that changed its image is listed in `mutated_by`. A
  repair by one command is never another command's starting state.

**Driver** (`subset_driver.py`):
- It replays each actual history into `model.Device`, one call at a time (model imported
  unchanged).
- It takes `model.exhaustive` for epochs of up to 8 events, and `model.sampled` with
  seeds 1, 183 and 3647685189 (67 records per seed) otherwise.
- `Device.crash_image` decides every projection, and every distinct image is remounted.
- Coordinates per scenario: the complete operation, every unit boundary, every barrier
  entry, every error write and error barrier, and a second cut. For the second cut, the
  first N distinct first-cut images are each re-run from their bytes only, and cut at
  every unit boundary again.
- `--shard I/N` partitions the fixed task list exactly; `--jobs` runs worker processes in
  parallel.

**Not reachable on the load route** (recorded per coordinate, never faked):
- Write errors: the seam has no write-error fault.
- Barrier errors other than the first: `native-flush-error` fails every barrier.

A load cut is a projection of the complete run's actual trace up to the coordinate, not an
interrupted host execution. The route is deterministic, and every real cut run of the
other bindings was checked to be such a prefix; that supports, but does not prove, the host
route under every cut. The 404 unreachable load coordinates are missing coverage, not
executed error coverage.

## Evidence (per shard part)

| File | Contents |
|---|---|
| `runs.jsonl` | one row per run: coordinate, worker result, trace reference, initial-image hash, epoch, plan and projections |
| `remounts.jsonl` | one raw R observation per distinct (image, remount kind) |
| `snapshots.jsonl` | the metadata part of each snapshot, once, by SHA-256 of its canonical JSON |
| `traces/` | actual traces, gzip. A cut trace equal to the complete trace up to record k (checked record by record) is cited as that prefix |
| `initial/` | every distinct initial image, gzip |
| `summary-*.json` | counts, scenario sizes, model and worker hashes |
| `SHA256SUMS` (bundle root) | SHA-256 of every OTHER file in the bundle; it is written outside the tree and moved in last, so it never lists itself, and `sha256sum -c` runs on it in CI |

An epoch of 256 events or fewer keeps every event, mask and landing order inline. A longer
epoch keeps its event-list hash and first and last IDs. Each of its sampled projections
keeps seed, draw, selected count, and the SHA-256 of its actual mask and landing order.
Both are regenerated by `model.sampled` from the retained events.

## Self-proofs (`selftest_core.py`, core worker)

(a,B); reverse-order repeated-LBA persistence; fresh second remount; all/none equal to
the old `write_through`/`flush_required` images at every old ordinal (5185 coordinates);
successful barriers end epochs and failed ones do not; a dropped-barrier/early-identity
control (the index persists before its chunk) that turns the existing
`crash_core_draft8` chunk predicate red while the honest replay never does. A dropped
barrier inside one index slot is reported as an observation only: the existing
fingerprint keeps every mixed slot at old or new. The separate torn suites are untouched.

## Scale

The two long chunk-copy epochs dominate everything else:
- the core stage-clear respool: about 1028 units with no barrier, ×5 seeds;
- the respool_full v3 passes: 4100 units each.

At every unit boundary with 201 sampled projections, these two would cost about 175
CPU-hours and about 10 GB of evidence. Verification #186 did not authorize that; it issued
a bounded plan instead, run with `--unit-plan v186` (`subset_driver.boundary_plan`):
- unit boundaries 0..8 and U-8..U; 2^k-1, 2^k, 2^k+1 for every power of two <= U;
  1024j-1, 1024j, 1024j+1; each metadata/identity/index call's first and end boundary and
  their neighbours (a unit outside the public chunk area: LBA < TAPE_LBA_CHUNK_BASE, or the
  mirror superblock); and every barrier entry's boundary and its neighbours;
- every barrier entry and barrier error, the complete operation, and error writes at every
  call next to a selected boundary plus every metadata/identity/index call;
- two DISTINCT first-cut bases per scenario: the first distinct image, and the first
  later-only projection (a later event persisted while an earlier one did not), else the
  next distinct image. Each second run starts from that base's bytes only, and the same
  plan is applied to its own actual trace. Fewer than two distinct bases is a recorded
  row with every enumerated image identity, never a duplicate;
- exhaustive plans for epochs <= 8, otherwise all 201 sampled plans.

These are SAMPLED unit coordinates of a long copy, not every boundary and not full WP-10
acceptance. `summary-*.json` records each scenario's plan (selected coordinates, error
calls, barriers) separately from its persistence plans. `wp10-subset.yml` runs everything
else on each pull request and these two on dispatch, sharded.
