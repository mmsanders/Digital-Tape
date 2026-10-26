# Verification324 r2 — correct the Windows platform constant, preserve interaction gates

Authority: Michael manually requested review/unlock of Software progress; PM583/324
scope remains unchanged. Source declaration/return is Product PR587 head
2decba2f2d38bcd6add6390ffc285e2864bf22ca, based on920f3d05. r1 publication
38c20dea/478499b2 predates implementation. r1 remains BYTE-IDENTICAL and historical.
This corrected publication follows inspection of that covered source/record and
does NOT claim to predate it. No new behavior or retrospective tests-first claim.

## Verification-origin defect and exact correction

APP-1/ADR194 requires selection preservation, not an impossible platform literal.
The primary [HTML Standard, text-field selection](https://html.spec.whatwg.org/multipage/form-control-infrastructure.html#textFieldSelection)
(retrieved26Oct2026, selection-direction rules) specifies forward on platforms that
do not support none, and identifies Windows as such a platform. The literal none
in six r1 expected readbacks was a Verification error. Software correctly returned
it instead of editing imported assertions or faking the observed value.

Only six expected readback direction constants change none→forward, in
E-ascii-caret, E-astral-caret, E-paste-exact-limit, E-reject-nul,
E-delete-to-empty and E-two-edits-reversed-acks. The requested setup remains none;
the actual browser readback is forward. Nothing normalizes or overwrites observed
values. All32 cases, steps, text, UTF8 bounds, start/end offsets, focus, selection,
details/scroll, callback and lifetime obligations remain. The same-before/after
actual selection comparison is unchanged. Forward/backward selections are still
distinguished, and real direction loss still fails. compatibility.py proves the
exact six-field catalog delta against r1 and rejects a deliberately changed actual
direction. contract.py contains the same predicates/self-controls as r1.

The retained plain-input/no-Product probe from hosted40266533461 (Edge155.0.4283.62,
win32, Windows Server runner) corroborates the primary rule: none requests read
forward; backward remains backward. It is not native Digital Tape/Windows11 UI
acceptance. No new browser/native probe was performed by Verification.

## Unicode-safe diagnostic helper and strict CI gate

The failed job121390058327 log shows a UnicodeEncodeError in Software's
interactions_summary.py while serializing the pre584 failures through Windows'
legacy output encoding. The later PowerShell JSON error is secondary to that
truncation. Original partial summary and complete underlying records remain retained.

summary.py is an OPTIONAL diagnostic writer from this independent package. It
serializes JSON using ASCII escapes and can write directly to --out; decoded
Unicode values are unchanged. Its positive/failing/Unicode transport controls
include a cp1252 round-trip. It is not a substitute acceptance gate.

```text
python -B tests/windows_interactions_r2/summary.py --input RESULT --candidate HEAD --out SUMMARY
python -B tests/windows_interactions_r2/contract.py --input RESULT --candidate HEAD
```

Software may mechanically use this helper instead of its unsafe stdout summary.
Check every command's actual exit immediately. The positive current qualifier must
exit0; do not mask its failure with a later successful probe or LASTEXITCODE=0.
The old-renderer control is expected to fail the qualifier and score below current;
handle that expected failure explicitly. Preserve the old failed job/artifact.
No rerun/install/browser-version upgrade is needed to diagnose either defect.

## Handoff / unchanged method

Import this NEW r2 subtree and its publication identity before updating the
workflow/adapter references; do not edit the r1 imported files or its import receipt.
The r1 README's production mountApp/mountScreen/Bridge method, actual raw/source/
adapter linkage,32-case coverage and all runtime exclusions still apply. --emit
retains the same scenarios; only the six correct Windows readbacks differ.

Offline replay of already retained current records passes all32 obligations under
r2; old renderer passes19/32, retaining13 real failures. That is controlled-component
evidence, not a successful current-head CI run or a new source/merge clearance.
New workflow/import head needs ordinary exact-head CI and direct return before final
324 disposition or325 build dependency release. No Product frontend change is
requested merely to implement an unsupported none direction. Existing lifecycle/
parser/backend/native facts carry without old corpus or runtime replay.

No new Product/app/child/device/metadata/OS-input experiment, permission change,
new provider/install or second UI/reference controller. Neither this package nor
the summary clears native/G1/A6/S3/INGEST/fullAPP/G2/Make/elevation. Listeners PAUSED;
324/325 remain OPEN for the bounded next return, no polling/automatic assignment.
