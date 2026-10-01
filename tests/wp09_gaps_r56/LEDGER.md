# WP-09 criterion ledger against DRAFT-9 (Verification #130)

The machine-readable form is `wp09-ledger.json`; `audit.py` checks that the two agree with the package.

**Authority.** Acceptance WP-09 (DRAFT-9 `ae77d13c…`) is byte-identical to DRAFT-8. The same holds for the WP-06 commit bounds WP-09 exercises, and for engine-api §7, §8 and §11.

## Dispositions

| Key | Package | Accepted Product evidence |
|---|---|---|
| RD | `record_draft8` (26) | P1-R25 (Verification #38, PR #39): exact bytes `a88850df…` for Product `9d3649d8`, engine tree `0d98ecb0`. **See the provenance section below.** |
| HI | `history_wp09_r44` (10,000 edits) | Verification #96 on Product PR #288, at `fa25ae0` |
| CAP | `capacity_wp09_r52` (27) | Verification #107 on Product PR #311. Carried to tree `4c754247`, confirmed in #131 |
| STR3 | `strengthen_r55` row 3 (27) | Verification #131 on Product PR #343 |
| SEQ | `sequential_wp06_r44` (38) | Verification #98 on Product PR #297. It is the WP-06 package, and it includes a 4,096-entry commit |

## Rows

| ID | Criterion | Status | Evidence |
|---|---|---|---|
| L01 | Overwrite, overdub and splice match their golden WAV | **listening-held** | Exact against the spec arithmetic: HI (25 checkpoints) and CAP (27 remounts). Listened goldens are WP-11. |
| L02 | Full-scale against full-scale overdub saturates at +32767/−32768 and never wraps | **partial + gap** | On HI's checkpoints, 45 saturated mixes are observed. Only **one** is full-scale against full-scale (negative); **none** is positive. RD A13 is reference arithmetic only. → `WP09.overdub.full_scale_saturation` |
| L03 | Splice at t=0 (§11) | covered | RD SP-T0; CAP splice×start; HI |
| L04 | Splice mid-run | covered | RD SP-MID; CAP splice×middle; HI |
| L05 | Splice at an exact run boundary | covered | RD SP-BOUNDARY, and only RD (see provenance) |
| L06 | Splice at end (append) | covered | RD SP-END and SP-EMPTY-B; CAP splice×end; HI |
| L07 | `tape_seek` and `tape_set_rate` while armed return BUSY | covered | RD ARMED-BUSY |
| L08 | Zero-accepted commit, 3 modes × start/middle/end: no-op; index, `total_frames` and `sequence` identical; tail renders (V5-008) | covered | RD EMPTY 3×3 and EMPTY-OW-MID |
| L09 | Commit ≤ 97 blocks | covered | SEQ (4,096 entries); RD A10; CAP C08 |
| L10 | Exactly two flushes when frames were accepted | covered | RD A10; CAP C08; SEQ; HI |
| L11 | Zero writes and zero flushes for the no-op (invariant 24) | covered | RD EMPTY; SEQ |
| L12 | CAP fixture premise (tapefs §5.5) | covered | STR3 |
| V-R55-01 | #118 row-3 clean trace meets the tapefs §8 / §9.4 floor | **gap** (verifier-owned) | → `WP10.respool_render.trace_floor` |

Result: 10 rows covered, 1 row partial with a gap, 1 row listening-held, and V-R55-01.

## Size exception

The genuine gaps plus V-R55-01 come to **2 rows**, short of the 3-row floor. This exception is recorded, not padded.

- Every other WP-09 clause has accepted Product coverage.
- Splitting L02 into a row per sign, or adding positions, would be padding: one fixture already carries every sign pair on both channels.

## Provenance: does any disposition accept exactly `c461e9e0…`? **No.**

- **What I accepted.** P1-R25 (`findings/P1-R25-WP09-DISPOSITION-2026-09-22.md`, merged by PR #39 at `e9e6ec7`) accepted exactly `a88850df6554df973fdda6071f65184fcd9012b8886c253dafbff4fc9e0966fc`. It is retained at `tests/record_draft8/evidence/p1-r25-product/`. Its `replay_product_evidence.py` authenticates that SHA by name. Before this return, no finding, test or commit in this repository named `c461e9e0`: `git log --all -S c461e9e0` was empty.
- **What Product main carries.** `tests/record_adapter/evidence/p1-r25-product/observations.jsonl` (blob `b83eb2d4`), stream `c461e9e00d47e6ae9c47827fbba68a2a796aed9b418f3aad94c6b34e3591db8f`, from Product `e4858b8` (parent `c2ccd596`).
- **The difference, measured on the evidence alone.** Both files hold the same 26 records in the same order. The only differences are in `WP09-ARMED-BUSY`, in two Software-runner presentation fields my replay ignores:
  - `errors`: `["armed BUSY/abort path issued block I/O"]` → `[]`;
  - `expected_blocked`: `true` → `false`.

  Every call, callback event, input and output hash, and every other field, is identical. The engine tree at `e4858b8` is `0d98ecb0…`, the same as at `9d3649d8`. I compared hashes; `engine/` was not opened.
- **Recommendation.** Record WP-09's RD rows as **published, with Product evidence not exactly accepted**. As the issue directs, I ran no disposition here.
  - **Behaviour.** A fresh *behavioural* disposition is not needed to establish these facts. The two bundles differ only in runner annotations, and the observations I accepted are unchanged.
  - **For a pin.** To pin, either:
    - (a) pin the accepted `a88850df…`; or
    - (b) route a **narrow identity disposition** of the exact current bytes `c461e9e0…`: authenticate, structurally diff against `a88850df…`, and replay with the corrected oracle.
  - **Currency.** Both bundles come from engine `0d98ecb0`, not the current `81ad8ec2`. Product CI regenerates this evidence into the same path without a `--retained` byte-identity check, so the committed bytes are not tied to the current engine. If PM wants WP-09 RD coverage current, the right step is a Software rebinding with `--retained` at the current engine, followed by a Verification disposition of those exact bytes.
