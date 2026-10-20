# Exact S1 closed-ID reachability return — Software485

Candidate `b9f430c8c9b33532abf07eea0ed2653310639f2d` (PR454), INGEST1-AP4.
**Global INTERNAL unreachability: UNPROVED. Global JOINED_PEAK unreachability:
UNPROVED. No new actual shipping witness for either ID is claimed.** The downloaded
d923 resource experiment is a separate459 executable, not an S1 report witness.
This return supplies bounded source arguments and the smallest missing obligations
under Verification233; it does not invent an input restriction or change code.

`SOURCE-INDEX.json` binds every `host/ingest/src` and vendored dependency file,
Cargo manifest/lock/toolchain and issued INGEST/APP contracts by Git blob/SHA256.
Links below refer to this exact S1 commit. The source review is not an exhaustive
audit of external Cargo dependencies or a proof about every permitted build/OS.

## INTERNAL — four production emission sites

An exact-tree search for INTERNAL and Fail construction found four production
emission expressions. The constant, null-subject classification and comments are
not additional emitters. `Fail::io` sets Class::Io; `prefixed` preserves ID/class;
`about` cannot add a subject to INTERNAL (`common.rs:50–78`). Decoder errors pass
through `named` (`main.rs:126`) or conversion propagation (`main.rs:253–255`).
The top-level run error path (`main.rs:552–574`) prints the ordinary diagnostic,
calls report::refusal and returns1 for Io, then report::end. This is a source-bound
propagation argument, not an actually observed INTERNAL report/exit.

| Exact site | Entry invariant and preservation argument | Missing fact / falsification requirement |
|---|---|---|
| [common.rs:199](https://github.com/mmsanders/Digital-Tape/blob/b9f430c8c9b33532abf07eea0ed2653310639f2d/host/ingest/src/common.rs#L199), `Decoded::finish` | After valid rate/channel and nonzero raw_frames, every existing plane must have exactly raw_frames elements. All six constructors (`wav.rs:139/269`, `flac.rs:474`, `mpeg.rs:348`, `aac.rs:234/638`) call finish; the guard rejects a mismatch before trim/finite-sample use. This proves what is detected, not that every decoder always preserves it. | **UNPROVED globally:** close constructor/append/frame-count invariants across every admitted codec, malformed-input/error edge and decoder dependency. A Decoded value with raw_frames=N and a plane of N-1 is the precise detecting countermodel; an isolated constructor would test the guard only, not production reachability. No such new executable control is claimed here. |
| [convert.rs:133](https://github.com/mmsanders/Digital-Tape/blob/b9f430c8c9b33532abf07eea0ed2653310639f2d/host/ingest/src/convert.rs#L133), `convert` after32 attempts | Nonsilent input is resampled, measured and assigned a constant gain. Each attempt quantizes with a reset PRNG; a measured peak failure reduces gain by the measured excess plus0.001dB. A nonlimited loudness deviation can adjust gain or switch to peak-limited. Source/allocator errors return earlier. None of those observations is a proven decreasing ranking function over all f64 gains and quantized PCM. | **UNPROVED:** a finite precision bound proving at least one attempt satisfies both guards by iteration32, or one admitted source that actually reaches exhaustion with full report evidence. Quantization discontinuity, threshold rounding, zero/undefined measurements and loudness feedback need explicit treatment. A proposed proof is falsified by32 successive valid attempts all taking continue; scripting those decisions alone is not a source witness. |
| [main.rs:258](https://github.com/mmsanders/Digital-Tape/blob/b9f430c8c9b33532abf07eea0ed2653310639f2d/host/ingest/src/main.rs#L258), nonsilent output length | Conditional structural argument: pass1 stores `out_frames=output_frames(effective,rate)`; pass2 verifies identical source bytes and re-decodes. For non44100 resampling, success appends one sample for each k in0..out_frames. At44100 it copies the effective slice. `quantize` appends two i16 values per left frame for mono, or per zipped stereo pair. Equal input-plane lengths and both resamplers producing out_frames therefore imply exactly2*out_frames samples. Silence deliberately uses no PCM and skips the guard. | **Conditional only:** complete pass1/pass2 decoder/trim determinism, rate44100 frame-count identity, stereo-plane equality, usize/u64/multiplication bounds and successful allocation/loop completion under the admitted domain. Without those premises the zip path can truncate to the shorter channel. A pair of unequal resampler lengths is the exact countermodel; a short returned PCM must hit this guard. No global proof or actual short-output witness supplied. |
| [mpeg.rs:322](https://github.com/mmsanders/Digital-Tape/blob/b9f430c8c9b33532abf07eea0ed2653310639f2d/host/ingest/src/mpeg.rs#L322), decoder initialization | After a nonempty admitted MPEG audio list, params use CODEC_ID_MP3, parsed rate and fixed mono/stereo channel positions. Every `MpaDecoder::try_new` Err is classified INTERNAL; per-packet decode failures later become SOURCE_CORRUPT instead. The vendored `decoder.rs:67` implementation and external Symphonia core types are dependencies of the initialization claim. | **UNPROVED:** complete enumeration of try_new error branches and feature/configuration/dependency assumptions proving they cannot occur for constructed params, including resource-failure behavior. An Err returned from initialization falsifies the premise and must propagate INTERNAL/exit1/null subject. A mock Err proves mapping only; a production witness requires admitted exact bytes/build and the actual error. |

Memory errors cannot be assumed away. The fallible common alloc/push/checkpoint
routes classify resource failures separately as IO_MEMORY; the reserve allocator,
small strings, decoder initialization and process/runtime failure remain additional
assumptions of any universal reachability claim. Finite successful memory rows for
different459 bytes neither prove these S1 invariants nor witness INTERNAL.

The smallest useful next facts are the four obligations in the table, each scoped
to one site. No blanket absence theorem, new broad census, decoder campaign or
forced test-only INTERNAL switch is proposed. Existing SOURCE_LEVEL and
DEST_NAME_INVALID actual witnesses and Linux report-position results carry without
reexecution.

## Global JOINED_PEAK — assembly, coordinates and exact missing proof

The only production global emitter is [main.rs:370](https://github.com/mmsanders/Digital-Tape/blob/b9f430c8c9b33532abf07eea0ed2653310639f2d/host/ingest/src/main.rs#L370).
`joined_dbtp` is computed from both channels using TruePeak::peak_streamed.
The source creates source/gap segments at exact `s.start` offsets, inserts88200
zero frames between folders, fills PCM by little-endian i16/32768, and zero-extends
outside the complete output (`main.rs:272–343`). It measures the whole virtual
stream first, then checks local segment boundaries, then the global result. If a
local check fails, JOIN_PEAK returns earlier; this is distinct from JOINED_PEAK.
The global comparison is `db + 0.1 > -1`, with six-decimal dbtp payload, Refuse
class/exit2 and null subject. Publication occurs later (`main.rs:503`), so this
returned refusal is before WAV/manifest publication. Optional report semantics are
separate from the output pair. No actual new ID/report witness was executed.

Relevant meter details at this candidate:

- `dsp.rs:257–262`:256 fractional phases,4-point grid (TP_GRID=64),
  TP_HALF=256, TP_BLOCK=1048576 frames. Taps are f32.
- `at/grid4` (`dsp.rs:296/321`) accumulate f32 products in fixed order over512
  sample support, with explicit zero extension.
- `peak_range` (`dsp.rs:357`) keeps a running gmax and refines positive grid
  local maxima at or above0.90*gmax. `peak` covers the isolated source with its
  zero tails. `peak_streamed` (`dsp.rs:394`) invokes peak_range per block with
  margin258; each invocation initializes its own gmax.
- Local join checks use a1536-frame slice centered at the boundary and test
  offsets512..1024 (`h=3*TP_HALF`, `h±TP_HALF` in main.rs:344–362).
- Each successful source conversion rechecks final quantized PCM; quantization
  resets Xorshift, draws TPDF in the declared per-channel order, applies ties-even
  rounding, duplicates mono and makes no neighbour-dependent gain change.

These facts do **not** prove that all global sampled/refined coordinates and
running thresholds are dominated by the isolated-source or local-boundary checks.
An isolated source's zero-extension samples differ from a neighbouring nonzero
source at a join. Streamed blocks also reset adaptive refinement state. No real-
arithmetic triangle inequality alone closes the actual scalar f32/f64 comparison.

**Global UNPROVED.** A finite complete argument must establish (1) support and
coordinate coverage for every source endpoint/join/gap and block edge, including
very short and unmeasurable sources; (2) refinement-set dominance despite differing
gmax histories/offset origins; (3) exact reduction/rounding/error bounds and guard
thresholds after source gain/dither/quantization; (4) complete segment enumeration
and correct mapping to pre-publication refusal/report outcome. The issued15-rate,
mono/stereo, trim and arbitrary admitted PCM domains cannot be replaced by the
finite source census. Dependency/libm and build-profile assumptions also remain.

A falsifiable candidate lemma would map each global evaluated interpolation
coordinate, with its512 samples and accumulation order, to an isolated/local
coordinate known to pass. One global coordinate with a different nonzero support,
different refinement eligibility or rounding causing a threshold crossing defeats
that lemma. A real non-silent production witness would require source-safe neighbours
but global guard failure, exact immutable inputs/profile and actual S1 report/output
receipts. Neither a fabricated parser line nor a proposed sample pattern is such a
witness. No new audio search or source-extracted numerical experiment was performed.

The earlier independently accepted finite canonical all-zero WAVE family remains
carried at its silence bounds: exact zero PCM/gaps cannot create a nonzero peak.
That argument does not extend to non-silent tails or prove either global ID absent.

## Return boundary

No source, oracle, tolerance, admission, report policy or production seam changed.
Verification232 owns independent adequacy/disposition of these four conditional
INTERNAL arguments and the global peak gaps. Missing complete proofs remain
visible; no package/454/459/APP acceptance or new campaign follows from this return.
