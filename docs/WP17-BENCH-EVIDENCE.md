# WP-17 bench evidence — BE-1

**PM-issued, 2 November 2026 (ADR-203).** Companion to FW-1; no acceptance limit
changes. This defines evidence artifacts and offline checking for the first bench
session. Assignments live in role issues, not here.

## Boundary

An offline check can establish artifact consistency and detect bad captures. It
does not establish that hardware ran, supply independent acceptance, qualify a
card, or replace Michael's witness and Verification's raw-data audit.
No physical session is ready merely because the offline checker passes.

Until parts/assembly and the exact kit are ready, target criteria remain NOT RUN.
FW-1's fixed-low-output/volume-check restriction remains. USB power only; no cells,
charging, power-cut rig or automatic destructive card preparation in this kit.

## Evidence bundle

Keep a session manifest with input Product commit, firmware binary hash, toolchain
pins, target/board revision, card identity as actually available, capture tool/version,
timestamp, operator/witness and per-file SHA-256. Missing CID is explicitly unknown
and is not required (ADR-208); once firmware runs it logs the CID at mount.

Preserve raw serial bytes/transcripts and every failed attempt alongside results.
Separate actual captures, simulated fixtures and absent observations. A simulated
case must never be reported as a physical PASS. Files over 1 MiB use release assets
with hashes under the standing evidence policy.

| Criterion | Required facts | Result boundary |
|---|---|---|
| F1 target | Seven normal-rate cases with exact reference identity, side/start/frame count/mode, raw returned PCM or digest, and matching extracted reference PCM | Check byte/digest and exact frame count; report malformed, truncated, wrong-reference or mismatching output. No whole-WAV/raw-PCM confusion. A digest/serial result alone does not observe analogue/I²S behavior |
| F2 target | Static engine terms and reserve separately from board/core totals; actual `tape_instance_size()` and painted-stack high-water from a target transcript | Reserve must fit actual size; existing RAM/.rodata/8192-byte stack limits stand. Missing actual/stack observations remain NOT RUN, never zero or inferred from a static map |
| F5 | Raw Play/Stop/position and removal record witnessed by Michael; exact before/after card identity and manual `tapectl verify` result | Missing witness, continuity or post-removal verify is incomplete. A transcript checker alone cannot establish a safe physical removal or card preservation |
| F3 | Firmware-timed wake → first non-silent frame from the serial log, plus Michael's MICHAEL-CHECKS verdict (ADR-208) | NOT RUN until the bench build exists; the firmware timestamp is the measurement |
| F4 | Recording/commit-latency evidence at the required entry count and card | Remains deferred to WP-18/19 |

## Offline checker interface

The Software kit exposes `python firmware/bench/tools/bench_evidence.py --offline
BUNDLE --out REPORT.json`. It reads saved evidence only: no serial/device connection,
flashing, disk opening, provisioning or network access in offline mode.

The versioned input manifest identifies each observation as `actual`, `simulated`
or `not_run`. Software declares the schema and serial/transcript grammar before
implementing new checker behavior; Verification authors expectations from this
contract/schema before that implementation. No implementation-specific assertions
or private test expectations are supplied to Verification.

The JSON report names the source identities/hashes, provenance class, per-criterion
observation state (`CONSISTENT`, `MISMATCH`, `INVALID`, `NOT_RUN`) and reasons.
Use `CONSISTENT`, not independent acceptance or target PASS. Missing observations
give NOT_RUN; malformed supplied evidence gives INVALID; contradictory or nonmatching
supplied data gives MISMATCH. Exit nonzero for INVALID/MISMATCH; incomplete NOT_RUN
may exit zero but must include `complete: false`. Simulation always has
`physical_run: false` and cannot make `complete: true` for a target session.
`complete` describes only the manifest's explicitly requested observation set,
not package acceptance. The first-session set is F1/F2/F5; F3/F4 retain their
separate pending/deferred states. Omitting a required first-session observation
cannot make that set complete.
The checker must reject manifest/file digest mismatch and conflicting candidate
identities, without rewriting the original evidence. Each output remains tied to
the exact input bundle and tool version.

## Preparation and handoff

The reviewed kit includes a short pin/wiring reference, exact firmware/tool inputs,
manual non-destructive first-start steps, reference-card preparation directions using
the existing WP-14 safety contract, and capture/return instructions. Existing serial
hooks may be composed; new behavior follows the independently published tests.
Controls include an altered sample, bad frame count/truncated transcript, false stack
value/omission, wrong artifact hash and contradictory simulation/physical markers.
Self-reported provenance alone is not proof of a physical run; the audit still checks
raw evidence and witness context.

Any actual bench work needs parts in hand and a separately ready, scoped Michael
session. This contract grants no physical authorization and does not turn the
unqualified atomicity rig into a bench prerequisite for ordinary unbatched playback.
