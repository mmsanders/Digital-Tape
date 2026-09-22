# WP-12 — independent DRAFT-8 re-spool tranche

Verifier-owned package authored from frozen TapeFS §9.4, §8, §4.5 and Engine
API §9 without inspection of product implementation. It is a **pre-product
semantic tranche**, not package/product acceptance.

## Cases

| ID | Script / purpose |
|---|---|
| `WP12-EMPTY` | empty Side B, with a crafted structural `sequence=0xFFFFFFFF`: promote → `INVALID_ARG`; respool → `TAPE_OK`; both terminal and zero-write |
| `WP12-TWOPASS` | corrected V3-003: H=10, live B `[10,12)`; pass 1 `[12,14)` commits B1/701, then pass 2 `[10,12)` commits B0/702 |
| `WP12-DECLINE` | only initial pass-1 destination is chunk 10 at H; once pass 1 lands there, no strictly-lower qualifying start exists, so pass 2 declines |
| `WP12-FULL` | no pass-1 destination → `TAPE_ERR_CARTRIDGE_FULL`, unchanged media |
| `WP12-DEGRADED` | equal-sequence divergent B slots; mount **Side A** into degraded-B, then respool → `TAPE_ERR_NO_VALID_INDEX` |
| `WP12-SEQ-EXHAUSTED` | non-empty side at sequence cap → preflight refusal, zero writes |
| `WP12-ONE-COMMIT` | exactly one sequence remains: pass 1 commits at `0xFFFFFFFD`; optional pass 2 is skipped |
| `WP12-STAGE-CLEAR` | mountable §9.3.3 row-1 stage state; re-spool clears stage partner-first before its first copy/index write |

## V3-003 safety model

The two-pass case is modeled as two real §8 commits, not as two copies followed
by one final index update.

1. Initial live B is `[10,12)`.
2. Pass 1 copies the complete two-chunk timeline to `[12,14)`, flushes it,
   writes B1 entries, flushes, writes the B1 header at sequence 701, and flushes.
3. Only after that B1 header commit is the old `[10,12)` range no longer live.
4. Pass 2 may then copy back to `[10,12)` and commit the **inactive B0** slot
   at sequence 702.

The verifier updates its live-set oracle at each header commit and rejects any
chunk write intersecting either live side at that moment. This directly checks
WP-12 / invariant 10 instead of inferring safety from the final layout.

For the two full-chunk V3-003 copy, the trace must cover the full 2048-block
destination for each pass; a one-block placeholder copy does not count.

## Budget scope

All semantic cases call `tape_respool` once with
`block_budget = 65535` and require `more_work == false`. This budget is
intentionally generous enough for the deterministic fixture and avoids
pretending that a tiny budget can complete the work.

Repeated small-budget continuation, BUSY behavior, argument stability,
re-entry, and FAULTED handling belong to **WP-12a**, not this semantic tranche.

## Self-test

```sh
python3 tests/respool_draft8/selftest.py
```

The self-test includes mutations for:

- pass 2 writing before pass 1 commits;
- copying only one block of the two-chunk V3-003 timeline;
- wrong B-slot alternation;
- unrelated chunk corruption above H;
- redundant superblock writes;
- false completion with the old budget-64 script;
- an illegal second pass in the decline and one-sequence-left cases;
- unreachable degraded-B Side-B mounting;
- refusal writes;
- stage-clear ordering; and
- terminal unmount failure.

See `COVERAGE.md` for the assertion boundary and `ADAPTER.md` for the
mechanical product-observation contract.

Still required before WP-12 acceptance: real product observations and
bit-exact rendered-audio preservation. WP-10 crash closure and WP-12a
continuation/state behavior remain their own work packages.
