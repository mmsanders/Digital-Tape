# V405 F3-IF/1 ready subsets, r1

Independent Verification authorship from Software674/PR677 declaration-onlyafdc9b7902830be59e81c098dc16d4dfb4e879c3, FW1/BE1 and ADR208/209. No new firmware/checker/build-hook implementation inspected. Preserve V39841/10 semantics and all old imports; this is a new explicitly scoped route, never an edit of their assertions.

Ready executable bindings:

- **22 fwhost wake-sim scenarios:** first rendered block versus first non-silent block, ceil conversion, exact100/120ms boundaries, three clocks, cycle/millis short rollover, control149999/150000/150001us and fractional rounding, timeout/wrap/mount failure, cold fallback and diagnostic serial trigger. Four mutation controls plus four malformed-wire controls detect wrong calculation/event/id/grammar. The selftest is a **wire-predicate selftest**, not actual measurement-module execution.
- **43 single-build offline CLI vectors** (41 artifact bundles plus exclusive-output/inside-bundle usage checks): genuine field matching with explicitly SYNTHETIC Michael records, missing/mismatched/negative verdict, >20% PM-field match/mismatch, timer underreport, environment/control provenance, toolchain/build/decoded-marker/hash/serial failures, strict fields, duplicate identity/sequence, cold wake and simulation. Materialization selftest does not execute a checker or claim those outcomes have passed. A separate actual driver control rejects a deliberately inert exit0 reporter on34 cases, including underreported control, declined human verdict and absent decoded marker. Actual CLI mode enforces declared exit codes and accepted:false/physical_run provenance flags, code strings where declared, immutable inputs and offline/exclusive-file boundaries. Complete report-layout/new-state ordering/multi-build behavior remains unbound below.
- **Two actual unchanged-helper fake-port cases:** BUILD/SLEEP/WAKE bytes and a truncated final WAKE retain exact bytes, order, LF send and SHA256. Canonical helper9929ef5f4bb0c7abd5340892883661e9d38953e075f993584df3d3e60b3e47da passes locally; CI repeats. This is new payload compatibility, not another broad helper campaign, physical connection or implementation license to rewrite the cleared helper.

Commands (NEW_DIRECTORY must not exist):

`python -B tests/f3_wake_if1_r1/run.py --selftest --out NEW_DIRECTORY`

`python -B tests/f3_wake_if1_r1/run.py --host PATH/fwhost --out NEW_DIRECTORY`

`python -B tests/f3_wake_if1_r1/checker.py --selftest --out NEW_DIRECTORY`

`python -B tests/f3_wake_if1_r1/checker.py --checker PATH/f3_evidence.py --out NEW_DIRECTORY`

`python -B tests/f3_wake_if1_r1/capture.py --helper PATH/bench_capture.py --out NEW_DIRECTORY`

Host/CLI modes execute returned tools; no Product implementation is supplied here. Import this directory unchanged before covered implementation. The offline guard substitutes a fake serial module and denies real ports/network/processes/input writes/output overwrites. Every outer result has accepted:false/physical_run:false; internal synthetic physical/actual labels test the declared provenance flag only. No fixture record is Michael's sign-off, and the example.invalid PM URL is deliberately not a reviewed PM decision.

Ready coverage licenses only the declared arithmetic/wire and single-build artifact/CLI behavior exercised here, with unchanged capture reuse. **RESERVED:** the exact gaps in BINDING-GAPS.md; full F3 hook/build/control integration and criterion disposition remain incomplete until those interfaces and tests are supplied. F4 stays NOT_RUN/f4_deferred; no recording/copy implementation. Actual target timing, warm-buffer validity, I2S/audio/codec delay, stack, caps and first-board actions require separately authorized real parts/session. No real device is accessed by these tests.
