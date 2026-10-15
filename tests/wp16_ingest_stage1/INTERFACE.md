# INGEST-1 Stage1 observation interface

Use actual issued ingest commands and file outputs. This is an observation schema,
not a new shipping CLI or adapter architecture. Software owns native transport
outside this immutable tree. Verification independently judges raw observations
and creates separate review receipts. A Software PASS flag is never evidence.

## Files / complete census

Each Windows11x64/currentmacOSarm64/Linuxx64 packet contains INDEX.json:
candidate_sha,binary_sha256,tool_version,profile,platform (windows11/macos/linux),
architecture (x64/arm64),config_sha256,profile_file,cases (caseID→record path).
Exact native OS/toolchain/library builds are retained in accompanying raw evidence.
All1927 CENSUS.json IDs must occur exactly once; no missing/timeout/failed/slow
matrix member may be called PASS. Inputs are exact downloaded ASSET.json bytes.
Use descriptor folder argv order and logical names; do not silently rename/omit.

Each record: exit,actual argv,config_sha256,stdout_file,stderr_file,native_record,
raw_trace. Success (and complete output after a post-publication kill) also gives
wav,manifest,before,joined_dbtp,summary. before lists interleaved stereo little-endian
float64 isolated pre-gain observations in source order. summary is the exact
peak_limited/unmeasurable/gapless_unknown count object; stdout must visibly report
those counts. joined_dbtp is the actual selected-profile final joined measurement,
null only for exact silence. Relative evidence paths cannot escape packet root.
All files/command exits/config/version/source hashes must bind the actual binary.
JSON files are UTF-8 on every host. Raw stdout/stderr capture may declare
stdout_encoding/stderr_encoding (default UTF-8); the independent receipt verifies
the actual capture encoding. Diagnostic matching uses NFC equivalence without
altering raw evidence. Native device_open means card/block-device access, not
ordinary standard handles, pipes or the null device used for host process I/O.

For capacity/riff-largest-legal only, before is
{"kind":"entire-zero","frames":1073741814}; the independent fixed source is exactly
signed zero. The checker reads/hash-checks every byte of the ACTUAL4,294,967,300-byte
WAV, exact header, zero PCM and manifest, without materializing giant float arrays.
Sparse output files are lawful; existence/length/header-only claims are not proof.
Compressing raw evidence is allowed with raw size/hash and authenticated replay.

## Conversion, meters and encoded origins

The pre-gain observations must be actual runtime values tied to shipping output,
not invented by undoing gain on a compressed waveform. Independently decoded
fixture intervals and documented mathematical transfer corroborate them. At44100,
no extra processing is allowed; profile-owned floating precision has a2e-6 times
source-peak enclosure (not a forced64-bit waveform). Lossy selected vectors allow at most2% RMS
error or1LSB absolute relative to an independent correctly trimmed decode. This
is a deliberately loose decoder-fidelity check, not a universal waveform hash or
a promise of lossless encoder recovery. Counts/metadata are exact separately.
Every source also passes exact integer PRNG/quantizer interval reconstruction,
enclosing only six-decimal gain reporting and one floating multiplication round;
dyadic and half-tie vectors have unique exact results. A nonzero effective source
that legally quantizes to one zero frame remains unmeasurable, not omitted or
misreported as an originally digital-silent source; its input peak stays valid.

profile_file declares resamplers by input rate. A generic FIR descriptor has
kind=fir, coefficients (or coefficients_file little-endian float64 plus SHA256),
first_highrate_index. At rational up=44100/gcd,down=rate/gcd, output j is the
zero-extended convolution evaluated at first_highrate_index+j*down. Coefficients
include interpolation scale. This mathematical definition does not force a library
or implementation. conversion.py reconstructs it independently; filter_bounds.py
encloses continuous passband/stopband magnitudes using DTFT nodes plus a derivative
bound and explicit numerical allowance. Source tone/end/latency observations are
checked too. Both reference designs qualify independently, never against each
other's waveform bytes.

Other documented mathematical filters remain admissible. Verification supplies
independently reconstructed reference floats and a same-bound continuous response
proof in its receipts (resampler-math:RATE,src-bounds:RATE); never Software-produced
expected files. The same count/fidelity/passband0.1dB/alias80dB assertions apply.
This also permits an alternative analytic enclosure when the conservative FIR
enclosure is inconclusive at an exact boundary; it is not a tolerance waiver.

Meter profile pins BS1770/EBU filter, reconstruction coefficients/support/window,
zero extension, reduction/FMA/SIMD/thread order, scalar rounding and deterministic
gain refinement. Actual qualification sources are in the pack: standard levels/
gates and independent finite-sinc boundary vectors. Candidate measurements must
meet issued loudness≤0.1LU and peak-underread≤0.1dB; actual final PCM/constant scalar/
TPDF/silence/status/target are independently checked. The0.1dB reported-peak guard
is applied ONCE to the candidate's calibrated measurement, not twice by also
demanding the reference filter's exact guarded number. Gain starts from reported
qualified input L/P; profiles may differ, physical ceiling remains−1dBTP.

Reported peak values must agree with the independently reviewed mathematical meter,
not simply be made conservative to permit arbitrary attenuation. Verification's
meter-math receipt covers source/final/join values and refinement. Where a reference
approximation near the physical ceiling is inconclusive, Verification may supply
a finite independent mathematical UPPER bound≤−1dBTP in ceiling_proofs[case][source
index or joined], bound to the actual PCM SHA in ceiling:CASE:INDEX/joined. No
Software field or unbound estimate can override this condition. Guard and physical
ceiling remain unchanged. Incomplete gating blocks are discarded, no short padding.

SOURCES.json's raw-origin convention is disclosed, not universal decoder semantics:
MP3 head=encoder_delay+529,tail=encoder_padding−529; BMFF generated AAC1024-frame
packets with exact integer edit. Verification owns encoded interval/counts. A
different raw decoder origin requires an independently approved source_raw_mappings
entry (raw_frames,trim_head,trim_tail,effective_frames) preserving the exact
presentation interval, with mapping:ASSET evidence. Actual priming/already-applied
skips must be shown; no arbitrary override, guessed silence or double trim.

LAME tag CRC: reflected8005/initial0. LAME span is frame start through tag byte33;
FFmpeg span is190 bytes of its zero-initialized metadata-frame writer buffer,
with the CRC field zero before calculation and zero padding beyond a short frame.
Both admitted spans have distinct positives and corruption controls. BMFF shortened
final stts must exactly agree with the edit; alone it refuses. Missing edits with
full packet durations remain untrimmed/unknown. Lossless is known/none/zero trims.
Minimal ADTS CRC vectors protect all56 header bits plus192 SCE bits (or192 CPE
bits and128 second-ICS bits), excluding element ID and zero-padding short regions;
poly8005/initialFFFF. Frozen protected FDK positives and CRC-byte-only negatives
also exercise actual spectral frames. Multi-block ADTS and non16 sowt refuse.

## Native evidence and independent receipts

native_record: scenario,exit,complete,raw_trace_sha256,observer_selftest,events,
dest_after,owned_stage_after, plus diagnostic_ok/competitor_unchanged/
unrelated_unchanged as relevant. Existing DEST also supplies dest_before and
before/after byte-hash census. Events have contiguous seq,op. stage_create adds
exclusive,adjacent. Normalized ops: preflight_complete,sources_revalidated,
stage_create,output_open,audio_flush_close,manifest_flush_close,
publish_dir_noreplace,source_mutation_detected. publish_file,device_open and
preflight_disk_scratch are forbidden where applicable. Successful publication
ops mean successful operations; failed no-replace attempts are recorded separately.

Bind complete raw native observer output, process/tree/binary identity, source
SHA/file identity EACH pass, input/output file snapshots/readbacks and operation
mapping. Prove full decode/count/order/trim/numeric/capacity before ANY output/stage
open, no private preflight disk scratch/card open, exclusive adjacent stage with
ONLY two files, close/flush both before one no-replace directory boundary. Mutation
refuses, ordinary errors clean only owned stage, concurrent/existing DEST and
unrelated sentinels remain unchanged. Kill before/after every enumerated cut:
DEST absent or complete pair at the actual boundary, never half. Post-publish kill
still requires complete WAV/manifest checking. No power-loss claim.

Qualify observer positive visibility and deliberate forbidden opens, dropped/
truncated records, child processes and process completion on EACH native method.
Empty/BEGIN-END-only/inaccessible traces do not establish absence. Native filename
cases retain exact raw argv/byte spelling and actual filesystem capability. Where
a filesystem itself prevents a normalized duplicate, retain that actual exclusion
and exercise the corresponding native invalid-path/duplicate-folder boundary;
do not pretend two impossible files existed or waive a codec matrix cell.
The independent logical-collision/comparator controls still run on every host.

Verification independently writes a SEPARATE receipts file, never supplied as a
Software self-certification. It binds candidate/binary/profile/platform/config
and checks with decision=PASS,reviewer=Verification,notes,artifact_sha256 list:
profile,decoder-mapping,libraries-config,manifest-field-truth,filesystem,
observer-controls,instrumented-shipping-equivalence,meter-math; native:CASE for
every record/raw trace, summary:CASE for actual stdout, and comparison:CASE:N for
additional observed runs. Optional mathematical mappings/proofs are as above.
Review notes must establish the actual property, not just repeat a PASS string.
Profile review includes deterministic scalar selection, codec/container label
truth, all extra manifest fields' nonvolatile meaning, exact native setup branches
and shipping-versus-instrumented equivalence/absence of diagnostic shipping seams.

## Exact relations / execution

Repeated source slices and unchanged source records (excluding logical path/start)
must match converted-alone observations. No filter/meter/gain/dither state sharing.
Each identity case has actual comparisons entries: mode=repeat,relocate,
different-target or standalone-versus-batch, with manifest,wav,raw_trace. Bind
commands/options/native runs, not copied expected hashes. Different target may
change ONLY target_seconds/capacity_frames in the manifest; PCM is unchanged.

```sh
python3 -B tests/wp16_ingest_stage1/review.py PACKET --sources SOURCES --verification-receipts RECEIPTS.json --out report.json
python3 -B tests/wp16_ingest_stage1/campaign.py --packet WIN --packet MAC --packet LINUX --verification-receipts WIN-REVIEW.json --verification-receipts MAC-REVIEW.json --verification-receipts LINUX-REVIEW.json --sources SOURCES --out campaign.json
```

campaign.py requires all three native platforms at the same exact head/profile and
full success-census WAV/manifest identity. Qualify each alternate profile separately.
A checked report still requires Verification's evidence-backed exact-head disposition
and import/publication/CI authentication. Reference selfchecks establish no shipping,
native, physical-card or fullWP16 acceptance. Direct return is Software435→Verification169.
