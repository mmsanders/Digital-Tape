# READ-1 authority repair — Software evidence return

Execution and candidate binding are separate. The copied original manifests retain
execution head `dfe426d4569a53c64558ca84e24cb41881521821`; they are not a new run.
Original exact-head [READ-1 run 37799314742](https://github.com/mmsanders/Digital-Tape/actions/runs/37799314742)
completed successfully, including 59 cases, actual controls, complete shipping
equivalence, baseline zero-budget differential, absence/leak control and replay.
Lossless observations, raw callback logs and build artifacts are in the [hashed
release](https://github.com/mmsanders/Digital-Tape/releases/tag/evidence-read1-dfe426d4569a53c64558ca84e24cb41881521821).
The archive SHA-256 is recorded in comparison.json and the original SHA256SUMS.
The downloaded manifest ZIP authenticated to its GitHub artifact digest before the
unchanged manifests were copied here.

The repaired verifier publication adds only the frozen acceptance authority copy
and its INPUTS pin/provenance. Every prior executable/schema/case/oracle/backend/
control file remains identical. Product main changed only PM docs/dashboard since
#411's base. Engine tree and the entire original adapter tree remain identical;
each original build source matches the original provenance SHA-256.

`tools/read1-carry.py` authenticates the original archive, rebuilds the unchanged
instrumented/shipping binaries in their canonical CI paths, requires their exact
original hashes, validates original manifests with their original executed head,
and replays the full original canonical stream through the corrected publication.
Its final-head binding manifest explicitly records that no new full campaign ran.
This preserves the original workflow and is not a duplicate C60 execution.
Independent Verification decides the admissibility of this identity binding.

## Retained regression blocker

Original [engine run 37799314356](https://github.com/mmsanders/Digital-Tape/actions/runs/37799314356)
completed with five failing jobs: strengthening R55, WP09 capacity, WP06 closure,
WP08 mapped-run regeneration and the accepted-binding regression gate. They report
fresh JSONL hashes differing from the old retained hashes. The first four fresh
streams still pass their unchanged behavioral oracles/negative-control baselines.
This does not make the mandatory byte-regeneration gate green.

A focused final-source WP09 capacity run reproduced all 27 cases. Recursive
comparison against the old retained stream found differences only in device-event
arrays (read count/LBA/request grouping); all other fields are identical. The new
read path batches count=64 instead of count=1. Its unchanged ten negative controls
still detect their targeted violations. Other failing streams require the same
complete difference authentication before any rebind decision.

No retained stream was overwritten, gate changed, assertion relaxed or golden
regenerated. Final-head retained CI remains mandatory. The known changed raw I/O
transcripts must be routed to PM/Verification for their disposition; behavioral
PASS alone grants no byte-comparison exception or independent acceptance.
All WP14, A8 engine-pin and Michael-reserved merge holds remain.
