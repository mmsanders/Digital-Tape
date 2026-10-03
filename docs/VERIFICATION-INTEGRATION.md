# Independent verification integration

This file states the **current** integration boundary and what is independently
accepted. It is a state table, not a chronicle. Earlier boundaries are preserved verbatim:
P1-R1 through P1-R24 in [the verification integration history](archive/verification-integration-history.md),
and the 25 September boundary in [its own archive](archive/verification-integration-2026-09-25.md)
(original SHA-256 `7f19b8a8d2fcfadf9461f1b8c33748a257baedf2b7509eb40b585acd86649373`).

## Current boundary — Phase 1 close-out, 3 October 2026

Every imported verifier package is declared in [tests/IMPORTS.json](../tests/IMPORTS.json)
(37 packages at main `320d729`). The last integrated publication is verifier `cdf89f5`
(WP-11 goldens, portability and ledgers), merged into product main through #369 at
`d93ca4e`. Every Phase 1 package is independently accepted for laptop scope; see the table.
Phase 1 acceptance makes no hardware, media, wake-latency, 85 dB-cap, copy-time or release claim.

## Integration rules that do not change

- Verifier package trees declared in `tests/IMPORTS.json` are imported **verbatim with modes
  preserved** and are Verification-owned. No assertion, fixture, expected sequence, operation
  argument, ordering, range, tolerance or exclusion is ever changed on import. Route a
  disagreement to Verification/PM.
- The nested `spec/` inside a package tree is an **authenticated test baseline**, not a
  second canonical publication point. Product authority is `spec/`; those copies are
  held in place by tamper controls (`VT8-A13`, `PB8-A01`) and must not be deduplicated.
- Product adapters (`tests/*_adapter/`) are Software-owned and live **outside** the verifier trees.
- Structural Rule 1 ordering is checked by CI for every IMPORTS-declared package (ADR-159);
  see [CLAUDE.md §3](../CLAUDE.md).
- A green run is not acceptance. Authorship, harness checks, engine execution,
  independent disposition, merge and package acceptance are separate facts.

## Coverage

| Package | Independent disposition | Integrated | Outstanding |
|---|---|---|---|
| WP-06 block device, superblock, index commit | Verification #138 DRAFT-10 ledger: 40 rows accepted (289/289 mount, 8/8 writability, 34/34 NOT_MOUNTED, #297 sequential 38/38, #326 closure 7/7) | `8dfe543`, `230e47e` | None; 2 WP-06e rows unreachable by spec (V10-002) |
| WP-07 chunk allocator, COW Side B | Verification PR #67: frozen 10,000-sequence allocator/COW package | Product PR #215 | None |
| WP-08 playback, seek, scrub | Verification #95 (#287), #122 (#327), #143 ledger; L01/L14 closed by goldens + Michael #367 | `abd8481`, `523a7fd`, `d93ca4e` | None |
| WP-09 record: overwrite, overdub, splice | Verification #96 (#288), #107 (#311), #346 gaps; L01 closed by goldens + #367 | `fa25ae0`, `66c6abc`, `d93ca4e` | None |
| WP-10 crash-injection harness | Verification PR #69 core; #83 R29-B; #86 R29-A; #119/#120; #141 DRAFT-10 ledger 63 rows, zero open (V10-001 disposed) | `867fd4a`, `215204b`, `b05f6af`, `d1ef202` | None |
| WP-11 CLI harness and goldens | Verification #143 PASS on exact #369 `b61a9e9`: golden 10/10, §8 differential on three configurations, mutation 7/7; Michael approved all ten references (#367) | `d93ca4e` | None |
| WP-12 re-spool / defragment | Verification #81 (#236), #87 (#272), #123 (#328); `wp11_ledgers_r63` WP-12/12a 36 rows, zero open | `788cb76`, `e4e15a0` | None |
| WP-13 embedded-readiness audit | Verification #83 at exact PR #241 `74f1173` (DRAFT-9, six gates); carried to DRAFT-10 by #361 | `867fd4a` | None |
| WP-36 slot capability model | Verification PR #57: 100,000-sequence / 1,997,914-operation literal-NULL campaign | Product PR #200 | None |

## Open independent findings

- `P1-R23-V01` rejects Hardware PR #87's sustained-write audit method. This is card
  characterisation, not engine coverage; it is parked with hardware (WP-05, ADR-160).
- `P1-R29-V01` (the old #227 continuity/budget-1 evidence) is superseded by the complete
  WP-10 and WP-12 ledgers (#141, #143). No engine finding is open.

## Reproduce

```
tools/fetch-evidence.sh            # raw observations live in a release asset
tools/ci/verify-spec-bundle.sh
make -C tests/mount_draft8 check
tools/ci/build.sh
tools/ci/unit.sh
tools/ci/run-golden.sh
```

The golden suite is green on main; a red golden run is a regression, not an expected
failure. A missing dependency is not a passing test.
