# Verification255: revised four-coordinate conservative schedule

PM510 / Software514, independent authoring only. Carry241 merge
e6bc7b87dab9d3620c3a018125cb7b404bca8c31:41/404 accepted,363 UNEXECUTED,
including23 old-selected and340 other coordinates. Write19 and write63 actual
10.836652/181.035610 CPU seconds are NOT rerun. Prior stop BEFORE write64 was
correct: old flat120-second estimate underestimated the256-order/projection row.
It used a32-fault aggregate/complete-route cost without the exponential active
epoch subset count and825 actual fresh verify/dump readbacks across the return.
Actual272 model orders/projections,825 readback records (including positive) and
829 total command records are evidence, not a uniform per-fault cost theorem.

## Fixed narrow rescope and structural cost

PLAN.json fixes NEW coordinates in this order: write64, write346, write351,
barrier50. Each is still unexecuted in the original missing404 list and was in
the original frozen25 selected list; none of accepted41 is repeated. Late rows
cover index and last-precommit superblock/flush neighbourhoods. This is the
explicit <=4-coordinate exception, NOT resumption of the old23 or a repeated-LBA
epoch/full campaign. No long-copy cuts, Tier1/2 or extra rows from budget slack.

Read-only count from immutable BASELINE shows exactly ONE active512-byte write
in the epoch after the last successful barrier at each selected cut (including
the failed write attempt; barrier50 has the preceding successful write). Original
any-subset model has exactly2 order classes and <=2 distinct projections here.
Original setup/full history remains mandatory, and prior successful barriers
establish durable state as before. Enumerate original model, never force2 by
dropping setup or failed-write eligibility. If actual history differs, stop at
method mismatch; no guessed state or reduced oracle. The old write63 active8
distinct-LBA writes produce256 classes, explaining its higher measured cost.

Reserve600 CPU-seconds/128MiB for build/mechanics and60seconds/16MiB for at most
one fresh ordinary no-fault positive matching405 route events,353 writes/52
barriers. Per selected row reserve120seconds fixed overhead PLUS6seconds for
EVERY possible distinct projection (132seconds total), and16MiB fixed PLUS8MiB
per projection (32MiB total). Sixseconds/projection includes three independent
cold commands (verify,dumpA,dumpB,1second each) and3seconds for reconstruction,
model/state/PCM validation and final raw capture/archive. Fixed overhead covers
full prefix, setup, failed operation and other per-row work. This is a conservative
planning envelope (>8x measured181.035610/256 per-projection CPU before the large
fixed overhead), not a hardware-independent worst-case time theorem.

Total four-row reservation1188 CPU-seconds/272MiB, below7200seconds/2GiB per lead.
Count ALL actual attempts, children, build, recorder, model, projection copies,
readbacks, archived and unarchived evidence; storage bound applies to retained
new evidence plus working material, not only compressed ZIP size. Sparse device
logical size does not waive actual filesystem storage usage. Never cut a costly
predicate or omit NEEDS_REPAIR to fit. If local actual build/workspace allocation
already exceeds its reserve, STOP before the first fault. Keep failed receipts.

## Gates before every invocation

Both this method MERGE and independent A252 recorder clearance are REQUIRED before
new execution. Use the cleared recorder. Preserve old source55552ad4fe57e99827ab8eb016044d0486017877,
engined96b4245e04d74078f8938744b1394c3018516f7 and original model/spec identities;
authenticate unchanged mechanics, disclose substantive change instead of reruns.

Before each command record cumulative actual CPU/storage plus next reservation
and the remaining mandatory completion reserve for the current row; proceed only
if these fit both caps. Before a fault reserve its ENTIRE row, every model order,
all required projection readbacks/validation/raw finalization. End a row before
starting the next. Enforce finite per-command CPU/storage limits without deleting
original incomplete output, using recorder supervisor/stop semantics. If any row
or build/positive exceeds its reservation, stop BEFORE the next invocation/row,
publish precise measured overrun and revised next-owner estimate; do not silently
spend slack or trim readbacks. Existing normal CI is mandatory, no optional old
Product campaigns. This method itself executes no Product/native fault command.

## Unchanged actual predicates and return

Import this method plus original wp10_missing_faults_r1/BASELINE and original199
host_fault/load_rows/model predicates unchanged. PLAN pins exact requested native
error, zero landed bytes/flush no durability ack, source/pristine/prefix/LBA/
payload/prior-barrier identities. Match actual setup and complete successful prefix;
reconstruct working bytes from original pristine+actual payloads/effects, compare
retained after image, then model persistence separately. Failed syscall is no
general physical persistence guarantee. No engine/format/port/batching changes.

Use unchanged selector: sorted distinct projection hashes, first each empty/empty,
empty/new,new/new PLUS EVERY NEEDS_REPAIR projection. Each verify/dumpA/dumpB starts
its OWN byte-identical restored image in a fresh cold process. Retain original
commands/streams/exits/seams/repairs/working bytes/full WAVs and judge live set/PCM/
labels/source under the original199 oracle; verify is NULL-write/unchanged, dump
keeps its old policy. No summary-only booleans or binding-hash-only acceptance.

Return exact import/candidate/build/host/runtime/CI/source/model/recorder-clearance
identities, actual per-command/per-row cumulative cost gates, all original and
failed evidence/inventories and usable immutable durable >1MiB transport. Actual
positive is a route control, not accepted41 replay. A scoped stop may leave some
or all four UNEXECUTED; coverage changes only for independently passed actual rows.
At most45/404 accepted after all4 pass; at least359 remain. Six absent long-copy
cuts remain UNEXECUTED. No overall443/physical/native/HOST/integration acceptance.
Issue255 remains OPEN for actual return, at most2 consolidated corrections then
precise final bounded disposition/next owner. All existing stop boundaries survive.
