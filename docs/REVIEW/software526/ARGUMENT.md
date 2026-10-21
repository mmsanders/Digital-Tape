# Software526 conditional cardinality proof return

Exact frozen S1b9f430c8c9b33532abf07eea0ed2653310639f2d; method269
4c84472d1c7b474a3a9e6ec679889e0d89a9a6fc/tree32bf7ed27b0384da6d08531ec0aef958f5df0973
was imported first. No codec was built, imported or executed. The prior six-body
stop is superseded for this invariant; this return adds46 pinned function nodes,
44 complete source files, capability/assignment/signature census and24 separate
obligation rows. Software's two lemma verdicts are PROVED_CONDITIONAL, awaiting
independent source judgment. The ledger checker proves shape ONLY.

## Complete invariant capability graph and induction

Let B be the exact owned AudioBuffer object, S its private owned spec, P the
length of its private SmallVec of planes, and C=count(S.channels). Distinguish
valid-frame count F and capacity N from P. A successful AudioBuffer::new moves S
and creates exactly C vectors with resize_with(C), each capacity N, F=0. Under
valid allocation/container semantics, P=C even when F=0. Admission supplies
positive mono/stereo C, so constructor's division by C is defined. Default zero-
capacity MP3 buffer is not a successfully returned decoded frame: is_unused forces
replacement before decode success. Its derived default capacity0 is a named Rust
Default contract, not an observed codec run.

This graph is projected onto the capability to mutate B/S/P or the host output's
outer cardinality. It is not an arithmetic/codec-quality call graph. Every call
that receives the whole output buffer is explicitly followed: MP3 decode_inner
to Layer3::decode; AAC decode_inner/decode_ga to ChannelPair::synth_audio; shared
clear/render/trim/shift/truncate and output slice access. Remaining numerical
callees receive only disjoint codec state, immutable headers/data or fixed-length
sample slices. Their ability to write B/S/P is PROVED_UNREACHABLE by the pinned
call signatures, exclusive owned state, field privacy and absence of unsafe code
in these crates, not by assuming those numerical callees compute correct samples.
The exact source includes those numerical modules so Verification can challenge
the capability cuts. The edge kind here denotes unreachable metadata mutation,
not that the numerical function call itself is unreachable. This interpretation
is explicit rather than silently changing an oracle assertion.

The census retains all AudioBuffer/AudioSpec references, output replacement and
private spec/plane field accesses, mutator signatures and unsafe matches across
the pinned MP3/AAC/audio modules, plus exact byte/hash/blob and one-based function
ranges. AudioBuffer fields are private; AudioSpec::channels returns only &Channels.
No API used by these paths exposes a mutable spec or mutable outer Vec/SmallVec.
plane_mut exposes &mut[f32] only. The apparent `self.planes=rest` writes in
AudioPlanes iterator next update its borrowed iterator remainder, NOT B. These
iterators receive immutable outer slices. Numerical output authority ends at
fixed slices, regardless of internal sample/state arithmetic.

AudioBuffer::clear changes F only. render_uninit checks capacity then changes F
only. truncate decreases F; shift either clears or copies samples inside each
EXISTING plane and decreases F; trim composes them. None changes P or S. Growth/
other render APIs in the retained source likewise do not expose outer ownership,
but they are not called by these concrete decode paths; no unspecified mutable
trait dispatcher is substituted for the concrete f32 implementations.

## MP3 lemma

Host mpeg::header admits LayerIII only and the frame walk rejects version/rate/
mono changes. The host directly constructs MpaDecoder for CODEC_ID_MP3, so State
is Layer3; the decode match additionally requires Layer3 header. LayerI/II code is
retained in source but excluded by those explicit two guards. Registry/demuxer
constructors are not this host path. At first decode, unused buffer is replaced
by BNEW(header.spec); subsequent spec mismatch returns Err BEFORE decode. Each
replacement proves the new object's invariant; no old-object lemma transfers by
variable name. Reset replaces separate codec state, leaving B/S/P intact.

Layer3::decode receives B but its ONLY output-capability operations are
render_uninit(Some576) and plane_mut(ch), then synthesis on a granule sub-slice.
Bit reservoir/read-main-data/requantization/stereo/hybrid helpers receive distinct
state/header/sample arrays, never B, S or the outer planes container. If any
stage errors, decode_ref clears F and returns Err; a partial numerical mutation
cannot corrupt cardinality. Later successful reuse starts from preserved B/S/P.
Trim is optional but also preserves P=C. Returned F32 generic reference is the
same B. Every successful admitted MP3 frame therefore has P=C under named premises.

## AAC lemma

Host ASC/ADTS/MP4 paths admit LC/config1 or2/1024 and directly construct AAC.
Constructor also rejects wrong codec, unknown channels, nonLC/SBR/>2/non1024.
It clones owned channel representation into the same spec used by BNEW. ASC and
buffer channel representation have no subsequent mutation/alias in this path.
Any actual spec-count disagreement with host ch is refused before copy/append.

decode_inner clears F then render_uninit(None), dispatching only LC decode_ga.
decode_ga changes pair/ICS/CRC state, never B/S/P directly. set_pair creates or
checks pair channel/is_pair and validates indices against ASC count; synth_audio
then obtains plane_mut(channel[/+1]) and gives only those sample slices to ICS and
DSP. Error exits do not return a frame, and decode_ref clears F. Failed pair
admission can leave internal pair state, but later success revalidates its indices;
a panic/error is not admitted success and cannot silently remove an output plane.
Reset touches pair state only. Same B persists until decoder drop; a new host
stream creates a new decoder/B. Every successful admitted AAC frame thus has P=C
under named premises. No PCM content/CRC-quality/no-panic theorem is inferred.

## Host C correspondence and copying

Both hosts check buffer.spec.channels.count()==host C BEFORE copying. Together
with the two codec lemmas, P=buffer C=host C. Generated GenericAudioBufferRef::F32
borrows the concrete B; its macro dispatch reaches Audio::copy_to_vecs_planar.
That resizes tmp OUTER length to P and each inner length to valid frame samples,
then copies every actual plane (carried239 exact copy bridge). Host constructs
exactly C output vectors by a C-iteration push loop; alloc reserves capacity but
does not create samples. Zip of C host vectors and P=C tmp vectors is exhaustive.
Append preserves outer count. finish checks declared channels/rate and each plane
length/finite/trim; it does NOT itself check outer plane count. This return closes
that necessary premise through constructor/mutator/caller induction instead of
using finish's per-plane loop as a substitute. Fresh decoder per stream and
per-return guard prevent correspondence silently carrying across a changed object.

## Explicit conditional contracts and exclusions

Rust privacy, borrowing, type/memory safety and successful standard/container
operations are conditional premises, including SmallVec/Vec resize_with/resize,
move/clone, slices, iteration/zip and ordinary representable integer arithmetic.
These are named contracts with exact usage/file pins; vendor codec mutators are
audited source nodes, not hidden inside a generic contract edge. Crates forbid
unsafe code; no external unsafe fabricator, data race, alias violation or compiler/
allocator/container defect is asserted impossible by an experiment. Such states
are outside the admitted conditional theorem, not actual codec counterexamples.
The pinned Cargo.lock accompanies source. Prior239 PCM/FLAC/scalar/copy and253
local constructor facts carry within their original limits.

Sixteen frozen abstract premise-falsifiers and30 independent shape rejections
remain labelled synthetic; they do NOT prove source semantics or universality.
No decoder fixture was independently declared necessary, so ZERO decoder runs.
Software's conditional lemma verdicts still require Verification269 to judge
graph completeness/capability cuts and EACH entire codec lemma. Global INTERNAL,
finite-precision peak/repetition and !limited loudness ranking remain UNPROVED;
no S1/fullAPP/HOST/native/integration permission follows.
