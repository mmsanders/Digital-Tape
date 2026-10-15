# INGEST-1 complete Stage 1 — ADR-177/178/180

Independent Verification #169 publication for direct Software #435 import.
This is the complete authored host-tool package, not Product/native/platform,
real-card or fullWP16 acceptance. Stage2 disposes Software's exact imported head.
No Product implementation/design/private tests were inspected. Individual lead,
no subworkers. Physical WP14A6 is not a dependency for this host-only work.

Authority: Product main c6ff868086e3333bb7568e60d3a2f4ec60fd3344, Verification input
10db792e0eb66d048257dedb0360af6d37b1c1ed; issue169 updated2026-10-15T05:31:00Z.
Exact public contract/WP16 copies and blobs are in authority/ and PINS.json.
Prior cc50b720 and main10db792/checkpoint subtree00cca9c046b006807fa491c957a1ad3736aaeeb1
are preserved, not imported or relabeled as complete. This is a distinct tree.

## Complete authored scope

CENSUS.json contains1927 concrete descriptors in six coherent rows, covering I1–I8.
SOURCES.json in the authenticated asset contains1763 CC0 fixtures with exact
bytes/hash/generator/licence and positive rate/channel/raw/trim/frame facts.
Every native/command case is an expectation, not an observed Product result.
Arithmetic loops are not padded into case counts.

- All issued lossless precision/rate/channel combinations, nativeFLAC every8–32
  precision, MPEG1/2/2.5 CBR/VBR, BMFF/ADTS AAC-LC, header/suffix independence,
  strict format/corruption/protection/refusal cases and complete source admission.
- ADR180:90 non16-bit sowt cells are named refusals, each with an admitted16-bit
  neighbour. CRC-positive/minimal SCE/CPE and frozen FDK AAC, checksum-only
  negatives, multiblock refusal, both MP3 tag-CRC writer spans, exact shortened
  stts/edit agreement and lone/conflicting refusal; lossless known/none/zero trims.
- Independent decode/interval and documented FIR reconstruction, exact count,
  stereo/mono/PRNG/draw order/round-even, constant-gain residual and truthful
  measured/silent/short/gated/peak-limited outcomes, final and joined peak checks.
- Actual-ingest generated EBU/direct-sinc calibration sources; source passband,
  alias, latency and endpoint cases. Two different reference FIRs satisfy both
  selected-vector tests and28 continuous-band magnitude enclosures, each retaining
  isolated/batch/repeat identity. No universal one-library waveform hashes.
- Natural/NFC/ASCII-only case folding/unbounded numeric ordering, folder argv
  order, exact source/gap joins, canonical schema/arithmetic/no volatile metadata,
  target/repeat/relocation/neighbour and same-profile three-platform identities.
- Exact-fit/one-frame-over/gap-inclusive/zero-output and RIFF boundaries; native
  preflight-no-output/scratch/device scope, source SHA/file identity binding,
  errors/exhaustion, concurrent DEST, existing data protection, exclusive adjacent
  stage, flush/close, single no-replace pair publication and every declared kill cut.

[COVERAGE.md](COVERAGE.md) maps predicates and causal controls. [INTERFACE.md](INTERFACE.md)
is the complete compact observation contract. Software owns adapter/transport
outside this immutable tree. Verification owns independent receipts/proofs, never
Software self-certification. No new shipping CLI or runner architecture is required.

## Replay / assets

Python3.12; numpy2.3.5/scipy1.17.0. FFmpeg6.1.1-3ubuntu5 is an authoring decoder,
not a universal output oracle. Its exact encoder provenance is in the source pack;
Install FFmpeg on PATH before decoder validation/integration replay. Publication
CI explicitly installs Ubuntu's FFmpeg package; it is not assumed on hosted runners.
extra encodings have extra-encoded/PROVENANCE.md. Source bytes are frozen for all
candidate platforms. The full pack is a durable hashed release; raw>1MiB is not git.

```sh
python3 -m pip install -r tests/wp16_ingest_stage1/requirements.txt
python3 -B tests/wp16_ingest_stage1/check_pins.py
python3 -B tests/wp16_ingest_stage1/selftest.py
python3 -B tests/wp16_ingest_stage1/completion_selftest.py
python3 -B tests/wp16_ingest_stage1/zero_boundary_selftest.py
python3 -B tests/wp16_ingest_stage1/large_selftest.py
python3 -B tests/wp16_ingest_stage1/calibrate.py --out /tmp/ingest-calibration.json
python3 -B tests/wp16_ingest_stage1/filter_bounds.py --out /tmp/ingest-filters.json
python3 -B tests/wp16_ingest_stage1/asset.py --destination /tmp/ingest-sources
python3 -B tests/wp16_ingest_stage1/format_selftest.py --sources /tmp/ingest-sources
python3 -B tests/wp16_ingest_stage1/integration_selftest.py --sources /tmp/ingest-sources
python3 -B tests/wp16_ingest_stage1/validate_fixtures.py /tmp/ingest-sources --out /tmp/ingest-fixtures.json
```

ASSET.json pins archive size/SHA256/member census and SOURCES.json hash.
Extraction authenticates every source. Sources expand to about1.1GB, including
two sparse signed-zero inputs. The largest legal output case is an ACTUAL
4,294,967,300-byte canonical WAV (RIFF size4,294,967,292), checked by streaming all
bytes/hash and exact zero payload, not by allocating a17GB float buffer or checking
just endpoints. The next source count must refuse before output. Source silence
permits a compact zero pre-gain descriptor; it does not waive actual full output.
This host-file boundary is not Michael's physical-card >4GiB witness.

Source authoring crosschecks include1382 exact lossless decodes,4 independent
extensible valid-bit/container decodes,99 lossy raw counts,139 behavior/qualification
checks,137 refusal identities and2 exact sparse source layouts/hashes. No pending
ruling cells. Reference feasibility evidence is in evidence/, including162 meter/
filter-vector observations,28 band enclosures, baseline/causal controls,10-case
file-packet integration and actual >4GiB reader control. These remain synthetic/
reference authorship evidence, not shipping behavior.

FFmpeg6.1 misinterprets some extensible16/24-valid-bits-in32 containers. The positive
facts follow Microsoft's WAVEFORMATEXTENSIBLE definition and are independently
cross-decoded with scipy.io.wavfile, not changed to FFmpeg's wrong count. See
[Microsoft](https://learn.microsoft.com/en-us/windows/win32/api/mmreg/ns-mmreg-waveformatextensible).
The candidate must honor actual container alignment/significant precision.

The existing WP14 publication workflow performs package selfchecks and durable
source rebuild/publication/download replay. It does not run a Product/native
campaign. No new permanent workflow. Every future source/package correction gets
a new identity; old published bytes/assets stay unchanged.

## Direct next owner and holds

Software #435 imports this complete tree verbatim with publication/asset identities,
binds actual observations for Windows11x64/currentmacOSarm64/Linuxx64 and returns
its clean exact candidate directly to Verification #169. Missing/failed/slow matrix
members or platforms never imply PASS. Verification then reviews raw evidence,
evaluates the full campaign and publishes its exact-head disposition. No PM
acknowledgement round is needed. #169 stays open between stages.

WP14A6/native/physical holds, real-card/fullWP16/WP15, hardware/media/atomicity,
target<30s, write/async/recording/firmware/frozen-format and WP11-golden holds survive.
No new Michael load/pull/dump/README/card test is requested by this publication.
