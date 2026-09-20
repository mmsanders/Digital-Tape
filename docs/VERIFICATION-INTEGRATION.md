# Independent verification integration

This file states the **current** integration boundary and what is independently
accepted. It is not a chronicle. The per-round import narrative for P1-R1 through
P1-R24, with every source publication, tree, blob and findings hash, is preserved
verbatim in [the verification integration history](archive/verification-integration-history.md).

## Current clean integration boundary — 20 September 2026

PR #77 is merged at product main
`4e1d248b62866871613775a50ab931f4a4597a52` with history preserved. The exact
ten corrected-cadence playback observations and exact 289 mount records are
independently accepted. That disposition does not accept source/helper design,
complete WP-06/WP-08, listening, WP-11 goldens or a package. Held PR #20/#64 are
not ancestors, and uncovered allocator/recording/crash/warm/state/operation and
performance behaviour was not imported.

Product main `48cc23fdbe6273dfe73f17fbdddf8e9fcc5ab3d9` imports corrected
complete verifier tree `3667a2830ba80dbcedad03b97870d1127001ab59` exactly and test-first.
Held PR #96 evidence head `088226a3c324a97fe19d4a4285a80af037b097d5` contains two
passing raw cases produced without an engine/adapter-tree change. Verification at
`e77b61fe420e48444cf0791c74fc7e296ef0ccf6` independently accepts exactly those
reset-side-B and recording/allocation observations. This does not accept source,
allocator/all-slot behavior beyond the exact cases, PR #96, WP-07 or the package.

PR #112 is then integrated at product main `be7f8f233c9eed5d70c6bc578d169b73e4f83c7c`,
tree `5f7b1aa5463abc096fa4a6de6056ca00b6430857`, through synchronization merge
`6e0de710c9ccc93bf90f9660a58fcdfc8adb1509`, which preserves pre-run code `20505f4...`
and evidence `15fbcfa...` as ancestors. `engine/`, `tests/ops_adapter/`,
`tests/ops_draft8/`, `spec/` and the exact run packet are unchanged across the
candidate, synchronized and final-main trees. Held PR #20/#64/#96 heads remain outside
ancestry. The integration changes no independent boundary: it re-confirms the same two
exact observations already dispositioned at verifier `391d6a8...` and accepts nothing
further.

Current work directions live only in role-labeled issues.

## Integration rules that do not change

- Verifier package trees — `tests/mount_draft8/`, `tests/ops_draft8/`,
  `tests/playback_draft8/`, `tests/playback_complete_draft8/` — are imported **verbatim
  with modes preserved** and are Verification-owned. No assertion, fixture, expected
  sequence, operation argument, ordering, range, tolerance or exclusion is ever changed
  on import. Route a disagreement to Verification/PM.
- The nested `spec/` inside a package tree is an **authenticated test baseline**, not a
  second canonical publication point. Product authority is `spec/`; those copies are
  held in place by tamper controls (`VT8-A13`, `PB8-A01`) and must not be deduplicated.
- Product adapters (`tests/ops_adapter/`, `tests/playback_adapter/`) are Software-owned
  and live **outside** the verifier trees.
- Structural Rule 1 ordering is recorded per import; see
  [CLAUDE.md §3](../CLAUDE.md).
- A green run is not acceptance. Authorship, harness checks, engine execution,
  independent disposition, merge and package acceptance are separate facts.

## Coverage

| Package | Accepted units | Outstanding areas | Source publication hash |
|---|---|---|---|
| WP-06 mount — `tests/mount_draft8/` | Exact 289/289 mount case records, including row 3 | Source and helper design; complete WP-06; merge status | Import `4ee116fa040bb5ce040325e0076365abf8b0f8f9`; hardened tree `4a862fa69ccb2fc4c9afe59c9c9161c3470f9263`; disposition `392d6bb9c948a5924fe18728fab04202bc8e337e` |
| WP-07 operations — `tests/ops_draft8/` | Two exact recorded observations: `VT8-001-RB-ALLSLOT` and `VT8-001-REC-ALLOCSEQ` | Splice-only arm and stage-1 BUSY refusal policies (invented, unreached); every unexercised branch; source; adapter design; atomicity; complete WP-07 | Hardened tree `4a862fa69ccb2fc4c9afe59c9c9161c3470f9263` from `dcc4d7cdb357cf0b082071390c762c25b650f617`; corrected complete subtree `3667a2830ba80dbcedad03b97870d1127001ab59` at verifier main `15dd16e...`; dispositions `e77b61fe420e48444cf0791c74fc7e296ef0ccf6` and `391d6a8308edfca46f639c3a6567c220d7a7b95d` |
| WP-08 playback — `tests/playback_draft8/`, `tests/playback_complete_draft8/` | Exact ten corrected-cadence product observation families; 698/698 completed per-render service sequences in each direction | Source and helper design; complete WP-08; listening; goldens | Three-family publication `7a22cbb4447c40c51b7c8b2282a685ed30a46ba6` (subtree `ff810814dbc8079c6903e6f85ed7ee312abd3076`); complete ten-family `121f5f7ab03c9ce08c38329e518c49a1ca9b65a5`; corrected `62b18deb8b4fbe6e797b00d792ee9f46ac0a8059`; cadence correction `e3a25bf3b9eda6581b5de524e5bd5fa2c032e0da`; disposition `392d6bb9c948a5924fe18728fab04202bc8e337e` |
| WP-11 goldens — `tests/playback_draft8/golden/` | **Nothing accepted.** Seven exact product PCM outputs byte-match verifier candidates | Candidate PCM is verifier-derived oracle bytes, unlistened, and is **not** an accepted golden. Golden CI stays red until Michael listens | Carried with the WP-08 publications above |
| WP-10 crash harness | Narrow independent mount package landed | Complete crash/operation/state run is not green | Carried with the WP-06 publication above |

Open independent findings: `P1-R23-V01` rejects Hardware PR #87's sustained-write audit
method (card characterisation, not engine coverage). No engine finding is open.

## Reproduce

```
tools/ci/verify-spec-bundle.sh
make -C tests/mount_draft8 check
tools/ci/build.sh
tools/ci/unit.sh
```

Missing WP-11 goldens remain a separate expected CI failure. A missing dependency is
not a passing test.
