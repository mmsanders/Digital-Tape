# Historical — superseded by P1-R1; do not execute

# Verification — next independent return

Phase 1 role: read [the role instructions](../ROLES/verification.md).
Work directly in your lead chat; the current coverage and safety holds remain binding.

**From acting PM · 8 September 2026 · Published instructions, carried by Michael.**

Your delivery at 4ee116fa040bb5ce040325e0076365abf8b0f8f9 was imported verbatim.
DRAFT-8 is canonically issued through #25 and all four files match your authenticated
test baseline. Tests landed on main through #27 before any corresponding new engine
implementation merge. Thank you for making the uncovered boundary explicit.

## Immediate request

Independently disposition the observations in
[the run packet](../verification/runs/2026-09-07/README.md).
Read the existing spec/tests and raw JSONL, not untested implementation, private tests,
PR #20’s mixed discussion or its diff. The two gzip files are lossless raw logs.
The after-run engine publication is 740c97e998c7672d9e98916102be84430993521b.
That SHA identifies the tested branch; it is not an instruction to inspect its code.

Software observed 15/289 failures before the DRAFT-8 reconciliation and 0/289 after.
The probe used the real public header/library; no fixture, assertion or accepted
result changed. Please confirm the covered assertions or return exact findings.
No need to repeat the full paper review of unchanged bytes.

## Next coverage needed

VT8-001 remains: independently test allocation events and all-slot running-sequence
consumption through specified public operations/media observations. Also preserve
the explicit warm-start/state-transition/operation exclusions in COVERAGE.md.
Return a tractable next tranche and required mechanical adapter contract.
Do not invent a product API or derive expectations from implementation.

## Return

Publish independent disposition/test source with immutable commit, covered test IDs,
actual runs, raw evidence and residual exclusions. PM/Software will import it into
Digital-Tape so new agents do not depend on chat history. If you need to inspect any
implementation, first identify which behaviour has independently authored landed tests
and stay within that boundary; a file containing mixed behaviour is not blanket permission.

No request for full WP-07 acceptance, green complete WP-10, operations freeze, WP-11
goldens or hardware qualification in this immediate return. Those obligations remain.
IR-018-18 has an implemented gate response; review it separately when assigned, without
turning software regression results into circuit qualification.
