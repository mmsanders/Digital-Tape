# R29-A promote crash/resume + promote long-operation coverage

## Frozen authority

- Digital-Tape main: `45c08bd7e25aeb6ca858faf4d30d139999f8dbd7`
- Verification input: `fe432ffac622b9d9e9c68e566d2cb9881f2aee62`
- TapeFS DRAFT-8 SHA-256: `3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb`
- Engine API DRAFT-8 SHA-256: `537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1`
- Acceptance DRAFT-8 SHA-256: `7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7`

## Promote WP-10 crash criteria

| ID | Verifier-owned assertion |
|---|---|
| R29-A-CRASH-01 | Full FRESH allocating path targets every required audio/index/superblock one-block write and following flush |
| R29-A-CRASH-02 | Full adopt-in-place path skips phase-1 data copy and step 3 |
| R29-A-CRASH-03 | First-use format→record-B→promote path uses S=0 and step-5 decline |
| R29-A-CRASH-04 | Every target write runs before, all 1…511 torn prefixes, and after-write; every following flush is targeted |
| R29-A-CRASH-05 | Every boundary runs in flush-required and write-through durability modes |
| R29-A-CRASH-06 | Crash remount discards working state and uses durable bytes only |
| R29-A-CRASH-07 | Every permitted stage-1 non-degraded state matches exactly one §9.3.3 row |
| R29-A-CRASH-08 | Deliberately unmatched stage-1 raw media returns INCONSISTENT with no recovery write |
| R29-A-CRASH-09 | S=0 stage-1 states between steps 4 and 6 match row 1 only |
| R29-A-CRASH-10 | All eleven §9.3.4 recovery rows are represented |
| R29-A-CRASH-11 | Mixed pair between steps 3/4 represented |
| R29-A-CRASH-12 | A-low/B-high state between steps 7/8 represented |
| R29-A-CRASH-13 | Both-low / old-high-water state between steps 8/9 represented |
| R29-A-CRASH-14 | No two structurally valid index slots share sequence after any FRESH injection |
| R29-A-CRASH-15 | Referenced Side A/B PCM is independently reconstructed and remains one of the exact permitted generations |
| R29-A-CRASH-16 | Water line and stage values follow step 4 / decline / step 9 exactly |
| R29-A-CRASH-17 | Step 4, step-5 decline and step 9 each have four two-interruption recovery seeds |
| R29-A-CRASH-18 | Second interruption on next partner write/flush cannot select a stale lower generation |
| R29-A-CRASH-19 | Shared sequence commits use global structural max and running values 501…504 |
| R29-A-CRASH-20 | Index-only commits do not advance sb_generation; ordinary superblock updates do not advance sequence |

## Re-run / capacity

| ID | Assertion |
|---|---|
| R29-A-RERUN-01 | Every one of the eleven recovery rows has an explicit repeated-promote case |
| R29-A-RERUN-02 | Rows 7–11 require zero additional chunk copy |
| R29-A-RERUN-03 | Rows 3–6 require exactly one low copy; rows 1–2 require the two normal copies |
| R29-A-RERUN-04 | Exact-tail row-4 recovery completes through adopt-in-place, not CARTRIDGE_FULL |
| R29-A-RERUN-05 | Repeated row-4 crashes preserve the same staging start/free_next and do not consume successive high runs |

## Stored position semantics

Terminal position clearing is exercised for:

1. uninterrupted full path;
2. step-5 decline;
3. resume at step 8;
4. resume at step 9;
5. NOTHING TO DO.

The frozen engine API exposes no position table. Caller-model position values must
remain present on every nonterminal continuation and are cleared by the caller only
after terminal `TAPE_OK / more_work=false`; no engine-side clearing claim is made.

## Promote headroom / counters

The case set includes all eight non-zero promote branches at their exact threshold, fourteen one-short refusals split by sequence/generation requirement, plus:

- FRESH allocating decline at `sequence=0xFFFFFFFB` writing only 0xFFFFFFFC/0xFFFFFFFD phase-1 sequences;
- historical FRESH allocating `sequence=0xFFFFFFFC` hazard refusing before any write;
- RESUME-at-step-5 decline at `sequence=0xFFFFFFFC`, which consumes zero sequences and succeeds if generation headroom exists;
- NOTHING-TO-DO with sequence 0xFFFFFFFE and 0xFFFFFFFF;
- NOTHING-TO-DO with sb_generation 0xFFFFFFFE and 0xFFFFFFFF;
- zero-write entry refusals for empty B, degraded B, and initial FRESH capacity failure.

## Promote WP-12a

The package covers:

- all fifteen promote-in-progress state-matrix columns;
- all eleven BUSY cells with an unchanged raw chunk-write trace followed by a
  continuation that prefix-extends progress without repeating a copied chunk LBA;
- allowed render/service/status-info-tell/matching-promote cells;
- block_budget=0 on initiation and continuation;
- promote's complete allowed mutable continuation-argument surface;
- own-device write/flush failure → terminal IO + FAULTED;
- all fifteen Faulted-row cells: eleven FAULTED refusals plus render, status/info/tell, abort, unmount;
- Faulted service performs zero block operations;
- Faulted abort clears raw frames_owed without media I/O and Faulted overrides armed state;
- render drains raw ring state and then underruns;
- all fifteen callback re-entry columns with only render and status/info/tell matrix cells exempt;
- next ordinary continuation survives callback BUSY and advances the cumulative raw
  trace; adapter-label equality is non-causal;
- repeated same-function block_budget=1 completion through a terminal raw promoted
  snapshot with no repeated chunk-region write.

Phase-0 and ordered phase-2 admission are independently exercised before index
selection: device size, version, state, nominal-length frame cap, stored/derived
chunk equality, fixed fields, mirror LBA, capacity and A waterline. Fixtures use
truthful 9-second/four-chunk and 21-second/eight-chunk geometry.

## Exact planner census

Crash cases:

| Scenario | flush-required | write-through | total |
|---|---:|---:|---:|
| FRESH allocating full path (14 targets) | 7,196 | 7,196 | 14,392 |
| FRESH adopt-in-place full path (11 targets) | 5,654 | 5,654 | 11,308 |
| first-use S=0 decline path (6 targets) | 3,084 | 3,084 | 6,168 |
| two-interruption closure (3 updates × 4 seeds) | 6,168 | 6,168 | 12,336 |
| **Total** | **22,102** | **22,102** | **44,204** |

For each ordinary target and each closure partner target in each durability mode there are exactly 514 coordinates:

- before: 1;
- torn prefixes: 511;
- after: 1;
- following flush: 1.

Across all crash targets:

- before-write/partner cases: 86;
- torn-write/partner cases: 43,946;
- after-write/partner cases: 86;
- flush-fault cases: 86.

Contract/headroom/re-run cases: **107**.

Grand total: **44,311**.

Canonical case-set SHA-256:

`8732af9434437d0411731b3e4909a2ca9a1278778e5d9c8947642cec7b793442`

Contract-family census:

- stage oracle: 5
- rerun rows: 11
- rerun specials: 2
- caller-model stored positions: 5
- exact-headroom success: 8
- one-short headroom: 14
- headroom specials: 3
- zero-needed reserved counters: 4
- shared sequence: 1
- counter domains: 1
- entry refusals: 3
- promote in-progress row: 15
- zero budget: 2
- allowed mutables: 1
- own-device failure: 1
- Faulted row: 15
- callback re-entry: 15
- small-budget completion: 1

## Explicit exclusions

This publication does **not** re-author or accept:

- the bounded record/reset/stage-clear WP-10 package already accepted through Verification #69;
- format/duplicate raw identity crash behavior (R29-B);
- full re-spool crash behavior (R29-C);
- WP-11 listening/goldens;
- product implementation or product evidence;
- hardware media atomicity.

Fixtures may contain already-accepted primitives as setup, but no duplicate acceptance is claimed.
