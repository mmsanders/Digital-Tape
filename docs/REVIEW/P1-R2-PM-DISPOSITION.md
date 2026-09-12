# P1-R2 PM disposition — returned verification, software and hardware work

**Date:** 12 September 2026 UTC · **Authority:** normal PM only · **Product input:**
`40507bf44db2f2743abddcc0188674938f4db89e`

This is an evidence and product-decision record, not a work assignment. Current work
directions live only in role-labeled issues.

## Exact returns reviewed

| Return | Immutable input | PM disposition |
|---|---|---|
| Verification issue #3 | verifier main `7ca24853ed32ddd327461594a31021cba4a408f3`; hardened source `dcc4d7cdb357cf0b082071390c762c25b650f617`; `tests/ops_draft8` tree `4a862fa69ccb2fc4c9afe59c9c9161c3470f9263` | P1-R1-V01/V02/V03 and D01 are resolved in verifier source. The package is ready for exact mechanical import. This is verifier-package readiness, not a product run or product acceptance. |
| Software PR #48 | `c4bd824bdf2bf7ceef9d497ec183ec155a9b45ba`; old verifier tree `c8a43df69a6be8e2c34bf79a1d79933abf48286a` | The old baseline import is authenticated and the adapter/link diagnostics are useful. It is superseded for integration by the hardened tree above and must not merge in its current form. |
| Hardware PR #47 | `74a9c2bf7a0cff4f449aedb3b63daa5771bb7e2a` | The sourcing/gap packet is coherent and its reproducible gates retain a PROVISIONAL timing verdict and CLOSED fabrication gate. It may receive normal integration review; no safety response, card or circuit is accepted by this disposition. |

## PM reproduction

- Verifier: `make -C tests check` passed, including two conforming cases, twelve
  targeted oracle controls, spec authentication, saved-evidence replay, and
  missing/tampered-evidence failures. Offline replay of the committed bundle passed.
- Software: the old package self-test passed (two conforming plus six mutations),
  the independent mount package remained 10/10, and the adapter failed to compile
  against current main exactly at the recorded DRAFT-8 API divergence. The held #20
  diagnostic's six undefined operations remain a blocker; no real VT8 media exists.
- Hardware: spec, thermal, mechanical, solenoid, atomicity and fabrication-gate
  regression tests passed; the real fabrication gate returned exit 2 with five
  blockers. CadQuery-dependent checks were not rerun locally.

## Decisions

1. The hardened verifier tree `4a862fa...` is the only authorized next VT8 import.
   Keep its assertions, evidence contract, executable modes and source identity exact.
2. Do not merge any mount split yet. Choose Software's option 3: wait until the
   DRAFT-8 §5.5 all-slot `cartridge_sequence` derivation is independently observable.
   Do not carry uncovered allocator functions onto main merely to satisfy a link.
3. Do not make a header-only DRAFT-8 API update and do not implement the six missing
   operations from two narrow cases. Main's older provisional API remains visible
   debt until corresponding independent coverage licenses a coherent implementation.
4. Michael's cost clarification supersedes the old no-64GB and six-SKU plan. The
   evaluation population is 2 × HTsemi `SDHFSBC064G` (64 GB, V30) and 2 × HTsemi
   `HTF032G3U3` (32 GB, U3 without V30). This is a sustained-write comparison only;
   it does not establish U3 equivalence, atomicity or card qualification. Michael
   still approves the actual order and identifies a non-limiting reader.
5. Recommend main protection after the current PM publication: require PRs with zero
   approvals, conversation resolution, the six currently-green engine jobs and
   `hardware / print packet is printable`; block force pushes/deletion and enforce
   for administrators. Keep the known-red WP-11 golden job and toolchain-dependent
   CAD jobs visible but non-required. Michael authorizes repository settings.

## Holds and exclusions

No product-engine code was reviewed, accepted or merged by PM. PR #20 remains held.
No real product observation has run through the hardened VT8 package. Full WP-07,
WP-10, WP-11, WP-12a and WP-36; operations/state freeze; PCM goldens; card atomicity;
hardware safety; fabrication; charging; and purchases remain open. The DRAFT-8 hashes
and signed Phase 0 scope are unchanged. A lead closing an issue means only that the
lead stopped; PM evaluates the linked return and issues fresh work when useful.
