# Verification232 Stage1: exact artifact method and actual-return obligations

Stage1 AUTHORING ONLY. No new executable has been run and no missing predicate is
accepted by this publication. Stage2 stays pending Product485's actual fresh return.
Authority PM483 / Verification232 (issued 2026-10-20T16:42:25Z); paired Software485.
Activation read canonical AGENTS.md, full CLAUDE.md, STATUS.md, Verification charter
and live232/485. Product input c617b0c012552869e2dd359e70204ae28909bed3;
fresh main d5ae04d44c60a6371e3adb7c8f292bfe528e8968. Verification input
4a1a09a0e618bba4685312da8721275e9b2ce9c3. No new Product implementation or private
tests inspected to author these expectations. No subworkers. GitHub only.

## Exact shipping exhaustion: adequacy and execution

The unchanged `tests/wp16_shipping_exhaustion_r1/runner.py` already accepts
`--binary`, `--sha256`, `--source`, `--out`: it can launch an external artifact
without rebuilding. Its imported `judge` remains unchanged. In contrast,
`findings/P2-201-DISPOSITION-2026-10-18/shipping.py` unconditionally runs Cargo and
is an independent rebuild experiment: do not use that script to establish the
identity of the downloaded artifact. It has not been silently repurposed.

`external.py` adds only artifact/dependency authentication and host/raw-file
binding around the existing runner. It requires the approved kit SHA256
`ffb0f78ac3980fa1bb130f0aff22d53ebb100ed3323a8e50ba62a6ee1819c865`, its unique
`ingest.exe` member AND supplied executable SHA256
`d923613badda95baeb387d5415d5212a5dedb7c5c7144b21874479babd178f5b`.
Observation `d544b6f5c82e653842625080a87ac63cb52353aaeca62494dd5d08eedb844d9a`
cannot substitute. Exact admitted source is the existing Stage1 `ordinary.wav`,
SHA256 `d36663d1e4f05abaac699a6c14e0fa86724db9b4decdb8c96abe0c9d1f645821`.
Missing/different input is rejected before launch. Fetch/authenticate the existing
source pack with `tests/wp16_ingest_stage1/asset.py` and ASSET.json at the input
commit: archive SHA256 `980c57c7616bbf7b1b8870f8c9b0da9ab8c7ae4678871788b4c60d9524a67edb`.
No new audio generation or full source campaign is needed.

Use a normal Windows runner, ordinary private files, unchanged security. Example
from repository root (replace operands with local paths; out must be absent):

```powershell
python -B findings/P2-232-METHOD-2026-10-20/external.py --kit KIT.zip --binary EXACT_ingest.exe --source ordinary.wav --out FRESH_RESULT
```

Add `--authenticate-only` for a no-execution binding check. Do not rebuild, relabel
a different executable, inject an allocator, or replace native child statuses.
Import the merged source verbatim; PINS.json binds dependencies to the preexisting
tree. Record imported commit/tree and each source hash, Python/version/architecture,
actual OS edition/build/InstallationType, run/job URL, exact commands and operands.
Adapter records host facts, hashes, raw per-file inventory and rechecks identities
after execution. `BINDING.json` is provenance, not a PASS oracle.

Exactly seven rows: unlimited then 3/4/6/8/12/64 MiB. Each includes same-cap
`--version` load control followed by the full `--out DEST --length 60 f0` path.
The existing native launcher calls SetInformationJobObject(PROCESS_MEMORY), creates
the actual child suspended, assigns it to that Job, then resumes it. Native DWORD
exit, hex status, timeout, stdout/stderr bytes and hashes remain visible. For each
row retain raw output-parent census, unchanged foreign sentinel, any unpublished
stage, and every successful audio.wav/manifest.json. Success bytes must equal that
same executable's admitted unlimited pair; ordinary exhaustion must exit exactly1,
emit its tool diagnostic and leave no DEST/stage/unowned entry. Abort, signal,
timeout, diagnostic absence, foreign damage or byte mismatch remains RED. At least
one actual bounded clean exit1 is required. Loader refusal is an incapable row,
not clean tool exhaustion. Absent/invalid source is not exhaustion. Never derive
PASS merely from the count of nonzero rows.

Carry the existing load/positive/red controls unchanged. Run existing selftest.py
and new selftest.py. Where existing access permits, run the existing `baseline-red`
mode on authenticated original executable SHA256
`0e1ef2cb4f283eb876f08019222da5d3ac744ec30d49f020a2e87323f31bcac1` and the same
source: require its actual 6MiB 0xC0000409 and neighbouring clean/positive rows.
Keep its RESULT contract_pass=false. Known retained RED is at input main
`findings/P2-201-EXHAUSTION-2026-10-18`; unavailable fresh access is explicitly
reported, never an invented RED or an unrelated failing executable.

Return original RESULT/BINDING/FILES, raw row stdout/stderr, saved output pairs,
all failures and census/sentinel facts; retain code dependencies and authentic
binary transport. Publish bounded ZIP plus size/SHA256 and stable downloadable
URL, run/artifact IDs, producer source commit and exact import before execution.
Independent Stage2 fetch must authenticate archive and inner inventory and reapply
the unchanged judge to actual raw rows. A Software PASS label or green CI is not
the judgment. Preserve partial evidence on failure; no dense sweep after a
capability stop. Resource ceiling: 2 CPU-hours /512MiB NEW compressed evidence.
Server execution establishes Server only. macOS enforced exhaustion remains separate.

## INTERNAL: actual witness or finite complete reachability argument

Ground this in issued APP S1 refusal/outcome semantics and INGEST preflight,
resource and publication contracts, not the spelling of a diagnostic. Candidate
is S1 b9f430c8c9b33532abf07eea0ed2653310639f2d. A genuine witness supplies immutable
admitted input/name/options/profile and exact executable/source/host bindings,
full invocation, native process result and raw report/stdout/stderr, independently
parsed outcome/subject, and output/stage/sentinel state. Show the actual guarded
condition producing INTERNAL in this run. A parser fixture exercises parsing only;
an injected status/test label does not witness actual shipping reachability.
APP annex section2 places INTERNAL in the closed exit1 list as a genuine tool
failure, never a substitute for a specified source refusal; generic UI failure
mapping carries. Parse the actual report with the existing S1 oracle unchanged.

An unreachability return must enumerate every production INTERNAL emission site
and propagation route in the pinned source/dependency closure, with exact file/blob
and callsite/guard references; distinguish normal entry from feature/test-only
entries. State the full admitted domain and build/OS assumptions. For each site,
provide the invariant at entry, initialization, preservation through every relevant
loop/pass/call/error edge, arithmetic/conversion/rounding conditions, and contradiction
with its emitting guard. Cover plane/output-length consistency, deterministic gain
refinement termination/convergence, decoder initialization and any other returned
site; this list from prior209 is a starting obligation, not an assertion of completeness.
Account for malformed/admitted inputs, resource failures, mutation detection and
dependency failure classification: an assumption that all calls succeed cannot
prove the failure surface unreachable. Separate memory-safe implementation promises
from actually established invariants. Mark omitted dependencies/branches UNPROVED.

Detecting obligation: identify a guard/invariant whose violation would falsify each
argument. Supply a concrete counterexample if one exists; otherwise give the finite
reason a counterexample is excluded and a narrow adversarial/control construction
showing the discriminator rejects a violated invariant. Source-extracted isolated
fixtures may test that discriminator but do not prove production reachability or
completeness. No broad reexecution campaign is requested. Verification will check
enumeration against pinned source only after this publication, and label each site
witnessed, proved under explicit assumptions, or UNPROVED with the smallest gap.
One bounded family cannot discharge all production paths.

## Global JOINED_PEAK beyond the accepted silence family

INGEST contract sections3-5 require exact presentation counts, quantized source
payload concatenation, 88200 all-zero folder-gap frames, final assembled true-peak
measurement including every join/gap, and named refusal before output if reported
peak+0.1 > -1 dBTP. No gain changes, fades or padding to rescue the join. Preserve
specified PRNG/reset/draw order, ties-to-even quantization and pinned scalar profile.

Actual witness route: supply admitted immutable non-silent sources/order/folders,
trim/effective and converted frame counts, exact profile and executable, independent
expected boundary/final measurement, actual raw S1 outcome/subject/exit and cleanup
receipts. Show why source guards pass and assembled guard fails at the reported
boundary. Retain comparison controls on each side of the same condition; a parser
JOINED_PEAK line alone is not a witnessed tool outcome.
APP annex section2 requires exit2 and a six-decimal `dbtp` payload; JOINED_PEAK's
subject may be null. Do not demand a fabricated boundary subject for the global
ID or confuse it with the separately named JOIN_PEAK boundary outcome.

Global proof route: quantify over ALL currently admitted source PCM/rates/trim/counts,
source lengths (including short/unmeasurable), endpoint/sample phases, neighbouring
sources and folder gaps. Identify actual meter/filter support and zero extension,
resampler/gain/dither/quantization arithmetic/reduction order and rounding. Relate
the exact evaluated/refined source sample coordinates and reconstruction state to
those at EVERY assembled join and gap, including endpoints and filter tails. Derive
a valid bound after constant gain, final quantization and concatenation; independently
safe isolated peaks do not imply a safe assembled peak. Include finite-precision
error and threshold comparison, not just real-arithmetic inequalities; preserve
the existing ceiling and guard margin. Prove completeness of join enumeration and
propagation to actual report/exit/publication behavior.

Detecting obligation: give an actual counterexample/control to a proposed universal
step (for example where the isolated-window-to-joined-window premise fails), or a
complete justified argument excluding it with a falsifiable boundary condition and
narrow discriminator control. No new audio campaign is authorized just to search
for an example. If support, rounding, coordinates, error bound or domain completeness
is missing, identify precisely that missing fact and return global UNPROVED.
Do not introduce an admission restriction, relax audio tolerances or treat a finite
test census as a theorem. Prior209's finite canonical zero-PCM WAVE family remains
accepted only at its documented all-zero/silence bounds, not globally.

## Carriage and stop

Carry230's 1640 byte identities, native publication/CSV judgments and their explicit
transport/PML/failed-open limitations without replaying the unchanged campaign.
SOURCE_LEVEL and DEST_NAME_INVALID witnesses, prior Linux report-write positions,
and bounded source/math results remain at their published scopes. S2 standalone
host PASS at 1ad813d carries under231 source/oracle identities; Software484 owns
current-main integration. No new S2 round absent a substantive behavior-changing delta.
A6 linkage remains held under223; S3 has no cleared platform. No overall459/454,
fullWP16/APP, zero-access absence, PML decoding or universal allocator clearance.

Stage1 is published only after ready PR, green normal CI and a merge commit on
Verification main; return exact import/method directly to485. Keep232 OPEN with
Stage2 pending actual fresh evidence. Stage2 authenticates then publishes bounded
PASS or smallest precise blocker for each family and returns485/483/459/454. At most
two consolidated substantive correction returns; the same unresolved finding twice
without new evidence stops. No polling, physical/card/security/install changes or
new human task. GitHub issue comments carry the handoff.

Local authoring checks: existing judge 12 detecting controls and new binding 8
detecting controls pass. An authenticate-only check against the retained approved
kit, actual d923 executable and original ordinary.wav passed all identities with
`executed=false`. This was no new resource execution or acceptance evidence.
