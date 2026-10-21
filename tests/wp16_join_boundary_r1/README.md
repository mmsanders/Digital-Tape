# Verification240 Stage1 — frozen join/support boundary family

PM497 / paired Software500. Authored independently before fresh implementation
or actual candidate output. Product input14cad0b637ecf45b61406a987767fda770ea73bd;
Verification input046b3f2c930efeb9bdb50d175164d2c4cbdb705b. Uses issued INGEST/AP4,
existing Stage1 integer/quantizer/reference design and the already reviewed234
support/coordinate gap. No new Product/private meter or expected results imported.

18 finite cases, all admitted little-endian PCM16 WAVE at44100Hz, mono/stereo;
every source shorter than17640frames so no finite gated loudness and no boost.
Input PCM stays below32MiB; target30seconds includes all88200-frame folder gaps.
All sources are nonzero; earlier silence controls carry without repetition. Four
endpoint lengths1/2/255/257; four low/high join variants; one exact same-source
folder-gap pair; four near-ceiling channel/one-LSB/grid variants; four compact
12-folder assemblies ending at2^20-1,2^20,2^20+1,2^20+2. The latter place actual
nonzero source endpoints at the global block reset, using short source prefixes,
not a long audio campaign. Matrix order/count/content is fixed in cases.py.

`python3 -B cases.py --out NEW_DIRECTORY` emits exact source bytes, with folders in
argument ordinal order and source01/source02 natural order. MANIFEST.json pins
every full WAV SHA256/size/rate implied by generator, source/output count, start,
gap and capacity. No resampling or trim ambiguity is introduced. Validate raw
headers and input hashes; don't use a fixture label to decide admission/outcome.

## Independent numerical facts and their limits

reference.py implements a declared independent16-phase sinc/Kaiser14 reference,
256-frame half support, matching the existing independent reference design. It
normalizes the finite interpolation filter in double precision, includes endpoint
tails and measures the union of EVERY nonzero input's finite reference support.
REFERENCE.json records source-alone and exact assembled gain0 reference peaks,
coordinates, and an absolute-contribution/L1 upper envelope. Separate per-source
gains are at most1 for these too-short inputs. At any evaluated reference point,
sum of absolute source contributions bounds any such gains; quantization adds
at most1.5LSB per sample (TPDF<1 and rounding<=0.5). Multiplying by that reference
phase's L1 bounds its added error, including zeros inside a nonzero source. Gaps
are exact zeros and have no added dither. An explicit1e-9 amplitude engineering
roundoff allowance is included; this is not an interval-certified libm theorem.

This is an independent finite sampled reference and conservative envelope for
THAT filter. It does not certify every continuous analogue peak, transfer a
bound to Product's different f32/256-phase/4-grid/refinement meter, or prove its
rounding near -1.1dBTP. No new tolerance is issued. The low-amplitude neighbours
have wide independent reference margin and must admit/succeed under ordinary
fault-free contract operation. High-amplitude cases are probes: the contract
permits source-wide peak-limited attenuation and final join refusal. Their exact
gain, PCM hashes or success/refusal are not invented reference goldens.

The remaining analytical bridge is still exact source/local/global support,
coordinate/history/refinement/finite-arithmetic coverage, including source/gap
ends around block reset and threshold rounding. These finite probes can expose
a missing branch or bound; no negative result proves global absence. If the
reference cannot decide a near-threshold actual fact under the existing issued
qualification, report that precise numerical method limit instead of treating
an approximate delta as a defect, copying the Product meter as oracle, tuning
amplitudes or expanding this matrix. No assertion/tolerance/gain/filter change.

## Actual Software return and independent Stage2

Import the complete merged package unchanged before generation/execution. Return
exact candidate/source/import/algorithm/build/binary/dependency/host identities,
full command argv/folder order/target, generated input manifests and resource
receipts, authentic raw stdout/stderr/exit and original report JSONL for every row.
Use released arithmetic profile and ordinary shipping build. If a permitted
mechanical observation adapter exposes source PCM/meter/local/global facts, pin
every source/adapter byte and show no arithmetic/control-flow change; distinguish
those observations from an uninstrumented production report. Never synthesize a
global error or feed our reference back into Product. Raw outputs >1MiB use bounded
immutable release transport with full inventory/hashes.

On success return complete WAV/manifest and independently bind source-alone
converted PCM/manifest if available WITHOUT running a new full campaign. Assert
exact source hashes/order/counts, known lossless trim0, mono L=R/channel order,
per-source reset/constant gain and deterministic issued dither, exact concatenation
and88200-zero gaps, canonical headers and published pair, source/assembled peak
guard and unmeasurable status/reason. Gained floating inputs require authentic
scalar/profile facts; don't assume our gain0 reference equals Product PCM.

On refusal authenticate ordering: source checks, local JOIN_PEAK boundaries then
global JOINED_PEAK decision, all before output/staging creation. An actual global
witness requires every relevant source check safe, no earlier local JOIN_PEAK,
actual global exceedance, Refuse/exit2, null global subject (or schema-valid
applicable subject on another refusal), six-decimal dbtp payload, named reason
and no published pair/unpublished stage; native lack-of-access is NOT inferred
from a missing output. Local JOIN_PEAK must identify the actual boundary/subject.
An extracted meter countermodel is labelled separately from admitted production
evidence. No source/publication access-absence claim from model-only traces.

Stage2 authenticates exact inputs/plumbing and evaluates those fixed predicates;
bounded success means only these families, not global unreachable JOINED_PEAK.
Stop on defect or precise method/capability boundary; two consolidated corrections
maximum, no unchanged repetition.2CPU-hours/512MiB per lead, no tuning, extra audio
matrix, full1927 replay, observer/native/hardware/tool/install/privilege campaign.
Carry234 resource,230 byte/CSV, originalRED stop and all wider holds by identity.
Normal CI/merge publication precedes Software execution. Keep240 open awaiting
Stage2 and move to other PM497 assignments; no fullS1/WP16/APP integration clearance.
