# Software499 conditional count certificates

Authority: merged Verification239 a294ea88, immutable25-row method imported at
1fcb3bd9. Source is exact S1b9f430c8c9b33532abf07eea0ed2653310639f2d, ingest
tree835078995d4e9cc2424f9ea8d6f11304b45f783f. PINS.json authenticates every cited
file/dependency. The workflow archives that Git commit and adds one test example;
it changes no original source. The locked compiler is the source's Rust1.97.0.
Target is hosted x86_64 Linux/usize64; actual compiler, build and commands retained.
These are successful-return/conditional length lemmas, not a whole-process
resource, panic, finite-precision convergence or global INTERNAL exclusion theorem.

## Base, step and error rules

The executable coefficient certificate in run.py verifies the exact linear
identity `(L+b)-(R+b)=L-R`; both missing-append and missing-raw-update transitions
fail. Model rows execute the recurrence on each frozen unit/block and distinguish
short/missing planes and inconsistent raw updates. This algebra proves induction
for arbitrary finite unit sequences **under the stated equal-unit premise**; its
binding to each concrete constructor is the source argument below. It does not
prove arbitrary source code by recognizing a keyword. Independent review of the
source-to-transition correspondence remains necessary.

All lemmas assume successful checked allocation/push/copy, valid input slices,
and representable host indices. Err via `?`, explicit refusal, panic or aborted
allocation is not a successful Decoded/Converted return; none is silently proved
impossible. Hash equality is collision resistance plus byte identity, not proof
that external nondeterminism or an arbitrary replacement decoder is absent.

### PCM WAV/AIFF constructor and deinterleave

common.rs `deinterleave`: C empty planes are allocated; C is1 or2 and width is
positive. WAV decode checks channels, the issued Pcm width, align=C*width,
byte_rate=rate*align and data.len()%align==0 before dividing. Its raw count is
data.len()/align. AIFF decode checks channels/width, positive declared frames and
the u128 equality offset+frames*C*width==SSND bytes after its8-byte prefix, then
passes exactly that suffix. Thus each caller supplies complete frames. Inner floor
division alone would truncate a partial block: frozen partial-frame is explicitly
an extracted caller discriminator, never a claim that deinterleave rejects it.

For each completed f iteration the inner enumerate visits each of the C planes
exactly once and pushes one sample; offset bounds follow from f<F and c<C. Base
length0, step+1, exit lengthF for every plane; raw=F. Sample conversion does not
change count. Caller validation/decode/allocation errors return before success;
finish rejects nonfinite samples and bad trim. The four valid frozen PCM neighbours
call actual deinterleave; no WAV/AIFF input campaign is added.

### FLAC constructor

flac.rs decode initializes C empty planes and samples=0. Each frame fixes block>0,
matches frame channel count to C, validates continuity/CRC/format, creates exactly
C subframes, and aligns/checks body CRC before append. Constant subframe resize
gives B; verbatim pushes B. Fixed/LPC subframes start with order samples, then
residual produces B-order: P=2^porder partitions each have B/P samples except the
first subtracts order; sum=P*(B/P)-order=B-order, using the checked divisibility
and order<=B/P conditions. Predictors push one per residual; wasted-bit/decorrelation
loops and integer-to-f64 maps modify values only. Therefore each successful
subframe returns B. All unsupported/truncated/CRC/arithmetic refusal edges escape
the current decode through Err, never a shortened successful block. Mid-append
allocation failure may leave local unequal planes but returns Err before Decoded.

`planes.iter_mut().zip(subs)` visits exactly C only under that established
cardinality, extends each by B, then `samples += B`; the coefficient induction
applies. Final STREAMINFO count/MD5 checks may refuse, not change lengths. Normal
return uses raw=samples and finish. This closes the conditional successful-return
length path; it does not prove all arithmetic/allocation failures unreachable.

### MP3/AAC copy/append bridge

mpeg.rs checks each decode_ref buffer frames=spf and spec channel count=C;
aac.rs decode_units checks frames=1024/spec channel count=C. Initialization creates
C empty vectors; the outer loop appends copies and normal raw is units*unit-size.
In vendor/symphonia-core/src/audio/generic.rs the dynamic copy methods dispatch to
the concrete Audio implementation. audio/mod.rs `copy_to_vecs_planar` resizes outer
to num_planes and EVERY inner vector to samples_planar, then copies. samples_planar
defaults to frames(); audio/buf.rs frames=num_frames, num_planes=planes.len,
and plane(i) slices0..num_frames. This establishes the copied length=reported
frames bridge **conditional on concrete buffer.num_planes==spec channel count**.

Residual: a complete constructor/render/reserve path proof of this equality for
every normal MpaDecoder/AacDecoder buffer return is not discharged here. A metadata
channel check is insufficient alone. Thus MP3/AAC append induction is now pinned
through the concrete copy implementation but its constructor cardinality premise
remains OPEN, not promoted to a completed codec theorem. Decode errors/AAC CRC
failures exit before successful return; ordinary fixed-codec MP3 constructor's
previously accepted conditional exclusion carries, with no invented rate Err.

### Decoded finish and trim

common.rs finish checks rate/channels/nonzero raw, iterates existing planes and
requires length=raw/finite values, then uses checked head+tail<raw. It does NOT
check planes.len()==channels. Therefore its successful guard implies positive
raw-head-tail only when constructor cardinality is supplied separately. Four
frozen trim rows call actual finish/effective_frames on deliberately empty-plane
constructed states so enormous u64 values do not allocate. These are guard
discriminators, not admitted sources. An invalid constructor can pass finish;
that is an explicit premise boundary, not a fabricated production INTERNAL.

### Output count, resample and quantize

dsp.rs output_frames computes floor((N*44100+rate/2)/rate) in u128, then checked
u64 conversion. For N<=u64::MAX and admitted positive rate<=192000, intermediate
is <2^80, hence fits u128; a u64 multiplication restriction would be false.
Five frozen scalar rows call that actual production function, including the wide
valid intermediate and final output overflow neighbours. Native rate0 is outside
this proved admitted domain and is not injected.

main pass1 stores raw/trim/effective/rate/channels/count. Pass2 hashes reread bytes
then decodes. Equal bytes plus deterministic same-source decoder/config imply
same metadata/planes/trim; hash equality alone without determinism is conditional.
The three frozen pass controls expose that distinction. On usize64, successfully
allocated Vec lengths fit isize::MAX, positive effective slice is within those
planes. Main rejects zero output and total output RIFF overflow; each source's
out<=total<2^30, so2*out and output indices/allocations fitusize64. There is no
new claim for32-bit targets or arbitrarily large successful allocations.

dsp resample44100 copies exactly the effective slice and requires its length to
equal out_frames (actual caller/count premise); other rates push once for each
k in0..out_frames after valid FIR construction, hence length=out. All ? exits
are unsuccessful. Quantize mono pushes twice per input; stereo zip pushes twice
per matched pair, hence2*min(L,R). With L=R=out this is2*out; without that premise
actual shortened stereo returns4 samples for L3/R2, and the frozen discriminator
correctly rejects a claimed six-sample production count. Source length check in
main detects disagreement. Quantization overflow returns None/refusal, not a
short success. Digital silence bypass uses empty PCM with writer emitting exactly
out_frames*4 zero bytes; it is explicitly exempt from c.pcm length check.

###32-attempt finite-precision refinement: minimal unresolved obligations

convert.rs initializes gain from measured input and peak bound, resets dither for
each quantize call, then has two continuing branches: peak over-ceiling updates
g downward and sets limited; loudness feedback can increase/decrease g while
!limited and can clamp to peak_bound. A real-number decrease is not a ranking
function for the bounded f64/f32/quantized/gated state. The smallest unclosed
peak branch obligation is a bound on the next quantized f32 refined peak after
`g -= p_out+GUARD_DB-CEILING_DBTP+0.001`, including rounding/dither, showing how
many repeats can remain above threshold. The other obligation is a finite bound
for the !limited gated loudness feedback, including transitions to undefined
loudness, cancellation/no-change updates and clamp/continue edges. No such
uniform contraction/rank bound is established. The fixed32-continue abstract
trace detects unsupported proof assertion; it is NOT an admitted codec witness.
No search, source change, fake switch or actual INTERNAL witness is reported.

## New facts and remaining judgment

New: pinned actual scalar/guard executions; conditional PCM/FLAC count induction;
the concrete vendor copy-to-vector length bridge with its exact remaining
plane/spec-constructor premise; wide-u128/count/usize64/output induction; explicit
quantize-shortening countermodel; precise two continuing-branch proof gaps.
Global INTERNAL remains UNPROVED. All source assumptions, model rows and native
rows are labelled in raw actual.json. The unchanged independent oracle judges
values only after outputs are saved. Verification239 independently reviews the
source correspondence and residuals; Software does not accept these lemmas itself.
