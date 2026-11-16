# Start here

1. Read [CLAUDE.md](../CLAUDE.md) and [STATUS](STATUS.md). With your task, that is the
   required reading.
2. Read anything else only for the sections your task touches:

| Working on | Usually needed |
|---|---|
| Firmware | `firmware/bench/README.md`, [FW-1](WP17-FIRMWARE-CONTRACT.md), `engine/include/tape.h` |
| Desktop tools | The contract for the tool ([tapectl](WP14-CLI-CONTRACT.md), [app](WP15-APP-CONTRACT.md), [ingest](WP16-INGEST-CONTRACT.md)) |
| Hardware | [Device design](DEVICE-DESIGN.md), [hardware status](STATUS-HARDWARE.md), `hardware/README.md` |
| Engine or format | [ENGINE-CHANGES](ENGINE-CHANGES.md), [spec/NAVIGATION.md](../spec/NAVIGATION.md), `tests/IMPORTS.json` |
| Planning | [Phase 3 plan](PHASE3-PLAN.md) and [ledger](PHASE3-LEDGER.md), [packages](PACKAGES/README.md) |

Product authority is `spec/`. Status never overrides the spec. Decisions from ADR-210 on
are in [DECISIONS](DECISIONS.md); earlier ones are indexed in
[the closed log's index](archive/DECISIONS-INDEX-ADR-001-209.md). `docs/archive/`,
`docs/REVIEW/` and `docs/verification/` are history and evidence: never a source of tasks.

## Build and check

- Engine and unit tests: `tools/ci/build.sh`, then `tools/ci/unit.sh`
- Everything the engine gates check: `tools/ci/all.sh`
- Firmware off target: `make -C engine all && make -C host && make -C firmware/bench/host`,
  then `python3 firmware/bench/host/run_checks.py --fwhost build/fwhost/fwhost --tapectl build/host/tapectl --out build/fwhost/checks`
- Firmware for the Teensy: `pio run -d firmware/bench -e teensy41`
- Hardware gate self-test: `make -C hardware fabrication-gate-test`. The real
  `make -C hardware fabrication-gate` must fail with CLOSED.

Raw evidence over 1 MiB lives in release `evidence-2026-09`; `tools/fetch-evidence.sh`
fetches and verifies it. A red golden run is a real regression.
