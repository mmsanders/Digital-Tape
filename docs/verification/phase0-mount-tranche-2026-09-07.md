# PM return — independent DRAFT-8 mount tranche

Date: 7 September 2026. Responds to `pm/phase0-test-handoff-2026-09-07.md`.

**Disposition: ready for mechanical test integration, within the coverage boundary below.**
No engine implementation was inspected or tested. No WP-06/WP-07 acceptance, PR #20
approval/merge, operations/state freeze, or hardware acceptance is implied.

## Return package

All source, fixtures/generators, runner instructions, the adapter contract, coverage
and raw evidence are under **`tests/mount_draft8/`**:

| Deliverable | Path |
|---|---|
| Runner and reproduction instructions | `tests/mount_draft8/README.md`, `run.py` |
| Independent byte fixtures / pinned generation hashes | `tests/mount_draft8/cases.py`, `fixtures.sha256` |
| Public-API observation probe / build | `tests/mount_draft8/mount_probe.c`, `Makefile` |
| Adapter contract and unobservable rules | `tests/mount_draft8/ADAPTER.md` |
| Coverage / every case ID | `tests/mount_draft8/COVERAGE.md`, `coverage.csv` |
| Ordinary allocation/write predicates | `tests/mount_draft8/ownership.py` |
| Fixture and instrumentation checks | `tests/mount_draft8/test_package.py`, `fixture_audit.py`, `probe_selftest.c` |
| Raw run evidence and provenance | `tests/mount_draft8/evidence/` |
| Authenticated supplied candidate | `tests/mount_draft8/spec/` |

Publish this completed package and status on verification **main**. The immutable
publication commit is supplied with the return message. There is no separate test
branch awaiting verification publication; product test integration remains pending.
The publication commit, rather than this document naming itself, identifies exact bytes.

## Baseline

All three supplied files exactly match the handoff's SHA-256 values:

- TapeFS: `3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb`
- Engine API: `537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1`
- Acceptance: `7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7`

Product main was independently checked at `ed5efd834aa8f7a96bc8ef811569b2687d919526`;
its manifest remains DRAFT-7. This package is intentionally candidate labelled and
does not claim issuance. PM must issue/authenticate the candidate before integration /
acceptance. The existing third-cut paper verdict remains **zero blockers, zero majors,
one documentation question**. V8R3-001 is retained unchanged.

## Evidence: separate claims

| Evidence category | Actual result |
|---|---|
| Authored | 289 deterministic mount-image cases, host C99 probe, independent assertions, ordinary allocation/write predicates, coverage and integration instructions |
| Fixture audit | All 289 assigned fixture verdicts agree with a separate verifier-owned metadata decoder; literal layout/CRC and generation manifest checks pass |
| New harness checks | Ten package self-tests pass, including 14 deliberately corrupted synthetic observations rejected; actual C callback instrumentation checked |
| Negative control | A deliberately wrong stub returns INVALID_ARG for a valid mount. The actual probe/runner records FAIL and exits 1; log retained |
| Missing implementation | No adapter argument exits 2. It never becomes a skip or green acceptance |
| Existing infrastructure | `make -C tests check` passes strict C99; the pre-existing sample crash test retains its asserted 1,029 cases |
| Conforming reference engine | **Not run.** The fixture auditor and synthetic transcripts are not a conforming engine and do not emulate playback/operations |
| Product engine | **Not run.** Actual public header/link paths await software's mechanical integration; no implementation was opened to obtain them |

The initial fixture generator had duplicate test IDs for geometry mutations.
`evidence/01-initial-check.log` preserves that failure. IDs were made unique without
changing expected behaviours. Later successful logs are separate. Fixtures contain
no real media/audio; deterministic seed is **0xD8A607**. Python standard library,
C99 compiler and Make suffice. Full commands and toolchain version are recorded.

## Coverage disposition

Mount tests cover phases 0–4, structural superblock selection before admission,
version/state/geometry refusals, index validity and fallback, frame-interval
non-overlap, both-side validation, both degraded-B causes, stage-oracle admission,
repair/no-repair/failure accounting, mounted info and clamped resume positions.
They test ownership's **mount-visible consequences**, especially deriving free space
from live B while mounting A and allowing references below `a_high_water`.

They do **not** test rendered PCM, allocator decisions or actual allocation/write
destinations, index commit protocol, running sequence consumption, stage clearing,
recording/edit/reset/promote/re-spool, the complete not-mounted/degraded state rows,
or full WP-07's 10,000 random edit sequences. The pure ownership predicates are
ready for future trace integration, not evidence that an allocator passed.
PM/software must compare its implementation surface with `COVERAGE.md` and retain
uncovered portions on the held branch. This is not a finding about PR #20's contents.

## Actionable remaining dependency

FINDING: VT8-001
SEVERITY: integration dependency (not a new specification defect)
AREA: WP-07 allocation decisions and TapeFS §5.5 running cartridge sequence
CLAIM: The public mount/info API cannot independently expose either allocation events or the all-structurally-valid-slot running sequence. These behaviours remain outside this mount tranche's merge/acceptance boundary.
REPRO: Mount a valid Side A while an unused slot is structurally valid at sequence 0xFFFFFFFF but semantically invalid. Selection/info can be correct whether the engine retained that sequence or discarded it. Likewise, correct free_chunks does not establish where a later allocator will write. The public API defines neither a sequence query nor an allocate-only call.
IMPACT: Passing 289 mount cases cannot justify merging or accepting uncovered allocator/commit/operation behaviour. It also cannot satisfy WP-07's random-edit requirement.
FIX: Land this tranche first; then independently author public operation tests and observe actual committed headers / write destinations, with the verifier trace contract in ADAPTER.md. Supply mechanical public-header/link integration for the present probe. Do not invent a product API, inspect implementation to choose expectations, or waive uncovered tests.

## Next independent step and inspected materials

After canonical authentication and test-first landing, run this probe against the
corresponding implementation and return its raw JSONL for independent disposition.
Only covered behaviours may cross the subsequent implementation-review boundary.
Proceed next to independent operation tests needed to observe allocation and sequence;
retain full WP-10, WP-11 and WP-12a follow-on requirements.

Inspected: the supplied PM handoff and DRAFT-8 candidate text; product main's working
agreement, manifest and branch metadata; verifier-owned repository history/current
files and the published third-cut review. **Not inspected:** engine source, product
implementation branches/diffs/issues, implementation-derived tests, or PR #20's
implementation/discussion. No Digital-Tape files were modified, and no review watcher
was restarted. No additional input from Michael is required for this delivery; the
next mechanical integration/issuance actions belong to the acting authority.
