# P1-R24 PM disposition — integrated VT8 slice, rejected card method, and held A1 Mini packet

**Date:** 20 September 2026 UTC  
**Input product main:** `be7f8f233c9eed5d70c6bc578d169b73e4f83c7c`  
**Input verifier main:** `8ca23c6acfa9e3ec5e96d54f2ec93cb8c329f3c9`  
**PM issue:** #121

## Decision

1. Authenticate Software's PR #112 integration at product main `be7f8f2...`.
   The ruleset-required synchronization merge preserved every authenticated product,
   adapter, verifier-package, spec and evidence tree. The merge is valid at the same
   narrow two-observation boundary; it creates no source or complete-package acceptance.
2. Accept Verification's rejection of repaired Hardware PR #87. `P1-R23-V01`
   reproduces: three adjacent malformed records terminate by traceback and eight
   malformed version/identity records pass. New sustained-write acquisition remains
   blocked pending another exact repair and independent re-audit.
3. Authenticate Hardware PR #120 as a useful but held advice/method candidate at
   exact head `7b224ff...`. Its `buy nothing now` recommendation is the safe current
   wallet decision. Named PETG/TPU products and categorical material exclusions remain
   provisional because neither Hardware nor PM could retrieve the cited first-party
   compatibility pages or datasheets.
4. Route the exact A1MINI-01 rev-1 method to independent Verification before any print.
   Its generated packet and controls reproduce, but its claim that one fit ladder can
   establish whether the printer resolves a 0.08 mm clasp sweep, and that nominal-volume
   mass coupons diagnose flow/repeatability with the available scale, require an
   independent method disposition.
5. Keep PR #120 draft and not merge-ready as a current-main integration candidate. It is
   clean against its assigned parent `8a7a8ba...`, but main advanced through PR #112;
   the active strict up-to-date rule therefore requires synchronization and fresh
   checks before a later merge. Its ten-path hardware delta is disjoint from PR #112;
   a normal three-way merge would retain those later main paths. Verification audits
   the exact hardware delta against its assigned parent; Hardware synchronizes only
   after that disposition.
6. Supersede only ADR-119's historical premise that Michael would not own a printer.
   Retain its zero-closed-strain and matched-pair design outcome: material robustness
   remains desirable even though the project may now choose material and colour.
   No material, printer, process or part is qualified.
7. Advance no roadmap rung. Preserve all product, physical, fabrication, charging,
   safety, wallet, regulatory and Michael-reserved holds.

## Software #118 / PR #112 integration

Product main `be7f8f233c9eed5d70c6bc578d169b73e4f83c7c`, tree
`5f7b1aa5463abc096fa4a6de6056ca00b6430857`, is a normal merge with parents the
assigned main `8a7a8baed67c64a69d894daf6ce1ac5fbe268597` and synchronization merge
`6e0de710c9ccc93bf90f9660a58fcdfc8adb1509`. The synchronization merge has parents
the accepted evidence commit `15fbcfae0085d5e2f2cb983959fe063c2233fa40`
and assigned main. It was required by the active strict up-to-date branch rule.

PM directly compared the authenticated candidate and synchronized/main trees:

| Path | Exact tree before = after = main |
|---|---|
| `engine/` | `65a72f78572223364c51e265fd68bffdda2b6518` |
| `tests/ops_adapter/` | `6f6df812ae346933dff91aebb739feb0e2f0a113` |
| `tests/ops_draft8/` | `3667a2830ba80dbcedad03b97870d1127001ab59` |
| `spec/` | `07f86e9cc5e74651c76b4769aeae103962396c14` |
| `docs/verification/runs/2026-09-19-r21/` | `21354797871a34e19d907fba34ed1e8539bf9209` |

The code-then-evidence commits retain their original identities and ancestry. Held
heads from PR #20, #64 and both PR #96 heads remain outside new-main ancestry. All ten
substantive engine CI contexts were green at the synchronized head; only the deliberate,
unrequired WP-11 missing-golden job remained red.

This closes the integration task only. Independent acceptance remains exactly
`VT8-001-RB-ALLSLOT` and `VT8-001-REC-ALLOCSEQ` as recorded observations. The
splice-only `tape_arm` policy, stage-1 `TAPE_ERR_BUSY` policy, source/helper design,
other behavior, complete WP-07, atomicity, PCM, goldens and listening remain unaccepted.

## Verification #19 / repaired PR #87 rejection

Verifier main `8ca23c6acfa9e3ec5e96d54f2ec93cb8c329f3c9`, tree
`02c83fd625aea39057f9c7bc40368a22bafa07aa`, is a one-file child of
`391d6a8308edfca46f639c3a6567c220d7a7b95d`. The finding SHA-256 is
`f634781f6bb1f520cb538e8a1a386301eaf04ac877b7a03c831db81095796a16`.
PM authenticated the return and reran the full verifier suite.

Accept `P1-R23-V01`. The exact repaired PR #87 head `e520c2c...` narrowly closes all
named `P1-R21-V01` forms and rechecked prior boundaries: 55 intended one-field
mutations controlled-reject with their intended marker; independently built mounted
and honest raw-device baselines pass; the acquisition writer and five schema-1 records
remain byte-identical.

The method as a whole remains rejected. PM independently reproduced all eleven
adjacent failures:

- `bytes_per_mb == 0`, zero `space_after_measurement.total_bytes`, and nonnumeric
  `schema_version` raise `ZeroDivisionError`, `ZeroDivisionError`, and `ValueError`;
- `schema_version == 3` passes despite no schema-3 contract; and
- non-string `sku`, `revision`, `cid`, `sample`, `reader`, `measured_at`, and `host`
  each pass without a problem.

Hardware must validate the top-level JSON object and every required identity field,
require exact schema 2 without coercion, and require positive divisors before any
arithmetic. Each retained control must reject with its own field named and no traceback.
Whether identity strings must also be nonempty remains a separate policy question;
this round does not invent that requirement.

No physical acquisition, qualification or stored-result promotion follows. The real
fabrication gate remains CLOSED/nonzero with five blockers.

## Hardware #119 / held PR #120

Held draft PR #120 head `7b224ff2523a5d02ddb2b136732cc98ab6994591`, tree
`9022b8d279e79b5335a25986bcdbfba36b44efe0`, has sole parent its assigned product
main `8a7a8baed67c64a69d894daf6ce1ac5fbe268597`. Against that parent it changes only
the A1 Mini material note, the A1MINI-01 generator/tests/packet and Hardware Makefile.
The existing library packet and PR #92 are unchanged.

PM reproduced A1MINI-01 generation and checks: six objects, a 132 x 42 x 26 mm bound,
six 0.05 mm ladder rungs, three 2400.0 mm³ nominal-volume coupons, committed-byte
identity and a 40 x 40 mm negative bed control. The existing library packet checks,
hardware regression controls and fabrication-gate controls pass. Hardware CI is green;
the ten substantive engine jobs are green and the deliberate WP-11 job remains red.
The real fabrication gate remains CLOSED with five blockers.

These results establish deterministic printable files and internal controls only.
They do not establish that a single subjective ladder measures printer resolution or
repeatability, that nominal-volume mass detects under-extrusion rather than conflating
filament density and dimensional error, or that Michael's scale has useful resolution.
Independent Verification receives those exact method questions without a print.

Hardware's current safe recommendation is accepted only as **buy nothing now**:

- use the already-owned white Bambu PLA Basic for currently justified geometry work;
- do not buy TPU while no TPU part exists; and
- do not ask Michael to buy PETG until the process method and primary compatibility/
  datasheet evidence are adequate for a specific test.

The proposed Bambu PETG HF, TPU 95A and third-party fallbacks remain leads, not an
approved or source-verified bill of materials. PM's direct public-web attempt also
failed to retrieve the first-party pages. No categorical safety/support conclusion
for ABS, ASA, PC, nylon or filled filament is accepted from search-index snippets.

ADR-119's zero-strain clasp outcome remains controlling. Its old library-only premise
is superseded by Michael's A1 Mini ownership and the current printer policy; this does
not reopen the clasp or qualify a selected production polymer.

## Routing and stop

- Hardware receives a bounded repair of the eleven exact `P1-R23-V01` card-method
  failures on PR #87. It must not run a card or touch PR #120/#92.
- Verification receives an independent, no-print audit of exact PR #120 A1MINI-01
  method files against the assigned parent. It does not disposition materials,
  product code, PR mergeability or a physical result.
- Software, Surge and Michael receive no issue. There is no merge, miscellaneous,
  purchase, print or other owner action ready for them this round.

PM stops after publishing this disposition, refreshing the dashboard, issuing the two
bounded assignments and closing #121. Lead closure remains a work-stop signal only.
