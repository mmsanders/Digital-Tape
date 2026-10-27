# Verification332 pre-code publication — PM593, 26 October 2026

Inputs: Product `9af79191671b4ce47732dc6cb3da269741ea5e4d`, Verification
`7731e29a5f6081140f013a8eb622fbae491d7c2f`; public Software594 declaration
[6425763463](https://github.com/mmsanders/Digital-Tape/issues/594#issuecomment-6425763463).
Authority: current APP-1A §8 and Verification332. No new594 implementation or private
tests were inspected. This is Stage A, not Product source acceptance or a native run.

`receipts.py` freezes schema1 field sets, ordering, identity, budget and capture
predicates. `--schema` prints the closed schema; `--input envelope.json` checks a
JSON object `{"files":{"relative-name":"base64-original-bytes"}}`; `--incomplete`
requires an incomplete result. It checks consistency, not authenticity. `cases.py`
freezes C01–C28 and command/parity oracles. Run both without arguments for pure
synthetic positive/causal-negative controls. No Product, child or UI is executed.
Import this whole directory byte-identically before covered implementation.

## Production binding and permitted controlled method

Use production `ingest_job::command` and `run_recorded`, and the SAME `Bridge`
admission/generation/serial worker/deliver/fail/cleanup path. Exercise `Session`
through its production creation/write boundary. Do not implement a second bridge,
capture pipeline or reference controller to generate expected traces. Tests may
call existing direct seams in a test environment; a controlled-test route is never
claimed to be a native gesture. The native callback currently enters Bridge directly;
record `native-event` there and `tauri-command` only in an actual command handler.
Correlate the boundary to its drop id. Do not insert an IPC event that never occurred.

After publication, Software594 may build/run its declared test-only harmless
`probe_child` through those seams on Windows11 using already available locked
tooling. It may read its OWN console association/PID/process creation time/argv/cwd,
write only owned fixture files and fixed stdout/stderr/report/known tiny output pair,
sleep for cancellation and return chosen0/2 codes. Behavior selection belongs in a
test-only owned fixture configuration, never a new production CLI flag or provider.
Record helper source/image hashes separately from the shipping INGEST pin. The
helper is neither bundled nor represented as the real pinned INGEST. No real INGEST,
app/native window, discovery poller, device command, observer or physical operation
is admitted by this method. No install/admin/security/ACL/policy change is admitted.

C01/C02 require original helper measurements: CREATE_NO_WINDOW yields null
GetConsoleWindow; test-only flag removal from a known console-attached runner gives
non-null. Preserve runner and helper identities and original metadata. A constant
assertion or mocked flag alone is insufficient. This controlled console-association
fact does not prove which old564 PID caused F328-1 or visible absence on a future app.

C03–C07 use success, refusal, missing executable, sleeping/cancel and shutdown cases.
Retain actual exit/wait, raw binary stdout/stderr (including non-UTF8/NUL/CRLF),
nonce-bearing report and known tiny manifest/audio originals in controlled harness
evidence BEFORE production cleanup. Independently hash those originals against the
Session copies, parse manifest frames and compare actual audio hash/length/frames.
The diagnostics session itself never copies audio/music. A killed child may have
null exit/no final report; retain available originals and mark missing facts honestly.
Spawn failure has no invented PID/wait. Cleanup still occurs after actual termination.

C08/C25 compare OFF/ON and sink-failure/healthy runs using the same fixture inputs.
`parity()` takes independently derived projections. Per-run random job path/nonce
and PID/timing may differ: first validate EACH raw invocation/report identity, then
replace only its proven own path/nonce tokens in the comparison projection and
hash the normalized report. Publish the exact normalization and raw hashes; never
normalize exits, streams, output bytes/frames, GUI state, cleanup or reaping.
Do not force reused nonce/randomness into shipping code just to get equal traces.

## Lifecycle and failure obligations

C09 requires exactly argv `[app,"--diagnostic-receipts"]`; absent, valued, duplicate
or extra-path forms are OFF. OFF must cause zero diagnostic filesystem calls, not
merely no surviving file. No env/config/UI/registry/build default. Existing four
child pin environment values remain unchanged; do not require a fifth build env
to identify source. A bound BUILD.json can supply source identity, otherwise null
is honest and incomplete. OS/arch constants are not OS build identity; a spawn-call
wall timestamp is not actual OS process creation time. Unknown facts stay unknown.

C10–C12/C26 exercise exclusive session/marker/record/blob creation, old/foreign
sentinels, occupied leaves and a controlled parent substitution at the production
boundary. Snapshot/check foreign bytes outside the logger. Initial symlink_metadata
then path-based write alone does NOT close the substitution race. Use a bounded
nonfollowing identity-bound creation/write capability or fail closed on replacement;
return a precise feasibility blocker if unavailable. No provider/security workaround.
Use ordinary permitted owned fixtures, not privileged link creation. Source review
and a controlled boundary substitution are required; a mock that only sets an
expected safety boolean does not establish production behavior.

C13–C20 cover stale generations, queued cancellation, rejected/no-change admissions,
capture ordering, malformed originals and unavailable provenance. All raw capture
happens after actual wait and before ordinary job deletion, with cleanup outcome
and stale-result decision retained. C17 compares source operation order AND actual
originals, not just log sequence. The same worker still runs with diagnostics OFF.
No cards-poll records are required; this exception covers the declared INGEST chain.

C21–C24/C25 require exact-limit and one-byte-over controls: JSONL UTF8 INCLUDING LF
<=65536 bytes per line, each raw blob <=4194304 bytes, total marker+records+blobs
<=16777216 bytes (directory metadata excluded). Account before write, reserve a
bounded best-effort incomplete record; never truncate originals. Inject create,
short-write, record/blob/footer and space exhaustion at the production sink boundary.
Stop collection once a sink failure occurs; never retry a child, alter its outcome,
skip reaping/cleanup or continue writing a seemingly complete trace. If even the
incomplete record cannot be written, the external harness records the failure;
absence of a valid complete footer is incomplete. A torn final line is invalid,
not a valid complete receipt. Preserve its original bytes outside the parser.

## Record rules and return

The marker contains schema/session. Each JSONL record has only schema/session/seq/
kind/data; seq starts0 and increments by1. Every work/pid/generation/blob link must
match. Only marker, records.jsonl and numbered report/stdout/stderr/manifest blobs
are receipt files. No copied audio or source music, arbitrary export or foreign
paths. The parser envelope is an evidence-transport representation, NOT a runtime
sink path or an export feature. Failed cleanup is an actual recorded result, not
silent success. Malformed report bytes remain byte-exact and make the chain
incomplete; they are never replaced by an expected report. Empty/rejected sessions
can complete without a child; admitted work needs outcome+cleanup or queued skip.

Unknown source/OS/app or child process identity, missing required capture or sink
failure cannot produce a complete chain. `incomplete` ends collection immediately;
a deliberately incomplete footer may retain earlier valid captures. The parser
does not validate every INGEST S1 semantic obligation: the existing published parser
corpus carries, and actual capture source review is still mandatory. S1 report
semantics are not replaced by this first-party consistency check.

Return one exact current-base two-commit import-before-code head, import tree/source
identity, normal CI, C01–C28 case-to-production/test bindings, commands/platform,
original helper/runner observations and raw capture hashes/immutable refs. Label
unexecuted cases; synthesized fixtures are oracle self-tests only. Two consolidated
correction responses maximum. Verification Stage B reviews actual production source,
controlled originals and CI before exact source clearance; Software owns integration.
585/325 ONE final build still waits for that cleared integrated source.

Future native admission separately needs final585 binary/archive/source/pins/OS/PID
identity and qualified actual controls. These receipts can correlate first-party
ingress/work/child/report/pair/cleanup with independently observed gestures, but
CANNOT establish G1/A4 whole-machine zero device/child attempts, failed/zero-access
own-HOST visibility, physicalA6/S3/fullAPP/G2 or an unobserved Show Details/NUL row.
Original564/328/331 stays partial and immutable. No Michael repeat is requested.
