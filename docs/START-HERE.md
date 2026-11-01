# Start here — a fresh lead context

This repository is enough to resume work. Don't load every archived round or the whole
decision log.

1. Fetch main and note its commit. Read [Michael's issue queue](https://github.com/mmsanders/Digital-Tape/issues?q=is%3Aissue%20is%3Aopen%20label%3Amichael).
2. Read [CLAUDE.md](../CLAUDE.md), [STATUS](STATUS.md) and your [role charter](ROLES/README.md).
   That, plus your live issue, is the required reading.
3. Read your open assignment issue and its scope updates. No open issue for your role means
   you are unassigned. Historical documents never supply a task.
4. Read anything else on demand, for the sections your task touches:

| Role | Usually needed |
|---|---|
| PM | [Phase 3 plan](PHASE3-PLAN.md), [packages](PACKAGES/README.md), [device design](DEVICE-DESIGN.md), spec/VERSION.md |
| Software | tests/IMPORTS.json and the COVERAGE/ADAPTER files of packages you touch, engine/README.md, tools/README.md, the contract named in your issue |
| Hardware | [device design](DEVICE-DESIGN.md), [hardware status](STATUS-HARDWARE.md), hardware/README.md, spec/hw/VERSION.md |
| Verification | Your verification-lead issue, spec/VERSION.md, the spec sections and contracts it names |
| Surge | Your surge issue and the inputs it names |

Product authority is spec/; hardware authority is spec/hw/. Status never overrides the spec.
Find decisions through [the decisions index](DECISIONS-INDEX.md) and spec sections through
[spec/NAVIGATION.md](../spec/NAVIGATION.md).

Merged does not mean accepted. Acceptance is the independent disposition recorded in STATUS.
Verification authors tests for new behaviour without reading the implementation first.

## Reproduce

Raw evidence over 1 MiB lives in release `evidence-2026-09`. Before replaying a retained
bundle, run `tools/fetch-evidence.sh`, which checks each asset against its committed hash.

- Spec bundle: `tools/ci/verify-spec-bundle.sh`
- Package checks: `make -C tests/mount_draft8 check`
- Build and units: `tools/ci/build.sh`, `tools/ci/unit.sh`
- Hardware gate self-test: `make -C hardware fabrication-gate-test`. The real
  `make -C hardware fabrication-gate` must fail with CLOSED.

The golden suite is green on main; a red golden run is a real regression.
