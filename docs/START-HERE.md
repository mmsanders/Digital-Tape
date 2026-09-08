# Start here — a fresh lead context

This repo is sufficient to resume the checkpoint. Do not begin by loading every
archived round or the entire decision log.

1. Fetch main; note its commit. Read [FOR-MICHAEL](FOR-MICHAEL.md) and surface open
   human questions before technical review; do not re-ask answered ones.
2. Read [CLAUDE](../CLAUDE.md), [STATUS](STATUS.md), and [freeze record](PHASE0-FREEZE.md).
3. Read [the current brief](REVIEW/README.md), then your role’s inputs below.

| Role | Read next | Deliver |
|---|---|---|
| PM | spec/VERSION.md, spec/README.md, docs/PACKAGES/README.md, docs/VERIFICATION-INTEGRATION.md | Decisions, bounded briefs, gate state and exact spec issuance |
| Software | tests/mount_draft8/COVERAGE.md and ADAPTER.md, docs/VERIFICATION-INTEGRATION.md, engine/README.md, tools/README.md | Mechanical integration and covered implementation; keep uncovered code held |
| Hardware | docs/STATUS-HARDWARE.md, hardware/README.md, spec/hw/VERSION.md, WP-04/05/24 | Reproducible designs, sourced parts, auditable measurements |
| Verification | docs/REVIEW/verification-lead.md, spec/VERSION.md, relevant spec sections and independent tests | Independent tests/result disposition; no premature implementation inspection |
| Surge | PM’s bounded assignment and referenced spec sections | Proposal with evidence and unknowns returned to PM |

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
