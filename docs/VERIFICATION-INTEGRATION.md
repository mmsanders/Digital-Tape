# Independent verification integration

**5 November 2026.** Which independent publications back each accepted package, and where
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
  V378 `98f46c94` (PR #379) publishes the explicit ADR-202 correction: 28 cases/four controls,
  exact ee478a91 off-target clearance, predecessor bytes unchanged. Software #647 integrated
  at `aa472667` after docs-only base sync and 117 passing checks; scoped code identities match.
  F6 passes, F1 host/F2 static carry, target halves do not. Full WP-17 acceptance pending.
  [PM650](REVIEW/PM650-P3-R2-2026-11-02.md) routes BE-1 kit Software652 and rig correction
  Hardware651 to independent review. V380 d23a90f7 publishes 27 aggregation regressions
  (old judge fails six late-corruption cases) and preflight; no repaired-head acceptance.
  [PM655](REVIEW/PM655-P3-R2-2026-11-03.md) receives both declarations and routes executable
  BE1-IF/2 / R374-2 bindings to V382. Published89bc424e (109/4),7df60b14 (71 timing),
  458be603 (53/47 IF3) and84c95d0e (229 records) bind the ready scopes; old bytes carry.
  [PM661](REVIEW/PM661-P3-2026-11-04.md) carries the later publications:
  V388 ebe20e08 (source7927f905, be1_review_r1 treea2540d46) holds kit d62e0de0 for
  SW652-R1..R3; V394/80d93c50 now clears corrected0db6ce5c bounded behavior. V3905b791e02
  (source5c6a5c1a) holds CI660/e0b6bb02 for removed supported-platform retained census;
  green111 checks authenticate execution, not coverage acceptance. V3922fc2298b
  (sourcef07495df) clears Hardware c55e5ad artifact-consistency correction:339 published
  plus3 CLI scenarios pass. Judge blobd4ab1866324cc8b87a0f80c2f3b48e3d664c33ee carries
  unchanged into443a5a53, which imports CLI treee52f7a5c and wires regression/negative
  controls. Software663 integrated unchanged hardware at60dfe6aa (head168b7dc0),
  after52 current-base successes/15 classifier skips. Physical method stays NOT CLEARED.
  [PM666](REVIEW/PM666-P3-2026-11-05.md) carries V394/80d93c50 (sourceb457ff75,
  CI41934691508): kit109/4/53/47 +8 cases and32+6 controls independently pass.
  V394/8790e20d (source7ae5f115, CI41936971089) publishes wp14_supported_r1
  tree15afc9e2 and review_order_r1 treebfad9c6b BEFORE Software corrections.
  Selftests are not returned-candidate acceptance. PR660/d8ead444 and665/8ce0fe52
  now go to V397 for actual-adapter/history/gate disposition; arm-m3/regression
  failures remain merge blockers until Software667's unchanged-gate runner repair.
  Independent registry supplies review/chronology facts; Git proves lineage/identity.
  Metadata-only final provenance is allowed; existing imported trees stay immutable.
  No repeat Hardware/kit acceptance solely for base/CI metadata; no target advance.

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
