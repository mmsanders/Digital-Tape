# Verification252 — immutable per-case recorder protocol, Stage1 only

PM510/252 paired Software511. Input Product192fed8cf1f367899db3c9ed967f5c4d1d898dec,
Verificatione6bc7b87dab9d3620c3a018125cb7b404bca8c31. Independently authored before
new recorder implementation, using the actual500 lost-raw and499 stale-timing
failures as requirements, not new Product expectations.32 fixed cases/controls;
only ordinary owned files and new harmless helper processes. No engine/audio/
codec/native/observer/install/security campaign. No old shipping case is rerun.

## Component and actual-return contract

Software may implement a standalone recorder in its chosen normal runtime, plus
a thin test driver. Import this complete package byte-identically first. Expose
an ordinary invocation that accepts one request plus fresh owned run root; document
exact usage/exit/error behavior. Independent tests judge raw behavior, not a fixed
implementation language or imported private checker. Never call this oracle to
generate actual recorder results. A component validate command must independently
reject the listed corruptions. Independent Stage2 also reapplies this oracle.

Fresh run/case namespace: IDs lowercase `[a-z][a-z0-9-]{0,63}`. Only owned root;
reject path traversal, absolute/alias/symlink/reparse targets and existing case
paths before modifying anything. Each ID may be reserved once. A duplicate ID or
existing path is refusal with the complete prior recursive byte census unchanged.
Use exclusive creation and a final commit boundary that cannot overwrite another
case. Publish final completed cases under `cases/ID/`; incomplete cases remain
separately under `incomplete/ID/`. A supervisor may move an interrupted incoming
directory there without rewriting any original raw. Never reuse a missing case,
replace original evidence, delete raw during cleanup, or proceed past an unresolved
failed commit. No power-loss durability or physical filesystem atomicity theorem
is claimed; demonstrate the chosen ordinary-process/filesystem commit semantics.

Request schema: case_id, mode, input_sha256, argv (actual complete child argv),
binary_sha256 (actual child executable bytes), helper_sha256 (this helper source),
source_commit (exact candidate/helper source identity), nonce. Requests are bound
externally to original frozen case inputs and invocation, not accepted from a
tampered receipt itself. Stage2 authenticates source/build/binary/host/PID/nonce
and actual child commands. Keep local paths and raw machine facts private; public
fixtures are synthetic or ordinary CI helper facts only, with complete hashes.

The completed directory has exactly input.bin, request.json, launch.json,
stdout.bin, stderr.bin, exit.json, timing.json, result.json and MANIFEST.json.
launch binds the five identity keys above plus actual positive child pid. Preserve
both streams as ORIGINAL BYTES before parsing, result handling or cleanup. Connect
child streams to fresh owned files or an equivalently proven continuously retained
route; buffering all raw until after result parsing fails the interruption cases.
Helper's first stdout line independently echoes actual pid/nonce/input hash/size.
exit.json has actual integer code; nonzero code7 is COMPLETE EVIDENCE of a failed
child, never a successful test verdict. result.json schema is fixed by oracle.py.
Counts equal original byte lengths, including empty/binary streams.

timing.json: integer nonnegative monotonic start_ns/end_ns/duration_ns and cpu_ns,
end>=start, duration=end-start, finalized:true. Retain actual collection method and
parent/child accounting in the return; don't report a fabricated constant timing
or substitute wall for CPU. Finish timing AFTER the producer terminates and stream
files close and BEFORE the final manifest. All final byte/size/hash entries cover
every original file except MANIFEST itself. No earlier timing placeholder hash.
Commit the complete directory only after hashing finalized bytes. Validate again
before transfer. A child kill/recorder kill/parser/cleanup exception retains raw
prefix/inputs/launch and cannot appear in completed results. Missing final manifest
means INCOMPLETE, even if a later supervisor labels its stop; an incomplete record
must never be repaired by regenerating lost raw or relabeling it complete.

Archive inventory binds every completed and incomplete original file, each final
case manifest, and any stop/supervisor receipts. ARCHIVE-MANIFEST.json excludes
itself only. Reject extra/missing/duplicate/unsafe members, altered/truncated ZIPs
and stale per-case bytes. Archive validation happens after final close. Original
failed artifacts are retained separately; no overwrite by a corrected transfer.

## Frozen32 checks

cases.py is the exact set. Six actual complete helpers exercise text/binary/empty/
exit7/unicode input and a second fresh case while preserving the first. Producer
kill and recorder kill happen only after helper's exclusive READY file and raw
header/payload are observed; retain the actual kill command/PIDs/exit and prefix.
Parser/cleanup failure controls must throw in the test driver after raw is already
retained; disclose those seams, never fake a child/process receipt. An external
supervisor may retain interrupted incoming directories; no completed manifest.
Use finite5-second readiness/termination bounds, stop affected scope if unavailable.

Three fresh-path controls prove refusal/unchanged census, including traversal.
Fifteen corruptions mutate COPIES of an authentic completed positive: changed
stdout, truncated stderr, missing exit/input, stale finalized timing hash, wrong
argv/binary/source/input/nonce/PID, unlisted file, incomplete promotion, counts and
negative timing. For identity/count/timing semantic controls rebuild internal
hashes so a checksum failure cannot substitute for detecting the wrong identity
or arithmetic. Compare against the untampered externally bound request.
Four archive controls add an extra/duplicate/traversal member or truncate bytes.
Keep authentic originals, mutated copies, before/after census and actual validator
argv/stdout/stderr/exit. Synthetic selftests are labelled, not actual recorder runs.

## Publication and judgment

Run package selftest and verify SHA256SUMS. Publish method via ready Verification
PR/all normal CI/MERGE COMMIT BEFORE Software executable helpers/recorder runs.
Then return exact candidate/import/package tree/source/build/host identities and
all32 original helper/recorder/validator outcomes, full request/result/original byte
inventory plus interrupted raw. >1MiB uses immutable usable hash-pinned release
transport, retaining failures; no public machine trace upload. At most2CPU-hours/
512MiB per lead; individual/no subworkers. Stage1 remains OPEN for actual Stage2.

Independent Stage2 authenticates actual child and commit/cleanup/transfer behavior,
reapplies raw/identity/corruption predicates and decides explicit bounded OVERALL
standalone recorder PASS/integration permission only if all applicable component
scope closes. A green synthetic fixture alone does not qualify the recorder.
Two consolidated corrections max; exact final capability/method stop instead of
unchanged repeated work. C254/D255 new executions wait that independent clearance
AND their own method publication. B source tracing/E offline preparation may proceed.
No S1/fullAPP/native/physical/A6/HOST acceptance or widening follows. Ready actual
returns first; then next eligible issued252-256 task in this same activation.
