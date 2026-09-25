# Full re-spool product-binding contract

This package is verifier-owned and implementation-independent. Software may import
this directory byte-for-byte and bind the frozen public API to it, but may not change
the planner, fixture bytes/digests, durability model, state oracle, permitted layouts,
negative controls, or coverage declarations.

The verifier was authored against Digital-Tape
`45c08bd7e25aeb6ca858faf4d30d139999f8dbd7` and Verification
`fe432ffac622b9d9e9c68e566d2cb9881f2aee62`, before product implementation
inspection.

## Product adapter boundary

The later Software binding exposes **raw observations only**. It must not emit
"old/new", "valid", "safe", "passes", overlap verdicts, an expected `free_next`,
or any other result that duplicates verifier logic.

For each planner case it returns one `WP10-RESPOOL-OBSERVATION-2` object containing:

- the exact planner case identity and confirmation that the planned injection fired;
- `fresh_remount_from_durable_only=true`;
- the raw remount return code and `remount_side = "B"`;
- the immediate post-remount raw `tape_info` fields:
  `uuid`, `total_chunks`, `free_chunks`, `entry_count`,
  `total_frames`, and `side_b_valid`;
- a pre- and post-crash compact metadata snapshot: exact primary/mirror 512-byte
  superblocks plus the first two blocks of all four index slots;
- the exact targeted device event (write LBA/count or flush);
- for every write-target case, exact 512-byte `target_block` observations:
  `before_hex`, the write callback's `intended_hex`, and the durable
  post-crash `durable_hex`;
- SHA-256 observations of verifier-designated raw audio regions and the Side-A
  control region.

### Public allocator observation

Frozen DRAFT-8 `tape_info` does **not** contain a `free_next` member. It exposes
`total_chunks` and `free_chunks`. Do not invent a private/public
`tape_info.free_next` field to satisfy the acceptance prose.

Verification independently derives:

```
reported_free_next = tape_info.total_chunks - tape_info.free_chunks
expected_free_next = max(a_high_water, max(live-B last + 1))
```

from the fresh remount and the raw selected B index, then requires equality after
**every injection**. The UUID, B validity, entry count and total frames bind that
`tape_info` observation to the same fresh remount whose raw metadata was supplied.

A failing observation is retained with `reproducer.retain_failure` as
`WP10-RESPOOL-FAILURE-1`, including the exact planner case/injection coordinate,
pre/post metadata snapshots, target event, target block bytes for write cases,
post-remount `tape_info`, and raw-region hashes.

## Dual-image crash device

The product binding uses separate working and durable images.

- Reads come from working bytes.
- In `write_through`, a successful write changes working and durable bytes.
- In `flush_required`, a successful write changes working only.
- A successful flush makes all preceding working writes durable.
- A torn **one-block write of any kind, including copied audio**, copies exactly the
  requested prefix (1…511 bytes) of the intended 512-byte payload into both working
  **and durable** bytes, leaves the suffix equal to the pre-write durable block, and
  then faults.
- `before_write` lands no target byte.
- `after_write` permits the full write to return, then cuts power before the
  following flush. Therefore the full block is durable only in `write_through`.
- `at_flush` fails/cuts before that flush changes durability. Preceding writes may
  already be durable in `write_through`.
- After every injected interruption, destroy the running instance and working image.
  Remount a fresh instance initialized only from durable bytes.

For a targeted write the adapter supplies raw block bytes; Verification, not Software,
computes the permitted durable result. For V3-003 copied blocks the intended 512-byte
payload is independently known from the verifier fixture. For the no-lower-run
fixture only the first 40 logical payload bytes of its partial block are normative;
the remaining write-buffer tail is observed raw and then used by the exact fault
model, never interpreted as logical audio.

## Verifier-owned raw destination preimages

The imported fixture contract initializes the targeted unallocated destinations
deterministically so torn-prefix behavior is independently checkable:

- V3-003 pass-1 [12,14): verifier pattern tag 90;
- V3-003 pass-2 [10,12): the old timeline bytes remain in place, verifier pattern
  tag 10;
- no-lower-run pass-1 chunk 10: verifier pattern tag 91.

An adapter whose `before_hex` differs from those verifier-owned bytes is rejected
before durability is considered.

## Crash targets

The canonical planner contains **4,209,696 cases** and has no runtime sampling
switches.

Every copied 512-byte audio block and every targeted 512-byte metadata block receives:

- before-write / landed 0;
- torn-write / every landed prefix **1…511**;
- after-write / landed 512;

in **both** durability modes. The data flush, entry-array flush and header flush are
also faulted in both modes. Torn lengths may not be sampled or collapsed.

The corrected V3-003 fixture is fixed at H=10, live B=[10,12), len=2,
free_next=12:

1. pass 1 copies to [12,14) and commits B1 sequence 701;
2. pass 2 copies back to [10,12) and commits B0 sequence 702.

The pass-2 campaign begins from the committed pass-1 durable image. Every pass-2
observation exposes the raw SHA-256 of [12,14), allowing Verification to prove that
no pass-2 interruption destroys the only live pass-1 copy while reclaimed [10,12)
is being written.

The no-lower-run fixture keeps the existing verifier-owned ten-fragment source and
compacts to chunk 10 once; pass 2 must decline.

## Clean functional and headroom observations

Software must also expose the ordinary call/event traces already understood by the
pinned `respool_draft8/oracle.py` for these verifier fixtures:

- empty Side B;
- corrected two-pass V3-003;
- no-lower-run decline;
- no valid pass-1 destination / CARTRIDGE_FULL;
- sequence-exhausted one-commit branch;
- one-sequence-remaining branch, where pass 1 succeeds and optional pass 2 is skipped.

The stage-clear transaction is not rebound here; Verification #69 already closed it.

Two extra empty fixtures carry (a) cartridge_sequence 0xFFFFFFFD and (b) deliberately
crafted sequence=sb_generation=0xFFFFFFFF. Re-spool must return TAPE_OK,
more_work=false and perform zero write/flush operations. A zero-needed counter is not
consulted.

## WP-12a raw state observations

For each of the 15 matrix columns, use a fresh equivalent fixture so calls such as
unmount do not affect later cells. Emit result code, the complete chronological
block trace, and the cumulative chronological list of chunk-region write LBAs
before and after the call. An adapter label may also be retained, but it is not
engine-sourced operation identity and Verification gives it no causal weight.

The binding additionally emits:

- repeated **block_budget=1** respool calls through terminal more_work=false,
  retaining the cumulative chunk-write list before and after every call;
- budget-zero initiation and continuation observations, including before/after state;
- an interfering BUSY call followed by an ordinary continuation;
- separate continuation write-failure and flush-failure observations;
- a Faulted-over-armed fixture with frames owed;
- render counts while the Faulted ring drains, underrun indication, and abort result.

### Frozen API non-applicabilities

Do not invent adapter hooks to satisfy prose that the public API cannot express.

`tape_respool(t, block_budget, more_work)` has no operation-specific continuation
argument other than `block_budget` and `more_work`, both explicitly allowed to
change. Therefore the changed-stable-argument continuation test has no respool input
to mutate.

Re-spool also has no `tape_progress_fn` parameter. The no-re-entry rule is triggered
while an engine callback is executing, and DRAFT-8 states that the current callback
surface is `tape_progress_fn`; only promote and duplicate expose it. Therefore there
is no respool-originated progress callback in which to re-enter respool. The adapter
must report these surfaces as absent, not create a private callback or private
argument.

### Continuation/no-restart evidence

The verifier derives only externally observable continuity. A BUSY call must leave
the complete operation trace unchanged; each ordinary continuation must preserve
the prior trace as an exact prefix, advance raw progress, and never repeat an
already-written chunk-region LBA. The terminal call must produce the exact raw media
required by the fixture. Constant adapter labels do not prove continuity. If a path
has no observable chunk-region write with which to distinguish restart, private
engine identity remains unobserved and no broader no-restart claim is made.

## Forbidden binding behavior

Software must not:

- inspect or modify verifier expectations based on product behavior;
- collapse durable bytes or allocator values into an adapter verdict;
- skip planner cases, copied-block coordinates, or torn lengths;
- reuse the live engine instance after simulated power loss;
- add a non-frozen `free_next` API instead of observing frozen `free_chunks`;
- substitute the previously accepted narrow 8/8 clean re-spool evidence for this
  crash/state campaign;
- include promote, format/duplicate, or §8 stage-clear acceptance in this tranche.
