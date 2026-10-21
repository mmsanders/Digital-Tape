# ADR189 §7 boundary-query independent extension

Verification208, 20 October2026. **AUTHORED ONLY; no S3 implementation/platform method or actual child acceptance.** Authority is Product `d09e5ba772729cb9b3d1c9b38b9052c4cbf77c6e`, APP-1A §7; unchanged annex snapshot is in spec/. Original cards/make tree81b627b7 and APP treebdd861b6 carry unchanged. This new separately identified package does not alter an imported immutable package.

49 finite model rows cover the five issued phases, required initial failure before write-mode access, optional-monitor success/omission (no new cadence), ordinary monitor failure, positively detected change including simultaneous ordinary query failure, known policy refusal and report-write failure on failed and successful commands.23 causal negatives detect early write access, ignored/relabeled failures, malformed payloads, continuation/reopen, rollback/lost stdout, report-warning suppression and changed ordinary success.

`oracle.py` loads an isolated copy of the already-published APP oracle and extends ONLY the new HOST_QUERY_FAILED make exit1 ID, null subject, phase set, op=media_query and string os_error. Existing IO bindings and underlying package bytes stay unchanged. New ID maps to card-interrupted. Other IDs/messages use existing predicates. Synthetic rows and zero-valued sample artifact hashes are **authoring controls only**.

## Actual-return interface

`check(observation)` consumes an independently bound actual-query/device/report journal: phase; initial/required/performed; ordinary query error vs positive change; known policy refusal/known facts; qualified observer/completeness/positive control; write-mode opens/destruction before required query; actual ordinary child error/exit; continuation/reopen; earlier/final stdout and publication inventories; report write failure/warning/stop; and actual raw report bytes as hex with exact nonce/version.

An adapter must bind these fields to the actual compiled test or qualified native raw events, child binary/source and original artifact SHA256. A test-fault seam may produce controls only in the issued compiled-test path; it cannot become a shipping receipt or fake successful OS query. The oracle's metadata checks are not independent authentication of a raw trace and never confer acceptance by themselves. With report failure, ordinary process outcome is judged independently; missing/truncated report cannot suppress it. Partial outputs preserve their actual pre-failure state; no unchanged-card or rollback claim.

Required initial queries precede write-mode access. Later monitoring is optional; a failed query actually performed must stop. Known policy refusals remain exit3/zero write-mode opens; unknown facts never become safe. Positive detected change remains CARD_CHANGED. No new queries, engine outcome or cadence is introduced.

## Per-platform method boundary

- Windows/macOS: HELD under ADR189; access-upgrade and post-path-open checks do not establish binding before authorized write-mode access.
- Linux: retained inode/diskseq facts are bounded capability evidence; the tested access upgrade succeeded after changed sequence, so no S3 method clearance.
- This oracle extension is available for exact import/tests, but enables **no platform** or production implementation by itself. No speculative API search/probe or human/card task.
- No-repeat claims: no39-row/audio/crash/census campaigns or closed209/466 replay; report/substitution and native G1/G2/physical/full APP holds carry.

Run `python3 -B tests/wp15_boundary_query_r1/selftest.py`. CI checks the annex snapshot and closed-file SHA256 manifest, runs the49/23 authoring controls and publishes a deterministic exact package archive/provenance/SHA256SUMS. The required sibling `tests/wp15_app1a_r1/oracle.py` stays at its prior published bytes; its required SHA is pinned in pins.json. Return import archive/tree/source identity to Product480 after this publication is merged; future actual commands need independent method clearance first.
