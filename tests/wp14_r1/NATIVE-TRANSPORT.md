# Mechanical native binding — Software #392, final authored protocol

Use the verifier-owned request/response runner in native.py. Expectations stay
in Verification; transport launches real binaries, creates only owned virtual
targets, captures observations and retains raw artifacts. It supplies no verdict.
Do not use physical user disks. No image substitute for a native device request.

Invocation: TRANSPORT [ARGS...] request.json response.json.
native.py adds --head identity and a persistent --evidence-dir; capture all raw
files there or other durable artifact paths, not the temporary backing directory.
Head/binary/OS build/provenance mismatches and unrelated process failures cannot
count as killing a mutant. No applicable case can be skipped.

## Inputs/setup

Each request carries case, command, platform, backing, target_bytes, facts,
binary_kind, erase_matches, control, independent expected fields, and optional
fixture/roundtrip/source/label_seconds/new_uuid/new_epoch/new_label.
request_sha256 is SHA256 of sorted-key JSON before adding request_sha256.

For normal cases freshly provision a 64,000,000,000-byte sparse native target
and load quiet audio where needed. Linux: actual loop, eligible ONLY via test
facts. macOS: hdiutil raw device. Windows: 64 GB virtual drive, not the old 8GiB
VHD. Production virtual/loop refusals use the shipped binary without test facts.
Probe uses actual platform facts without TAPECTL_TEST_FACTS, not injected facts.

Fixture requests contain a complete verifier-built whole image at target_bytes.
Bind its exact bytes without reprovisioning; the small mirror/geometry is truthful.
All layout/empty-table/engine corruption is authored in prepare(), not the adapter.
For roundtrip and capacity requests source points to verifier-owned WAV bytes
with source_sha256. Honor label_seconds. Roundtrip requires real detach/reattach,
then both-side dump, native NULL dump traces, and preserved output files.
Return dumps={A:path,B:path}, dump_traces={A:trace,B:trace}, and reattached=true
only with actual detach/reattach raw records. For native-exact-MBR-FAT-OS-README,
return an authenticated sparse snapshot of target_bytes, os_readme containing
read_via='native-filesystem', actual volume_label/path/content_hex, and a separate
successful post-provision verify_trace/verify_exit/verify_output. This proves
both sides mount after that provision, not merely during a later unrelated case.

Facts map only to issued keys whole/removable/sd_bus/bytes/holds_os/layout_ok and
repeat mounted=partition:where. foreign_mount means a mounted foreign entry;
mounted=['1:owned'] means an actual mounted own P1, using its real mount path.
virtual is a real setup/probe state, not a new facts-file key. Empty facts means
an empty test facts file with refusing defaults. Match --erase only when requested.
Never inject facts into production or ordinary images. Actual probe/OS mount/read
artifacts must prove the binding, not only self-reported booleans.

## Response and raw observations

All responses: case, platform, head_sha (40 lower hex), binary_path,
binary_sha256 (actual binary hash), os_build (exact native OS build), request_sha256,
capture_origin='native-candidate', control_applied (requested profile or null),
capture_artifacts=[{path,sha256},...] (all files persistent, verified by runner).
Also exit/stdout/stderr and trace, except symbol-tool cases. Include actual build/
compiler/configuration, command argv, source build identity and capture setup in
raw artifacts. Resolve Software's raw short build ID to the authenticated full
head; a dirty mutant build additionally requires exact patch/build provenance.

Symbols: authentic native symbol output in symbols, symbol_tool_exit=0. The
shipped binary must omit all advertised symbols/config strings; test build must
contain all as the causal red control. Never replace failed/empty tool output with
invented symbols. The inspection binary itself is hashed before any control verdict.

Trace fields: operation, platform, target_kind='device', target_bytes, success,
events in actual order; refusal/exit=3 for refusals; engine_used=false only when
no engine call occurred (policy/probe/unsafe layout/NOT_PROVISIONED/LBA0 failure).
Events:
- open/write_open (actual OS opens, including failed attempts);
- write: absolute whole-target offset/bytes, issued_before_return, coalesced,
  actual payload data_hex or payload_path/payload_sha256/payload_offset when
  provision replay needs it; never a reconstructed expected payload;
- read: actual absolute offset/bytes/success; phase, side/frame and
  referenced_chunk for service reads/faults. Capture ordinary reads for A6;
  bind/block_count alone does not prove a >4GiB mirror access;
- flush: success (reported), os_success (native result), os_call. Raw macOS
  fallback requires actual fullfsync_unsupported='ENOTTY'/'ENOTSUP' observation;
  never manufacture this cause from the fallback's name;
- engine_bind: literal write_is_null, base_lba, blocks;
- engine_mount: actual side A/B, cold and returned result;
- engine_info: actual side, needs_repair, side_b_valid.

The last two and service read context are mechanical observations at existing
public API call sites, not new engine behavior/instrumentation. Retain raw
wp14-trace-1 plus any additional authenticated capture. Normalization only renames/
joins actual observations; it cannot invent absent reads, error causes or API calls.
A failing mount is not subsequently serviced; closed findings match real engine
observations in table order. LBA0 failure is IO, never fallback/mount.

## Controls

Direct advertised profiles: noop-flush, hidden-flush-error, nonnull-binding,
read-error:2048. They mutate the actual test binary at the observed port/binding.
Known chunk0 fixtures require full-read errors A and B frame0, not mount faults.
No-op and hidden-error controls report success; non-NULL clean commands run
successfully even when they write nothing. An unrelated process failure cannot
kill these controls.

Additional native-flush-error, unmount-error, target-read-error:0 describe actual
test-only OS failure setups: return a real failed native barrier/unmount/read at
that boundary and capture propagation. Software may bind an external syscall
fault setup or test-only shim; preserve exact setup/patch/OS result. These are not
production CLI commands nor permission for engine changes.

A4 controls are actual isolated forbidden-facts cases paired with repaired cases,
rather than preliminary invented guard-bypass mutations. A5 controls are actual
corrupted fixtures plus clean/standby counterparts, not finding-suppression code.
MBR order is checked on captured writes; no-op provision is its durability control.
Independent reordered/missing-barrier transcript controls self-test that oracle.

## Provision interruption replay

provision-interruption-capture uses the supplied truthful small old image.
Preserve an exact pre-command baseline copy, matching baseline_sha256; do not
reprovision the seed first. Invoke provision with new_uuid/new_epoch/new_label
and label_seconds. Return baseline and final_snapshot paths plus the full native
write/flush transcript and replayable authenticated payloads. This is not a model
or an expected journal supplied by Software.

Verifier replays every actual successful flush epoch using none/all/first/last
pending writes, compares the fully replayed state to the actual final snapshot,
and dispatches child replay-* verify requests on native owned devices. Bind exact
snapshot bytes, without reformatting/reprovisioning. Old/new must cold mount;
zero-MBR devices must be NOT_PROVISIONED with no engine mount. New FAT/README is
checked independently. Dynamic case census comes from actual legal flush count.

This is representative destructive-provision outcome verification, not an
exhaustive any-subset WP10 qualification or media-atomicity proof. Real pulls
remain Michael's held physical work. Windows Server2025 remains supplemental.
All static cases, candidate controls and generated replays must run at the final
imported/bound head before software PASS. Raw assets over 1MiB go to CI/release
storage with hashes, not source-tree commits.
