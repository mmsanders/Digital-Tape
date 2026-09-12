# Start here — a fresh lead context

This repo is sufficient to resume the checkpoint. Do not begin by loading every
archived round or the entire decision log.

1. Fetch main; note its commit. Read [Michael's issue queue](https://github.com/mmsanders/Digital-Tape/issues?q=is%3Aissue%20is%3Aopen%20label%3Amichael) and surface open
   human questions before technical review; do not re-ask answered ones.
2. Read [CLAUDE](../CLAUDE.md), [STATUS](STATUS.md), and [freeze record](PHASE0-FREEZE.md).
3. Read [the Phase 1 development plan](PHASE1-DEVELOPMENT.md), your
   [role instructions](ROLES/README.md), and [issue workflow](ISSUE-WORKFLOW.md).
   Read your current open assignment issue and scope updates, then the inputs below.
   No eligible issue means unassigned; historical documents do not supply a task.

| Role | Read next | Deliver |
|---|---|---|
| PM | spec/VERSION.md, spec/README.md, docs/PACKAGES/README.md, docs/VERIFICATION-INTEGRATION.md | Decisions, labeled assignment issues, gate state and exact spec issuance |
| Software | tests/mount_draft8/COVERAGE.md and ADAPTER.md, docs/VERIFICATION-INTEGRATION.md, engine/README.md, tools/README.md | Mechanical integration and covered implementation; keep uncovered code held |
| Hardware | docs/STATUS-HARDWARE.md, hardware/README.md, spec/hw/VERSION.md, WP-04/05/24 | Reproducible designs, sourced parts, auditable measurements |
| Verification | Current verification-lead issue, spec/VERSION.md, relevant spec sections and independent tests | Independent tests/result disposition; no premature implementation inspection |
| Surge | Current authorized surge issue and referenced authoritative inputs | Results, evidence and unknowns returned to Michael and the responsible lead |

Product authority is spec/; hardware authority is spec/hw/. Test-package spec copies
are authenticated historical inputs. Status never overrides the contract.
Paper review, test return and integration evidence are under docs/verification/.

“Done” in an old report does not mean merged. PR #20 is held; its positive mount
run is separate from the older provisional code on main. Verification must not read
that branch’s source, diff, private tests or mixed discussion to derive expectations.

Search the append-only DECISIONS log for relevant ADRs rather than ingesting it all.
docs/archive/pre-phase0/ is superseded round traffic; do not execute old assignments.
Original out-of-repo charters/Plan Rev B are not checkpoint dependencies: the current
agreement, package index and concrete spec/package files carry operating scope.
Report a missing requirement rather than inventing text from an absent document.

## Reproduce

Run the spec bundle gate, independent package checks, build and unit scripts:
tools/ci/verify-spec-bundle.sh; make -C tests/mount_draft8 check;
tools/ci/build.sh; tools/ci/unit.sh.
Then run make -C hardware fabrication-gate-test.
The separate make -C hardware fabrication-gate must currently fail with CLOSED.

Missing WP-11 goldens remain a separate expected CI failure. CAD requires CadQuery;
hardware CI records the tested environment. A missing dependency is not a passing test.
