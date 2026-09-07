# DRAFT-8 candidate — independent mount and ownership tranche

**Ready for test integration. No product-engine execution or work-package acceptance.**
Authored 7 September 2026, independently of engine implementation, in response to
`pm/phase0-test-handoff-2026-09-07.md`. This is the smallest useful mount tranche;
it does not release all of WP-06, WP-07, or PR #20.

## Contents and provenance

- `cases.py`: byte-exact fixture generator and individually assigned mount expectations.
- `mount_probe.c`: host-only public-API driver and block-device traffic recorder.
- `candidate_api.h`: relevant DRAFT-8 public declarations, transcribed solely from the spec.
- `run.py`: executable assertion runner. Missing engine, invalid JSON, crashes, timeouts,
  and unexpected results fail; there are no acceptance skips.
- `fixture_audit.py`: separate verifier metadata decoder used to audit fixture construction;
  **not a reference engine** and never linked to the probe.
- `test_package.py`, `probe_selftest.c`: fixture, checker and instrumentation self-tests.
- `rejecting_stub.c`: deliberately wrong negative control, never an acceptance implementation.
- `ownership.py`: ordinary bump-allocation/write predicates for a later operation trace adapter.
- `COVERAGE.md`, `coverage.csv`: exact boundaries; CSV lists every mount test ID.
- `ADAPTER.md`: integration contract and interfaces that remain unobservable.
- `spec/`: four supplied candidate files, preserved verbatim. `cases.py` pins all three hashes.
- `evidence/`: real logs, including the initial failure and deliberately failing engine control.

The parent repository's `spec/` courtesy copies have not been replaced. The product's
published manifest was DRAFT-7 at intake; this subdirectory explicitly targets the
PM-authorized **DRAFT-8 third-cut candidate**. Canonical issuance and comparison of all
three hashes remain required before integration/acceptance. Changed hashes require
coverage-impact review, even if only wording changed. V8R3-001 remains an open,
non-blocking documentation question; this tranche neither edits nor tests away it.

Fixtures are assembled directly from TapeFS offsets, little-endian fields and
CRC-32/ISO-HDLC. No product format routine creates them. A compact binary envelope
holds two superblocks and all four 128-block index slots, regardless of device size.
Unspecified chunk bytes are 0xA5 poison; no real cartridge contents are used.
The deterministic interval generator uses Python's seeded RNG, seed **0xD8A607**.
The checked-in fixture hash manifest also detects generator/environment drift.
Generated cases are mount-image cases, **not random edit sequences**.

## Reproduce without an engine

Requirements: Python 3.9+ (standard library only), a C99 compiler, and Make. From the
verification repository root:

```sh
make -C tests check
make -C tests/mount_draft8 check
python3 tests/mount_draft8/run.py --list
```

The new package runs ten self-tests, audits **289 fixture verdicts**, and checks
fourteen deliberately corrupted synthetic observations. `--list` reports 289 cases.
These are harness/fixture results, not 289 passing product tests. The legacy strict-C99
harness still exercises its 1,029-case sample scenario independently of this tranche.

The default `check` builds only verifier-owned negative-control/instrumentation code.
There is intentionally no default engine implementation. This command exits **2**:

```sh
python3 tests/mount_draft8/run.py
```

This command exits **1**, preserving a genuine failing probe observation:

```sh
python3 tests/mount_draft8/run.py --adapter tests/mount_draft8/build/rejecting_probe \
  --case M-base-A --log tests/mount_draft8/build/negative-control.jsonl
```

## Integrate mechanically, then run the real engine

Land this test source on `Digital-Tape/main` before the corresponding implementation,
following Structural Rule 1. PM/software supplies the **actual public header and engine
object/library paths**; none were inspected to author these tests. The placeholder
values below must be replaced with those integration paths:

```sh
make -C tests/mount_draft8 engine PUBLIC_HEADER=PUBLIC_HEADER_NAME \
  CPPFLAGS=-I/absolute/public/include ENGINE_OBJECTS=/absolute/engine/library.a
python3 tests/mount_draft8/run.py --adapter tests/mount_draft8/build/engine_probe \
  --log tests/mount_draft8/build/engine-results.jsonl
```

Run `--case TEST_ID` to replay a single failure. Each log includes the adapter binary
hash, seed, fixture hash, raw stdout/stderr, process exit, allowed result set, and
assertion failures. Default per-case timeout is 30 seconds; this is a **host test-runner
watchdog**, not a product timeout or acceptance latency requirement. Adjust it for
instrumented builds; no test is silently dropped on timeout.

Success against the engine requires exit 0 and all 289 observations to pass. It is
still only the scope in `COVERAGE.md`; it does not accept recording, rendering,
allocation writes, reset, promotion, re-spool, crash safety, or entire work packages.
Retain engine failures verbatim and escalate normative disagreement to PM.
