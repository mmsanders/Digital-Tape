# Independent verification integration

**2 November 2026.** Which independent publications back each accepted package, and where
their evidence is. Imported verifier trees and their source commits are declared in
[tests/IMPORTS.json](../tests/IMPORTS.json); CI proves byte identity and ordering
(`.github/workflows/evidence-integrity.yml`, `verifier-publication.yml`).

## Accepted packages

| Package | Independent disposition | Integrated |
|---|---|---|
| WP-06 block device, superblock, commit | Verification #138 DRAFT-10 ledger: 40 rows accepted, 2 unreachable by spec | Phase 1 main |
| WP-07 allocator / copy-on-write | Verification #67, frozen 10,000-sequence package | Product #215 |
| WP-08 playback, seek, scrub | Verification #95, #122, #143; goldens approved by Michael (#367) | Product #369 |
| WP-09 record | Verification #143 | Product #369 |
| WP-10 crash-injection harness | Verification #141 (63 rows, zero open) | Product #362 |
| WP-11 CLI and golden suite | Verification #143; ten goldens, mutation 7/7 | Product #369 (`d93ca4e`) |
| WP-12 re-spool | Verification #143 (36 rows) | Product #369 |
| WP-13 embedded readiness | Verification #66, six gates | Product #206 |
| WP-36 slot capability | Verification #57, 100,000-sequence campaign | Product #200 |
| WP-14 `tapectl` on real cards | Verification #364 Stage 1 `48489cf9`; A4 restored by clearance `3ff22aae` | Main `ea54a41` |
| WP-16 ingest | Verification #364 Stage 1 `48489cf9` (I1–I8, own-host) | Main `1695552d` |
| WP-15 app | Verification #364 clearance `3ff22aae` (exact `5101e3f3`, ZIP `b8a689cf`); #370 C2 `12187bb8`, `1938e651`; G2 deferred (ADR-198) | Main `ea54a41` |

Engine tree pinned at `d96b4245` (A8, ADR-175); goldens and replays green on the last code head.

## Carried into Phase 3

- **Round 1 disposition:** [PM648 review](REVIEW/PM648-P3-R1-2026-11-02.md).
  Verification `41995965` (PR #375), `3d616c14` (#376) and `d7540127` (#377) are merged publications.
  Exact Software candidate `ee478a91` / Product #647 is **held, unmerged** pending a new
  verifier correction/re-disposition under ADR-202. F6 independently passes on that candidate;
  F1 host and F2 static pass, target halves do not. Full WP-17 acceptance is pending.

- **Q-P2-1 any-subset coverage** (ADR-195 §4). The model is published (`tests/wp10_subset_r1`)
  and bounded campaigns found no violation (Verification #186, #210). Verification `41995965`
  executes all 365 deferred faults without violation (404/404 with prior receipts). The six
  requested long cuts are unavailable on the exact three-unit fixture, not executed cuts.
  Broader large-epoch/repeated-LBA completeness and firmware batching remain held by PM.
- **Media atomicity** (WP-05 A-6) has no physical result yet. The judge
  (`hardware/characterisation/media_atomicity.py`) has its own negative controls, but
  Verification `3d616c14` finds skipped non-qualifying tears/stale-busy admission plus
  electrical/timing and SPI-to-SD4 scope gaps. Method NOT CLEARED; no physical tear claimed.

## Where the history is

- Verification findings and raw evidence: the
  [digital-tape-verification](https://github.com/mmsanders/digital-tape-verification) repo,
  each cited by merged commit.
- Product-side evidence bundles: docs/verification/ (raw evidence over 1 MiB is in release
  `evidence-2026-09`; `tools/fetch-evidence.sh` checks hashes).
- Earlier versions of this file, cited by tests/IMPORTS.json attestations:
  - [archive/verification-integration-history.md](archive/verification-integration-history.md)
  - [archive/verification-integration-2026-09-25.md](archive/verification-integration-2026-09-25.md)
  - [archive/verification-integration-2026-10-19.md](archive/verification-integration-2026-10-19.md)
- Round-by-round PM reviews: docs/REVIEW/. Closed phase plans: docs/archive/.
