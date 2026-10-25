# [Verification]318 pre-code discovery integration expectations and preflight

PM576/578/318; inputs Product1cf5577099ecc4445e8465bfb9addb1d780008eb,
Verificationbd9be79a05993981dabc5327d0cf90400305ed4d; spec tree
e07292dc75ea183602aacd2cd668036934506c2c, unchanged APP-1/APP-1A.
318updated25Oct03:10:34Z. Current canonical four/live bodies/comments read;
Michael manually selected both open Verification issues. No Software578 app
implementation/private tests inspected; no new interface implementation supplied.
PRE-CODE Software declaration5786394000771 arrived while PR319 was still unmerged;
Software explicitly has not implemented. Final tests bind children::TAPECTL,
DT_TAPECTL_SHA256/DT_TAPECTL_VERSION,12hex build ID,completion+2s scheduling,
10s timeout and strict current-report freshness before publication/implementation.
This package freezes missing behavior before new discovery app code. It does not
clear implementation, child build or live enumeration.318 stays OPEN for actual
Software interface/source/build/controlled evidence after publication.

## Existing facts and exact boundary

Carry independent S2 policy/report tests from wp15_app1a_r1 and wp15_cards_make_r1,
and Verification231/4a1a09a0's exact standalone S2 integration disposition:
accepted1ad813d integrated469/10faee5. Do not rerun its39/actual/platform controls.
The new app reuses the accepted parser/report vocabulary and backend, rather than
copying another parser or introducing raw-device access in the app.305/306 and
286/297/299 source/components carry only their existing exact scope.

Original bundled tapectl SHA82798af2 predates S2 and is NOT a cards child. Leave
the authenticated564 bundle untouched. A newly built child needs a new manifest/
pin/version and source/engine/lock/compiler/protection provenance; do not transfer
old tapectl binary clearance to it. host/Makefile sets TAPECTL_BUILD_ID to the full
source HEAD (plus-dirty if modified) by default. The declared BUILD-only command
may override HEAD_ID to its source's12hex prefix; report version is then exactly
`tapectl-wp15-s2+<source SHA first12hex>`, bound to full40hex source and64hex binary
pin. No `unknown`, dirty or old binary substitution. Capture the exact macro/build
command and use the explicit non-test tapectl.exe target: default host `all` also
builds tapectl-test. No invocation of unrelated provision/load/verify/make/test build.

### Accepted-path source preflight (paper only)

The accepted/current discover_win.c blob is
`49e0f7e930756a64739b2d49c2b43f91ea1e9d84`; discover.c/discover.h and report.c/h
remain identical to accepted1ad813d. Current engine tree remains
`d96b4245e04d74078f8938744b1394c3018516f7`. Full tapectl.c now has other independently
issued host work; its cards dispatch must be crosswalked in the new build, not
blanket reaccepted. Current tapectl.c blobd76fe3f6bf7f12f35fb2c25c8170ed05dcfb8f6a.

Read-only source review of the **already accepted** S2 path finds CreateFileW
desired-access0 for disk/interface/volume handles, existing Windows inventory and
registry queries, DeviceIoControl operations for storage device number/property,
geometry, OS drive layout and volume extents. No ReadFile/WriteFile/raw-sector
parse/unmount/write-access open in discover_win.c. cards dispatch calls that
enumerator, pure discover_policy, ordinary stdout/report output; it does not call
the destructive device/session provider. Unknown query/volume/census facts remain
unprobed/unavailable. This substantiates the *source* metadata-only boundary, not
actual client execution, universal device-open absence or physical safety.

**NO LIVE ENUMERATION ADMITTED NOW.** First Software declares exact proposed child
source/current main, build ID/version, binary hash, app pin registry, ordinary
unelevated token/context, owned report/job paths and expanded argv. Verify the
new binary matches accepted cards call-path/production no-test compile and unchanged
engine; then publish a separate specific live-source/binary/argv admission if
justified. At most one owned-app/current-user metadata enumeration may be proposed.
No raw data/partition reads, write-mode open, unmount/write, physical handling,
observer/VHD, new native method or provider hunt. No sample/self-log can prove G1.
If those facts cannot substantiate the boundary, keep live scope HELD and dispose
only covered integration source. No need to block component authoring on a card.

## Minimum declared internal bindings

Software declares names/type wiring before code if needed; tests bind observable
behavior, not a redesigned public API. Reuse the current authoritative snapshot/
app-state/card_line surface and permanently false Make. One coordinator owns poll
lifetime/current ticket; no independent UI/host parser fork. Actual production
functions and actual completion closure must be exercised by the test adapter.
Test-only typed child outcomes/ordinary Command construction may be controlled;
no fake executable, shipping selector, running-app injection or real enumeration.

contract.py --emit supplies23 rows, using existing independent report parsing,
plus controlled timer schedules. Adapter returns actual normalized rows/requests/
traces/source refs. `--input --candidate` applies only the component qualifier.
Metadata and booleans alone do not establish linkage or actual absence: independent
source/raw/adapter/current-build review is mandatory before clearance.

| Area | Frozen expectation |
|---|---|
| Card line |0offered `Put a card in.`;1offered `Card ready (N GB).`;2+ `Leave just one card in the computer.`. Decimal GB rounding (63.6/64.4→64;128GiB→137), no lists/picker/path text. Tests deliberately avoid unspecified half-ties. Discovery is a hint, never a safe-card/Make authorization. |
| Unknown/unprobed | Unknown required OS facts never become offered. Preserve aggregate unprobed counts for raw/details, do not display refused disk names or invent sizes. One valid candidate plus unknowns is still one hint, with Make disabled. Policy implementation itself carries existing independent tests. |
| Exit/report precedence | Reuse accepted report::Tool::Cards validation/version/nonce/ordering/partial semantics. Nonzero/crash/spawn/timeout cannot use stale success stdout. This NEW app-discovery hint requires exit0+complete stdout+usable current nonce/version report; missing/wrong/partial report means unknown/no hint, while the actual child exit remains unchanged. This is new freshness binding, not a change to accepted INGEST or standalone command semantics. Wrong report cannot select ID-specific failure text. No stderr word chooses outcome. |
| Output completeness | Exactly one last summary; offered equals unique card rows; positive integer exact sizes, valid counters; no unknown/duplicate/refused/provisioned records, duplicate paths or truncated summary. Malformed output yields generic failure/no retained current hint. No second safety/layout parser in app. |
| Polling | Nominal2s after previous terminal while not Making; single-flight, no overlapping child/catch-up burst, work outside coordinator/UI lock. Controlled schedules use first due tick2000ms: terminal3000→next5000; slow terminal7000→next9000; Making2000/4000→first6000; stopped→none. Logical test time only, not new native wall-clock tolerance. |
| Lifetime | Current ticket/generation only; stale/wrong-job/duplicate completion cannot publish; fresh distinct nonce/exclusive report per invocation.10s timeout invalidates→cancel→child terminal→owned cleanup; shutdown stops polls then same sequence; old terminal/cleanup precedes replacement. No retry after actual tool/consent rejection; ordinary enumeration failure remains a reported runtime outcome, not a fabricated tool denial. |
| Invocation | Pinned newly declared S2 child beside app executable, cwd-independent/nonshell/unelevated. Only `tapectl.exe cards --report PRIVATE --report-nonce FRESH`, options may reorder. Reports/job/control under per-user app-owned root, never source/card; no app device open. |
| Hard hold | Even valid music+label+one offered hint leaves Make false, no make/elevation/device call or shipping fake flag. Failure clears old hint. Source/foreign sentinels unchanged; cleanup only owning terminated job, no external cleanup call. |

Report bytes/stdout/stderr/current ticket/argv/nonce and renderer capture refs
must remain separately inspectable, with private device paths redacted only in
the public transport. Native metadata/real UI claims require their own admitted
actual originals, never model booleans. New app binary is a new identity:315/316
old app startup/control facts do not transfer. No source or live clearance now.

## Return boundary

This is the independently PUBLISHED **test/preflight readiness handoff**, not
Software acceptance or final318 return. Next owner Software578 declares the narrow
interface/build/pin mapping, imports this exact package before implementation,
then returns exact source/component/raw/CI. Temporary paired dependency is recorded
once; no polling loop. No missing capability is claimed for covered source work.
Verification later judges ready actual return under Michael's manual activation,
maximum two consolidated exact-delta corrections; normal current-base protections.
No native/readers/A4/A6/INGEST/S3/fullAPP/G2/physical/shipping Make clearance.
Both listeners PAUSED. Stop this activation after direct paired/PM handoff.
