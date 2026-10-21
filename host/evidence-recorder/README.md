# Immutable helper-process evidence recorder

Software511, standalone Linux/Python3 component. Import of independently merged
Verification252 method precedes this implementation. No engine/Product behavior
changes. This component records the frozen helper protocol; it does not claim to
validate arbitrary programs' domain semantics, power-loss durability, native
observer behavior or other platforms. Independent acceptance is pending.

Run `python3 -B host/evidence-recorder/recorder.py record --root /owned/run
--request /owned/request.json --input /owned/original-input.bin`. Request schema is
the independently imported tests/evidence_recorder_r1/README.md schema. The child
argv is absolute Python executable, `-B`, exact helper source, then its flags.
`--input` in child argv must name `/owned/run/incoming/ID/input.bin`; after commit
the original argv stays as launched, and its bytes move intact to `cases/ID`.
Source commit identifies the exact helper/recorder build snapshot. Requests remain
external immutable expectations for subsequent validation.

`validate --root /owned/run/cases/ID --request /owned/original-request.json`
checks closed file inventory, external request/launch/input identity, actual child
header, helper protocol streams/exit, finalized timing and result counts.
`archive-validate --root /owned/archive.zip --request /owned/expected-inventory.json`
checks closed ZIP member names, duplicates, hashes and external inventory.
Success exits0; refusal/incomplete/validation failure exits2 with error on stderr.
Child exit7 is recorded as complete failed-child evidence, never a test PASS.

The run root has an ownership marker and permanent exclusive `reserved/ID`
tombstones. Existing IDs/paths, traversal and symlink/reparse path components are
refused. Raw streams are direct files from child launch. Popen.wait completes,
writers close, exit/timing finish, result parses and all bytes hash before the
case directory rename. The exclusive reservation serializes cooperating recorder
processes for an ID. The owned directory must not have an adversarial concurrent
writer; this is ordinary-process commit behavior, not a security primitive or an
atomic no-replace theorem against arbitrary external filesystem mutation.

An interruption keeps raw under incomplete; an externally killed recorder can
leave incoming, which a supervisor moves byte-for-byte to incomplete. Do not
repair, retry or promote that ID. Do not proceed after an unresolved failed commit.
Case validation rejects absent/changed manifest, identity, stream or timing facts.
This protocol's exposed `--test-seam` options are test-driver failures AFTER actual
raw retention: kill-producer, parser-raises and cleanup-raises. The production
recorder performs no raw deletion; cleanup-raises simulates a caller's cleanup
exception before publication. Recorder kill is an actual external supervisor kill.

CPU timing is the recorder's process_time_ns plus Linux RUSAGE_CHILDREN user/system
delta after wait, including child descendants accounted by wait. Wall timing uses
monotonic_ns separately. Concurrent unrelated child processes within a recorder
instance are unsupported. Incomplete records lack final timing and are never
presented as complete. Test-run budget adds600 seconds of build/supervision reserve
plus elapsed wall times logical CPUs, including the interrupted child; actual
host/runtime/compiler/source identities travel with the original return.

`run_method.py --source EXACT_COMMIT --out FRESH_ABSOLUTE_DIRECTORY` runs the frozen
32 cases once. It retains original requests, child/recorder/validator argv and
PID/streams/exit/timing, interruption receipts, censuses, original positives,
mutation copies/recipes and original/mutated ZIPs. It never calls the independent
oracle to construct actual results. Independent byte predicates run only after
retention. Original failures remain outside any later corrected attempt. No
shipping CLI/audio/codec/native/fault execution is part of this runner.
