# Verification352 Stage A: cards-1 and new612 candidate expectations

Authority: Product PM611 / Software612; Verification352. Product input
`a993ba79d32ebde232072485fd1c8b83a95690d5`, Verification input
`ed34966c909edb5c9e3aaa4bb753e84f6343152f`. Canonical AGENTS, CLAUDE,
STATUS and Verification charter read at that Product main. Public interface
declaration: Software612 comment6458235646. This package was authored before
inspection of any new612 implementation. Old source/evidence remains accepted
only by its original identity. This is tests/expectations READY, not source PASS.

## Interface ruling

Use the declared production seams. `receipts.py:FIELDS` is the frozen closed
cards-1 schema: existing schema1 envelope, session sequence, old INGEST kinds and
old data unchanged. One cards-contract immediately after session. The three
routine clarifications below complete the declaration; no further declaration
round is required before implementing this covered scope.

* Use separate `cards-blob` / `cards-missing` records, not old INGEST `blob`
  work IDs. Raw role names remain report/stdout/stderr. Preserve byte-exact
  originals, including NUL/non-UTF8 stderr. No reconstructed JSON as originals.
* `cards-publication-attempt` precedes the actual effect; `cards-publication`
  follows it with published/stale-dropped/failed and error null or actual failure.
  The state_ref binds the actual View/callback state, not an assertion that the
  UI displayed it. A missing result remains partial, never inferred success.
* A failed job creation has job_dir null and actual job_error, no PID/terminal,
  honest not-launched/publication, cleanup attempted=false/result=not-created.
  A failed resolve/spawn with an existing job has no invented PID/terminal;
  its real directory cleanup is attempted and recorded afterwards.

Run IDs cards-1..N and strictly increasing bridge tickets; no overlapping runs
through cleanup. Launch record immediately after spawn, before wait, from actual
Request/Ran and OS facts. Pin version is LABELLED as a pin. Observed version is
only the retained child report; no cached pin passed off as queried output.
The exe measured hash is actual at launch and compared to the build pin.
OS creation-time failure is null with incomplete evidence; never a guessed time.
OS wait/reap is distinct from kill/cancel request. Timeout/cancel is incomplete
even if a process exits0. Capture happens before removal; cleanup outcome is
recorded only after the actual operation. A failure/absence is not success.

4MiB maximum retained per blob,16MiB total session,64KiB maximum JSONL line.
Truncated records label retained bytes, original bytes, prefix digest and status;
they cannot make a complete footer. Missing/error records retain actual reasons.
The bounded sink's stop/incomplete path may leave only a valid prefix, or damaged
last bytes on actual write failure: preserve these privately, never promote an
unparseable receipt to complete. A stopped sink does not stop Product publication,
change cleanup policy, reschedule work, retry, or create a busy loop.
Cleanup after sink failure continues as it did before; do not fabricate an event
that could not be written. No new run cap or collector/scheduler is requested.

`validate` checks internal consistency against an independently supplied binding
(actual app/child/path/pin/private root). Synthetic fixtures do not authenticate
source, original files, OS observations, no-device-access or visible UI. Wrong
output from a child may be recorded honestly as incomplete; contradictory receipt
identities are rejected, even when someone labels the session incomplete.
It calls the accepted S2 report/stdout parsers, not a new discovery judge.

For mixed legacy/cards sessions, original full seq/session is checked first.
Only a validator projection strips cards records/leaves and resequences unchanged
legacy data for the untouched r2 validator. This projection is NOT retained
original evidence or native sequence authority. Raw full originals remain the
review input. No old r2 assertion is weakened or rewritten.

## Mandatory source/component acceptance matrix (next stage)

These are independent detecting obligations, NOT claimed executed tests. Software
imports this exact package first and adds cases in the existing harness. Return
source refs, invocation/exit/build logs, test list, hash-pinned controlled probe,
raw component originals, before/after file inventory and actual callback Views.
The reviewer independently inspects these and runs the exported offline oracle.
Self-reported booleans or a constructed typed trace cannot satisfy the matrix.

| Row | Exercise in existing component harness | Independent acceptance/failure detector |
|---|---|---|
| P1 wiring | Real production poll_once -> discover -> run_cards -> command/run with permitted harmless probe_child, real job dir, actual spawn/wait | Non-cfg(test) receipt calls, real PID/OS-start/argv/cwd/nonce/measured hash/flags, originals match external component artifacts. Changing/removing a production call must make the test fail. Never direct-inject cards events into Session to simulate this row. |
| P2 publication/capture/cleanup | Probe success, refusal/nonzero, resolve failure, spawn failure, create failure, stale publication | Bind actual returned/published View/state_ref, and returned removal outcome; originals retained before removal; failed launches have no PID. Inject effect failure in the existing seam and assert receipt failure/partial result, not only a note(). |
| P3 timing/stop | Existing timeout, cancel, invalidation, shutdown/join, refusal after stopped, late completion | Existing10s timeout, singleflight and2000ms-after-terminal schedule unchanged; actual reaped end distinguished from request, footer after join, no post-stop admission/publication. Use existing logical clock/barriers, no synchronous poll in production. |
| P4 OFF | Same real production wiring, opt-in absent, observable sink/file-call sentinel | ZERO diagnostic calls/files/dirs with defaultOFF, unchanged View/child pins/CREATE_NO_WINDOW. An ON-only export is insufficient. |
| P5 sink safety | Existing owned private-root harness: foreign/reparse root, existing leaf, blob/session/line exhaustion, write/read failure | Exclusive/no-overwrite, safe name, owned private root, no writes to foreign tree; original sentinel bytes unchanged. Actual errors remain bounded and reported incomplete; no Product result/cleanup/schedule change or loop. Repeat defaultOFF with failures armed. |
| P6 regression boundary | Existing retained INGEST record controls and source diff | No INGEST schema/data changes; no child rebuilds; accepted zero-access S2 implementation/pins, argv/results/UI text/order unchanged. note() remains test-only with no sink. No native app, S2 or INGEST execution. |

Old actual backend286/297 and Make299 evidence is carried, not rerun. P1-P6
controlled executions are COMPONENT facts only. No shell workaround, native
observer, app launch, scheduler force or real-card/OS inventory collection is
authorized. A source scanner alone is not a production wiring test. An integration
test may select a pinned harmless fixture via existing test seam; no shipping fake
flag or alternate production route.

## Candidate boundary

`candidate.py` is the NEW PM611/612 profile; existing candidate_r1/r2/archive files
stay byte-identical. It calls the accepted r1 byte/archive gate and explicitly
carries all r2 diagnostic guards. It does NOT lie to r2 with count=1. The old
PM593 single-build rule still applies to its own scope; PM604's old585 exception
is immutable. New612 allows1 or2 compilation attempts and exactlyONE uploaded
candidate, after source clearance/protected integration. No successful extra
reproducibility build, third attempt, or child rebuild. Record every attempt's
times/source/clearance/integration/log/exit/artifacts (including failed artifacts),
and normal CI builds separately. A second failure or material functional scope
change is a blocker. No count1 claim after count2. Compare metadata to actual
workflow/command logs and retained artifacts; metadata alone cannot establish
that no omitted build exists.

Keep the closed five-member ZIP, unchanged authenticated INGEST3895f3f3 and
S2 tapectl44ef2686, new actual app/source/README hashes, external inventory/test
sheet. Packaging judge checks bytes only, no payload execution. Final native
method/launcher/human kit may be prepared against actual new hash later, but no
runtime grant here. Preserve original564 partial clips/ShowDetails/NUL/launch and
F328 PID limitations, old STOPs, native/session/A6/INGEST/fullAPP/G2 holds.7/12
remains. First-party receipt availability is not independent G1 absence proof.

Run `python -B tests/windows_cards_receipts_r1/controls.py` and `candidate.py`.
All local controls are synthetic/offline; no Product source or binary runs.
