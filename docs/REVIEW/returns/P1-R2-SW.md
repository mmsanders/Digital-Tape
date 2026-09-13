# P1-R2-SW return — Software Lead

**Issue:** [#50](https://github.com/mmsanders/Digital-Tape/issues/50) (`software-lead`, updated `2026-09-12T11:31:07Z`).
**Input main:** `7fe9942a847c6decfa40ea75aa08d16ea730bb39`. **Returned:** 12 September 2026 UTC.
**Status:** integration complete. **Next owner:** PM; Verification for independent disposition.

Integration only. No engine or header implementation, no mount split, no allocator
import, no PR #20 merge, no repository-setting change. **A merge authenticates
integration; it is not independent package or product acceptance.**

## 1. PR #47 — reviewed, updated, merged

Reviewed head `74a9c2bf7a0cff4f449aedb3b63daa5771bb7e2a`; merged as `8d9e8bd`.

Updated onto current main by **merging main in, not rebasing**, so Hardware's
history and any checkout stay valid. One conflict, `docs/STATUS-HARDWARE.md`, which
PM had rewritten on main as its disposition of this same return. Resolved by taking
PM's version: PM owns the status record, and its text already carries this branch's
substantive facts. The vendor-access narrowing that PM's table drops survives in
`hardware/sourcing/2026-09-12-parts.md`, which the branch adds. No Hardware method,
measurement claim, evidence file or provisional conclusion was altered.

Checks reproduced on the merged result: `spec-check`, `thermal-check`, `mech-check`,
`solenoid-test` (24 checks + red-proof), `atomicity-test` (43 + red-proof),
`fabrication-gate-test` (3/3) all pass; `fabrication-gate` → **exit 2, CLOSED, five
blockers**; solenoid verdict remains **PROVISIONAL**. Engine side unaffected. PR CI
green on every job; `golden` red as expected.

**Finding returned on the PR — not blocking, and not fixed by me.** The new
supply-envelope criterion has no *retained* automated negative control. It works — I
verified substituting the NXP `74HC221DB112` 4.5–5.5 V listing makes `check_criteria`
return the expected failure — but nothing in `thermal/test_solenoid.py` pins it. The
`--mutate` path proves only the generic fail-open, which predates this change and
would still pass if the supply-envelope inequality were deleted. Per CLAUDE.md §1
that criterion currently rests on a one-off manual demonstration. I did not write the
test: `hardware/` is Hardware's, and a test asserting their criterion is their method.

## 2. Hardened package import — exact

Every tracked file and mode under `tests/ops_draft8/` replaced with the verifier tree
`4a862fa69ccb2fc4c9afe59c9c9161c3470f9263` from `dcc4d7cdb357cf0b082071390c762c25b650f617`.
The directory was removed from the index and re-extracted with `git archive`, so no
byte or mode passed through a copy. The product subtree hash reproduces `4a862fa6…`
exactly.

| Mode | Blob | Path |
|---|---|---|
| `100644` | `6857187cb515597d9a935be06a3d06f2e50cab18` | `ADAPTER.md` |
| `100644` | `5fb6f8786c9a0fd38f00fa7a97bfd84bffdcd84b` | `COVERAGE.md` |
| `100644` | `7ed146c55b7c46d73de8b1b75726d0ac7381fb50` | `README.md` |
| `100755` | `55e0a234d456623f20306ae00c099ace90f41b7e` | `_synthetic_adapter.py` |
| `100644` | `443be133190bff00c4b39292ee723008f91e2bd9` | `evidence/runner-selftest.jsonl` |
| `100644` | `b8d40fe1e97839c0515570b271c237fae6c678ff` | `evidence/selftest.log` |
| `100644` | `62cc3190b08ad136a08b12ea45fa4d5d566b7cec` | `hardened.py` |
| `100644` | `213b5526044532f314e9d8ab1bf7ec5ee74beb2a` | `oracle.py` |
| `100644` | `175bf17982d487daebf4d660f4d317efb548e21d` | `replay.py` |
| `100644` | `828487c25d3d34f5e1df798b4f84bfd5d8714518` | `runner.py` |
| `100644` | `edfcc4f164f19b6de288744c64b451e995b84738` | `selftest.py` |

**Mode change worth noting:** `runner.py` and `selftest.py` move `100755` → `100644`
in the hardened tree; only `_synthetic_adapter.py` stays executable. That is the
verifier's tree and it is reproduced exactly, not normalised. `oracle.py` and both
historical `evidence/` logs are byte-identical to the baseline import — the hardening
is layered in `hardened.py` rather than edited into the oracle.

The old `c8a43df6…` tree is provenance only and no longer the active package.

## 3. Adapter adapted to the revised contract

`tests/ops_adapter/` stays outside the verifier tree. Mechanical changes only:

- **`VT8-OPS-OBSERVATION-1` envelope** with `format`, `adapter_kind`, `calls`, `events`.
- **`adapter_kind` hard-coded `product`**, so the runner's synthetic/product identity
  check is meaningful rather than self-reported per run.
- **Ordered public-call results** with exactly the fields each script depends on:
  mounted side, `side_b_valid`, seek frame, record mode, feed requested/accepted, and
  every service call's `block_budget` and `more_work`. `tape_instance_size` and
  `tape_init` are harness setup, not script steps, so they are not recorded — the
  contract's sequence starts at `tape_mount`.
- **Symbolic results** for the whole `tape_result` enum, not integers.
- **Complete callback rc and range records**, including unexpected callbacks and
  nonzero returns. Nothing is filtered to make a verdict pass. Batches are
  range-checked with widened 64-bit arithmetic before any copy.
- The phase before the first public call is named `init`, deliberately outside the
  contract's allowed phase set, so block I/O during `tape_init` surfaces as a schema
  violation instead of being attributed to the following mount.
- The record script no longer calls `tape_get_info`, and the reset script no longer
  unmounts after the final remount: both would have broken the contract's exact call
  sequence.
- **`preserve.sh` removed as obsolete.** It existed because the old runner deleted its
  temporary media. The hardened runner retains input and final VO08 itself, gzipped
  and hash-bound, and `replay.py` recomputes verdicts offline from that bundle.

No assertion, fixture, expected value, case semantics, ordering, range or verifier
source was edited.

## 4. CI job added

`engine / independent VT8-001 package self-checks (synthetic, not engine acceptance)`
runs `python3 tests/ops_draft8/selftest.py`. The name and its comment both say
synthetic: no engine is built, linked or executed in that job. The known-red
`golden suite (awaiting WP-11 fixtures)` job is untouched — not hidden, not required,
not worked around.

## 5. Checks actually run

| Check | Result |
|---|---|
| `tests/ops_draft8/selftest.py` (hardened) | **PASS** — 2 conforming + **12 oracle controls** + tampered-spec + missing-evidence + tampered-evidence replay controls |
| Synthetic runner, evidence bundle creation | **2/2 PASS**, bundle at `docs/verification/runs/2026-09-12-r2/synthetic-evidence/` |
| `replay.py` offline replay of that bundle | **PASS** — evidence complete, hash-bound, DRAFT-8 authenticated, verdicts recomputed offline with no engine or adapter execution |
| Product subtree hash / modes vs verifier commit | **exact match** on all 11 files |
| `make -C tests/mount_draft8 check` | **10/10** |
| `tools/ci/verify-spec-bundle.sh` | **green**, frozen hashes unchanged |
| `tools/ci/all.sh` | build, allocation audit, indirect funnel, stack (23 fns ≤ 8 KiB), memory budgets, **meta-gate 15/15**, scaffolding — all green |
| `tools/ci/run-golden.sh` | **RED** on `no tests/golden/MANIFEST` — expected WP-11, left visible |
| Hardware suite on merged #47 | all pass; `fabrication-gate` **CLOSED, exit 2** |

## 6. Findings

**The six missing operations are unchanged.** The revised adapter compiles clean
against #20's public header and fails to link on exactly `tape_seek`, `tape_arm`,
`tape_feed`, `tape_service`, `tape_commit`, `tape_reset_side_b`. Adapting to the new
contract required no product API addition, which is itself evidence that the frozen
public surface is sufficient for this tranche.

**The adapter's observation schema has never been exercised against a real engine.**
Every PASS in this round comes from the verifier's synthetic stand-in. The product
adapter's `calls`/`events` emission was written against `ADAPTER.md` and `hardened.py`
by reading; the first product run is where it is actually tested, and it is a
reasonable place to expect schema mismatches. Flagging it rather than letting a green
synthetic suite imply the product path is proven.

**Main's public header still predates the frozen DRAFT-8 API** (`tape_mount` warm-start
parameter, `tape_tell` return, three missing `tape_info` fields), so the adapter does
not compile against main. PM decision 3 keeps this as visible debt; unchanged here.

## Residual holds

PR #20 held; §5.5 `cartridge_sequence` observability open; all six operations
unimplemented; no mount split; no allocator import; full WP-07 incl. 10,000 random
edits, complete WP-10, WP-11, WP-12a, WP-36 open; operations/state freeze open; PCM
goldens open; card atomicity, hardware safety, fabrication, charging and purchases
open; frozen DRAFT-8 hashes unchanged; WP-11 golden red visible and unrequired;
no repository setting changed. Two VT8 cases that have never run accept nothing.
