# Start here — a fresh lead context

This repo is sufficient to resume the checkpoint. Do not begin by loading every
archived round or the entire decision log.

1. Fetch main; note its commit. Read [Michael's issue queue](https://github.com/mmsanders/Digital-Tape/issues?q=is%3Aissue%20is%3Aopen%20label%3Amichael) and surface open
   human questions before technical review; do not re-ask answered ones.
2. Read [CLAUDE](../CLAUDE.md) and [STATUS](STATUS.md). Required reading is capped at
   four documents plus your issue — see CLAUDE.md §4 and your charter. The table below
   is **read on demand**, for the sections your tranche touches, not a mandate.
3. Read your [role instructions](ROLES/README.md) and [issue workflow](ISSUE-WORKFLOW.md).
   Phase scope and parked work are in [the roadmap](PACKAGES/README.md).
   Read your current open assignment issue and scope updates, then the inputs below.
   No eligible issue means unassigned; historical documents do not supply a task.

| Role | Read next | Deliver |
|---|---|---|
| PM | spec/VERSION.md, spec/README.md, docs/PACKAGES/README.md, docs/VERIFICATION-INTEGRATION.md | Decisions, labeled assignment issues, gate state and exact spec issuance |
| Software | tests/IMPORTS.json (every imported verifier package), the COVERAGE/ADAPTER files of the packages your tranche touches, engine/README.md, tools/README.md, docs/WP11-CLI-CONTRACT.md | Mechanical integration and covered implementation; keep uncovered code held |
| Hardware | **Parked through Phase 2.** On resume: docs/STATUS-HARDWARE.md, hardware/README.md, spec/hw/VERSION.md, WP-04/05/24/25 | Reproducible designs, sourced parts, auditable measurements |
| Verification | Current verification-lead issue, spec/VERSION.md, relevant spec sections and independent tests | Independent tests/result disposition; no premature implementation inspection |
| Surge | Current authorized surge issue and referenced authoritative inputs | Results, evidence and unknowns returned to Michael and the responsible lead |

Product authority is spec/; hardware authority is spec/hw/. Test-package spec copies
are authenticated historical inputs. Status never overrides the contract.
Paper review, test return and integration evidence are under docs/verification/.

“Done” in an old report does not mean merged, and merged does not mean accepted:
acceptance is the independent disposition recorded in STATUS. Verification still
authors tests for new behaviour without reading the implementation first.

Search the append-only DECISIONS log for relevant ADRs rather than ingesting it all.
docs/archive/pre-phase0/ is superseded round traffic; do not execute old assignments.
Original out-of-repo charters/Plan Rev B are not checkpoint dependencies: the current
agreement, package index and concrete spec/package files carry operating scope.
Report a missing requirement rather than inventing text from an absent document.

## Reproduce

Raw evidence over 1 MiB lives in release `evidence-2026-09`, not the tree. Before any
command that replays a retained bundle, run `tools/fetch-evidence.sh`, which verifies
each asset against its committed `.sha256` and refuses a mismatch.

Run the spec bundle gate, independent package checks, build and unit scripts:
tools/ci/verify-spec-bundle.sh; make -C tests/mount_draft8 check;
tools/ci/build.sh; tools/ci/unit.sh.
Then run make -C hardware fabrication-gate-test.
The separate make -C hardware fabrication-gate must currently fail with CLOSED.

The golden suite is green on main; a red golden run is a real regression. CAD requires CadQuery;
hardware CI records the tested environment. A missing dependency is not a passing test.
