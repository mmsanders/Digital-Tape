# PM510 Software read-only preparation

21 October 2026 PDT. Product main192fed8cf1f367899db3c9ed967f5c4d1d898dec;
Verification maine6bc7b87dab9d3620c3a018125cb7b404bca8c31. Individual Software
Lead, no subworkers. Required canonical four and live511–515 directions reviewed.
This is an inventory/source trace and cost-planning input, not implementation,
an independently authored method, executable proof, acceptance or a new run.
At intake none of paired252–256 had a method-publication comment or a new merged
package on Verification main. Import the exact future publication before work.

## A /511: existing recorder failures and concrete correction boundaries

Exact inspected transports: Software499 evidence69075205a31a2cbea4f00e142bc8b65d3437091c;
Software500 tested55d1bdde94d0e14abcc82e62628b8c344e609c5d; Software501 tested
6c5756bffdf8ed6a0ae37c9ea68f92333afb368a. No old commands were rerun.

499 `tools/software499/run.py:35` captures a process into memory and asserts its
exit before adding a command record. It writes all command evidence at loop end;
an earlier exception can therefore prevent accumulated command publication.
Its line65 creates SHA256SUMS.json inside the process timed by workflow499 line34:
external `/usr/bin/time` finishes run-time.txt only after that process exits.
Consequently the inner checksum can precede final timing bytes. The original
stale checksum remains preserved; the later authenticated outer inventory stands.

500 `tools/software500/run.py` rejects an existing run root, but native output is
followed by report parsing and assertions outside its later validation try/except.
PROCESS.json/LEDGER.json are written only after those steps. The actual first
endpoint-1 run's reader exception plus tee/final-upload failure lost original raw.
The corrected Decimal/pipefail/always-upload path does not make each individual
case an independently finalized immutable commit. Lost endpoint-1 remains zero
usable credit; no reconstruction or retry is authorized.

501 `tools/software501/run.py` uses put-if-absent/same-bytes and per-command raw
files. This is useful prior art, but PROCESS follows child completion, outer
LEDGER is rewritten, and terminal inventory/archive exist only at driver end.
Exceptions can leave a partial directory requiring explicit incomplete status.

Proposed implementation boundaries for the forthcoming independent protocol:

1. Exclusive case-ID reservation before child launch; reject duplicate/reused paths.
2. Write raw stdout/stderr directly to newly opened files before parsing or judgment.
3. Persist planned argv/input/binary/source identities before launch; retain actual
   exit and final timing only after process/writers close. No external writer may
   change an inventoried file after case completion.
4. Keep interrupted/incomplete cases as such; never manufacture a completed receipt.
5. Bind finalized bytes and counts, verify the closed inventory, then publish the
   case through one filesystem operation. No host power-loss durability claim.
6. Archive only frozen bytes; compare closed member set/size/hash after archive
   creation and after transfer. Retain originals before any cleanup.

The independent252 protocol must choose the concrete schema/API and >=25 finite
helper/control cases before this is implemented. No helper has been executed.

## B /512: narrowly identified constructor chain, not a discharged lemma

Source S1b9f430c8c9b33532abf07eea0ed2653310639f2d, ingest tree
835078995d4e9cc2424f9ea8d6f11304b45f783f. Prior239/25b20d95 conditional copy/count
arguments carry; no repeat of its25 rows or claim about other numerical gaps.

Candidate six necessary new vendor functions for the independently issued scope:

| Function | Exact source location below host/ingest/vendor/ |
|---|---|
| AudioBuffer::new | symphonia-core/src/audio/buf.rs:80 |
| MpaDecoder::decode_inner | symphonia-bundle-mp3/src/decoder.rs:85 |
| MpaDecoder::decode_ref | symphonia-bundle-mp3/src/decoder.rs:157 |
| AacDecoder::try_new | symphonia-codec-aac/src/aac/mod.rs:62 |
| AacDecoder::decode_inner | symphonia-codec-aac/src/aac/mod.rs:251 |
| AacDecoder::decode_ref | symphonia-codec-aac/src/aac/mod.rs:284 |

AudioBuffer::new computes C from spec.channels().count(), creates planes with
resize_with(C), and stores the same spec. The fields are private. MP3 first-frame
decode_inner replaces an unused buffer with AudioBuffer::new(header.spec(),1152);
later frames reject unequal buffer/header spec before success. AAC try_new builds
AudioBuffer::new from its admitted ASC channels; decode_inner clears/renders the
existing buffer. decode_ref exposes the buffer only on successful decode_inner.
Read-only trace suggests the missing bridge is constructor plus preservation,
not merely the already-checked metadata channel count. This is still a proposed
source correspondence pending exact independent admission/stream-change controls.

Callers mpeg.rs:334–337 and aac.rs:163–166 check frames/spec then copy vectors.
Existing num_planes/copy bridge from239 remains conditional until253 disposition.
Do not promote impossible mutated private-buffer states to admitted codec inputs.
No new fixture binding or executable proof helper has run; <=8 existing fixtures
and the final exact six-function boundary must come from the published method.

## C /513: concrete source entry points, execution held

Same S1 source: dsp.rs TP_PHASES:257, TP_BLOCK:259, TP_HALF:262;
TruePeak::at:296, grid4:321, peak_range:357, peak_streamed:394;
convert.rs:81 peak bound,90 linear gain,91 quantize,95–96 refinement update.
These locate support/grid/block-coordinate and gain-precision obligations.
They are not a transfer proof. Retained17-case archive remains unchanged with
260 closed files; no new shipping CLI execution or recovered endpoint-1.
254 must preselect <=3 already-usable inputs and independently prescribe actual
function/intermediate bindings and phase/offset/reset/rounded-substitution controls.
New instrumented execution waits both254 publication and252 recorder clearance.

## D /514: measured cost input, not a self-issued schedule

Authenticated approved Software501 ZIP remains3370251bytes SHA256
eb7fcf40f00e3ad0201657ccae88016b8705b6ca0877d496fe6dbf1b16730db7.
Reading its original LEDGER.json gives:

| Original new row | CPU seconds | Original model orders/distinct projections | New compressed bytes |
|---|---:|---:|---:|
| write19 | 10.836652 |16/16|143620|
| write63 |181.035610 |256/256|1571288|

Both rows were already independently disposed by241/e6bc7b87; no invocation here.
Original archive has829 process records; the independent breakdown is one provision,
three loads and825 cold readbacks. New native errors and positive alone therefore
do not explain total cost: each new distinct projected image incurs complete cold
verify/dumpA/dumpB capture, PCM/state checks,32MiB materialization/hash operations,
and compression/inventory. Enumeration and order-digest work also scale with the
original landing-order model even when image effects can be deduplicated.

The old fixed120-second reservation did not account conservatively for this growth:
write63 has16 times as many projections as write19 and ~16.7 times measured CPU.
Observed ratios are ~0.6773 and0.7072 CPU-seconds/projection, inclusive row work;
they are observations, not a worst-case bound or permission to rerun for timing.

Planning suggestion for255 to independently accept/reject: reserve120 seconds
fixed row overhead plus4 seconds per original enumerated order (not merely unique
projection), with separate host/build/positive/packaging reserves. At <=256 orders
this is1144 seconds/row; four such rows plus600 build and240 positive/packaging
reserve would be5416 seconds before any new execution, below7200. This deliberately
large empirical margin is NOT a proven runtime bound. The independent method must
account for the selected coordinates' complete original history, order generation,
all required cold commands/controls and evidence costs before issuing <=4 rows.
No bound is claimed for a coordinate with greater enumeration or unbounded work.
If no credible conservative plan fits, return that result without a fault run.
First actual per-row overrun stops before the next row even with global slack.
The oldremaining23 stay unexecuted; accepted41/404 is unchanged.

## E /515: prior capability record, preparation-only boundary

Read only existing software491/README.md and RUN-STOP.md at14cad0b. Prior236 method
9991eded2ca2892f436088241848a55de4d31b88/tree944df7d2 remains historical authority;
the new256 kit/readiness method is a separate unpublished dependency at intake.
The known Python native-FFI/probe-235.exe route was not declared impossible by491:
it was never implemented after the independent observer-privilege prerequisite
stop. A buildable named helper would not supply missing capture authorization.

Future kit must preserve probe image/runtime/source/dependency/ABI identities and
the exact Procmon4.12/filter pins in515, owned-file/NUL/verified-absent-name allowlist,
private session receipts/cleanup, and explicit NOT AUTHORIZED TO RUN commands.
No token reprobe, QueryDosDevice/CreateFile target call, observer launch, compiler
retry/repair, provider hunt, capture, elevation, physical path or human collection
instruction occurred. No new kit implementation/synthetic executable validation
before256 publication. Old six native cases remain unexecuted/unqualified.

## Current next owners

252–256 independent method publication is the dependency for uncovered work.
511/512/513/514/515 remain OPEN. This preparation consumes no native/audio/fault
case budget or correction return and supplies no independent acceptance. No new
scope, engine/format change, whole459 consolidation or Phase2 rung gain follows.
