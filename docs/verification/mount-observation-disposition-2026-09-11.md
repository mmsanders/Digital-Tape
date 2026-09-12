# DRAFT-8 mount observation disposition — 11 September 2026

## Disposition

**The post-reconciliation raw observation set satisfies all 289 independently
authored mount-tranche assertions.** The pre-reconciliation set independently
recomputes to 274 passing and 15 failing cases. This confirms only the executable
boundary in `tests/mount_draft8/COVERAGE.md`; it is not approval of PR #20 as a
whole and does not accept allocator, running-sequence consumption, recording,
warm-start, state-transition, operation, crash-safety, rendered-PCM or hardware
behaviour.

No engine source, PR #20 diff or mixed discussion, private implementer test, or
unlanded implementation artifact was inspected for this disposition.

## Immutable inputs

- Canonical product input: `mmsanders/Digital-Tape` `main` at
  `4c273ce57ce6848762b00b8990b0b29a3dc9f74b`.
- Canonical DRAFT-8 hashes:
  - TapeFS: `3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb`
  - Engine API: `537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1`
  - Acceptance: `7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7`
- Independent mount source: verifier commit
  `4ee116fa040bb5ce040325e0076365abf8b0f8f9`, imported to product main through
  PR #27. The product package and current verifier package compare byte-for-byte;
  the test package's authenticated spec copies match canonical DRAFT-8.
- `pr20-before.jsonl.gz`:
  - Git blob: `5f623d540fd3e4b14c35b07e8583ae2e21e9a872`
  - compressed SHA-256:
    `b0debac21bd426d441bebfa752b0f044a2cfdcfa650cc38610c53f900cbd9784`
  - recorded adapter SHA-256:
    `56bfbe047be207fa5fd6e6afccef2c2bda270436ca721105e7ef5aff7b3c8b04`
  - run packet identifies engine input
    `56c50e226f55b509728811515da7a6d588d15c27`.
- `pr20-after.jsonl.gz`:
  - Git blob: `77068d2c1ad81f0613e096a0d462e6a9d4fe7d95`
  - compressed SHA-256:
    `188f4e564ac025c6d3f543f2d7dd1b0087eb339e64ac9bc1992f7cec5f3ade48`
  - recorded adapter SHA-256:
    `787a70015ed09aca472c1a2548dfdba87e11ee90777be97113e989adea204bf6`
  - run packet identifies engine input
    `740c97e998c7672d9e98916102be84430993521b`.

The raw provenance records contain the adapter hashes but not the engine Git SHA;
the source-commit association above is therefore supplied by the committed run
packet rather than cryptographically encoded in the JSONL itself. This limits the
provenance claim, not the independent recomputation of the recorded observations.

## Independent method and results

Both gzip streams passed integrity checking and decoded as UTF-8 JSONL. For each
stream, Verification:

1. required exactly one provenance record plus 289 case records;
2. regenerated all cases from the independently authored `cases.py` using seed
   `0xD8A607`;
3. required exact case order and uniqueness, fixture SHA-256, and allowed-result
   tuple for every record;
4. parsed each raw adapter `stdout` observation and reran the independent
   `run.check` oracle;
5. compared every recomputed error list and PASS/FAIL result with the stored result.

No integrity defect, fixture mismatch, case mismatch, allowed-result mismatch,
malformed observation, or stored-versus-recomputed verdict mismatch was found.

| Observation set | Recomputed pass | Recomputed fail | Disposition |
|---|---:|---:|---|
| Before reconciliation | 274 | 15 | Red, failures independently confirmed |
| After reconciliation | 289 | 0 | Green for the mount-tranche assertions only |

The fifteen pre-reconciliation failures are exactly:

- pre-read/addressability: `M-phase0-1`, `M-phase0-2`, `M-phase0-2047`,
  `M-phase0-2048`;
- stale-partner selection/repair: `M-repair-0-stale-rw`,
  `M-repair-0-stale-ro`, `M-repair-0-stale-minor`,
  `M-repair-0-stale-writefail`, `M-repair-0-stale-flushfail`,
  `M-repair-1-stale-rw`, `M-repair-1-stale-ro`,
  `M-repair-1-stale-minor`, `M-repair-1-stale-writefail`,
  `M-repair-1-stale-flushfail`, and `M-newer-water-wins`.

## Reproduced verifier checks

Environment: Python 3.12.14; GCC 13.3.0; strict C99 flags retained.

- `python3 procedures/audit_mount_observations.py /path/to/Digital-Tape`:
  pass; recomputed 274/289 before and 289/289 after with zero integrity defects.
- `make -C tests check`: pass (fault device, crash harness, audio oracle).
- `make -C tests/mount_draft8 check`: 10/10 pass, including fixture
  authentication, 289 synthetic checker transcripts, fourteen rejected mount
  mutations, callback instrumentation, missing-engine failure and deliberately
  wrong-engine negative control.
- `python3 tests/ops_draft8/selftest.py`: pass; two conforming VT8-001 synthetic
  observations accepted and six required mutations caught.
- `python3 tests/ops_draft8/runner.py --adapter
  tests/ops_draft8/_synthetic_adapter.py --log /tmp/vt8-runner-selftest.jsonl`:
  2/2 pass. This is runner plumbing evidence, not a product-engine run.

## VT8-001 return and next owner

The tractable next tranche is already published on verifier `main` at
`a91138667673fcf19dc9e83c9034322b982b1771` under `tests/ops_draft8/`:

- `VT8-001-RB-ALLSLOT` observes all-slot running-sequence consumption through
  `tape_reset_side_b`, final committed media and block-callback traffic.
- `VT8-001-REC-ALLOCSEQ` observes ordinary Side-B allocation at or above the
  independently derived high-water/free pointer and all-slot sequence consumption
  through public recording operations, final media and block-callback traffic.

The package remains verifier-owned test source, not imported product coverage and
not product acceptance. PM/Software may import the exact directory mechanically
before corresponding implementation acceptance, construct the public-API adapter
defined in `tests/ops_draft8/ADAPTER.md`, and return the raw product observations to
Verification. Assertions, fixture values, sequence expectations, operation
arguments, accepted results and exclusions are non-mechanical and must not change.

## Residual holds

PR #20 remains held outside the 289-case mount boundary. Full WP-07, operations/state
freeze, complete WP-10, WP-11 goldens, WP-12a, hardware safety, card atomicity,
fabrication, cell charging, purchases and Michael's reserved approvals remain open.
