# Verification235 Stage1 — six harmless observer visibility controls

**AUTHORING ONLY.** Six synthetic neighbours and27 detecting mutations qualify
the method's decision checks, not actual Windows calls or observer capability.
Software491 implements the test helper only after this package is merged on
Verification main. This package makes no native calls and inspects no newly
uncovered Product implementation. Stage2 remains pending one bounded fresh run.

Authority PM490 / live235 (updated2026-10-20T20:40:47Z), paired Software491.
Required four onboarding documents/live issues read. Issued Product input
b8fa545bbef5a95766ca2da36ed66b82ee13a79c; activation main
5dac551313c011262aa1b6c57b3584a23fab63b1; Verification input
aba3ce314cd31bbaad254c1d956552b56d3b91ad. Individual lead/no subworkers/GitHub only.

## Retained observer preflight and adequacy

Existing retained230 packet is the original198343663-byte archive SHA256
e6d3f2b9e60e93bc90a7516e66418da301c4c0dc3a306dfea3e1394a81731ff3.
Read retained config/platform/filter, existing observer lifecycle/filter code and
prior independent230/234 limits; no Product audio/engine code was opened.
PINS.json records exact retained hashes. Installed Procmon64.exe is version4.12,
SHA25628495e642b2a465474a4edc58380eaf8b7ee580f3fbcb4141061deadafe9b885.
Existing296-byte filter.pmc SHA256
6bc51ab36ed855ef86a903808d899ab349827122db04b7e0bb13fe285adc2f74:

- include Process_Name is ingest.exe OR begins_with probe-;
- exclude Registry, Network, Profiling event classes;
- DestructiveFilter=1 (excluded events cannot be recovered from this capture).

Retained observers.py SHA560cc9a5 and collector74e1af2c are unchanged. Existing
probe covers successful ordinary/child/create and a prior successful device open;
it does not establish failed or desired-access-zero coverage. Its four damaged
trace controls and230 CSV reconciliation carry, not universal absence. Existing
PML/CSV alignment is a producer claim checked at CSV level, not independent PML
decoding. This package adds just the missing six-row visibility method.

Preflight must authenticate the existing executable/config, tool version, local OS
edition/build/architecture, export commands and capture categories; record current
privilege/context and differences. Use existing authorized capability only. Missing
privilege/tool/config is a concrete stop, not an elevation/install/security request.
Do not launch a second capture over another owner's session or terminate unrelated
sessions. If safe exclusive ownership cannot be established, stop.

Name the isolated helper **probe-235.exe**, already admitted by the unchanged
filter. Record its source/binary/build/dependency hashes; it is not the real kit
probe or shipping executable. Use an independent private directory; never overwrite
any old probe/kit/receipt. Do not run old observer selftest/run_packet/start(): those
can copy/run other probes and exceed this scope. The test-only driver may use the
same existing Procmon CLI lifecycle with a byte-identical copy of filter.pmc:
LoadConfig/BackingFile, WaitForIdle, one short capture, owned-session terminate,
OpenLog/SaveAs CSV. Preserve actual commands/exits/timeouts/logs. No new observer,
collector, export parser, PML decoder, tool/provider search or configuration change.

## Fixed native calls — exactly once per case

Create an owned ordinary local fixture file and a separate foreign sentinel before
observation; close setup handles. Prove file bytes/hash and no symlink/reparse or
shared/network path. Reserve one nonexistent child pathname under that same private
directory without creating it. Generate one32-hex random nonce; use a single exact
DOS name `DTVerify235_<nonce>`. Before capture, QueryDosDeviceW that NON-NULL exact
name once with a fixed4096-WCHAR buffer; capture returned DWORD and immediate error.
Zero return plus ERROR_FILE_NOT_FOUND(2) establishes the selected absent-name
premise. Any mapping, other error or insufficient buffer stops, with no enumeration,
regeneration or retry. Do not call QueryDosDeviceW(NULL) or DefineDosDevice.

Every case: CreateFileW with share READ|WRITE|DELETE=7, NULL security attributes
(no inheritance), OPEN_EXISTING=3, FILE_ATTRIBUTE_NORMAL=0x80, NULL template.
No backup/overlapped/delete/reparse flags. No data I/O through any returned NUL or
device handle, no read to make a positive. CloseHandle exactly once only for a
valid owned returned handle. Fixture setup/hash readback is ordinary-file activity
outside the six target call intervals; it does not add a device operation.

| Case ID | Exact target | dwDesiredAccess | Intended neighbour |
|---|---|---:|---|
|file-read|absolute owned fixture pathname|GENERIC_READ=0x80000000|successful file open|
|file-zero|same exact owned fixture pathname|0|successful zero-access file open|
|missing-read|the reserved absent owned child pathname|0x80000000|OPEN_EXISTING refusal|
|nul-zero|literal `\\.\NUL`|0|successful zero-access NUL open|
|nul-read|same literal `\\.\NUL`|0x80000000|successful NUL read-access open, no ReadFile|
|absent-dos-zero|`\\.\DTVerify235_<nonce>` after exact-name absence check|0|absent-name refusal|

These are intended neighbours, not fabricated OS outcomes. Actual CreateFileW
return determines success: HANDLE != INVALID_HANDLE_VALUE (all-one pointer value);
failure is INVALID_HANDLE_VALUE with GetLastError captured IMMEDIATELY before
logging/timestamp/close/other APIs. GetLastError after success is not an outcome
oracle. Record pointer width, raw unsigned/hex handle, exact UTF16 path and every
numeric parameter, PID/TID, per-process instance key, before/after timestamps,
native error and CloseHandle parameters/result/error. Helper stdout is raw facts,
not a PASS label. A differing actual OS outcome is retained as incapable for the
intended neighbour; no burst/retry to obtain a preferred result. Missing-name
refusals normally yield2/3; another error is still an actual call but cannot serve
as the intended absent-name neighbour. No attempt is inferred from a label alone.

Use six short sequential helper process instances, one target CreateFileW each;
each command carries exact `<nonce>:<case-id>` marker. No PID reuse is permitted
for this single experiment; if it happens retain it as a binding stop, do not rerun.
Capture helper/native source and actual binary and inspect implementation only
against these already-authored expectations. Record launch PID, image path/hash,
parent, start/end, child exit and complete stdout/stderr. Use native FILETIME/QPC
brackets for calls and process lifetime; preserve clock frequency, UTC/local offset,
date, precision/resolution and conversion evidence. Event time intervals represent
known original precision, never a widened post-hoc search window. Clock ambiguity
or unmatched lifetime is a held binding, not nearest-time matching.

Native API semantics are grounded in Microsoft
[CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew),
[QueryDosDeviceW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-querydosdevicew)
and [last-error semantics](https://learn.microsoft.com/en-us/windows/win32/debug/last-error-code).
Zero desired access still attempts an open. An explicit exact-name metadata query
is not a license to enumerate physical-device names or open a physical positive.

## Independent native/observer correlation and loss

Ground-truth helper facts and observer events are separate inputs. For each case,
retain the entire selected helper process-instance row census, including Process
Start/Exit and all CreateFile/reparse/close rows, not a grep of successful opens.
Process Start must carry exact nonce/case/image/PID; Process Exit must establish
actual helper completion. Bind PID reuse boundaries and descendants explicitly;
no basename-only ownership, filename/time proximity or fabricated parent relation.
Retain every original global CSV record index and hash of canonical parsed row
fields (sorted-key UTF8 JSON, no omitted fields), complete header/global row count,
global CSV SHA256 and PML SHA256. Bind extra/duplicate/unattributed rows and every
selected index exactly once. Do not synthesize a process start from a call log.
Kernel cleanup rows may follow Process Exit: retain them under the original
instance until capture end/next authenticated Process Start, while call/open
events themselves must fit the actual live process interval. `ownership_end`
records that independently established cleanup boundary, not a widened call window.

Match the one issued target call to exactly one terminal CreateFile outcome after
any retained REPARSE records, with matching process instance, target identity,
overlapping genuine timestamp brackets, observed disposition and desired-access
Detail. Ordinary paths must match the exact owned path. NUL may be displayed as
`\\.\NUL`, `NUL` or `\Device\Null`; retain original strings and justify this exact
alias map. For the generated absent DOS name, preserve the unique generated token
and exact observed path; no fuzzy suffix/drive remapping. Other alias transforms
or multiple terminal events are a held correlation pending the single allowed
method correction, not automatic acceptance.

Read access expects observed Generic Read/Read Data and no write data; zero access
must not be mislabelled from a read-data event. Windows may add implicit metadata/
synchronization rights: preserve the actual Desired Access detail. The native
requested zero is authenticated from the helper and attributed call, not inferred
by treating every Procmon textual right as the literal Win32 mask. Missing detail
or unresolved mapping is incapable. Native success must agree with observer
SUCCESS; native2/3/5/32/123 errors have explicit NAME NOT FOUND/PATH NOT FOUND/
ACCESS DENIED/SHARING VIOLATION/NAME INVALID equivalents in oracle.py. Unknown
result translation stays held, never inferred from a generic FAILURE string.

Require native loss/status/count evidence from the existing tool/config plus full
selected-PID census/start/end coverage. `accounted_no_loss` requires cited actual
tool counters/status/session evidence and explanation of their scope. Merely no
warning, sequence-contiguous selected rows or equal PML/CSV counts cannot prove
zero capture loss. If the existing tool cannot expose sufficient accounting, mark
loss unknown and the capability HELD; do not add another provider/tool or decoder.
Collection/export/truncation problems stop. A missing terminal event for a proven
attempt is **INCAPABLE/HELD**, not evidence of an absent open. An ordinary-file
positive does not rescue a failed/zero-access row that the observer cannot see.

## Runnable package and actual-return contract

`python -B tests/wp16_observer_visibility_r1/selftest.py` runs six synthetic
neighbours and27 dropped/misattributed/wrong-mask/outcome/native-fact/process/
nonce/time/loss/config/census controls. No helper or capture executes.
`selftest.positive()` documents every normalized schema1 field consumed by
`oracle.py INPUT.json --out RESULT.json`. Software supplies the same finite shape
from actual facts, with raw source references and raw provenance alongside it;
the synthetic fixture must never be presented as actual evidence. No literal
synthetic digest/marker/handle may stand in for a missing actual field.

The oracle's `OBSERVED` is a preliminary finite normalized result, conditional on
independent raw/source/native authentication. Its top-level output permanently
leaves retained-candidate absence, physical-device absence and independent PML/CSV
proof false. Stage2 independently reconstructs normalized fields from raw helper
records and private CSV, audits every logical-target/image/time conversion and
row hash/index, inspects returned helper source/binary/parameters and applies the
published judgments. Caller-supplied hashes/booleans or a Software PASS label do
not authenticate themselves. Missing actual field is malformed/binding failure;
known invisible/uncorrelated primitive is incapable, not absent.

Return helper source/binary/build command/dependency pins; exact imported package
commit/tree/files/SHA256SUMS; six raw native stdout/stderr and launch receipts;
full numeric native parameters and handle/error/close facts; exact observer/config/
OS/privilege/commands; selected row indices/canonical hashes/complete PID census;
clock conversion, target-alias map, loss/count evidence; fixture/sentinel hashes;
and actual scope/resource accounting. Retain originals privately and provide
accessible local paths to Verification, plus SHA256/bytes for full CSV/PML. Bind
bounded public relevant control events and anonymous target/process fields to
their exact original indices/hashes with an explicit redaction map. Do not publish
full-machine traces, environment blocks or personal paths. Public normalized data
alone cannot substitute for unavailable private raw access. Original raw >1MiB
stays outside Git; approved bounded public transport needs stable URL/size/SHA256
and complete member inventory. PML/CSV correspondence is not independently claimed
without proof; no new decoder is authorized.

## Proposed criterion mapping and stop

All six primitives plus required correlation/loss facts observed permits only the
exact observer/config/OS and these finite file/NUL/absent-name capabilities. NUL is
a null device and the generated absent DOS name a namespace refusal surrogate;
neither establishes behavior of real raw physical devices, volumes, cards/readers,
all refusal modes or all desired masks. Even identical observer/config/OS cannot
retroactively add missing call classes/ground truth/loss accounting to old230.
Retained capture596k CSV facts/234 resource/1640 byte identities carry unchanged.
If otherwise capable, the smallest potential next step is PM-authorized exact-
candidate observer application with established scope/identity, not a new run in
this tranche and not a full1927 collection. This package cannot clear old459 absence.

One short capture; six target native cases plus necessary ordinary fixture/process
markers;2CPU-hours/512MiB cumulative NEW compressed evidence. No retry after tool/
privilege/config or repeated primitive incapability. Stage1 publishes ready PR,
normal green CI and merge commit, with exact source/tree/hash transport to491.
Leave235 OPEN Stage2 pending actual return. Stage2 returns bounded capability or
precise blocker with one evidence-grounded next-method condition to491/490/459,
publishes through the same process, and closes at stop. At most one consolidated
method/binding correction after first substantive return. No physical/card/network/
other-user-file opens, NUL/device I/O, observer/collector/Product changes, alternative
provider investigation, install/security/human task, new candidate run, audio/
exhaustion/global-S1 replay or broader WP16/APP/S3/G2/A6/Mac integration clearance.
