# WP14 P2-R1 complete independent authored package

Verification #146; normative Product ADR165 merge
`6f362f093435ab1a1501055b3bb1cdbe37a5b04c`. Authored without reading WP14
implementation. E-1 and original paper work are carried, not repeated. See
[coverage](COVERAGE.md), [transport](NATIVE-TRANSPORT.md) and the
[final preflight](../../findings/P2-R1-WP14-AUTHORING-2026-10-06.md).
Publication completes **test authoring**, not Product acceptance or native runs.

```sh
python3 tests/wp14_r1/check_pins.py
python3 tests/wp14_r1/selftest.py
python3 tests/wp14_r1/amendment_selftest.py
python3 tests/wp14_r1/completion_selftest.py
python3 tests/wp14_r1/catalog.py
```

These are verifier selftests, zero Product runs. INPUTS.json, ADR164-INPUTS.json
and ADR165-INPUTS.json preserve all issued inputs and exact hashes. The frozen
spec copies, E-1 overlay/manifest and previous evidence remain byte-identical.
ADR165 resolves the collision inside this package; no separate collision tranche.

After Software's byte-identical import/binding, use the final exact head:

```sh
python3 tests/wp14_r1/runner.py /absolute/path/to/tapectl --head FULL_SHA > image-linux.json
python3 tests/wp14_r1/native.py --platform linux --head FULL_SHA --evidence-dir /absolute/path/to/capture /absolute/path/to/transport > native-linux.json
python3 tests/wp14_r1/qualification.py --head FULL_SHA /absolute/path/to/six-json-bundle
```

Repeat image/native runs on macOS and Windows. Image census: 79 cases and
11 causal output controls. Native census: Linux 97, macOS/Windows 96 applicable
static requests each, plus all generated native provision-replay cases. The
closed census gate rejects omitted cases, duplicates and missing replay.
No inapplicable Linux path test is a Windows/macOS skipped case.

All ten unchanged WP11 reference WAVs and mandatory full C60 run on bare and
whole images, and native virtual targets; exact bytes/final frame, no tolerance.
Only temporary regular files/owned virtual devices are used. Full C60 needs
several GiB scratch; the 64 GB target is sparse, and can consume its full apparent
size on a filesystem without holes. Capture payload/replay assets can exceed
1 MiB: retain in CI/release assets with hashes, never commit them to the repo.

Transport owns capture only; expectations/verdicts stay here. Actual no-op,
hidden-error, non-NULL, native failure and referenced-service controls must run.
Raw captures, OS builds, binary/head hashes and fault linkage must be authenticated,
not accepted from JSON assertions. Git identity and unchanged Phase1/golden
qualification are mandatory. Neither completeness nor oracle CI claims acceptance.

[Michael's checklist](REAL-CARD.md) covers macOS provision/load/reinsert/README,
ten pulls, Windows10 initial readback and fresh provision/load/reinsert, >4GiB
capture. Tested release hashes are required before script-ready delivery.
A1/A2/A3/A6 physical/named-OS holds survive software CI; Server2025 is supplemental,
not Windows10 acceptance. Keep #146 open across stages.
