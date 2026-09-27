# R29-A promote product binding

Software-owned mechanical binding for the imported, finally corrected R29-A
promote verifier package `tests/promote_draft8`: tree
`197d2f2adbc9dba40d78bc1a1cd37c162858784b`, Verification publication
`9a036f1dd5645acdf7c52866bd10c78e14cc2d49` (#84), 44,307 cases, planner digest
`71be1754…80aa`. It supersedes the P1-R25 binding of the 16-row classification
package (tree `2b79e0b0`) and the obsolete PR #257 candidate (tree `2eb707d7`),
whose evidence stays in history.

Nothing here edits the verifier tree or decides a verdict. `adapter.py` builds
setup media from the verifier's own `fixture.py` and `oracle` seed helpers.
`r29a_promote_worker.c` drives the real engine on an in-memory device that keeps
separate working and durable images. It reports raw facts: public results,
chronological device callback traces, raw bytes and numeric counters. The
verifier's `oracle.validate_case` decides every case.

## Run

    make -C engine clean all
    make -C tests/promote_adapter clean all
    python3 tests/promote_adapter/run_product.py --evidence <dir>        # canonical
    python3 tests/promote_adapter/diagnostic_sweep.py --out <dir>        # all failures
    python3 tests/promote_adapter/b6_setup_audit.py --out <dir>          # B6 raw setup

`run_product.py` checks four things against git history before any case runs:

- the declared base `867fd4ab…`;
- the import `8886aa39…`;
- the verifier tree;
- that the import's parent is the base.

It then runs the verifier's `runner.py`, which stops at the first failing case
and retains `failure-reproducer.json`.

`diagnostic_sweep.py` is **not** the canonical run. It sends every canonical
case to the same adapter and validates each one with the same oracle. Instead
of stopping at the first failure, it records every failure, so one round shows
the whole picture.

## Binding choices for Verification to audit

These decide how a case reaches the state the package describes. None of them
changes a case, a tolerance or the order of cases.

**B1 — Closure seeds keep their degraded superblock pair.**

- Every two-interruption seed has an invalid or stale partner.
- On a writable mount, tapefs §4.1 phase 4 would repair that partner before
  promote runs, and the verifier's expected post-image contains no repair.
- The device therefore refuses the write issued inside `tape_mount` with
  rc 5. Nothing lands, and the mount succeeds with `needs_repair`. This is the
  flaky-partner case that §4.6 V7-001 names.
- The refused write is emitted in `setup_events`.

**B2 — Step-4 closure is reached in flight.**

- Step 9 and the step-5 decline have a §9.3.3 RESUME entry. They mount the
  verifier seed directly, so the next write is the targeted partner write.
- Step 4 is a FRESH-path update and has no resume entry. Re-running from the
  seed would re-commit A at a new sequence first, as §9.3.1 step 2 requires.
- So step 4 starts from `scenario_initial("fresh_alloc_full")` carrying the
  seed's superblock pair. The engine's own phase-1 copy and steps 2–3 then
  reach the seed.
- `pre_snapshot` is the durable image captured immediately before the targeted
  partner write. The oracle requires it to equal the verifier seed byte for
  byte. `run_start_snapshot` records where the run began.

**B3 — What the operation snapshot counts.**

- `progress_blocks` is the last `blocks_done` delivered to the progress callback.
- `own_device_event_count` and `chunk_write_lbas` count device callbacks issued
  during `tape_promote` calls. A permitted `tape_service` probe reads the card
  for playback; those reads belong to service, not to the operation.

**B4 — Faulted-row render.**

- The separate Playing fixture is a stage-1 row-1 cartridge built with the
  verifier encoders. Its live run is 20,000 frames, longer than the
  16,384-frame ring.
- The cartridge is played on Side B and the ring is filled. The fault is the
  own-device failure of `tape_arm`'s §8 stage-clearing write.
- `ring_frames` counts the frames `tape_render` can still emit. §6.3
  interpolates frame i with frame i+1, so the last frame of a window that stops
  short of the timeline end cannot be emitted yet.
- `ring_window_frames_after` is also reported.

**B5 — Counter domains.**

- The index-only span runs from the entry-block call to the header call (§8).
- The superblock-only span runs from the partner call to the candidate call
  (§4.6).
- Both spans are chosen by the raw write kinds in the trace. Every call's
  counters are emitted in `calls`.

**B6 — Crafted setup media, with raw proof.**

- Media for the branch-exact counters, entry refusals and zero-needed cases
  come from verifier fixtures or seeds.
- Only sequences, generations and CRCs are rewritten. Sequences keep their
  relative order.
- For every crafted-counter case (`headroom_exact`, `headroom_short`,
  `headroom_special`, `zero_needed_reserved`) the observation carries
  `setup_evidence`:
  - `base_source`, naming the verifier fixture or seed the medium came from;
  - `declared_rewrite`;
  - `base_image`, every non-zero block of that verifier medium;
  - `setup_image`, every non-zero block the worker actually put on the device
    before mount.
- `b6_setup_audit.py` recomputes each base from `tests/promote_draft8` and
  diffs it against the setup image byte by byte. Only an index header's
  sequence (8–11) or CRC (60–63), or a superblock's `sb_generation` (12–15) or
  CRC (508–511), may differ.
- The audit also requires: every structural slot and superblock stays
  structural; the relative sequence order is unchanged; and both the declared
  rewrite and the engine-reported `counter_values` match the image.
- Six red controls must each be rejected: entry-block drift, audio-byte drift,
  swapped order, an unauthorised header field, a forged base, and an
  undeclared rewrite.

## Findings from PR #257, corrected by Verification #84

- **F1:** the unreachable allocating-decline branch was removed from the package
  (four cases).
- **F2:** `exact_tail_capacity` now uses a dedicated four-chunk seed. The
  adapter mounts that seed as medium `seed_exact_tail`.
- **F3:** the `shared_sequence` membership now reads A=10/8.

Verification found B1–B5 PASS. B6 is answered by the raw setup evidence above.

## Boundary

Promote remains barred from consumer and release use. A Software green is
evidence, not acceptance.
