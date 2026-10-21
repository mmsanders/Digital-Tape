# Verification254: retained-input meter precision and coordinate method

PM510 / Software513. Authoring only, before new instrumented driver execution.
Product main192fed8cf1f367899db3c9ed967f5c4d1d898dec / Verification main
e6bc7b87dab9d3620c3a018125cb7b404bca8c31. Carry240 review merge
659b0e43a70dfbd6db3d4b52747ad087c7fac201 and immutable18-case method
1f919513757b94a84f2cab46f6d146de80f9b553.17 original usable returns, endpoint-1
LOST/no credit/no rerun,67 spans/55 declared gain0/12 attenuated remain unchanged.
Original inner ZIP297029 bytes SHA256
108ad9bfe7036605e0405e52c46f9065fb6028244bb953b276f694d3faa0476c is now durable.

## Fixed selected inputs and gate

SELECTED.json binds ONLY join-29000-1 (attenuated shifted join), gap-1 (same-source
gap/reset contrast), block-end-1 (2^20+1 streamed boundary). Exactly these THREE
already-usable cases, their original WAVE inputs and retained converted/assembled
bytes. No endpoint-1, new source, shipping CLI rerun, audio search, tuning or case
expansion. Preserve all original inputs and old reports byte-for-byte. New driver
data is instrumented evidence, never a reconstructed original shipping receipt.

Do not execute the new meter/quantizer driver until BOTH this method is merged
and independent A252 standalone recorder clearance is explicitly published. Use
that cleared recorder for new case evidence. Read-only source/retained bytes and
ordinary method selftests can proceed meanwhile. Software may add test-only
access to existing exact functions; no production arithmetic, coefficient, gain,
threshold, phase, dither/reset or branch changes. Record instrumented delta and
show the called implementation matches the pinned source. At most2CPU-hours and
512MiB including builds/raw/new returned bytes; no expansion at a gate failure.

## Three checkable obligations

O1 SUPPORT/COORDINATES. Already reviewed Product TruePeak has256 phases,512 taps
and TP_HALF256. For evaluation (n0,q), tap i reads x[n0+i-255], i=0..511, with
zero outside valid input; full support [n0-255,n0+256] inclusive. Signed subphase
position z maps by Euclidean division n0=z//256, q=z%256 including negative z.
Joined sample global coordinate equals source start+local sample; gaps are88200
frames, outside whole signal is zero. A streamed block at lo fills from lo-258;
buffer-local sample/evaluation index k maps to global lo-258+k. Do not reset this
offset at source/gap boundaries or treat physical buffer prefix as signal frame0.

For each selected join, gap and streamed cut bind a finite window of evaluations:
n0 in boundary+{-257,-256,-255,-1,0,1,255,256,257}, four grid phases{0,64,128,192},
and signed refined neighbours centre+{-63,-1,0,1,63} around each grid centre.
Deduplicate coordinates; boundaries are each source start/end, gap start/end and
actual streamed lo/hi in the selected assembly. This is a finite observation set,
not exhaustive all256-phase peak or numerical transfer proof. Return each mapped
sample support, actual fill start/length and per-channel bytes/hash; authenticate
against retained original PCM slices and zero gaps. A wrong phase, off-by-one,
source-relative/global offset or reset must fail the independent integer mapping.

O2 EXACT GAIN/QUANTIZER BINDING. For each selected source occurrence return the
actual production conversion's full-precision gain bits (f64 or declared actual
type), input frame/channel/trim, source invocation order and dither initial/final
state or source-bound reset proof. Never infer exact gain from six-decimal text.
Preserve actual gain-selection branch/repetition count and every meter call used
in selecting that gain. With those bits independently compute the existing pinned
quantizer on the SAME input/source reset and compare to the newly instrumented
output, then separately compare with retained original converted bytes. A mismatch
with old bytes is an observation requiring explanation, not permission to rewrite
old evidence or tune a scalar. A matching original manifest alone does not bind
the original hidden gain. Original unit-gain comparisons retain conditional status.

O3 METER PRECISION/HISTORY. Return raw IEEE little-endian f32 bits for coefficients,
grid4/at values at the selected finite coordinates and f32 maxima; actual f64/db
gain diagnostics as bits with type. Full coefficient table bytes may be one shared
hash-pinned object. Bind support, sum order, padding and actual function source.
Compare grid4 lanes to actual at() at q=0/64/128/192 for SAME support, requiring
bit equality under the pinned actual build, or precise discrepancy. Record actual
peak_range lo/hi, grid running maximum/history, local-max decision, refinement
centres/intervals and global streamed block reset/aggregation. Those histories may
differ across standalone/assembly contexts: DO NOT require or assume equal peak
outputs absent an independently justified transfer. Return the exact dependency
or residual when histories prevent an inference; no fabricated tolerance/ranking.

## Negative controls and verdict

oracle.py/selftest.py validate independent integer support/Euclidean/global/block
mapping and exact float-bit decoding. Synthetic wrong phase, support off-by-one,
global offset, stream reset and rounded gain diagnostics are causally rejected.
Actual driver return must include copies of its real observations with these same
mutations, rehashed internally, with the original externally bound request.
Rounded text is a diagnostic, not equality proof even when it prints the same.
No independent16-phase double reference is promoted into Product512-tap/256-phase/
refined-f32 support or a global absence theorem; immutable old expectations remain.

Return exact import/method/source/build/host/runtime/A-clearance identities, actual
commands/stdout/stderr/exit/final timing, selected inputs, original archive and new
artifact inventories and durable >1MiB transport. Ledger O1/O2/O3 separately:
demonstrated facts, conditional inferences and smallest remaining premise. Source
inspection alone cannot supply a missing actual precision receipt. Stage2 issue254
stays OPEN while waiting; at most two consolidated corrections, then exact scoped
disposition. No JOINED_PEAK witness/absence or Product integration follows from a
green method/selftest or this finite precision task. All existing holds survive.
