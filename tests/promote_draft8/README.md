# DRAFT-8 full promote crash/resume + promote long-operation verifier

Independent verifier-first publication for Digital-Tape-Verification issue #70
(P1-R29-VER-A), corrected under issues #76, #78 and #84.

This package is authored from the frozen DRAFT-8 specification bundle and verifier-owned prior patterns. It contains no product implementation code and performs no product disposition.

## Frozen inputs

- Digital-Tape: `45c08bd7e25aeb6ca858faf4d30d139999f8dbd7`
- Verification input: `fe432ffac622b9d9e9c68e566d2cb9881f2aee62`
- `spec/tapefs-v1.md` SHA-256: `3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb`
- `spec/engine-api.md` SHA-256: `537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1`
- `spec/acceptance.md` SHA-256: `7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7`

## Package

- `fixture.py`: byte-exact verifier media and target write plans
- `media.py`: independent superblock/index parser, selection, stage oracle and PCM reconstruction
- `planner.py`: deterministic exhaustive 44,307-case manifest
- `oracle.py`: dual-image durability simulator, recovery/rerun/headroom/WP-12a validators
- `selftest.py`: positive self-tests and deliberately red negative controls
- `runner.py`: later product evidence runner
- `synthetic_adapter.py`: synthetic-only development adapter, explicitly refused by production runner
- `ADAPTER.md`: raw observation contract
- `COVERAGE.md`: frozen criteria, exact census and exclusions

## Why the audio fixture is one block

The promoted timeline has exactly 128 stereo s16 frames, which is exactly 512 bytes.

DRAFT-8 permits the remainder of a partially referenced chunk to be undefined. A compact copy of this fixture therefore has one required data-block write. The package is exhaustive over every write in this valid full transaction, including all 511 nontrivial torn prefixes. It does not sample a longer data copy.

The fragmented allocating seed still exercises real compaction: its first 64 frames come from chunk 1 and its second 64 frames from chunk 2; phase 1 compacts them into chunk 3 and phase 2 compacts them to chunk 0.

Issue #76 corrects the compact media labels to truthful DRAFT-8 geometry: the
four-chunk fixtures use 9 seconds and the eight-chunk fixtures use 21 seconds. The
independent parser now applies phase-0 capacity and ordered phase-2 version/state/
geometry admission before any index selection. Operation labels are retained only
as non-causal adapter metadata; budget-1 continuation uses cumulative raw chunk-
write traces. Stored positions are explicitly caller-owned model state because the
frozen public engine API exposes no device-side position table.

Issue #78 corrects the frozen Promote-in-progress oracle without changing planner
membership: Promote begins from *Mounted, idle*, so ordinary and callback-nested
render retain rate 0 and return `TAPE_OK` with zero frames, empty PCM and no device
I/O. Own-device failure begins in **Promote in progress**. The Faulted ring-drain
cell may use a separate Playing fixture and proves only the frozen Faulted row, not
a Promote-while-Playing path.

Issue #84 removes four impossible FRESH-allocating `S < len` headroom cases.
For a valid live-B index, §5.1 makes its physical-frame intervals disjoint;
because every interval lies below `free_next`, their total frame count is at
most `free_next * CHUNK_FRAMES`. Therefore allocating `S = free_next` always
satisfies `S >= ceil(total_frames / CHUNK_FRAMES) = len`. Reachable decline is
still covered by first-use/adopt-in-place and RESUME at step 5. The correction
also gives the row-4 exact-tail case a four-chunk seed whose only free chunk was
already consumed, and reconciles the shared-sequence fixture membership as
A=10/8, B=500/499 without changing the structural maximum or 501…504 commits.

## Planner

- raw crash injections: **44,204**
- contract/headroom/re-run: **103**
- total: **44,307**
- flush-required: **22,102 crash cases**
- write-through: **22,102 crash cases**
- canonical SHA-256: `71be17545262d3b35fed9213b9305f71e4c8956693fbf4ec8f6d06f9f7ba80aa`

See COVERAGE.md for the phase census.

## Self-test

Run:

    python3 tests/promote_draft8/selftest.py

The repository's verifier-package workflow discovers `tests/*_draft8/selftest.py` automatically.

The self-test authenticates the exact planner census/digest, target write plans,
all three stage-oracle rows plus the S=0 uniqueness and unmatched refusal, all
eleven recovery rows, all promote two-interruption closure seeds, every contract
family, the allocating-branch reachability proof, exact-tail geometry and
shared-sequence membership, with negative controls that make each major oracle
go red.

## Later binding

Read ADAPTER.md first.

The product adapter is a mechanical observer. It must not decide that a stage row is valid, that a BUSY left the operation live, that a copy was unnecessary, that counters had headroom, that positions were cleared at the correct time, or that FAULTED precedence held. It reports concrete bytes/events/states; this package decides.

A successful Software run is retained evidence, not self-acceptance.

## Scope

This is R29-A only. It deliberately excludes R29-B format/duplicate, R29-C re-spool, the already accepted bounded core crash tranche, WP-11, product implementation, and hardware media atomicity.
