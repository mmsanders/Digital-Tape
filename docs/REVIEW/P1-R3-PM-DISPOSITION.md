# P1-R3 PM disposition — merged integration and retained controls

**Date:** 12 September 2026 UTC  
**Owner:** PM under [issue #51](https://github.com/mmsanders/Digital-Tape/issues/51)  
**Input product main:** `5b0f891222a68848a7c94282f335368c256f902a`  
**Input verifier main:** `7ca24853ed32ddd327461594a31021cba4a408f3`

## Disposition

Hardware PR #47 merged as `8d9e8bdffc245d797702a2b3a461348672b0644a`.
Software PR #48 merged as the input product main. The imported
`tests/ops_draft8` tree is exactly
`4a862fa69ccb2fc4c9afe59c9c9161c3470f9263`, matching independent Verification,
including all eleven blobs and executable modes. This authenticates the import;
it is not a product-code review, real-engine observation or acceptance.

PM reproduced these integration checks on the input main:

- `python3 tests/ops_draft8/selftest.py`: PASS for two conforming traces, twelve
  oracle controls and the spec/evidence/replay controls; missing and tampered
  evidence fail as required.
- `make -C tests/mount_draft8 check`: PASS, 10/10.
- `tools/ci/verify-spec-bundle.sh`: PASS for the frozen specification bundle.
- `tools/ci/all.sh`: all build, allocation, funnel, stack, memory, meta-gate and
  scaffolding checks passed; the command exited 1 only at the deliberately red
  WP-11 golden gate because `tests/golden/MANIFEST` remains absent.
- Hardware spec, thermal, solenoid and fabrication-gate regression tests passed.
  The real fabrication gate remained CLOSED with exit 2 and five blockers.

The synthetic adapter has never run against the real engine. `seek`, `arm`, `feed`,
`service`, `commit` and `reset_side_b` remain undefined. Therefore VT8-001 does not
provide a product observation and grants no WP-07, #20 or broader acceptance.

## Retained correction and queues

The new supply-envelope inequality rejects a direct one-off out-of-envelope
mutation, but `hardware/thermal/test_solenoid.py` has no targeted retained negative
control for that criterion. The existing generic fail-open mutation would survive
deletion of the exact inequality. A bounded Hardware correction is required.

Independent Verification issue
[#4](https://github.com/mmsanders/digital-tape-verification/issues/4) remains open
without a return and is not superseded. Michael issue
[#49](https://github.com/mmsanders/Digital-Tape/issues/49) remains active. Software
and Surge have no newly useful task this round, so no issue is created for them.

## Holds preserved

- Draft PR #20 remains held; no engine code or uncovered operation is accepted.
- WP-11 remains deliberately red pending independent playback/golden evidence.
- Frozen specification hashes and independent Verification ownership are unchanged.
- Fabrication and cell charging remain CLOSED; solenoid timing remains PROVISIONAL.
- No card purchase, speed-class equivalence, atomicity qualification or physical
  print result is inferred. Michael retains purchase, settings and final-signature
  authority.
