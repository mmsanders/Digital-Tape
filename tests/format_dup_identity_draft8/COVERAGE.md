# R29 format/duplicate raw-identity + duplicate WP-12a coverage

## Frozen authority

- Digital-Tape: 45c08bd7e25aeb6ca858faf4d30d139999f8dbd7
- Verification input: fe432ffac622b9d9e9c68e566d2cb9881f2aee62
- TapeFS DRAFT-8 SHA-256: 3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb
- Engine API DRAFT-8 SHA-256: 537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1
- Acceptance DRAFT-8 SHA-256: 7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7

## Raw format/duplicate identity coverage

| ID | Verifier assertion |
|---|---|
| R29-B-RAW-01 | Geometry/capacity refusal for equal-divergent destination precedes destination SB reads/writes |
| R29-B-RAW-02 | Ordinary step 1 is a v1 WRITE_IN_PROGRESS template |
| R29-B-RAW-03 | Ordinary step-1 order is partner first, candidate/other last |
| R29-B-RAW-04 | Healthy pair tie: mirror partner, primary candidate |
| R29-B-RAW-05 | Equal-generation-divergent tie uses mirror then primary |
| R29-B-RAW-06 | Torn first partner preserves a selectable unwritten copy where specified |
| R29-B-RAW-07 | Mandatory shapes: healthy, mirror-only, generation-0, v2-only, equal-divergent |
| R29-B-RAW-08 | Exhaustion candidate and exhaustion x equal-divergent shapes |
| R29-B-RAW-09 | Ordinary reusable generation-1 media writes step-1 generation 2 |
| R29-B-RAW-10 | Once a template is durable, previous candidate UUID cannot be selected |
| R29-B-RAW-11 | No-headroom fallback writes zero to non-selectable copy first |
| R29-B-RAW-12 | Equal-divergent exhaustion zeroes mirror first |
| R29-B-RAW-13 | First durable/torn zero can select surviving primary; both gone gives BAD_MAGIC |
| R29-B-RAW-14 | Equal-divergent with headroom exact split: INCONSISTENT / surviving-copy / INCOMPLETE / completed-new |
| R29-B-RAW-15 | Equal-divergent without headroom exact split: INCONSISTENT / surviving-primary / BAD_MAGIC / completed-new |
| R29-B-RAW-16 | Identity assignment ends at SB generation 1, A0 sequence 1, B0 sequence 2 |
| R29-B-RAW-17 | Final identity order is mirror, flush, primary, flush |
| R29-B-RAW-18 | Both durability modes and every 1..511 torn prefix at every target one-block write |
| R29-B-RAW-19 | Fresh remount is from durable bytes only; raw parser owns selection/UUID/state judgment |
| R29-B-RAW-20 | Failure reproducer retains exact raw pre/post primary+mirror and selected result |

## Duplicate WP-12a coverage

| ID | Verifier assertion |
|---|---|
| R29-B-LONG-01 | block_budget=1 completes by repeated calls to tape_dup with a cumulative raw chunk-write trace |
| R29-B-LONG-02 | Complete 15-column duplicate-in-progress row |
| R29-B-LONG-03 | All 11 BUSY cells leave raw progress/event/chunk-write state unchanged; continuation prefix-extends it without repeated copied LBAs |
| R29-B-LONG-04 | block_budget=0 is INVALID_ARG on initiating and continuation calls, no state/work change |
| R29-B-LONG-05 | Fixed continuation args: destination ctx, UUID, epoch, nominal length |
| R29-B-LONG-06 | Only budget/more_work/callback/user may vary |
| R29-B-LONG-07 | Callback re-entry: read-only/render exemptions; every other tested same-instance call BUSY |
| R29-B-LONG-08 | Re-entrant BUSY leaves the raw trace unchanged; next ordinary continuation advances it |
| R29-B-LONG-09 | Destination write failure from Playing does not FAULT source or alter rate/position/ring and audio continues |
| R29-B-LONG-10 | Already-FAULTED source returns FAULTED from duplicate with zero block operations |
| R29-B-LONG-11 | Product adapter emits only raw/public facts; Verification derives all continuity/state/audio verdicts and rejects derived verdict fields |
| R29-B-LONG-12 | Negative controls mutate raw rate/ring/progress/callback-depth facts and make a constant-label continuation repeat a copied LBA |

The complete project-wide 45-cell WP-12a matrix is the three 15-column in-progress rows. This tranche fully exercises duplicate's own 15-column row; promote and re-spool rows are deliberately not duplicated here.

## Raw-observation independence boundary

The WP-12a product binding may expose non-causal adapter labels, exact progress/
event counters, exact arguments, transport/rate/position/ring facts, callback entry/
depth counts, raw call sequences, cumulative chunk-write traces, render bytes, and
terminal raw media. Label equality never proves engine continuity.

It may not expose precomputed conclusions such as operation-survived, work-advanced, restart-count, unchanged-rate/ring, audio-continues, source-faulted, recursed, or final-identity judgments. The verifier rejects those semantic fields and computes each disposition from the raw facts.

## Exact planner census

There are fourteen raw crash scenarios: 2 operations x 7 destination shapes.

Each scenario contains 2 durability modes x (4 writes x 513 landed-byte outcomes + 4 flush faults) = 4,112 cases.

Raw crash cases: 57,568.

Contract/refusal cases: 43.

Grand total: 57,611.

Canonical case-set SHA-256:

c493e77dff948df48d9c67c51ef4b68f0a61d2e02615b2d08760a594e79dc4e3

The PM-return raw-schema correction does not alter planner membership, ordering, census, or digest.

Phase-0 and ordered phase-2 admission are exercised before index selection using
truthful 9-second/four-chunk geometry, including the frame cap, stored/derived chunk
equality, fixed layout, mirror LBA, capacity, A waterline, and version/state
precedence.

## Explicit exclusions

This publication does not re-author or accept:

- bounded WP-10 record/reset/stage-clear already accepted via Verification #69;
- promote crash/resume;
- full re-spool crash enumeration;
- the existing narrow format/duplicate refusal package except refusal setups necessary to prove raw equal-divergent precedence;
- promote/re-spool WP-12a in-progress rows;
- product implementation or product evidence;
- hardware media-atomicity validation;
- unrelated WP-07/WP-09/WP-11/WP-13 criteria.
