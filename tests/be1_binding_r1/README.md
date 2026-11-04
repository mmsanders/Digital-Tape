# BE1-IF/2 independent executable binding r1 (V382)

Authority: BE1/FW1, V382 and ADR204 at Product51d0f8f. Declaration received at
97a5502216d1822d1708edad922e856b08dc909b, blobf7cd579eecadc827aacb4449035e361324ab2d88,
SHA256 d2a41dbdee9ee8654bbaa465c2cd358ef840b12b9c80a28845cc9008548faffa.
Authored without reading a new checker/helper implementation. Neither exists at input.
Old publications remain unchanged. This ready subset does not clear the entire kit.

## Execute

Use Python3.10+ and canonical LF `tests/golden` from the independent publication.
On Windows export those versioned bytes with Git (do not normalize/rewrite old
working files or regenerate references). Paths below are relative to the repository.

```
python -B tests/be1_binding_r1/run.py --selftest --golden tests/golden --out build/be1-selftest
python -B tests/be1_binding_r1/capture.py --selftest --out build/capture-selftest
python -B tests/be1_binding_r1/run.py --checker PRODUCT/firmware/bench/tools/bench_evidence.py --golden tests/golden --out build/be1-product
python -B tests/be1_binding_r1/capture.py --helper PRODUCT/firmware/bench/tools/bench_capture.py --out build/capture-product
```

Each output directory must be new. Runner generates the verifier-owned bundles
and expectations deterministically; every Product invocation receives only the
bundle, report path and independently authenticated frozen references. Expectations
are not passed to Product code. The CLI is exactly BE1-IF/2. No renderer or target
is run. Large raw fixtures are generated locally, not committed or uploaded.
Candidate results must name the exact candidate commit in the disposition in
addition to the checker/helper SHA256 recorded by these runners.

109 ready bundles cover all seven cases: digest and stream positives, altered
PCM with updated device and file hashes, WAV/PCM confusion, frame±1, reference,
command and missing-case controls. They also cover LF/CRLF, malformed/truncated
records and stream runs, duplicate digests, live underruns, hashes/file lists/paths,
candidate/toolchain, simulated/mixed/absent/provenance/order states, F2 actual/reserve,
sum/RAM/rodata/stack limits and boundaries, and the unambiguous F5 position/removal/
missing-sequence/witness checks. No witness is fabricated. An intentionally false
`actual` marker appears only in a negative provenance-conflict fixture.

The offline execution guard denies and records attempted sockets, serial imports,
subprocesses, native dynamic loading, external reads and writes except the named
report. Bundle snapshots detect mutations. It permits Python runtime, checker
directory and reference reads; no online Python package installation is involved.
This Python audit boundary is an instrumented test method, not an OS sandbox or
proof against deliberately bypassing Python instrumentation. Ordinary checker
effects and attempted effects both fail this suite, even if the checker catches
the denied exception. Controls demonstrate four denied effects plus false flags,
states, blanket success and hidden diagnostics. Harness-only stubs emit known
reports; they are not a substitute Product checker or an acceptance oracle.

Four capture cases inject a fake `serial.Serial` module with byte/CRLF/run
fragmentation and a digest-shaped line embedded in PCM. No pyserial is installed
or real device opened; only `V382_FAKE_ONLY` is allowed. Exact raw bytes, no command
writes and no other port/network/device access are required. Truncation and newline
rewrite controls fail. Fake EOF terminates the harness stub only; the real helper
must stop at the complete protocol digest, including stream framing. Timeout,
partial-output retention, send terminators and info completion need declaration
clarification before the remaining cases or helper behavior can be licensed.

## Explicit remaining declaration conflicts

V382 returned these to Software652 before publication. This package licenses only
its ready covered behaviors, not assumptions for the following unresolved cases:

- F5 first-problem precedence can hide supplied verify failure/malformed data behind
  missing witness/sequence. BE1 requires supplied failure to remain visible/nonzero.
  Full F5 witness/card/manual-verify combinations await corrected aggregation rules;
  there is no synthetic physical-positive or independent witness acceptance here.
- Candidate rules name a `firmware_hex` file role missing from the closed file schema.
  Ready F2 bundles include the named firmware.hex/SHA256SUMS facts; role-key validation
  awaits the explicit declaration fix, not an invented input field.
- Superseded observations are retained but exit semantics conflict with section1's
  any-error rule. Failed-then-retried aggregate tests await a single declared rule.
- Capture timeout/result/partial bytes, `info` without a digest, and send termination
  need exact rules. The helper must not ship these untested behaviors.

The matrix's remaining conflicts are dependencies on corrected declarations, not
a claim that no schema was supplied. Simulation always stays nonphysical and
incomplete. Positive artifact consistency never supplies target/package acceptance.
