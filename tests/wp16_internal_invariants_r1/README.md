# Verification239 Stage1 — finite INTERNAL subproof challenges

AUTHORED ONLY under PM497/239, before new Software499 proof implementation.
Inputs Product14cad0b6, Verification046b3f2c; exact S1b9f430c8c9b33532abf07eea0ed2653310639f2d,
233 obligations and234 reviewed20-file source pins. No new uncovered Product code
or private expectations were used. Existing fixed-codec constructor conditional
result carries; no all-process/resource theorem is added.

25 immutable tiny challenges cover PCM block divisibility, per-channel append and
raw-count induction, trim checked arithmetic, exact half-up output counts (including
wide valid intermediates and final-u64 overflow), pass/source premises, mono/stereo
count preservation and unjustified32-attempt convergence. `cases.py` specifies
the complete schema/expected results. `oracle.py` uses contract integer arithmetic,
not Product code. `selftest.py` checks each expected result and detects25 answer
corruptions. No audio/native/codec execution or admitted failure witness occurs.

## What Software must actually return

Import all package files verbatim from the merged source/tree. Return exact
candidate/source/blob/lock/build/host/target-width and extraction/adapter identities,
raw25 challenge input/output and detecting discriminator runs, plus a NEW checkable
per-site certificate. Do not call a copy of this oracle to generate actual answers.
For actual scalar functions call the pinned production function through mechanical
plumbing; for an induction/countermodel use a separately labelled extracted guard
or proof checker. Label every row as actual function, extracted discriminator or
proof-model only. Invalid states supplied to extracted finish/zip are countermodels
to a premise, not admitted production sources or INTERNAL witnesses. A false append
premise need not be rejected by finish itself: constructor obligations come first.

Newly useful facts are scoped, executable conditional lemmas with source-bound
initialization/preservation/error/return edges, not another inventory narrative:

1. WAV/AIFF deinterleave: caller proves positive width/channel and complete block
   divisibility. Initially each plane length0. Each completed frame appends one
   element to EVERY required channel; after k frames all lengths=k. Success raw
   count equals the same frame cardinality. Prove caller/parser preconditions;
   do not pretend the inner floor division itself rejects partial frames.
2. FLAC block append: initialize C planes and raw accumulator0; every successful
   block validates C subframes and identical block size, appends each complete
   plane and updates raw by that same count. Prove all loop/CRC/continuity/error
   paths either preserve the relation or return before successful Decoded state.
3. MP3/AAC unit append: establish packet's reported frames AND actual copied
   vector/channel lengths. A metadata frames check alone does not prove
   copy_to_vecs_planar's shape. Pin vendor implementation/dependencies and the
   append/raw update edges; explicitly leave unclosed copied-shape premises open.
4. Decoded/trim: successful constructors supply exactly channels planes of
   raw_frames elements and finite values; checked head+tail<raw gives positive
   effective count. Distinguish the original finish guard's existing-plane check
   from a constructor's plane-cardinality proof. Failures do not become successful
   states; resource errors cannot be assumed away to claim production reachability.
5. Pass/resample/quantize: byte hash equality alone requires deterministic decoder
   rate/channel/trim/count result. Exact count uses a sufficiently wide checked
   intermediate; requiring u64 intermediate multiplication would wrongly reject
   valid inputs. Prove output count fits target usize/allocation/index bounds.
   Rate44100 identity needs effective slice length=out_frames; other-rate k-loop
   needs one output/k. Stereo zip requires equal channel lengths, then exactly
   2*out_frames samples; shortened stereo is not rescued by claiming zip succeeded.
6. Refinement: real-arithmetic decreasing gain is insufficient. Supply an actual
   finite-precision invariant/ranking certificate covering peak reduction, gated
   loudness feedback, quantization/dither reset, threshold/undefined/nonfinite
   branches and every continue, proving successful exit by32; or return the
   smallest unresolved branch/inequality. The frozen32-continue countermodel
   rejects an unsupported global claim but is not a codec witness. Do not invent
   a fake production failure or require runtime-wide proof for the carried MP3
   fixed-codec constructor result.

Every lemma names full admitted domain/build/target/dependency premises, verifies
base/step/all success/error edges and points to exact pinned source lines. Return
source-extracted missing append/raw-update, shortened plane, truncated count,
changed pass-state and unsupported-convergence negatives as detecting controls
within this same25-case set, plus valid neighbours. Controls that prove only a
model's detector are labelled accordingly. No case count/domain expansion or
outcome-based tuning; a real defect returns exact finding without code/assertion
changes. No full vendor/codec/audio campaign or new admission restriction.

Independent Stage2 will authenticate actual extraction/plumbing and raw results,
apply frozen comparisons and assess induction completeness. A newly proved finite
subdomain is useful without a global theorem, but every claimed reduction of a
residual must have a checkable fact. Global INTERNAL stays UNPROVED unless all
applicable premises close; genuine admitted witness requires immutable admitted
source/executable/raw report/exit/cleanup facts, not these model vectors.

2CPU-hours/512MiB per lead; existing normal hosted build/CI allowed, no installs/
privilege/tool hunt. Raw large artifacts outside Git with complete hashes/stable
transport. Stage1 normal CI/merge publication precedes execution. Return actual
facts to239, leave Stage2 pending and continue other queue work. No454/459/fullAPP
integration permission from proof-model success. Two consolidated correction
returns maximum; unchanged incapability stops. S1/physical/native/Mac/S3 holds carry.
